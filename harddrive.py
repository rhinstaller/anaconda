#
# harddrive.py - Install method for hard drive installs
#
# Copyright 1999-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# General Public License.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#


from installmethod import InstallMethod, FileCopyException
from image import findIsoImages, ImageInstallMethod
import shutil
import os
import sys
import isys
import iutil
import string
from rhpl.translate import _, cat, N_
from constants import *

import logging
log = logging.getLogger("anaconda")

# Install from one or more iso images
class HardDriveInstallMethod(ImageInstallMethod):
    def getMethodUri(self):
        return "file://%s" % self.tree

    def copyFileToTemp(self, filename):
        wasmounted = self.mediaIsMounted
        self.switchMedia(1, filename)
            
        path = ImageInstallMethod.copyFileToTemp(self, filename)

        self.switchMedia(wasmounted)
        return path

    def badPackageError(self, pkgname):
        return _("The file %s cannot be opened.  This is due to a missing "
                 "file or perhaps a corrupt package.  Please verify your "
                 "installation images and that you have all the required "
                 "media.\n\n"
                 "If you reboot, your system will be left in an inconsistent "
                 "state that will likely require reinstallation.\n\n") % pkgname

    # mounts disc image cdNum under self.tree
    def mountMedia(self, cdNum):
        if self.mediaIsMounted:
            raise SystemError, "trying to mount already-mounted iso image!"

        self.mountDirectory()

        retry = True
        while retry:
            try:
                isoImage = self.isoDir + '/' + self.path + '/' + self.discImages[cdNum]

                isys.makeDevInode("loop3", "/tmp/loop3")
                isys.losetup("/tmp/loop3", isoImage, readOnly = 1)

                isys.mount("loop3", self.tree, fstype = 'iso9660', readOnly = 1);
                self.mediaIsMounted = cdNum

                retry = False
            except:
                ans = self.messageWindow( _("Missing ISO 9660 Image"),
                                          _("The installer has tried to mount "
                                            "image #%s, but cannot find it on "
                                            "the hard drive.\n\n"
                                            "Please copy this image to the "
                                            "drive and click Retry. Click Reboot "
                                            " to abort the installation.")
                                            % (cdNum,), type="custom",
	                                    custom_icon="warning",
                                            custom_buttons=[_("_Reboot"),
	                                                    _("Re_try")])
                if ans == 0:
                    sys.exit(0)
                elif ans == 1:
                    self.discImages = findIsoImages(self.isoPath, self.messageWindow)

    def umountMedia(self):
	if self.mediaIsMounted:
	    isys.umount(self.tree)
	    isys.makeDevInode("loop3", "/tmp/loop3")
	    isys.unlosetup("/tmp/loop3")
	    self.umountDirectory()
	    self.mediaIsMounted = 0

    # This mounts the directory containing the iso images, and places the
    # mount point in self.isoDir. It's only used directly by __init__;
    # everything else goes through switchMedia
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
	    self.isoDirIsMounted = 0
	
    # return reference to file specified on ISO #1
    # mounts ISO #1, copies file to destdir, umounts ISO #1
    # will probably do bad things if called during package installation
    # returns None if file doesn't exist
    def getFilename(self, filename, callback=None, destdir=None, retry=1):
        if destdir is None:
            destdir = self.getTempPath()
        fn = destdir + '/' + os.path.basename(filename)

        self.switchMedia(1, filename)
        try:
            shutil.copy(self.tree + '/' + filename, fn)
        except:
            fn = None
        return fn

    def switchMedia(self, mediano, filename=""):
        if mediano != self.mediaIsMounted:
            log.info("switching from iso %s to %s for %s" % (self.mediaIsMounted, mediano, filename))
            self.umountMedia()
            self.mountMedia(mediano)

    def systemMounted(self, fsset, mntPoint):
        self.switchMedia(1)

    def systemUnmounted(self):
	self.umountMedia()

    def filesDone(self):
        # we're trying to unmount the source image at the end.  if it
        # fails, we'll reboot soon enough anyway
        try:
            self.umountMedia()
        except:
            log.warning("unable to unmount media")

    # we cannot remove the partition we are hosting hard drive install from
    def protectedPartitions(self):
	return [self.device]
    
    def __init__(self, method, rootPath, intf):
        """@param method hd://device:fstype:/path"""
        method = method[5:]
        device = method[0:method.index(":")]
        tmpmethod = method[method.index(":") + 1:]
        fstype = tmpmethod[0:tmpmethod.index("/")]
        path = tmpmethod[tmpmethod.index("/") + 1:]

	ImageInstallMethod.__init__(self, method, rootPath, intf)

	self.device = device
	self.path = path
	self.fstype = fstype
        self.isoDirIsMounted = 0
        self.mediaIsMounted = 0
	self.messageWindow = intf.messageWindow
        self.currentMedia = []
        self.tree = "/tmp/isomedia/"

        # Mount the partition containing the ISO images just long enough for
        # us to build up a list of all the path names.
	self.mountDirectory()
	self.discImages = findIsoImages(self.isoDir + '/' + self.path, self.messageWindow)
        self.umountDirectory()
