# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderList
import os
import isys
import rpm

import todo

FILENAME = 1000000

class InstallMethod:

    def readComps(self, hdlist):
	isys.mount('/tmp/' + self.device, "/tmp/hdimage");
	cs = ComponentSet('i386', "/tmp/hdimage/" + self.path + 
		'/RedHat/base/comps', hdlist)
	isys.umount("/tmp/hdimage")
	return cs

    def getFilename(self, h):
	return self.tree + "/RedHat/RPMS/" + self.fnames[h]

    def readHeaders(self):
	isys.mount('/tmp/' + self.device, "/tmp/hdimage");
	hl = []
	path = "/tmp/hdimage" + self.path + "/RedHat/RPMS"
	for n in os.listdir(path):
	    if (n[len(n) - 4:] == '.rpm'):
		fd = os.open(path + "/" + n, 0)
		(h, isSource) = rpm.headerFromPackage(fd)
		self.fnames[h] = n
		hl.append(h)
		os.close(fd)
		
	isys.umount("/tmp/hdimage")
	return HeaderList(hl)

    def targetFstab(self, fstab):
	self.isMounted = 0
	for (mntpoint, (device, fsystem, reformat)) in fstab.items():
	    if (device == self.device):
		self.isMounted = 1
		self.tree = "/mnt/sysimage" + mntpoint + "/" + self.path
		self.needsUnmount = 0

	if (not self.isMounted):
	    isys.mount('/tmp/' + self.device, "/tmp/hdimage");
	    self.tree = "/tmp/hdimage/" + self.path
	    self.needsUnmount = 1
	    
    def filesDone(self):
	if (self.needsUnmount):
	    isys.umount("/tmp/hdimage")

    def unlinkFilename(self, fullName):
	pass
	    
    def __init__(self, device, path):
	self.device = device
	self.path = path
	isys.makeDevInode(device, '/tmp/' + device)
	self.fnames = {}
