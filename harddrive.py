# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderList
import os
import isys
import rpm
import string

import todo

FILENAME = 1000000

class InstallMethod:

    def mountMedia(self):
	if (self.isMounted):
	    raise SystemError, "trying to mount already-mounted image!"
	
	f = open("/proc/mounts", "r")
	l = f.readlines()
	f.close()

	for line in l:
	    s = string.split(line)
	    if s == "/tmp/" + self.device:
		self.tree = s[1] + "/"
		return
	
	isys.makeDevInode(self.device, '/tmp/' + self.device)
	isys.mount('/tmp/' + self.device, "/tmp/hdimage", 
		   fstype = self.fstype);
	self.tree = "/tmp/hdimage/"
	self.isMounted = 1

    def umountMedia(self):
	if self.isMounted:
	    isys.umount(self.tree)
	    self.tree = None
	    self.isMounted = 0
	
    def readComps(self, hdlist):
	self.mountMedia()
	cs = ComponentSet(self.tree + self.path + 
                          '/RedHat/base/comps', hdlist)
	self.umountMedia()
	return cs

    def getFilename(self, h):
	return self.tree + "RedHat/RPMS/" + self.fnames[h]

    def readHeaders(self):
	self.mountMedia()
	hl = []
	path = self.tree + self.path + "/RedHat/RPMS"
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
		
	self.umountMedia()
	return HeaderList(hl)

    def targetFstab(self, fstab):
	self.mountMedia()
	    
    def filesDone(self):
	self.umountMedia()

    def unlinkFilename(self, fullName):
	pass
	    
    def __init__(self, device, type, path):
	self.device = device
	self.path = path
	self.fstype = type
	self.fnames = {}
