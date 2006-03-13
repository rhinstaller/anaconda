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
import kudzu
from constants import *
from flags import flags

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

def hasFloppyDevice():
    try:
        for dev in kudzu.probe(kudzu.CLASS_FLOPPY, kudzu.BUS_UNSPEC,
                               kudzu.PROBE_ALL):
            if not dev.detached:
                return True
    except:
        return False
    return False

def probeFloppyDevice():
    fdDevice = "fd0"

    # we now have nifty kudzu code that does all of the heavy lifting
    # and properly detects detached floppy drives, ide floppies, and
    # even usb floppies
    devices = kudzu.probe(kudzu.CLASS_FLOPPY,
                          kudzu.BUS_IDE | kudzu.BUS_MISC | kudzu.BUS_SCSI,
                          kudzu.PROBE_ALL)

    if not devices:
        log.warning("no floppy devices found but we'll try fd0 anyway")
        return fdDevice

    for device in devices:
        if device.detached:
            continue
        log.info("anaconda floppy device %s" % (device.device))
        return device.device
    
    log.info("anaconda floppy device is %s", fdDevice)
    return fdDevice
