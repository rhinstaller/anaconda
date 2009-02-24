#
# autopart.py - auto partitioning logic
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import parted
import copy
import string, sys
import fsset
import lvm
import logging
from anaconda_log import logger, logFile
import cryptodev
import partedUtils
import partRequests
from constants import *
from errors import *

import iutil
import isys

log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)


PARTITION_FAIL = -1
PARTITION_SUCCESS = 0

BOOT_NOT_EXT2 = -1
BOOTEFI_NOT_VFAT = -2
BOOTALPHA_NOT_BSD = -3
BOOTALPHA_NO_RESERVED_SPACE = -4
BOOTIPSERIES_TOO_HIGH = -5

# check that our "boot" partitions meet necessary constraints unless
# the request has its ignore flag set
def bootRequestCheck(req, diskset):
    if not req.device or req.ignoreBootConstraints:
        return PARTITION_SUCCESS

    part = None

    if not hasattr(req, "drive"):
        return PARTITION_SUCCESS

    for drive in req.drive:
        part = diskset.disks[drive].getPartitionByPath("/dev/%s" % req.device)

    if not part:
        return PARTITION_SUCCESS

    if iutil.isEfi():
        if req.mountpoint == "/boot":
            if not part.fileSystem.type.startswith("ext"):
                return BOOT_NOT_EXT2
        elif req.mountpoint == "/boot/efi":
            if not part.fileSystem.type in ["fat16", "fat32"]:
                return BOOTEFI_NOT_VFAT
    elif iutil.isAlpha():
        return bootAlphaCheckRequirements(part)
    elif (iutil.getPPCMachine() == "pSeries" or
          iutil.getPPCMachine() == "iSeries"):
        for drive in req.drive:
            part = diskset.disks[drive].getPartitionByPath("/dev/%s" % req.device)
            if part and ((part.geometry.end * part.geometry.device.sectorSize /
                          (1024.0 * 1024)) > 4096):
                return BOOTIPSERIES_TOO_HIGH

    return PARTITION_SUCCESS

# Alpha requires a BSD partition to boot. Since we can be called after:
#
#   - We re-attached an existing /boot partition (existing dev.drive)
#   - We create a new one from a designated disk (no dev.drive)
#   - We auto-create a new one from a designated set of disks (dev.drive
#     is a list)
#
# it's simpler to get disk the partition belong to through dev.device
# Some other tests pertaining to a partition where /boot resides are:
#
#   - There has to be at least 1 MB free at the begining of the disk
#     (or so says the aboot manual.)

def bootAlphaCheckRequirements(part):
    disk = part.disk

    # Disklabel check
    if not disk.type == "bsd":
        return BOOTALPHA_NOT_BSD

    # The first free space should start at the begining of the drive
    # and span for a megabyte or more.
    free = disk.getFirstPartition()
    while free:
        if free.type & parted.PARTITION_FREESPACE:
            break
        free = free.nextPartition()
    if (not free or free.geometry.start != 1L or free.getSize(unit="MB") < 1):
        return BOOTALPHA_NO_RESERVED_SPACE

    return PARTITION_SUCCESS

def getMinimumSector(disk):
    if disk.type == 'sun':
        (cylinders, heads, sectors) = disk.device.biosGeometry
        start = long(sectors * heads)
        start /= long(1024 / disk.device.sectorSize)
        return start + 1
    return 0L

def getAutopartitionBoot(partitions):
    """Return the proper shorthand for the boot dir (arch dependent)."""
    fsname = fsset.fileSystemTypeGetDefaultBoot().getName()
    if iutil.isEfi():
        ret = [ ["/boot/efi", "efi", 50, 200, 1, 1, 0] ]
        for req in partitions.requests:
            if req.fstype == fsset.fileSystemTypeGet("efi") \
                    and not req.mountpoint:
                req.mountpoint = "/boot/efi"
                ret = []
        ret.append(("/boot", fsname, 200, None, 0, 1, 0))
        return ret
    elif (iutil.getPPCMachine() == "pSeries"):
        return [ (None, "PPC PReP Boot", 4, None, 0, 1, 0),
                 ("/boot", fsname, 200, None, 0, 1, 0) ]
    elif (iutil.getPPCMachine() == "iSeries") and not iutil.hasiSeriesNativeStorage():
        return [ (None, "PPC PReP Boot", 16, None, 0, 1, 0) ]
    elif (iutil.getPPCMachine() == "iSeries") and iutil.hasiSeriesNativeStorage():
        return []
    elif (iutil.getPPCMachine() == "PMac") and iutil.getPPCMacGen() == "NewWorld":
        return [ ( None, "Apple Bootstrap", 1, 1, 0, 1, 0), 
                 ("/boot", fsname, 200, None, 0, 1, 0) ]
    else:
        return [ ("/boot", fsname, 200, None, 0, 1, 0) ]


