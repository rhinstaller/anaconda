#!/usr/bin/python
#
# 11.1.2001	Pekka.Savola@netcore.fi
#		
#		"If it breaks you get to keep both the pieces"
#
#		(needless to say, Red Hat doesn't support this)
#
#
# Checks RH comps, hdlist files and RPMS directory.  I use:
#
# /ftp/redhat-7.0/RedHat/base/comps
# /ftp/redhat-7.0/RedHat/base/hdlist
# /ftp/redhat-7.0/RedHat/RPMS/*
#
# So, you run this with 'check-repository.py /ftp/redhat-7.0'
#
# Checks for (everything that the installer should, really!):
#  - typos in comps file, ie. missing packages
#  - incorrect hdlist
#  - corruption of RPM headers in packages found in hdlist
#  - ...
#
# Hacked up and down from Red Hat's todo.py in anaconda package.
#
# Notes:  I have deliberately ripped off extra junk like support for
# 	  multiple architectures.  Not too difficult to remerge if you
#	  really need those.  I only have i386.


import sys
sys.path.append('/usr/lib/anaconda')

from comps import ComponentSet, HeaderList
import os
import rpm

import todo

FILENAME = 1000000

class CheckRepository:

#    def freeHeaderList(self):
#	if (self.hdList):
#	    self.hdList = None

    def getHeaderList(self):
	self.hdList = self.readHeaders()
	return self.hdList

    def getCompsList(self):
	if (not self.comps):
	    self.getHeaderList()
	    try:
		    self.comps = self.readComps(self.hdList)
            except KeyError, package:
		print 'There was a problem with', package, '(there may be further problems)'

	return self.comps

    def readComps(self, hdlist):
	cs = ComponentSet(self.path + 
                          '/RedHat/base/comps', hdlist)
	return cs

    def getFilename(self, h):
	return self.path + "/RedHat/RPMS/" + self.fnames[h]

    def readHeaders(self):
	hl = []
	path = self.path + "/RedHat/RPMS"
	for n in os.listdir(path):
            fd = os.open(path + "/" + n, 0)
            try:
                (h, isSource) = rpm.headerFromPackage(fd)
		if (h and not isSource):
		    self.fnames[h] = n
		    hl.append(h)
            except:
		pass
            os.close(fd)
		
	return HeaderList(hl)

    def __init__(self, path):
	self.path = path
	self.fnames = {}
        
	self.hdList = None
	self.comps = None

	self.getCompsList ()
	self.getHeaderList ()
        
try:
	CheckRepository(sys.argv[1])
except OSError, msg:
	print 'Directory was invalid: ', msg
except IndexError:
	print 'Usage: ', sys.argv[0], '<repository directory>'
