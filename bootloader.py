#
# bootloader.py: anaconda bootloader shims
#
# Erik Troan <ewt@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import isys
import partedUtils
import os
import iutil
import string
import rhpl
from flags import flags
from constants import *

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

import booty
import bootloaderInfo
from fsset import *

def bootloaderSetupChoices(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        return

    # FIXME: this is a hack...
    if flags.livecd:
        return 

    if anaconda.id.ksdata:
        anaconda.id.bootloader.updateDriveList(anaconda.id.ksdata.bootloader["driveorder"])
    else:
        anaconda.id.bootloader.updateDriveList()

# iSeries bootloader on upgrades
    if iutil.getPPCMachine() == "iSeries" and not anaconda.id.bootloader.device:        
        drives = anaconda.id.diskset.disks.keys()
        drives.sort()
        bootPart = None
        for drive in drives:
            disk = anaconda.id.diskset.disks[drive]
            part = disk.next_partition()
            while part:
                if part.is_active() and part.native_type == 0x41:
                    bootPart = partedUtils.get_partition_name(part)
                    break
                part = disk.next_partition(part)
            if bootPart:
                break
        if bootPart:
            anaconda.id.bootloader.setDevice(bootPart)
            dev = Device()
            dev.device = bootPart
            anaconda.id.fsset.add(FileSystemSetEntry(dev, None, fileSystemTypeGet("PPC PReP Boot")))

    choices = anaconda.id.fsset.bootloaderChoices(anaconda.id.diskset, anaconda.id.bootloader)
    if not choices and iutil.getPPCMachine() != "iSeries":
	anaconda.dispatch.skipStep("instbootloader")
    else:
	anaconda.dispatch.skipStep("instbootloader", skip = 0)

    anaconda.id.bootloader.images.setup(anaconda.id.diskset, anaconda.id.fsset)

    if anaconda.id.bootloader.defaultDevice != None and choices:
        keys = choices.keys()
        # there are only two possible things that can be in the keys
        # mbr and boot.  boot is ALWAYS present.  so if the dev isn't
        # listed, it was mbr and we should nicely fall back to boot
        if anaconda.id.bootloader.defaultDevice not in keys:
            log.warning("MBR not suitable as boot device; installing to partition")
            anaconda.id.bootloader.defaultDevice = "boot"
        anaconda.id.bootloader.setDevice(choices[anaconda.id.bootloader.defaultDevice][0])
    elif choices and iutil.isMactel() and choices.has_key("boot"): # haccckkkk
        anaconda.id.bootloader.setDevice(choices["boot"][0])        
    elif choices and choices.has_key("mbr") and not \
         (choices.has_key("boot") and choices["boot"][1] == N_("RAID Device")):
        anaconda.id.bootloader.setDevice(choices["mbr"][0])
    elif choices and choices.has_key("boot"):
        anaconda.id.bootloader.setDevice(choices["boot"][0])
    

    bootDev = anaconda.id.fsset.getEntryByMountPoint("/")
    if not bootDev:
        bootDev = anaconda.id.fsset.getEntryByMountPoint("/boot")
    part = partedUtils.get_partition_by_name(anaconda.id.diskset.disks,
                                              bootDev.device.getDevice())
    if part and partedUtils.end_sector_to_cyl(part.geom.dev,
                                               part.geom.end) >= 1024:
        anaconda.id.bootloader.above1024 = 1
    

def writeBootloader(anaconda):
    def dosync():
        isys.sync()
        isys.sync()
        isys.sync()

    justConfigFile = not flags.setupFilesystems

    if anaconda.id.bootloader.defaultDevice == -1:
        return

    # now make the upgrade stuff work for kickstart too. ick.
    if anaconda.isKickstart and anaconda.id.bootloader.doUpgradeOnly:
        import checkbootloader
        (bootType, theDev) = checkbootloader.getBootloaderTypeAndBoot(anaconda.rootPath)
        
        anaconda.id.bootloader.doUpgradeonly = 1
        if bootType == "GRUB":
            anaconda.id.bootloader.useGrubVal = 1
            anaconda.id.bootloader.setDevice(theDev)
        else:
            anaconda.id.bootloader.doUpgradeOnly = 0    

    # We don't need to let the user know if we're just doing the bootloader.
    if not justConfigFile:
        w = anaconda.intf.waitWindow(_("Bootloader"), _("Installing bootloader..."))

    kernelList = []
    otherList = []
    root = anaconda.id.fsset.getEntryByMountPoint('/')
    if root:
        rootDev = root.device.getDevice()
    else:
        rootDev = None

    kernelLabel = None
    kernelLongLabel = None

    def rectifyLuksName(anaconda, name):
        if name is not None and name.startswith('mapper/luks-'):
            try:
                newname = anaconda.id.partitions.encryptedDevices.get(name[12:])
                if newname is None:
                    for luksdev in anaconda.id.partitions.encryptedDevices.values():
                        if os.path.basename(luksdev.getDevice(encrypted=1)) == name[12:]:
                            newname = luksdev
                            break
                name = newname.getDevice()
            except:
                pass
        return name

    defaultDev = anaconda.id.bootloader.images.getDefault()
    defaultDev = rectifyLuksName(anaconda, defaultDev)

    for (dev, (label, longlabel, type)) in anaconda.id.bootloader.images.getImages().items():
        dev = rectifyLuksName(anaconda, dev)
        if (dev == rootDev) or (rootDev is None and kernelLabel is None):
	    kernelLabel = label
            kernelLongLabel = longlabel
	elif dev == defaultDev:
	    otherList = [(label, longlabel, dev)] + otherList
	else:
	    otherList.append((label, longlabel, dev))

    if kernelLabel is None and not flags.livecd: # FIXME
        log.error("unable to find default image, bailing")
	if not justConfigFile:
	    w.pop()
        return

    plainLabelUsed = 0
    defkern = "kernel"
    for (version, arch, nick) in anaconda.backend.kernelVersionList():
	if plainLabelUsed:
            kernelList.append(("%s-%s" %(kernelLabel, nick),
                               "%s-%s" %(kernelLongLabel, nick),
                               version))
	else:
	    kernelList.append((kernelLabel, kernelLongLabel, version))
            if nick in ("hypervisor", "guest"): # XXX: *sigh* inconsistent
                defkern = "kernel-xen-%s" %(nick,)
            elif nick != "base":
                defkern = "kernel-%s" %(nick,)
	    plainLabelUsed = 1

    f = open(anaconda.rootPath + "/etc/sysconfig/kernel", "w+")
    f.write("# UPDATEDEFAULT specifies if new-kernel-pkg should make\n"
            "# new kernels the default\n")
    # only update the default if we're setting the default to linux (#156678)
    if rootDev == defaultDev:
        f.write("UPDATEDEFAULT=yes\n")
    else:
        f.write("UPDATEDEFAULT=no\n")        
    f.write("\n")
    f.write("# DEFAULTKERNEL specifies the default kernel package type\n")
    f.write("DEFAULTKERNEL=%s\n" %(defkern,))
    f.close()

    dosync()
    try:
        anaconda.id.bootloader.write(anaconda.rootPath, anaconda.id.fsset, anaconda.id.bootloader,
                                     anaconda.id.instLanguage, kernelList, otherList, defaultDev,
                                     justConfigFile, anaconda.intf)
	if not justConfigFile:
	    w.pop()
    except bootloaderInfo.BootyNoKernelWarning:
	if not justConfigFile:
	    w.pop()
        if anaconda.intf:
            anaconda.intf.messageWindow(_("Warning"),
                               _("No kernel packages were installed on your "
                                 "system.  Your boot loader configuration "
                                 "will not be changed."))

    dosync()

# return instance of the appropriate bootloader for our arch
def getBootloader():
    if not flags.livecd:
        return booty.getBootloader()
    else:
        return bootloaderInfo.isolinuxBootloaderInfo()

def hasWindows(bl):
    foundWindows = False
    for (k,v) in bl.images.getImages().iteritems():
        if v[0].lower() == 'other' and v[2] in bootloaderInfo.dosFilesystems:
            foundWindows = True
            break

    return foundWindows
