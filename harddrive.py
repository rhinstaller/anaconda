# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderList, HeaderListFromFile
from installmethod import InstallMethod
import os
import isys
import iutil
import rpm
import string
from translate import _, cat, N_

import todo

FILENAME = 1000000

# Install from a set of files laid out on the hard drive like a CD
class OldHardDriveInstallMethod(InstallMethod):

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
	
	isys.mount(self.device, "/tmp/hdimage", fstype = self.fstype,
		   readOnly = 1);
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

    def getFilename(self, h, timer):
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

    def systemMounted(self, fstab, mntPoint, selected):
	self.mountMedia()
	    
    def filesDone(self):
	self.umountMedia()

    def protectedPartitions(self):
        rc = []
        rc.append(self.device)
        return rc
    
    def __init__(self, device, type, path):
	InstallMethod.__init__(self)
	self.device = device
	self.path = path
	self.fstype = type
	self.fnames = {}
        self.isMounted = 0
        
# Install from one or more iso images
class HardDriveInstallMethod(InstallMethod):

    # mounts disc image cdNum under self.tree
    def mountMedia(self, cdNum):
	if (self.mediaIsMounted):
	    raise SystemError, "trying to mount already-mounted iso image!"

	self.mountDirectory()

	isoImage = self.isoDir + '/' + self.path + '/' + self.discImages[cdNum]

	isys.makeDevInode("loop2", "/tmp/loop2")
	isys.losetup("/tmp/loop2", isoImage, readonly = 1)
	
	isys.mount("loop2", "/tmp/hdimage", fstype = 'iso9660', readOnly = 1);
	self.tree = "/tmp/hdimage/"
	self.mediaIsMounted = cdNum

    def umountMedia(self):
	if self.mediaIsMounted:
	    isys.umount(self.tree)
	    isys.makeDevInode("loop2", "/tmp/loop2")
	    isys.unlosetup("/tmp/loop2")
	    self.umountDirectory()
	    self.tree = None
	    self.mediaIsMounted = 0

    # This mounts the directory containing the iso images, and places the
    # mount point in self.isoDir. It's only used directly by __init__;
    # everything else goes through mountMedia
    def mountDirectory(self):
	if (self.isoDirIsMounted):
	    raise SystemError, "trying to mount already-mounted image!"
	
	f = open("/proc/mounts", "r")
	l = f.readlines()
	f.close()

	for line in l:
	    s = string.split(line)
	    if s[0] == "/tmp/" + self.device:
		self.isoDir = s[1] + "/"
		return
	
	isys.mount(self.device, "/tmp/isodir", fstype = self.fstype, 
		   readOnly = 1);
	self.isoDir = "/tmp/isodir/"
	self.isoDirIsMounted = 1

    def umountDirectory(self):
	if self.isoDirIsMounted:
	    isys.umount(self.isoDir)
	    self.tree = None
	    self.isoDirIsMounted = 0
	
    def readComps(self, hdlist):
	self.mountMedia(1)
	cs = ComponentSet(self.tree + '/RedHat/base/comps', hdlist)
	self.umountMedia()
	return cs

    def getFilename(self, h, timer):
	if self.mediaIsMounted != h[1000002]:
	    self.umountMedia()
	    self.mountMedia(h[1000002])

	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def readHeaders(self):
	self.mountMedia(1)
	hl = HeaderListFromFile(self.tree + "/RedHat/base/hdlist")
	self.umountMedia()

	# Make sure all of the correct CD images are available
	for h in hl.values():
	    if not self.discImages.has_key(h[1000002]):
		self.messageWindow(_("Error"),
			_("Missing CD #%d, which is required for the "
			  "install.") % h[1000002])
		sys.exit(0)

	return hl

    def systemMounted(self, fstab, mntPoint, selected):
	self.mountMedia(1)
	    
    def filesDone(self):
	self.umountMedia()

    def protectedPartitions(self):
        rc = []
        rc.append(self.device)
        return rc
    
    def __init__(self, device, type, path, messageWindow):
	InstallMethod.__init__(self)
	self.device = device
	self.path = path
	self.fstype = type
	self.fnames = {}
        self.isoDirIsMounted = 0
        self.mediaIsMounted = 0
	self.discImages = {}
	self.messageWindow = messageWindow

	# Go ahead and poke through the directory looking for interesting
	# iso images
	self.mountDirectory()
	files = os.listdir(self.isoDir + '/' + self.path)

	arch = iutil.getArch()

	for file in files:
	    what = self.isoDir + '/' + self.path + '/' + file
	    if not isys.isIsoImage(what): continue

	    isys.makeDevInode("loop2", "/tmp/loop2")

	    try:
		isys.losetup("/tmp/loop2", what, readonly = 1)
	    except SystemError:
		continue

	    try:
		isys.mount("loop2", "/mnt/cdimage", fstype = "iso9660",
			   readOnly = 1)
		for num in range(1, 10):
		    discTag = "/mnt/cdimage/.disc%d-%s" % (num, arch)
		    if os.access(discTag, os.R_OK):
			self.discImages[num] = file

		isys.umount("/mnt/cdimage")
	    except SystemError:
		pass

	    isys.makeDevInode("loop2", '/tmp/' + "loop2")
	    isys.unlosetup("/tmp/loop2")

	self.umountDirectory()
