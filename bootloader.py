#
# bootloader.py: anaconda bootloader shims
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
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
# Author(s): Erik Troan <ewt@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#

import isys
import parted
import os, sys
import iutil
import string
from flags import flags
from constants import *
from storage.devices import devicePathToName
from storage import getReleaseString
from booty.util import getDiskPart

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

import booty
from booty import bootloaderInfo, checkbootloader

def isEfiSystemPartition(part):
    if not part.active:
        return False
    return (part.disk.type == "gpt" and
            part.name == "EFI System Partition" and
            part.getFlag(parted.PARTITION_BOOT) and
            part.fileSystem.type in ("fat16", "fat32") and
            isys.readFSLabel(part.getDeviceNodeName()) != "ANACONDA")

def bootloaderSetupChoices(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        rc = anaconda.intf.messageWindow(_("Warning"),
                _("Filesystems have already been activated.  You "
                  "cannot go back past this point.\n\nWould you like to "
                  "continue with the installation?"),
                type="custom", custom_icon=["error","error"],
                custom_buttons=[_("_Exit installer"), _("_Continue")])

        if rc == 0:
            sys.exit(0)
        return DISPATCH_FORWARD

    if anaconda.ksdata and anaconda.ksdata.bootloader.driveorder:
        anaconda.bootloader.updateDriveList(anaconda.ksdata.bootloader.driveorder)
    else:
        #We want the selected bootloader drive to be preferred
        pref = anaconda.bootloader.drivelist[:1]
        anaconda.bootloader.updateDriveList(pref)

    if iutil.isEfi() and not anaconda.bootloader.device:
        bootPart = None
        partitions = anaconda.storage.partitions
        for part in partitions:
            if part.partedPartition.active and isEfiSystemPartition(part.partedPartition):
                bootPart = part.name
                break
        if bootPart:
            anaconda.bootloader.setDevice(bootPart)

# iSeries bootloader on upgrades
    if iutil.getPPCMachine() == "iSeries" and not anaconda.bootloader.device:
        bootPart = None
        partitions = anaconda.storage.partitions
        for part in partitions:
            if part.partedPartition.active and \
               part.partedPartition.getFlag(parted.PARTITION_PREP):
                bootPart = part.name
                break
        if bootPart:
            anaconda.bootloader.setDevice(bootPart)

    choices = anaconda.platform.bootloaderChoices(anaconda.bootloader)
    if not choices and iutil.getPPCMachine() != "iSeries":
	anaconda.dispatch.skipStep("instbootloader")
    else:
	anaconda.dispatch.skipStep("instbootloader", skip = 0)

    # FIXME: ...
    anaconda.bootloader.images.setup(anaconda.storage)

    if anaconda.bootloader.defaultDevice != None and choices:
        keys = choices.keys()
        # there are only two possible things that can be in the keys
        # mbr and boot.  boot is ALWAYS present.  so if the dev isn't
        # listed, it was mbr and we should nicely fall back to boot
        if anaconda.bootloader.defaultDevice not in keys:
            log.warning("MBR not suitable as boot device; installing to partition")
            anaconda.bootloader.defaultDevice = "boot"
        anaconda.bootloader.setDevice(choices[anaconda.bootloader.defaultDevice][0])
    elif choices and iutil.isMactel() and choices.has_key("boot"): # haccckkkk
        anaconda.bootloader.setDevice(choices["boot"][0])        
    elif choices and choices.has_key("mbr"):
        anaconda.bootloader.setDevice(choices["mbr"][0])
    elif choices and choices.has_key("boot"):
        anaconda.bootloader.setDevice(choices["boot"][0])

def fixedMdraidGrubTarget(anaconda, grubTarget):
    # handle change made in F12 - before F12 mdX used to mean installation
    # into mbrs of mdX members' disks
    fixedGrubTarget = grubTarget
    (product, version) = getReleaseString(anaconda.rootPath)
    try:
        if float(version) < 12:
            stage1Devs = anaconda.bootloader.getPhysicalDevices(grubTarget)
            fixedGrubTarget = getDiskPart(stage1Devs[0], anaconda.storage)[0]
            log.info("Mdraid grub upgrade: %s -> %s" % (grubTarget,
                                                       fixedGrubTarget))
    except ValueError:
        log.warning("Can't decide mdraid grub upgrade fix, product: %s, version: %s" % (product, version))

    return fixedGrubTarget

def writeBootloader(anaconda):
    def dosync():
        isys.sync()
        isys.sync()
        isys.sync()

    if anaconda.bootloader.defaultDevice == -1:
        return

    if anaconda.bootloader.doUpgradeOnly:
        (bootType, theDev) = checkbootloader.getBootloaderTypeAndBoot(anaconda.rootPath, storage=anaconda.storage)
        
        anaconda.bootloader.doUpgradeonly = 1
        if bootType == "GRUB":
            if theDev.startswith('/dev/md'):
                theDev = fixedMdraidGrubTarget(anaconda,
                                               devicePathToName(theDev))
            anaconda.bootloader.useGrubVal = 1
            anaconda.bootloader.setDevice(devicePathToName(theDev))
        else:
            anaconda.bootloader.doUpgradeOnly = 0    

    w = anaconda.intf.waitWindow(_("Bootloader"), _("Installing bootloader."))

    kernelList = []
    otherList = []
    # getDefault needs to return a device, but that's too invasive for now.
    rootDev = anaconda.storage.rootDevice

    if not anaconda.bootloader.images.getDefault():
        defaultDev = None
    else:
        defaultDev = anaconda.storage.devicetree.getDeviceByName(anaconda.bootloader.images.getDefault())

    kernelLabel = None
    kernelLongLabel = None

    for (dev, (label, longlabel, type)) in anaconda.bootloader.images.getImages().items():
        if (rootDev is None and kernelLabel is None) or (dev == rootDev.name):
	    kernelLabel = label
            kernelLongLabel = longlabel
	elif (not defaultDev and not dev) or (defaultDev and dev == defaultDev.name):
	    otherList = [(label, longlabel, dev)] + otherList
	else:
	    otherList.append((label, longlabel, dev))

    if kernelLabel is None:
        log.error("unable to find default image, bailing")
        w.pop()
        return

    plainLabelUsed = 0
    defkern = "kernel"
    for (version, arch, nick) in \
            anaconda.backend.kernelVersionList(anaconda.rootPath):
	if plainLabelUsed:
            kernelList.append(("%s-%s" %(kernelLabel, nick),
                               "%s-%s" %(kernelLongLabel, nick),
                               version))
	else:
	    kernelList.append((kernelLabel, kernelLongLabel, version))
            if nick != "base":
                defkern = "kernel-%s" %(nick,)
	    plainLabelUsed = 1

    f = open(anaconda.rootPath + "/etc/sysconfig/kernel", "w+")
    f.write("# UPDATEDEFAULT specifies if new-kernel-pkg should make\n"
            "# new kernels the default\n")
    # only update the default if we're setting the default to linux (#156678)
    if (not defaultDev and not rootDev) or (defaultDev and rootDev.name == defaultDev.name):
        f.write("UPDATEDEFAULT=yes\n")
    else:
        f.write("UPDATEDEFAULT=no\n")        
    f.write("\n")
    f.write("# DEFAULTKERNEL specifies the default kernel package type\n")
    f.write("DEFAULTKERNEL=%s\n" %(defkern,))
    f.close()

    dosync()
    try:
        rc = anaconda.bootloader.write(anaconda.rootPath, anaconda.bootloader,
                                       kernelList, otherList, defaultDev)
        w.pop()

        if rc and anaconda.intf:
            anaconda.intf.messageWindow(_("Warning"),
                               _("There was an error installing the bootloader.  "
                                 "The system may not be bootable."))
    except booty.BootyNoKernelWarning:
        w.pop()
        if anaconda.intf:
            anaconda.intf.messageWindow(_("Warning"),
                               _("No kernel packages were installed on the "
                                 "system.  Bootloader configuration "
                                 "will not be changed."))

    dosync()

def hasWindows(bl):
    foundWindows = False
    for (k,v) in bl.images.getImages().iteritems():
        if v[0].lower() == 'other' and v[2] in bootloaderInfo.dosFilesystems:
            foundWindows = True
            break

    return foundWindows
