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
from storage import findExistingRootDevices
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
        (anaconda.rootParts, notUpgradable) = findExistingRootDevices(anaconda,
                                        upgradeany=flags.cmdline.has_key("upgradeany"))

        if notUpgradable and not anaconda.rootParts:
            oldInstalls = ""
            for info in notUpgradable:
                if None in info[:2]:
                    oldInstalls += _("Unknown release on %s") % (info[2])
                else:
                    oldInstalls += "%s %s on %s" % (info)
                oldInstalls += "\n"
            rc = anaconda.intf.messageWindow(_("Cannot Upgrade"),
                    _("Your current installation cannot be upgraded. This "
                      "is likely due to it being too old. Only the previous two "
                      "releases may be upgraded. To upgrade older releases "
                      "you must first upgrade through all intermediate releases.\n\n"
                      "%s") % oldInstalls,
                type="custom", custom_icon=["error","error"],
                custom_buttons=[_("_Exit installer"), _("_Continue")])
            if rc == 0:
                sys.exit(0)

    setUpgradeRoot(anaconda)

    if anaconda.rootParts is not None and len(anaconda.rootParts) > 0:
        anaconda.dispatch.request_steps_gently("findinstall")
    else:
        anaconda.dispatch.skip_steps("findinstall")

def bindMountDevDirectory(instPath):
    getFormat("bind",
              device="/dev",
              mountpoint="/dev",
              exists=True).mount(chroot=instPath)

# returns None if no filesystem exist to migrate
def upgradeMigrateFind(anaconda):
    migents = anaconda.storage.migratableDevices
    if not migents or len(migents) < 1:
        anaconda.dispatch.skip_steps("upgrademigratefs")
    else:
        anaconda.dispatch.request_steps("upgrademigratefs")

def copyFromSysimage(filename):
    """Mirrors filename from the sysimage on the ramdisk."""
    sysfile = os.path.normpath("%s/%s" % (ROOT_PATH, filename))
    if os.access(sysfile, os.R_OK):
        try:
            # remove our copy if we have one (think liveinstall)
            os.remove(filename)
        except OSError:
            pass
        try:
            shutil.copyfile(sysfile, filename)
        except OSError as e:
            log.error("Error copying %s to sysimage: %s" %(sysfile, e.strerror))
            return False
    else:
        log.error("Error copying %s to sysimage, file not accessible." % sysfile)
        return False
    return True

def restoreTime(anaconda):
    """Load time setup for upgrade install.
    
    We need to find out the timezone and the UTC parameter of the old system and
    set the system time accordingly, so timestamps are set correctly for the
    files the upgrade procedure will create.

    This is pretty much what packages.setupTimezone() does in reverse.
    """
    if anaconda.dir == DISPATCH_BACK:
        return
    if os.environ.has_key("TZ"):
        del os.environ["TZ"]
    copyFromSysimage('/etc/localtime')
    copyFromSysimage('/etc/adjtime')
    if iutil.isS390():
        return
    args = [ "--hctosys" ]
    try:
        iutil.execWithRedirect("/sbin/hwclock", args,stdout = "/dev/tty5",
                               stderr = "/dev/tty5")
    except RuntimeError:
        log.error("Failed to set the clock.")

# XXX handle going backwards
def upgradeMountFilesystems(anaconda):
    # mount everything and turn on swap

    try:
        mountExistingSystem(anaconda.storage.fsset, anaconda.upgradeRoot[0], allowDirty = 0)
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
        if not os.path.islink(ROOT_PATH + n): continue
        l = os.readlink(ROOT_PATH + n)
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
        if not os.path.islink(ROOT_PATH + n):
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
    if os.path.exists(ROOT_PATH + "/etc/rpm/platform"):
        shutil.move(ROOT_PATH + "/etc/rpm/platform",
                    ROOT_PATH + "/etc/rpm/platform.rpmsave")

    # if they've been booting with selinux disabled, then we should
    # disable it during the install as well (#242510)
    try:
        if os.path.exists(ROOT_PATH + "/.autorelabel"):
            ctx = selinux.getfilecon(ROOT_PATH + "/.autorelabel")[1]
            if not ctx or ctx == "unlabeled":
                flags.selinux = False
                log.info("Disabled SELinux for upgrade based on /.autorelabel")
    except Exception as e:
        log.warning("error checking selinux state: %s" %(e,))

def setSteps(anaconda):
    dispatch = anaconda.dispatch
    dispatch.reset_scheduling() # scrap what is scheduled
    # in case we are scheduling steps from the examine GUI, some of them are
    # already done:
    dispatch.schedule_steps_gently(
                "language",
                "keyboard",
                "filtertype",
                "filter",
                "storageinit",
                "findrootparts",
                "findinstall"
                )
    # schedule the rest:
    dispatch.schedule_steps(
                "upgrademount",
                "restoretime",
                "upgrademigfind",
                "upgrademigratefs",
                "enablefilesystems",
                "upgradecontinue",
                "reposetup",
                "upgbootloader",
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

    if not iutil.isX86() and not iutil.isS390():
        dispatch.skip_steps("bootloader")

    if not iutil.isX86():
        dispatch.skip_steps("upgbootloader")

    dispatch.skip_steps("cleardiskssel")
