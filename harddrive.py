# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderList
from installmethod import InstallMethod
import os
import isys
import rpm
import string

import todo

FILENAME = 1000000

class HardDriveInstallMethod(InstallMethod):

    def mountMedia(self):
	if (self.isMounted):
	    raise SystemError, "trying to mount already-mounted image!"
	
	f = open("/proc/mounts", "r")
	l = f.readlines()
	f.close()

	for line in l:
	    s = string.split(line)
	    if s[0] == "/tmp/" + self.device:
		self.tree = s[1] + "/"
		return
	
	isys.mount(self.device, "/tmp/hdimage", fstype = self.fstype);
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
	return self.tree + self.path + "/RedHat/RPMS/" + self.fnames[h]

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

    def systemMounted(self, fstab, mntPoint):
	self.mountMedia()
	    
    def filesDone(self):
	self.umountMedia()

    def __init__(self, device, type, path):
	InstallMethod.__init__(self)
	self.device = device
	self.path = path
	self.fstype = type
	self.fnames = {}
        self.isMounted = 0
        
