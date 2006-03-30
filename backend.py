#
# backend.py: Interface for installation backends
#
# Paul Nasrat <pnasrat@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright (c) 2005 Red Hat, Inc.
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

    def doPostSelection(self, intf, id, instPath, dir):
        pass

    def doPreInstall(self, intf, id, instPath, dir):
        pass

    def doPostInstall(self, intf, id, instPath):
        sys.stdout.flush()
        if flags.setupFilesystems:
            syslog.stop()

    def doInstall(self, intf, id, instPath):
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
            self.modeText = _("Upgrading %s-%s-%s.%s.\n")
        else:
            self.modeText = _("Installing %s-%s-%s.%s.\n")

    def kernelVersionList(self):
        pass

    def doInitialSetup(self, id, instPath):
        pass

    def doRepoSetup(self, intf, instPath):
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

    def getDefaultGroups(self):
        log.warning("getDefaultGroups not implemented for backend!")
        pass

    def writePackagesKS(self, f):
        log.warning("writePackagesKS not implemented for backend!")
        pass

    def writeConfiguration(self):
        log.warning("writeConfig not implemented for backend!")
        pass

def doRepoSetup(backend, intf, id, instPath):
    backend.doInitialSetup(id, instPath)
    backend.doRepoSetup(intf, instPath)
    if id.upgrade:
        backend.checkSupportedUpgrade(intf, instPath)

def doPostSelection(backend, intf, id, instPath, dir):
    return backend.doPostSelection(intf, id, instPath, dir)

def doPreInstall(backend, intf, id, instPath, dir):
    backend.doPreInstall(intf, id, instPath, dir)

def doPostInstall(backend, intf, id, instPath):
    backend.doPostInstall(intf, id, instPath)

def doInstall(backend, intf, id, instPath):
    backend.doInstall(intf, id, instPath)

# does this need to be per-backend?  we'll just leave here until it does :)
def doBasePackageSelect(backend, instClass, intf):
    instClass.setPackageSelection(backend, intf)
    instClass.setGroupSelection(backend, intf)

def writeConfiguration(backend, id, instPath):
    log.info("Writing main configuration")
    if not flags.test:
        backend.writeConfiguration()
        id.write(instPath)
   
