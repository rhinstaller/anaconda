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
import os
import configparser
import collections
import multiprocessing
import operator
import hashlib
import shutil
import sys
import time
import threading
from requests.exceptions import RequestException

from pyanaconda.flags import flags
from pyanaconda.core.i18n import _, N_
from pyanaconda.progress import progressQ, progress_message
from pyanaconda.core.util import ProxyString, ProxyStringError
from pyanaconda.core import constants
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.simpleconfig import SimpleConfigFile
from pyanaconda.kickstart import RepoData
from pyanaconda.product import productName, productVersion
from pyanaconda.payload.errors import MetadataError, NoSuchGroup, DependencyError, \
    PayloadInstallError, PayloadSetupError, PayloadError

import pyanaconda.errors as errors
import pyanaconda.localization
import pyanaconda.payload as payload

import dnf
import dnf.logging
import dnf.exceptions
import dnf.repo
import dnf.callback
import dnf.transaction
import libdnf.conf
import dnf.conf.substitutions
import rpm
from dnf.const import GROUP_PACKAGE_TYPES

from blivet.size import Size
from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, KS_MISSING_IGNORE

from pyanaconda.anaconda_loggers import get_packaging_logger, get_dnf_logger
log = get_packaging_logger()


DNF_CACHE_DIR = '/tmp/dnf.cache'
DNF_PLUGINCONF_DIR = '/tmp/dnf.pluginconf'
DNF_PACKAGE_CACHE_DIR_SUFFIX = 'dnf.package.cache'
DNF_LIBREPO_LOG = '/tmp/dnf.librepo.log'
DOWNLOAD_MPOINTS = {'/tmp',
                    '/',
                    '/var/tmp',
                    '/mnt/sysimage',
                    '/mnt/sysimage/home',
                    '/mnt/sysimage/tmp',
                    '/mnt/sysimage/var',
                    }
REPO_DIRS = ['/etc/yum.repos.d',
             '/etc/anaconda.repos.d',
             '/tmp/updates/anaconda.repos.d',
             '/tmp/product/anaconda.repos.d']
YUM_REPOS_DIR = "/etc/yum.repos.d/"

USER_AGENT = "%s (anaconda)/%s" % (productName, productVersion)

# Bonus to required free space which depends on block size and rpm database size estimation.
# Every file could be aligned to fragment size so 4KiB * number_of_files should be a worst
# case scenario. 2KiB for RPM DB was acquired by testing.
# 6KiB = 4K(max default fragment size) + 2K(rpm db could be taken for a header file)
BONUS_SIZE_ON_FILE = Size("6 KiB")


def _failure_limbo():
    progressQ.send_quit(1)
    while True:
        time.sleep(10000)


def _df_map():
    """Return (mountpoint -> size available) mapping."""
    output = util.execWithCapture('df', ['--output=target,avail'])
    output = output.rstrip()
    lines = output.splitlines()
    structured = {}
    for line in lines:
        items = line.split()
        key = items[0]
        val = items[1]
        if not key.startswith('/'):
            continue
        structured[key] = Size(int(val) * 1024)

    # Add /var/tmp/ if this is a directory or image installation
    if not conf.target.is_hardware:
        var_tmp = os.statvfs("/var/tmp")
        structured["/var/tmp"] = Size(var_tmp.f_frsize * var_tmp.f_bfree)
    return structured


def _paced(fn):
    """Execute `fn` no more often then every 2 seconds."""
    def paced_fn(self, *args):
        now = time.time()
        if now - self.last_time < 2:
            return
        self.last_time = now
        return fn(self, *args)
    return paced_fn


def _pick_mpoint(df, download_size, install_size, download_only):
    def reasonable_mpoint(mpoint):
        return mpoint in DOWNLOAD_MPOINTS

    requested = download_size
    requested_root = requested + install_size
    root_mpoint = util.getSysroot()
    log.debug('Input mount points: %s', df)
    log.info('Estimated size: download %s & install %s', requested,
             (requested_root - requested))

    # Find sufficient mountpoint to download and install packages.
    sufficients = {key: val for (key, val) in df.items()
                   if ((key != root_mpoint and val > requested) or val > requested_root) and
                   reasonable_mpoint(key)}

    # If no sufficient mountpoints for download and install were found and we are looking
    # for download mountpoint only, ignore install size and try to find mountpoint just
    # to download packages. This fallback is required when user skipped space check.
    if not sufficients and download_only:
        sufficients = {key: val for (key, val) in df.items() if val > requested and
                       reasonable_mpoint(key)}
        if sufficients:
            log.info('Sufficient mountpoint for download only found: %s', sufficients)
    elif sufficients:
        log.info('Sufficient mountpoints found: %s', sufficients)

    if not sufficients:
        log.debug("No sufficient mountpoints found")
        return None

    sorted_mpoints = sorted(sufficients.items(), key=operator.itemgetter(1), reverse=True)

    # try to pick something else than root mountpoint for downloading
    if download_only and len(sorted_mpoints) >= 2 and sorted_mpoints[0][0] == root_mpoint:
        return sorted_mpoints[1][0]
    else:
        # default to the biggest one:
        return sorted_mpoints[0][0]


class PayloadRPMDisplay(dnf.callback.TransactionProgress):
    def __init__(self, queue_instance):
        super().__init__()
        self._queue = queue_instance
        self._last_ts = None
        self._postinst_phase = False
        self.cnt = 0

    def progress(self, package, action, ti_done, ti_total, ts_done, ts_total):
        # Process DNF actions, communicating with anaconda via the queue
        # A normal installation consists of 'install' messages followed by
        # the 'post' message.
        if action == dnf.transaction.PKG_INSTALL and ti_done == 0:
            # do not report same package twice
            if self._last_ts == ts_done:
                return
            self._last_ts = ts_done

            msg = '%s.%s (%d/%d)' % \
                (package.name, package.arch, ts_done, ts_total)
            self.cnt += 1
            self._queue.put(('install', msg))

            # Log the exact package nevra, build time and checksum
            nevra = "%s-%s.%s" % (package.name, package.evr, package.arch)
            log_msg = "Installed: %s %s %s" % (nevra, package.buildtime, package.returnIdSum()[1])
            self._queue.put(('log', log_msg))

        elif action == dnf.transaction.TRANS_POST:
            self._queue.put(('post', None))
            log_msg = "Post installation setup phase started."
            self._queue.put(('log', log_msg))
            self._postinst_phase = True

        elif action == dnf.transaction.PKG_SCRIPTLET:
            # Log the exact package nevra, build time and checksum
            nevra = "%s-%s.%s" % (package.name, package.evr, package.arch)
            log_msg = "Configuring (running scriptlet for): %s %s %s" % (nevra, package.buildtime,
                                                                         package.returnIdSum()[1])
            self._queue.put(('log', log_msg))

            # only show progress in UI for post-installation scriptlets
            if self._postinst_phase:
                msg = '%s.%s' % (package.name, package.arch)
                self._queue.put(('configure', msg))

        elif action == dnf.transaction.PKG_VERIFY:
            msg = '%s.%s (%d/%d)' % (package.name, package.arch, ts_done, ts_total)
            self._queue.put(('verify', msg))

            # Log the exact package nevra, build time and checksum
            nevra = "%s-%s.%s" % (package.name, package.evr, package.arch)
            log_msg = "Verifying: %s %s %s" % (nevra, package.buildtime, package.returnIdSum()[1])
            self._queue.put(('log', log_msg))

            # Once the last package is verified the transaction is over
            if ts_done == ts_total:
                self._queue.put(('done', None))

    def error(self, message):
        """Report an error that occurred during the transaction. Message is a
        string which describes the error.
        """
        self._queue.put(('error', message))


class DownloadProgress(dnf.callback.DownloadProgress):
    def __init__(self):
        super().__init__()
        self.downloads = collections.defaultdict(int)
        self.last_time = time.time()
        self.total_files = 0
        self.total_size = Size(0)

    @_paced
    def _update(self):
        msg = _('Downloading %(total_files)s RPMs, '
                '%(downloaded)s / %(total_size)s (%(percent)d%%) done.')
        downloaded = Size(sum(self.downloads.values()))
        vals = {
            'downloaded': downloaded,
            'percent': int(100 * downloaded / self.total_size),
            'total_files': self.total_files,
            'total_size': self.total_size
        }
        progressQ.send_message(msg % vals)

    def end(self, dnf_payload, status, msg):  # pylint: disable=arguments-differ
        nevra = str(dnf_payload)
        if status is dnf.callback.STATUS_OK:
            self.downloads[nevra] = dnf_payload.download_size
            self._update()
            return
        log.warning("Failed to download '%s': %d - %s", nevra, status, msg)

    def progress(self, dnf_payload, done):  # pylint: disable=arguments-differ
        nevra = str(dnf_payload)
        self.downloads[nevra] = done
        self._update()

    # TODO: Remove pylint disable after DNF-2.5.0 will arrive in Fedora
    def start(self, total_files, total_size, total_drpms=0):  # pylint: disable=arguments-differ
        self.total_files = total_files
        self.total_size = Size(total_size)


def do_transaction(base, queue_instance):
    # Execute the DNF transaction and catch any errors. An error doesn't
    # always raise a BaseException, so presence of 'quit' without a preceeding
    # 'post' message also indicates a problem.
    try:
        display = PayloadRPMDisplay(queue_instance)
        base.do_transaction(display=display)
        exit_reason = "DNF quit"
    except BaseException as e:  # pylint: disable=broad-except
        log.error('The transaction process has ended abruptly')
        log.info(e)
        import traceback
        exit_reason = str(e) + traceback.format_exc()
    finally:
        base.close()  # Always close this base.
        queue_instance.put(('quit', str(exit_reason)))


class DNFPayload(payload.PackagePayload):
    def __init__(self, data):
        super().__init__(data)

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

    def unsetup(self):
        super().unsetup()
        self._base = None
        self._configure()
        self._repoMD_list = []

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
        repo.sslverify = not (ksrepo.noverifyssl or flags.noverifyssl)
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

    def _fetch_md(self, repo):
        """Download repo metadata

        :param repo: name/id of repo to fetch
        :type repo: str
        :returns: None
        """
        ksrepo = self._base.repos[repo]
        ksrepo.enable()
        try:
            # Load the metadata to verify that the repo is valid
            ksrepo.load()
        except dnf.exceptions.RepoError as e:
            ksrepo.disable()
            log.debug("repo: '%s' - %s failed to load repomd", ksrepo.name,
                      ksrepo.baseurl or ksrepo.mirrorlist or ksrepo.metalink)
            raise MetadataError(e)

        log.info("enabled repo: '%s' - %s and got repomd", ksrepo.name,
                 ksrepo.baseurl or ksrepo.mirrorlist or ksrepo.metalink)

    def add_repo(self, ksrepo):
        """Add an enabled repo to dnf and kickstart repo lists.

        :param ksrepo: Kickstart Repository to add
        :type ksrepo: Kickstart RepoData object.
        :returns: None
        """
        self._add_repo(ksrepo)
        self._fetch_md(ksrepo.name)
        super().add_repo(ksrepo)

    def _enable_modules(self):
        """Enable modules (if any)."""
        # convert data from kickstart to module specs
        module_specs = []
        for module in self.data.module.dataList():
            # stream definition is optional
            if module.stream:
                module_spec = "{name}:{stream}".format(name=module.name, stream=module.stream)
            else:
                module_spec = module.name
            module_specs.append(module_spec)

        # forward the module specs to enable to DNF
        log.debug("enabling modules: %s", module_specs)
        try:
            module_base = dnf.module.module_base.ModuleBase(self._base)
            module_base.enable(module_specs)
        except dnf.exceptions.MarkingErrors as e:
            log.debug("ModuleBase.enable(): some packages, groups or modules are "
                      "missing or broken:\n%s", e)
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
            log.info("skipping core group due to %%packages --nocore; system may not be complete")
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
                group_spec = "@{group_name}/{types}".format(group_name=group.name, types=types)
            else:
                # if group is a regular group this is equal to @group/mandatory,default,conditional
                # (current content of the DNF GROUP_PACKAGE_TYPES constant)
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
            # install_specs() returns a list of specs that appear to be missing
            self._base.install_specs(install=include_list, exclude=exclude_list)
        except dnf.exceptions.MarkingErrors as e:
            log.debug("install_specs(): some packages, groups or modules "
                      " are missing or broken:\n%s", e)
            # if no errors were reported and --ignoremissing was used we can continue
            transaction_broken = e.error_group_specs or \
                e.error_pkg_specs or \
                e.module_debsolv_errors
            if not transaction_broken and self.data.packages.handleMissing == KS_MISSING_IGNORE:
                log.info("ignoring missing package/group/module specs due to --ingoremissing flag "
                         "in kickstart")
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
        config.installroot = util.getSysroot()
        config.prepend_installroot('persistdir')

        self._base.conf.substitutions.update_from_etc(config.installroot)

        if self.data.packages.multiLib:
            config.multilib_policy = "all"

        if self.data.packages.timeout is not None:
            config.timeout = self.data.packages.timeout

        if self.data.packages.retries is not None:
            config.retries = self.data.packages.retries

        self._configure_proxy()

        # Start with an empty comps so we can go ahead and use the environment
        # and group properties. Unset reposdir to ensure dnf has nothing it can
        # check automatically
        config.reposdir = []
        self._base.read_comps()

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
        df_map = _df_map()
        mpoint = _pick_mpoint(df_map, download_size, install_size, download_only=True)
        if mpoint is None:
            msg = ("Not enough disk space to download the packages; size %s." % download_size)
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
                log.warning("Selected lang %s does not match any available langpack", lang)
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
        # is any locking needed here?
        repo_names = [constants.BASE_REPO_NAME] + constants.DEFAULT_REPOS
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                if repo.id in repo_names:
                    return repo.id
        return None

    @property
    def environments(self):
        return [env.id for env in self._base.comps.environments]

    @property
    def groups(self):
        groups = self._base.comps.groups_iter()
        return [g.id for g in groups]

    @property
    def repos(self):
        # known repo ids
        with self._repos_lock:
            return [r.id for r in self._base.repos.values()]

    @property
    def space_required(self):
        size = self._space_required()
        if not self.storage:
            log.warning("Payload doesn't have storage")
            return size

        download_size = self._download_space
        valid_points = _df_map()
        root_mpoint = util.getSysroot()
        for (key, val) in self.storage.mountpoints.items():
            new_key = key
            if key.endswith('/'):
                new_key = key[:-1]
            # we can ignore swap
            if key.startswith('/') and ((root_mpoint + new_key) not in valid_points):
                valid_points[root_mpoint + new_key] = val.format.free_space_estimate(val.size)

        m_point = _pick_mpoint(valid_points, download_size, size, download_only=False)
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
        self._enable_modules()
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

        if self._updates_enabled:
            self.enable_repo("updates")
            if not constants.isFinal:
                self.enable_repo("updates-testing")
        else:
            self.disable_repo("updates")
            if not constants.isFinal:
                self.disable_repo("updates-testing")

    def disable_repo(self, repo_id):
        try:
            self._base.repos[repo_id].disable()
            log.info("Disabled '%s'", repo_id)
        except KeyError:
            pass
        super().disable_repo(repo_id)

    def enable_repo(self, repo_id):
        try:
            self._base.repos[repo_id].enable()
            log.info("Enabled '%s'", repo_id)
        except KeyError:
            pass
        super().enable_repo(repo_id)

    def environment_description(self, environment_id):
        env = self._base.comps.environment_by_pattern(environment_id)
        if env is None:
            raise NoSuchGroup(environment_id)
        return (env.ui_name, env.ui_description)

    def environment_id(self, environment):
        """Return environment id for the environment specified by id or name."""
        # the enviroment must be string or else DNF >=3 throws an assert error
        if not isinstance(environment, str):
            log.warning("environment_id() called with non-string argument: %s", environment)
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
        self._base.read_comps()
        self._refresh_environment_addons()

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
                _failure_limbo()

        if os.path.exists(self._download_location):
            log.info("Removing existing package download location: %s", self._download_location)
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
                _failure_limbo()

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
                    _failure_limbo()
            (token, msg) = queue_instance.get()

        process.join()
        # Don't close the mother base here, because we still need it.
        if os.path.exists(self._download_location):
            log.info("Cleaning up downloaded packages: %s", self._download_location)
            shutil.rmtree(self._download_location)
        else:
            # Some installation sources, such as NFS, don't need to download packages to
            # local storage, so the download location might not always exist. So for now
            # warn about this, at least until the RFE in bug 1193121 is implemented and
            # we don't have to care about clearing the download location ourselves.
            log.warning("Can't delete nonexistent download location: %s", self._download_location)

    def get_repo(self, repo_id):
        """Return the yum repo object."""
        return self._base.repos[repo_id]

    def is_repo_enabled(self, repo_id):
        try:
            return self._base.repos[repo_id].enabled
        except (dnf.exceptions.RepoError, KeyError):
            return super().is_repo_enabled(repo_id)

    def verify_available_repositories(self):
        """Verify availability of repositories."""
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
        super().reset()
        shutil.rmtree(DNF_CACHE_DIR, ignore_errors=True)
        shutil.rmtree(DNF_PLUGINCONF_DIR, ignore_errors=True)
        self.tx_id = None
        self._base.reset(sack=True, repos=True)
        self._configure_proxy()
        self._repoMD_list = []

    def update_base_repo(self, fallback=True, checkmount=True):
        log.info('configuring base repo')
        self.reset()
        install_tree_url, mirrorlist, metalink = self._setup_install_device(self.storage,
                                                                            checkmount)

        # Fallback to installation root
        base_repo_url = install_tree_url

        method = self.data.method
        sslverify = True
        if method.method == "url":
            sslverify = not (method.noverifyssl or flags.noverifyssl)

        # Read in all the repos from the installation environment, make a note of which
        # are enabled, and then disable them all.  If the user gave us a method, we want
        # to use that instead of the default repos.
        self._base.read_all_repos()

        # If setup updates/updates-testing
        self.set_updates_enabled(self._updates_enabled)

        # Repos on disk are always enabled. When reloaded their state needs to
        # be synchronized with the user selection.
        enabled = []
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                enabled.append(repo.id)
                repo.disable()

        # If askmethod was specified on the command-line, leave all the repos
        # disabled and return
        if flags.askmethod:
            return

        if method.method:
            try:
                self._refresh_install_tree(install_tree_url)
                self._base.conf.releasever = self._get_release_version(install_tree_url)
                base_repo_url = self._get_base_repo_location(install_tree_url)

                if self.first_payload_reset:
                    self._add_treeinfo_repositories(install_tree_url, base_repo_url)

                log.debug("releasever from %s is %s", base_repo_url, self._base.conf.releasever)
            except configparser.MissingSectionHeaderError as e:
                log.error("couldn't set releasever from base repo (%s): %s",
                          method.method, e)

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
                ksrepo.baseurl = self._setup_harddrive_addon_repo(self.storage, ksrepo)

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
            for repo in self.addons:
                if repo in enabled_repos:
                    self._fetch_md(repo)

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

            for ksrepo in self.data.repo.dataList():
                existing_urls.append(ksrepo.baseurl)

            for repo_md in self._install_tree_metadata.get_metadata_repos():
                if repo_md.path not in existing_urls:
                    repo = RepoData(name=repo_md.name, baseurl=repo_md.path,
                                    install=False, enabled=True)
                    repo.treeinfo_origin = True
                    self.data.repo.dataList().append(repo)

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
            repo_path = util.getSysroot() + YUM_REPOS_DIR + "%s.repo" % repo.id
            try:
                log.info("Writing %s.repo to target system.", repo.id)
                self._write_dnf_repo(repo, repo_path)
            except PayloadSetupError as e:
                log.error(e)

        # We don't need the mother base anymore. Close it.
        self._base.close()
        super().post_install()


class RepoMDMetaHash(object):
    """Class that holds hash of a repomd.xml file content from a repository.
    This class can test availability of this repository by comparing hashes.
    """
    def __init__(self, dnf_payload, repo):
        self._repoId = repo.id
        self._method = dnf_payload.data.method
        self._urls = repo.baseurl
        self._repomd_hash = ""

    @property
    def repoMD_hash(self):
        """Return SHA256 hash of the repomd.xml file stored."""
        return self._repomd_hash

    @property
    def id(self):
        """Name of the repository."""
        return self._repoId

    def store_repoMD_hash(self):
        """Download and store hash of the repomd.xml file content."""
        repomd = self._download_repoMD(self._method)
        self._repomd_hash = self._calculate_hash(repomd)

    def verify_repoMD(self):
        """Download and compare with stored repomd.xml file."""
        new_repomd = self._download_repoMD(self._method)
        new_repomd_hash = self._calculate_hash(new_repomd)
        return new_repomd_hash == self._repomd_hash

    def _calculate_hash(self, data):
        m = hashlib.sha256()
        m.update(data.encode('ascii', 'backslashreplace'))
        return m.digest()

    def _download_repoMD(self, method):
        proxies = {}
        repomd = ""
        headers = {"user-agent": USER_AGENT}
        sslverify = not flags.noverifyssl

        if hasattr(method, "proxy"):
            proxy_url = method.proxy
            try:
                proxy = ProxyString(proxy_url)
                proxies = {"http": proxy.url,
                           "https": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy for test if repo available %s: %s",
                         proxy_url, e)

        session = util.requests_session()

        # Test all urls for this repo. If any of these is working it is enough.
        for url in self._urls:
            try:
                result = session.get("%s/repodata/repomd.xml" % url, headers=headers,
                                     proxies=proxies, verify=sslverify)
                if result.ok:
                    repomd = result.text
                    break
                else:
                    log.debug("Server returned %i code when downloading repomd",
                              result.status_code)
                    continue
            except RequestException as e:
                log.debug("Can't download new repomd.xml from %s with proxy: %s. Error: %s",
                          url, proxies, e)

        return repomd
