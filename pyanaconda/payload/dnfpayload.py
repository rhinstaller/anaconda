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

from pyanaconda.dbus import DBus
from pyanaconda.dbus.constants import MODULE_LOCALIZATION_NAME, MODULE_LOCALIZATION_PATH

from blivet.size import Size
from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, KS_MISSING_IGNORE
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _, N_
from pyanaconda.progress import progressQ, progress_message
from pyanaconda.core.util import ProxyString, ProxyStringError
from pyanaconda.core import constants
from pyanaconda.core import util

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
import dnf.conf.parser
import dnf.conf.substitutions
import rpm
import librepo

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
        super(PayloadRPMDisplay, self).__init__()
        self._queue = queue_instance
        self._last_ts = None
        self._postinst_phase = False
        self.cnt = 0

    def progress(self, package, action, ti_done, ti_total, ts_done, ts_total):
        # Process DNF actions, communicating with anaconda via the queue
        # A normal installation consists of 'install' messages followed by
        # the 'post' message.
        if action == self.PKG_INSTALL and ti_done == 0:
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

        elif action == self.TRANS_POST:
            self._queue.put(('post', None))
            log_msg = "Post installation setup phase started."
            self._queue.put(('log', log_msg))
            self._postinst_phase = True

        elif action == self.PKG_SCRIPTLET:
            # Log the exact package nevra, build time and checksum
            nevra = "%s-%s.%s" % (package.name, package.evr, package.arch)
            log_msg = "Configuring (running scriptlet for): %s %s %s" % (nevra, package.buildtime, package.returnIdSum()[1])
            self._queue.put(('log', log_msg))

            # only show progress in UI for post-installation scriptlets
            if self._postinst_phase:
                msg = '%s.%s' % (package.name, package.arch)
                #self.cnt += 1
                self._queue.put(('configure', msg))

        elif action == self.PKG_VERIFY:
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
        base.close()
        queue_instance.put(('quit', str(exit_reason)))


class DNFPayload(payload.PackagePayload):
    def __init__(self, data):
        payload.PackagePayload.__init__(self, data)

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

        self.requirements.set_apply_callback(self._apply_requirements)

    def unsetup(self):
        super(DNFPayload, self).unsetup()
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
            return dnf.conf.parser.substitute(url, self._base.conf.substitutions)

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
            if not url and not mirrorlist and not metalink:
                self._base.repos[repo.id].enable()
            else:
                with self._repos_lock:
                    self._base.repos.pop(repo.id)
                    self._base.repos.add(repo)
                repo.enable()
        # If the repo's not already known, we've got to add it.
        else:
            with self._repos_lock:
                self._base.repos.add(repo)
            repo.enable()

        # Load the metadata to verify that the repo is valid
        try:
            self._base.repos[repo.id].load()
        except dnf.exceptions.RepoError as e:
            raise payload.MetadataError(e)

        log.info("added repo: '%s' - %s", ksrepo.name, url or mirrorlist or metalink)

    def addRepo(self, ksrepo):
        """Add a repo to dnf and kickstart repo lists.

        :param ksrepo: Kickstart Repository to add
        :type ksrepo: Kickstart RepoData object.
        :returns: None
        """
        self._add_repo(ksrepo)
        super(DNFPayload, self).addRepo(ksrepo)

    def _apply_selections(self):
        if self.data.packages.nocore:
            log.info("skipping core group due to %%packages --nocore; system may not be complete")
        else:
            try:
                self._select_group('core', required=True)
                log.info("selected group: core")
            except payload.NoSuchGroup as e:
                self._miss(e)

        env = None

        if self.data.packages.default and self.environments:
            env = self.environments[0]
        elif self.data.packages.environment:
            env = self.data.packages.environment

        excludedGroups = [group.name for group in self.data.packages.excludedGroupList]

        if env:
            try:
                self._select_environment(env, excludedGroups)
                log.info("selected env: %s", env)
            except payload.NoSuchGroup as e:
                self._miss(e)

        for group in self.data.packages.groupList:
            if group.name == 'core' or group.name in excludedGroups:
                continue

            default = group.include in (GROUP_ALL,
                                        GROUP_DEFAULT)
            optional = group.include == GROUP_ALL

            try:
                self._select_group(group.name, default=default, optional=optional)
                log.info("selected group: %s", group.name)
            except payload.NoSuchGroup as e:
                self._miss(e)

        for pkg_name in self.data.packages.excludedList:
            self._exclude_package(pkg_name)
            log.info("excluded package: '%s'", pkg_name)

        for pkg_name in self.data.packages.packageList:
            try:
                self._install_package(pkg_name)
                log.info("selected package: '%s'", pkg_name)
            except payload.NoSuchPackage as e:
                self._miss(e)

        self._select_kernel_package()

    def _apply_requirements(self, requirements):
        for req in self.requirements.packages:
            ignore_msgs = []
            if req.id in self.instclass.ignoredPackages:
                ignore_msgs.append("IGNORED by install class %s" % self.instclass)
            if req.id in self.data.packages.excludedList:
                ignore_msgs.append("IGNORED because excluded")
            if not ignore_msgs:
                try:
                    self._install_package(req.id, required=req.strong)
                except payload.NoSuchPackage as e:
                    self._miss(e)
            log.debug("selected package: %s, requirement for %s %s",
                       req.id, req.reasons, ", ".join(ignore_msgs))

        for req in self.requirements.groups:
            try:
                self._select_group(req.id, required=req.strong)
                log.debug("selected group: %s, requirement for %s",
                           req.id, req.reasons)
            except payload.NoSuchGroup as e:
                self._miss(e)

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

    def _configure(self):
        self._base = dnf.Base()
        conf = self._base.conf
        conf.cachedir = DNF_CACHE_DIR
        conf.pluginconfpath = DNF_PLUGINCONF_DIR
        conf.logdir = '/tmp/'

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

        size = sum(tsi.installed.downloadsize for tsi in transaction)
        # reserve extra
        return Size(size) + Size("150 MB")

    def _exclude_package(self, pkg_name):
        subj = dnf.subject.Subject(pkg_name)
        pkgs = subj.get_best_query(self._base.sack)
        # The only way to get expected behavior is to declare it
        # as excluded from the installable set
        return self._base.sack.add_excludes(pkgs)

    def _install_package(self, pkg_name, required=False):
        try:
            return self._base.install(pkg_name)
        except dnf.exceptions.MarkingError:
            raise payload.NoSuchPackage(pkg_name, required=required)

    def _miss(self, exn):
        if self.data.packages.handleMissing == KS_MISSING_IGNORE:
            return

        log.error('Missed: %r', exn)
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

    def _select_group(self, group_id, default=True, optional=False, required=False):
        grp = self._base.comps.group_by_pattern(group_id)
        if grp is None:
            raise payload.NoSuchGroup(group_id, required=required)
        types = {'mandatory'}
        if default:
            types.add('default')
        if optional:
            types.add('optional')
        try:
            self._base.group_install(grp.id, types)
        except dnf.exceptions.MarkingError as e:
            # dnf-1.1.9 raises this error when a package is missing from a group
            raise payload.NoSuchPackage(str(e), required=True)
        except dnf.exceptions.CompsError as e:
            # DNF raises this when it is already selected
            log.debug(e)

    def _select_environment(self, env_id, excluded):
        # dnf.base.environment_install excludes on packages instead of groups,
        # which is unhelpful. Instead, use group_install for each group in
        # the environment so we can skip the ones that are excluded.
        for groupid in set(self.environmentGroups(env_id, optional=False)) - set(excluded):
            self._select_group(groupid)

    def _select_kernel_package(self):
        kernels = self.kernelPackages
        for kernel in kernels:
            try:
                self._install_package(kernel)
            except payload.NoSuchPackage:
                log.info('kernel: no such package %s', kernel)
            else:
                log.info('kernel: selected %s', kernel)
                break
        else:
            log.error('kernel: failed to select a kernel from %s', kernels)

    def langpacks(self):
        # get all available languages in repos
        available_langpacks = self._base.sack.query().available() \
            .filter(name__glob="langpacks-*")
        alangs = [p.name.split('-', 1)[1] for p in available_langpacks]

        langpacks = []
        # add base langpacks into transaction
        localization_proxy = DBus.get_proxy(MODULE_LOCALIZATION_NAME, MODULE_LOCALIZATION_PATH)
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
    def mirrorEnabled(self):
        return True

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
            size += tsi.installed.installsize
            # number of files installed on the system
            files_nm += len(tsi.installed.files)

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
        self._apply_selections()
        self.requirements.apply()

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
        super(DNFPayload, self).disableRepo(repo_id)

    def enableRepo(self, repo_id):
        try:
            self._base.repos[repo_id].enable()
            log.info("Enabled '%s'", repo_id)
        except KeyError:
            pass
        super(DNFPayload, self).enableRepo(repo_id)

    def environmentDescription(self, environmentid):
        env = self._base.comps.environment_by_pattern(environmentid)
        if env is None:
            raise payload.NoSuchGroup(environmentid)
        return (env.ui_name, env.ui_description)

    def environmentId(self, environment):
        """Return environment id for the environment specified by id or name."""
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
        self._base.close()
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
            return super(DNFPayload, self).isRepoEnabled(repo_id)

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
        localization_proxy = DBus.get_proxy(MODULE_LOCALIZATION_NAME, MODULE_LOCALIZATION_PATH)
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
        super(DNFPayload, self).reset()
        shutil.rmtree(DNF_CACHE_DIR, ignore_errors=True)
        shutil.rmtree(DNF_PLUGINCONF_DIR, ignore_errors=True)
        self.txID = None
        self._base.reset(sack=True, repos=True)
        self._configure_proxy()
        self._repoMD_list = []

    def updateBaseRepo(self, fallback=True, checkmount=True):
        log.info('configuring base repo')
        self.reset()
        url, mirrorlist, metalink = self._setupInstallDevice(self.storage,
                                                             checkmount)
        method = self.data.method
        sslverify = True
        if method.method == "url":
            sslverify = not (method.noverifyssl or flags.noverifyssl)

        # Read in all the repos from the installation environment, make a note of which
        # are enabled, and then disable them all.  If the user gave us a method, we want
        # to use that instead of the default repos.
        self._base.read_all_repos()

        # Repos on disk are always enabled. When reloaded their state needs to
        # be synchronized with the user selection.
        self.setUpdatesEnabled(self._updates_enabled)

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
                        repo.enable()

        for ksrepo in self.data.repo.dataList():
            log.debug("repo %s: mirrorlist %s, baseurl %s, metalink %s",
                      ksrepo.name, ksrepo.mirrorlist, ksrepo.baseurl, ksrepo.metalink)
            # one of these must be set to create new repo
            if not (ksrepo.mirrorlist or ksrepo.baseurl or ksrepo.metalink or
                    ksrepo.name in self._base.repos):
                raise payload.PayloadSetupError("Repository %s has no mirror, baseurl or metalink set "
                                                "and is not one of the pre-defined repositories"
                                                % ksrepo.name)

            self._add_repo(ksrepo)

        ksnames = [r.name for r in self.data.repo.dataList()]
        ksnames.append(constants.BASE_REPO_NAME)
        with self._repos_lock:
            for repo in self._base.repos.iter_enabled():
                id_ = repo.id
                if 'source' in id_ or 'debuginfo' in id_:
                    self.disableRepo(id_)
                elif constants.isFinal and 'rawhide' in id_:
                    self.disableRepo(id_)

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
                raise payload.PayloadSetupError("repo %s has no baseurl, mirrorlist or metalink", repo.id)

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

        super(DNFPayload, self).postInstall()

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
