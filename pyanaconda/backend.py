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
from constants import *

import isys
import kickstart
import packages
import storage

from flags import flags
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class AnacondaBackend:
    def __init__(self, anaconda):
        """Abstract backend class all backends should inherit from this
           @param instPath: root path for the installation to occur"""
        self.anaconda = anaconda
        self.instPath = ROOT_PATH
        self.instLog = None
        self.modeText = ""

        # some backends may not support upgrading
        self.supportsUpgrades = True
        self.supportsPackageSelection = False

        # some backends may have a special case for rootfs formatting
        # FIXME: we should handle this a little more elegantly
        self.skipFormatRoot = False

    def postAction(self, anaconda):
        pass

    def doPreSelection(self, intf, id, instPath):
        pass

    def doPostSelection(self, anaconda):
        pass

    def doPreInstall(self, anaconda):
        self.initLog(ROOT_PATH)

    def copyFirmware(self):
        # Multiple driver disks may be loaded, so we need to glob for all
        # the firmware files in the common DD firmware directory
        for f in glob.glob(DD_FIRMWARE+"/*"):
            try:
                shutil.copyfile(f, "%s/lib/firmware/" % ROOT_PATH)
            except IOError as e:
                log.error("Could not copy firmware file %s: %s" % (f, e.strerror))

    def doPostInstall(self, anaconda):
        #always copy the firmware files from DD
        self.copyFirmware()

        if anaconda.extraModules:
            for (n, arch, tag) in self.kernelVersionList():
                packages.recreateInitrd(n, ROOT_PATH)

        #copy RPMS
        for d in glob.glob(DD_RPMS):
            shutil.copytree(d, ROOT_PATH + "/root/" + os.path.basename(d))

        #copy modules and firmware
        if os.path.exists(DD_ALL):
            try:
                shutil.copytree(DD_ALL, ROOT_PATH + "/root/DD")
            except IOError as e:
                pass

        storage.writeEscrowPackets(anaconda)
        sys.stdout.flush()

    def doInstall(self, anaconda):
        log.warning("doInstall not implemented for backend!")
        raise NotImplementedError

    def initLog(self, instPath):
        if not os.path.isdir(instPath + "/root"):
            iutil.mkdirChain(instPath + "/root")

        if self.anaconda.upgrade:
            logname = '/root/upgrade.log'
        else:
            logname = '/root/install.log'

        instLogName = instPath + logname
        try:
            shutil.rmtree (instLogName)
        except OSError:
            pass

        self.instLog = open(instLogName, "w+")

        syslogname = "%s%s.syslog" % (instPath, logname)
        try:
            shutil.rmtree (syslogname)
        except OSError:
            pass

        if self.anaconda.upgrade:
            self.modeText = _("%s Upgrading %s\n")
        else:
            self.modeText = _("%s Installing %s\n")

    def kernelVersionList(self):
        return []

    def getMinimumSizeMB(self, part):
        """Return the minimal size for part in megabytes if we can."""
        return 0

    def doBackendSetup(self, anaconda):
        log.warning("doBackendSetup not implemented for backend!")

    def groupExists(self, group):
        log.warning("groupExists not implemented for backend!")
        return True

    def selectGroup(self, group, *args):
        log.warning("selectGroup not implemented for backend!")

    def deselectGroup(self, group, *args):
        log.warning("deselectGroup not implemented for backend!")

    def packageExists(self, pkg):
        log.warning("packageExists not implemented for backend!")
        return True
    
    def selectPackage(self, pkg, *args):
        log.warning("selectPackage not implemented for backend!")

    def deselectPackage(self, pkg, *args):
        log.warning("deselectPackage not implemented for backend!")

    def getDefaultGroups(self, anaconda):
        log.warning("getDefaultGroups not implemented for backend!")
        return []

    def resetPackageSelections(self):
        # we just leave this one unimplemented if it's not needed
        pass

    # write out any config files that live on the installed system
    # (e.g., /etc/yum.repos.d/* files)
    def writeConfiguration(self):
        log.warning("writeConfig not implemented for backend!")

    def complete(self, anaconda):
        pass

def doBackendSetup(anaconda):
    if anaconda.backend.doBackendSetup(anaconda) == DISPATCH_BACK:
        return DISPATCH_BACK

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
    if anaconda.ksdata:
        anaconda.backend.resetPackageSelections()
        kickstart.selectPackages(anaconda)
    elif anaconda.displayMode != 't':
        anaconda.backend.resetPackageSelections()
        anaconda.instClass.setPackageSelection(anaconda)
        anaconda.instClass.setGroupSelection(anaconda)

def writeConfiguration(anaconda):
    log.info("Writing main configuration")
    anaconda.write()
    anaconda.backend.writeConfiguration()
