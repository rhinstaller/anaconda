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
        - document all methods
        - YumPayload
            - preupgrade
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
from pyanaconda import isys
from pyanaconda.network import hasActiveNetDev

from pyanaconda.image import opticalInstallMedia
from pyanaconda.image import mountImage
from pyanaconda.image import findFirstIsoImage

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

from pyanaconda.errors import *
from pyanaconda.packaging import NoSuchGroup, NoSuchPackage
import pyanaconda.progress as progress

default_repos = [productName.lower(), "rawhide"]

from threading import Lock
_yum_lock = Lock()

_yum_cache_dir = "/tmp/yum.cache"

class YumPayload(PackagePayload):
    """ A YumPayload installs packages onto the target system using yum.

        User-defined (aka: addon) repos exist both in ksdata and in yum. They
        are the only repos in ksdata.repo. The repos we find in the yum config
        only exist in yum. Lastly, the base repo exists in yum and in
        ksdata.method.
    """
    def __init__(self, data):
        if rpm is None or yum is None:
            raise PayloadError("unsupported payload type")

        PackagePayload.__init__(self, data)

        self.install_device = None
        self.proxy = None                           # global proxy
        self._root_dir = "/tmp/yum.root"
        self._repos_dir = "/etc/yum.repos.d,/etc/anaconda.repos.d,/tmp/updates/anaconda.repos.d,/tmp/product/anaconda.repos.d"
        self._yum = None

        self.reset()

    def reset(self, root=None):
        """ Reset this instance to its initial (unconfigured) state. """
        from pyanaconda.storage.size import Size

        if os.path.ismount(INSTALL_TREE) and not flags.testing:
            isys.umount(INSTALL_TREE)

        if os.path.islink(INSTALL_TREE):
            os.unlink(INSTALL_TREE)

        if os.path.ismount(ISO_DIR) and not flags.testing:
            isys.umount(INSTALL_TREE)

        if self.install_device:
            self.install_device.teardown(recursive=True)

        self.install_device = None

        self._space_required = Size(bytes=0)

        self._groups = []
        self._packages = []

        self._resetYum(root=root)

    def setup(self, storage, proxy=None):
        self.proxy = proxy
        self._writeYumConfig()

        self.updateBaseRepo(storage)

        # When setup is called, it's already in a separate thread. That thread
        # will try to select groups right after this returns, so make sure we
        # have group info ready.
        self.gatherRepoMetadata()

    def _resetYum(self, root=None):
        """ Delete and recreate the payload's YumBase instance. """
        import shutil
        if root is None:
            root = self._root_dir

        with _yum_lock:
            if self._yum:
                for repo in self._yum.repos.listEnabled():
                    if repo.name == BASE_REPO_NAME and \
                       os.path.isdir(repo.cachedir):
                        shutil.rmtree(repo.cachedir)

                del self._yum

            self._yum = yum.YumBase()

            self._yum.use_txmbr_in_callback = True

            # Set some configuration parameters that don't get set through a config
            # file.  yum will know what to do with these.
            self._yum.preconf.enabled_plugins = ["blacklist", "whiteout"]
            self._yum.preconf.fn = "/tmp/anaconda-yum.conf"
            self._yum.preconf.root = root
            # set this now to the best default we've got ; we'll update it if/when
            # we get a base repo set up
            self._yum.preconf.releasever = self._getReleaseVersion(None)

    def _writeYumConfig(self):
        """ Write out anaconda's main yum configuration file. """
        buf = """
[main]
cachedir=%s
keepcache=0
logfile=/tmp/yum.log
metadata_expire=never
pluginpath=/usr/lib/yum-plugins,/tmp/updates/yum-plugins
pluginconfpath=/etc/yum/pluginconf.d,/tmp/updates/pluginconf.d
plugins=1
reposdir=%s
""" % (_yum_cache_dir, self._repos_dir)

        if flags.noverifyssl:
            buf += "sslverify=0\n"

        if self.proxy:
            # FIXME: include proxy_username, proxy_password
            buf += "proxy=%s\n" % proxy

        open("/tmp/anaconda-yum.conf", "w").write(buf)

    def _yumCacheDirHack(self):
        # This is what it takes to get yum to use a cache dir outside the
        # install root. We do this so we don't have to re-gather repo meta-
        # data after we change the install root to ROOT_PATH, which can only
        # happen after we've enabled the new storage configuration.
        if not self._yum.conf.cachedir.startswith(self._yum.conf.installroot):
            return

        root = self._yum.conf.installroot
        self._yum.conf.cachedir = self._yum.conf.cachedir[len(root):]

    def _writeInstallConfig(self):
        """ Write out the yum config that will be used to install packages.

            Write out repo config files for all enabled repos, then
            create a new YumBase instance with the new filesystem tree as its
            install root.
        """
        self._repos_dir = "/tmp/yum.repos.d"
        if not os.path.isdir(self._repos_dir):
            os.mkdir(self._repos_dir)

        for repo in self._yum.repos.listEnabled():
            cfg_path = "%s/%s.repo" % (self._repos_dir, repo.id)
            ks_repo = self.getRepo(repo.id)
            with open(cfg_path, "w") as f:
                f.write("[%s]\n" % repo.id)
                f.write("name=Install - %s\n" % repo.id)
                f.write("enabled=1\n")
                if repo.baseurl:
                    f.write("baseurl=%s\n" % repo.baseurl[0])
                elif repo.mirrorlist:
                    f.write("mirrorlist=%s" % repo.mirrorlist)
                else:
                    log.error("repo %s has no baseurl or mirrorlist" % repo.id)
                    f.close()
                    os.unlink(cfg_path)
                    continue

                # kickstart repo modifiers
                if ks_repo:
                    if ks_repo.noverifyssl:
                        f.write("verifyssl=0\n")

                    if ks_repo.proxy:
                        f.write("proxy=%s\n" % ks_repo.proxy)

                    if ks_repo.cost:
                        f.write("cost=%d\n" % ks_repo.cost)

                    if ks_repo.includepkgs:
                        f.write("includepkgs=%s\n"
                                % ",".join(ks_repo.includepkgs))

                    if ks_repo.excludepkgs:
                        f.write("exclude=%s\n"
                                % ",".join(ks_repo.excludepkgs))

                    if ks_repo.ignoregroups:
                        f.write("enablegroups=0\n")

        releasever = self._yum.conf.yumvar['releasever']
        self._writeYumConfig()
        self._resetYum(root=ROOT_PATH)
        log.debug("setting releasever to previous value of %s" % releasever)
        self._yum.preconf.releasever = releasever

        self._yumCacheDirHack()
        self.gatherRepoMetadata()

        # trigger setup of self._yum.config
        log.debug("installation yum config repos: %s"
                  % ",".join([r.id for r in self._yum.repos.listEnabled()]))

    def release(self):
        from yum.packageSack import MetaSack
        log.debug("deleting package sacks")
        if hasattr(self._yum, "_pkgSack"):
            self._yum._pkgSack = None

        self._yum.repos.pkgSack = MetaSack()

        for repo in self._yum.repos.repos.values():
            repo._sack = None

    ###
    ### METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def repos(self):
        return self._yum.repos.repos.keys()

    @property
    def addOns(self):
        return [r.name for r in self.data.repo.dataList()]

    @property
    def baseRepo(self):
        repo_names = [BASE_REPO_NAME] + default_repos
        base_repo_name = None
        for repo_name in repo_names:
            if repo_name in self.repos and \
               self._yum.repos.getRepo(repo_name).enabled:
                base_repo_name = repo_name
                break

        return base_repo_name

    def updateBaseRepo(self, storage, fallback=True, root=None):
        """ Update the base repo based on self.data.method.

            - Tear down any previous base repo devices, symlinks, &c.
            - Reset the YumBase instance.
            - Try to convert the new method to a base repo.
            - If that fails, we'll use whatever repos yum finds in the config.
            - Set up addon repos.
            - Filter out repos that don't make sense to have around.
            - Get metadata for all enabled repos, disabling those for which the
              retrieval fails.
        """
        log.info("updating base repo")

        # start with a fresh YumBase instance
        self.reset(root=root)

        # see if we can get a usable base repo from self.data.method
        try:
            self._configureBaseRepo(storage)
        except PayloadError as e:
            if not fallback:
                for repo in self._yum.repos.repos.values():
                    if repo.enabled:
                        self.disableRepo(repo.id)
                raise

            # this preserves the method details while disabling it
            self.data.method.method = None
        finally:
            self._yumCacheDirHack()

        if BASE_REPO_NAME not in self._yum.repos.repos.keys():
            log.info("using default repos from local yum configuration")
            if self._yum.conf.yumvar['releasever'] == "rawhide" and \
               "rawhide" in self.repos:
                self.enableRepo("rawhide")

        # set up addon repos
        # FIXME: driverdisk support
        for repo in self.data.repo.dataList():
            try:
                self.configureAddOnRepo(repo)
            except NoNetworkError as e:
                log.error("repo %s needs an active network connection"
                          % repo.name)
                self.removeRepo(repo.name)
            except PayloadError as e:
                log.error("repo %s setup failed: %s" % (repo.name, e))
                self.removeRepo(repo.name)

        # now disable and/or remove any repos that don't make sense
        for repo in self._yum.repos.repos.values():
            """ Rules for which repos to enable/disable/remove

                - always remove
                    - source, debuginfo
                - disable if isFinal
                    - rawhide, development
                - disable all other built-in repos if rawhide is enabled
                - remove any repo when not isFinal and repo not enabled
                - if a base repo is defined, disable any repo not defined by
                  the user that is not the base repo

                FIXME: updates needs special handling

            """
            if repo.id in self.addOns:
                continue

            if "-source" in repo.id or "-debuginfo" in repo.id:
                self._removeYumRepo(repo.id)
            elif isFinal and ("rawhide" in repo.id or "development" in repo.id):
                # XXX the "development" part seems a bit heavy handed
                self._removeYumRepo(repo.id)
            elif self._yum.conf.yumvar['releasever'] == "rawhide" and \
                 "rawhide" in self.repos and \
                 self._yum.repos.getRepo("rawhide").enabled and \
                 repo.id != "rawhide":
                self.disableRepo(repo.id)
            elif self.data.method.method and \
                 repo.id != BASE_REPO_NAME and \
                 repo.id not in [r.name for r in self.data.repo.dataList()]:
                # if a method/repo was given, disable all default repos
                self.disableRepo(repo.id)

    def gatherRepoMetadata(self):
        # now go through and get metadata for all enabled repos
        log.info("gathering repo metadata")
        for repo_id in self.repos:
            repo = self._yum.repos.getRepo(repo_id)
            if repo.enabled:
                try:
                    self._getRepoMetadata(repo)
                except PayloadError as e:
                    log.error("failed to grab repo metadata for %s: %s"
                              % (repo_id, e))
                    self.disableRepo(repo_id)

        log.info("metadata retrieval complete")

    def _configureBaseRepo(self, storage):
        """ Configure the base repo.

            If self.data.method.method is set, failure to configure a base repo
            should generate a PayloadError exception.

            If self.data.method.method is unset, no exception should be raised
            and no repo should be configured.
        """
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
                device.teardown(recursive=True)
                raise PayloadSetupError("failed to find valid iso image")

            if path.endswith(".iso"):
                path = os.path.dirname(path)

            # mount the ISO on a loop
            image = os.path.normpath("%s/%s" % (path, image))
            mountImage(image, INSTALL_TREE)

            self.install_device = device
            url = "file://" + INSTALL_TREE
        elif method.method == "nfs":
            # Mount the NFS share on ISO_DIR. If it ends up not being nfsiso we
            # will create a symlink at INSTALL_TREE pointing to ISO_DIR.
            self._setupNFS(ISO_DIR, method.server, method.dir, method.opts)

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
                # mount the ISO on a loop
                image = os.path.normpath("%s/%s" % (ISO_DIR, image))
                mountImage(image, INSTALL_TREE)
            else:
                # create a symlink at INSTALL_TREE that points to ISO_DIR
                try:
                    if os.path.exists(INSTALL_TREE):
                        os.unlink(INSTALL_TREE)
                    os.symlink(os.path.basename(ISO_DIR), INSTALL_TREE)
                except OSError as e:
                    log.error("failed to update %s symlink: %s"
                              % (INSTALL_TREE, e))
                    raise PayloadSetupError(str(e))

            url = "file://" + INSTALL_TREE
        elif method.method == "url":
            url = method.url
            sslverify = not (method.noverifyssl or flags.noverifyssl)
            proxy = method.proxy or self.proxy
        elif method.method == "cdrom" or not method.method:
            # cdrom or no method specified -- check for media
            device = opticalInstallMedia(storage.devicetree)
            if device:
                self.install_device = device
                url = "file://" + INSTALL_TREE
                if not method.method:
                    method.method = "cdrom"
            elif method.method == "cdrom":
                raise PayloadSetupError("no usable optical media found")

        if method.method:
            self._yum.preconf.releasever = self._getReleaseVersion(url)
            self._yumCacheDirHack()
            try:
                self._addYumRepo(BASE_REPO_NAME, url,
                                 proxy=proxy, sslverify=sslverify)
            except MetadataError as e:
                log.error("base repo (%s/%s) not valid -- removing it"
                          % (method.method, url))
                self._removeYumRepo(BASE_REPO_NAME)
                raise

    def configureAddOnRepo(self, repo):
        """ Configure a single ksdata repo. """
        url = repo.baseurl
        if url and url.startswith("nfs:"):
            (opts, server, path) = iutil.parseNfsUrl(url)
            mountpoint = "%s/%s.nfs" % (MOUNT_DIR, repo.name)
            self._setupNFS(mountpoint, server, path, opts)

            url = "file://" + mountpoint

        if self._repoNeedsNetwork(repo) and not hasActiveNetDev():
            raise NoNetworkError

        proxy = repo.proxy or self.proxy
        sslverify = not (flags.noverifyssl or repo.noverifyssl)

        # this repo is already in ksdata, so we only add it to yum here
        self._addYumRepo(repo.name, url, repo.mirrorlist, cost=repo.cost,
                         exclude=repo.excludepkgs, includepkgs=repo.includepkgs,
                         proxy=proxy, sslverify=sslverify)

        # TODO: enable addons via treeinfo

    def _getRepoMetadata(self, yumrepo):
        """ Retrieve repo metadata if we don't already have it. """
        from yum.Errors import RepoError, RepoMDError

        # And try to grab its metadata.  We do this here so it can be done
        # on a per-repo basis, so we can then get some finer grained error
        # handling and recovery.
        log.debug("getting repo metadata for %s" % yumrepo.id)
        with _yum_lock:
            try:
                yumrepo.getPrimaryXML()
            except RepoError as e:
                raise MetadataError(e.value)

            # Not getting group info is bad, but doesn't seem like a fatal error.
            # At the worst, it just means the groups won't be displayed in the UI
            # which isn't too bad, because you may be doing a kickstart install and
            # picking packages instead.
            log.debug("getting group info for %s" % yumrepo.id)
            try:
                yumrepo.getGroups()
            except RepoMDError:
                log.error("failed to get groups for repo %s" % yumrepo.id)

    def _addYumRepo(self, name, baseurl, mirrorlist=None, **kwargs):
        """ Add a yum repo to the YumBase instance. """
        from yum.Errors import RepoError

        # First, delete any pre-existing repo with the same name.
        if name in self._yum.repos.repos:
            self._yum.repos.delete(name)

        log.debug("adding yum repo %s with baseurl %s and mirrorlist %s"
                    % (name, baseurl, mirrorlist))
        with _yum_lock:
            # Then add it to yum's internal structures.
            obj = self._yum.add_enable_repo(name,
                                            baseurl=[baseurl],
                                            mirrorlist=mirrorlist,
                                            **kwargs)

            # this will trigger retrieval of repomd.xml, which is small and yet
            # gives us some assurance that the repo config is sane
            obj.mdpolicy = "meh"
            try:
                obj.repoXML
            except RepoError as e:
                raise MetadataError(e.value)

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

    def _removeYumRepo(self, repo_id):
        if repo_id in self.repos:
            with _yum_lock:
                self._yum.repos.delete(repo_id)
                self._groups = []
                self._packages = []

    def removeRepo(self, repo_id):
        """ Remove a repo as specified by id. """
        log.debug("removing repo %s" % repo_id)

        # if this is an NFS repo, we'll want to unmount the NFS mount after
        # removing the repo
        mountpoint = None
        yum_repo = self._yum.repos.getRepo(repo_id)
        ks_repo = self.getRepo(repo_id)
        if yum_repo and ks_repo and ks_repo.baseurl.startswith("nfs:"):
            mountpoint = yum_repo.baseurl[0][7:]    # strip leading "file://"

        self._removeYumRepo(repo_id)
        super(YumPayload, self).removeRepo(repo_id)

        if mountpoint and os.path.ismount(mountpoint):
            try:
                isys.umount(mountpoint)
            except SystemError as e:
                log.error("failed to unmount nfs repo %s: %s" % (mountpoint, e))

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

            self._groups = []
            self._packages = []

    ###
    ### METHODS FOR WORKING WITH GROUPS
    ###
    @property
    def groups(self):
        from yum.Errors import RepoError
        from yum.Errors import GroupsError

        with _yum_lock:
            if not self._groups:
                if self.needsNetwork and not hasActiveNetDev():
                    raise NoNetworkError

                try:
                    self._groups = self._yum.comps
                except (RepoError, GroupsError) as e:
                    log.error("failed to get group info: %s" % e)
                    raise MetadataError(e.value)

            return [g.groupid for g in self._groups.get_groups()]

    def description(self, groupid):
        """ Return name/description tuple for the group specified by id. """
        with _yum_lock:
            if not self._groups.has_group(groupid):
                raise NoSuchGroup(groupid)

            group = self._groups.return_group(groupid)

            return (group.ui_name, group.ui_description)

    def _selectYumGroup(self, groupid, default=True, optional=False):
        # select the group in comps
        pkg_types = ['mandatory']
        if default:
            pkg_types.append("default")

        if optional:
            pkg_types.append("optional")

        log.debug("select group %s" % groupid)
        with _yum_lock:
            try:
                self._yum.selectGroup(groupid, group_package_types=pkg_types)
            except yum.Errors.GroupsError:
                raise NoSuchGroup(groupid)

    def _deselectYumGroup(self, groupid):
        # deselect the group in comps
        log.debug("deselect group %s" % groupid)
        with _yum_lock:
            try:
                self._yum.deselectGroup(groupid, force=True)
            except yum.Errors.GroupsError:
                raise NoSuchGroup(groupid)

    ###
    ### METHODS FOR WORKING WITH PACKAGES
    ###
    @property
    def packages(self):
        from yum.Errors import RepoError

        with _yum_lock:
            if not self._packages:
                if self.needsNetwork and not hasActiveNetDev():
                    raise NoNetworkError

                try:
                    self._packages = self._yum.pkgSack.returnPackages()
                except RepoError as e:
                    raise MetadataError(e.value)

            return self._packages

    def _selectYumPackage(self, pkgid):
        """Mark a package for installation.

           pkgid - The name of a package to be installed.  This could include
                   a version or architecture component.
        """
        log.debug("select package %s" % pkgid)
        with _yum_lock:
            try:
                mbrs = self._yum.install(pattern=pkgid)
            except yum.Errors.InstallError:
                raise NoSuchPackage(pkgid)

    def _deselectYumPackage(self, pkgid):
        """Mark a package to be excluded from installation.

           pkgid - The name of a package to be excluded.  This could include
                   a version or architecture component.
        """
        log.debug("deselect package %s" % pkgid)
        with _yum_lock:
            self._yum.tsInfo.deselect(pkgid)

    ###
    ### METHODS FOR QUERYING STATE
    ###
    @property
    def spaceRequired(self):
        """ The total disk space (Size) required for the current selection. """
        return self._space_required

    def calculateSpaceNeeds(self):
        from pyanaconda.storage.size import Size

        # XXX this will only be useful if you've run checkSoftwareSelection
        total = 0
        with _yum_lock:
            for txmbr in self._yum.tsInfo.getMembers():
                total += getattr(txmbr.po, "installedsize", 0)

        total += total * 0.10   # add 10% to account for metadata, &c
        self._space_required = Size(bytes=total)

        return self._space_required

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

    def _applyYumSelections(self):
        """ Apply the selections in ksdata to yum.

            This follows the same ordering/pattern as kickstart.py.
        """
        for package in self.data.packages.packageList:
            self._selectYumPackage(package)

        for group in self.data.packages.groupList:
            default = False
            optional = False
            if group.include == GROUP_DEFAULT:
                default = True
            elif group.include == GROUP_ALL:
                default = True
                optional = True

            self._selectYumGroup(group.name, default=default, optional=optional)

        for package in self.data.packages.excludedList:
            self._deselectYumPackage(package)

        for group in self.data.packages.excludedGroupList:
            self._deselectYumGroup(group.name)

        self.selectKernelPackage()

    def checkSoftwareSelection(self):
        log.info("checking software selection")

        with _yum_lock:
            self.release()
            self._yum._undoDepInstalls()

        self._applyYumSelections()

        with _yum_lock:
            # doPostSelection
            # select kernel packages
            # select packages needed for storage, bootloader

            # check dependencies
            log.info("checking dependencies")
            (code, msgs) = self._yum.buildTransaction(unfinished_transactions_check=False)
            self._removeTxSaveFile()
            if code == 0:
                # empty transaction?
                log.debug("empty transaction")
            elif code == 2:
                # success
                log.debug("success")
            elif self.data.packages.handleMissing == KS_MISSING_IGNORE:
                log.debug("ignoring missing due to ks config")
            elif self.data.upgrade.upgrade:
                log.debug("ignoring unresolved deps on upgrade")
            else:
                for msg in msgs:
                    log.warning(msg)

                raise DependencyError(msgs)

        self.calculateSpaceNeeds()
        log.info("%d packages selected totalling %s"
                 % (len(self._yum.tsInfo.getMembers()), self.spaceRequired))

    def selectKernelPackage(self):
        kernels = self.kernelPackages
        selected = None
        # XXX This is optimistic. I'm curious if yum will DTRT if I just say
        #     "select this kernel" without jumping through hoops to figure out
        #     which arch it should use.
        for kernel in kernels:
            try:
                # XXX might need explicit arch specification
                self._selectYumPackage(kernel)
            except NoSuchPackage as e:
                log.info("no %s package" % kernel)
                continue
            else:
                log.info("selected %s" % kernel)
                selected = kernel
                # select module packages for this kernel

                # select the devel package if gcc will be installed
                if self._yum.tsInfo.matchNaevr(name="gcc"):
                    log.info("selecting %s-devel" % kernel)
                    # XXX might need explicit arch specification
                    self._selectYumPackage("%s-devel" % kernel)

                break

        if not selected:
            log.error("failed to select a kernel from %s" % kernels)

    def preInstall(self, packages=None):
        """ Perform pre-installation tasks. """
        super(YumPayload, self).preInstall(packages=packages)
        progress.send_message(_("Starting package installation process"))

        self._writeInstallConfig()
        self.checkSoftwareSelection()

        # doPreInstall
        # create mountpoints for protected device mountpoints (?)
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
        from yum.Errors import PackageSackError, RepoError, YumBaseError, YumRPMTransError

        log.info("preparing transaction")
        log.debug("initialize transaction set")
        with _yum_lock:
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
            progress.send_step()
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
            else:
                log.info("transaction complete")
                self.install_log.write("*** FINISHED INSTALLING PACKAGES ***")
                progress.send_step()
            finally:
                self.install_log.close()
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
    def __init__(self, yb, log, upgrade=False):
        self._yum = yb              # yum.YumBase
        self.install_log = log      # file instance
        self.upgrade = upgrade      # boolean

        self.package_file = None    # file instance (package file management)

        self.total_actions = 0
        self.completed_actions = None   # will be set to 0 when starting tx
        self.base_arch = iutil.getArch()

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
            if amount == 6:
                progress.send_message(_("Preparing transaction from installation source"))
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

            # If self.completed_actions is still None, that means this package
            # is being opened to retrieve a %pretrans script. Don't log that
            # we're installing the package unless we've been called with a
            # TRANS_START event.
            if self.completed_actions is not None:
                if self.upgrade:
                    mode = _("Upgrading")
                else:
                    mode = _("Installing")

                self.completed_actions += 1
                msg_format = "%s %s (%d/%d)"
                progress_package = txmbr.name
                if txmbr.arch not in ["noarch", self.base_arch]:
                    progress_package = "%s.%s" % (txmbr.name, txmbr.arch)

                progress_msg =  msg_format % (mode, progress_package,
                                              self.completed_actions,
                                              self.total_actions)
                log_msg = msg_format % (mode, txmbr.po,
                                        self.completed_actions,
                                        self.total_actions)
                self.install_log.write("%s %s\n" % (time.strftime("%H:%M:%S"),
                                                    log_msg))
                self.install_log.flush()
                progress.send_message(progress_msg)

            self.package_file = None
            repo = self._yum.repos.getRepo(txmbr.po.repoid)

            while self.package_file is None:
                try:
                    package_path = repo.getPackage(txmbr.po)
                except (yum.Errors.NoMoreMirrorsRepoError, IOError):
                    if os.path.exists(txmbr.po.localPkg()):
                        os.unlink(txmbr.po.localPkg())
                        log.debug("retrying download of %s" % txmbr.po)
                        continue
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

            if package_path.startswith(_yum_cache_dir):
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
