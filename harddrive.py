# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderList
import isys

class InstallMethod:

    def readComps(self, hdlist):
	isys.mount('/tmp/' + self.device, "/tmp/hdimage");
	cs = ComponentSet('i386', "/tmp/hdimage/" + self.tree + 
		'/RedHat/base/comps', hdlist)
	isys.umount("/tmp/hdimage")
	return cs

    def getFilename(self, h):
	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def readHeaders(self):
	isys.mount('/tmp/' + self.device, "/tmp/hdimage");
	hl = HeaderList("/tmp/hdimage/" + self.path + "/RedHat/base/hdlist")
	isys.umount("/tmp/hdimage")
	return hl

    def targetFstab(self, fstab):
	self.isMounted = 0
	for (device, fsystem, reformat) in fstab.items():
	    if (device == self.device):
		self.isMounted = 1
		self.tree = "/mnt/sysimage" + fsystem + "/" + self.path
		self.needsUnmount = 0

	if (not self.isMounted):
	    isys.mount('/tmp/' + self.device, "/tmp/hdimage");
	    self.tree = "/tmp/hdimage/" + self.path
	    self.needsUnmount = 1
	    
    def filesDone(self):
	if (self.needsUnmount):
	    isys.umount("/tmp/hdimage")
	    
    def __init__(self, device, path):
	self.device = device
	self.path = path
