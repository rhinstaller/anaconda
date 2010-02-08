#
# installmethod.py - Base class for install methods
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
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

import os, shutil, string
from constants import *

import logging
log = logging.getLogger("anaconda")

import isys, product

def doMethodComplete(anaconda):
    def _ejectDevice():
        # Ejecting the CD/DVD for kickstart is handled only after %post scripts
        # have been run.
        if anaconda.ksdata:
            return None

        if anaconda.mediaDevice:
            return anaconda.storage.devicetree.getDeviceByName(anaconda.mediaDevice)

        # If we booted off the boot.iso instead of disc 1, eject that as well.
        if anaconda.stage2 and anaconda.stage2.startswith("cdrom://"):
            dev = anaconda.stage2[8:].split(':')[0]
            return anaconda.storage.devicetree.getDeviceByName(dev)

    anaconda.backend.complete(anaconda)
    dev = _ejectDevice()
    if dev:
        dev.eject()

    mtab = "/dev/root / ext3 ro 0 0\n"
    rootDevice = anaconda.storage.rootDevice
    if rootDevice:
        mtab = "/dev/root / %s ro 0 0\n" % rootDevice.format.type

    f = open(anaconda.rootPath + "/etc/mtab", "w+")
    f.write(mtab)
    f.close()
