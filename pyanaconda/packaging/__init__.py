# __init__.py
# Entry point for anaconda's software management module.
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

"""

import os
from urlgrabber.grabber import URLGrabber
from urlgrabber.grabber import URLGrabError
import ConfigParser
import shutil
import time

if __name__ == "__main__":
    from pyanaconda import anaconda_log
    anaconda_log.init()

from pyanaconda.constants import *
from pyanaconda.flags import flags

from pyanaconda import iutil
from pyanaconda.network import hasActiveNetDev

from pykickstart.parser import Group

import logging
log = logging.getLogger("anaconda")

from pyanaconda.backend_log import log as instlog

from pyanaconda.errors import *
#from pyanaconda.progress import progress

###
### ERROR HANDLING
###
class PayloadError(Exception):
    pass

class MetadataError(PayloadError):
    pass

class NoNetworkError(PayloadError):
    pass

# setup
class PayloadSetupError(PayloadError):
    pass

class ImageMissingError(PayloadSetupError):
    pass

class ImageDirectoryMountError(PayloadSetupError):
    pass

# software selection
class NoSuchGroup(PayloadError):
    pass

class NoSuchPackage(PayloadError):
    pass

class DependencyError(PayloadError):
    pass

# installation
class PayloadInstallError(PayloadError):
    pass


def get_mount_device(mountpoint):
    import re
    mounts = open("/proc/mounts").readlines()
    mount_device = None
    for mount in mounts:
        try:
            (device, path, rest) = mount.split(None, 2)
        except ValueError:
            continue

        if path == mountpoint:
            mount_device = device
            break

    if mount_device and re.match(r'/dev/loop\d+$', mount_device):
        from pyanaconda.storage.devicelibs import loop
        loop_name = os.path.basename(mount_device)
        mount_device = loop.get_backing_file(loop_name)
        log.debug("found backing file %s for loop device %s" % (mount_device,
                                                                loop_name))

    log.debug("%s is mounted on %s" % (mount_device, mountpoint))
    return mount_device

class Payload(object):
    """ Payload is an abstract class for OS install delivery methods. """
    def __init__(self, data):
        self.data = data

    def setup(self, storage):
        """ Do any payload-specific setup. """
        raise NotImplementedError()

    def release(self):
        """ Release any resources in use by this object, but do not do final
            cleanup.  This is useful for dealing with payload backends that do
            not get along well with multithreaded programs.
        """
        pass

    def reset(self):
        """ Reset the instance, not including ksdata. """
        pass

    ###
    ### METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def repos(self):
        """A list of repo identifiers, not objects themselves."""
        raise NotImplementedError()

    @property
    def addOns(self):
        """ A list of addon repo identifiers. """
        return []

    @property
    def baseRepo(self):
        """ The identifier of the current base repo. """
        return None

    def getRepo(self, repo_id):
        """ Return a ksdata Repo instance matching the specified repo id. """
        repo = None
        for r in self.data.repo.dataList():
            if r.name == repo_id:
                repo = r
                break

        return repo

    def updateBaseRepo(self, storage):
        """ Update the base repository from ksdata.method. """
        pass

    def configureAddOnRepo(self, repo):
        """ Set up an addon repo as defined in ksdata Repo repo. """
        pass

    def addRepo(self, newrepo):
        """Add the repo given by the pykickstart Repo object newrepo to the
           system.  The repo will be automatically enabled and its metadata
           fetched.

           Duplicate repos will not raise an error.  They should just silently
           take the place of the previous value.
        """
        # Add the repo to the ksdata so it'll appear in the output ks file.
        self.data.repo.dataList().append(newrepo)

    def removeRepo(self, repo_id):
        repos = self.data.repo.dataList()
        try:
            idx = [repo.name for repo in repos].index(repo_id)
        except ValueError:
            log.error("failed to remove repo %s: not found" % repo_id)
        else:
            repos.pop(idx)

    def enableRepo(self, repo_id):
        raise NotImplementedError()

    def disableRepo(self, repo_id):
        raise NotImplementedError()

    ###
    ### METHODS FOR WORKING WITH GROUPS
    ###
    @property
    def groups(self):
        raise NotImplementedError()

    def description(self, groupid):
        raise NotImplementedError()

    def groupSelected(self, groupid):
        return Group(groupid) in self.data.packages.groupList

    def selectGroup(self, groupid, default=True, optional=False):
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

    def deselectGroup(self, groupid):
        grp = Group(groupid)

        if grp in self.data.packages.excludedGroupList:
            return

        if grp in self.data.packages.groupList:
            self.data.packages.groupList.remove(grp)

        self.data.packages.excludedGroupList.append(grp)

    ###
    ### METHODS FOR WORKING WITH PACKAGES
    ###
    @property
    def packages(self):
        raise NotImplementedError()

    def packageSelected(self, pkgid):
        return pkgid in self.data.packages.packageList

    def selectPackage(self, pkgid):
        """Mark a package for installation.

           pkgid - The name of a package to be installed.  This could include
                   a version or architecture component.
        """
        if pkgid in self.data.packages.packageList:
            return

        if pkgid in self.data.packages.excludedList:
            self.data.packages.excludedList.remove(pkgid)

        self.data.packages.packageList.append(pkgid)

    def deselectPackage(self, pkgid):
        """Mark a package to be excluded from installation.

           pkgid - The name of a package to be excluded.  This could include
                   a version or architecture component.
        """
        if pkgid in self.data.packages.excludedList:
            return

        if pkgid in self.data.packages.packageList:
            self.data.packages.packageList.remove(pkgid)

        self.data.packages.excludedList.append(pkgid)

    ###
    ### METHODS FOR QUERYING STATE
    ###
    @property
    def spaceRequired(self):
        raise NotImplementedError()

    @property
    def kernelVersionList(self):
        raise NotImplementedError()

    ##
    ## METHODS FOR TREE VERIFICATION
    ##
    def _getTreeInfo(self, url, sslverify, proxies):
        """ Retrieve treeinfo and return the path to the local file. """
        if not url:
            return None

        log.debug("retrieving treeinfo from %s (proxies: %s ; sslverify: %s)"
                    % (url, proxies, sslverify))

        ugopts = {"ssl_verify_peer": sslverify,
                  "ssl_verify_host": sslverify}

        ug = URLGrabber()
        try:
            treeinfo = ug.urlgrab("%s/.treeinfo" % url,
                                  "/tmp/.treeinfo", copy_local=True,
                                  proxies=proxies, **ugopts)
        except URLGrabError as e:
            try:
                treeinfo = ug.urlgrab("%s/treeinfo" % url,
                                      "/tmp/.treeinfo", copy_local=True,
                                      proxies=proxies, **ugopts)
            except URLGrabError as e:
                log.info("Error downloading treeinfo: %s" % e)
                treeinfo = None

        return treeinfo

    def _getReleaseVersion(self, url):
        """ Return the release version of the tree at the specified URL. """
        version = productVersion.split("-")[0]

        log.debug("getting release version from tree at %s (%s)" % (url,
                                                                    version))

        proxies = {}
        if self.proxy:
            proxies = {"http": self.proxy,
                       "https": self.proxy}

        treeinfo = self._getTreeInfo(url, not flags.noverifyssl, proxies)
        if treeinfo:
            c = ConfigParser.ConfigParser()
            c.read(treeinfo)
            try:
                # Trim off any -Alpha or -Beta
                version = c.get("general", "version").split("-")[0]
            except ConfigParser.Error:
                pass

        log.debug("got a release version of %s" % version)
        return version

    ##
    ## METHODS FOR MEDIA MANAGEMENT (XXX should these go in another module?)
    ##
    def _setupDevice(self, device, mountpoint):
        """ Prepare an install CD/DVD for use as a package source. """
        log.info("setting up device %s and mounting on %s" % (device.name,
                                                              mountpoint))
        if os.path.ismount(mountpoint):
            mdev = get_mount_device(mountpoint)
            log.warning("%s is already mounted on %s" % (mdev, mountpoint))
            if mdev == device.path:
                return
            else:
                log.info("mounting on top of it")

        try:
            device.setup()
            device.format.setup(mountpoint=mountpoint)
        except StorageError as e:
            log.error("mount failed: %s" % e)
            exn = PayloadSetupError(str(e))
            if errorHandler.cb(exn) == ERROR_RAISE:
                device.teardown(recursive=True)
                raise exn

    def _setupNFS(self, mountpoint, server, path, options):
        """ Prepare an NFS directory for use as a package source. """
        log.info("mounting %s:%s:%s on %s" % (server, path, options, mountpoint))
        if os.path.ismount(mountpoint):
            log.debug("%s already has something mounted on it" % mountpoint)
            return

        # mount the specified directory
        url = "%s:%s" % (server, path)

        try:
            isys.mount(url, mountpoint, options=options)
        except SystemError as e:
            log.error("mount failed: %s" % e)
            exn = PayloadSetupError(str(e))
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

    ###
    ### METHODS FOR INSTALLING THE PAYLOAD
    ###
    def preInstall(self):
        """ Perform pre-installation tasks. """
        # XXX this should be handled already
        iutil.mkdirChain(ROOT_PATH + "/root")

        if self.data.upgrade.upgrade:
            mode = "upgrade"
        else:
            mode = "install"

        log_file_name = "%s.log" % mode
        log_file_path = "%s/root/%s" % (ROOT_PATH, log_file_name)
        try:
            shutil.rmtree (log_file_path)
        except OSError:
            pass

        self.install_log = open(log_file_path, "w+")

        syslogname = "%s%s.syslog" % log_file_path
        try:
            shutil.rmtree (syslogname)
        except OSError:
            pass
        instlog.start(ROOT_PATH, syslogname)

    def install(self):
        """ Install the payload. """
        raise NotImplementedError()

    def postInstall(self):
        """ Perform post-installation tasks. """
        pass

        # set default runlevel/target (?)
        # write out static config (storage, modprobe, keyboard, ??)
        #   kickstart should handle this before we get here
        # copy firmware
        # recreate initrd
        #   postInstall or bootloader.install
        # copy dd rpms (yum/rpm only?)
        #   kickstart
        # copy dd modules and firmware (yum/rpm only?)
        #   kickstart
        # write escrow packets
        # stop logger

class ImagePayload(Payload):
    """ An ImagePayload installs an OS image to the target system. """
    def __init__(self, data):
        super(ImagePayload, self).__init__(data)
        self.image_file = None

    def setup(self, storage):
        if not self.image_file:
            exn = PayloadSetupError("image file not set")
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

class ArchivePayload(ImagePayload):
    """ An ArchivePayload unpacks source archives onto the target system. """
    pass

class PackagePayload(Payload):
    """ A PackagePayload installs a set of packages onto the target system. """
    pass

def payloadInitialize(storage, ksdata, payload):
    from pyanaconda.kickstart import selectPackages
    from pyanaconda.threads import threadMgr

    storageThread = threadMgr.get("AnaStorageThread")
    if storageThread:
        storageThread.join()

    payload.setup(storage)

    # And now that we've set up the payload, we need to apply any kickstart
    # selections.  This could include defaults from an install class.
    selectPackages(ksdata, payload)

def show_groups(payload):
    #repo = ksdata.RepoData(name="anaconda", baseurl="http://cannonball/install/rawhide/os/")
    #obj.addRepo(repo)

    desktops = []
    addons = []

    for grp in payload.groups:
        if grp.endswith("-desktop"):
            desktops.append(payload.description(grp))
        elif not grp.endswith("-support"):
            addons.append(payload.description(grp))

    import pprint

    print "==== DESKTOPS ===="
    pprint.pprint(desktops)
    print "==== ADDONS ===="
    pprint.pprint(addons)

    print payload.groups

def print_txmbrs(payload, f=None):
    if f is None:
        f = sys.stdout

    print >> f, "###########"
    for txmbr in payload._yum.tsInfo.getMembers():
        print >> f, txmbr
    print >> f, "###########"

def write_txmbrs(payload, filename):
    if os.path.exists(filename):
        os.unlink(filename)

    f = open(filename, 'w')
    print_txmbrs(payload, f)
    f.close()

###
### MAIN
###
if __name__ == "__main__":
    import os
    import sys
    import pyanaconda.storage as _storage
    import pyanaconda.platform as _platform
    from pykickstart.version import makeVersion
    from pyanaconda.packaging.yumpayload import YumPayload

    # set some things specially since we're just testing
    flags.testing = True

    # set up ksdata
    ksdata = makeVersion()

    #ksdata.method.method = "url"
    #ksdata.method.url = "http://husky/install/f17/os/"
    #ksdata.method.url = "http://dl.fedoraproject.org/pub/fedora/linux/development/17/x86_64/os/"

    # set up storage and platform
    platform = _platform.getPlatform()
    storage = _storage.Storage(data=ksdata, platform=platform)
    storage.reset()

    # set up the payload
    payload = YumPayload(ksdata)
    payload.setup(storage)

    for repo in payload._yum.repos.repos.values():
        print repo.name, repo.enabled

    ksdata.method.method = "url"
    #ksdata.method.url = "http://husky/install/f17/os/"
    ksdata.method.url = "http://dl.fedoraproject.org/pub/fedora/linux/development/17/x86_64/os/"

    # now switch the base repo to what we set ksdata.method to just above
    payload.updateBaseRepo(storage)
    for repo in payload._yum.repos.repos.values():
        print repo.name, repo.enabled

    # list all of the groups
    show_groups(payload)
