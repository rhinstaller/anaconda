#
# floppy.py - floppy drive probe and bootdisk creation
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
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
from log import log
import re
import os
from flags import flags
import dispatch
import rpm
from translate import _

def probeFloppyDevice():
    fdDevice = "fd0"
    if iutil.getArch() == "sparc":
	try:
	    f = open(fdDevice, "r")
	except IOError, (errnum, msg):
	    if errno.errorcode[errnum] == 'ENXIO':
		fdDevice = "fd1"
	else:
	    f.close()
    elif iutil.getArch() == "alpha":
	pass
    elif iutil.getArch() == "i386" or iutil.getArch() == "ia64":
	# Look for the first IDE floppy device
	drives = isys.floppyDriveDict()
	if not drives:
	    log("no IDE floppy devices found")
	    return fdDevice

	floppyDrive = drives.keys()[0]
	# need to go through and find if there is an LS-120
	for dev in drives.keys():
	    if re.compile(".*[Ll][Ss]-120.*").search(drives[dev]):
		floppyDrive = dev

	# No IDE floppy's -- we're fine w/ /dev/fd0
	if not floppyDrive: return fdDevice

	if iutil.getArch() == "ia64":
	    fdDevice = floppyDrive
	    log("anaconda floppy device is %s", fdDevice)
	    return fdDevice

	# Look in syslog for a real fd0 (which would take precedence)
	try:
	    f = open("/tmp/syslog", "r")
	except IOError:
	    try: 
		f = open("/var/log/dmesg", "r")
	    except IOError:
		return fdDevice

	for line in f.readlines():
	    # chop off the loglevel (which init's syslog leaves behind)
	    line = line[3:]
	    match = "Floppy drive(s): "
	    if match == line[:len(match)]:
		# Good enough
		floppyDrive = "fd0"
		break

	fdDevice = floppyDrive
    else:
	raise SystemError, "cannot determine floppy device for this arch"

    log("anaconda floppy device is %s", fdDevice)

    return fdDevice

def makeBootdisk (intf, floppyDevice, hdList, instPath):
    if flags.test:
	return dispatch.DISPATCH_NOOP

    # this is faster then waiting on mkbootdisk to fail
    device = floppyDevice
    file = "/tmp/floppy"
    isys.makeDevInode(device, file)
    try:
	fd = os.open(file, os.O_RDONLY)
    except:
	return dispatch.DISPATCH_BACK
    os.close(fd)

    kernel = hdList['kernel']
    kernelTag = "-%s-%s" % (kernel[rpm.RPMTAG_VERSION],
			    kernel[rpm.RPMTAG_RELEASE])

    w = intf.waitWindow (_("Creating"), _("Creating boot disk..."))
    rc = iutil.execWithRedirect("/sbin/mkbootdisk",
				[ "/sbin/mkbootdisk",
				  "--noprompt",
				  "--device",
				  "/dev/" + floppyDevice,
				  kernelTag[1:] ],
				stdout = '/dev/tty5', stderr = '/dev/tty5',
				searchPath = 1, root = instPath)
    w.pop()

    if rc:
	import dispatch
	return dispatch.DISPATCH_BACK

