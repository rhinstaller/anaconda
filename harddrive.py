# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderList
import os
import isys
import rpm

import todo

FILENAME = 1000000

class InstallMethod:

    def readComps(self, hdlist):
	isys.makeDevInode(self.device, '/tmp/' + self.device)
	isys.mount('/tmp/' + self.device, "/tmp/hdimage", 
		   fstype = self.fstype);
	cs = ComponentSet("/tmp/hdimage/" + self.path + 
                          '/RedHat/base/comps', hdlist)
	isys.umount("/tmp/hdimage")
	return cs

    def getFilename(self, h):
	return self.tree + "/RedHat/RPMS/" + self.fnames[h]

    def readHeaders(self):
	isys.makeDevInode(self.device, '/tmp/' + self.device)
	isys.mount('/tmp/' + self.device, "/tmp/hdimage", 
		   fstype = self.fstype);
	hl = []
	path = "/tmp/hdimage" + self.path + "/RedHat/RPMS"
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
		
	isys.umount("/tmp/hdimage")
	return HeaderList(hl)

    def targetFstab(self, fstab):
	self.isMounted = 0
	for (mntpoint, device, fsystem, reformat, size) in fstab.mountList():
	    if (device == self.device and fsystem == "ext2"):
		self.isMounted = 1
		self.tree = "/mnt/sysimage" + mntpoint + "/" + self.path
		self.needsUnmount = 0

	if (not self.isMounted):
	    isys.mount('/tmp/' + self.device, "/tmp/hdimage", 
		       fstype = self.fstype)
	    self.tree = "/tmp/hdimage/" + self.path
	    self.needsUnmount = 1
	    
    def filesDone(self):
	if (self.needsUnmount):
	    isys.umount("/tmp/hdimage")

    def unlinkFilename(self, fullName):
	pass
	    
    def __init__(self, device, type, path):
	self.device = device
	self.path = path
	self.fstype = type
	self.fnames = {}
