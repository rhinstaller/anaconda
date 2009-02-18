#!/usr/bin/python
#
# raid.py - raid probing control
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""Raid probing control."""

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

# XXX define availraidlevels and defaultmntpts as arch characteristics
availRaidLevels = getRaidLevels()

import parted
import isys
import os
import partitioning
import partitions
import partedUtils

import logging
log = logging.getLogger("anaconda")

# these arches can have their /boot on RAID and not have their
# boot loader blow up
raidBootArches = [ "i386", "x86_64", "ppc" ]

def scanForRaid(drives):
    """Scans for raid devices on drives.

    drives is a list of device names.
    Returns a list of (mdMinor, devices, level, totalDisks) tuples.
    """
    
    raidSets = {}
    raidDevices = {}
    encryptedDevices = partitions.Partitions.encryptedDevices

    for d in drives:
        parts = []
	isys.makeDevInode(d, "/tmp/" + d)
        try:
            dev = parted.PedDevice.get("/tmp/" + d)
            disk = parted.PedDisk.new(dev)

            raidParts = partedUtils.get_raid_partitions(disk)
            for part in raidParts:
                # if the part is encrypted, add the mapped dev instead
                pname = partedUtils.get_partition_name(part)
                cryptoDev = encryptedDevices.get(pname)
                if cryptoDev and not cryptoDev.openDevice():
                    dev = cryptoDev.getDevice()
                else:
                    dev = pname
                parts.append(dev)
        except:
            pass

	os.remove("/tmp/" + d)
        for dev in parts:
            try:
                (major, minor, raidSet, level, nrDisks, totalDisks, mdMinor) =\
                        isys.raidsb(dev)
            except ValueError:
                # bad magic, this can't be part of our raid set
                log.error("reading raid sb failed for %s",dev)
                continue

	    if raidSets.has_key(raidSet):
	    	(knownLevel, knownDisks, knownMinor, knownDevices) = \
			raidSets[raidSet]
		if knownLevel != level or knownDisks != totalDisks or \
		   knownMinor != mdMinor:
                    # Raise hell
		    log.error("raid set inconsistency for md%d: "
                              "all drives in this raid set do not "
                              "agree on raid parameters.  Skipping raid device",
                              mdMinor)
                    continue
		knownDevices.append(dev)
		raidSets[raidSet] = (knownLevel, knownDisks, knownMinor,
				     knownDevices)
	    else:
		raidSets[raidSet] = (level, totalDisks, mdMinor, [dev,])

	    if raidDevices.has_key(mdMinor):
	    	if (raidDevices[mdMinor] != raidSet):
		    log.error("raid set inconsistency for md%d: "
                              "found members of multiple raid sets "
                              "that claim to be md%d.  Using only the first "
                              "array found.", mdMinor, mdMinor)
                    continue
	    else:
	    	raidDevices[mdMinor] = raidSet

    raidList = []
    for key in raidSets.keys():
	(level, totalDisks, mdMinor, devices) = raidSets[key]
	if len(devices) < totalDisks:
            log.warning("missing components of raid device md%d.  The "
                        "raid device needs %d drive(s) and only %d (was/were) "
                        "found. This raid device will not be started.", mdMinor,
                        totalDisks, len(devices))
	    continue
	raidList.append((mdMinor, devices, level, totalDisks))

    return raidList
		
def startAllRaid(driveList):
    """Do a raid start on raid devices and return a list like scanForRaid."""
    rc = []
    mdList = scanForRaid(driveList)
    for mdDevice, deviceList, level, numActive in mdList:
    	devName = "md%d" % (mdDevice,)
	isys.raidstart(devName, deviceList[0])
        rc.append((devName, deviceList, level, numActive))
    return rc

def stopAllRaid(mdList):
    """Do a raid stop on each of the raid device tuples given."""
    for dev, devices, level, numActive in mdList:
	isys.raidstop(dev)

def isRaid10(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID10."""
    if raidlevel in ("RAID10", "10", 10):
        return True
    return False

def isRaid6(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID6."""
    if raidlevel in ("RAID6", "6", 6):
        return True
    return False

def isRaid5(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID5."""
    if raidlevel in ("RAID5", "5", 5):
        return True
    return False

def isRaid1(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID1."""
    if raidlevel in ("mirror", "RAID1", "1", 1):
        return True
    return False

def isRaid0(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID0."""
    if raidlevel in ("stripe", "RAID0", "0", 0):
        return True
    return False

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
        return 2
    else:
        raise ValueError, "invalid raidlevel in get_raid_min_members"

def get_raid_max_spares(raidlevel, nummembers):
    """Return the maximum number of raid spares for raidlevel."""
    if isRaid0(raidlevel):
        return 0
    elif isRaid1(raidlevel) or isRaid5(raidlevel) or isRaid6(raidlevel) or isRaid10(raidlevel):
        return max(0, nummembers - get_raid_min_members(raidlevel))
    else:
        raise ValueError, "invalid raidlevel in get_raid_max_spares"

def register_raid_device(mdname, newdevices, newlevel, newnumActive):
    """Register a new RAID device in the mdlist."""
    for dev, devices, level, numActive in partedUtils.DiskSet.mdList:
        if mdname == dev:
            if (devices != newdevices or level != newlevel or
                numActive != newnumActive):
                raise ValueError, "%s is already in the mdList!" % (mdname,)
            else:
                return
    partedUtils.DiskSet.mdList.append((mdname, newdevices[:], newlevel,
                                       newnumActive))

def lookup_raid_device(mdname):
    """Return the requested RAID device information."""
    for dev, devices, level, numActive in partedUtils.DiskSet.mdList:
        if mdname == dev:
            return (dev, devices, level, numActive)
    raise KeyError, "md device not found"


