#
# harddrive.py - Install method for hard drive installs
#
# Copyright 1999-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#


from hdrlist import groupSetFromCompsFile, HeaderListFromFile
from installmethod import InstallMethod, FileCopyException
from image import findIsoImages
import shutil
import os
import isys
import iutil
import rpm
import string
from rhpl.translate import _, cat, N_
from rhpl.log import log

FILENAME = 1000000

# Install from a set of files laid out on the hard drive like a CD
class OldHardDriveInstallMethod(InstallMethod):
    def copyFileToTemp(self, filename):
        wasmounted = self.isMounted

        if not wasmounted:
            self.mountMedia()
        tmppath = self.getTempPath()
        path = tmppath + os.path.basename(filename)
        shutil.copy(self.tree + "/" + filename, path)

        if not wasmounted:
            self.umountMedia()
        
        return path

    def mountMedia(self):
	if (self.isMounted):
	    raise SystemError, "trying to mount already-mounted image!"
	
	f = open("/proc/mounts", "r")
	l = f.readlines()
	f.close()

	for line in l:
	    s = string.split(line)
	    if s[0] == "/dev/" + self.device:
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
	
    def readCompsViaMethod(self, hdlist):
	self.mountMedia()
	fname = self.findBestFileMatch(self.tree + self.path, 'comps.xml')
        cs = groupSetFromCompsFile(fname, hdlist)
	self.umountMedia()
	return cs

    def getFilename(self, h, timer):
        if h[1000005] is not None:
            path = "/RedHat/Updates/"
        else:
            path = "/RedHat/RPMS/"

	return self.tree + self.path + path + h[FILENAME]

    def readHeaders(self):
	self.mountMedia()
        if not os.access(self.tree + "/RedHat/base/hdlist", os.R_OK):
            self.umountMedia()
            raise FileCopyException
	hl = HeaderListFromFile(self.tree + self.path + "/RedHat/base/hdlist")
	self.umountMedia()
	return hl
	
    def mergeFullHeaders(self, hdlist):
	self.mountMedia()
        if not os.access(self.tree + "/RedHat/base/hdlist2", os.R_OK):
            self.umountMedia()
            raise FileCopyException
	hdlist.mergeFullHeaders(self.tree + self.path + "/RedHat/base/hdlist2")
	self.umountMedia()


    def systemMounted(self, fsset, chroot):
	self.mountMedia()
	    
    def filesDone(self):
        # we're trying to unmount the source image at the end.  if it
        # fails, we'll reboot soon enough anyway
        try:
            self.umountMedia()
        except:
            log("unable to unmount media")

    def protectedPartitions(self):
        rc = []
        rc.append(self.device)
        return rc
    
    def __init__(self, device, type, path, rootPath):
	InstallMethod.__init__(self, rootPath)
	self.device = device
	self.path = path
	self.fstype = type
	self.fnames = {}
        self.isMounted = 0
        
# Install from one or more iso images
class HardDriveInstallMethod(InstallMethod):
    def copyFileToTemp(self, filename):
        wasmounted = self.mediaIsMounted

        if not wasmounted:
            self.mountMedia(1)
        tmppath = self.getTempPath()
        path = tmppath + os.path.basename(filename)
        shutil.copy(self.tree + "/" + filename, path)

        if not wasmounted:
            self.umountMedia()
        
        return path

    # mounts disc image cdNum under self.tree
    def mountMedia(self, cdNum):
	if (self.mediaIsMounted):
	    raise SystemError, "trying to mount already-mounted iso image!"

	self.mountDirectory()

	isoImage = self.isoDir + '/' + self.path + '/' + self.discImages[cdNum]

	isys.makeDevInode("loop3", "/tmp/loop3")
	isys.losetup("/tmp/loop3", isoImage, readOnly = 1)
	
	isys.mount("loop3", "/tmp/isomedia", fstype = 'iso9660', readOnly = 1);
	self.tree = "/tmp/isomedia/"
	self.mediaIsMounted = cdNum

    def umountMedia(self):
	if self.mediaIsMounted:
	    isys.umount(self.tree)
	    isys.makeDevInode("loop3", "/tmp/loop3")
	    isys.unlosetup("/tmp/loop3")
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
	    if s[0] == "/dev/" + self.device:
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
	
    def readCompsViaMethod(self, hdlist):
	self.mountMedia(1)
	fname = self.findBestFileMatch(self.tree, 'comps.xml')
        cs = groupSetFromCompsFile(fname, hdlist)
	self.umountMedia()
	return cs

    def getFilename(self, h, timer):
	if self.mediaIsMounted != h[1000002]:
            log("switching from iso %s to %s" %(self.mediaIsMounted,
                                                h[1000002]))
	    self.umountMedia()
	    self.mountMedia(h[1000002])

        if h[1000005] is not None:
            path = "/RedHat/Updates/"
        else:
            path = "/RedHat/RPMS/"

	return self.tree + path + h[1000000]

    def readHeaders(self):
	self.mountMedia(1)
        if not os.access(self.tree + "/RedHat/base/hdlist", os.R_OK):
            self.umountMedia()
            raise FileCopyException
	hl = HeaderListFromFile(self.tree + "/RedHat/base/hdlist")
	self.umountMedia()

	# Make sure all of the correct CD images are available
	for h in hl.values():
            import sys
	    if not self.discImages.has_key(h[1000002]):
		self.messageWindow(_("Error"),
			_("Missing ISO image for CD #%d, which is required for the "
			  "install.\n\nThe system will now reboot.") % h[1000002])
		sys.exit(0)

	return hl

    def mergeFullHeaders(self, hdlist):
	self.mountMedia(1)
        if not os.access(self.tree + "/RedHat/base/hdlist", os.R_OK):
            self.umountMedia()
            raise FileCopyException
	hdlist.mergeFullHeaders(self.tree + "/RedHat/base/hdlist2")
	self.umountMedia()

    def systemMounted(self, fsset, mntPoint):
	self.mountMedia(1)
	    
    def systemUnmounted(self):
	self.umountMedia()

    def filesDone(self):
        # we're trying to unmount the source image at the end.  if it
        # fails, we'll reboot soon enough anyway
        try:
            self.umountMedia()
        except:
            log("unable to unmount media")

    def protectedPartitions(self):
        rc = []
        rc.append(self.device)
        return rc
    
    def __init__(self, device, type, path, messageWindow, rootPath):
	InstallMethod.__init__(self, rootPath)
	self.device = device
	self.path = path
	self.fstype = type
	self.fnames = {}
        self.isoDirIsMounted = 0
        self.mediaIsMounted = 0
	self.messageWindow = messageWindow

	# Go ahead and poke through the directory looking for interesting
	# iso images
	self.mountDirectory()
	self.discImages = findIsoImages(self.isoDir + '/' + self.path, messageWindow)

	self.umountDirectory()
