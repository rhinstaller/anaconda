#
# floppy.py - floppy drive probe and bootdisk creation
#
# Erik Troan <ewt@redhat.com>
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
import errno
import iutil
import re
import os
import rpm
import kudzu
from constants import *
from flags import flags

from rhpl.log import log
from rhpl.translate import _

def probeFloppyDevice():
    fdDevice = "fd0"

    # we now have nifty kudzu code that does all of the heavy lifting
    # and properly detects detached floppy drives, ide floppies, and
    # even usb floppies
    devices = kudzu.probe(kudzu.CLASS_FLOPPY,
                          kudzu.BUS_IDE | kudzu.BUS_MISC | kudzu.BUS_SCSI,
                          kudzu.PROBE_ALL)

    if not devices:
        log("no floppy devices found but we'll try fd0 anyway")
        return fdDevice

    for device in devices:
        if device.detached:
            continue
        log("anaconda floppy device %s" % (device.device))
        return device.device
    
    log("anaconda floppy device is %s", fdDevice)
    return fdDevice

def makeBootdisk (intf, floppyDevice, hdList, instPath, bootloader):
    if flags.test:
	return DISPATCH_NOOP

    rc = intf.messageWindow( _("Insert a floppy disk"),
			_("Please remove any diskettes from the floppy "
			  "drive, and insert the floppy diskette that "
			  "is to contain the boot disk.\n\nAll data will "
			  "be ERASED during creation of the boot disk."),
			type="custom", custom_buttons=[_("Cancel"), _("Make boot disk")])

    if rc:
	return DISPATCH_NOOP
    
    # this is faster then waiting on mkbootdisk to fail
    device = floppyDevice
    file = "/tmp/floppy"
    isys.makeDevInode(device, file)
    try:
	fd = os.open(file, os.O_RDONLY)
    except:
        intf.messageWindow( _("Error"),
		    _("An error occured while making the boot disk. "
		      "Please make sure that there is a floppy "
		      "in the first floppy drive."))
	return DISPATCH_BACK
    os.close(fd)

    kernel = hdList['kernel']
    kernelTag = "-%s-%s" % (kernel[rpm.RPMTAG_VERSION],
			    kernel[rpm.RPMTAG_RELEASE])

    if bootloader.args.get():
        args = bootloader.args.get()
    else:
        args = ""

    w = intf.waitWindow (_("Creating"), _("Creating boot disk..."))
    rc = iutil.execWithRedirect("/sbin/mkbootdisk",
				[ "/sbin/mkbootdisk",
                                  "--kernelargs", args,
				  "--noprompt",
				  "--device",
				  "/dev/" + floppyDevice,
				  kernelTag[1:] ],
				stdout = '/dev/tty5', stderr = '/dev/tty5',
				searchPath = 1, root = instPath)
    w.pop()

    if rc:
        intf.messageWindow( _("Error"),
		    _("An error occured while making the boot disk. "
		      "Please make sure that there is a floppy "
		      "in the first floppy drive."))
	return DISPATCH_BACK
    return DISPATCH_FORWARD
