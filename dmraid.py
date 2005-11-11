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

import logging
log = logging.getLogger("anaconda.dmraid")
import isys

# these arches can have their /boot on DMRAID and not have their
# boot loader blow up
# XXX This needs to be functional so it can test if drives sit on particular
# controlers. -pj
dmraidBootArches = [ "i386", "x86_64" ]

class DegradedRaidWarning(Warning):
    def __init__(self, *args):
        self.args = args
    def __str__(self):
        return self.args and ('%s' % self.args[0]) or repr(self)

def getRaidSetDisks(rs, descend=False):
    """Builds a list of disks used by a dmraid set

    rs is a block.dmraid.raidset instance
    Returns a list of parted.PedDevice instances.
    """

    if not isinstance(rs, block.dmraid.raidset):
        raise TypeError, "getRaidSetInfo needs raidset, got %s" % (rs.__type__,)

    devs = []
    for c in rs.children:
        if isinstance(c, block.dmraid.raiddev):
            dev = parted.PedDevice.get(c.device.path)
            devs.append(dev)
        elif descend and isinstance(c, block.dmraid.raidset): 
            devs += getRaidSetDisks(c)
    return devs

# This is a placeholder, because "spares" isn't implemented in
# block.dmraid.raidset yet; once dmraid has support for SNIA DDF or
# fake raid 5, I'll add it. -pj
def getRaidSetSpareDisks(rs, descend=False):
    """Builds a list of disks used as spares by a dmraid set

    rs is a block.dmraid.raidset instance
    Returns a list of parted.PedDevice instances.
    """

    if not isinstance(rs, block.dmraid.raidset):
        raise TypeError, "getRaidSetInfo needs raidset, got %s" % (rs.__type__,)

    devs = []
    if hasattr(rs, 'spares'):
        for c in rs.spares:
            if isinstance(c, block.dmraid.raiddev):
                dev = parted.PedDevice.get(c.device.path)
                devs.append(dev)
            elif descend and isinstance(c, block.dmraid.raidset): 
                devs += getRaidSetSpareDisks(c, descend)
    # children might have spares, too.
    for c in rs.children:
        if descend and isinstance(c, block.dmraid.raidset):
            devs += getRaidSetSpareDisks(c, descend)
    return devs

def getRaidSetInfo(rs):
    """Builds information about a dmraid set
    
    rs is a block.dmraid.raidset instance
    Returns a list of tuples for this raidset and its
      dependencies, in sorted order, of the form
      (raidSet, parentRaidSet, devices, level, nrDisks, totalDisks)
    """

    if not isinstance(rs, block.dmraid.raidset):
        raise TypeError, "getRaidSetInfo needs raidset, got %s" % (rs.__type__,)

    sets = []
    for c in rs.children:
        if isinstance(c, block.dmraid.raidset):
            infos = getRaidSetInfo(c)
            for info in infos:
                if info[1] is None:
                    info[1] = rs
            sets += infos

    try:
        parent = None

        devs = getRaidSetDisks(rs)
        sparedevs = getRaidSetSpareDisks(rs)

        totalDisks = len(devs) + len(sparedevs)
        nrDisks = len(devs)
        devices = devs + sparedevs

        # XXX missing some types here -pj
        dmtype2level = { 'stripe': 0, 'mirror': 1, }
        level = dmtype2level[rs.dmtype]

        sets.append((rs, parent, devices, level, nrDisks, totalDisks))
    except:
        # something went haywire
        log.error("Exception occurred reading info for %s: %s" % \
            (repr(rs), (sys.exc_type, ))) # XXX PJFIX sys.exc_info)))
        raise

    return sets

def scanForRaid(drives):
    """Scans for dmraid devices on drives.

    drives is a list of device names.
    Returns a list of (raidSet, parentRaidSet, devices, level, totalDisks)
      tuples.
    """

    Sets = {}
    Devices = {}

    probeDrives = []
    for d in drives:
        dp = "/tmp/" + d
        isys.makeDevInode(d, dp)
        probeDrives.append(dp)
    
    dmsets = block.RaidSets(probeDrives)
    rets = []
    for dmset in dmsets:
        infos = getRaidSetInfo(dmset)

        for info in infos:
            rets.append(info)
            #(rs, parent, devices, level, nrDisks, totalDisks) = info
    return rets

def startRaidDev(rs, degradedOk=False):
    if rs.total_devs > rs.found_devs and not degradedOk:
        raise DegradedRaidWarning, rs
    name = str(rs)
    table = rs.dmTable

    block.dm.map(name=name, table=table)

def startAllRaid(driveList):
    """Do a raid start on raid devices and return a list like scanForRaid."""
    rc = []
    dmList = scanForRaid(driveList)
    for dmset in dmList:
        rs, parent, devices, level, nrDisks, totalDisks = dmset
        startRaidDev(rs, False)
        rc.append(dmset)

    return rc

def stopAllRaid(dmList):
    """Do a raid stop on each of the raid device tuples given."""

    maplist = block.dm.list()
    maps = {}
    for m in maplist:
        maps[m.name] = m
    del maplist
        
    for dmset in dmList:
        name = str(dmset[0])
        map = maps[name]
        try:
            map.remove()
        except:
            pass
