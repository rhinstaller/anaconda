#
# backend.py: Interface for installation backends
#
# Paul Nasrat <pnasrat@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright (c) 2005-2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import shutil
import iutil
import os, sys
import logging
from syslogd import syslog

from rhpl.translate import _

from flags import flags
from fsset import devify
log = logging.getLogger("anaconda")


class AnacondaBackend:
    def __init__(self, method, instPath):
        """Abstract backend class all backends should inherit from this
           @param method: Object of InstallMethod type
           @param instPath: root path for the installation to occur"""

        self.method = method
        self.instPath = instPath
        self.instLog = None
        self.modeText = ""

    def doPreSelection(self, intf, id, instPath):
        pass

    def doPostSelection(self, anaconda):
        pass

    def doPreInstall(self, anaconda):
        pass

    def copyFirmware(self, anaconda):
        import glob, shutil

        # Multiple driver disks may be loaded, so we need to glob for all
        # the firmware files in all the driver disk directories.
        for f in glob.glob("/tmp/ramfs/DD-*/firmware/*"):
            try:
                fn = f.split('/')[-1]
                shutil.copyfile(f, "%s/lib/firmware/%s" % (anaconda.rootPath, fn))
            except IOError, e:
                log.error("Could not copy firmware file %s: %s" % (f, e.strerror))

    def doPostInstall(self, anaconda):
        self.copyFirmware(anaconda)

        sys.stdout.flush()
        if flags.setupFilesystems:
            syslog.stop()

    def doInstall(self, anaconda):
        pass

    def initLog(self, id, instPath):
        upgrade = id.getUpgrade()

        if upgrade:
            logname = '/root/upgrade.log'
        else:
            logname = '/root/install.log'

        instLogName = instPath + logname
        try:
            shutil.rmtree (instLogName)
        except OSError:
            pass

        instLog = open(instLogName, "w+")
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

    def kernelVersionList(self):
        pass

    def doInitialSetup(self, anaconda):
        pass

    def doRepoSetup(self, anaconda):
        log.warning("doRepoSetup not implemented for backend!")
        pass

    def groupExists(self, group):
        log.warning("groupExists not implemented for backend!")
        pass

    def selectGroup(self, group, *args):
        log.warning("selectGroup not implemented for backend!")
        pass

    def deselectGroup(self, group, *args):
        log.warning("deselectGroup not implemented for backend!")
        pass

    def packageExists(self, pkg):
        log.warning("packageExists not implemented for backend!")
        pass
    
    def selectPackage(self, pkg, *args):
        log.warning("selectPackage not implemented for backend!")
        pass

    def deselectPackage(self, pkg, *args):
        log.warning("deselectPackage not implemented for backend!")
        pass

    def removeGroupsPackages(self, grp, *args):
        log.warning("removeGroupsPackages not implemented for backend!")
        pass

    def getDefaultGroups(self, anaconda):
        log.warning("getDefaultGroups not implemented for backend!")
        pass

    # write out the %packages section of anaconda-ks.cfg
    def writePackagesKS(self, f, anaconda):
        log.warning("writePackagesKS not implemented for backend!")
        pass

    # write out any config files that live on the installed system
    # (e.g., /etc/yum.repos.d/* files)
    def writeConfiguration(self):
        log.warning("writeConfig not implemented for backend!")
        pass

    # write out any other kickstart bits the backend requires - no warning
    # here because this may not be needed
    def writeKS(self, f):
        pass

def doRepoSetup(anaconda):
    anaconda.backend.doInitialSetup(anaconda)
    anaconda.backend.doRepoSetup(anaconda)
    if anaconda.id.upgrade:
        anaconda.backend.checkSupportedUpgrade(anaconda)

def doPostSelection(anaconda):
    return anaconda.backend.doPostSelection(anaconda)

def doPreInstall(anaconda):
    anaconda.backend.doPreInstall(anaconda)

def doPostInstall(anaconda):
    anaconda.backend.doPostInstall(anaconda)

def doInstall(anaconda):
    anaconda.backend.doInstall(anaconda)

# does this need to be per-backend?  we'll just leave here until it does :)
def doBasePackageSelect(anaconda):
    anaconda.id.instClass.setPackageSelection(anaconda)
    anaconda.id.instClass.setGroupSelection(anaconda)

def writeConfiguration(anaconda):
    log.info("Writing main configuration")
    if not flags.test:
        anaconda.backend.writeConfiguration()
        anaconda.id.write()
   
