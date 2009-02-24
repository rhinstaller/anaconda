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

def getRaidLevels():
    avail = []
    try:
        f = open("/proc/mdstat", "r")
    except:
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

# FIXME: these functions should be consolidated into one function
def isRaid10(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID10."""
    return raidlevel in ("RAID10", "10", 10)

def isRaid6(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID6."""
    return raidlevel in ("RAID6", "6", 6)

def isRaid5(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID5."""
    return raidlevel in ("RAID5", "5", 5)

def isRaid1(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID1."""
    return raidlevel in ("mirror", "RAID1", "1", 1)

def isRaid0(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID0."""
    return raidlevel in ("stripe", "RAID0", "0", 0)

def get_raid_min_members(raidlevel):
    """Return the minimum number of raid members required for raid level"""
    if isRaid0(raidlevel):
        return 2
    elif isRaid1(raidlevel):
        return 2
    elif isRaid5(raidlevel):
        return 3
    elif isRaid6(raidlevel):
        return 4
    elif isRaid10(raidlevel):
        return 4
    else:
        raise ValueError, "invalid raidlevel in get_raid_min_members"

def get_raid_max_spares(raidlevel, nummembers):
    """Return the maximum number of raid spares for raidlevel."""
    if isRaid0(raidlevel):
        return 0
    elif isRaid1(raidlevel) or isRaid5(raidlevel) or \
         isRaid6(raidlevel) or isRaid10(raidlevel):
        return max(0, nummembers - get_raid_min_members(raidlevel))
    else:
        raise ValueError, "invalid raidlevel in get_raid_max_spares"

def mdcreate(device, level, disks, spares=0):
    argv = ["--create", device, "--level", str(level)]
    raid_devs = len(disks) - spares
    argv.append("--raid-devices=%d" % raid_devs)
    if spares:
        argv.append("--spare-devices=%d" % spares)
    argv.extend(disks)
    
    rc = iutil.execWithRedirect("mdadm",
                                argv,
                                stderr = "/dev/null",
                                stdout = "/dev/null",
                                searchPath=1)

    if rc:
        raise MDRaidError("mdcreate failed for %s" % device)

    # mdadm insists on starting the new array, so we have to stop it here
    #self.mddeactivate(device)

def mddestroy(device):
    rc = iutil.execWithRedirect("mdadm",
                                ["--zero-superblock", device],
                                stderr = "/dev/null",
                                stdout = "/dev/null",
                                searchPath=1)

    if rc:
        raise MDRaidError("mddestroy failed for %s" % device)

def mdadd(device):
    # XXX NOTUSED: mdadm -I is broken and dledford says it should be
    #              avoided if possible, so we used mdadm -A instead
    rc = iutil.execWithRedirect("mdadm",
                                ["--incremental", 
                                 "--quiet",
                                 "--auto=yes",
                                 device],
                                stderr = "/dev/null",
                                stdout = "/dev/null",
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

    filename = None
    if members:
        from tempfile import mkstemp
        (fd, filename) = mkstemp(prefix="%s_devices." % device,
                                     dir="/tmp",
                                     text=True)
        os.write(fd, "DEVICE %s\n" % " ".join(members))
        config_arg = "--config=%s" % filename
        os.close(fd)
        del mkstemp
    else:
        config_arg = ""

    rc = iutil.execWithRedirect("mdadm",
                                ["--assemble",
                                 config_arg,
                                 device,
                                 identifier,
                                 "--auto=md",
                                 "--update=super-minor"],
                                stderr = "/dev/null",
                                stdout = "/dev/null",
                                searchPath=1)

    if filename and os.access(filename, os.R_OK):
        try:
            os.unlink(filename)
        except OSError, e:
            log.debug("unlink of %s failed: %s" % (filename, e))

    if rc:
        raise MDRaidError("mdactivate failed for %s" % device)


def mddeactivate(device):
    rc = iutil.execWithRedirect("mdadm",
                                ["--stop", device],
                                stderr = "/dev/null",
                                stdout = "/dev/null",
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
                                  stderr="/dev/null").splitlines()

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

