#!/usr/bin/python

import _balkan
import isys
import os

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
		    raise SystemError, "raid set inconsistency for md%d" % \
				(mdMinor)
		knownDevices.append(dev)
		raidSets[raidSet] = (knownLevel, knownDisks, knownMinor,
				     knownDevices)
	    else:
		raidSets[raidSet] = (level, totalDisks, mdMinor, [dev,])

	    if raidDevices.has_key(mdMinor):
	    	if (raidDevices[mdMinor] != raidSet):
		    raise SystemError, "raid set inconsistency for md%d" % \
				(mdMinor)
	    else:
	    	raidDevices[mdMinor] = raidSet

    raidList = []
    for key in raidSets.keys():
	(level, totalDisks, mdMinor, devices) = raidSets[key]
	if len(devices) < totalDisks:
	    str = "missing components of raid device md%d" % (mdMinor,)
	    raise SystemError, str
	raidList.append((mdMinor, devices))

    return raidList
		
def startAllRaid(driveList):
    mdList = []
    for (mdDevice, deviceList) in scanForRaid(driveList):
    	devName = "md%d" % (mdDevice,)
	isys.raidstart(devName, deviceList[0])
	mdList.append(devName)
    return mdList

def stopAllRaid(mdList):
    for dev in mdList:
	isys.raidstop(dev)
