# yumpayload.py
# Yum/rpm software payload management.
#
# Copyright (C) 2012  Red Hat, Inc.
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#                    Chris Lumens <clumens@redhat.com>
#

"""
    TODO
        - error handling!!!
        - document all methods
        - YumPayload
            - preupgrade
            - clean up use of flags.testing
            - write test cases
            - more logging in key methods
            - rpm macros
                - __file_context_path
                    - what does this do if we run in permissive mode?
            - handling of proxy needs cleanup
                - passed to anaconda as --proxy, --proxyUsername, and
                  --proxyPassword
                    - drop the use of a file for proxy and ftp auth info
                - specified via KS as a URL

"""

import os
import shutil
import time

from . import *

try:
    import rpm
except ImportError:
    log.error("import of rpm failed")
    rpm = None

try:
    import yum
except ImportError:
    log.error("import of yum failed")
    yum = None

from pyanaconda.constants import *
from pyanaconda.flags import flags

from pyanaconda import iutil
from pyanaconda.network import hasActiveNetDev

from pyanaconda.image import opticalInstallMedia
from pyanaconda.image import mountImage
from pyanaconda.image import findFirstIsoImage

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

from pyanaconda.errors import *
#from pyanaconda.progress import progress

class YumPayload(PackagePayload):
    """ A YumPayload installs packages onto the target system using yum. """
    def __init__(self, data):
        if rpm is None or yum is None:
            raise PayloadError("unsupported payload type")

        PackagePayload.__init__(self, data)

        self._groups = []
        self._packages = []

        self.install_device = None
        self.proxy = None                           # global proxy

        self._yum = yum.YumBase()

        self._yum.use_txmbr_in_callback = True

        # Set some configuration parameters that don't get set through a config
        # file.  yum will know what to do with these.
        # XXX We have to try to set releasever before we trigger a read of the
        #     repo config files. We do that from setup before adding any repos.
        self._yum.preconf.enabled_plugins = ["blacklist", "whiteout"]
        self._yum.preconf.fn = "/tmp/anaconda-yum.conf"
        self._yum.preconf.root = ROOT_PATH
        self._cache_dir = "/var/cache/yum"

    def setup(self, storage, proxy=None):
        buf = """
[main]
installroot=%s
cachedir=%s
keepcache=0
logfile=/tmp/yum.log
metadata_expire=never
pluginpath=/usr/lib/yum-plugins,/tmp/updates/yum-plugins
pluginconfpath=/etc/yum/pluginconf.d,/tmp/updates/pluginconf.d
plugins=1
reposdir=/etc/yum.repos.d,/etc/anaconda.repos.d,/tmp/updates/anaconda.repos.d,/tmp/product/anaconda.repos.d
""" % (ROOT_PATH, self._cache_dir)

        if proxy:
            # FIXME: include proxy_username, proxy_password
            buf += "proxy=%s" % proxy

        fd = open("/tmp/anaconda-yum.conf", "w")
        fd.write(buf)
        fd.close()

        self.proxy = proxy
        self._configureMethod(storage)
        self._configureRepos(storage)
        if flags.testing:
            self._yum.setCacheDir()

        # go ahead and get metadata for all enabled repos now
        for repoid in self.repos:
            repo = self._yum.repos.getRepo(repoid)
            if repo.enabled:
                try:
                    self._getRepoMetadata(repo)
                except MetadataError as e:
                    log.error("error fetching metadata for %s: %s" % (repoid, e))
                    self.removeRepo(repoid)

    ###
    ### METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def repos(self):
        return self._yum.repos.repos.keys()

    @property
    def baseRepo(self):
        repo_names = [BASE_REPO_NAME, productName.lower(), "rawhide"]
        base_repo_name = None
        for repo_name in repo_names:
            if repo_name in self.repos and \
               self._yum.repos.getRepo(repo_name).enabled:
                base_repo_name = repo_name
                break

        return base_repo_name

    def _repoNeedsNetwork(self, repo):
        """ Returns True if the ksdata repo requires networking. """
        urls = [repo.baseurl] + repo.mirrorlist
        network_protocols = ["http:", "ftp:", "nfs:", "nfsiso:"]
        for url in urls:
            if any([url.startswith(p) for p in network_protocols]):
                return True

        return False

    def _configureRepos(self, storage):
        """ Configure the initial repository set. """
        log.info("configuring repos")
        # FIXME: driverdisk support

        # add/enable the repos anaconda knows about
        # identify repos based on ksdata.
        for repo in self.data.repo.dataList():
            self._configureKSRepo(storage, repo)

        # remove/disable repos that don't make sense during system install.
        # If a method was given, disable any repos that aren't in ksdata.
        for repo in self._yum.repos.repos.values():
            if "-source" in repo.id or "-debuginfo" in repo.id:
                log.info("excluding source or debug repo %s" % repo.id)
                self.removeRepo(repo.id)
            elif isFinal and ("rawhide" in repo.id or "development" in repo.id):
                log.info("excluding devel repo %s for non-devel anaconda" % repo.id)
                self.removeRepo(repo.id)
            elif not isFinal and not repo.enabled:
                log.info("excluding disabled repo %s for prerelease" % repo.id)
                self.removeRepo(repo.id)
            elif self.data.method.method and \
                 repo.id != BASE_REPO_NAME and \
                 repo.id not in [r.name for r in self.data.repo.dataList()]:
                log.info("disabling repo %s" % repo.id)
                self.disableRepo(repo.id)

    def _configureMethod(self, storage):
        """ Configure the base repo. """
        log.info("configuring base repo")
        # set up the main repo specified by method=, repo=, or ks method
        # XXX FIXME: does this need to handle whatever was set up by dracut?
        # XXX FIXME: most of this probably belongs up in Payload
        method = self.data.method
        sslverify = True
        url = None
        proxy = None

        if method.method == "harddrive":
            if method.biospart:
                log.warning("biospart support is not implemented")
                devspec = method.biospart
            else:
                devspec = method.partition

            # FIXME: teach DeviceTree.resolveDevice about biospart
            device = storage.devicetree.resolveDevice(devspec)
            self._setupDevice(device, mountpoint=ISO_DIR)

            # check for ISO images in the newly mounted dir
            path = ISO_DIR
            if method.dir:
                path = os.path.normpath("%s/%s" % (path, method.dir))

            image = findFirstIsoImage(path)
            if not image:
                exn = PayloadSetupError("failed to find valid iso image")
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn

            if path.endswith(".iso"):
                path = os.path.dirname(path)

            # mount the ISO on a loop
            image = os.path.normpath("%s/%s" % (path, image))
            mountImage(image, INSTALL_TREE)

            self.install_device = device
            url = "file://" + INSTALL_TREE
        elif method.method == "nfs":
            # XXX what if we mount it on ISO_DIR and then create a symlink
            #     if there are no isos instead of the remount?
            self._setupNFS(INSTALL_TREE, method.server, method.dir,
                           method.opts)

            # check for ISO images in the newly mounted dir
            path = ISO_DIR
            if method.dir.endswith(".iso"):
                # if the given URL includes a specific ISO image file, use it
                image_file = os.path.basename(method.dir)
                path = os.path.normpath("%s/%s" % (path, image_file))

            image = findFirstIsoImage(path)

            # it appears there are ISO images in the dir, so assume they want to
            # install from one of them
            if image:
                isys.umount(INSTALL_TREE)
                self._setupNFS(ISO_DIR, method.server, method.path,
                               method.options)

                # mount the ISO on a loop
                image = os.path.normpath("%s/%s" % (ISO_DIR, image))
                mountImage(image, INSTALL_TREE)

            url = "file://" + INSTALL_TREE
        elif method.method == "url":
            url = method.url
            sslverify = not (method.noverifyssl or flags.noverifyssl)
            proxy = method.proxy or self.proxy
        elif method.method == "cdrom" or not method.method:
            device = opticalInstallMedia(storage.devicetree)
            if device:
                self.install_device = device
                url = "file://" + INSTALL_TREE
                if not method.method:
                    method.method = "cdrom"

        self._yum.preconf.releasever = self._getReleaseVersion(url)

        if method.method:
            # FIXME: handle MetadataError
            self._addYumRepo(BASE_REPO_NAME, url,
                             proxy=proxy, sslverify=sslverify)

    def _configureKSRepo(self, storage, repo):
        """ Configure a single ksdata repo. """
        url = getattr(repo, "baseurl", repo.mirrorlist)
        if url.startswith("nfs:"):
            # FIXME: create a directory other than INSTALL_TREE based on
            #        the repo's id/name to avoid crashes if the base repo is NFS
            (opts, server, path) = iutil.parseNfsUrl(url)
            self._setupNFS(INSTALL_TREE, server, path, opts)
        else:
            # check for media, fall back to default repo
            device = opticalInstallMedia(storage.devicetree)
            if device:
                self.install_device = device

        if self._repoNeedsNetwork(repo) and not hasActiveNetDev():
            raise NoNetworkError

        proxy = repo.proxy or self.proxy
        sslverify = not (flags.noverifyssl or repo.noverifyssl)

        # this repo does not go into ksdata -- only yum
        self.addYumRepo(repo.id, repo.baseurl, repo.mirrorlist, cost=repo.cost,
                        exclude=repo.excludepkgs, includepkgs=repo.includepkgs,
                        proxy=proxy, sslverify=sslverify)

        # TODO: enable addons

    def _getRepoMetadata(self, yumrepo):
        """ Retrieve repo metadata if we don't already have it. """
        from yum.Errors import RepoError, RepoMDError

        # And try to grab its metadata.  We do this here so it can be done
        # on a per-repo basis, so we can then get some finer grained error
        # handling and recovery.
        try:
            yumrepo.getPrimaryXML()
            yumrepo.getOtherXML()
        except RepoError as e:
            raise MetadataError(e.value)

        # Not getting group info is bad, but doesn't seem like a fatal error.
        # At the worst, it just means the groups won't be displayed in the UI
        # which isn't too bad, because you may be doing a kickstart install and
        # picking packages instead.
        try:
            yumrepo.getGroups()
        except RepoMDError:
            log.error("failed to get groups for repo %s" % yumrepo.id)

    def _addYumRepo(self, name, baseurl, mirrorlist=None, **kwargs):
        """ Add a yum repo to the YumBase instance. """
        # First, delete any pre-existing repo with the same name.
        if name in self._yum.repos.repos:
            self._yum.repos.delete(name)

        # Replace anything other than HTTP/FTP with file://
        if baseurl and \
           not baseurl.startswith("http:") and \
           not baseurl.startswith("ftp:"):
            baseurl = "file://" + INSTALL_TREE

        log.debug("adding yum repo %s with baseurl %s and mirrorlist %s"
                    % (name, baseurl, mirrorlist))
        # Then add it to yum's internal structures.
        obj = self._yum.add_enable_repo(name,
                                        baseurl=[baseurl],
                                        mirrorlist=mirrorlist,
                                        **kwargs)

        self._getRepoMetadata(obj)

        # Adding a new repo means the cached packages and groups lists
        # are out of date.  Clear them out now so the next reference to
        # either will cause it to be regenerated.
        self._groups = []
        self._packages = []

    def addRepo(self, newrepo):
        """ Add a ksdata repo. """
        log.debug("adding new repo %s" % newrepo.name)
        self._addYumRepo(newrepo)   # FIXME: handle MetadataError
        super(YumRepo, self).addRepo(newrepo)

    def removeRepo(self, repo_id):
        """ Remove a repo as specified by id. """
        log.debug("removing repo %s" % repo_id)
        if repo_id in self.repos:
            self._yum.repos.delete(repo_id)

        super(YumPayload, self).removeRepo(repo_id)

    def enableRepo(self, repo_id):
        """ Enable a repo as specified by id. """
        log.debug("enabling repo %s" % repo_id)
        if repo_id in self.repos:
            self._yum.repos.enableRepo(repo_id)

    def disableRepo(self, repo_id):
        """ Disable a repo as specified by id. """
        log.debug("disabling repo %s" % repo_id)
        if repo_id in self.repos:
            self._yum.repos.disableRepo(repo_id)

    ###
    ### METHODS FOR WORKING WITH GROUPS
    ###
    @property
    def groups(self):
        from yum.Errors import RepoError

        if not self._groups:
            if not hasActiveNetDev():
                raise NoNetworkError

            try:
                self._groups = self._yum.comps
            except RepoError as e:
                raise MetadataError(e.value)

        return [g.groupid for g in self._groups.get_groups()]

    def description(self, groupid):
        """ Return name/description tuple for the group specified by id. """
        if not self._groups.has_group(groupid):
            raise NoSuchGroup(groupid)

        group = self._groups.return_group(groupid)

        return (group.ui_name, group.ui_description)

    def selectGroup(self, groupid, default=True, optional=False):
        super(YumPayload, self).selectGroup(groupid, default=default,
                                            optional=optional)
        # select the group in comps
        pkg_types = ['mandatory']
        if default:
            pkg_types.append("default")

        if optional:
            pkg_types.append("optional")

        log.debug("select group %s" % groupid)
        try:
            self._yum.selectGroup(groupid, group_package_types=pkg_types)
        except yum.Errors.GroupsError:
            log.error("no such group: %s" % groupid)

    def deselectGroup(self, groupid):
        super(YumPayload, self).deselectGroup(groupid)
        # deselect the group in comps
        log.debug("deselect group %s" % groupid)
        try:
            self._yum.deselectGroup(groupid, force=True)
        except yum.Errors.GroupsError:
            log.error("no such group: %s" % groupid)

    ###
    ### METHODS FOR WORKING WITH PACKAGES
    ###
    @property
    def packages(self):
        from yum.Errors import RepoError

        if not self._packages:
            if not hasActiveNetDev():
                raise NoNetworkError

            try:
                self._packages = self._yum.pkgSack.returnPackages()
            except RepoError as e:
                raise MetadataError(e.value)

        return self._packages

    def selectPackage(self, pkgid):
        """Mark a package for installation.

           pkgid - The name of a package to be installed.  This could include
                   a version or architecture component.
        """
        super(YumPayload, self).selectPackage(pkgid)
        log.debug("select package %s" % pkgid)
        try:
            mbrs = self._yum.install(pattern=pkgid)
        except yum.Errors.InstallError:
            log.error("no package matching %s" % pkgid)

    def deselectPackage(self, pkgid):
        """Mark a package to be excluded from installation.

           pkgid - The name of a package to be excluded.  This could include
                   a version or architecture component.
        """
        super(YumPayload, self).deselectPackage(pkgid)
        log.debug("deselect package %s" % pkgid)
        self._yum.tsInfo.deselect(pkgid)

    ###
    ### METHODS FOR INSTALLING THE PAYLOAD
    ###
    def _removeTxSaveFile(self):
        # remove the transaction save file
        if self._yum._ts_save_file:
            try:
                os.unlink(self._yum._ts_save_file)
            except (OSError, IOError):
                pass
            else:
                self._yum._ts_save_file = None

    def checkSoftwareSelection(self):
        log.info("checking software selection")

        self._yum._undoDepInstalls()

        # doPostSelection
        # select kernel packages
        # select packages needed for storage, bootloader

        # check dependencies
        # XXX FIXME: set self._yum.dsCallback before entering this loop?
        while True:
            log.info("checking dependencies")
            (code, msgs) = self._yum.buildTransaction(unfinished_transactions_check=False)

            if code == 0:
                # empty transaction?
                log.debug("empty transaction")
                break
            elif code == 2:
                # success
                log.debug("success")
                break
            elif self.data.packages.handleMissing == KS_MISSING_IGNORE:
                log.debug("ignoring missing due to ks config")
                break
            elif self.data.upgrade.upgrade:
                log.debug("ignoring unresolved deps on upgrade")
                break

            for msg in msgs:
                log.warning(msg)

            exn = DependencyError(msgs)
            rc = errorHandler.cb(exn)
            if rc == ERROR_RAISE:
                raise exn
            elif rc == ERROR_RETRY:
                # FIXME: figure out how to allow modification of software set
                self._yum._undoDepInstalls()
                return False
            elif rc == ERROR_CONTINUE:
                break

        # check free space (?)

        self._removeTxSaveFile()

    def preInstall(self):
        """ Perform pre-installation tasks. """
        super(YumPayload, self).preInstall()

        # doPreInstall
        # create a bunch of directories like /var, /var/lib/rpm, /root, &c (?)
        # create mountpoints for protected device mountpoints (?)
        # initialize the backend logger
        # write static configs (storage, modprobe.d/anaconda.conf, network, keyboard)
        #   on upgrade, just make sure /etc/mtab is a symlink to /proc/self/mounts

        if not self.data.upgrade.upgrade:
            # this adds nofsync, which speeds things up but carries a risk of
            # rpmdb data loss if a crash occurs. that's why we only do it on
            # initial install and not for upgrades.
            rpm.addMacro("__dbi_htconfig",
                         "hash nofsync %{__dbi_other} %{__dbi_perms}")

        if self.data.packages.excludeDocs:
            rpm.addMacro("_excludedocs", "1")

    def install(self):
        """ Install the payload. """
        log.info("preparing transaction")
        log.debug("initialize transaction set")
        self._yum.initActionTs()

        log.debug("populate transaction set")
        try:
            # uses dsCallback.transactionPopulation
            self._yum.populateTs(keepold=0)
        except RepoError as e:
            log.error("error populating transaction: %s" % e)
            exn = PayloadInstallError(str(e))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        log.debug("check transaction set")
        self._yum.ts.check()
        log.debug("order transaction set")
        self._yum.ts.order()
        self._yum.ts.clean()

        # set up rpm logging to go to our log
        self._yum.ts.ts.scriptFd = self.install_log.fileno()
        rpm.setLogFile(self.install_log)

        # create the install callback
        rpmcb = RPMCallback(self._yum, self.install_log,
                            upgrade=self.data.upgrade.upgrade)

        if flags.testing:
            self._yum.ts.setFlags(rpm.RPMTRANS_FLAG_TEST)

        log.info("running transaction")
        try:
            self._yum.runTransaction(cb=rpmcb)
        except PackageSackError as e:
            log.error("error running transaction: %s" % e)
            exn = PayloadInstallError(str(e))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn
        except YumRPMTransError as e:
            log.error("error running transaction: %s" % e)
            for error in e.errors:
                log.error(e[0])
            exn = PayloadInstallError(str(e))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn
        except YumBaseError as e:
            log.error("error [2] running transaction: %s" % e)
            for error in e.errors:
                log.error("%s" % e[0])
            exn = PayloadInstallError(str(e))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn
        finally:
            self._yum.ts.close()
            iutil.resetRpmDb()

    def postInstall(self):
        """ Perform post-installation tasks. """
        self._yum.close()

        # clean up repo tmpdirs
        self._yum.cleanPackages()
        self._yum.cleanHeaders()

        # remove cache dirs of install-specific repos
        for repo in self._yum.repos.listEnabled():
            if repo.name == BASE_REPO_NAME or repo.id.startswith("anaconda-"):
                shutil.rmtree(repo.cachedir)

        # clean the yum cache on upgrade
        if self.data.upgrade.upgrade:
            self._yum.cleanMetadata()

        # TODO: on preupgrade, remove the preupgrade dir

        self._removeTxSaveFile()

        super(YumPayload, self).postInstall()

class RPMCallback(object):
    def __init__(self, yb, log, upgrade):
        self._yum = yb              # yum.YumBase
        self.install_log = log      # file instance
        self.upgrade = upgrade      # boolean

        self.package_file = None    # file instance (package file management)

        self.total_actions = 0
        self.completed_actions = 0

    def _get_txmbr(self, key):
        """ Return a (name, TransactionMember) tuple from cb key. """
        if hasattr(key, "po"):
            # New-style callback, key is a TransactionMember
            txmbr = key
            name = key.name
        else:
            # cleanup/remove error
            name = key
            txmbr = None

        return (name, txmbr)

    def callback(self, event, amount, total, key, userdata):
        """ Yum install callback. """
        if event == rpm.RPMCALLBACK_TRANS_START:
            self.total_actions = total
            self.completed_actions = 0
        elif event == rpm.RPMCALLBACK_TRANS_PROGRESS:
            # amount / total complete
            pass
        elif event == rpm.RPMCALLBACK_TRANS_STOP:
            # we are done
            pass
        elif event == rpm.RPMCALLBACK_INST_OPEN_FILE:
            # update status that we're installing/upgrading %h
            # return an open fd to the file
            txmbr = self._get_txmbr(key)[1]

            if self.upgrade:
                mode = _("Upgrading")
            else:
                mode = _("Installing")

            self.completed_actions += 1
            self.install_log.write("%s %s %s (%d/%d)\n"
                                    % (time.strftime("%H:%M:%S"),
                                       mode,
                                       txmbr.po,
                                       self.completed_actions,
                                       self.total_actions))
            self.install_log.flush()

            self.package_file = None
            repo = self._yum.repos.getRepo(txmbr.po.repoid)

            while self.package_file is None:
                try:
                    package_path = repo.getPackage(txmbr.po)
                except (yum.Errors.NoMoreMirrorsRepoError, IOError):
                    exn = PayloadInstallError("failed to open package")
                    if errorHandler.cb(exn, txmbr.po) == ERROR_RAISE:
                        raise exn
                except yum.Errors.RepoError:
                    continue

                self.package_file = open(package_path)

            return self.package_file.fileno()
        elif event == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            # close and remove the last opened file
            # update count of installed/upgraded packages
            package_path = self.package_file.name
            self.package_file.close()
            self.package_file = None

            cache_dir = os.path.normpath("%s/%s" % (ROOT_PATH, self._cache_dir))
            if package_path.startswith(cache_dir):
                try:
                    os.unlink(package_path)
                except OSError as e:
                    log.debug("unable to remove file %s" % e.strerror)
        elif event == rpm.RPMCALLBACK_UNINST_START:
            # update status that we're cleaning up %key
            #progress.set_text(_("Cleaning up %s" % key))
            pass
        elif event in (rpm.RPMCALLBACK_CPIO_ERROR,
                       rpm.RPMCALLBACK_UNPACK_ERROR,
                       rpm.RPMCALLBACK_SCRIPT_ERROR):
            name = self._get_txmbr(key)[0]

            # Script errors store whether or not they're fatal in "total".  So,
            # we should only error out for fatal script errors or the cpio and
            # unpack problems.
            if event != rpm.RPMCALLBACK_SCRIPT_ERROR or total:
                exn = PayloadInstallError("cpio, unpack, or fatal script error")
                if errorHandler.cb(exn, name) == ERROR_RAISE:
                    raise exn
