#!/usr/bin/python
#
# dmraid.py - dmraid probing control
#
# Peter Jones <pjones@redhat.com>
#
# Copyright 2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""DMRaid probing control."""
# XXX dmraid and md raid should be abstracted from the same thing. -pj
# XXX dmraid and lvm should use a common control mechanism (such as block.dm)
#     for device-mapper. -pj

import sys
import block
import parted
import raid
from flags import flags

import logging
log = logging.getLogger("anaconda.dmraid")
import isys

# these arches can have their /boot on DMRAID and not have their
# boot loader blow up
# XXX This needs to be functional so it can test if drives sit on particular
# controlers. -pj
dmraidBootArches = [ "i386", "x86_64" ]

cachedDrives = {}

class DegradedRaidWarning(Warning):
    def __init__(self, *args):
        self.args = args
    def __str__(self):
        return self.args and ('%s' % self.args[0]) or repr(self)

def getRaidSetInfo(rs):
    """Builds information about a dmraid set
    
    rs is a block.dmraid.raidset instance
    Returns a list of tuples for this raidset and its
      dependencies, in sorted order, of the form
      (raidSet, parentRaidSet, devices, level, nrDisks, totalDisks)
    """

    if not isinstance(rs, block.RaidSet):
        raise TypeError, "getRaidSetInfo needs raidset, got %s" % (rs.__class__,)

    for m in rs.members:
        if isinstance(m, block.RaidSet):
            infos = getRaidSetInfo(m)
            for info in infos:
                if info[1] is None:
                    info[1] = rs
                yield info

    try:
        parent = None

        devs = list(rs.members)
        sparedevs = list(rs.spares)

        totalDisks = len(devs) + len(sparedevs)
        nrDisks = len(devs)
        devices = devs + sparedevs

        level = rs.level

        yield (rs, parent, devices, level, nrDisks, totalDisks)
    except:
        # something went haywire
        log.error("Exception occurred reading info for %s: %s" % \
            (repr(rs), (sys.exc_type, ))) # XXX PJFIX sys.exc_info)))
        raise

def scanForRaid(drives, degradedOk=False):
    """Scans for dmraid devices on drives.

    drives is a list of device names.
    Returns a list of (raidSet, parentRaidSet, devices, level, totalDisks)
      tuples.
    """

    log.debug("scanning for dmraid on drives %s" % (drives,))
    Sets = {}
    Devices = {}

    probeDrives = []
    for d in drives:
        dp = "/tmp/" + d
        isys.makeDevInode(d, dp)
        probeDrives.append(dp)
    
    dmsets = block.getRaidSets(probeDrives)
    for dmset in dmsets:
        infos = getRaidSetInfo(dmset)
        for info in infos:
            rs = info[0]
            log.debug("got raidset %s" % (rs,))

            # XXX not the way to do this; also, need to inform the user
            if rs.rs.total_devs > rs.rs.found_devs \
                    and not degradedOk:
                #raise DegradedRaidWarning, rs
                continue
            #(rs, parent, devices, level, nrDisks, totalDisks) = info
            # XXX ewwwww, what a hack.
            isys.cachedDrives["mapper/" + rs.name] = rs
            drives = []
            for m in rs.members:
                if isinstance(m, block.RaidDev):
                    disk = m.rd.device.path.split('/')[-1]
                    if isys.cachedDrives.has_key(disk):
                        drives.append({disk:isys.cachedDrives[disk]})
                        del isys.cachedDrives[disk]
            cachedDrives[rs] = drives
            yield info

def startRaidDev(rs):
    if flags.dmraid == 0:
        return
    rs.prefix = '/tmp/mapper/'
    log.debug("starting raid %s with mknod=True" % (rs,))
    rs.activate(mknod=True)

def startAllRaid(driveList):
    """Do a raid start on raid devices and return a list like scanForRaid."""

    if flags.dmraid == 0:
        return
    log.debug("starting all dmraids on drives %s" % (driveList,))
    dmList = scanForRaid(driveList)
    for dmset in dmList:
        rs = dmset[0]
        startRaidDev(rs)
        yield dmset

def stopRaidSet(rs):
    if flags.dmraid == 0:
        return
    log.debug("stopping raid %s" % (rs,))
    if isys.cachedDrives.has_key("mapper/" + rs.name):
        del isys.cachedDrives["mapper/" + rs.name]
    if cachedDrives.has_key(rs):
        for item in cachedDrives[rs]:
            isys.cachedDrives[item.keys()[0]] = item.values()[0]

    rs.deactivate()
    #block.removeDeviceMap(map)

def stopAllRaid(dmList):
    """Do a raid stop on each of the raid device tuples given."""

    if flags.dmraid == 0:
        return
    import traceback as _traceback
    stack = _traceback.format_stack()
    for frame in stack:
        log.debug(frame)
    log.debug("stopping all dmraids")
    for rs in dmList:
        stopRaidSet(rs[0])

def isRaid6(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID6."""
    return False

def isRaid5(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID5."""
    return False

def isRaid1(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID1."""
    return raid.isRaid1(raidlevel)

def isRaid0(raidlevel):
    """Return whether raidlevel is a valid descriptor of RAID1."""
    return raid.isRaid0(raidlevel)

def get_raid_min_members(raidlevel):
    """Return the minimum number of raid members required for raid level"""
    return raid.get_raid_min_members(raidlevel)

def get_raid_max_spares(raidlevel, nummembers):
    """Return the maximum number of raid spares for raidlevel."""
    return raid.get_raid_max_spares(raidlevel, nummembers)

def register_raid_device(dmname, newdevices, newlevel, newnumActive):
    """Register a new RAID device in the dmlist."""
    raise NotImplementedError

def lookup_raid_device(dmname):
    """Return the requested RAID device information."""
    for rs, parent, devices, level, nrDisks, totalDisks in \
            partedUtils.DiskSet.dmList:
        if dmname == rs.name:
            return (rs.name, devices, level, totalDisks)
    raise KeyError, "dm device not found"
