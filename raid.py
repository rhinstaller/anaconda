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
	for i in range(0, len(parts) - 1):
	    (type, start, size) = parts[i]
	    if type != 7: continue

	    dev = "%s%d" % (d, i + 1)

	    (major, minor, raidSet, level, nrDisks, totalDisks, mdMinor) = \
	    	isys.raidsb(dev)

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
	if len(devices) != totalDisks:
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
