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

import kickstart
import packages
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

        # some backends may not support upgrading
        self.supportsUpgrades = True
        self.supportsPackageSelection = False

    def doPreSelection(self, intf, id, instPath):
        pass

    def doPostSelection(self, anaconda):
        pass

    def doPreInstall(self, anaconda):
        self.initLog(anaconda.id, anaconda.rootPath)        

    def copyDriverDiskModules(self, anaconda):
        """Copy over modules from a driver disk."""
        kernelVersions = self.kernelVersionList()
        foundModule = 0

        try:
            f = open("/etc/arch")
            arch = f.readline().strip()
            del f
        except IOError:
            arch = os.uname()[2]

        for (path, name) in anaconda.id.extraModules:
            if not path:
                path = "/modules.cgz"
            pattern = ""
            names = ""
            for (n, arch, tag) in kernelVersions:
                if tag == "base":
                    pkg = "kernel"
                else:
                    pkg = "kernel-%s" %(tag,)

                # version 1 path
                pattern = pattern + " %s/%s/%s.ko " % (n, arch, name)
                # version 0 path
                pattern = pattern + " %s/%s.ko " % (n, name)
                names = names + " %s.ko" % (name,)
            command = ("cd %s/lib/modules; gunzip < %s | "
                       "%s/bin/cpio --quiet -iumd %s" % 
                       (anaconda.rootPath, path, anaconda.rootPath, pattern))
            log.info("running: '%s'" % (command, ))
            os.system(command)

            for (n, arch, tag) in kernelVersions:
                if tag == "base":
                    pkg = "kernel"
                else:
                    pkg = "kernel-%s" %(tag,)
                
                toDir = "%s/lib/modules/%s/updates" % \
                        (anaconda.rootPath, n)
                to = "%s/%s.ko" % (toDir, name)

                if (os.path.isdir("%s/lib/modules/%s" %(anaconda.rootPath, n)) and not
                    os.path.isdir("%s/lib/modules/%s/updates" %(anaconda.rootPath, n))):
                    os.mkdir("%s/lib/modules/%s/updates" %(anaconda.rootPath, n))
                if not os.path.isdir(toDir):
                    continue

                for p in ("%s/%s.ko" %(arch, name), "%s.ko" %(name,)):
                    fromFile = "%s/lib/modules/%s/%s" % (anaconda.rootPath, n, p)

                    if (os.access(fromFile, os.R_OK)):
                        log.info("moving %s to %s" % (fromFile, to))
                        os.rename(fromFile, to)
                        # the file might not have been owned by root in the cgz
                        os.chown(to, 0, 0)
                        foundModule = 1
                    else:
                        log.warning("missing DD module %s (this may be okay)" % 
                            fromFile)

        if foundModule == 1:
            for (n, arch, tag) in kernelVersions:
                packages.recreateInitrd(n, anaconda.rootPath)

    def doPostInstall(self, anaconda):
        self.copyDriverDiskModules(anaconda)

        sys.stdout.flush()
        if flags.setupFilesystems:
            syslog.stop()

    def doInstall(self, anaconda):
        log.warning("doInstall not implemented for backend!")        
        pass

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
        return []

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

    def getDefaultGroups(self, anaconda):
        log.warning("getDefaultGroups not implemented for backend!")
        pass

    def writePackagesKS(self, f):
        log.warning("writePackagesKS not implemented for backend!")
        pass

    def writeConfiguration(self):
        log.warning("writeConfig not implemented for backend!")
        pass

    def getRequiredMedia(self):
        log.warning("getRequiredMedia not implmented for backend!")
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
    if anaconda.isKickstart:
        kickstart.selectPackages(anaconda)
    else:
        anaconda.id.instClass.setPackageSelection(anaconda)
        anaconda.id.instClass.setGroupSelection(anaconda)

def writeConfiguration(anaconda):
    log.info("Writing main configuration")
    if not flags.test:
        anaconda.id.write(anaconda)
        anaconda.backend.writeConfiguration()
   
