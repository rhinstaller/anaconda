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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import configparser
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

from glob import glob

from pyanaconda.modules.common.structures.payload import RepoConfigurationData, \
    PackagesConfigurationData
from pyanaconda.modules.payloads.payload.dnf.initialization import configure_dnf_logging
from pyanaconda.modules.payloads.payload.dnf.installation import ImportRPMKeysTask, \
    SetRPMMacrosTask, UpdateDNFConfigurationTask
from pyanaconda.modules.payloads.payload.dnf.requirements import collect_language_requirements, \
    collect_platform_requirements, collect_driver_disk_requirements, collect_remote_requirements, \
    apply_requirements
from pyanaconda.modules.payloads.payload.dnf.utils import get_kernel_package, \
    get_product_release_version, get_default_environment, get_installation_specs, \
    get_kernel_version_list
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.payload.source import SourceFactory, PayloadSourceTypeUnrecognized

from pyanaconda import errors as errors
from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core import constants, util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import INSTALL_TREE, ISO_DIR, PAYLOAD_TYPE_DNF, \
    SOURCE_TYPE_URL, SOURCE_TYPE_CDROM, URL_TYPE_BASEURL, URL_TYPE_MIRRORLIST, \
    URL_TYPE_METALINK, SOURCE_REPO_FILE_TYPES, SOURCE_TYPE_CDN, MULTILIB_POLICY_ALL
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.flags import flags
from pyanaconda.kickstart import RepoData
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE, SUBSCRIPTION
from pyanaconda.modules.payloads.source.utils import has_network_protocol
from pyanaconda.modules.common.errors.storage import DeviceSetupError, MountFilesystemError
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.base import Payload
from pyanaconda.payload.dnf.utils import DNF_PACKAGE_CACHE_DIR_SUFFIX, \
    YUM_REPOS_DIR, do_transaction, get_df_map, pick_mount_point
from pyanaconda.payload.dnf.download_progress import DownloadProgress
from pyanaconda.payload.dnf.repomd import RepoMDMetaHash
from pyanaconda.payload.errors import MetadataError, PayloadError, NoSuchGroup, DependencyError, \
    PayloadInstallError, PayloadSetupError
from pyanaconda.payload.image import find_first_iso_image, find_optical_install_media
from pyanaconda.payload.install_tree_metadata import InstallTreeMetadata
from pyanaconda.progress import progressQ, progress_message
from pyanaconda.ui.lib.payload import get_payload, get_source, create_source, set_source, \
    set_up_sources, tear_down_sources

log = get_packaging_logger()

__all__ = ["DNFPayload"]


class DNFPayload(Payload):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A list of verbose error strings
        self.verbose_errors = []

        # Get a DBus payload to use.
        self._payload_proxy = get_payload(self.type)

        self.tx_id = None
        self._install_tree_metadata = None

        # Used to determine which add-ons to display for each environment.
        # The dictionary keys are environment IDs. The dictionary values are two-tuples
        # consisting of lists of add-on group IDs. The first list is the add-ons specific
        # to the environment, and the second list is the other add-ons possible for the
        # environment.
        self._environment_addons = {}

        self._dnf_manager = DNFManager()
        self._download_location = None
        self._updates_enabled = True

        # Configure the DNF logging.
        configure_dnf_logging()

        # FIXME: Don't call this method before set_from_opts.
        # This will create a default source if there is none.
        self._configure()

        # Protect access to _base.repos to ensure that the dictionary is not
        # modified while another thread is attempting to iterate over it. The
        # lock only needs to be held during operations that change the number
        # of repos or that iterate over the repos.
        self._repos_lock = threading.RLock()

        # save repomd metadata
        self._repoMD_list = []

        # Additional packages required by installer based on used features
        self._requirements = []

    @property
    def _base(self):
        """Return a DNF base.

        FIXME: This is a temporary property.
        """
        return self._dnf_manager._base

    def set_from_opts(self, opts):
        """Set the payload from the Anaconda cmdline options.

        :param opts: a namespace of options
        """
        # Set the source based on opts.method if it isn't already set
        # - opts.method is currently set by command line/boot options
        if opts.method and (not self.proxy.Sources or self.is_source_default()):
            try:
                source = SourceFactory.parse_repo_cmdline_string(opts.method)
            except PayloadSourceTypeUnrecognized:
                log.error("Unknown method: %s", opts.method)
            else:
                source_proxy = source.create_proxy()
                set_source(self.proxy, source_proxy)

        # Set up the current source.
        source_proxy = self.get_source_proxy()

        if source_proxy.Type == SOURCE_TYPE_URL:
            # Get the repo configuration.
            repo_configuration = RepoConfigurationData.from_structure(
                source_proxy.RepoConfiguration
            )

            if opts.proxy:
                repo_configuration.proxy = opts.proxy

            if not conf.payload.verify_ssl:
                repo_configuration.ssl_verification_enabled = conf.payload.verify_ssl

            # Update the repo configuration.
            source_proxy.SetRepoConfiguration(
                RepoConfigurationData.to_structure(repo_configuration)
            )

        # Set up packages.
        if opts.multiLib:
            packages = self.get_packages_data()
            packages.multilib_policy = MULTILIB_POLICY_ALL
            self.set_packages_data(packages)

        # Reset all the other things now that we have new configuration.
        self._configure()

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_DNF

    def get_source_proxy(self):
        """Get the DBus proxy of the RPM source.

        The default source for the DNF payload is set via
        the default_source option in the payload section
        of the Anaconda config file.

        :return: a DBus proxy
        """
        return get_source(self.proxy, conf.payload.default_source)

    @property
    def source_type(self):
        """The DBus type of the source."""
        source_proxy = self.get_source_proxy()
        return source_proxy.Type

    def get_packages_data(self) -> PackagesConfigurationData:
        """Get the DBus data with the packages configuration."""
        return PackagesConfigurationData.from_structure(
            self.proxy.Packages
        )

    def set_packages_data(self, data: PackagesConfigurationData):
        """Set the DBus data with the packages configuration."""
        return self.proxy.SetPackages(
            PackagesConfigurationData.to_structure(data)
        )

    def is_ready(self):
        """Is the payload ready?"""
        return self.base_repo is not None

    def is_complete(self):
        """Is the payload complete?"""
        return self.source_type not in SOURCE_REPO_FILE_TYPES or self.base_repo

    def setup(self):
        self.verbose_errors = []

    def unsetup(self):
        self._configure()
        self._repoMD_list = []
        self._install_tree_metadata = None
        tear_down_sources(self.proxy)

    @property
    def needs_network(self):
        """Test base and additional repositories if they require network."""
        return (self.proxy.IsNetworkRequired() or
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
        for s in sources:
            if has_network_protocol(s):
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
            self._handle_marking_error(e)

        # forward the module specs to enable to DNF
        log.debug("enabling modules: %s", module_specs_to_enable)
        try:
            module_base = dnf.module.module_base.ModuleBase(self._base)
            module_base.enable(module_specs_to_enable)
        except dnf.exceptions.MarkingErrors as e:
            log.debug("ModuleBase.enable(): some packages, groups "
                      "or modules are missing or broken:\n%s", e)
            self._handle_marking_error(e)

    def _apply_selections(self):
        log.debug("applying DNF package/group/module selection")

        # Get the packages configuration data.
        data = self.get_packages_data()

        # Get the default environment.
        default_environment = get_default_environment(self._dnf_manager)

        # Get the installation specs.
        include_list, exclude_list = get_installation_specs(
            data, default_environment
        )

        # Add the kernel package.
        kernel_package = get_kernel_package(self._base, exclude_list)

        if kernel_package:
            include_list.append(kernel_package)

        # Apply requirements.
        apply_requirements(self._requirements, include_list, exclude_list)

        # Apply specs.
        try:
            self._dnf_manager.apply_specs(include_list, exclude_list)
        except dnf.exceptions.MarkingErrors as e:
            self._handle_marking_error(e)

    def _bump_tx_id(self):
        if self.tx_id is None:
            self.tx_id = 1
        else:
            self.tx_id += 1
        return self.tx_id

    def _get_proxy_url(self):
        """Get a proxy of the current source.

        :return: a proxy or None
        """
        source_proxy = self.get_source_proxy()
        source_type = source_proxy.Type

        if source_type != SOURCE_TYPE_URL:
            return None

        data = RepoConfigurationData.from_structure(
            source_proxy.RepoConfiguration
        )

        return data.proxy

    def _configure(self):
        self._dnf_manager.reset_base()
        self._dnf_manager.configure_base(self.get_packages_data())
        self._dnf_manager.configure_proxy(self._get_proxy_url())
        self._dnf_manager.dump_configuration()

    def _handle_marking_error(self, exn):
        # FIXME: Move this code outside the payload class.
        log.error('DNF marking error: %r', exn)
        if errors.errorHandler.cb(exn) == errors.ERROR_RAISE:
            # The progress bar polls kind of slowly, thus installation could
            # still continue for a bit before the quit message is processed.
            # Doing a sys.exit also ensures the running thread quits before
            # it can do anything else.
            progressQ.send_quit(1)
            util.ipmi_abort(scripts=self.data.scripts)
            sys.exit(1)

    def _pick_download_location(self):
        download_size = self._dnf_manager.get_download_size()
        install_size = self._dnf_manager.get_installation_size()
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
            if self.source_type == SOURCE_TYPE_CDN:
                if is_module_available(SUBSCRIPTION):
                    subscription_proxy = SUBSCRIPTION.get_proxy()
                    if subscription_proxy.IsSubscriptionAttached:
                        # If CDN is used as the installation source and we have
                        # a subscription attached then any of the enabled repos
                        # should be fine as the base repo.
                        # If CDN is used but subscription has not been attached
                        # there will be no redhat.repo file to parse and we
                        # don't need to do anything.
                        for repo in self._base.repos.iter_enabled():
                            return repo.id
                else:
                    log.error("CDN install source set but Subscription module is not available")
            else:
                for repo in self._base.repos.iter_enabled():
                    if repo.id in repo_names:
                        return repo.id

        return None

    ###
    # METHODS FOR WORKING WITH ENVIRONMENTS
    ###

    @property
    def environments(self):
        return self._dnf_manager.environments

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

    def add_repo(self, ksrepo):
        """Add an enabled repo to dnf and kickstart repo lists.

        Add the repo given by the pykickstart Repo object ksrepo to the
        system.

        Duplicate repos will not raise an error.  They should just silently
        take the place of the previous value.

        :param ksrepo: Kickstart Repository to add
        :type ksrepo: Kickstart RepoData object.
        :returns: None
        """
        if ksrepo.enabled:
            self._add_repo(ksrepo)
            self._fetch_md(ksrepo.name)

        # Add the repo to the ksdata so it'll appear in the output ks file.
        self.data.repo.dataList().append(ksrepo)

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
            repo.includepkgs = ksrepo.includepkgs

        if ksrepo.excludepkgs:
            repo.excludepkgs = ksrepo.excludepkgs

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
            raise MetadataError(e) from e

        log.info("enabled repo: '%s' - %s and got repomd", repo.id,
                 repo.baseurl or repo.mirrorlist or repo.metalink)

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

    @property
    def space_required(self):
        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        size = self._dnf_manager.get_installation_size()
        download_size = self._dnf_manager.get_download_size()
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
            raise DependencyError(msg) from e

        log.info("%d packages selected totalling %s",
                 len(self._base.transaction), self.space_required)

    def set_updates_enabled(self, state):
        """Enable or Disable the repos used to update closest mirror.

        :param bool state: True to enable updates, False to disable.
        """
        self._updates_enabled = state

        # Enable or disable updates.
        if self._updates_enabled:
            for repo in conf.payload.updates_repositories:
                self.enable_repo(repo)
        else:
            for repo in conf.payload.updates_repositories:
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
        return (grp.ui_name, grp.ui_description or "")

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

    def pre_install(self):
        super().pre_install()

        # Collect all package and group requirements.
        self._collect_requirements()

    def _collect_requirements(self):
        self._requirements.extend(
            collect_remote_requirements()
            + collect_language_requirements(self._base)
            + collect_platform_requirements(self._base)
            + collect_driver_disk_requirements()
        )

    def install(self):
        progress_message(N_('Starting package installation process'))

        # Get the packages configuration data.
        data = self.get_packages_data()

        # Add the rpm macros to the global transaction environment
        task = SetRPMMacrosTask(data)
        task.run()

        self.check_software_selection()
        self._download_location = self._pick_download_location()

        if os.path.exists(self._download_location):
            log.info("Removing existing package download "
                     "location: %s", self._download_location)
            shutil.rmtree(self._download_location)
        pkgs_to_download = self._base.transaction.install_set  # pylint: disable=no-member
        log.info('Downloading packages to %s.', self._download_location)
        progressQ.send_message(_('Downloading packages'))
        progress = DownloadProgress()
        try:
            self._base.download_packages(pkgs_to_download, progress)
        except dnf.exceptions.DownloadError as e:
            msg = 'Failed to download the following packages: %s' % str(e)
            raise PayloadInstallError(msg) from None

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
                raise PayloadInstallError("DNF error: %s" % msg)

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

    def reset(self):
        tear_down_sources(self.proxy)
        self.reset_additional_repos()
        self._install_tree_metadata = None
        self.tx_id = None
        self._dnf_manager.clear_cache()
        self._dnf_manager.configure_proxy(self._get_proxy_url())
        self._repoMD_list = []

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

    def is_source_default(self):
        """Report if the current source type is the default source type.

        NOTE: If no source was set previously a new default one
              will be created.
        """
        return self.source_type == conf.payload.default_source

    def update_base_repo(self, fallback=True, checkmount=True):
        """Update the base repository from the DBus source."""
        log.info("Configuring the base repo")
        self.reset()

        disabled_treeinfo_repo_names = self._cleanup_old_treeinfo_repositories()

        # Find the source and its type.
        source_proxy = self.get_source_proxy()
        source_type = source_proxy.Type

        # Change the default source to CDROM if there is a valid install media.
        # FIXME: Set up the default source earlier.
        if checkmount and self.is_source_default() and find_optical_install_media():
            source_type = SOURCE_TYPE_CDROM
            source_proxy = create_source(source_type)
            set_source(self.proxy, source_proxy)

        # Set up the source.
        set_up_sources(self.proxy)

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

        # Add a new repo.
        if source_type not in SOURCE_REPO_FILE_TYPES:
            # Get the repo configuration of the first source.
            data = RepoConfigurationData.from_structure(
                self.proxy.GetRepoConfigurations()[0]
            )

            log.debug("Using the repo configuration: %s", data)

            # Get the URL.
            install_tree_url = data.url if data.type == URL_TYPE_BASEURL else ""
            mirrorlist = data.url if data.type == URL_TYPE_MIRRORLIST else ""
            metalink = data.url if data.type == URL_TYPE_METALINK else ""

            # Fallback to the installation root.
            base_repo_url = install_tree_url

            try:
                self._refresh_install_tree(data)
                self._base.conf.releasever = self._get_release_version(install_tree_url)
                base_repo_url = self._get_base_repo_location(install_tree_url)
                log.debug("releasever from %s is %s", base_repo_url, self._base.conf.releasever)

                self._load_treeinfo_repositories(base_repo_url, disabled_treeinfo_repo_names, data)
            except configparser.MissingSectionHeaderError as e:
                log.error("couldn't set releasever from base repo (%s): %s", source_type, e)

            try:
                base_ksrepo = self.data.RepoData(
                    name=constants.BASE_REPO_NAME,
                    baseurl=base_repo_url,
                    mirrorlist=mirrorlist,
                    metalink=metalink,
                    noverifyssl=not data.ssl_verification_enabled,
                    proxy=data.proxy,
                    sslcacert=data.ssl_configuration.ca_cert_path,
                    sslclientcert=data.ssl_configuration.client_cert_path,
                    sslclientkey=data.ssl_configuration.client_key_path
                )
                self._add_repo(base_ksrepo)
                self._fetch_md(base_ksrepo.name)
            except (MetadataError, PayloadError) as e:
                log.error("base repo (%s/%s) not valid -- removing it",
                          source_type, base_repo_url)
                log.error("reason for repo removal: %s", e)
                with self._repos_lock:
                    self._base.repos.pop(constants.BASE_REPO_NAME, None)
                if not fallback:
                    with self._repos_lock:
                        for repo in self._base.repos.iter_enabled():
                            self.disable_repo(repo.id)
                    return

                # Fallback to the default source
                #
                # This is at the moment CDN on RHEL
                # and closest mirror everywhere else.
                tear_down_sources(self.proxy)

                source_type = conf.payload.default_source
                source_proxy = create_source(source_type)
                set_source(self.proxy, source_proxy)

                set_up_sources(self.proxy)

        # We need to check this again separately in case REPO_FILES were set above.
        if source_type in SOURCE_REPO_FILE_TYPES:

            # If this is a kickstart install, just return now as we normally do not
            # want to read the on media repo files in such a case. On the other hand,
            # the local repo files are a valid use case if the system is subscribed
            # and the CDN is selected as the installation source.
            if self.source_type == SOURCE_TYPE_CDN and is_module_available(SUBSCRIPTION):
                # only check if the Subscription module is available & CDN is the
                # installation source
                subscription_proxy = SUBSCRIPTION.get_proxy()
                load_cdn_repos = subscription_proxy.IsSubscriptionAttached
            else:
                # if the Subscription module is not available, we simply can't use
                # the CDN repos, making our decision here simple
                load_cdn_repos = False
            if flags.automatedInstall and not load_cdn_repos:
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
            payload_utils.mount(image, iso_mount_dir, fstype='iso9660', options="ro")

        if not iso_path.endswith(".iso"):
            result_path = os.path.normpath("%s/%s" % (iso_path,
                                                      os.path.basename(image)))
            while result_path.startswith("/"):
                # ridiculous
                result_path = result_path[1:]

            return result_path

        return iso_path

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
            raise PayloadSetupError(str(e)) from e

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

    def _refresh_install_tree(self, data: RepoConfigurationData):
        """Refresh installation tree metadata."""
        if data.type != URL_TYPE_BASEURL:
            return

        if not data.url:
            return

        url = data.url
        proxy_url = data.proxy or None

        # ssl_verify can be:
        #   - the path to a cert file
        #   - True, to use the system's certificates
        #   - False, to not verify
        ssl_verify = (data.ssl_configuration.ca_cert_path
                      or (conf.payload.verify_ssl and data.ssl_verification_enabled))
        ssl_client_cert = data.ssl_configuration.client_cert_path or None
        ssl_client_key = data.ssl_configuration.client_key_path or None
        ssl_cert = (ssl_client_cert, ssl_client_key) if ssl_client_cert else None

        log.debug("retrieving treeinfo from %s (proxy: %s ; ssl_verify: %s)",
                  url, proxy_url, ssl_verify)

        proxies = {}
        if proxy_url:
            try:
                proxy = ProxyString(proxy_url)
                proxies = {"http": proxy.url,
                           "https": proxy.url,
                           "ftp": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy for _getTreeInfo %s: %s",
                         proxy_url, e)

        headers = {"user-agent": constants.USER_AGENT}
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
        log.debug("getting release version from tree at %s", url)

        if self._install_tree_metadata:
            version = self._install_tree_metadata.get_release_version()
            log.debug("using treeinfo release version of %s", version)
        else:
            version = get_product_release_version()
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

    def _load_treeinfo_repositories(self, base_repo_url, repo_names_to_disable, data):
        """Load new repositories from treeinfo file.

        :param base_repo_url: base repository url. This is not saved anywhere when the function
                              is called. It will be add to the existing urls if not None.
        :param repo_names_to_disable: list of repository names which should be disabled after load
        :type repo_names_to_disable: [str]
        :param data: repo configuration data
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

                    # disable repositories disabled by user manually before
                    if repo_md.name in repo_names_to_disable:
                        repo_enabled = False
                    else:
                        repo_enabled = repo_treeinfo.type in enabled_repositories_from_treeinfo

                    repo = RepoData(
                        name=repo_md.name,
                        baseurl=repo_md.path,
                        noverifyssl=not data.ssl_verification_enabled,
                        proxy=data.proxy,
                        sslcacert=data.ssl_configuration.ca_cert_path,
                        sslclientcert=data.ssl_configuration.client_cert_path,
                        sslclientkey=data.ssl_configuration.client_key_path,
                        install=False,
                        enabled=repo_enabled
                    )
                    repo.treeinfo_origin = True
                    log.debug("Adding new treeinfo repository: %s enabled: %s",
                              repo_md.name, repo_enabled)

                    self.add_repo(repo)

    def _cleanup_old_treeinfo_repositories(self):
        """Remove all old treeinfo repositories before loading new ones.

        Find all repositories added from treeinfo file and remove them. After this step new
        repositories will be loaded from the new link.

        :return: list of repository names which were disabled before removal
        :rtype: [str]
        """
        disabled_repo_names = []

        for ks_repo_name in self.addons:
            repo = self.get_addon_repo(ks_repo_name)
            if repo.treeinfo_origin:
                log.debug("Removing old treeinfo repository %s", ks_repo_name)

                if not repo.enabled:
                    disabled_repo_names.append(ks_repo_name)

                self.remove_repo(ks_repo_name)

        return disabled_repo_names

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
                f.write("includepkgs=%s\n" % ",".join(ks_repo.includepkgs))

            if ks_repo.excludepkgs:
                f.write("excludepkgs=%s\n" % ",".join(ks_repo.excludepkgs))

    def post_setup(self):
        """Perform post-setup tasks.

        Save repomd hash to test if the repositories can be reached.
        """
        self._repoMD_list = []
        proxy_url = self._get_proxy_url()

        for repo in self._base.repos.iter_enabled():
            repoMD = RepoMDMetaHash(repo, proxy_url)
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

        # rpm needs importing installed certificates manually, see rhbz#748320 and rhbz#185800
        task = ImportRPMKeysTask(
            sysroot=conf.target.system_root,
            gpg_keys=conf.payload.default_rpm_gpg_keys
        )
        task.run()

        # Update the DNF configuration.
        task = UpdateDNFConfigurationTask(
            sysroot=conf.target.system_root,
            data=self.get_packages_data()
        )
        task.run()

    @property
    def kernel_version_list(self):
        return get_kernel_version_list()

    def match_available_packages(self, pattern):
        return self._dnf_manager.match_available_packages(pattern)
