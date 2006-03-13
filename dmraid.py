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
import string
import block
import partedUtils
import raid
from flags import flags

import logging
from anaconda_log import logger, logFile

logger.addLogger ("anaconda.dmraid", minLevel=logging.DEBUG)
log = logging.getLogger("anaconda.dmraid")
logger.addFileHandler (logFile, log)

import isys

# these arches can have their /boot on DMRAID and not have their
# boot loader blow up
# XXX This needs to be functional so it can test if drives sit on particular
# controlers. -pj
dmraidBootArches = [ "i386", "x86_64" ]

dmNameUpdates = {}

class DmDriveCache:
    def __init__(self):
        self.cache = {}

    def add(self, rs):
        isys.cachedDrives["mapper/" + rs.name] = rs
        log.debug("adding %s to isys cache" % ("mapper/" + rs.name,))
        for m in rs.members:
            if isinstance(m, block.RaidDev):
                disk = m.rd.device.path.split('/')[-1]
                if isys.cachedDrives.has_key(disk):
                    self.cache.setdefault(rs.name, {})
                    self.cache[rs.name][rs.name] = rs
                    log.debug("adding %s to dmraid cache" % (disk,))
                    self.cache[rs.name][disk] = isys.cachedDrives[disk]
                    log.debug("removing %s from isys cache" % (disk,))
                    del isys.cachedDrives[disk]

    def remove(self, name):
        if isys.cachedDrives.has_key(name):
            rs = isys.cachedDrives[name]
            log.debug("removing %s from isys cache" % (name,))
            del isys.cachedDrives[name]
            if self.cache.has_key(rs.name):
                del self.cache[rs.name][rs.name]
                for k,v in self.cache[rs.name].items():
                    log.debug("adding %s from to isys cache" % (name,))
                    isys.cachedDrives[k] = v
                log.debug("removing %s from dmraid cache" % (rs,))
                del self.cache[rs.name]

    def rename(self, rs, newname):
        oldname = 'mapper/' + rs.name
        if isys.cachedDrives.has_key(oldname):
            dmNameUpdates[rs.name] = newname
            self.remove(oldname)
            # XXX why doesn't setting the property work?
            rs.set_name(newname)
            self.add(rs)

    def __contains__(self, name):
        for k in self.cache.keys():
            if k.name == name:
                return True
        return False

cacheDrives = DmDriveCache()

class DegradedRaidWarning(Warning):
    def __init__(self, *args):
        self.args = args
    def __str__(self):
        return self.args and ('%s' % self.args[0]) or repr(self)

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
        dp = "/dev/" + d
        isys.makeDevInode(d, dp)
        probeDrives.append(dp)
        dp = "/tmp/" + d
        isys.makeDevInode(d, dp)
    
    dmsets = []
    def nonDegraded(rs):
        log.debug("got raidset %s (%s)" % (rs, string.join(rs.member_devpaths)))
        log.debug("  valid: %s found_devs: %s total_devs: %s" % (rs.valid, rs.rs.found_devs, rs.rs.total_devs))

        if not rs.valid and not degradedOk:
            log.warning("raid %s (%s) is degraded" % (rs, rs.name))
            #raise DegradedRaidWarning, rs
            return False
        return True

    raidsets = filter(nonDegraded, block.getRaidSets(probeDrives) or [])
    def updateName(rs):
        if dmNameUpdates.has_key(rs.name):
            rs.set_name(dmNameUpdates[rs.name])
        cacheDrives.add(rs)
        return rs
        
    return reduce(lambda x,y: x + [updateName(y),], raidsets, [])

def renameRaidSet(rs, name):
    cacheDrives.rename(rs, name)
            
def startRaidDev(rs):
    if flags.dmraid == 0:
        return
    rs.prefix = '/dev/mapper/'
    log.debug("starting raid %s with mknod=True" % (rs,))
    rs.activate(mknod=True)

def startAllRaid(driveList):
    """Do a raid start on raid devices."""

    if not flags.dmraid:
        return []
    log.debug("starting all dmraids on drives %s" % (driveList,))

    dmList = scanForRaid(driveList)
    for rs in dmList:
        startRaidDev(rs)
    return dmList

def stopRaidSet(rs):
    if flags.dmraid == 0:
        return
    log.debug("stopping raid %s" % (rs,))
    name = "mapper/" + rs.name
    if name in cacheDrives:
        cacheDrives.remove(name)

        rs.deactivate()
        #block.removeDeviceMap(map)

def stopAllRaid(dmList):
    """Do a raid stop on each of the raid device tuples given."""

    if not flags.dmraid:
        return
    log.debug("stopping all dmraids")
    for rs in dmList:
        stopRaidSet(rs)

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
