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

_bdModulePath = ":/tmp/updates/bdevid/:/mnt/source/RHupdates/bdevid/"
import block
block.setBdevidPath(block.getBdevidPath() + _bdModulePath)

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

    def _addMapDevs(self, name, devs, obj):
        isys.cachedDrives["mapper/" + name] = obj
        log.debug("adding %s to isys cache" % ("mapper/" + name,))
        for dev in devs:
            disk = dev.split('/')[-1]
            if isys.cachedDrives.has_key(disk):
                self.cache.setdefault(obj.name, {})
                self.cache[obj.name][obj.name] = obj
                log.debug("adding %s to dm cache" % (disk,))
                self.cache[obj.name][disk] = isys.cachedDrives[disk]
                log.debug("removing %s from isys cache" % (disk,))
                del isys.cachedDrives[disk]

    def add(self, obj):
        if isinstance(obj, block.MultiPath):
            return self._addMapDevs(obj.name, obj.bdevs, obj)
        else:
            members = []
            for m in obj.members:
                if isinstance(m, block.RaidDev):
                    members.append(m.rd.device.path)
            return self._addMapDevs(obj.name, members, obj)

    def remove(self, name):
        objname = "mapper/" + name
        if  isys.cachedDrives.has_key(objname):
            obj = isys.cachedDrives[objname]
            log.debug("removing %s from isys cache" % (objname,))
            del isys.cachedDrives[objname]
            if self.cache.has_key(obj.name):
                del self.cache[obj.name][obj.name]
                for k,v in self.cache[obj.name].items():
                    log.debug("adding %s to isys cache" % (k,))
                    isys.cachedDrives[k] = v
                log.debug("removing %s from dm cache" % (obj,))
                del self.cache[obj.name]

    def rename(self, obj, newname):
        oldname = 'mapper/' + obj.name
        if isys.cachedDrives.has_key(oldname):
            dmNameUpdates[obj.name] = newname
            self.remove(obj.name)
            # XXX why doesn't setting the property work?
            obj.set_name(newname)
            self.add(obj)

    def __contains__(self, name):
        return self.cache.has_key(name)

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
            
def startAllRaid(driveList):
    """Do a raid start on raid devices."""

    if not flags.dmraid:
        return []
    log.debug("starting all dmraids on drives %s" % (driveList,))

    try:
        dmList = scanForRaid(driveList)
    except Exception, e:
        log.error("error scanning dmraid, disabling: %s" %(e,))
        flags.dmraid = 0
        dmList = []
        
    newDmList = []
    for rs in dmList:
        rs.prefix = '/dev/mapper/'
        log.debug("starting raid %s with mknod=True" % (rs,))
        try:
            rs.activate(mknod=True)
            newDmList.append(rs)
        except Exception, e:
            log.error("Activating raid %s failed: " % (rs.rs,))
            log.error("  table: %s" % (rs.rs.table,))
            log.error("  exception: %s" % (e,))
            try:
                rs.deactivate()
                del rs
            except:
                pass

    return newDmList

def stopAllRaid(dmList):
    """Do a raid stop on each of the raid device tuples given."""

    if not flags.dmraid:
        return
    log.debug("stopping all dmraids")
    for rs in dmList:
        log.debug("stopping raid %s" % (rs,))
        if rs.name in cacheDrives:
            cacheDrives.remove(rs.name)

            rs.deactivate()
            #block.removeDeviceMap(map)

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

def scanForMPath(drives):
    log.debug("scanning for multipath on drives %s" % (drives,))
    mpaths = []

    probeDrives = []
    for d in drives:
        dp = "/dev/" + d
        isys.makeDevInode(d, dp)
        probeDrives.append(dp)
        dp = "/tmp/" + d
        isys.makeDevInode(d, dp)

    import block as _block
    _block.setBdevidPath(_block.getBdevidPath() + _bdModulePath)

    _block.load("scsi")
    mpaths = _block.getMPaths(probeDrives)
    log.debug("mpaths: %s" % (mpaths,))
    
    def updateName(mp):
        if dmNameUpdates.has_key(mp.name):
            mp.set_name(dmNameUpdates[mp.name])
        cacheDrives.add(mp)
        return mp
    
    return reduce(lambda x,y: x + [updateName(y),], mpaths, [])

def renameMPath(mpath, name):
    cacheDrives.rename(mpath, name)

def startMPath(mpath):
    if flags.mpath == 0:
        return
    mpath.prefix = '/dev/mapper/'
    log.debug("starting mpath %s with mknod=True" % (mpath,))
    mpath.activate(mknod=True)

def startAllMPath(driveList):
    """Start all of the MPaths of the specified drives."""

    if not flags.mpath:
        return []
    log.debug("starting all mpaths on drives %s" % (driveList,))

    try:
        mpList = scanForMPath(driveList)
    except Exception, e:
        log.error("error scanning mpaths, disabling: %s" %(e,))
        flags.mpath = 0
        mpList = []
        
    for mp in mpList:
        startMPath(mp)
    return mpList

def stopMPath(mp):
    if flags.mpath == 0:
        return

    log.debug("stopping mpath %s" % (mp,))
    if mp.name in cacheDrives:
        cacheDrives.remove(mp.name)

        mp.deactivate()
        #block.removeDeviceMap(map)

def stopAllMPath(mpList):
    """Do a mpath stop on each of the mpath device tuples given."""

    if not flags.mpath:
        return
    log.debug("stopping all mpaths")
    for mp in mpList:
        stopMPath(mp)

