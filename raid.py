#!/usr/bin/python
#
# raid.py - raid probing control
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

# XXX partedify

import _balkan
import isys
import os
from log import log

def scanForRaid(drives):
    raidSets = {}
    raidDevices = {}

    for d in drives:
	isys.makeDevInode(d, "/tmp/" + d)
	try:
	    parts = _balkan.readTable('/tmp/' + d)
	except SystemError, msg:
	    parts = []

	os.remove("/tmp/" + d)
	for i in range(0, len(parts)):
	    (type, start, size) = parts[i]
	    if type != _balkan.RAID: continue

	    dev = "%s%d" % (d, i + 1)

            try:
                (major, minor, raidSet, level, nrDisks, totalDisks, mdMinor) =\
                        isys.raidsb(dev)
            except ValueError:
                # bad magic, this can't be part of our raid set
                continue

	    if raidSets.has_key(raidSet):
	    	(knownLevel, knownDisks, knownMinor, knownDevices) = \
			raidSets[raidSet]
		if knownLevel != level or knownDisks != totalDisks or \
		   knownMinor != mdMinor:
                    # Raise hell
		    log("raid set inconsistency for md%d: "
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
		    log("raid set inconsistency for md%d: "
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
            log("missing components of raid device md%d.  The "
                "raid device needs %d drives and only %d were found. "
                "This raid device will not be started.", mdMinor,
                len(devices), totalDisks)
	    continue
	raidList.append((mdMinor, devices, level, totalDisks))

    return raidList
		
def startAllRaid(driveList):
    rc = []
    mdList = scanForRaid(driveList)
    for mdDevice, deviceList, level, numActive in mdList:
    	devName = "md%d" % (mdDevice,)
	isys.raidstart(devName, deviceList[0])
        rc.append((devName, deviceList, level, numActive))
    return rc

def stopAllRaid(mdList):
    for dev, devices, level, numActive in mdList:
	isys.raidstop(dev)
