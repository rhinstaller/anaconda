#!/usr/bin/python

import _balkan
import isys
import os

def scanForRaid(drives):
    for d in drives:
	isys.makeDevInode(d, "/tmp/" + d)
	parts = _balkan.readTable('/tmp/' + d)
	os.remove("/tmp/" + d)
	raidSets = {}
	raidDevices = {}
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
		       pass
		knownDevices.append(dev)
	    else:
		raidSets[raidSet] = (level, totalDisks, mdMinor, [dev,])

	    if raidDevices.has_key(mdMinor):
	    	if (raidDevices[mdMinor] != raidSet):
		    # Raise hell
		    pass
	    else:
	    	raidDevices[mdMinor] = raidSet

	raidList = []
	for key in raidSets.keys():
	    (level, totalDisks, mdMinor, devices) = raidSets[key]
	    if len(devices) != totalDisks:
	    	# raise hell
		pass
	    raidList.append((mdMinor, devices))

	return raidList
		
def startAllRaid(driveList):
    mdList = []
    for (mdDevice, deviceList) in scanForRaid(['sda']):
    	devName = "md%d" % (mdDevice,)
	isys.raidstart(devName, deviceList[0])
	mdList.append(devName)
	return mdList

def stopAllRaid(mdList):
    for dev in mdList:
	isys.raidstop(dev)
