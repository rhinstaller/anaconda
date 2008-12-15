#
# bootloader.py: anaconda bootloader shims
#
# Erik Troan <ewt@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import isys
import partitioning
import partedUtils
import os
import crypt
import whrandom
import language
import iutil
import string
from flags import flags
from constants import *

from rhpl.log import log
from rhpl.translate import _

from booty import *
from bootloaderInfo import *
from fsset import *

showLilo = 0
try:
    f = open("/proc/cmdline", "r")
    if f.read().find("lilo") != -1:
        showLilo = 1
except:
    pass



def bootloaderSetupChoices(dispatch, bl, fsset, diskSet, dir):
    if dir == DISPATCH_BACK:
        return

# iSeries bootloader on upgrades
    if iutil.getPPCMachine() == "iSeries" and not bl.device:        
        drives = diskSet.disks.keys()
        drives.sort()
        bootPart = None
        for drive in drives:
            disk = diskSet.disks[drive]
            part = disk.next_partition()
            while part:
                if part.is_active() and part.native_type == 0x41:
                    bootPart = partedUtils.get_partition_name(part)
                    break
                part = disk.next_partition(part)
            if bootPart:
                break
        if bootPart:
            bl.setDevice(bootPart)
            dev = Device()
            dev.device = bootPart
            fsset.add(FileSystemSetEntry(dev, None, fileSystemTypeGet("PPC PReP Boot")))

    choices = fsset.bootloaderChoices(diskSet, bl)
    if not choices and iutil.getPPCMachine() != "iSeries":
	dispatch.skipStep("instbootloader")
    else:
	dispatch.skipStep("instbootloader", skip = 0)

    bl.images.setup(diskSet, fsset)

    if bl.defaultDevice != None and choices:
        keys = choices.keys()
        # there are only two possible things that can be in the keys
        # mbr and boot.  boot is ALWAYS present.  so if the dev isn't
        # listed, it was mbr and we should nicely fall back to boot
        if bl.defaultDevice not in keys:
            log("MBR not suitable as boot device; installing to partition")
            bl.defaultDevice = "boot"
        bl.setDevice(choices[bl.defaultDevice][0])
    elif choices and choices.has_key("mbr") and not \
         (choices.has_key("boot") and choices["boot"][1] == N_("RAID Device")):
        bl.setDevice(choices["mbr"][0])
    elif choices and choices.has_key("boot"):
        bl.setDevice(choices["boot"][0])
    

    bootDev = fsset.getEntryByMountPoint("/")
    if not bootDev:
        bootDev = fsset.getEntryByMountPoint("/boot")
    part = partedUtils.get_partition_by_name(diskSet.disks,
                                              bootDev.device.getDevice())
    if part and partedUtils.end_sector_to_cyl(part.geom.dev,
                                               part.geom.end) >= 1024:
        bl.above1024 = 1
    

def writeBootloader(intf, instRoot, fsset, bl, langs, comps):
    def dosync():
        isys.sync()
        isys.sync()
        isys.sync()
        
    justConfigFile = not flags.setupFilesystems

    if bl.defaultDevice == -1:
        return

    # now make the upgrade stuff work for kickstart too. ick.
    if bl.kickstart == 1 and bl.doUpgradeOnly == 1:
        import checkbootloader
        (bootType, theDev) = checkbootloader.getBootloaderTypeAndBoot(instRoot)
        
        bl.doUpgradeonly = 1
        if bootType == "GRUB":
            bl.useGrubVal = 1
            bl.setDevice(theDev)
        elif bootType == "LILO":
            bl.useGrubVal = 0
            bl.setDevice(theDev)            
        else:
            bl.doUpgradeOnly = 0    

    # We don't need to let the user know if we're just doing the bootloader.
    if not justConfigFile:
        w = intf.waitWindow(_("Bootloader"), _("Installing bootloader..."))

    kernelList = []
    otherList = []
    rootDev = fsset.getEntryByMountPoint('/').device.getDevice()
    defaultDev = bl.images.getDefault()

    kernelLabel = None
    kernelLongLabel = None

    for (dev, (label, longlabel, type)) in bl.images.getImages().items():
	if dev == rootDev:
	    kernelLabel = label
            kernelLongLabel = longlabel
	elif dev == defaultDev:
	    otherList = [(label, longlabel, dev)] + otherList
	else:
	    otherList.append((label, longlabel, dev))

    if kernelLabel is None:
        log("unable to find default image, bailing")
	if not justConfigFile:
	    w.pop()
        return

    plainLabelUsed = 0
    defkern = "kernel"
    for (version, nick) in comps.kernelVersionList():
	if plainLabelUsed:
            kernelList.append(("%s-%s" %(kernelLabel, nick),
                               "%s-%s" %(kernelLongLabel, nick),
                               version))
	else:
	    kernelList.append((kernelLabel, kernelLongLabel, version))
            if nick != "up":
                defkern = "kernel-%s" %(nick,)
	    plainLabelUsed = 1

    f = open(instRoot + "/etc/sysconfig/kernel", "w+")
    f.write("# UPDATEDEFAULT specifies if new-kernel-pkg should make\n"
            "# new kernels the default\n")
    f.write("UPDATEDEFAULT=yes\n")
    f.write("\n")
    f.write("# DEFAULTKERNEL specifies the default kernel package type\n")
    f.write("DEFAULTKERNEL=%s\n" %(defkern,))
    f.close()

    dosync()
    try:
        bl.write(instRoot, fsset, bl, langs, kernelList, otherList, defaultDev,
                 justConfigFile, intf)
	if not justConfigFile:
	    w.pop()
    except BootyNoKernelWarning:
	if not justConfigFile:
	    w.pop()
        if intf:
            intf.messageWindow(_("Warning"),
                               _("No kernel packages were installed on your "
                                 "system.  Your boot loader configuration "
                                 "will not be changed."))
    dosync()

# note that this function no longer actually creates an initrd.
# the kernel's %post does this now
def makeInitrd (kernelTag, instRoot):
    if iutil.getArch() == 'ia64':
	initrd = "/boot/efi/initrd%s.img" % (kernelTag, )
    else:
	initrd = "/boot/initrd%s.img" % (kernelTag, )

    return initrd

# return instance of the appropriate bootloader for our arch
def getBootloader():
    import booty
    return booty.getBootloader()
