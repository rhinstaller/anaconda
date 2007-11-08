#
# harddrive.py - Install method for hard drive installs
#
# Copyright 1999-2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# General Public License.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from image import findIsoImages, ImageInstallMethod
import shutil
import os
import sys
import isys
import string
from rhpl.translate import _, cat, N_
from constants import *

import logging
log = logging.getLogger("anaconda")

# Install from one or more iso images
class HardDriveInstallMethod(ImageInstallMethod):
    def getMethodUri(self):
        return "file://%s" % self.tree

    def badPackageError(self, pkgname):
        return _("The file %s cannot be opened.  This is due to a missing "
                 "file or perhaps a corrupt package.  Please verify your "
                 "installation images and that you have all the required "
                 "media.\n\n"
                 "If you exit, your system will be left in an inconsistent "
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

                isys.losetup("/dev/loop3", isoImage, readOnly = 1)

                isys.mount("/dev/loop3", self.tree, fstype = 'iso9660', readOnly = 1);
                self.mediaIsMounted = cdNum

                retry = False
            except:
                ans = self.messageWindow( _("Missing ISO 9660 Image"),
                                          _("The installer has tried to mount "
                                            "image #%s, but cannot find it on "
                                            "the hard drive.\n\n"
                                            "Please copy this image to the "
                                            "drive and click Retry. Click Exit "
                                            " to abort the installation.")
                                            % (cdNum,), type="custom",
	                                    custom_icon="warning",
                                            custom_buttons=[_("_Exit"),
	                                                    _("_Retry")])
                if ans == 0:
                    sys.exit(0)
                elif ans == 1:
                    self.discImages = findIsoImages(self.isoPath, self.messageWindow)

    def umountMedia(self):
	if self.mediaIsMounted:
	    isys.umount(self.tree)
	    isys.unlosetup("/dev/loop3")
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
	
        try:
            isys.mount(self.device, "/tmp/isodir", fstype = self.fstype)
        except SystemError, msg:
            log.error("couldn't mount ISO source directory: %s" % msg)
            self.messageWindow(_("Couldn't Mount ISO Source"),
                               _("An error occurred mounting the source "
                                 "device %s.  This may happen if your ISO "
                                 "images are located on an advanced storage "
                                 "device like LVM or RAID, or if there was a "
                                 "problem mounting a partition.  Click exit "
                                 "to abort the installation.")
                               % (self.device,), type="custom",
                               custom_icon="error",
                               custom_buttons=[_("_Exit")])
            sys.exit(0)


	self.isoDir = "/tmp/isodir/"
	self.isoDirIsMounted = 1

    def umountDirectory(self):
	if self.isoDirIsMounted:
	    isys.umount(self.isoDir)
	    self.isoDirIsMounted = 0

    def switchMedia(self, mediano, filename=""):
        if mediano != self.mediaIsMounted:
            log.info("switching from iso %s to %s for %s" % (self.mediaIsMounted, mediano, filename))
            self.umountMedia()
            self.mountMedia(mediano)

    def systemMounted(self, fsset, mntPoint):
        self.switchMedia(1)

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
        (device, fstype, path) = method.split(":", 3)
        device = method[0:method.index(":")]

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
