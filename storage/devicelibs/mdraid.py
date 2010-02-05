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
RAID4 = 4
RAID1 = 1
RAID0 = 0

def getRaidLevels():
    mdstat_descriptors = {
        RAID10: ("[RAID10]", "[raid10]"),
        RAID6: ("[RAID6]", "[raid6]"),
        RAID5: ("[RAID5]", "[raid5]"),
        RAID4: ("[RAID4]", "[raid4]"),
        RAID1: ("[RAID1]", "[raid1]"),
        RAID0: ("[RAID0]", "[raid0]"),
    }
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

            for level in mdstat_descriptors:
                for d in mdstat_descriptors[level]:
                    if d in lst:
                        avail.append(level)
                        break

        f.close()

    avail.sort()
    return avail

raid_levels = getRaidLevels()

def raidLevel(descriptor):
    for level in raid_levels:
        if isRaid(level, descriptor):
            return level
    else:
        raise ValueError, "invalid raid level descriptor %s" % descriptor

def isRaid(raid, raidlevel):
    """Return whether raidlevel is a valid descriptor of raid"""
    raid_descriptors = {RAID10: ("RAID10", "raid10", "10", 10),
                        RAID6: ("RAID6", "raid6", "6", 6),
                        RAID5: ("RAID5", "raid5", "5", 5),
                        RAID4: ("RAID4", "raid4", "4", 4),
                        RAID1: ("mirror", "RAID1", "raid1", "1", 1),
                        RAID0: ("stripe", "RAID0", "raid0", "0", 0)}

    if raid in raid_descriptors:
        return raidlevel in raid_descriptors[raid]
    else:
        raise ValueError, "invalid raid level %d" % raid

def get_raid_min_members(raidlevel):
    """Return the minimum number of raid members required for raid level"""
    raid_min_members = {RAID10: 2,
                        RAID6: 4,
                        RAID5: 3,
                        RAID4: 3,
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
                       RAID4: lambda: max(0, nummembers - get_raid_min_members(RAID4)),
                       RAID1: lambda: max(0, nummembers - get_raid_min_members(RAID1)),
                       RAID0: lambda: 0}

    for raid, max_spares_func in raid_max_spares.items():
        if isRaid(raid, raidlevel):
            return max_spares_func()

    raise ValueError, "invalid raid level %d" % raidlevel

def mdadm(args, progress=None):
    rc = iutil.execWithPulseProgress("mdadm", args,
                                     stdout = "/dev/tty5",
                                     stderr = "/dev/tty5",
                                     progress=progress)
    if not rc:
        return

    try:
        # grab the last line of program.log and strip off the timestamp
        msg = open("/tmp/program.log").readlines()[-1]
        msg = msg.split("program: ", 1)[1].strip()
    except Exception:
        msg = ""

    raise MDRaidError(msg)

def mdcreate(device, level, disks, spares=0, metadataVer=None, bitmap=False,
             progress=None):
    argv = ["--create", device, "--run", "--level=%s" % level]
    raid_devs = len(disks) - spares
    argv.append("--raid-devices=%d" % raid_devs)
    if spares:
        argv.append("--spare-devices=%d" % spares)
    if metadataVer:
        argv.append("--metadata=%s" % metadataVer)
    if bitmap:
        argv.append("--bitmap=internal")
    argv.extend(disks)
    
    try:
        mdadm(argv, progress=progress)
    except MDRaidError as msg:
        raise MDRaidError("mdcreate failed for %s: %s" % (device, msg))

def mddestroy(device):
    args = ["--zero-superblock", device]

    try:
        mdadm(args)
    except MDRaidError as msg:
        raise MDRaidError("mddestroy failed for %s: %s" % (device, msg))

def mdadd(device, no_degraded=False):
    args = ["--incremental", "--quiet"]
    if no_degraded:
        args.append("--no-degraded")
    args.append(device)

    try:
        mdadm(args)
    except MDRaidError as msg:
        raise MDRaidError("mdadd failed for %s: %s" % (device, msg))

def mdactivate(device, members=[], super_minor=None, update_super_minor=False,
               uuid=None):
    if super_minor is None and not uuid:
        raise ValueError("mdactivate requires either a uuid or a super-minor")
    
    if uuid:
        identifier = "--uuid=%s" % uuid
    elif super_minor is not None:
        identifier = "--super-minor=%d" % super_minor
    else:
        identifier = ""

    if update_super_minor:
        extra_args = ["--update=super-minor"]
    else:
        extra_args = [ ]

    args = ["--assemble", device, identifier, "--run", "--auto=md"]
    args += extra_args
    args += members

    try:
        mdadm(args)
    except MDRaidError as msg:
        raise MDRaidError("mdactivate failed for %s: %s" % (device, msg))

def mddeactivate(device):
    args = ["--stop", device]

    try:
        mdadm(args)
    except MDRaidError as msg:
        raise MDRaidError("mddeactivate failed for %s: %s" % (device, msg))

def mdexamine(device):
    vars = iutil.execWithCapture("mdadm",
                                 ["--examine", "--brief", device],
                                 stderr="/dev/tty5").split()

    info = {}
    if vars:
        try:
            info["device"] = vars[1]
            vars = vars[2:]
        except IndexError:
            return {}

    for var in vars:
        (name, equals, value) = var.partition("=")
        if not equals:
            continue

        info[name.lower()] = value.strip()

    return info

