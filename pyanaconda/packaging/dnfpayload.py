# dnfpayload.py
# DNF/rpm software payload management.
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Red Hat Author(s): Ales Kozumplik <akozumpl@redhat.com>
#
import os

from blivet.size import Size
import blivet.arch
from pyanaconda.flags import flags
from pyanaconda.i18n import _
from pyanaconda.progress import progressQ

import configparser
import collections
import itertools
import logging
import multiprocessing
import operator
from pyanaconda import constants
from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, KS_MISSING_IGNORE
import pyanaconda.errors as errors
import pyanaconda.iutil
import pyanaconda.localization
import pyanaconda.packaging as packaging
import shutil
import sys
import time
from pyanaconda.iutil import ProxyString, ProxyStringError
from pyanaconda.iutil import open   # pylint: disable=redefined-builtin

log = logging.getLogger("packaging")

import dnf
import dnf.exceptions
import dnf.repo
import dnf.callback
import rpm

DNF_CACHE_DIR = '/tmp/dnf.cache'
DNF_PACKAGE_CACHE_DIR_SUFFIX = 'dnf.package.cache'
DOWNLOAD_MPOINTS = {'/tmp',
                    '/',
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

def _failure_limbo():
    progressQ.send_quit(1)
    while True:
        time.sleep(10000)

def _df_map():
    """Return (mountpoint -> size available) mapping."""
    output = pyanaconda.iutil.execWithCapture('df', ['--output=target,avail'])
    output = output.rstrip()
    lines = output.splitlines()
    structured = {}
    for line in lines:
        items = line.split()
        key = items[0]
        val = items[1]
        if not key.startswith('/'):
            continue
        structured[key] = Size(int(val)*1024)
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

def _pick_mpoint(df, requested):
    def reasonable_mpoint(mpoint):
        return mpoint in DOWNLOAD_MPOINTS

    # reserve extra
    requested = requested + Size("150 MB")
    sufficients = {key : val for (key, val) in df.items() if val > requested
                   and reasonable_mpoint(key)}
    log.info('Sufficient mountpoints found: %s', sufficients)

    if not len(sufficients):
        return None
    # default to the biggest one:
    return sorted(sufficients.items(), key=operator.itemgetter(1),
                  reverse=True)[0][0]

class PayloadRPMDisplay(dnf.callback.LoggingTransactionDisplay):
    def __init__(self, queue_instance):
        super(PayloadRPMDisplay, self).__init__()
        self._queue = queue_instance
        self._last_ts = None
        self.cnt = 0

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        if action == self.PKG_INSTALL and te_current == 0:
            # do not report same package twice
            if self._last_ts == ts_current:
                return
            self._last_ts = ts_current

            msg = '%s.%s (%d/%d)' % \
                (package.name, package.arch, ts_current, ts_total)
            self.cnt += 1
            self._queue.put(('install', msg))
        elif action == self.TRANS_POST:
            self._queue.put(('post', None))

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
            'percent'     : int(100 * downloaded/self.total_size),
            'total_files' : self.total_files,
            'total_size'  : self.total_size
        }
        progressQ.send_message(msg % vals)

    def end(self, payload, status, err_msg):
        nevra = str(payload)
        if status is dnf.callback.STATUS_OK:
            self.downloads[nevra] = payload.download_size
            self._update()
            return
        log.critical("Failed to download '%s': %d - %s", nevra, status, err_msg)

    def progress(self, payload, done):
        nevra = str(payload)
        self.downloads[nevra] = done
        self._update()

    def start(self, total_files, total_size):
        self.total_files = total_files
        self.total_size = Size(total_size)

def do_transaction(base, queue_instance):
    try:
        display = PayloadRPMDisplay(queue_instance)
        base.do_transaction(display=display)
    except BaseException as e:
        log.error('The transaction process has ended abruptly')
        log.info(e)
        queue_instance.put(('quit', str(e)))

class DNFPayload(packaging.PackagePayload):
    def __init__(self, data):
        packaging.PackagePayload.__init__(self, data)

        self._base = None
        self._download_location = None
        self._configure()

    def unsetup(self):
        super(DNFPayload, self).unsetup()
        self._base = None
        self._configure()

    def _replace_vars(self, url):
        """ Replace url variables with their values

            :param url: url string to do replacement on
            :type url:  string
            :returns:   string with variables substituted
            :rtype:     string or None

            Currently supports $releasever and $basearch
        """
        if not url:
            return url

        url = url.replace("$releasever", self._base.conf.releasever)
        url = url.replace("$basearch", blivet.arch.getArch())

        return url


    def _add_repo(self, ksrepo):
        """Add a repo to the dnf repo object

           :param ksrepo: Kickstart Repository to add
           :type ksrepo: Kickstart RepoData object.
           :returns: None
        """
        repo = dnf.repo.Repo(ksrepo.name, DNF_CACHE_DIR)
        url = self._replace_vars(ksrepo.baseurl)
        mirrorlist = self._replace_vars(ksrepo.mirrorlist)

        if url and url.startswith("nfs://"):
            (server, path) = url[6:].split(":", 1)
            mountpoint = "%s/%s.nfs" % (constants.MOUNT_DIR, repo.name)
            self._setupNFS(mountpoint, server, path, None)

            url = "file://" + mountpoint

        if url:
            repo.baseurl = [url]
        if mirrorlist:
            repo.mirrorlist = mirrorlist
        repo.sslverify = not (ksrepo.noverifyssl or flags.noverifyssl)
        if ksrepo.proxy:
            try:
                repo.proxy = ProxyString(ksrepo.proxy).url
            except ProxyStringError as e:
                log.error("Failed to parse proxy for _add_repo %s: %s",
                          ksrepo.proxy, e)

        # If this repo is already known, it's one of two things:
        # (1) The user is trying to do "repo --name=updates" in a kickstart file
        #     and we should just know to enable the already existing on-disk
        #     repo config.
        # (2) It's a duplicate, and we need to delete the existing definition
        #     and use this new one.  The highest profile user of this is livecd
        #     kickstarts.
        if repo.id in self._base.repos:
            if not url and not mirrorlist:
                self._base.repos[repo.id].enable()
            else:
                self._base.repos.pop(repo.id)
                self._base.repos.add(repo)
                repo.enable()
        # If the repo's not already known, we've got to add it.
        else:
            self._base.repos.add(repo)
            repo.enable()

        # Load the metadata to verify that the repo is valid
        try:
            self._base.repos[repo.id].load()
        except dnf.exceptions.RepoError as e:
            raise packaging.MetadataError(e)

        log.info("added repo: '%s' - %s", ksrepo.name, url or mirrorlist)

    def addRepo(self, ksrepo):
        """Add a repo to dnf and kickstart repo lists

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
            except packaging.NoSuchGroup as e:
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
            except packaging.NoSuchGroup as e:
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
            except packaging.NoSuchGroup as e:
                self._miss(e)

        for pkg_name in set(self.data.packages.packageList) - set(self.data.packages.excludedList):
            try:
                self._install_package(pkg_name)
                log.info("selected package: '%s'", pkg_name)
            except packaging.NoSuchPackage as e:
                self._miss(e)

        self._select_kernel_package()

        for pkg_name in self.requiredPackages:
            try:
                self._install_package(pkg_name, required=True)
                log.debug("selected required package: %s", pkg_name)
            except packaging.NoSuchPackage as e:
                self._miss(e)

        for group in self.requiredGroups:
            try:
                self._select_group(group, required=True)
                log.debug("selected required group: %s", group)
            except packaging.NoSuchGroup as e:
                self._miss(e)

    def _bump_tx_id(self):
        if self.txID is None:
            self.txID = 1
        else:
            self.txID += 1
        return self.txID

    def _configure(self):
        self._base = dnf.Base()
        conf = self._base.conf
        conf.cachedir = DNF_CACHE_DIR
        conf.logdir = '/tmp/'
        # disable console output completely:
        conf.debuglevel = 0
        conf.errorlevel = 0
        self._base.logging.setup_from_dnf_conf(conf)

        conf.releasever = self._getReleaseVersion(None)
        conf.installroot = pyanaconda.iutil.getSysroot()
        conf.prepend_installroot('persistdir')

        # NSS won't survive the forking we do to shield out chroot during
        # transaction, disable it in RPM:
        conf.tsflags.append('nocrypto')

        if self.data.packages.multiLib:
            conf.multilib_policy = "all"

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

        # Start with an empty comps so we can go ahead and use the environment
        # and group properties. Unset reposdir to ensure dnf has nothing it can
        # check automatically
        conf.reposdir = []
        self._base.read_comps()

        conf.reposdir = REPO_DIRS

    @property
    def _download_space(self):
        transaction = self._base.transaction
        if transaction is None:
            return Size(0)

        size = sum(tsi.installed.downloadsize for tsi in transaction)
        return Size(size)

    def _install_package(self, pkg_name, required=False):
        try:
            return self._base.install(pkg_name)
        except dnf.exceptions.MarkingError:
            raise packaging.NoSuchPackage(pkg_name, required=required)

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
            pyanaconda.iutil.ipmi_report(constants.IPMI_ABORTED)
            sys.exit(1)

    def _pick_download_location(self):
        required = self._download_space
        df_map = _df_map()
        mpoint = _pick_mpoint(df_map, required)
        log.info("Download space required: %s, use filesystem at: %s", required,
                 mpoint)
        if mpoint is None:
            msg = "Not enough disk space to download the packages."
            raise packaging.PayloadError(msg)

        pkgdir = '%s/%s' % (mpoint, DNF_PACKAGE_CACHE_DIR_SUFFIX)
        for repo in self._base.repos.iter_enabled():
            repo.pkgdir = pkgdir

        return pkgdir

    def _select_group(self, group_id, default=True, optional=False, required=False):
        grp = self._base.comps.group_by_pattern(group_id)
        if grp is None:
            raise packaging.NoSuchGroup(group_id, required=required)
        types = {'mandatory'}
        if default:
            types.add('default')
        if optional:
            types.add('optional')
        exclude = self.data.packages.excludedList
        try:
            self._base.group_install(grp, types, exclude=exclude)
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
            except packaging.NoSuchPackage:
                log.info('kernel: no such package %s', kernel)
            else:
                log.info('kernel: selected %s', kernel)
                break
        else:
            log.error('kernel: failed to select a kernel from %s', kernels)

    def _sync_metadata(self, dnf_repo):
        try:
            dnf_repo.load()
        except dnf.exceptions.RepoError as e:
            id_ = dnf_repo.id
            log.info('_sync_metadata: addon repo error: %s', e)
            self.disableRepo(id_)

    @property
    def baseRepo(self):
        # is any locking needed here?
        repo_names = [constants.BASE_REPO_NAME] + self.DEFAULT_REPOS
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
        return [r.id for r in self._base.repos.values()]

    @property
    def spaceRequired(self):
        transaction = self._base.transaction
        if transaction is None:
            return Size("3000 MB")

        size = sum(tsi.installed.installsize for tsi in transaction)
        # add 35% to account for the fact that the above method is laughably
        # inaccurate:
        size *= 1.35
        return Size(size)

    def _isGroupVisible(self, grpid):
        grp = self._base.comps.group_by_pattern(grpid)
        if grp is None:
            raise packaging.NoSuchGroup(grpid)
        return grp.visible

    def _groupHasInstallableMembers(self, grpid):
        return True

    def checkSoftwareSelection(self):
        log.info("checking software selection")
        self._bump_tx_id()
        self._base.reset(goal=True)
        self._apply_selections()

        try:
            if self._base.resolve():
                log.debug("checking dependencies: success.")
            else:
                log.debug("empty transaction")
        except dnf.exceptions.DepsolveError as e:
            msg = str(e)
            log.warning(msg)
            raise packaging.DependencyError(msg)

        log.info("%d packages selected totalling %s",
                 len(self._base.transaction), self.spaceRequired)

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
            raise packaging.NoSuchGroup(environmentid)
        return (env.ui_name, env.ui_description)

    def environmentGroups(self, environmentid, optional=True):
        env = self._base.comps.environment_by_pattern(environmentid)
        if env is None:
            raise packaging.NoSuchGroup(environmentid)
        group_ids = (id_.name for id_ in env.group_ids)
        option_ids = (id_.name for id_ in env.option_ids)
        if optional:
            return list(itertools.chain(group_ids, option_ids))
        else:
            return list(group_ids)

    def environmentHasOption(self, environmentid, grpid):
        env = self._base.comps.environment_by_pattern(environmentid)
        if env is None:
            raise packaging.NoSuchGroup(environmentid)
        return grpid in (id_.name for id_ in env.option_ids)

    def environmentOptionIsDefault(self, environmentid, grpid):
        env = self._base.comps.environment_by_pattern(environmentid)
        if env is None:
            raise packaging.NoSuchGroup(environmentid)

        # Look for a group in the optionlist that matches the group_id and has
        # default set
        return any(grp for grp in env.option_ids if grp.name == grpid and grp.default)

    def groupDescription(self, grpid):
        """ Return name/description tuple for the group specified by id. """
        grp = self._base.comps.group_by_pattern(grpid)
        if grp is None:
            raise packaging.NoSuchGroup(grpid)
        return (grp.ui_name, grp.ui_description)

    def gatherRepoMetadata(self):
        for repo in self._base.repos.iter_enabled():
            self._sync_metadata(repo)
        self._base.fill_sack(load_system_repo=False)
        self._base.read_comps()
        self._refreshEnvironmentAddons()

    def install(self):
        progressQ.send_message(_('Starting package installation process'))

        # Add the rpm macros to the global transaction environment
        for macro in self.rpmMacros:
            rpm.addMacro(macro[0], macro[1])

        if self.install_device:
            self._setupMedia(self.install_device)
        try:
            self.checkSoftwareSelection()
            self._download_location = self._pick_download_location()
        except packaging.PayloadError as e:
            if errors.errorHandler.cb(e) == errors.ERROR_RAISE:
                _failure_limbo()

        pkgs_to_download = self._base.transaction.install_set
        log.info('Downloading packages.')
        progressQ.send_message(_('Downloading packages'))
        progress = DownloadProgress()
        try:
            self._base.download_packages(pkgs_to_download, progress)
        except dnf.exceptions.DownloadError as e:
            msg = 'Failed to download the following packages: %s' % str(e)
            exc = packaging.PayloadInstallError(msg)
            if errors.errorHandler.cb(exc) == errors.ERROR_RAISE:
                _failure_limbo()

        log.info('Downloading packages finished.')

        pre_msg = _("Preparing transaction from installation source")
        progressQ.send_message(pre_msg)

        queue_instance = multiprocessing.Queue()
        process = multiprocessing.Process(target=do_transaction,
                                          args=(self._base, queue_instance))
        process.start()
        (token, msg) = queue_instance.get()
        while token not in ('post', 'quit'):
            if token == 'install':
                msg = _("Installing %s") % msg
                progressQ.send_message(msg)
            (token, msg) = queue_instance.get()

        if token == 'quit':
            _failure_limbo()

        post_msg = _("Performing post-installation setup tasks")
        progressQ.send_message(post_msg)
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
        """ Return the yum repo object. """
        return self._base.repos[repo_id]

    def isRepoEnabled(self, repo_id):
        try:
            return self._base.repos[repo_id].enabled
        except (dnf.exceptions.RepoError, KeyError):
            return super(DNFPayload, self).isRepoEnabled(repo_id)

    def languageGroups(self):
        locales = [self.data.lang.lang] + self.data.lang.addsupport
        match_fn = pyanaconda.localization.langcode_matches_locale
        gids = set()
        gl_tuples = ((g.id, g.lang_only) for g in self._base.comps.groups_iter())
        for (gid, lang) in gl_tuples:
            for locale in locales:
                if match_fn(lang, locale):
                    gids.add(gid)
        log.info('languageGroups: %s', gids)
        return list(gids)

    def preInstall(self, packages=None, groups=None):
        super(DNFPayload, self).preInstall(packages, groups)
        self.requiredPackages = ["dnf"]
        if packages:
            self.requiredPackages += packages
        self.requiredGroups = groups

    def reset(self):
        super(DNFPayload, self).reset()
        shutil.rmtree(DNF_CACHE_DIR, ignore_errors=True)
        self.txID = None
        self._base.reset(sack=True, repos=True)

    def updateBaseRepo(self, fallback=True, checkmount=True):
        log.info('configuring base repo')
        self.reset()
        url, mirrorlist, sslverify = self._setupInstallDevice(self.storage,
                                                              checkmount)
        method = self.data.method

        # Read in all the repos from the installation environment, make a note of which
        # are enabled, and then disable them all.  If the user gave us a method, we want
        # to use that instead of the default repos.
        self._base.read_all_repos()

        enabled = []
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
                    mirrorlist=mirrorlist, noverifyssl=not sslverify, proxy=proxy)
                self._add_repo(base_ksrepo)
            except (packaging.MetadataError, packaging.PayloadError) as e:
                log.error("base repo (%s/%s) not valid -- removing it",
                          method.method, url)
                self._base.repos.pop(constants.BASE_REPO_NAME, None)
                if not fallback:
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
            for (id_, repo) in self._base.repos.items():
                if id_ in enabled:
                    repo.enable()

        for ksrepo in self.data.repo.dataList():
            self._add_repo(ksrepo)

        ksnames = [r.name for r in self.data.repo.dataList()]
        ksnames.append(constants.BASE_REPO_NAME)
        for repo in self._base.repos.iter_enabled():
            id_ = repo.id
            if 'source' in id_ or 'debuginfo' in id_:
                self.disableRepo(id_)
            elif constants.isFinal and 'rawhide' in id_:
                self.disableRepo(id_)

    def _writeDNFRepo(self, repo, repo_path):
        """ Write a repo object to a DNF repo.conf file

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
                raise packaging.PayloadSetupError("repo %s has no baseurl, mirrorlist or metalink", repo.id)

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

    def postInstall(self):
        """ Perform post-installation tasks. """
        # Write selected kickstart repos to target system
        for ks_repo in (ks for ks in (self.getAddOnRepo(r) for r in self.addOns) if ks.install):
            try:
                repo = self.getRepo(ks_repo.name)
                if not repo:
                    continue
            except (dnf.exceptions.RepoError, KeyError):
                continue
            repo_path = pyanaconda.iutil.getSysroot() + YUM_REPOS_DIR + "%s.repo" % repo.id
            try:
                log.info("Writing %s.repo to target system.", repo.id)
                self._writeDNFRepo(repo, repo_path)
            except packaging.PayloadSetupError as e:
                log.error(e)

        super(DNFPayload, self).postInstall()
