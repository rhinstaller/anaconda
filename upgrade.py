#
# upgrade.py - Existing install probe and upgrade procedure
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Matt Wilson <msw@redhat.com>
#

import isys
import os
import iutil
import time
import sys
import os.path
import shutil
import string
import selinux
from flags import flags
from constants import *
from product import productName
from storage import findExistingRootDevices, getReleaseString
from storage import mountExistingSystem
from storage.formats import getFormat

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import rpm

import logging
log = logging.getLogger("anaconda")

def queryUpgradeContinue(anaconda):
    if anaconda.dir == DISPATCH_FORWARD:
        return

    rc = anaconda.intf.messageWindow(_("Proceed with upgrade?"),
                       _("The file systems of the Linux installation "
                         "you have chosen to upgrade have already been "
                         "mounted. You cannot go back past this point. "
                         "\n\n") + 
                       _("Would you like to continue with the upgrade?"),
                         type="custom", custom_icon=["error","error"],
                         custom_buttons=[_("_Exit installer"), _("_Continue")])
    if rc == 0:
        sys.exit(0)
    return DISPATCH_FORWARD

def setUpgradeRoot(anaconda):
    anaconda.upgradeRoot = []
    root_device = None
    # kickstart can pass device as device name or uuid. No quotes allowed.
    if anaconda.ksdata and anaconda.ksdata.upgrade.root_device is not None:
        root_device = anaconda.ksdata.upgrade.root_device
    for (dev, label) in anaconda.rootParts:
        if ((root_device is not None) and
            (root_device == dev.name or root_device == "UUID=%s" % dev.format.uuid)):
            anaconda.upgradeRoot.insert(0, (dev,label))
        else:
            anaconda.upgradeRoot.append((dev,label))

def findRootParts(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        return
    if anaconda.rootParts is None:
        anaconda.rootParts = findExistingRoots(anaconda,
                                               flags.cmdline.has_key("upgradeany"))

    setUpgradeRoot(anaconda)

    if anaconda.rootParts is not None and len(anaconda.rootParts) > 0:
        anaconda.dispatch.skipStep("findinstall", skip = 0)
        if productName.find("Red Hat Enterprise Linux") == -1:
            anaconda.dispatch.skipStep("installtype", skip = 1)
    else:
        anaconda.dispatch.skipStep("findinstall", skip = 1)
        anaconda.dispatch.skipStep("installtype", skip = 0)

def findExistingRoots(anaconda, upgradeany=False):
    rootparts = findExistingRootDevices(anaconda, upgradeany=upgradeany)
    return rootparts

def bindMountDevDirectory(instPath):
    getFormat("bind",
              device="/dev",
              mountpoint="/dev",
              exists=True).mount(chroot=instPath)

# returns None if no filesystem exist to migrate
def upgradeMigrateFind(anaconda):
    migents = anaconda.storage.migratableDevices
    if not migents or len(migents) < 1:
        anaconda.dispatch.skipStep("upgrademigratefs")
    else:
        anaconda.dispatch.skipStep("upgrademigratefs", skip = 0)
    

# returns None if no more swap is needed
def upgradeSwapSuggestion(anaconda):
    # mem is in kb -- round it up to the nearest 4Mb
    mem = iutil.memInstalled()
    rem = mem % 16384
    if rem:
	mem = mem + (16384 - rem)
    mem = mem / 1024

    anaconda.dispatch.skipStep("addswap", 0)
    
    # don't do this if we have more then 250 MB
    if mem > 250:
        anaconda.dispatch.skipStep("addswap", 1)
        return
    
    swap = iutil.swapAmount() / 1024

    # if we have twice as much swap as ram and at least 192 megs
    # total, we're safe 
    if (swap >= (mem * 1.5)) and (swap + mem >= 192):
        anaconda.dispatch.skipStep("addswap", 1)
	return

    # if our total is 512 megs or more, we should be safe
    if (swap + mem >= 512):
        anaconda.dispatch.skipStep("addswap", 1)
	return

    fsList = []

    for device in anaconda.storage.fsset.devices:
        if not device.format:
            continue
        if device.format.mountable and device.format.linuxNative:
            if not device.format.status:
                continue
            space = isys.pathSpaceAvailable(anaconda.rootPath + device.format.mountpoint)
            if space > 16:
                info = (device, space)
                fsList.append(info)

    suggestion = mem * 2 - swap
    if (swap + mem + suggestion) < 192:
        suggestion = 192 - (swap + mem)
    if suggestion < 32:
        suggestion = 32
    suggSize = 0
    suggMnt = None
    for (device, size) in fsList:
	if (size > suggSize) and (size > (suggestion + 100)):
	    suggDev = device

    anaconda.upgradeSwapInfo = (fsList, suggestion, suggDev)

# XXX handle going backwards
def upgradeMountFilesystems(anaconda):
    # mount everything and turn on swap

    try:
        mountExistingSystem(anaconda, anaconda.upgradeRoot[0], allowDirty = 0)
    except ValueError as e:
        log.error("Error mounting filesystem: %s" % e)
        anaconda.intf.messageWindow(_("Mount failed"),
            _("The following error occurred when mounting the file "
              "systems listed in /etc/fstab.  Please fix this problem "
              "and try to upgrade again.\n%s" % e))
        sys.exit(0)
    except IndexError as e:
        # The upgrade root is search earlier but we give the message here.
        log.debug("No upgrade root was found.")
        if anaconda.ksdata and anaconda.ksdata.upgrade.upgrade:
            anaconda.intf.messageWindow(_("Upgrade root not found"),
                _("The root for the previously installed system was not "
                  "found."), type="custom",
                custom_icon="info",
                custom_buttons=[_("Exit installer")])
            sys.exit(0)
        else:
            rc = anaconda.intf.messageWindow(_("Upgrade root not found"),
                    _("The root for the previously installed system was not "
                      "found.  You can exit installer or backtrack to choose "
                      "installation instead of upgrade."),
                type="custom",
                custom_buttons = [ _("_Back"),
                                   _("_Exit installer") ],
                custom_icon="question")
            if rc == 0:
                return DISPATCH_BACK
            elif rc == 1:
                sys.exit(0)

    checkLinks = ( '/etc', '/var', '/var/lib', '/var/lib/rpm',
                   '/boot', '/tmp', '/var/tmp', '/root',
                   '/bin/sh', '/usr/tmp')
    badLinks = []
    for n in checkLinks:
        if not os.path.islink(anaconda.rootPath + n): continue
        l = os.readlink(anaconda.rootPath + n)
        if l[0] == '/':
            badLinks.append(n)

    if badLinks:
        message = _("The following files are absolute symbolic " 
                    "links, which we do not support during an " 
                    "upgrade. Please change them to relative "
                    "symbolic links and restart the upgrade.\n\n")
        for n in badLinks:
            message = message + '\t' + n + '\n'
        anaconda.intf.messageWindow(_("Absolute Symlinks"), message)
        sys.exit(0)

    # fix for 80446
    badLinks = []
    mustBeLinks = ( '/usr/tmp', )
    for n in mustBeLinks:
        if not os.path.islink(anaconda.rootPath + n):
            badLinks.append(n)

    if badLinks: 
        message = _("The following are directories which should instead "
                    "be symbolic links, which will cause problems with the "
                    "upgrade.  Please return them to their original state "
                    "as symbolic links and restart the upgrade.\n\n")
        for n in badLinks:
            message = message + '\t' + n + '\n'
        anaconda.intf.messageWindow(_("Invalid Directories"), message)
        sys.exit(0)

    anaconda.storage.turnOnSwap(upgrading=True)
    anaconda.storage.mkDevRoot()

    # Move /etc/rpm/platform out of the way.
    if os.path.exists(anaconda.rootPath + "/etc/rpm/platform"):
        shutil.move(anaconda.rootPath + "/etc/rpm/platform",
                    anaconda.rootPath + "/etc/rpm/platform.rpmsave")

    # if they've been booting with selinux disabled, then we should
    # disable it during the install as well (#242510)
    try:
        if os.path.exists(anaconda.rootPath + "/.autorelabel"):
            ctx = selinux.getfilecon(anaconda.rootPath + "/.autorelabel")[1]
            if not ctx or ctx == "unlabeled":
                flags.selinux = False
                log.info("Disabled SELinux for upgrade based on /.autorelabel")
    except Exception, e:
        log.warning("error checking selinux state: %s" %(e,))

def setSteps(anaconda):
    dispatch = anaconda.dispatch
    dispatch.setStepList(
                "language",
                "keyboard",
                "welcome",
                "filtertype",
                "filter",
                "cleardiskssel",
                "installtype",
                "storageinit",
                "findrootparts",
                "findinstall",
                "upgrademount",
                "upgrademigfind",
                "upgrademigratefs",
                "enablefilesystems",
                "upgradecontinue",
                "reposetup",
                "upgbootloader",
                "checkdeps",
                "dependencies",
                "confirmupgrade",
                "postselection",
                "reipl",
                "install",
                "preinstallconfig",
                "installpackages",
                "postinstallconfig",
                "instbootloader",
                "dopostaction",
                "methodcomplete",
                "postscripts",
                "copylogs",
                "complete"
            )

    if not iutil.isX86():
        dispatch.skipStep("bootloader")

    if not iutil.isX86():
        dispatch.skipStep("upgbootloader")            
