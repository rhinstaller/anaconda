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
import os, stat
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

def makeBootdisk (intf, dir, floppyDevice, hdList, instPath, bootloader):
    if dir == DISPATCH_BACK:
	return DISPATCH_NOOP
    
    if flags.test:
	return DISPATCH_NOOP

    kernel = hdList['kernel']
    kernelTag = "-%s-%s" % (kernel[rpm.RPMTAG_VERSION],
			    kernel[rpm.RPMTAG_RELEASE])


    # FIXME: if other arches had working boot disks, we wouldn't be able
    # to hardcode /boot
    kernel = "%s/boot/vmlinuz%s" %(instPath, kernelTag)
    size = 0
    if os.access(kernel, os.R_OK):
        try:
            kernelsize = os.stat(kernel)[stat.ST_SIZE]
            log("kernelsize is %s" %(kernelsize,))
        except:
            kernelsize = 0
        size = size + kernelsize
        
    initrd = "%s/boot/initrd%s.img" %(instPath, kernelTag)
    if os.access(initrd, os.R_OK):
        try:
            initrdsize = os.stat(initrd)[stat.ST_SIZE]
            log("initrdsize is %s" %(initrdsize,)            )
        except:
            initrdsize = 0
        size = size + initrdsize

    log("boot floppy size is %s" %(size,))

    # go within 10 K of the size of the boot disk to have a tad
    # bit of safety.  if this fails, we're no worse off than we used
    # to be.
    if size >= 1416 * 1024:
        intf.messageWindow(_("Unable to make boot floppy"),
                           _("The size of the kernel modules needed "
                             "for your machine make it impossible to "
                             "create a boot disk that will fit on a "
                             "floppy diskette."),
                           type = "warning")
        return DISPATCH_NOOP

    

    rc = intf.messageWindow( _("Insert a floppy disk"),
			_("Please remove any diskettes from the floppy "
			  "drive, and insert the floppy diskette that "
			  "is to contain the boot disk.\n\nAll data will "
			  "be ERASED during creation of the boot disk."),
			type="custom", custom_buttons=[_("_Cancel"), _("_Make boot disk")])

    if not rc:
	return DISPATCH_NOOP
    
    # this is faster then waiting on mkbootdisk to fail
    device = floppyDevice
    isys.makeDevInode(device, "/tmp/floppy")
    try:
	fd = os.open("/tmp/floppy", os.O_RDONLY)
    except:
        intf.messageWindow( _("Error"),
		    _("An error occurred while making the boot disk. "
		      "Please make sure that there is a floppy "
		      "in the first floppy drive."))
	return DISPATCH_BACK
    os.close(fd)

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
		    _("An error occurred while making the boot disk. "
		      "Please make sure that there is a floppy "
		      "in the first floppy drive."))
	return DISPATCH_BACK


    # more sanity checking -- see if the initrd size and kernel size
    # match what we thought they would be
    device = floppyDevice
    file = "/tmp/floppy"
    isys.makeDevInode(device, file)
    try:
        isys.mount("/tmp/floppy", "/mnt/floppy", "vfat")
    except:
        intf.messageWindow(_("Error"),
                           _("An error occurred while attempting to verify "
                             "the boot disk.  Please make sure that you "
                             "have a good floppy in the first floppy drive."))
        return DISPATCH_BACK

    problem = 0
    if os.access("/mnt/floppy/vmlinuz", os.R_OK):
        if kernelsize != 0:
            size = os.stat("/mnt/floppy/vmlinuz")[stat.ST_SIZE]
            if size != kernelsize:
                problem = 1
        else:
            log("unable to verify kernel size.  hope it fit!")
    else:
        problem = 1

    if initrdsize != 0:
        if os.access("/mnt/floppy/initrd.img", os.R_OK):
            size = os.stat("/mnt/floppy/initrd.img")[stat.ST_SIZE]
            if size != initrdsize:
                problem = 1
        else:
            problem = 1

    try:
        isys.umount("/mnt/floppy")
    except:
        pass

    if problem == 1:    
        intf.messageWindow(_("Error"),
                           _("Your boot floppy appears to be invalid.  This "
                             "is likely due to a bad floppy.  Please make "
                             "sure that you have a good floppy in the "
                             "first floppy drive."))
        return DISPATCH_BACK
    
    return DISPATCH_FORWARD
