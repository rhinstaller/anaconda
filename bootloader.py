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
import os
import crypt
import whrandom
import language
import iutil
import string
from flags import flags
from log import log
from constants import *
from translate import _

from booty import *
from bootloaderInfo import *


def bootloaderSetupChoices(dispatch, bl, fsset, diskSet, dir):
    if dir == DISPATCH_BACK:
        return

    # do not give option to change bootloader if partitionless case
    if fsset.rootOnLoop():
        bl.setUseGrub(0)
        dispatch.skipStep("bootloader")
        dispatch.skipStep("bootloaderpassword")
	dispatch.skipStep("instbootloader")
        return
    
    choices = fsset.bootloaderChoices(diskSet)
    if not choices:
	dispatch.skipStep("instbootloader")
    else:
	dispatch.skipStep("instbootloader", skip = 0)

    bl.images.setup(diskSet, fsset)

    # XXX fix mbr vs boot handling here
    if bl.defaultDevice != None and choices:
        keys = choices.keys()
#        if bl.defaultDevice > len(keys)
        if "mbr" in keys:
            bl.defaultDevice = "mbr"
        else:
            bl.defaultDevice = "boot"
        bl.setDevice(choices[bl.defaultDevice][0])

    bootDev = fsset.getEntryByMountPoint("/")
    if not bootDev:
        bootDev = fsset.getEntryByMountPoint("/boot")
    part = partitioning.get_partition_by_name(diskSet.disks,
                                              bootDev.device.getDevice())
    if part and partitioning.end_sector_to_cyl(part.geom.disk.dev,
                                               part.geom.end) >= 1024:
        bl.above1024 = 1
    

def writeBootloader(intf, instRoot, fsset, bl, langs, comps):
    justConfigFile = not flags.setupFilesystems

    if bl.defaultDevice == -1:
        return

    w = intf.waitWindow(_("Bootloader"), _("Installing bootloader..."))

    kernelList = []
    otherList = []
    rootDev = fsset.getEntryByMountPoint('/').device.getDevice()
    defaultDev = bl.images.getDefault()

    for (dev, (label, longlabel, type)) in bl.images.getImages().items():
	if dev == rootDev:
	    kernelLabel = label
            kernelLongLabel = longlabel
	elif dev == defaultDev:
	    otherList = [(label, longlabel, dev)] + otherList
	else:
	    otherList.append((label, longlabel, dev))

    plainLabelUsed = 0
    for (version, nick) in comps.kernelVersionList():
	if plainLabelUsed:
            kernelList.append(("%s-%s" %(kernelLabel, nick),
                               "%s-%s" %(kernelLongLabel, nick),
                               version))
	else:
	    kernelList.append((kernelLabel, kernelLongLabel, version))
	    plainLabelUsed = 1


    bl.write(instRoot, fsset, bl, langs, kernelList, otherList, defaultDev,
                 justConfigFile, intf)

    w.pop()

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
