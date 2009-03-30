#
# mdraid.py
# mdraid functions
#
# Copyright (C) 2009  Red Hat, Inc.  All rights reserved.
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
# Author(s): Dave Lehman <dlehman@redhat.com>
#

import os

import iutil
from ..errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

# raidlevels constants
RAID10 = 10
RAID6 = 6
RAID5 = 5
RAID1 = 1
RAID0 = 0

def getRaidLevels():
    avail = []
    try:
        f = open("/proc/mdstat", "r")
    except IOError:
        pass
    else:
        for l in f.readlines():
            if not l.startswith("Personalities"):
                continue

            lst = l.split()

            for lev in ["RAID0", "RAID1", "RAID5", "RAID6", "RAID10"]:
                if "[" + lev + "]" in lst or "[" + lev.lower() + "]" in lst:
                    avail.append(lev)

        f.close()

    avail.sort()
    return avail

raid_levels = getRaidLevels()

def isRaid(raid, raidlevel):
    """Return whether raidlevel is a valid descriptor of raid"""
    raid_descriptors = {RAID10: ("RAID10", "10", 10),
                        RAID6: ("RAID6", "6", 6),
                        RAID5: ("RAID5", "5", 5),
                        RAID1: ("mirror", "RAID1", "1", 1),
                        RAID0: ("stripe", "RAID0", "0", 0)}

    if raid in raid_descriptors:
        return raidlevel in raid_descriptors[raid]
    else:
        raise ValueError, "invalid raid level %d" % raid

def get_raid_min_members(raidlevel):
    """Return the minimum number of raid members required for raid level"""
    raid_min_members = {RAID10: 2,
                        RAID6: 4,
                        RAID5: 3,
                        RAID1: 2,
                        RAID0: 2}

    for raid, min_members in raid_min_members.items():
        if isRaid(raid, raidlevel):
            return min_members

    raise ValueError, "invalid raid level %d" % raidlevel

def get_raid_max_spares(raidlevel, nummembers):
    """Return the maximum number of raid spares for raidlevel."""
    raid_max_spares = {RAID10: lambda: max(0, nummembers - get_raid_min_members(RAID10)),
                       RAID6: lambda: max(0, nummembers - get_raid_min_members(RAID6)),
                       RAID5: lambda: max(0, nummembers - get_raid_min_members(RAID5)),
                       RAID1: lambda: max(0, nummembers - get_raid_min_members(RAID1)),
                       RAID0: lambda: 0}

    for raid, max_spares_func in raid_max_spares.items():
        if isRaid(raid, raidlevel):
            return max_spares_func()

    raise ValueError, "invalid raid level %d" % raidlevel

def mdcreate(device, level, disks, spares=0):
    argv = ["--create", device, "--run", "--level", str(level)]
    raid_devs = len(disks) - spares
    argv.append("--raid-devices=%d" % raid_devs)
    if spares:
        argv.append("--spare-devices=%d" % spares)
    argv.extend(disks)
    
    rc = iutil.execWithRedirect("mdadm",
                                argv,
                                stderr = "/dev/tty5",
                                stdout = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise MDRaidError("mdcreate failed for %s" % device)

    # mdadm insists on starting the new array, so we have to stop it here
    #self.mddeactivate(device)

def mddestroy(device):
    rc = iutil.execWithRedirect("mdadm",
                                ["--zero-superblock", device],
                                stderr = "/dev/tty5",
                                stdout = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise MDRaidError("mddestroy failed for %s" % device)

def mdadd(device):
    rc = iutil.execWithRedirect("mdadm",
                                ["--incremental", 
                                 "--quiet",
                                 "--auto=md",
                                 device],
                                stderr = "/dev/tty5",
                                stdout = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise MDRaidError("mdadd failed for %s" % device)

def mdactivate(device, members=[], super_minor=None, uuid=None):
    if super_minor is None and not uuid:
        raise ValueError("mdactivate requires either a uuid or a super-minor")
    
    if uuid:
        identifier = "--uuid=%s" % uuid
    elif super_minor is not None:
        identifier = "--super-minor=%d" % super_minor
    else:
        identifier = ""

    rc = iutil.execWithRedirect("mdadm",
                                ["--assemble",
                                 device,
                                 identifier,
                                 "--auto=md",
                                 "--update=super-minor"] + members,
                                stderr = "/dev/tty5",
                                stdout = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise MDRaidError("mdactivate failed for %s" % device)


def mddeactivate(device):
    rc = iutil.execWithRedirect("mdadm",
                                ["--stop", device],
                                stderr = "/dev/tty5",
                                stdout = "/dev/tty5",
                                searchPath=1)

    if rc:
        raise MDRaidError("mddeactivate failed for %s" % device)

def mdexamine(device):
    # XXX NOTUSED: we grab metadata from udev, which ran 'mdadm -E --export'
    #
    # FIXME: this will not work with version >= 1 metadata
    #
    # We should use mdadm -Eb or mdadm -E --export for a more easily
    # parsed output format.
    lines = iutil.execWithCapture("mdadm",
                                  ["--examine", device],
                                  stderr="/dev/tty5").splitlines()

    info = {
            'major': "-1",
            'minor': "-1",
            'uuid' : "",
            'level': -1,
            'nrDisks': -1,
            'totalDisks': -1,
            'mdMinor': -1,
        }

    for line in lines:
        (key, sep, val) = line.strip().partition(" : ")
        if not sep:
            continue
        if key == "Version":
            (major, sep, minor) = val.partition(".")
            info['major'] = major
            info['minor'] = minor
        elif key == "UUID":
            info['uuid'] = val.split()[0]
        elif key == "Raid Level":
            info['level'] = int(val[4:])
        elif key == "Raid Devices":
            info['nrDisks'] = int(val)
        elif key == "Total Devices":
            info['totalDisks'] = int(val)
        elif key == "Preferred Minor":
            info['mdMinor'] = int(val)
        else:
            continue

    if not info['uuid']:
        raise MDRaidError("UUID missing from device info")

    return info

