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
            - handling of proxy needs cleanup
                - passed to anaconda as --proxy, --proxyUsername, and
                  --proxyPassword
                    - drop the use of a file for proxy and ftp auth info
                - specified via KS as a URL

"""

from ConfigParser import MissingSectionHeaderError

import os
import shutil
import sys
import time
import tempfile

from . import *

import logging
log = logging.getLogger("packaging")

try:
    import rpm
    import rpmUtils
except ImportError:
    log.error("import of rpm failed")
    rpm = None
    rpmUtils = None

try:
    import yum
    # This is a bit of a hack to short circuit yum's internal logging
    # handler setup.  We already set one up so we don't need it to run.
    # yum may give us an API to fiddle this at a later time.
    yum.logginglevels._added_handlers = True
except ImportError:
    log.error("import of yum failed")
    yum = None

from pyanaconda.constants import *
from pyanaconda.flags import flags

from pyanaconda import iutil
from pyanaconda.iutil import ProxyString, ProxyStringError
from pyanaconda import isys
from pyanaconda.network import hasActiveNetDev
from pyanaconda.storage.size import Size

from pyanaconda.image import opticalInstallMedia
from pyanaconda.image import mountImage
from pyanaconda.image import findFirstIsoImage

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

from pyanaconda.errors import *
from pyanaconda.packaging import NoSuchGroup, NoSuchPackage
import pyanaconda.progress as progress

from pyanaconda.localization import expand_langs
import itertools

from pykickstart.constants import KS_MISSING_IGNORE

default_repos = [productName.lower(), "rawhide"]

from threading import RLock
_yum_lock = RLock()

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
        self._root_dir = "/tmp/yum.root"
        self._repos_dir = "/etc/yum.repos.d,/etc/anaconda.repos.d,/tmp/updates/anaconda.repos.d,/tmp/product/anaconda.repos.d"
        self._yum = None
        self._setup = False

        self._requiredPackages = []
        self._requiredGroups = []

        self.reset()

    def reset(self, root=None):
        """ Reset this instance to its initial (unconfigured) state. """

        # cdrom: install_device.teardown (INSTALL_TREE)
        # hd: umount INSTALL_TREE, install_device.teardown (ISO_DIR)
        # nfs: umount INSTALL_TREE
        # nfsiso: umount INSTALL_TREE, umount ISO_DIR
        if os.path.ismount(INSTALL_TREE) and not flags.testing:
            if self.install_device and \
               get_mount_device(INSTALL_TREE) == self.install_device.path:
                self.install_device.teardown(recursive=True)
            else:
                isys.umount(INSTALL_TREE, removeDir=False)

        if os.path.ismount(ISO_DIR) and not flags.testing:
            if self.install_device and \
               get_mount_device(ISO_DIR) == self.install_device.path:
                self.install_device.teardown(recursive=True)
            # The below code will fail when nfsiso is the stage2 source
            # But if we don't do this we may not be able to switch from
            # one nfsiso repo to another nfsiso repo.  We need to have a
            # way to detect the stage2 state and work around it.
            # Commenting out the below is a hack for F18.  FIXME
            #else:
            #    # NFS
            #    isys.umount(ISO_DIR, removeDir=False)

        self.install_device = None

        # This value comes from a default install of the x86_64 Fedora 18.  It
        # is meant as a best first guess only.  Once package metadata is
        # available we can use that as a better value.
        self._space_required = Size(spec="3000 MB")

        self._groups = None
        self._packages = []

        self._resetYum(root=root)

    def setup(self, storage):
        super(YumPayload, self).setup(storage)

        self._writeYumConfig()
        self._setup = True

        self.updateBaseRepo()

        # When setup is called, it's already in a separate thread. That thread
        # will try to select groups right after this returns, so make sure we
        # have group info ready.
        self.gatherRepoMetadata()

    def _resetYum(self, root=None, keep_cache=False):
        """ Delete and recreate the payload's YumBase instance. """
        import shutil
        if root is None:
            root = self._root_dir

        with _yum_lock:
            if self._yum:
                if not keep_cache:
                    for repo in self._yum.repos.listEnabled():
                        if repo.name == BASE_REPO_NAME and \
                           os.path.isdir(repo.cachedir):
                            shutil.rmtree(repo.cachedir)

                del self._yum

            self._yum = yum.YumBase()

            self._yum.use_txmbr_in_callback = True

            # Set some configuration parameters that don't get set through a config
            # file.  yum will know what to do with these.
            # Enable all types of yum plugins. We're somewhat careful about what
            # plugins we put in the environment.
            self._yum.preconf.plugin_types = yum.plugins.ALL_TYPES
            self._yum.preconf.enabled_plugins = ["blacklist", "whiteout", "fastestmirror",
                                                 "langpacks"]
            self._yum.preconf.fn = "/tmp/anaconda-yum.conf"
            self._yum.preconf.root = root
            # set this now to the best default we've got ; we'll update it if/when
            # we get a base repo set up
            self._yum.preconf.releasever = self._getReleaseVersion(None)
            # Set the yum verbosity to 6, and update yum's internal logger
            # objects to the debug level.  This is a bit of a hack requiring
            # internal knowledge of yum, that will hopefully go away in the
            # future with API improvements.
            self._yum.preconf.debuglevel = 6
            self._yum.preconf.errorlevel = 6
            self._yum.logger.setLevel(logging.DEBUG)
            self._yum.verbose_logger.setLevel(logging.DEBUG)

        self.txID = None

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

        if self.data.packages.multiLib:
            buf += "multilib_policy=all\n"

        if self.data.method.proxy:
            try:
                proxy = ProxyString(self.data.method.proxy)
                buf += "proxy=%s\n" % (proxy.noauth_url,)
                if proxy.username:
                    buf += "proxy_username=%s\n" % (proxy.username,)
                if proxy.password:
                    buf += "proxy_password=%s\n" % (proxy.password,)
            except ProxyStringError as e:
                log.error("Failed to parse proxy for _writeYumConfig %s: %s" \
                          % (self.data.method.proxy, e))

        open("/tmp/anaconda-yum.conf", "w").write(buf)

    # YUMFIXME: yum should allow a cache dir outside of the installroot
    def _yumCacheDirHack(self):
        # This is what it takes to get yum to use a cache dir outside the
        # install root. We do this so we don't have to re-gather repo meta-
        # data after we change the install root to ROOT_PATH, which can only
        # happen after we've enabled the new storage configuration.
        with _yum_lock:
            if not self._yum.conf.cachedir.startswith(self._yum.conf.installroot):
                return

            root = self._yum.conf.installroot
            self._yum.conf.cachedir = self._yum.conf.cachedir[len(root):]

    def _writeInstallConfig(self):
        """ Write out the yum config that will be used to install packages.

            Write out repo config files for all enabled repos, then
            create a new YumBase instance with the new filesystem tree as its
            install root.

            This needs to be called from inside a yum_lock
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
                if repo.mirrorlist:
                    f.write("mirrorlist=%s" % repo.mirrorlist)
                elif repo.baseurl:
                    f.write("baseurl=%s\n" % repo.baseurl[0])
                else:
                    log.error("repo %s has no baseurl or mirrorlist" % repo.id)
                    f.close()
                    os.unlink(cfg_path)
                    continue

                # kickstart repo modifiers
                if ks_repo:
                    if ks_repo.noverifyssl:
                        f.write("sslverify=0\n")

                    if ks_repo.proxy:
                        try:
                            proxy = ProxyString(ks_repo.proxy)
                            f.write("proxy=%s\n" % (proxy.noauth_url,))
                            if proxy.username:
                                f.write("proxy_username=%s\n" % (proxy.username,))
                            if proxy.password:
                                f.write("proxy_password=%s\n" % (proxy.password,))
                        except ProxyStringError as e:
                            log.error("Failed to parse proxy for _writeInstallConfig %s: %s" \
                                      % (self.data.method.proxy, e))

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
        self._resetYum(root=ROOT_PATH, keep_cache=True)
        log.debug("setting releasever to previous value of %s" % releasever)
        self._yum.preconf.releasever = releasever

        self._yumCacheDirHack()
        self.gatherRepoMetadata()

        # trigger setup of self._yum.config
        log.debug("installation yum config repos: %s"
                  % ",".join([r.id for r in self._yum.repos.listEnabled()]))

    # YUMFIXME: there should be a way to reset package sacks without all this
    #           knowledge of the yum internals or, better yet, some convenience
    #           functions for multi-threaded applications
    def release(self):
        from yum.packageSack import MetaSack
        with _yum_lock:
            log.debug("deleting package sacks")
            if hasattr(self._yum, "_pkgSack"):
                self._yum._pkgSack = None

            self._yum.repos.pkgSack = MetaSack()

            for repo in self._yum.repos.repos.values():
                repo._sack = None

    def deleteYumTS(self):
        with _yum_lock:
            log.debug("deleting yum transaction info")
            self._yum.closeRpmDB()
            del self._yum.tsInfo
            del self._yum.ts

    def preStorage(self):
        self.release()
        with _yum_lock:
            self._yum.close()

    ###
    ### METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def repos(self):
        if not self._setup:
            return []

        _repos = []
        with _yum_lock:
            _repos = self._yum.repos.repos.keys()

        return _repos

    @property
    def addOns(self):
        return [r.name for r in self.data.repo.dataList()]

    @property
    def baseRepo(self):
        repo_names = [BASE_REPO_NAME] + default_repos
        base_repo_name = None
        with _yum_lock:
            for repo_name in repo_names:
                if repo_name in self.repos and \
                   self._yum.repos.getRepo(repo_name).enabled:
                    base_repo_name = repo_name
                    break

        return base_repo_name

    def updateBaseRepo(self, fallback=True, root=None, checkmount=True):
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
            self._configureBaseRepo(self.storage, checkmount=checkmount)
        except PayloadError as e:
            if not fallback:
                with _yum_lock:
                    for repo in self._yum.repos.repos.values():
                        if repo.enabled:
                            self.disableRepo(repo.id)
                raise

            # this preserves the method details while disabling it
            self.data.method.method = None
            self.install_device = None
        finally:
            self._yumCacheDirHack()

        with _yum_lock:
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
        with _yum_lock:
            for repo in self._yum.repos.repos.values():
                # Rules for which repos to enable/disable/remove
                #
                # - always remove
                #     - source, debuginfo
                # - disable if isFinal
                #     - rawhide, development
                # - disable all other built-in repos if rawhide is enabled
                # - remove any repo when not isFinal and repo not enabled
                # - if a base repo is defined, disable any repo not defined by
                #   the user that is not the base repo
                #
                # FIXME: updates needs special handling
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
            with _yum_lock:
                repo = self._yum.repos.getRepo(repo_id)
                if repo.enabled:
                    try:
                        self._getRepoMetadata(repo)
                    except PayloadError as e:
                        log.error("failed to grab repo metadata for %s: %s"
                                  % (repo_id, e))
                        self.disableRepo(repo_id)

        log.info("metadata retrieval complete")

    @property
    def ISOImage(self):
        if not self.data.method.method == "harddrive":
            return None
        # This could either be mounted to INSTALL_TREE or on
        # DRACUT_ISODIR if dracut did the mount.
        dev = get_mount_device(INSTALL_TREE)
        if dev:
            return dev[len(ISO_DIR)+1:]
        dev = get_mount_device(DRACUT_ISODIR)
        if dev:
            return dev[len(DRACUT_ISODIR)+1:]
        return None

    def _setUpMedia(self, device):
        method = self.data.method
        if method.method == "harddrive":
            self._setupDevice(device, mountpoint=ISO_DIR)

            # check for ISO images in the newly mounted dir
            path = ISO_DIR
            if method.dir:
                path = os.path.normpath("%s/%s" % (path, method.dir))

            # XXX it would be nice to streamline this when we're just setting
            #     things back up after storage activation instead of having to
            #     pretend we don't already know which ISO image we're going to
            #     use
            image = findFirstIsoImage(path)
            if not image:
                device.teardown(recursive=True)
                raise PayloadSetupError("failed to find valid iso image")

            if path.endswith(".iso"):
                path = os.path.dirname(path)

            # this could already be set up the first time through
            if not os.path.ismount(INSTALL_TREE):
                # mount the ISO on a loop
                image = os.path.normpath("%s/%s" % (path, image))
                mountImage(image, INSTALL_TREE)

            if not method.dir.endswith(".iso"):
                method.dir = os.path.normpath("%s/%s" % (method.dir,
                                                         os.path.basename(image)))
                while method.dir.startswith("/"):
                    # riduculous
                    method.dir = method.dir[1:]
        # Check to see if the device is already mounted, in which case
        # we don't need to mount it again
        elif method.method == "cdrom" and get_mount_paths(device.path):
                return
        else:
            device.format.setup(mountpoint=INSTALL_TREE)

    def _configureBaseRepo(self, storage, checkmount=True):
        """ Configure the base repo.

            If self.data.method.method is set, failure to configure a base repo
            should generate a PayloadError exception.

            If self.data.method.method is unset, no exception should be raised
            and no repo should be configured.

            If checkmount is true, check the dracut mount to see if we have
            usable media mounted.
        """
        log.info("configuring base repo")
        # set up the main repo specified by method=, repo=, or ks method
        # XXX FIXME: does this need to handle whatever was set up by dracut?
        # XXX FIXME: most of this probably belongs up in Payload
        method = self.data.method
        sslverify = True
        url = None
        mirrorlist = None

        # See if we already have stuff mounted due to dracut
        isodev = get_mount_device(DRACUT_ISODIR)
        device = get_mount_device(DRACUT_REPODIR)

        if method.method == "harddrive":
            if method.biospart:
                log.warning("biospart support is not implemented")
                devspec = method.biospart
            else:
                devspec = method.partition
                needmount = True
                # See if we used this method for stage2, thus dracut left it
                if isodev and method.partition and method.partition in isodev \
                and DRACUT_ISODIR in device:
                    # Everything should be setup
                    url = "file://" + DRACUT_REPODIR
                    needmount = False
                    # We don't setup an install_device here
                    # because we can't tear it down
            isodevice = storage.devicetree.resolveDevice(devspec)
            if needmount:
                self._setUpMedia(isodevice)
                url = "file://" + INSTALL_TREE
                self.install_device = isodevice
        elif method.method == "nfs":
            # See if dracut dealt with nfsiso
            if isodev:
                options, host, path = iutil.parseNfsUrl('nfs:%s' % isodev)
                # See if the dir holding the iso is what we want
                # and also if we have an iso mounted to /run/install/repo
                if path and path in isodev and DRACUT_ISODIR in device:
                    # Everything should be setup
                    url = "file://" + DRACUT_REPODIR
            else:
                # see if the nfs dir is mounted
                needmount = True
                if device:
                    options, host, path = iutil.parseNfsUrl('nfs:%s' % device)
                    if path and path in device:
                        needmount = False
                        path = DRACUT_REPODIR
                if needmount:
                    # Mount the NFS share on INSTALL_TREE. If it ends up
                    # being nfsiso we will move the mountpoint to ISO_DIR.
                    if method.dir.endswith(".iso"):
                        nfsdir = os.path.dirname(method.dir)
                    else:
                        nfsdir = method.dir
                    self._setupNFS(INSTALL_TREE, method.server, nfsdir,
                                   method.opts)
                    path = INSTALL_TREE

                # check for ISO images in the newly mounted dir
                if method.dir.endswith(".iso"):
                    # if the given URL includes a specific ISO image file, use it
                    image_file = os.path.basename(method.dir)
                    path = os.path.normpath("%s/%s" % (path, image_file))

                image = findFirstIsoImage(path)

                # it appears there are ISO images in the dir, so assume they want to
                # install from one of them
                if image:
                    # move the mount to ISO_DIR
                    # work around inability to move shared filesystems
                    iutil.execWithRedirect("mount",
                                           ["--make-rprivate", "/"],
                                           stderr="/dev/tty5", stdout="/dev/tty5")
                    iutil.execWithRedirect("mount",
                                           ["--move", INSTALL_TREE, ISO_DIR],
                                           stderr="/dev/tty5", stdout="/dev/tty5")
                    # Mounts are kept track of in isys it seems
                    # Remove the count for the source
                    if isys.mountCount.has_key(INSTALL_TREE):
                        if isys.mountCount[INSTALL_TREE] > 1:
                            isys.mountCount[INSTALL_TREE] -= 1
                        else:
                            del(isys.mountCount[INSTALL_TREE])
                    # Add a count for the new location
                    if not isys.mountCount.has_key(ISO_DIR):
                        isys.mountCount[ISO_DIR] = 0
                    isys.mountCount[ISO_DIR] += 1
                    # mount the ISO on a loop
                    image = os.path.normpath("%s/%s" % (ISO_DIR, image))
                    mountImage(image, INSTALL_TREE)

                    url = "file://" + INSTALL_TREE
                else:
                    # Fall back to the mount path instead of a mounted iso
                    url = "file://" + path
        elif method.method == "url":
            url = method.url
            mirrorlist = method.mirrorlist
            sslverify = not (method.noverifyssl or flags.noverifyssl)
        elif method.method == "cdrom" or (checkmount and not method.method):
            # Did dracut leave the DVD or NFS mounted for us?
            device = get_mount_device(DRACUT_REPODIR)
            # Only look at the dracut mount if we don't already have a cdrom
            if device and not self.install_device:
                self.install_device = storage.devicetree.getDeviceByPath(device)
                url = "file://" + DRACUT_REPODIR
                if not method.method:
                    # See if this is a nfs mount
                    if ':' in device:
                        # prepend nfs: to the url as that's what the parser
                        # wants.  Note we don't get options from this, but
                        # that's OK for the UI at least.
                        options, host, path = iutil.parseNfsUrl("nfs:%s" %
                                                                device)
                        method.method = "nfs"
                        method.server = host
                        method.dir = path
                    else:
                        method.method = "cdrom"
            else:
                # cdrom or no method specified -- check for media
                if not self.install_device:
                    self.install_device = opticalInstallMedia(storage.devicetree)
                if self.install_device:
                    if not method.method:
                        method.method = "cdrom"
                    self._setUpMedia(self.install_device)
                    url = "file://" + INSTALL_TREE
                elif method.method == "cdrom":
                    raise PayloadSetupError("no usable optical media found")

        if method.method:
            with _yum_lock:
                try:
                    self._yum.preconf.releasever = self._getReleaseVersion(url)
                except MissingSectionHeaderError as e:
                    log.error("couldn't set releasever from base repo (%s): %s"
                              % (method.method, e))
                    self._removeYumRepo(BASE_REPO_NAME)
                    raise PayloadSetupError("base repo is unusable")

            self._yumCacheDirHack()
            try:
                self._addYumRepo(BASE_REPO_NAME, url, mirrorlist=mirrorlist,
                                 proxyurl=method.proxy, sslverify=sslverify)
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

        proxy = repo.proxy or self.data.method.proxy
        sslverify = not (flags.noverifyssl or repo.noverifyssl)

        # this repo is already in ksdata, so we only add it to yum here
        self._addYumRepo(repo.name, url, repo.mirrorlist, cost=repo.cost,
                         exclude=repo.excludepkgs, includepkgs=repo.includepkgs,
                         proxyurl=proxy, sslverify=sslverify)

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

    def _addYumRepo(self, name, baseurl, mirrorlist=None, proxyurl=None, **kwargs):
        """ Add a yum repo to the YumBase instance. """
        from yum.Errors import RepoError

        # First, delete any pre-existing repo with the same name.
        with _yum_lock:
            if name in self._yum.repos.repos:
                self._yum.repos.delete(name)

        if proxyurl:
            try:
                proxy = ProxyString(proxyurl)
                kwargs["proxy"] = proxy.noauth_url
                if proxy.username:
                    kwargs["proxy_username"] = proxy.username
                if proxy.password:
                    kwargs["proxy_password"] = proxy.password
            except ProxyStringError as e:
                log.error("Failed to parse proxy for _addYumRepo %s: %s" \
                          % (proxyurl, e))

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
            # YUMFIXME: yum's instant policy doesn't work as advertised
            obj.mdpolicy = "meh"
            try:
                obj.repoXML
            except RepoError as e:
                raise MetadataError(e.value)

        # Adding a new repo means the cached packages and groups lists
        # are out of date.  Clear them out now so the next reference to
        # either will cause it to be regenerated.
        self._groups = None
        self._packages = []

    def addRepo(self, newrepo):
        """ Add a ksdata repo. """
        log.debug("adding new repo %s" % newrepo.name)
        self._addYumRepo(newrepo.name, newrepo.baseurl, newrepo.mirrorlist, newrepo.proxy)   # FIXME: handle MetadataError
        super(YumPayload, self).addRepo(newrepo)

    def _removeYumRepo(self, repo_id):
        if repo_id in self.repos:
            with _yum_lock:
                self._yum.repos.delete(repo_id)
                self._groups = None
                self._packages = []

    def removeRepo(self, repo_id):
        """ Remove a repo as specified by id. """
        log.debug("removing repo %s" % repo_id)

        # if this is an NFS repo, we'll want to unmount the NFS mount after
        # removing the repo
        mountpoint = None
        with _yum_lock:
            yum_repo = self._yum.repos.getRepo(repo_id)
            ks_repo = self.getRepo(repo_id)
            if yum_repo and ks_repo and ks_repo.baseurl.startswith("nfs:"):
                mountpoint = yum_repo.baseurl[0][7:]    # strip leading "file://"

        self._removeYumRepo(repo_id)
        super(YumPayload, self).removeRepo(repo_id)

        if mountpoint and os.path.ismount(mountpoint):
            try:
                isys.umount(mountpoint, removeDir=False)
            except SystemError as e:
                log.error("failed to unmount nfs repo %s: %s" % (mountpoint, e))

    def enableRepo(self, repo_id):
        """ Enable a repo as specified by id. """
        log.debug("enabling repo %s" % repo_id)
        if repo_id in self.repos:
            with _yum_lock:
                self._yum.repos.enableRepo(repo_id)

    def disableRepo(self, repo_id):
        """ Disable a repo as specified by id. """
        log.debug("disabling repo %s" % repo_id)
        if repo_id in self.repos:
            with _yum_lock:
                self._yum.repos.disableRepo(repo_id)

            self._groups = None
            self._packages = []

    ###
    ### METHODS FOR WORKING WITH ENVIRONMENTS
    ###
    @property
    def environments(self):
        """ List of environment ids. """
        from yum.Errors import RepoError
        from yum.Errors import GroupsError

        environments = []
        yum_groups = self._yumGroups
        if yum_groups:
            with _yum_lock:
                environments = [i.environmentid for i in yum_groups.get_environments()]

        return environments

    def environmentSelected(self, environmentid):
        groups = self._yumGroups
        if not groups:
            return False

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            for group in environment.groups:
                if not self.groupSelected(group):
                    return False
            return True

    def environmentHasOption(self, environmentid, grpid):
        groups = self._yumGroups
        if not groups:
            return False

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            if grpid in environment.options:
                return True
        return False

    def environmentDescription(self, environmentid):
        """ Return name/description tuple for the environment specified by id. """
        groups = self._yumGroups
        if not groups:
            return (environmentid, environmentid)

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)

            return (environment.ui_name, environment.ui_description)

    def selectEnvironment(self, environmentid):
        groups = self._yumGroups
        if not groups:
            return

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            for group in environment.groups:
                self.selectGroup(group)

    def deselectEnvironment(self, environmentid):
        groups = self._yumGroups
        if not groups:
            return

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            for group in environment.groups:
                self.deselectGroup(group)
            for group in environment.options:
                self.deselectGroup(group)

    def environmentGroups(self, environmentid):
        groups = self._yumGroups
        if not groups:
            return []

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            return environment.groups + environment.options

    ###
    ### METHODS FOR WORKING WITH GROUPS
    ###
    @property
    def _yumGroups(self):
        """ yum.comps.Comps instance. """
        from yum.Errors import RepoError, GroupsError
        with _yum_lock:
            if not self._groups:
                if not self.needsNetwork or hasActiveNetDev():
                    try:
                        self._groups = self._yum.comps
                    except (RepoError, GroupsError) as e:
                        log.error("failed to get group info: %s" % e)

        return self._groups

    @property
    def groups(self):
        """ List of group ids. """
        from yum.Errors import RepoError
        from yum.Errors import GroupsError

        groups = []
        yum_groups = self._yumGroups
        if yum_groups:
            with _yum_lock:
                groups = [g.groupid for g in yum_groups.get_groups()]

        return groups

    def languageGroups(self, lang):
        groups = []
        yum_groups = self._yumGroups

        if yum_groups:
            with _yum_lock:
                langs = expand_langs(lang)
                groups = map(lambda x: [g.groupid for g in
                             yum_groups.get_groups() if g.langonly == x],
                             langs)

        # the map gives us a list of results, this set call reduces
        # it down to a unique set, then list() makes it back into a list.
        return list(set(itertools.chain(*groups)))

    def groupDescription(self, groupid):
        """ Return name/description tuple for the group specified by id. """
        groups = self._yumGroups
        if not groups:
            return (groupid, groupid)

        with _yum_lock:
            if not groups.has_group(groupid):
                raise NoSuchGroup(groupid)

            group = groups.return_group(groupid)

            return (group.ui_name, group.ui_description)

    def _isGroupVisible(self, groupid):
        groups = self._yumGroups
        if not groups:
            return False

        with _yum_lock:
            if not groups.has_group(groupid):
                return False

            group = groups.return_group(groupid)
            return group.user_visible

    def _groupHasInstallableMembers(self, groupid):
        groups = self._yumGroups
        if not groups:
            return False

        with _yum_lock:
            if not groups.has_group(groupid):
                return False

            group = groups.return_group(groupid)
            pkgs = group.mandatory_packages.keys() + group.default_packages.keys()
            if pkgs:
                return True
            return False

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
                    log.error("failed to get package list: %s" % e)

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
        # XXX this will only be useful if you've run checkSoftwareSelection
        total = 0
        with _yum_lock:
            for txmbr in self._yum.tsInfo.getMembers():
                total += getattr(txmbr.po, "installedsize", 0)

        total += total * 0.35   # add 35% to account for the fact that the above
                                # method is laughably inaccurate
        self._space_required = Size(bytes=total)

        return self._space_required

    ###
    ### METHODS FOR INSTALLING THE PAYLOAD
    ###
    def _removeTxSaveFile(self):
        # remove the transaction save file
        with _yum_lock:
            if self._yum._ts_save_file:
                try:
                    os.unlink(self._yum._ts_save_file)
                except (OSError, IOError):
                    pass
                else:
                    self._yum._ts_save_file = None

    def _handleMissing(self, exn):
        if self.data.packages.handleMissing == KS_MISSING_IGNORE:
            return

        if errorHandler.cb(exn, str(exn)) == ERROR_RAISE:
            # The progress bar polls kind of slowly, thus installation could
            # still continue for a bit before the quit message is processed.
            # Doing a sys.exit also ensures the running thread quits before
            # it can do anything else.
            progress.send_quit(1)
            sys.exit(1)

    def _applyYumSelections(self):
        """ Apply the selections in ksdata to yum.

            This follows the same ordering/pattern as kickstart.py.
        """
        self._selectYumGroup("core")

        if self.data.packages.default and self.environments:
            self.selectEnvironment(self.environments[0])

        for package in self.data.packages.packageList:
            try:
                self._selectYumPackage(package)
            except NoSuchPackage as e:
                self._handleMissing(e)

        for group in self.data.packages.groupList:
            default = False
            optional = False
            if group.include == GROUP_DEFAULT:
                default = True
            elif group.include == GROUP_ALL:
                default = True
                optional = True

            try:
                self._selectYumGroup(group.name, default=default, optional=optional)
            except NoSuchGroup as e:
                self._handleMissing(e)

        for package in self.data.packages.excludedList:
            try:
                self._deselectYumPackage(package)
            except NoSuchPackage as e:
                self._handleMissing(e)

        for group in self.data.packages.excludedGroupList:
            try:
                self._deselectYumGroup(group.name)
            except NoSuchGroup as e:
                self._handleMissing(e)

        self.selectKernelPackage()
        self.selectRequiredPackages()

    def checkSoftwareSelection(self):
        log.info("checking software selection")
        self.txID = time.time()

        if self.skipBroken:
            log.info("running software check with skip_broken = True")
            with _yum_lock:
                self._yum.conf.skip_broken = True

        self.release()
        self.deleteYumTS()

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
        with _yum_lock:
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
                with _yum_lock:
                    if self._yum.tsInfo.matchNaevr(name="gcc"):
                        log.info("selecting %s-devel" % kernel)
                        # XXX might need explicit arch specification
                        self._selectYumPackage("%s-devel" % kernel)
                break

        if not selected:
            log.error("failed to select a kernel from %s" % kernels)

    def selectRequiredPackages(self):
        if self._requiredPackages:
            map(self._selectYumPackage, self._requiredPackages)

        if self._requiredGroups:
            map(self._selectYumGroup, self._requiredGroups)

    def preInstall(self, packages=None, groups=None):
        """ Perform pre-installation tasks. """
        super(YumPayload, self).preInstall()
        progress.send_message(_("Starting package installation process"))

        self._requiredPackages = packages
        self._requiredGroups = groups

        if self.install_device:
            self._setUpMedia(self.install_device)

        with _yum_lock:
            self._writeInstallConfig()

        # We have this block twice.  For kickstart installs, this is the only
        # place dependencies will be checked.  If a dependency error is hit
        # here, there's nothing the user can do about it since you cannot go
        # back to the first hub.
        try:
            self.checkSoftwareSelection()
        except DependencyError as e:
            if errorHandler.cb(e) == ERROR_RAISE:
                progress.send_quit(1)
                sys.exit(1)

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

        if flags.selinux:
            for d in ["/tmp/updates",
                      "/etc/selinux/targeted/contexts/files",
                      "/etc/security/selinux/src/policy",
                      "/etc/security/selinux"]:
                f = d + "/file_contexts"
                if os.access(f, os.R_OK):
                    rpm.addMacro("__file_context_path", f)
                    break
        else:
            rpm.addMacro("__file_context_path", "%{nil}")

    def _transactionErrors(self, errors):
        spaceNeeded = {}
        retval = ""

        # RPM can give us a bunch of potential errors, but we really only
        # care about a handful.
        for (descr, (ty, mount, need)) in errors:
            log.error(descr)

            if ty == rpm.RPMPROB_DISKSPACE:
                spaceNeeded[mount] = need

        # Now that we've found the ones we are interested in, create an
        # error string to match.
        if spaceNeeded:
            retval += _("You need more space on the following "
                        "file systems:\n")

            for (mount, need) in spaceNeeded.items():
                retval += "%s on %s\n" % (Size(need), mount)

        return retval

    def install(self):
        """ Install the payload. """
        from yum.Errors import PackageSackError, RepoError, YumBaseError, YumRPMTransError

        log.info("preparing transaction")
        log.debug("initialize transaction set")
        with _yum_lock:
            self._yum.initActionTs()

            if rpmUtils and rpmUtils.arch.isMultiLibArch():
                self._yum.ts.ts.setColor(3)

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

            # Write scriptlet output to a file to be logged later
            script_log = tempfile.NamedTemporaryFile(delete=False)
            self._yum.ts.ts.scriptFd = script_log.fileno()
            rpm.setLogFile(script_log)

            # create the install callback
            rpmcb = RPMCallback(self._yum, script_log,
                                upgrade=self.data.upgrade.upgrade)

            if flags.testing:
                self._yum.ts.setFlags(rpm.RPMTRANS_FLAG_TEST)

            log.info("running transaction")
            progress.send_step()
            try:
                self._yum.runTransaction(cb=rpmcb)
            except PackageSackError as e:
                log.error("error [1] running transaction: %s" % e)
                exn = PayloadInstallError(str(e))
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn
            except YumRPMTransError as e:
                log.error("error [2] running transaction: %s" % e)
                exn = PayloadInstallError(self._transactionErrors(e.errors))
                if errorHandler.cb(exn) == ERROR_RAISE:
                    progress.send_quit(1)
                    sys.exit(1)
            except YumBaseError as e:
                log.error("error [3] running transaction: %s" % e)
                for error in e.errors:
                    log.error("%s" % error[0])
                exn = PayloadInstallError(str(e))
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn
            else:
                log.info("transaction complete")
                progress.send_step()
            finally:
                self._yum.ts.close()
                iutil.resetRpmDb()
                script_log.close()

                # log the contents of the scriptlet logfile
                log.info("==== start rpm scriptlet logs ====")
                with open(script_log.name) as f:
                    for l in f:
                        log.info(l)
                log.info("==== end rpm scriptlet logs ====")
                os.unlink(script_log.name)

    def writeMultiLibConfig(self):
        if not self.data.packages.multiLib:
            return

        # write out the yum config with the new multilib_policy value
        # FIXME: switch to using yum-config-manager once it stops expanding
        #        all yumvars and writing out the expanded pairs to the conf
        yb = yum.YumBase()
        yum_conf_path = "/etc/yum.conf"
        yb.preconf.fn = ROOT_PATH + yum_conf_path
        yb.conf.multilib_policy = "all"

        # this will appear in yum.conf, which is silly
        yb.conf.config_file_path = yum_conf_path

        # hack around yum having expanded $basearch in the cachedir value
        cachedir = yb.conf.cachedir.replace("/%s/" % yb.arch.basearch,
                                            "/$basearch/")
        yb.conf.cachedir = cachedir
        yum_conf = ROOT_PATH + yum_conf_path
        if os.path.exists(yum_conf):
            try:
                os.rename(yum_conf, yum_conf + ".anacbak")
            except OSError as e:
                log.error("failed to back up yum.conf: %s" % e)

        try:
            yb.conf.write(open(yum_conf, "w"))
        except Exception as e:
            log.error("failed to write out yum.conf: %s" % e)

    def postInstall(self):
        """ Perform post-installation tasks. """
        with _yum_lock:
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

        self.writeMultiLibConfig()

        super(YumPayload, self).postInstall()

class RPMCallback(object):
    def __init__(self, yb, log, upgrade=False):
        self._yum = yb              # yum.YumBase
        self.install_log = log      # logfile for yum script logs
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
                log.info(log_msg)
                self.install_log.write(log_msg+"\n")
                self.install_log.flush()

                progress.send_message(progress_msg)

            self.package_file = None
            repo = self._yum.repos.getRepo(txmbr.po.repoid)

            while self.package_file is None:
                try:
                    # checkfunc gets passed to yum's use of URLGrabber which
                    # then calls it with the file being fetched. verifyPkg
                    # makes sure the checksum matches the one in the metadata.
                    #
                    # From the URLGrab documents:
                    # checkfunc=(function, ('arg1', 2), {'kwarg': 3})
                    # results in a callback like:
                    #   function(obj, 'arg1', 2, kwarg=3)
                    #     obj.filename = '/tmp/stuff'
                    #     obj.url = 'http://foo.com/stuff'
                    checkfunc = (self._yum.verifyPkg, (txmbr.po, 1), {})
                    package_path = repo.getPackage(txmbr.po, checkfunc=checkfunc)
                except URLGrabError as e:
                    log.error("URLGrabError: %s" % (e,))
                    exn = PayloadInstallError("failed to get package")
                    if errorHandler.cb(exn, package=txmbr.po) == ERROR_RAISE:
                        raise exn
                except (yum.Errors.NoMoreMirrorsRepoError, IOError):
                    if os.path.exists(txmbr.po.localPkg()):
                        os.unlink(txmbr.po.localPkg())
                        log.debug("retrying download of %s" % txmbr.po)
                        continue
                    exn = PayloadInstallError("failed to open package")
                    if errorHandler.cb(exn, package=txmbr.po) == ERROR_RAISE:
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

            # rpm doesn't tell us when it's started post-trans stuff which can
            # take a very long time.  So when it closes the last package, just
            # display the message.
            if self.completed_actions == self.total_actions:
                progress.send_message(_("Performing post-install setup tasks"))
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
                if errorHandler.cb(exn, package=name) == ERROR_RAISE:
                    raise exn
