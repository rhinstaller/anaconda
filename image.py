#
# image.py - Install method for disk image installs (CD & NFS)
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

from comps import ComponentSet, HeaderListFromFile
from installmethod import InstallMethod
import iutil
import os
import isys
import time
import kudzu
import string
import shutil
from constants import *

from rhpl.log import log
from rhpl.translate import _

class ImageInstallMethod(InstallMethod):

    def readCompsViaMethod(self, hdlist):
	return ComponentSet(self.tree + '/RedHat/base/comps.xml', hdlist)

    def getFilename(self, h, timer):
	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def readHeaders(self):
	return HeaderListFromFile(self.tree + "/RedHat/base/hdlist")

    def mergeFullHeaders(self, hdlist):
	hdlist.mergeFullHeaders(self.tree + "/RedHat/base/hdlist2")

    def getSourcePath(self):
        return self.tree

    def __init__(self, tree, rootPath):
	InstallMethod.__init__(self, rootPath)
	self.tree = tree

class CdromInstallMethod(ImageInstallMethod):

    def systemUnmounted(self):
	if self.loopbackFile:
	    isys.makeDevInode("loop0", "/tmp/loop")
	    isys.lochangefd("/tmp/loop", 
			"%s/RedHat/base/stage2.img" % self.tree)
	    self.loopbackFile = None

    def systemMounted(self, fsset, chroot, selected):
	changeloop=0
	for p in selected:
	    if p[1000002] and p[1000002] > 1:
		changeloop=1
		break
	if changeloop == 0:
	    return

	self.loopbackFile = "%s%s%s" % (chroot,
                                        fsset.filesystemSpace(chroot)[0][0],
                                        "/rhinstall-stage2.img")

	try:
	    iutil.copyFile("%s/RedHat/base/stage2.img" % self.tree, 
			    self.loopbackFile,
			    (self.progressWindow, _("Copying File"),
			    _("Transferring install image to hard drive...")))
	except:
	    self.messageWindow(_("Error"),
		    _("An error occurred transferring the install image "
		      "to your hard drive. You are probably out of disk "
		      "space."))
	    os.unlink(self.loopbackFile)
	    return 1

	isys.makeDevInode("loop0", "/tmp/loop")
	isys.lochangefd("/tmp/loop", self.loopbackFile)

    def getFilename(self, h, timer):
        if h[1000002] == None:
            log ("header for %s has no disc location tag, assuming it's"
                 "on the current CD", h[1000000])
        elif h[1000002] != self.currentDisc:
	    timer.stop()

	    key = ".disc%d-%s" % (self.currentDisc, iutil.getArch())
	    f = open("/mnt/source/" + key)
	    timestamp = f.readline()
	    f.close()

	    self.currentDisc = h[1000002]
	    isys.umount("/mnt/source")

	    done = 0
	    key = "/mnt/source/.disc%d-%s" % (self.currentDisc, iutil.getArch())

	    cdlist = []
	    for (dev, something, descript) in \
		    kudzu.probe(kudzu.CLASS_CDROM, kudzu.BUS_UNSPEC, 0):
		if dev != self.device:
		    cdlist.append(dev)

	    for dev in cdlist:
		try:
		    if not isys.mount(dev, "/mnt/source", fstype = "iso9660", 
			       readOnly = 1):
			if os.access(key, os.O_RDONLY):
			    f = open(key)
			    newStamp = f.readline()
			    f.close()
			    if newStamp == timestamp:
				done = 1

			if not done:
			    isys.umount("/mnt/source")
		except:
		    pass

		if done:
		    break

		if done:
		    break

	    if not done:
		isys.ejectCdrom(self.device)

	    while not done:
		self.messageWindow(_("Change CDROM"), 
		    _("Please insert disc %d to continue.") % self.currentDisc)

		try:
		    if isys.mount(self.device, "/mnt/source", 
				  fstype = "iso9660", readOnly = 1):
			time.sleep(3)
			isys.mount(self.device, "/mnt/source", 
				   fstype = "iso9660", readOnly = 1)
		    
		    if os.access(key, os.O_RDONLY):
			f = open(key)
			newStamp = f.readline()
			f.close()
			if newStamp == timestamp:
			    done = 1
                            # make /tmp/cdrom again so cd gets ejected
                            isys.makeDevInode(self.device, "/tmp/cdrom")

		    if not done:
			self.messageWindow(_("Wrong CDROM"),
				_("That's not the correct %s CDROM.")
                                           % (productName,))
			isys.umount("/mnt/source")
			isys.ejectCdrom(self.device)
		except:
		    self.messageWindow(_("Error"), 
			    _("The CDROM could not be mounted."))

	    timer.start()

        tmppath = self.getTempPath()
        copied = 0
        # FIXME: should retry a few times then prompt for new cd
        while not copied:
            try:
                shutil.copy(self.tree + "/RedHat/RPMS/" + h[1000000],
                            tmppath + h[1000000])
            except IOError, (errnum, msg):
                log("IOError %s occurred copying %s: %s",
                    errnum, h[1000000], str(msg))
                time.sleep(5)
            else:
                copied = 1
                        
	return tmppath + h[1000000]

    def unlinkFilename(self, fullName):
        os.remove(fullName)

    def filesDone(self):
        if not self.loopbackFile: return

	try:
	    # this isn't the exact right place, but it's close enough
	    os.unlink(self.loopbackFile)
	except SystemError:
	    pass

    def __init__(self, url, messageWindow, progressWindow, rootPath):
	(self.device, tree) = string.split(url, "/", 1)
	self.messageWindow = messageWindow
	self.progressWindow = progressWindow
	self.currentDisc = 1
        self.loopbackFile = None
	ImageInstallMethod.__init__(self, "/" + tree, rootPath)

class NfsInstallMethod(ImageInstallMethod):

    def __init__(self, tree, rootPath):
	ImageInstallMethod.__init__(self, tree, rootPath)

def findIsoImages(path, messageWindow):
    files = os.listdir(path)
    arch = iutil.getArch()
    discImages = {}

    for file in files:
	what = path + '/' + file
	if not isys.isIsoImage(what): continue

	isys.makeDevInode("loop2", "/tmp/loop2")

	try:
	    isys.losetup("/tmp/loop2", what, readOnly = 1)
	except SystemError:
	    continue

	try:
	    isys.mount("loop2", "/mnt/cdimage", fstype = "iso9660",
		       readOnly = 1)
	    for num in range(1, 10):
		discTag = "/mnt/cdimage/.disc%d-%s" % (num, arch)
		if os.access(discTag, os.R_OK):
		    import stat

		    # warn user if images appears to be wrong size
		    if os.stat(what)[stat.ST_SIZE] % 2048:
			rc = messageWindow(_("Warning"),
	       "The ISO image %s has a size which is not "
	       "a multiple of 2048 bytes.  This may mean "
	       "it was corrupted on transfer to this computer."
	       "\n\nPress OK to continue (but installation will "
	       "probably fail), or Cancel to exit the "
	       "installer (RECOMMENDED). " % file, type = "okcancel")
			if rc:
			    import sys
			    sys.exit(0)

		    discImages[num] = file

	    isys.umount("/mnt/cdimage")
	except SystemError:
	    pass

	isys.makeDevInode("loop2", '/tmp/' + "loop2")
	isys.unlosetup("/tmp/loop2")

    return discImages

class NfsIsoInstallMethod(NfsInstallMethod):

    def getFilename(self, h, timer):
	if self.imageMounted != h[1000002]:
	    self.umountImage()
	    self.mountImage(h[1000002])

	return self.mntPoint + "/RedHat/RPMS/" + h[1000000]

    def umountImage(self):
	if self.imageMounted:
	    isys.umount(self.mntPoint)
	    isys.makeDevInode("loop3", "/tmp/loop3")
	    isys.unlosetup("/tmp/loop3")
	    self.mntPoint = None
	    self.imageMounted = 0

    def mountImage(self, cdNum):
	if (self.imageMounted):
	    raise SystemError, "trying to mount already-mounted iso image!"

	isoImage = self.isoPath + '/' + self.discImages[cdNum]

	isys.makeDevInode("loop3", "/tmp/loop3")
	isys.losetup("/tmp/loop3", isoImage, readOnly = 1)
	
	isys.mount("loop3", "/tmp/isomedia", fstype = 'iso9660', readOnly = 1);
	self.mntPoint = "/tmp/isomedia/"
	self.imageMounted = cdNum

    def filesDone(self):
	self.umountImage()

    def __init__(self, tree, messageWindow, rootPath):
	self.imageMounted = None
	self.isoPath = tree

	# the tree points to the directory that holds the iso images
	# even though we already have the main one mounted once, it's
	# easiest to just mount it again so that we can treat all of the
	# images the same way -- we use loop3 for everything

	self.discImages = findIsoImages(tree, messageWindow)
	self.mountImage(1)

	ImageInstallMethod.__init__(self, self.mntPoint, rootPath)

