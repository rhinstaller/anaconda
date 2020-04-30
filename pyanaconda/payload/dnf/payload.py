# DNF/rpm software payload management.
#
# Copyright (C) 2019  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import configparser
import functools
import multiprocessing
import os
import shutil
import sys
import threading
import dnf
import dnf.logging
import dnf.exceptions
import dnf.module
import dnf.module.module_base
import dnf.repo
import dnf.subject
import libdnf.conf
import libdnf.repo
import rpm
import re
import pyanaconda.localization

from blivet.size import Size
from dnf.const import GROUP_PACKAGE_TYPES
from fnmatch import fnmatch
from glob import glob

from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, KS_MISSING_IGNORE, KS_BROKEN_IGNORE, \
    GROUP_REQUIRED
from pykickstart.parser import Group

from pyanaconda import errors as errors
from pyanaconda import isys
from pyanaconda.anaconda_loggers import get_dnf_logger, get_packaging_logger
from pyanaconda.core import constants, util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import INSTALL_TREE, ISO_DIR, DRACUT_REPODIR, DRACUT_ISODIR, \
    PAYLOAD_TYPE_DNF
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.payload import parse_nfs_url
from pyanaconda.core.regexes import VERSION_DIGITS
from pyanaconda.core.util import ProxyString, ProxyStringError, decode_bytes
from pyanaconda.flags import flags
from pyanaconda.kickstart import RepoData
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import LOCALIZATION, STORAGE
from pyanaconda.modules.common.errors.storage import MountFilesystemError, DeviceSetupError
from pyanaconda.modules.payloads.source.utils import is_valid_install_disk
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.base import Payload
from pyanaconda.payload.dnf.utils import DNF_CACHE_DIR, DNF_PLUGINCONF_DIR, REPO_DIRS, \
    DNF_LIBREPO_LOG, DNF_PACKAGE_CACHE_DIR_SUFFIX, BONUS_SIZE_ON_FILE, YUM_REPOS_DIR, \
    go_to_failure_limbo, do_transaction, get_df_map, pick_mount_point
from pyanaconda.payload.dnf.download_progress import DownloadProgress
from pyanaconda.payload.dnf.repomd import RepoMDMetaHash
from pyanaconda.payload.errors import MetadataError, PayloadError, NoSuchGroup, DependencyError, \
    PayloadInstallError, PayloadSetupError
from pyanaconda.payload.image import find_first_iso_image, mountImage, verify_valid_installtree, \
    find_optical_install_media
from pyanaconda.payload.install_tree_metadata import InstallTreeMetadata
from pyanaconda.product import productName, productVersion
from pyanaconda.progress import progressQ, progress_message
from pyanaconda.simpleconfig import SimpleConfigFile

log = get_packaging_logger()

USER_AGENT = "%s (anaconda)/%s" % (productName, productVersion)

__all__ = ["DNFPayload"]


class DNFPayload(Payload):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.install_device = None
        self.tx_id = None

        self._install_tree_metadata = None
        self._rpm_macros = []

        # Used to determine which add-ons to display for each environment.
        # The dictionary keys are environment IDs. The dictionary values are two-tuples
        # consisting of lists of add-on group IDs. The first list is the add-ons specific
        # to the environment, and the second list is the other add-ons possible for the
        # environment.
        self._environment_addons = {}

        self._base = None
        self._download_location = None
        self._updates_enabled = True
        self._configure()

        # Protect access to _base.repos to ensure that the dictionary is not
        # modified while another thread is attempting to iterate over it. The
        # lock only needs to be held during operations that change the number
        # of repos or that iterate over the repos.
        self._repos_lock = threading.RLock()

        # save repomd metadata
        self._repoMD_list = []

        self._req_groups = set()
        self._req_packages = set()
        self.requirements.set_apply_callback(self._apply_requirements)

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_DNF

    @property
    def is_hmc_enabled(self):
        return self.data.method.method == "hmc"

    def is_ready(self):
        """Is the payload ready?"""
        return self.base_repo is not None

    def unsetup(self):
        super().unsetup()
        self._base = None
        self._configure()
        self._repoMD_list = []
        self._install_tree_metadata = None

    @property
    def needs_network(self):
        """Test base and additional repositories if they require network."""
        url = ""
        if self.data.method.method is None:
            # closest mirror set
            return True
        elif self.data.method.method == "nfs":
            # NFS is always on network
            return True
        elif self.data.method.method == "url":
            if self.data.url.url:
                url = self.data.url.url
            elif self.data.url.mirrorlist:
                url = self.data.url.mirrorlist
            elif self.data.url.metalink:
                url = self.data.url.metalink

        return (self._source_needs_network([url]) or
                any(self._repo_needs_network(repo) for repo in self.data.repo.dataList()))

    def _repo_needs_network(self, repo):
        """Returns True if the ksdata repo requires networking."""
        urls = [repo.baseurl]
        if repo.mirrorlist:
            urls.extend(repo.mirrorlist)
        elif repo.metalink:
            urls.extend(repo.metalink)
        return self._source_needs_network(urls)

    def _source_needs_network(self, sources):
        """Return True if the source requires network.

        :param sources: Source paths for testing
        :type sources: list
        :returns: True if any source requires network
        """
        network_protocols = ["http:", "ftp:", "nfs:", "nfsiso:"]
        for s in sources:
            if s and any(s.startswith(p) for p in network_protocols):
                log.debug("Source %s needs network for installation", s)
                return True

        log.debug("Source doesn't require network for installation")
        return False

    def _replace_vars(self, url):
        """Replace url variables with their values.

        :param url: url string to do replacement on
        :type url:  string
        :returns:   string with variables substituted
        :rtype:     string or None

        Currently supports $releasever and $basearch.
        """
        if url:
            return libdnf.conf.ConfigParser.substitute(url, self._base.conf.substitutions)

        return None

    def _add_repo(self, ksrepo):
        """Add a repo to the dnf repo object.

        :param ksrepo: Kickstart Repository to add
        :type ksrepo: Kickstart RepoData object.
        :returns: None
        """
        repo = dnf.repo.Repo(ksrepo.name, self._base.conf)
        url = self._replace_vars(ksrepo.baseurl)
        mirrorlist = self._replace_vars(ksrepo.mirrorlist)
        metalink = self._replace_vars(ksrepo.metalink)

        if url and url.startswith("nfs://"):
            (server, path) = url[6:].split(":", 1)
            # DNF is dynamically creating properties which seems confusing for Pylint here
            # pylint: disable=no-member
            mountpoint = "%s/%s.nfs" % (constants.MOUNT_DIR, repo.name)
            self._setup_NFS(mountpoint, server, path, None)

            url = "file://" + mountpoint

        if url:
            repo.baseurl = [url]
        if mirrorlist:
            repo.mirrorlist = mirrorlist
        if metalink:
            repo.metalink = metalink
        repo.sslverify = not ksrepo.noverifyssl and conf.payload.verify_ssl
        if ksrepo.proxy:
            try:
                repo.proxy = ProxyString(ksrepo.proxy).url
            except ProxyStringError as e:
                log.error("Failed to parse proxy for _add_repo %s: %s",
                          ksrepo.proxy, e)

        if ksrepo.cost:
            repo.cost = ksrepo.cost

        if ksrepo.includepkgs:
            repo.include = ksrepo.includepkgs

        if ksrepo.excludepkgs:
            repo.exclude = ksrepo.excludepkgs

        if ksrepo.sslcacert:
            repo.sslcacert = ksrepo.sslcacert

        if ksrepo.sslclientcert:
            repo.sslclientcert = ksrepo.sslclientcert

        if ksrepo.sslclientkey:
            repo.sslclientkey = ksrepo.sslclientkey

        # If this repo is already known, it's one of two things:
        # (1) The user is trying to do "repo --name=updates" in a kickstart file
        #     and we should just know to enable the already existing on-disk
        #     repo config.
        # (2) It's a duplicate, and we need to delete the existing definition
        #     and use this new one.  The highest profile user of this is livecd
        #     kickstarts.
        if repo.id in self._base.repos:
            if not url and not mirrorlist and not metalink:
                self._base.repos[repo.id].enable()
            else:
                with self._repos_lock:
                    self._base.repos.pop(repo.id)
                    self._base.repos.add(repo)
        # If the repo's not already known, we've got to add it.
        else:
            with self._repos_lock:
                self._base.repos.add(repo)

        if not ksrepo.enabled:
            self.disable_repo(repo.id)

        log.info("added repo: '%s' - %s", ksrepo.name, url or mirrorlist or metalink)

    def _fetch_md(self, repo_name):
        """Download repo metadata

        :param repo_name: name/id of repo to fetch
        :type repo_name: str
        :returns: None
        """
        repo = self._base.repos[repo_name]
        repo.enable()
        try:
            # Load the metadata to verify that the repo is valid
            repo.load()
        except dnf.exceptions.RepoError as e:
            repo.disable()
            log.debug("repo: '%s' - %s failed to load repomd", repo.id,
                     repo.baseurl or repo.mirrorlist or repo.metalink)
            raise MetadataError(e)

        log.info("enabled repo: '%s' - %s and got repomd", repo.id,
                 repo.baseurl or repo.mirrorlist or repo.metalink)

    def add_repo(self, ksrepo):
        """Add an enabled repo to dnf and kickstart repo lists.

        Add the repo given by the pykickstart Repo object ksrepo to the
        system.  The repo will be automatically enabled and its metadata
        fetched.

        Duplicate repos will not raise an error.  They should just silently
        take the place of the previous value.

        :param ksrepo: Kickstart Repository to add
        :type ksrepo: Kickstart RepoData object.
        :returns: None
        """
        self._add_repo(ksrepo)
        self._fetch_md(ksrepo.name)

        # Add the repo to the ksdata so it'll appear in the output ks file.
        ksrepo.enabled = True
        self.data.repo.dataList().append(ksrepo)

    def _process_module_command(self):
        """Enable/disable modules (if any)."""
        # convert data from kickstart to module specs
        module_specs_to_enable = []
        module_specs_to_disable = []
        for module in self.data.module.dataList():
            # stream definition is optional
            if module.stream:
                module_spec = "{name}:{stream}".format(
                    name=module.name,
                    stream=module.stream
                )
            else:
                module_spec = module.name

            if module.enable:
                module_specs_to_enable.append(module_spec)
            else:
                module_specs_to_disable.append(module_spec)

        # forward the module specs to disable to DNF
        log.debug("disabling modules: %s", module_specs_to_disable)
        try:
            module_base = dnf.module.module_base.ModuleBase(self._base)
            module_base.disable(module_specs_to_disable)
        except dnf.exceptions.MarkingErrors as e:
            log.debug(
                "ModuleBase.disable(): some packages, groups "
                "or modules are missing or broken:\n%s", e
            )
            self._payload_setup_error(e)

        # forward the module specs to enable to DNF
        log.debug("enabling modules: %s", module_specs_to_enable)
        try:
            module_base = dnf.module.module_base.ModuleBase(self._base)
            module_base.enable(module_specs_to_enable)
        except dnf.exceptions.MarkingErrors as e:
            log.debug("ModuleBase.enable(): some packages, groups "
                      "or modules are missing or broken:\n%s", e)
            self._payload_setup_error(e)

    def _apply_selections(self):
        log.debug("applying DNF package/group/module selection")

        # note about package/group/module spec formatting:
        # - leading @ signifies a group or module
        # - no leading @ means a package

        include_list = []
        exclude_list = []

        # handle "normal" groups
        for group in self.data.packages.excludedGroupList:
            log.debug("excluding group %s", group.name)
            exclude_list.append("@{}".format(group.name))

        # core groups
        if self.data.packages.nocore:
            log.info("skipping core group due to %%packages "
                     "--nocore; system may not be complete")
            exclude_list.append("@core")
        else:
            log.info("selected group: core")
            include_list.append("@core")

        # environment
        env = None
        if self.data.packages.default and self.environments:
            env = self.environments[0]
            log.info("selecting default environment: %s", env)
        elif self.data.packages.environment:
            env = self.data.packages.environment
            log.info("selected environment: %s", env)
        if env:
            include_list.append("@{}".format(env))

        # groups from kickstart data
        for group in self.data.packages.groupList:
            default = group.include in (GROUP_ALL,
                                        GROUP_DEFAULT)
            optional = group.include == GROUP_ALL

            # Packages in groups can have different types
            # and we provide an option to users to set
            # which types are going to be installed
            # via the --nodefaults and --optional options.
            #
            # To not clash with module definitions we
            # only use type specififcations if --nodefault,
            # --optional or both are used
            if not default or optional:
                type_list = list(GROUP_PACKAGE_TYPES)
                if not default:
                    type_list.remove("default")
                if optional:
                    type_list.append("optional")

                types = ",".join(type_list)
                group_spec = "@{group_name}/{types}".format(
                    group_name=group.name,
                    types=types
                )
            else:
                # if group is a regular group this is equal to
                # @group/mandatory,default,conditional (current
                # content of the DNF GROUP_PACKAGE_TYPES constant)
                group_spec = "@{}".format(group.name)

            include_list.append(group_spec)

        # handle packages
        for pkg_name in self.data.packages.excludedList:
            log.info("excluded package: '%s'", pkg_name)
            exclude_list.append(pkg_name)

        for pkg_name in self.data.packages.packageList:
            log.info("selected package: '%s'", pkg_name)
            include_list.append(pkg_name)

        # add kernel package
        kernel_package = self._get_kernel_package()
        if kernel_package:
            include_list.append(kernel_package)

        # resolve packages and groups required by Anaconda
        self.requirements.apply()

        # add required groups
        for group_name in self._req_groups:
            include_list.append("@{}".format(group_name))
        # add packages
        include_list.extend(self._req_packages)

        # log the resulting set
        log.debug("transaction include list")
        log.debug(include_list)
        log.debug("transaction exclude list")
        log.debug(exclude_list)

        # feed it to DNF
        try:
            # FIXME: Remove self._base.conf.strict workaround when bz1761518 is fixed
            # install_specs() returns a list of specs that appear to be missing
            self._base.install_specs(install=include_list, exclude=exclude_list,
                                     strict=self._base.conf.strict)
        except dnf.exceptions.MarkingErrors as e:
            log.debug("install_specs(): some packages, groups or modules "
                      " are missing or broken:\n%s", e)
            # if no errors were reported and --ignoremissing was used we can continue
            transaction_broken = e.error_group_specs or \
                e.error_pkg_specs or \
                e.module_depsolv_errors
            if not transaction_broken and self.data.packages.handleMissing == KS_MISSING_IGNORE:
                log.info("ignoring missing package/group/module "
                         "specs due to --ignoremissing flag in kickstart")
            else:
                self._payload_setup_error(e)
        except Exception as e:  # pylint: disable=broad-except
            self._payload_setup_error(e)

    def _apply_requirements(self, requirements):
        self._req_groups = set()
        self._req_packages = set()
        for req in self.requirements.packages:
            ignore_msgs = []
            if req.id in conf.payload.ignored_packages:
                ignore_msgs.append("IGNORED by the configuration.")
            if req.id in self.data.packages.excludedList:
                ignore_msgs.append("IGNORED because excluded")
            if not ignore_msgs:
                # NOTE: req.strong not handled yet
                self._req_packages.add(req.id)
            log.debug("selected package: %s, requirement for %s %s",
                      req.id, req.reasons, ", ".join(ignore_msgs))

        for req in self.requirements.groups:
            # NOTE: req.strong not handled yet
            log.debug("selected group: %s, requirement for %s",
                      req.id, req.reasons)
            self._req_groups.add(req.id)

        return True

    def _bump_tx_id(self):
        if self.tx_id is None:
            self.tx_id = 1
        else:
            self.tx_id += 1
        return self.tx_id

    def _configure_proxy(self):
        """Configure the proxy on the dnf.Base object."""
        config = self._base.conf

        if hasattr(self.data.method, "proxy") and self.data.method.proxy:
            try:
                proxy = ProxyString(self.data.method.proxy)
                config.proxy = proxy.noauth_url
                if proxy.username:
                    config.proxy_username = proxy.username
                if proxy.password:
                    config.proxy_password = proxy.password
                log.info("Using %s as proxy", self.data.method.proxy)
            except ProxyStringError as e:
                log.error("Failed to parse proxy for dnf configure %s: %s",
                          self.data.method.proxy, e)
        else:
            # No proxy configured
            config.proxy = None
            config.proxy_username = None
            config.proxy_password = None

    def get_platform_id(self):
        """Obtain the platform id (if available).

        At the moment we get the platform id from /etc/os-release
        but treeinfo or something similar that maps to the current
        repository looks like a better bet longer term.

        :return: platform id or None if not found
        :rtype: str or None
        """
        platform_id = None
        if os.path.exists("/etc/os-release"):
            config = SimpleConfigFile()
            config.read("/etc/os-release")
            os_release_platform_id = config.get("PLATFORM_ID")
            # simpleconfig return "" for keys that are not found
            if os_release_platform_id:
                platform_id = os_release_platform_id
            else:
                log.error("PLATFORM_ID missing from /etc/os-release")
        else:
            log.error("/etc/os-release is missing, platform id can't be obtained")
        return platform_id

    def _configure(self):
        self._base = dnf.Base()
        config = self._base.conf
        config.cachedir = DNF_CACHE_DIR
        config.pluginconfpath = DNF_PLUGINCONF_DIR
        config.logdir = '/tmp/'
        # enable depsolver debugging if in debug mode
        self._base.conf.debug_solver = flags.debug
        # set the platform id based on the /os/release
        # present in the installation environment
        platform_id = self.get_platform_id()
        if platform_id is not None:
            log.info("setting DNF platform id to: %s", platform_id)
            self._base.conf.module_platform_id = platform_id

        config.releasever = self._get_release_version(None)
        config.installroot = conf.target.system_root
        config.prepend_installroot('persistdir')

        self._base.conf.substitutions.update_from_etc(config.installroot)

        if self.data.packages.multiLib:
            config.multilib_policy = "all"

        if self.data.packages.timeout is not None:
            config.timeout = self.data.packages.timeout

        if self.data.packages.retries is not None:
            config.retries = self.data.packages.retries

        if self.data.packages.handleBroken == KS_BROKEN_IGNORE:
            log.warning(
                "\n*********************************************************************\n"
                "User has requested to skip broken packages. Using this option may result "
                "in an UNUSABLE system!\n"
                "*********************************************************************"
            )
            config.strict = False

        self._configure_proxy()

        # Start with an empty comps so we can go ahead and use the environment
        # and group properties. Unset reposdir to ensure dnf has nothing it can
        # check automatically
        config.reposdir = []
        self._base.read_comps(arch_filter=True)

        config.reposdir = REPO_DIRS

        # Two reasons to turn this off:
        # 1. Minimal installs don't want all the extras this brings in.
        # 2. Installs aren't reproducible due to weak deps. failing silently.
        if self.data.packages.excludeWeakdeps:
            config.install_weak_deps = False

        # Setup librepo logging
        libdnf.repo.LibrepoLog.removeAllHandlers()
        libdnf.repo.LibrepoLog.addHandler(DNF_LIBREPO_LOG)

        # Increase dnf log level to custom DDEBUG level
        # Do this here to prevent import side-effects in anaconda_logging
        dnf_logger = get_dnf_logger()
        dnf_logger.setLevel(dnf.logging.DDEBUG)

        log.debug("Dnf configuration:\n%s", config.dump())

    @property
    def _download_space(self):
        transaction = self._base.transaction
        if transaction is None:
            return Size(0)

        size = sum(tsi.pkg.downloadsize for tsi in transaction)
        # reserve extra
        return Size(size) + Size("150 MB")

    def _payload_setup_error(self, exn):
        log.error('Payload setup error: %r', exn)
        if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
            # The progress bar polls kind of slowly, thus installation could
            # still continue for a bit before the quit message is processed.
            # Doing a sys.exit also ensures the running thread quits before
            # it can do anything else.
            progressQ.send_quit(1)
            util.ipmi_abort(scripts=self.data.scripts)
            sys.exit(1)

    def _pick_download_location(self):
        download_size = self._download_space
        install_size = self._space_required()
        df_map = get_df_map()
        mpoint = pick_mount_point(
            df_map,
            download_size,
            install_size,
            download_only=True
        )
        if mpoint is None:
            msg = ("Not enough disk space to download the "
                   "packages; size %s." % download_size)
            raise PayloadError(msg)

        log.info("Mountpoint %s picked as download location", mpoint)
        pkgdir = '%s/%s' % (mpoint, DNF_PACKAGE_CACHE_DIR_SUFFIX)
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                repo.pkgdir = pkgdir

        return pkgdir

    def _package_name_installable(self, package_name):
        """Check if the given package name looks instalable."""
        subj = dnf.subject.Subject(package_name)
        return bool(subj.get_best_query(self._base.sack))

    @property
    def kernel_packages(self):
        if "kernel" in self.data.packages.excludedList:
            return []

        kernels = ["kernel"]

        if payload_utils.arch_is_x86() and isys.isPaeAvailable():
            kernels.insert(0, "kernel-PAE")

        # ARM systems use either the standard Multiplatform or LPAE platform
        if payload_utils.arch_is_arm():
            if isys.isLpaeAvailable():
                kernels.insert(0, "kernel-lpae")

        return kernels

    def _get_kernel_package(self):
        kernels = self.kernel_packages
        selected_kernel_package = None
        for kernel_package in kernels:
            if self._package_name_installable(kernel_package):
                log.info('kernel: selected %s', kernel_package)
                selected_kernel_package = kernel_package
                break  # one kernel is good enough
            else:
                log.info('kernel: no such package %s', kernel_package)
        else:
            log.error('kernel: failed to select a kernel from %s', kernels)
        return selected_kernel_package

    def langpacks(self):
        # get all available languages in repos
        available_langpacks = self._base.sack.query().available() \
            .filter(name__glob="langpacks-*")
        alangs = [p.name.split('-', 1)[1] for p in available_langpacks]

        langpacks = []
        # add base langpacks into transaction
        localization_proxy = LOCALIZATION.get_proxy()
        for lang in [localization_proxy.Language] + localization_proxy.LanguageSupport:
            loc = pyanaconda.localization.find_best_locale_match(lang, alangs)
            if not loc:
                log.warning("Selected lang %s does not match "
                            "any available langpack", lang)
                continue
            langpacks.append("langpacks-" + loc)
        return langpacks

    def _sync_metadata(self, dnf_repo):
        try:
            dnf_repo.load()
        except dnf.exceptions.RepoError as e:
            id_ = dnf_repo.id
            log.info('_sync_metadata: addon repo error: %s', e)
            self.disable_repo(id_)
            self.verbose_errors.append(str(e))
        log.debug('repo %s: _sync_metadata success from %s', dnf_repo.id,
                  dnf_repo.baseurl or dnf_repo.mirrorlist or dnf_repo.metalink)

    @property
    def base_repo(self):
        """Get the identifier of the current base repo or None."""
        # is any locking needed here?
        repo_names = [constants.BASE_REPO_NAME] + constants.DEFAULT_REPOS
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                if repo.id in repo_names:
                    return repo.id
        return None

    ###
    # METHODS FOR WORKING WITH ENVIRONMENTS
    ###

    @property
    def environments(self):
        return [env.id for env in self._base.comps.environments]

    def select_environment(self, environment_id):
        if environment_id not in self.environments:
            raise NoSuchGroup(environment_id)

        self.data.packages.environment = environment_id

    @property
    def environment_addons(self):
        return self._environment_addons

    ###
    # METHODS FOR WORKING WITH GROUPS
    ###

    @property
    def groups(self):
        groups = self._base.comps.groups_iter()
        return [g.id for g in groups]

    def selected_groups(self):
        """Return list of selected group names from kickstart.

        NOTE:
        This group names can be mix of group IDs and other valid identifiers.
        If you want group IDs use `selected_groups_IDs` instead.

        :return: list of group names in a format specified by a kickstart file.
        """
        return [grp.name for grp in self.data.packages.groupList]

    def selected_groups_IDs(self):
        """Return list of IDs for selected groups.

        :return: List of selected group IDs.
        :raise PayloadError: If translation is not supported by payload.
        """
        # pylint: disable=try-except-raise
        try:
            ret = []
            for grp in self.selected_groups():
                ret.append(self.group_id(grp))
            return ret
        # Translation feature is not implemented for this payload.
        except NotImplementedError:
            raise PayloadError(("Can't translate group names to group ID - "
                                "Group translation is not implemented for %s payload." % self))
        except PayloadError as ex:
            raise PayloadError("Can't translate group names to group ID - {}".format(ex))

    def group_selected(self, groupid):
        return Group(groupid) in self.data.packages.groupList

    def select_group(self, groupid, default=True, optional=False):
        if optional:
            include = GROUP_ALL
        elif default:
            include = GROUP_DEFAULT
        else:
            include = GROUP_REQUIRED

        grp = Group(groupid, include=include)

        if grp in self.data.packages.groupList:
            # I'm not sure this would ever happen, but ensure that re-selecting
            # a group with a different types set works as expected.
            if grp.include != include:
                grp.include = include

            return

        if grp in self.data.packages.excludedGroupList:
            self.data.packages.excludedGroupList.remove(grp)

        self.data.packages.groupList.append(grp)

    def deselect_group(self, groupid):
        grp = Group(groupid)

        if grp in self.data.packages.excludedGroupList:
            return

        if grp in self.data.packages.groupList:
            self.data.packages.groupList.remove(grp)

        self.data.packages.excludedGroupList.append(grp)

    ###
    # METHODS FOR WORKING WITH REPOSITORIES
    ###

    @property
    def repos(self):
        """A list of repo identifiers, not objects themselves."""
        with self._repos_lock:
            return [r.id for r in self._base.repos.values()]

    @property
    def addons(self):
        """A list of addon repo names."""
        return [r.name for r in self.data.repo.dataList()]

    @property
    def mirrors_available(self):
        """Is the closest/fastest mirror option enabled?  This does not make
        sense for those payloads that do not support this concept.
        """
        return conf.payload.enable_closest_mirror

    @property
    def disabled_repos(self):
        """A list of names of the disabled repos."""
        disabled = []
        for repo in self.addons:
            if not self.is_repo_enabled(repo):
                disabled.append(repo)

        return disabled

    @property
    def enabled_repos(self):
        """A list of names of the enabled repos."""
        enabled = []
        for repo in self.addons:
            if self.is_repo_enabled(repo):
                enabled.append(repo)

        return enabled

    def get_addon_repo(self, repo_id):
        """Return a ksdata Repo instance matching the specified repo id."""
        repo = None
        for r in self.data.repo.dataList():
            if r.name == repo_id:
                repo = r
                break

        return repo

    def add_disabled_repo(self, ksrepo):
        """Add the repo given by the pykickstart Repo object ksrepo to the
        list of known repos.  The repo will be automatically disabled.

        Duplicate repos will not raise an error.  They should just silently
        take the place of the previous value.
        """
        ksrepo.enabled = False
        self.data.repo.dataList().append(ksrepo)

    def remove_repo(self, repo_id):
        repos = self.data.repo.dataList()
        try:
            idx = [repo.name for repo in repos].index(repo_id)
        except ValueError:
            log.error("failed to remove repo %s: not found", repo_id)
        else:
            repos.pop(idx)

    def add_driver_repos(self):
        """Add driver repositories and packages."""
        # Drivers are loaded by anaconda-dracut, their repos are copied
        # into /run/install/DD-X where X is a number starting at 1. The list of
        # packages that were selected is in /run/install/dd_packages

        # Add repositories
        dir_num = 0
        while True:
            dir_num += 1
            repo = "/run/install/DD-%d/" % dir_num
            if not os.path.isdir(repo):
                break

            # Run createrepo if there are rpms and no repodata
            if not os.path.isdir(repo + "/repodata"):
                rpms = glob(repo + "/*rpm")
                if not rpms:
                    continue
                log.info("Running createrepo on %s", repo)
                util.execWithRedirect("createrepo_c", [repo])

            repo_name = "DD-%d" % dir_num
            if repo_name not in self.addons:
                ks_repo = self.data.RepoData(name=repo_name,
                                             baseurl="file://" + repo,
                                             enabled=True)
                self.add_repo(ks_repo)

        # Add packages
        if not os.path.exists("/run/install/dd_packages"):
            return
        with open("/run/install/dd_packages", "r") as f:
            for line in f:
                package = line.strip()
                self.requirements.add_packages([package], reason="driver disk")

    @property
    def ISO_image(self):
        """The location of a mounted ISO repo, or None."""
        if not self.data.method.method == "harddrive":
            return None

        # This could either be mounted to INSTALL_TREE or on
        # DRACUT_ISODIR if dracut did the mount.
        device_path = payload_utils.get_mount_device_path(INSTALL_TREE)
        if device_path:
            return device_path[len(ISO_DIR) + 1:]

        device_path = payload_utils.get_mount_device_path(DRACUT_ISODIR)
        if device_path:
            return device_path[len(DRACUT_ISODIR) + 1:]

        return None

    @property
    def space_required(self):
        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        size = self._space_required()
        download_size = self._download_space
        valid_points = get_df_map()
        root_mpoint = conf.target.system_root

        for key in payload_utils.get_mount_points():
            new_key = key
            if key.endswith('/'):
                new_key = key[:-1]
            # we can ignore swap
            if key.startswith('/') and ((root_mpoint + new_key) not in valid_points):
                valid_points[root_mpoint + new_key] = device_tree.GetFileSystemFreeSpace([key])

        m_point = pick_mount_point(valid_points, download_size, size, download_only=False)
        if not m_point or m_point == root_mpoint:
            # download and install to the same mount point
            size = size + download_size
            log.debug("Install + download space required %s", size)
        else:
            log.debug("Download space required %s for mpoint %s (non-chroot)",
                      download_size, m_point)
            log.debug("Installation space required %s", size)
        return size

    def _space_required(self):
        transaction = self._base.transaction
        if transaction is None:
            return Size("3000 MB")

        size = 0
        files_nm = 0
        for tsi in transaction:
            # space taken by all files installed by the packages
            size += tsi.pkg.installsize
            # number of files installed on the system
            files_nm += len(tsi.pkg.files)

        # append bonus size depending on number of files
        bonus_size = files_nm * BONUS_SIZE_ON_FILE
        size = Size(size)
        # add another 10% as safeguard
        total_space = (size + bonus_size) * 1.1
        log.debug("Size from DNF: %s", size)
        log.debug("Bonus size %s by number of files %s", bonus_size, files_nm)
        log.debug("Total size required %s", total_space)
        return total_space

    def _is_group_visible(self, grpid):
        grp = self._base.comps.group_by_pattern(grpid)
        if grp is None:
            raise NoSuchGroup(grpid)
        return grp.visible

    def check_software_selection(self):
        log.info("checking software selection")
        self._bump_tx_id()
        self._base.reset(goal=True)
        self._process_module_command()
        self._apply_selections()

        try:
            if self._base.resolve():
                log.info("checking dependencies: success")
            else:
                log.info("empty transaction")
        except dnf.exceptions.DepsolveError as e:
            msg = str(e)
            log.warning(msg)
            raise DependencyError(msg)

        log.info("%d packages selected totalling %s",
                 len(self._base.transaction), self.space_required)

    def set_updates_enabled(self, state):
        """Enable or Disable the repos used to update closest mirror.

        :param bool state: True to enable updates, False to disable.
        """
        self._updates_enabled = state

        # Enable or disable updates.
        if self._updates_enabled:
            for repo in constants.DEFAULT_UPDATE_REPOS:
                self.enable_repo(repo)
        else:
            for repo in constants.DEFAULT_UPDATE_REPOS:
                self.disable_repo(repo)

        # Disable updates-testing.
        self.disable_repo("updates-testing")
        self.disable_repo("updates-testing-modular")

    def disable_repo(self, repo_id):
        try:
            self._base.repos[repo_id].disable()
            log.info("Disabled '%s'", repo_id)
        except KeyError:
            pass

        repo = self.get_addon_repo(repo_id)
        if repo:
            repo.enabled = False

    def enable_repo(self, repo_id):
        try:
            self._base.repos[repo_id].enable()
            log.info("Enabled '%s'", repo_id)
        except KeyError:
            pass

        repo = self.get_addon_repo(repo_id)
        if repo:
            repo.enabled = True

    def environment_description(self, environment_id):
        env = self._base.comps.environment_by_pattern(environment_id)
        if env is None:
            raise NoSuchGroup(environment_id)
        return (env.ui_name, env.ui_description)

    def environment_id(self, environment):
        """Return environment id for the environment specified by id or name."""
        # the enviroment must be string or else DNF >=3 throws an assert error
        if not isinstance(environment, str):
            log.warning("environment_id() called with non-string "
                        "argument: %s", environment)

        env = self._base.comps.environment_by_pattern(environment)

        if env is None:
            raise NoSuchGroup(environment)

        return env.id

    def environment_has_option(self, environment_id, grpid):
        env = self._base.comps.environment_by_pattern(environment_id)
        if env is None:
            raise NoSuchGroup(environment_id)
        return grpid in (id_.name for id_ in env.option_ids)

    def environment_option_is_default(self, environment_id, grpid):
        env = self._base.comps.environment_by_pattern(environment_id)
        if env is None:
            raise NoSuchGroup(environment_id)

        # Look for a group in the optionlist that matches the group_id and has
        # default set
        return any(grp for grp in env.option_ids if grp.name == grpid and grp.default)

    def group_description(self, grpid):
        """Return name/description tuple for the group specified by id."""
        grp = self._base.comps.group_by_pattern(grpid)
        if grp is None:
            raise NoSuchGroup(grpid)
        return (grp.ui_name, grp.ui_description)

    def group_id(self, group_name):
        """Translate group name to group ID.

        :param group_name: Valid identifier for group specification.
        :returns: Group ID.
        :raise NoSuchGroup: If group_name doesn't exists.
        :raise PayloadError: When Yum's groups are not available.
        """
        grp = self._base.comps.group_by_pattern(group_name)
        if grp is None:
            raise NoSuchGroup(group_name)
        return grp.id

    def gather_repo_metadata(self):
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                self._sync_metadata(repo)
        self._base.fill_sack(load_system_repo=False)
        self._base.read_comps(arch_filter=True)
        self._refresh_environment_addons()

    def _refresh_environment_addons(self):
        log.info("Refreshing environment_addons")
        self._environment_addons = {}

        for environment in self.environments:
            self._environment_addons[environment] = ([], [])

            # Determine which groups are specific to this environment and which other groups
            # are available in this environment.
            for grp in self.groups:
                if self.environment_has_option(environment, grp):
                    self._environment_addons[environment][0].append(grp)
                elif self._is_group_visible(grp):
                    self._environment_addons[environment][1].append(grp)

    @property
    def rpm_macros(self):
        """A list of (name, value) pairs to define as macros in the rpm transaction."""
        return self._rpm_macros

    @rpm_macros.setter
    def rpm_macros(self, value):
        self._rpm_macros = value

    def pre_install(self):
        super().pre_install()

        # Set rpm-specific options

        # nofsync speeds things up at the risk of rpmdb data loss in a crash.
        # But if we crash mid-install you're boned anyway, so who cares?
        self.rpm_macros.append(('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'))

        if self.data.packages.excludeDocs:
            self.rpm_macros.append(('_excludedocs', '1'))

        if self.data.packages.instLangs is not None:
            # Use nil if instLangs is empty
            self.rpm_macros.append(('_install_langs', self.data.packages.instLangs or '%{nil}'))

        if conf.security.selinux:
            for d in ["/tmp/updates",
                      "/etc/selinux/targeted/contexts/files",
                      "/etc/security/selinux/src/policy",
                      "/etc/security/selinux"]:
                f = d + "/file_contexts"
                if os.access(f, os.R_OK):
                    self.rpm_macros.append(('__file_context_path', f))
                    break
        else:
            self.rpm_macros.append(('__file_context_path', '%{nil}'))

        # Add platform specific group
        groupid = util.get_platform_groupid()
        if groupid and groupid in self.groups:
            self.requirements.add_groups([groupid], reason="platform")
        elif groupid:
            log.warning("Platform group %s not available.", groupid)

    def install(self):
        progress_message(N_('Starting package installation process'))

        # Add the rpm macros to the global transaction environment
        for macro in self.rpm_macros:
            rpm.addMacro(macro[0], macro[1])

        if self.install_device:
            self._setup_media(self.install_device)
        try:
            self.check_software_selection()
            self._download_location = self._pick_download_location()
        except PayloadError as e:
            if errors.errorHandler.cb(e) == errors.ERROR_RAISE:
                log.error("Installation failed: %r", e)
                go_to_failure_limbo()

        if os.path.exists(self._download_location):
            log.info("Removing existing package download "
                     "location: %s", self._download_location)
            shutil.rmtree(self._download_location)
        pkgs_to_download = self._base.transaction.install_set
        log.info('Downloading packages to %s.', self._download_location)
        progressQ.send_message(_('Downloading packages'))
        progress = DownloadProgress()
        try:
            self._base.download_packages(pkgs_to_download, progress)
        except dnf.exceptions.DownloadError as e:
            msg = 'Failed to download the following packages: %s' % str(e)
            exc = PayloadInstallError(msg)
            if errors.errorHandler.cb(exc) == errors.ERROR_RAISE:
                log.error("Installation failed: %r", exc)
                go_to_failure_limbo()

        log.info('Downloading packages finished.')

        pre_msg = (N_("Preparing transaction from installation source"))
        progress_message(pre_msg)

        queue_instance = multiprocessing.Queue()
        process = multiprocessing.Process(target=do_transaction,
                                          args=(self._base, queue_instance))
        process.start()
        (token, msg) = queue_instance.get()
        # When the installation works correctly it will get 'install' updates
        # followed by a 'post' message and then a 'quit' message.
        # If the installation fails it will send 'quit' without 'post'
        while token:
            if token == 'install':
                msg = _("Installing %s") % msg
                progressQ.send_message(msg)
            elif token == 'configure':
                msg = _("Configuring %s") % msg
                progressQ.send_message(msg)
            elif token == 'verify':
                msg = _("Verifying %s") % msg
                progressQ.send_message(msg)
            elif token == 'log':
                log.info(msg)
            elif token == 'post':
                msg = (N_("Performing post-installation setup tasks"))
                progressQ.send_message(msg)
            elif token == 'done':
                break  # Installation finished successfully
            elif token == 'quit':
                msg = ("Payload error - DNF installation has ended up abruptly: %s" % msg)
                raise PayloadError(msg)
            elif token == 'error':
                exc = PayloadInstallError("DNF error: %s" % msg)
                if errors.errorHandler.cb(exc) == errors.ERROR_RAISE:
                    log.error("Installation failed: %r", exc)
                    go_to_failure_limbo()
            (token, msg) = queue_instance.get()

        process.join()
        # Don't close the mother base here, because we still need it.
        if os.path.exists(self._download_location):
            log.info("Cleaning up downloaded packages: "
                     "%s", self._download_location)
            shutil.rmtree(self._download_location)
        else:
            # Some installation sources, such as NFS, don't need to download packages to
            # local storage, so the download location might not always exist. So for now
            # warn about this, at least until the RFE in bug 1193121 is implemented and
            # we don't have to care about clearing the download location ourselves.
            log.warning("Can't delete nonexistent download "
                        "location: %s", self._download_location)

    def get_repo(self, repo_id):
        """Return the yum repo object."""
        return self._base.repos[repo_id]

    def is_repo_enabled(self, repo_id):
        """Return True if repo is enabled."""
        try:
            return self._base.repos[repo_id].enabled
        except (dnf.exceptions.RepoError, KeyError):
            repo = self.get_addon_repo(repo_id)
            if repo:
                return repo.enabled
            else:
                return False

    def verify_available_repositories(self):
        """Verify availability of existing repositories.

        This method tests if URL links from active repositories can be reached.
        It is useful when network settings is changed so that we can verify if repositories
        are still reachable.
        """
        if not self._repoMD_list:
            return False

        for repo in self._repoMD_list:
            if not repo.verify_repoMD():
                log.debug("Can't reach repo %s", repo.id)
                return False
        return True

    def language_groups(self):
        localization_proxy = LOCALIZATION.get_proxy()
        locales = [localization_proxy.Language] + localization_proxy.LanguageSupport
        match_fn = pyanaconda.localization.langcode_matches_locale
        gids = set()
        gl_tuples = ((g.id, g.lang_only) for g in self._base.comps.groups_iter())
        for (gid, lang) in gl_tuples:
            for locale in locales:
                if match_fn(lang, locale):
                    gids.add(gid)
        return list(gids)

    def reset(self):
        self.reset_install_device()
        self.reset_additional_repos()

        shutil.rmtree(DNF_CACHE_DIR, ignore_errors=True)
        shutil.rmtree(DNF_PLUGINCONF_DIR, ignore_errors=True)

        self.tx_id = None
        self._base.reset(sack=True, repos=True)
        self._configure_proxy()
        self._repoMD_list = []

    def reset_install_device(self):
        """Unmount the previous base repo and reset the install_device."""
        # cdrom: install_device.teardown (INSTALL_TREE)
        # hd: umount INSTALL_TREE, install_device.teardown (ISO_DIR)
        # nfs: umount INSTALL_TREE
        # nfsiso: umount INSTALL_TREE, umount ISO_DIR
        install_device_path = payload_utils.get_device_path(self.install_device)

        if os.path.ismount(INSTALL_TREE):
            if self.install_device and \
               payload_utils.get_mount_device_path(INSTALL_TREE) == install_device_path:
                payload_utils.teardown_device(self.install_device)
            else:
                payload_utils.unmount(INSTALL_TREE, raise_exc=True)

        if os.path.ismount(ISO_DIR):
            if self.install_device and \
               payload_utils.get_mount_device_path(ISO_DIR) == install_device_path:
                payload_utils.teardown_device(self.install_device)
            # The below code will fail when nfsiso is the stage2 source
            # But if we don't do this we may not be able to switch from
            # one nfsiso repo to another nfsiso repo.  We need to have a
            # way to detect the stage2 state and work around it.
            # Commenting out the below is a hack for F18.  FIXME
            # else:
            #     # NFS
            #     blivet.util.umount(ISO_DIR)

        self.install_device = None

    def reset_additional_repos(self):
        for name in self._find_mounted_additional_repos():
            installation_dir = INSTALL_TREE + "-" + name
            self._unmount_source_directory(installation_dir)

            iso_dir = ISO_DIR + "-" + name
            self._unmount_source_directory(iso_dir)

    def _find_mounted_additional_repos(self):
        prefix = ISO_DIR + "-"
        prefix_len = len(prefix)
        result = []

        for dir_path in glob(prefix + "*"):
            result.append(dir_path[prefix_len:])

        return result

    def _unmount_source_directory(self, mount_point):
        if os.path.ismount(mount_point):
            device_path = payload_utils.get_mount_device_path(mount_point)
            device = payload_utils.resolve_device(device_path)
            if device:
                payload_utils.teardown_device(device)
            else:
                payload_utils.unmount(mount_point, raise_exc=True)

    def update_base_repo(self, fallback=True, checkmount=True):
        """Update the base repository from ksdata.method."""
        log.info('configuring base repo')
        self.reset()
        install_tree_url, mirrorlist, metalink = self._setup_install_device(checkmount)

        # Fallback to installation root
        base_repo_url = install_tree_url

        method = self.data.method
        sslverify = True
        if method.method == "url":
            sslverify = not method.noverifyssl and conf.payload.verify_ssl

        # Read in all the repos from the installation environment, make a note of which
        # are enabled, and then disable them all.  If the user gave us a method, we want
        # to use that instead of the default repos.
        self._base.read_all_repos()

        # Enable or disable updates.
        self.set_updates_enabled(self._updates_enabled)

        # Repo files are always loaded from the system.
        # When reloaded their state needs to be synchronized with the user configuration.
        # So we disable them now and enable them later if required.
        enabled = []
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                enabled.append(repo.id)
                repo.disable()

        if method.method:
            try:
                self._refresh_install_tree(install_tree_url)
                self._base.conf.releasever = self._get_release_version(install_tree_url)
                base_repo_url = self._get_base_repo_location(install_tree_url)

                if self.first_payload_reset:
                    self._add_treeinfo_repositories(install_tree_url, base_repo_url)

                log.debug("releasever from %s is %s", base_repo_url, self._base.conf.releasever)
            except configparser.MissingSectionHeaderError as e:
                log.error("couldn't set releasever from base repo (%s): "
                          "%s", method.method, e)

            try:
                proxy = getattr(method, "proxy", None)
                base_ksrepo = self.data.RepoData(
                    name=constants.BASE_REPO_NAME, baseurl=base_repo_url,
                    mirrorlist=mirrorlist, metalink=metalink,
                    noverifyssl=not sslverify, proxy=proxy,
                    sslcacert=getattr(method, 'sslcacert', None),
                    sslclientcert=getattr(method, 'sslclientcert', None),
                    sslclientkey=getattr(method, 'sslclientkey', None))
                self._add_repo(base_ksrepo)
                self._fetch_md(base_ksrepo.name)
            except (MetadataError, PayloadError) as e:
                log.error("base repo (%s/%s) not valid -- removing it",
                          method.method, base_repo_url)
                log.error("reason for repo removal: %s", e)
                with self._repos_lock:
                    self._base.repos.pop(constants.BASE_REPO_NAME, None)
                if not fallback:
                    with self._repos_lock:
                        for repo in self._base.repos.iter_enabled():
                            self.disable_repo(repo.id)
                    return

                # this preserves the method details while disabling it
                method.method = None
                self.install_device = None

        # We need to check this again separately in case method.method was unset above.
        if not method.method:
            # If this is a kickstart install, just return now
            if flags.automatedInstall:
                return

            # Otherwise, fall back to the default repos that we disabled above
            with self._repos_lock:
                for (id_, repo) in self._base.repos.items():
                    if id_ in enabled:
                        log.debug("repo %s: fall back enabled from default repos", id_)
                        repo.enable()

        for repo in self.addons:
            ksrepo = self.get_addon_repo(repo)

            if ksrepo.is_harddrive_based():
                ksrepo.baseurl = self._setup_harddrive_addon_repo(ksrepo)

            log.debug("repo %s: mirrorlist %s, baseurl %s, metalink %s",
                      ksrepo.name, ksrepo.mirrorlist, ksrepo.baseurl, ksrepo.metalink)
            # one of these must be set to create new repo
            if not (ksrepo.mirrorlist or ksrepo.baseurl or ksrepo.metalink or
                    ksrepo.name in self._base.repos):
                raise PayloadSetupError("Repository %s has no mirror, baseurl or "
                                        "metalink set and is not one of "
                                        "the pre-defined repositories" %
                                        ksrepo.name)

            self._add_repo(ksrepo)

        with self._repos_lock:

            # disable unnecessary repos
            for repo in self._base.repos.iter_enabled():
                id_ = repo.id
                if 'source' in id_ or 'debuginfo' in id_:
                    self.disable_repo(id_)
                elif constants.isFinal and 'rawhide' in id_:
                    self.disable_repo(id_)

            # fetch md for enabled repos
            enabled_repos = self.enabled_repos
            for repo_name in self.addons:
                if repo_name in enabled_repos:
                    self._fetch_md(repo_name)

    def _setup_install_device(self, checkmount):
        # XXX FIXME: does this need to handle whatever was set up by dracut?
        method = self.data.method
        url = None
        mirrorlist = None
        metalink = None

        # See if we already have stuff mounted due to dracut
        iso_device_path = payload_utils.get_mount_device_path(DRACUT_ISODIR)
        repo_device_path = payload_utils.get_mount_device_path(DRACUT_REPODIR)

        if method.method == "harddrive":
            log.debug("Setting up harddrive install device")
            url = self._setup_harddrive_device(method, iso_device_path, repo_device_path)
        elif method.method == "nfs":
            log.debug("Setting up nfs install device")
            url = self._setup_nfs_device(method, iso_device_path, repo_device_path)
        elif method.method == "url":
            url = method.url
            mirrorlist = method.mirrorlist
            metalink = method.metalink
        elif method.method == "hmc":
            log.debug("Setting up hmc install device")
            url = self._setup_hmc_device(method, iso_device_path, repo_device_path)
        elif method.method == "cdrom" or (checkmount and not method.method):
            log.debug("Setting up cdrom install device")
            url = self._setup_cdrom_device(method, iso_device_path, repo_device_path)

        return url, mirrorlist, metalink

    def _setup_harddrive_device(self, method, iso_device_path, repo_device_path):
        url = None
        need_mount = False

        if method.biospart:
            log.warning("biospart support is not implemented")
            dev_spec = method.biospart
        else:
            dev_spec = method.partition
            need_mount = True
            # See if we used this method for stage2, thus dracut left it
            if iso_device_path and method.partition and \
               method.partition in iso_device_path and \
               DRACUT_ISODIR in repo_device_path:
                # Everything should be setup
                url = "file://" + DRACUT_REPODIR
                need_mount = False
                # We don't setup an install_device here
                # because we can't tear it down

        iso_device = payload_utils.resolve_device(dev_spec)
        if need_mount:
            if not iso_device:
                raise PayloadSetupError("device for HDISO install %s does not exist" % dev_spec)

            url = self._setup_media(iso_device)
            self.install_device = iso_device

        return url

    def _setup_nfs_device(self, method, iso_device_path, repo_device_path):
        # There are several possible scenarios here:
        # 1. dracut could have mounted both the nfs repo and an iso and used
        #    the stage2 from inside the iso to boot from.
        #    iso_device_path and repo_device_path will be set in this case.
        # 2. dracut could have mounted the nfs repo and used a stage2 from
        #    the NFS mount w/o mounting the iso.
        #    iso_device_path will be None and repo_device_path will be the nfs: path
        # 3. dracut did not mount the nfs (eg. stage2 came from elsewhere)
        #    iso_device_path and/or repo_device_path are None
        # 4. The repo may not contain an iso, in that case use it as is
        url = None
        path = None

        if iso_device_path and repo_device_path:
            path = parse_nfs_url('nfs:%s' % iso_device_path)[2]
            # See if the dir holding the iso is what we want
            # and also if we have an iso mounted to /run/install/repo
            if path and path in iso_device_path and DRACUT_ISODIR in repo_device_path:
                # Everything should be setup
                url = "file://" + DRACUT_REPODIR
        else:
            # see if the nfs dir is mounted
            need_mount = True
            if repo_device_path:
                _options, host, path = parse_nfs_url('nfs:%s' % repo_device_path)
                if method.server and method.server == host and \
                   method.dir and method.dir == path:
                    need_mount = False
                    path = DRACUT_REPODIR
            elif iso_device_path:
                # iso_device_path with no repo_device_path can happen when options on an existing
                # nfs mount have changed. It is already mounted, but on INSTALL_TREE
                # which is the same as DRACUT_ISODIR, making it hard for _setup_NFS
                # to detect that it is already mounted.
                _options, host, path = parse_nfs_url('nfs:%s' % iso_device_path)
                if path and path in iso_device_path:
                    need_mount = False
                    path = DRACUT_ISODIR

            if need_mount:
                # Mount the NFS share on INSTALL_TREE. If it ends up
                # being nfsiso we will move the mountpoint to ISO_DIR.
                if method.dir.endswith(".iso"):
                    nfs_dir = os.path.dirname(method.dir)
                else:
                    nfs_dir = method.dir

                self._setup_NFS(INSTALL_TREE, method.server, nfs_dir, method.opts)
                path = INSTALL_TREE

            # check for ISO images in the newly mounted dir
            if method.dir.endswith(".iso"):
                # if the given URL includes a specific ISO image file, use it
                image_file = os.path.basename(method.dir)
                path = os.path.normpath("%s/%s" % (path, image_file))

            image = find_first_iso_image(path)

            # An image was found, mount it on INSTALL_TREE
            if image:
                if path.startswith(INSTALL_TREE):
                    # move the INSTALL_TREE mount to ISO_DIR so we can
                    # mount the contents of the iso there.
                    # work around inability to move shared filesystems
                    util.execWithRedirect("mount",
                                          ["--make-rprivate", "/"])
                    util.execWithRedirect("mount",
                                          ["--move", INSTALL_TREE, ISO_DIR])
                    # The iso is now under ISO_DIR
                    path = ISO_DIR
                elif path.endswith(".iso"):
                    path = os.path.dirname(path)

                # mount the ISO on a loop
                image = os.path.normpath("%s/%s" % (path, image))
                mountImage(image, INSTALL_TREE)

                url = "file://" + INSTALL_TREE
            elif os.path.isdir(path):
                # Fall back to the mount path instead of a mounted iso
                url = "file://" + path
            else:
                # Do not try to use iso as source if it is not valid source
                raise PayloadSetupError("Not a valid ISO image!")

        return url

    def _setup_hmc_device(self, method, iso_device_path, repo_device_path):
        # Check if /dev/hmcdrv is already mounted.
        if repo_device_path == "/dev/hmcdrv":
            log.debug("HMC is already mounted at %s.", DRACUT_REPODIR)
            url = "file://" + DRACUT_REPODIR
        else:
            log.debug("Trying to mount the content of HMC media drive.")

            # Test the SE/HMC file access.
            if util.execWithRedirect("/usr/sbin/lshmc", []):
                raise PayloadSetupError("The content of HMC media drive couldn't be accessed.")

            # Test if a path is a mount point.
            if os.path.ismount(INSTALL_TREE):
                log.debug("Don't mount the content of HMC media drive yet.")
            else:
                # Make sure that the directories exists.
                util.mkdirChain(INSTALL_TREE)

                # Mount the device.
                if util.execWithRedirect("/usr/bin/hmcdrvfs", [INSTALL_TREE]):
                    raise PayloadSetupError("The content of HMC media drive couldn't be mounted.")

            log.debug("We are ready to use the HMC at %s.", INSTALL_TREE)
            url = "file://" + INSTALL_TREE

        return url

    def _setup_cdrom_device(self, method, iso_device_path, repo_device_path):
        url = None

        # FIXME: We really should not talk about NFS here - regression from re-factorization?

        # Check for valid optical media if we didn't boot from one
        if not is_valid_install_disk(DRACUT_REPODIR):
            self.install_device = find_optical_install_media()

        # Only look at the dracut mount if we don't already have a cdrom
        if repo_device_path and not self.install_device:
            self.install_device = payload_utils.resolve_device(repo_device_path)
            url = "file://" + DRACUT_REPODIR
            if not method.method:
                # See if this is a nfs mount
                if ':' in repo_device_path:
                    # prepend nfs: to the url as that's what the parser
                    # wants.  Note we don't get options from this, but
                    # that's OK for the UI at least.
                    _options, host, path = parse_nfs_url("nfs:%s" % repo_device_path)
                    method.method = "nfs"
                    method.server = host
                    method.dir = path
                else:
                    method.method = "cdrom"
        else:
            if self.install_device:
                if not method.method:
                    method.method = "cdrom"
                url = self._setup_media(self.install_device)
            elif method.method == "cdrom":
                raise PayloadSetupError("no usable optical media found")

        return url

    def _setup_media(self, device):
        method = self.data.method

        if method.method == "harddrive":
            try:
                method.dir = self._find_and_mount_iso(device, ISO_DIR, method.dir, INSTALL_TREE)
            except PayloadSetupError as ex:
                log.warning(str(ex))

                try:
                    self._setup_install_tree(device, method.dir, INSTALL_TREE)
                    return util.join_paths("file:///", INSTALL_TREE, method.dir)
                except PayloadSetupError as ex:
                    log.error(str(ex))
                    raise PayloadSetupError("failed to setup installation tree or ISO from HDD")
        elif not (method.method == "cdrom" and self._device_is_mounted_as_source(device)):
            payload_utils.mount_device(device, INSTALL_TREE)

        return util.join_paths("file:///", INSTALL_TREE)

    def _find_and_mount_iso(self, device, device_mount_dir, iso_path, iso_mount_dir):
        """Find and mount installation source from ISO on device.

        Return changed path to the iso to save looking for iso in the future call.
        """
        self._setup_device(device, mountpoint=device_mount_dir)

        # check for ISO images in the newly mounted dir
        path = device_mount_dir
        if iso_path:
            path = os.path.normpath("%s/%s" % (path, iso_path))

        # XXX it would be nice to streamline this when we're just setting
        #     things back up after storage activation instead of having to
        #     pretend we don't already know which ISO image we're going to
        #     use
        image = find_first_iso_image(path)
        if not image:
            payload_utils.teardown_device(device)
            raise PayloadSetupError("failed to find valid iso image")

        if path.endswith(".iso"):
            path = os.path.dirname(path)

        # this could already be set up the first time through
        if not os.path.ismount(iso_mount_dir):
            # mount the ISO on a loop
            image = os.path.normpath("%s/%s" % (path, image))
            mountImage(image, iso_mount_dir)

        if not iso_path.endswith(".iso"):
            result_path = os.path.normpath("%s/%s" % (iso_path,
                                                      os.path.basename(image)))
            while result_path.startswith("/"):
                # ridiculous
                result_path = result_path[1:]

            return result_path

        return iso_path

    def _setup_install_tree(self, device, install_tree_path, device_mount_dir):
        self._setup_device(device, mountpoint=device_mount_dir)
        path = os.path.normpath("%s/%s" % (device_mount_dir, install_tree_path))

        if not verify_valid_installtree(path):
            payload_utils.teardown_device(device)
            raise PayloadSetupError("failed to find valid installation tree")

    @staticmethod
    def _setup_device(device, mountpoint):
        """Prepare an install CD/DVD for use as a package source."""
        log.info("setting up device %s and mounting on %s", device, mountpoint)
        # Is there a symlink involved?  If so, let's get the actual path.
        # This is to catch /run/install/isodir vs. /mnt/install/isodir, for
        # instance.
        real_mountpoint = os.path.realpath(mountpoint)
        mount_device_path = payload_utils.get_mount_device_path(real_mountpoint)

        if mount_device_path:
            log.warning("%s is already mounted on %s", mount_device_path, mountpoint)

            if mount_device_path == payload_utils.get_device_path(device):
                return
            else:
                payload_utils.unmount(real_mountpoint)

        try:
            payload_utils.setup_device(device)
            payload_utils.mount_device(device, mountpoint)
        except (DeviceSetupError, MountFilesystemError) as e:
            log.error("mount failed: %s", e)
            payload_utils.teardown_device(device)
            raise PayloadSetupError(str(e))

    @staticmethod
    def _setup_NFS(mountpoint, server, path, options):
        """Prepare an NFS directory for use as an install source."""
        log.info("mounting %s:%s:%s on %s", server, path, options, mountpoint)
        device_path = payload_utils.get_mount_device_path(mountpoint)

        # test if the mountpoint is occupied already
        if device_path:
            _server, colon, _path = device_path.partition(":")
            if colon == ":" and server == _server and path == _path:
                log.debug("%s:%s already mounted on %s", server, path, mountpoint)
                return
            else:
                log.debug("%s already has something mounted on it", mountpoint)
                payload_utils.unmount(mountpoint)

        # mount the specified directory
        url = "%s:%s" % (server, path)

        if not options:
            options = "nolock"
        elif "nolock" not in options:
            options += ",nolock"

        payload_utils.mount(url, mountpoint, fstype="nfs", options=options)

    def _device_is_mounted_as_source(self, device):
        device_path = payload_utils.get_device_path(device)
        device_mounts = payload_utils.get_mount_paths(device_path)
        return INSTALL_TREE in device_mounts or DRACUT_REPODIR in device_mounts

    def _setup_harddrive_addon_repo(self, ksrepo):
        iso_device = payload_utils.resolve_device(ksrepo.partition)
        if not iso_device:
            raise PayloadSetupError("device for HDISO addon repo install %s does not exist" %
                                    ksrepo.partition)

        ksrepo.generate_mount_dir()

        device_mount_dir = ISO_DIR + "-" + ksrepo.mount_dir_suffix
        install_root_dir = INSTALL_TREE + "-" + ksrepo.mount_dir_suffix

        self._find_and_mount_iso(iso_device, device_mount_dir, ksrepo.iso_path, install_root_dir)
        url = "file://" + install_root_dir

        return url

    def _refresh_install_tree(self, url):
        """Refresh installation tree metadata.

        :param url: url of the repo
        :type url: string
        """
        if not url:
            return

        if hasattr(self.data.method, "proxy"):
            proxy_url = self.data.method.proxy
        else:
            proxy_url = None

        # ssl_verify can be:
        #   - the path to a cert file
        #   - True, to use the system's certificates
        #   - False, to not verify
        ssl_verify = getattr(self.data.method, "sslcacert", None) or conf.payload.verify_ssl

        ssl_client_cert = getattr(self.data.method, "ssl_client_cert", None)
        ssl_client_key = getattr(self.data.method, "ssl_client_key", None)
        ssl_cert = (ssl_client_cert, ssl_client_key) if ssl_client_cert else None

        log.debug("retrieving treeinfo from %s (proxy: %s ; ssl_verify: %s)",
                  url, proxy_url, ssl_verify)

        proxies = {}
        if proxy_url:
            try:
                proxy = ProxyString(proxy_url)
                proxies = {"http": proxy.url,
                           "https": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy for _getTreeInfo %s: %s",
                         proxy_url, e)

        headers = {"user-agent": USER_AGENT}
        self._install_tree_metadata = InstallTreeMetadata()
        try:
            ret = self._install_tree_metadata.load_url(url, proxies, ssl_verify, ssl_cert, headers)
        except IOError as e:
            self._install_tree_metadata = None
            self.verbose_errors.append(str(e))
            log.warning("Install tree metadata fetching failed: %s", str(e))
            return

        if not ret:
            log.warning("Install tree metadata can't be loaded!")
            self._install_tree_metadata = None

    def _get_release_version(self, url):
        """Return the release version of the tree at the specified URL."""
        try:
            version = re.match(VERSION_DIGITS, productVersion).group(1)
        except AttributeError:
            version = "rawhide"

        log.debug("getting release version from tree at %s (%s)", url, version)

        if self._install_tree_metadata:
            version = self._install_tree_metadata.get_release_version()
            log.debug("using treeinfo release version of %s", version)
        else:
            log.debug("using default release version of %s", version)

        return version

    def _get_base_repo_location(self, install_tree_url):
        """Try to find base repository from the treeinfo file.

        The URL can be installation tree root or a subfolder in the installation root.
        The structure of the installation root can be similar to this.

        / -
          | - .treeinfo
          | - BaseRepo -
          |            | - repodata
          |            | - Packages
          | - AddonRepo -
                        | - repodata
                        | - Packages

        The .treeinfo file contains information where repositories are placed from the
        installation root.

        User can provide us URL to the installation root or directly to the repository folder.
        Both options are valid.
        * If the URL points to an installation root we need to find position of
        repositories in the .treeinfo file.
        * If URL points to repo directly then no .treeinfo file is present. We will just use this
        repo.
        """
        if self._install_tree_metadata:
            repo_md = self._install_tree_metadata.get_base_repo_metadata()
            if repo_md:
                log.debug("Treeinfo points base repository to %s.", repo_md.path)
                return repo_md.path

        log.debug("No base repository found in treeinfo file. Using installation tree root.")
        return install_tree_url

    def _add_treeinfo_repositories(self, install_tree_url, base_repo_url=None):
        """Add all repositories from treeinfo file which are not already loaded.

        :param install_tree_url: Url to the installation tree root.
        :param base_repo_url: Base repository url. This is not saved anywhere when the function
        is called. It will be add to the existing urls if not None.
        """
        if self._install_tree_metadata:
            existing_urls = []

            if base_repo_url is not None:
                existing_urls.append(base_repo_url)

            for ksrepo in self.addons:
                baseurl = self.get_addon_repo(ksrepo).baseurl
                existing_urls.append(baseurl)

            enabled_repositories_from_treeinfo = conf.payload.enabled_repositories_from_treeinfo

            for repo_md in self._install_tree_metadata.get_metadata_repos():
                if repo_md.path not in existing_urls:
                    repo_treeinfo = self._install_tree_metadata.get_treeinfo_for(repo_md.name)
                    repo_enabled = repo_treeinfo.type in enabled_repositories_from_treeinfo
                    repo = RepoData(name=repo_md.name, baseurl=repo_md.path,
                                    install=False, enabled=repo_enabled)
                    repo.treeinfo_origin = True
                    self.add_repo(repo)

        return install_tree_url

    def _write_dnf_repo(self, repo, repo_path):
        """Write a repo object to a DNF repo.conf file.

        :param repo: DNF repository object
        :param string repo_path: Path to write the repo to
        :raises: PayloadSetupError if the repo doesn't have a url
        """
        with open(repo_path, "w") as f:
            f.write("[%s]\n" % repo.id)
            f.write("name=%s\n" % repo.id)
            if self.is_repo_enabled(repo.id):
                f.write("enabled=1\n")
            else:
                f.write("enabled=0\n")

            if repo.mirrorlist:
                f.write("mirrorlist=%s\n" % repo.mirrorlist)
            elif repo.metalink:
                f.write("metalink=%s\n" % repo.metalink)
            elif repo.baseurl:
                f.write("baseurl=%s\n" % repo.baseurl[0])
            else:
                f.close()
                os.unlink(repo_path)
                raise PayloadSetupError("The repo {} has no baseurl, mirrorlist or "
                                        "metalink".format(repo.id))

            # kickstart repo modifiers
            ks_repo = self.get_addon_repo(repo.id)
            if not ks_repo:
                return

            if ks_repo.noverifyssl:
                f.write("sslverify=0\n")

            if ks_repo.proxy:
                try:
                    proxy = ProxyString(ks_repo.proxy)
                    f.write("proxy=%s\n" % proxy.url)
                except ProxyStringError as e:
                    log.error("Failed to parse proxy for _writeInstallConfig %s: %s",
                              ks_repo.proxy, e)

            if ks_repo.cost:
                f.write("cost=%d\n" % ks_repo.cost)

            if ks_repo.includepkgs:
                f.write("include=%s\n" % ",".join(ks_repo.includepkgs))

            if ks_repo.excludepkgs:
                f.write("exclude=%s\n" % ",".join(ks_repo.excludepkgs))

    @property
    def needs_storage_configuration(self):
        """Should we write the storage before doing the installation?"""
        return True

    def post_setup(self):
        """Perform post-setup tasks.

        Save repomd hash to test if the repositories can be reached.
        """
        super().post_setup()
        self._repoMD_list = []
        for repo in self._base.repos.iter_enabled():
            repoMD = RepoMDMetaHash(self, repo)
            repoMD.store_repoMD_hash()
            self._repoMD_list.append(repoMD)

    def post_install(self):
        """Perform post-installation tasks."""
        # Write selected kickstart repos to target system
        for ks_repo in (ks for ks in (self.get_addon_repo(r) for r in self.addons) if ks.install):
            if ks_repo.baseurl.startswith("nfs://"):
                log.info("Skip writing nfs repo %s to target system.", ks_repo.name)
                continue

            try:
                repo = self.get_repo(ks_repo.name)
                if not repo:
                    continue
            except (dnf.exceptions.RepoError, KeyError):
                continue
            repo_path = conf.target.system_root + YUM_REPOS_DIR + "%s.repo" % repo.id
            try:
                log.info("Writing %s.repo to target system.", repo.id)
                self._write_dnf_repo(repo, repo_path)
            except PayloadSetupError as e:
                log.error(e)

        # We don't need the mother base anymore. Close it.
        self._base.close()
        super().post_install()

    @property
    def kernel_version_list(self):
        # Find all installed rpms that provide 'kernel'
        files = []
        ts = rpm.TransactionSet(conf.target.system_root)
        mi = ts.dbMatch('providename', 'kernel')

        for hdr in mi:
            unicode_fnames = (decode_bytes(f) for f in hdr.filenames)
            # Find all /boot/vmlinuz- files and strip off vmlinuz-
            files.extend((f.split("/")[-1][8:] for f in unicode_fnames
                         if fnmatch(f, "/boot/vmlinuz-*") or
                         fnmatch(f, "/boot/efi/EFI/%s/vmlinuz-*" % conf.bootloader.efi_dir)))

        return sorted(files, key=functools.cmp_to_key(payload_utils.version_cmp))
