#
# edd.py
# BIOS EDD data parsing functions
#
# Copyright (C) 2010  Red Hat, Inc.  All rights reserved.
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
# Author(s): Hans de Goede <hdegoede@redhat.com>
#

import os
import struct

import logging
log = logging.getLogger("storage")

def get_edd_dict(devices):
    """Given an array of devices return a dict with the BIOS ID for them."""
    edd_dict = {}

    for biosdev in range(80, 80 + 15):
        sysfspath = "/sys/firmware/edd/int13_dev%d" % biosdev
        if not os.path.exists(sysfspath):
            break # We are done

        sysfspath = "/sys/firmware/edd/int13_dev%d/mbr_signature" % biosdev
        if not os.path.exists(sysfspath):
            log.warning("No mbrsig for biosdev: %d" % biosdev)
            continue

        try:
            file = open(sysfspath, "r")
            eddsig = file.read()
            file.close()
        except (IOError, OSError) as e:
            log.warning("Error reading EDD mbrsig for %d: %s" %
                        (biosdev, str(e)))
            continue

        sysfspath = "/sys/firmware/edd/int13_dev%d/sectors" % biosdev
        try:
            file = open(sysfspath, "r")
            eddsize = file.read()
            file.close()
        except (IOError, OSError) as e:
            eddsize = None

        found = []
        for dev in devices:
            try:
                fd = os.open(dev.path, os.O_RDONLY)
                os.lseek(fd, 440, 0) 
                mbrsig = struct.unpack('I', os.read(fd, 4))
                os.close(fd)
            except OSError as e:
                log.warning("Error reading mbrsig from disk %s: %s" %
                            (dev.name, str(e)))
                continue

            mbrsigStr = "0x%08x\n" % mbrsig
            if mbrsigStr == eddsig:
                if eddsize:
                    sysfspath = "/sys%s/size" % dev.sysfsPath
                    try:
                        file = open(sysfspath, "r")
                        size = file.read()
                        file.close()
                    except (IOError, OSError) as e:
                        log.warning("Error getting size for: %s" % dev.name)
                        continue
                    if eddsize != size:
                        continue
                found.append(dev.name)

        if not found:
            log.error("No matching mbr signature found for biosdev %d" %
                      biosdev)
        elif len(found) > 1:
            log.error("Multiple signature matches found for biosdev %d: %s" %
                      (biosdev, str(found)))
        else:
            log.info("Found %s for biosdev %d" %(found[0], biosdev))
            edd_dict[found[0]] = biosdev

    return edd_dict
