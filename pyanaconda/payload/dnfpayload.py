# dnfpayload.py
# DNF/rpm software payload management.
#
# Copyright (C) 2013-2015  Red Hat, Inc.
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

from blivet.size import Size
from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, KS_MISSING_IGNORE
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _, N_
from pyanaconda.progress import progressQ, progress_message
from pyanaconda.core.util import ProxyString, ProxyStringError
from pyanaconda.core import constants
from pyanaconda.core import util
from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.simpleconfig import SimpleConfigFile

import pyanaconda.errors as errors
import pyanaconda.localization
import pyanaconda.payload as payload

import configparser
import collections
import itertools
import multiprocessing
import operator
import hashlib
import shutil
import sys
import time
import threading
from requests.exceptions import RequestException


from pyanaconda.anaconda_loggers import get_packaging_logger, get_dnf_logger
log = get_packaging_logger()

import dnf
import dnf.logging
import dnf.exceptions
import dnf.repo
import dnf.callback
import dnf.transaction
import libdnf.conf
import dnf.conf.substitutions
import rpm
import librepo

from dnf.const import GROUP_PACKAGE_TYPES

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

from pyanaconda.product import productName, productVersion
USER_AGENT = "%s (anaconda)/%s" % (productName, productVersion)

# Bonus to required free space which depends on block size and rpm database size estimation.
# Every file could be aligned to fragment size so 4KiB * number_of_files should be a worst
# case scenario. 2KiB for RPM DB was acquired by testing.
# 6KiB = 4K(max default fragment size) + 2K(rpm db could be taken for a header file)
BONUS_SIZE_ON_FILE = Size("6 KiB")

class InstallSpecsMissing(Exception):
    """Raised is some of the requested install specs seems to be missing from the repos."""
    def __init__(self, missing_specs):
        super().__init__()
        self.missing_specs = missing_specs
        self.missing_packages = []
        self.missing_groups_and_modules=[]
        for spec in missing_specs:
            if spec.startswith("@"):
                self.missing_groups_and_modules.append(spec)
            else:
                self.missing_packages.append(spec)

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
    if flags.dirInstall or flags.imageInstall:
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
                   if ((key != root_mpoint and val > requested) or val > requested_root) and reasonable_mpoint(key)}

    # If no sufficient mountpoints for download and install were found and we are looking
    # for download mountpoint only, ignore install size and try to find mountpoint just
    # to download packages. This fallback is required when user skipped space check.
    if not sufficients and download_only:
        sufficients = {key: val for (key, val) in df.items() if val > requested and reasonable_mpoint(key)}
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
            log_msg = "Configuring (running scriptlet for): %s %s %s" % (nevra, package.buildtime, package.returnIdSum()[1])
            self._queue.put(('log', log_msg))

            # only show progress in UI for post-installation scriptlets
            if self._postinst_phase:
                msg = '%s.%s' % (package.name, package.arch)
                #self.cnt += 1
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
            'downloaded'  : downloaded,
            'percent'     : int(100 * downloaded / self.total_size),
            'total_files' : self.total_files,
            'total_size'  : self.total_size
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
    def start(self, total_files, total_size, total_drpms=0): # pylint: disable=arguments-differ
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
    except BaseException as e:
        log.error('The transaction process has ended abruptly')
        log.info(e)
        import traceback
        exit_reason = str(e) + traceback.format_exc()
    finally:
        base.close() # Always close this base.
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
            self._setupNFS(mountpoint, server, path, None)

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

        # If this repo is already known, it's one of two things:
        # (1) The user is trying to do "repo --name=updates" in a kickstart file
        #     and we should just know to enable the already existing on-disk
        #     repo config.
        # (2) It's a duplicate, and we need to delete the existing definition
        #     and use this new one.  The highest profile user of this is livecd
        #     kickstarts.
        if repo.id in self._base.repos:
            if url or mirrorlist or metalink:
                with self._repos_lock:
                    self._base.repos.pop(repo.id)
                    self._base.repos.add(repo)
        # If the repo's not already known, we've got to add it.
        else:
            with self._repos_lock:
                self._base.repos.add(repo)

        if not ksrepo.enabled:
            self.disableRepo(repo.id)

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
            raise payload.MetadataError(e)

        log.info("enabled repo: '%s' - %s and got repomd", ksrepo.name,
                 ksrepo.baseurl or ksrepo.mirrorlist or ksrepo.metalink)

    def addRepo(self, ksrepo):
        """Add an enabled repo to dnf and kickstart repo lists.

        :param ksrepo: Kickstart Repository to add
        :type ksrepo: Kickstart RepoData object.
        :returns: None
        """
        self._add_repo(ksrepo)
        self._fetch_md(ksrepo.name)
        super().addRepo(ksrepo)

    def addDisabledRepo(self, ksrepo):
        """Add a disabled repo to dnf and kickstart repo lists.

        :param ksrepo: Kickstart Repository to add
        :type ksrepo: Kickstart RepoData object.
        :returns: None
        """
        ksrepo.disable()
        self._add_repo(ksrepo)
        super().addDisabledRepo(ksrepo)
    def _enable_modules(self):
        """Enable modules (if any)."""
        for module in self.data.module.dataList():
            # stream definition is optional
            if module.stream:
                module_spec = "{name}:{stream}".format(name=module.name, stream=module.stream)
            else:
                module_spec = module.name
            log.debug("enabling module: %s", module_spec)
            try:
                self._base.enable_module([module_spec])
            except dnf.module.exceptions.NoModuleException as e:
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
            missing_specs = self._base.install_specs(install=include_list, exclude=exclude_list)
            if missing_specs:
                if self.data.packages.handleMissing == KS_MISSING_IGNORE:
                    log.info("ignoring missing package/group/module specs due to --ingoremissing flag in kickstart: %s", missing_specs)
                else:
                    log.debug("install_specs() reports that some specs are missing: %s", missing_specs)
                    raise InstallSpecsMissing(missing_specs)
        except Exception as e:  # pylint: disable=broad-except
            self._payload_setup_error(e)

    def _apply_requirements(self, requirements):
        self._req_groups = set()
        self._req_packages = set()
        for req in self.requirements.packages:
            ignore_msgs = []
            if req.id in self.instclass.ignoredPackages:
                ignore_msgs.append("IGNORED by install class %s" % self.instclass)
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
        if self.txID is None:
            self.txID = 1
        else:
            self.txID += 1
        return self.txID

    def _configure_proxy(self):
        """Configure the proxy on the dnf.Base object."""
        conf = self._base.conf

        if hasattr(self.data.method, "proxy") and self.data.method.proxy:
            try:
                proxy = ProxyString(self.data.method.proxy)
                conf.proxy = proxy.noauth_url
                if proxy.username:
                    conf.proxy_username = proxy.username
                if proxy.password:
                    conf.proxy_password = proxy.password
                log.info("Using %s as proxy", self.data.method.proxy)
            except ProxyStringError as e:
                log.error("Failed to parse proxy for dnf configure %s: %s",
                          self.data.method.proxy, e)
        else:
            # No proxy configured
            conf.proxy = None
            conf.proxy_username = None
            conf.proxy_password = None

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
        conf = self._base.conf
        conf.cachedir = DNF_CACHE_DIR
        conf.pluginconfpath = DNF_PLUGINCONF_DIR
        conf.logdir = '/tmp/'
        # enable depsolver debugging if in debug mode
        self._base.conf.debug_solver = flags.debug
        # set the platform id based on the /os/release
        # present in the installation environment
        platform_id = self.get_platform_id()
        if platform_id is not None:
            log.info("setting DNF platform id to: %s", platform_id)
            self._base.conf.module_platform_id = platform_id

        conf.releasever = self._getReleaseVersion(None)
        conf.installroot = util.getSysroot()
        conf.prepend_installroot('persistdir')

        self._base.conf.substitutions.update_from_etc(conf.installroot)

        # NSS won't survive the forking we do to shield out chroot during
        # transaction, disable it in RPM:
        conf.tsflags.append('nocrypto')

        if self.data.packages.multiLib:
            conf.multilib_policy = "all"

        if self.data.packages.timeout is not None:
            conf.timeout = self.data.packages.timeout

        if self.data.packages.retries is not None:
            conf.retries = self.data.packages.retries

        self._configure_proxy()

        # Start with an empty comps so we can go ahead and use the environment
        # and group properties. Unset reposdir to ensure dnf has nothing it can
        # check automatically
        conf.reposdir = []
        self._base.read_comps()

        conf.reposdir = REPO_DIRS

        # Two reasons to turn this off:
        # 1. Minimal installs don't want all the extras this brings in.
        # 2. Installs aren't reproducible due to weak deps. failing silently.
        if self.data.packages.excludeWeakdeps:
            conf.install_weak_deps = False

        # Setup librepo logging
        librepo.log_set_file(DNF_LIBREPO_LOG)

        # Increase dnf log level to custom DDEBUG level
        # Do this here to prevent import side-effects in anaconda_logging
        dnf_logger = get_dnf_logger()
        dnf_logger.setLevel(dnf.logging.DDEBUG)

        log.debug("Dnf configuration:\n%s", conf.dump())

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
        install_size = self._spaceRequired()
        df_map = _df_map()
        mpoint = _pick_mpoint(df_map, download_size, install_size, download_only=True)
        if mpoint is None:
            msg = ("Not enough disk space to download the packages; size %s." % download_size)
            raise payload.PayloadError(msg)

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
        kernels = self.kernelPackages
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
            self.disableRepo(id_)
            self.verbose_errors.append(str(e))
        log.debug('repo %s: _sync_metadata success from %s', dnf_repo.id,
                 dnf_repo.baseurl or dnf_repo.mirrorlist or dnf_repo.metalink)

    @property
    def baseRepo(self):
        # is any locking needed here?
        repo_names = [constants.BASE_REPO_NAME] + self.DEFAULT_REPOS
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
    def spaceRequired(self):
        size = self._spaceRequired()
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
            log.debug("Download space required %s for mpoint %s (non-chroot)", download_size, m_point)
            log.debug("Installation space required %s", size)
        return size

    def _spaceRequired(self):
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

    def _isGroupVisible(self, grpid):
        grp = self._base.comps.group_by_pattern(grpid)
        if grp is None:
            raise payload.NoSuchGroup(grpid)
        return grp.visible

    def _groupHasInstallableMembers(self, grpid):
        return True

    def checkSoftwareSelection(self):
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
            raise payload.DependencyError(msg)

        log.info("%d packages selected totalling %s",
                 len(self._base.transaction), self.spaceRequired)

    def setUpdatesEnabled(self, state):
        """Enable or Disable the repos used to update closest mirror.

        :param bool state: True to enable updates, False to disable.
        """
        self._updates_enabled = state

        if self._updates_enabled:
            self.enableRepo("updates")
            if not constants.isFinal:
                self.enableRepo("updates-testing")
        else:
            self.disableRepo("updates")
            if not constants.isFinal:
                self.disableRepo("updates-testing")

    def disableRepo(self, repo_id):
        try:
            self._base.repos[repo_id].disable()
            log.info("Disabled '%s'", repo_id)
        except KeyError:
            pass
        super().disableRepo(repo_id)

    def enableRepo(self, repo_id):
        try:
            self._base.repos[repo_id].enable()
            log.info("Enabled '%s'", repo_id)
        except KeyError:
            pass
        super().enableRepo(repo_id)

    def environmentDescription(self, environmentid):
        env = self._base.comps.environment_by_pattern(environmentid)
        if env is None:
            raise payload.NoSuchGroup(environmentid)
        return (env.ui_name, env.ui_description)

    def environmentId(self, environment):
        """Return environment id for the environment specified by id or name."""
        # the enviroment must be string or else DNF >=3 throws an assert error
        if not isinstance(environment, str):
            log.warning("environmentId() called with non-string argument: %s", environment)
        env = self._base.comps.environment_by_pattern(environment)
        if env is None:
            raise payload.NoSuchGroup(environment)
        return env.id

    def environmentGroups(self, environmentid, optional=True):
        env = self._base.comps.environment_by_pattern(environmentid)
        if env is None:
            raise payload.NoSuchGroup(environmentid)
        group_ids = (id_.name for id_ in env.group_ids)
        option_ids = (id_.name for id_ in env.option_ids)
        if optional:
            return list(itertools.chain(group_ids, option_ids))
        else:
            return list(group_ids)

    def environmentHasOption(self, environmentid, grpid):
        env = self._base.comps.environment_by_pattern(environmentid)
        if env is None:
            raise payload.NoSuchGroup(environmentid)
        return grpid in (id_.name for id_ in env.option_ids)

    def environmentOptionIsDefault(self, environmentid, grpid):
        env = self._base.comps.environment_by_pattern(environmentid)
        if env is None:
            raise payload.NoSuchGroup(environmentid)

        # Look for a group in the optionlist that matches the group_id and has
        # default set
        return any(grp for grp in env.option_ids if grp.name == grpid and grp.default)

    def groupDescription(self, grpid):
        """Return name/description tuple for the group specified by id."""
        grp = self._base.comps.group_by_pattern(grpid)
        if grp is None:
            raise payload.NoSuchGroup(grpid)
        return (grp.ui_name, grp.ui_description)

    def groupId(self, group_name):
        """Translate group name to group ID.

        :param group_name: Valid identifier for group specification.
        :returns: Group ID.
        :raise NoSuchGroup: If group_name doesn't exists.
        :raise PayloadError: When Yum's groups are not available.
        """
        grp = self._base.comps.group_by_pattern(group_name)
        if grp is None:
            raise payload.NoSuchGroup(group_name)
        return grp.id

    def gatherRepoMetadata(self):
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                self._sync_metadata(repo)
        self._base.fill_sack(load_system_repo=False)
        self._base.read_comps()
        self._refreshEnvironmentAddons()

    def install(self):
        progress_message(N_('Starting package installation process'))

        # Add the rpm macros to the global transaction environment
        for macro in self.rpmMacros:
            rpm.addMacro(macro[0], macro[1])

        if self.install_device:
            self._setupMedia(self.install_device)
        try:
            self.checkSoftwareSelection()
            self._download_location = self._pick_download_location()
        except payload.PayloadError as e:
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
            exc = payload.PayloadInstallError(msg)
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
                raise payload.PayloadError(msg)
            elif token == 'error':
                exc = payload.PayloadInstallError("DNF error: %s" % msg)
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

    def getRepo(self, repo_id):
        """Return the yum repo object."""
        return self._base.repos[repo_id]

    def isRepoEnabled(self, repo_id):
        try:
            return self._base.repos[repo_id].enabled
        except (dnf.exceptions.RepoError, KeyError):
            return super().isRepoEnabled(repo_id)

    def verifyAvailableRepositories(self):
        """Verify availability of repositories."""
        if not self._repoMD_list:
            return False

        for repo in self._repoMD_list:
            if not repo.verify_repoMD():
                log.debug("Can't reach repo %s", repo.id)
                return False
        return True

    def languageGroups(self):
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
        self.txID = None
        self._base.reset(sack=True, repos=True)
        self._configure_proxy()
        self._repoMD_list = []

    def updateBaseRepo(self, fallback=True, checkmount=True):
        log.info('configuring base repo')
        self.reset()
        url, mirrorlist, metalink = self._setupInstallDevice(self.storage, checkmount)

        method = self.data.method
        sslverify = True
        if method.method == "url":
            sslverify = not (method.noverifyssl or flags.noverifyssl)

        # Read in all the repos from the installation environment, make a note of which
        # are enabled, and then disable them all.  If the user gave us a method, we want
        # to use that instead of the default repos.
        self._base.read_all_repos()

        # If setup updates/updates-testing
        self.setUpdatesEnabled(self._updates_enabled)

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
                self._refreshTreeInfo(url)
                self._base.conf.releasever = self._getReleaseVersion(url)
                log.debug("releasever from %s is %s", url, self._base.conf.releasever)
            except configparser.MissingSectionHeaderError as e:
                log.error("couldn't set releasever from base repo (%s): %s",
                          method.method, e)

            try:
                proxy = getattr(method, "proxy", None)
                base_ksrepo = self.data.RepoData(
                    name=constants.BASE_REPO_NAME, baseurl=url,
                    mirrorlist=mirrorlist, metalink=metalink,
                    noverifyssl=not sslverify, proxy=proxy)
                self._add_repo(base_ksrepo)
                self._fetch_md(base_ksrepo.name)
            except (payload.MetadataError, payload.PayloadError) as e:
                log.error("base repo (%s/%s) not valid -- removing it",
                          method.method, url)
                log.error("reason for repo removal: %s", e)
                with self._repos_lock:
                    self._base.repos.pop(constants.BASE_REPO_NAME, None)
                if not fallback:
                    with self._repos_lock:
                        for repo in self._base.repos.iter_enabled():
                            self.disableRepo(repo.id)
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

        for repo in self.addOns:
            ksrepo = self.getAddOnRepo(repo)
            log.debug("repo %s: mirrorlist %s, baseurl %s, metalink %s",
                      ksrepo.name, ksrepo.mirrorlist, ksrepo.baseurl, ksrepo.metalink)
            # one of these must be set to create new repo
            if not (ksrepo.mirrorlist or ksrepo.baseurl or ksrepo.metalink or
                    ksrepo.name in self._base.repos):
                raise payload.PayloadSetupError("Repository %s has no mirror, baseurl or metalink set "
                                                "and is not one of the pre-defined repositories"
                                                % ksrepo.name)

            self._add_repo(ksrepo)

        with self._repos_lock:

            # disable unnecessary repos
            for repo in self._base.repos.iter_enabled():
                id_ = repo.id
                if 'source' in id_ or 'debuginfo' in id_:
                    self.disableRepo(id_)
                elif constants.isFinal and 'rawhide' in id_:
                    self.disableRepo(id_)

            # fetch md for enabled repos
            enabled_repos = self.enabledRepos
            for repo in self.addOns:
                if repo in enabled_repos:
                    self._fetch_md(repo)

    def _writeDNFRepo(self, repo, repo_path):
        """Write a repo object to a DNF repo.conf file.

        :param repo: DNF repository object
        :param string repo_path: Path to write the repo to
        :raises: PayloadSetupError if the repo doesn't have a url
        """
        with open(repo_path, "w") as f:
            f.write("[%s]\n" % repo.id)
            f.write("name=%s\n" % repo.id)
            if self.isRepoEnabled(repo.id):
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
                raise payload.PayloadSetupError("The repo {} has no baseurl, mirrorlist or "
                                                "metalink".format(repo.id))

            # kickstart repo modifiers
            ks_repo = self.getAddOnRepo(repo.id)
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

    def postSetup(self):
        """Perform post-setup tasks.

        Save repomd hash to test if the repositories can be reached.
        """
        self._repoMD_list = []
        for repo in self._base.repos.iter_enabled():
            repoMD = RepoMDMetaHash(self, repo)
            repoMD.store_repoMD_hash()
            self._repoMD_list.append(repoMD)

    def postInstall(self):
        """Perform post-installation tasks."""
        # Write selected kickstart repos to target system
        for ks_repo in (ks for ks in (self.getAddOnRepo(r) for r in self.addOns) if ks.install):
            if ks_repo.baseurl.startswith("nfs://"):
                log.info("Skip writing nfs repo %s to target system.", ks_repo.name)
                continue

            try:
                repo = self.getRepo(ks_repo.name)
                if not repo:
                    continue
            except (dnf.exceptions.RepoError, KeyError):
                continue
            repo_path = util.getSysroot() + YUM_REPOS_DIR + "%s.repo" % repo.id
            try:
                log.info("Writing %s.repo to target system.", repo.id)
                self._writeDNFRepo(repo, repo_path)
            except payload.PayloadSetupError as e:
                log.error(e)

        # We don't need the mother base anymore. Close it.
        self._base.close()
        super().postInstall()

    def writeStorageLate(self):
        pass


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
                    log.debug("Server returned %i code when downloading repomd", result.status_code)
                    continue
            except RequestException as e:
                log.debug("Can't download new repomd.xml from %s with proxy: %s. Error: %s", url, proxies, e)

        return repomd
