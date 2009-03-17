#
# backend.py: Interface for installation backends
#
# Copyright (C) 2005, 2006, 2007  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Paul Nasrat <pnasrat@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#

import glob
import shutil
import iutil
import os, sys
import logging
from syslogd import syslog
from constants import *

import isys
import kickstart
import packages

from flags import flags
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class AnacondaBackend:
    def __init__(self, anaconda):
        """Abstract backend class all backends should inherit from this
           @param instPath: root path for the installation to occur"""

        self.instPath = anaconda.rootPath
        self.instLog = None
        self.modeText = ""

        # some backends may not support upgrading
        self.supportsUpgrades = True
        self.supportsPackageSelection = False

        # some backends may have a special case for rootfs formatting
        # FIXME: we should handle this a little more elegantly
        self.skipFormatRoot = False

        self._loopbackFile = None

    def postAction(self, anaconda):
        pass

    def doPreSelection(self, intf, id, instPath):
        pass

    def doPostSelection(self, anaconda):
        pass

    def doPreInstall(self, anaconda):
        self.initLog(anaconda.id, anaconda.rootPath)

    def copyFirmware(self, anaconda):
        # Multiple driver disks may be loaded, so we need to glob for all
        # the firmware files in all the driver disk directories.
        for f in glob.glob("/tmp/DD-*/firmware/*"):
            try:
                shutil.copyfile(f, "%s/lib/firmware/" % anaconda.rootPath)
            except IOError, e:
                log.error("Could not copy firmware file %s: %s" % (f, e.strerror))

    def doPostInstall(self, anaconda):
        has_iscsi_disk = False

        # See if we have an iscsi disk. If we do we rerun mkinitrd, as
        # the initrd might need iscsi-initiator-utils, and chances are
        # it was not installed yet the first time mkinitrd was run, as
        # mkinitrd does not require it.
        root = anaconda.id.storage.fsset.rootDevice
        disks = anaconda.id.storage.devicetree.getDevicesByType("iscsi")
        for disk in disks:
            if root.dependsOn(disk):
                has_iscsi_disk = True
                break

        if anaconda.id.extraModules:
            self.copyFirmware(anaconda)

        if anaconda.id.extraModules or has_iscsi_disk:
            for (n, arch, tag) in self.kernelVersionList(anaconda.rootPath):
                packages.recreateInitrd(n, anaconda.rootPath)

        for d in glob.glob("/tmp/DD-*"):
            shutil.copytree(d, "/root/" + os.path.basename(d))

        sys.stdout.flush()
        if flags.setupFilesystems:
            syslog.stop()

    def doInstall(self, anaconda):
        log.warning("doInstall not implemented for backend!")
        raise NotImplementedError

    def initLog(self, id, instPath):
        upgrade = id.getUpgrade()

        if not os.path.isdir(instPath + "/root"):
            iutil.mkdirChain(instPath + "/root")

        if upgrade:
            logname = '/root/upgrade.log'
        else:
            logname = '/root/install.log'

        instLogName = instPath + logname
        try:
            shutil.rmtree (instLogName)
        except OSError:
            pass

        self.instLog = open(instLogName, "w+")

       # dont start syslogd if we arent creating filesystems
        if flags.setupFilesystems:
            syslogname = "%s%s.syslog" % (instPath, logname)
            try:
                shutil.rmtree (syslogname)
            except OSError:
                pass
            syslog.start (instPath, syslogname)
        else:
            syslogname = None

        if upgrade:
            self.modeText = _("Upgrading %s\n")
        else:
            self.modeText = _("Installing %s\n")

    def mountInstallImage(self, anaconda, installimg):
        if not flags.setupFilesystems:
            return

        if self._loopbackFile and os.path.exists(self._loopbackFile):
            return

        # If we've booted off the first CD/DVD (so, not the boot.iso) then
        # copy the install.img to the filesystem and switch loopback devices
        # to there.  Otherwise we won't be able to unmount and swap media.
        if not anaconda.mediaDevice or not os.path.exists(installimg):
            return

        free = anaconda.id.storage.fsset.fsFreeSpace(anaconda.rootPath)
        self._loopbackFile = "%s%s/rhinstall-install.img" % (anaconda.rootPath,
                                                             free[0][0])

        try:
            win = anaconda.intf.waitWindow(_("Copying File"),
                    _("Transferring install image to hard drive..."))
            shutil.copyfile(installimg, self._loopbackFile)
            win.pop()
        except Exception, e:
            if win:
                win.pop()

            log.critical("error transferring install.img: %s" %(e,))

            if isinstance(e, IOError) and e.errno == 5:
                msg = _("An error occurred transferring the install image "
                        "to your hard drive.  This is probably due to "
                        "bad media.")
            else:
                msg = _("An error occurred transferring the install image "
                        "to your hard drive. You are probably out of disk "
                        "space.")

            anaconda.intf.messageWindow(_("Error"), msg)
            try:
                os.unlink(self._loopbackFile)
            except:
                pass

            return 1

        isys.lochangefd("/dev/loop0", self._loopbackFile)
        isys.umount("/mnt/stage2")

    def removeInstallImage(self):
        if self._loopbackFile:
            try:
                os.unlink(self._loopbackFile)
            except SystemError:
                pass

    def kernelVersionList(self, rootPath="/"):
        return []

    def getMinimumSizeMB(self, part):
        """Return the minimal size for part in megabytes if we can."""
        return 0

    def doBackendSetup(self, anaconda):
        log.warning("doBackendSetup not implemented for backend!")
        raise NotImplementedError

    def groupExists(self, group):
        log.warning("groupExists not implemented for backend!")
        raise NotImplementedError

    def selectGroup(self, group, *args):
        log.warning("selectGroup not implemented for backend!")
        raise NotImplementedError

    def deselectGroup(self, group, *args):
        log.warning("deselectGroup not implemented for backend!")
        raise NotImplementedError

    def packageExists(self, pkg):
        log.warning("packageExists not implemented for backend!")
        raise NotImplementedError
    
    def selectPackage(self, pkg, *args):
        log.warning("selectPackage not implemented for backend!")
        raise NotImplementedError

    def deselectPackage(self, pkg, *args):
        log.warning("deselectPackage not implemented for backend!")
        raise NotImplementedError

    def getDefaultGroups(self, anaconda):
        log.warning("getDefaultGroups not implemented for backend!")
        raise NotImplementedError

    def resetPackageSelections(self):
        # we just leave this one unimplemented if it's not needed
        pass

    # write out the %packages section of anaconda-ks.cfg
    def writePackagesKS(self, f, anaconda):
        log.warning("writePackagesKS not implemented for backend!")
        raise NotImplementedError

    # write out any config files that live on the installed system
    # (e.g., /etc/yum.repos.d/* files)
    def writeConfiguration(self):
        log.warning("writeConfig not implemented for backend!")
        raise NotImplementedError

    # write out any other kickstart bits the backend requires - no warning
    # here because this may not be needed
    def writeKS(self, f):
        pass

    def getRequiredMedia(self):
        log.warning("getRequiredMedia not implmented for backend!")
        raise NotImplementedError

    def complete(self, anaconda):
        pass

def doBackendSetup(anaconda):
    if anaconda.backend.doBackendSetup(anaconda) == DISPATCH_BACK:
        return DISPATCH_BACK

    if anaconda.id.upgrade:
        anaconda.backend.checkSupportedUpgrade(anaconda)
        iutil.writeRpmPlatform(anaconda.rootPath)

def doPostSelection(anaconda):
    return anaconda.backend.doPostSelection(anaconda)

def doPreInstall(anaconda):
    anaconda.backend.doPreInstall(anaconda)

def doPostInstall(anaconda):
    anaconda.backend.doPostInstall(anaconda)

def doInstall(anaconda):
    return anaconda.backend.doInstall(anaconda)

# does this need to be per-backend?  we'll just leave here until it does :)
def doBasePackageSelect(anaconda):
    anaconda.backend.resetPackageSelections()
    if anaconda.isKickstart:
        kickstart.selectPackages(anaconda)
    else:
        anaconda.id.instClass.setPackageSelection(anaconda)
        anaconda.id.instClass.setGroupSelection(anaconda)

def writeConfiguration(anaconda):
    log.info("Writing main configuration")
    if not flags.test:
        anaconda.id.write()
        anaconda.backend.writeConfiguration()
