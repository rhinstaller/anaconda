#
# harddrive.py - Install method for hard drive installs
#
# Copyright 1999-2003 Red Hat, Inc.
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
import sys
import isys
import iutil
import rpm
import string
from rhpl.translate import _, cat, N_
from rhpl.log import log
from constants import *

FILENAME = 1000000

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

    # return reference to file specified on ISO #1
    #
    # mounts ISO #1, copies file to destdir, umounts ISO #1
    #
    # will probably do bad things if called during package installation
    #
    # returns None if file doesn't exist
    def getFilename(self, filename, callback=None, destdir=None, retry=1):
	if destdir is None:
	    tmppath = self.getTempPath()
	else:
	    tmppath = destdir
	    
        fn = tmppath + '/' + os.path.basename(filename)

	self.mountMedia(1)
	try:
	    shutil.copy(self.tree + '/' + filename, fn)
	except:
	    fn = None
	    
        self.umountMedia()

	return fn


    # return reference to the RPM file specified by the header
    # will mount the appropriate ISO image as required by CD # in header
    def getRPMFilename(self, h, timer, callback=None):
	if self.mediaIsMounted != h[1000002]:
            log("switching from iso %s to %s" %(self.mediaIsMounted,
                                                h[1000002]))
	    self.umountMedia()
	    self.mountMedia(h[1000002])

	return "%s/%s/RPMS/%s" % (self.tree, productPath, h[1000000])

    def readHeaders(self):
	self.mountMedia(1)
        if not os.access("%s/%s/base/hdlist" % (self.tree, productPath), os.R_OK):
            self.umountMedia()
            raise FileCopyException
	hl = HeaderListFromFile("%s/%s/base/hdlist" % (self.tree, productPath))
	self.umountMedia()

	# Make sure all of the correct CD images are available
	missing_images = []
	for h in hl.values():
	    if not self.discImages.has_key(h[1000002]):
		if h[1000002] not in missing_images:
		    missing_images.append(h[1000002])

	if len(missing_images) > 0:
	    missing_images.sort()
	    missing_string = ""
	    for missing in missing_images:
		missing_string += "\t\t\tCD #%d\n" % (missing,)
		
	    self.messageWindow(_("Error"),
			       _("The following ISO images are missing which are required for the install:\n\n%s\nThe system will now reboot.") % missing_string)
	    sys.exit(0)
		
	return hl

    def mergeFullHeaders(self, hdlist):
	self.mountMedia(1)
        if not os.access("%s/%s/base/hdlist" % (self.tree, productPath), os.R_OK):
            self.umountMedia()
            raise FileCopyException
	hdlist.mergeFullHeaders("%s/%s/base/hdlist2" % (self.tree, productPath))
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

    # we cannot remove the partition we are hosting hard drive install from
    def protectedPartitions(self):
	return [self.device]
    
    def __init__(self, method, rootPath, intf):
	InstallMethod.__init__(self, method, rootPath, intf)

        device = method[0:method.index(":")]
        tmpmethod = method[method.index(":") + 1:]
        fstype = tmpmethod[0:tmpmethod.index("/")]
        path = tmpmethod[tmpmethod.index("/") + 1:]

	self.device = device
	self.path = path
	self.fstype = fstype
	self.fnames = {}
        self.isoDirIsMounted = 0
        self.mediaIsMounted = 0
	self.messageWindow = intf.messageWindow

	# Go ahead and poke through the directory looking for interesting
	# iso images
	self.mountDirectory()
	self.discImages = findIsoImages(self.isoDir + '/' + self.path, self.messageWindow)
	self.umountDirectory()
