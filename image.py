#
# image.py - Install method for disk image installs (CD & NFS)
#
# Copyright 1999-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from installmethod import InstallMethod, FileCopyException
import shutil
import os
import sys
import isys
import time
import stat
import kudzu
import string
import shutil
import product
import rhpl
import sets

from constants import *

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

# this sucks, but we want to consider s390x as s390x in here but generally
# don't.  *sigh*
if os.uname()[4] == "s390x":
    _arch = "s390x"
else:
    _arch = rhpl.getArch()

# given groupset containing information about selected packages, use
# the disc number info in the headers to come up with message describing
# the required CDs
#
# dialog returns a value of 0 if user selected to abort install
def presentRequiredMediaMessage(anaconda):
    reqcds = anaconda.backend.ayum.tsInfo.reqmedia.keys()

    # if only one CD required no need to pop up a message
    if len(reqcds) < 2:
	return

    # check what discs our currently mounted one provides
    if os.access("/mnt/source/.discinfo", os.R_OK):
        discNums = []
        try:
            f = open("/mnt/source/.discinfo")
            stamp = f.readline().strip()
            descr = f.readline().strip()
            arch = f.readline().strip()
            discNums = getDiscNums(f.readline().strip())
            f.close()
        except Exception, e:
            log.critical("Exception reading discinfo: %s" %(e,))

        log.info("discNums is %s" %(discNums,))
        haveall = 0
        s = sets.Set(reqcds)
        t = sets.Set(discNums)
        if s.issubset(t):
            haveall = 1

        if haveall == 1:
            return

    reqcds.sort()
    reqcdstr = ""
    for cdnum in reqcds:
        if cdnum == -99: # non-CD bits
            continue
	reqcdstr += "\t\t%s %s CD #%d\n" % (product.productName, product.productVersion, cdnum,)
		
    return anaconda.intf.messageWindow( _("Required Install Media"),
				        _("The software you have selected to "
                                          "install will require the following CDs:\n\n"
                                          "%s\nPlease "
                                          "have these ready before proceeding with "
                                          "the installation.  If you need to abort "
                                          "the installation and reboot please "
                                          "select \"Reboot\".") % (reqcdstr,),
                                          type="custom", custom_icon="warning",
                                          custom_buttons=[_("_Reboot"), _("_Back"), _("_Continue")])



class ImageInstallMethod(InstallMethod):

    def switchMedia(self, mediano, filename=""):
        pass

    def getFilename(self, filename, callback=None, destdir=None, retry=1):
	return self.tree + "/" + filename

    def getSourcePath(self):
        return self.tree

    def getMethodUri(self):
        return "file://%s" % (self.tree,)

    def copyFileToTemp(self, filename):
        tmppath = self.getTempPath()
        path = tmppath + os.path.basename(filename)
        shutil.copy(self.tree + "/" + filename, path)
        
        return path

    def __init__(self, tree, rootPath, intf):
	InstallMethod.__init__(self, tree, rootPath, intf)
	self.tree = tree
	self.isoPath = tree
        self.splitmethod = True

class CdromInstallMethod(ImageInstallMethod):

    def unmountCD(self):
        done = 0
        while done == 0:
            try:
                isys.umount("/mnt/source")
                self.currentMedia = []
                break
            except Exception, e:
                log.error("exception in unmountCD: %s" %(e,))
                self.messageWindow(_("Error"),
                                   _("An error occurred unmounting the CD.  "
                                     "Please make sure you're not accessing "
                                     "%s from the shell on tty2 "
                                     "and then click OK to retry.")
                                   % ("/mnt/source",))

    def ejectCD(self):
        if self.noeject:
            log.info("noeject in effect, not ejecting cdrom")
        else:
            isys.ejectCdrom(self.device, makeDevice=1)

    def badPackageError(self, pkgname):
        return _("The file %s cannot be opened.  This is due to a missing "
                 "file or perhaps a corrupt package.  Please verify your "
                 "installation images and that you have all the required "
                 "media.\n\n"
                 "If you reboot, your system will be left in an inconsistent "
                 "state that will likely require reinstallation.\n\n") % pkgname

    def systemUnmounted(self):
	if self.loopbackFile:
	    isys.makeDevInode("loop0", "/tmp/loop")
	    isys.lochangefd("/tmp/loop", 
			"%s/images/stage2.img" % (self.tree,))
	    self.loopbackFile = None

    def systemMounted(self, fsset, chroot):
	self.loopbackFile = "%s%s%s" % (chroot,
                                        fsset.filesystemSpace(chroot)[0][0],
                                        "/rhinstall-stage2.img")

	try:
            win = self.waitWindow (_("Copying File"),
                                   _("Transferring install image to hard drive..."))
	    shutil.copyfile("%s/images/stage2.img" % (self.tree,), 
			    self.loopbackFile)
            win.pop()
	except Exception, e:
            if win:
                win.pop()

            log.critical("error transferring stage2.img: %s" %(e,))
	    self.messageWindow(_("Error"),
		    _("An error occurred transferring the install image "
		      "to your hard drive. You are probably out of disk "
		      "space."))
	    os.unlink(self.loopbackFile)
	    return 1

	isys.makeDevInode("loop0", "/tmp/loop")
	isys.lochangefd("/tmp/loop", self.loopbackFile)

    def getFilename(self, filename, callback=None, destdir=None, retry=1):
	return self.tree + "/" + filename

    def switchMedia(self, mediano, filename=""):
        log.info("switching from CD %s to %s for %s" %(self.currentMedia, mediano, filename))
        if mediano in self.currentMedia:
            return
        if os.access("/mnt/source/.discinfo", os.R_OK):
            f = open("/mnt/source/.discinfo")
            timestamp = f.readline().strip()
            f.close()
        else:
            timestamp = self.timestamp

        if self.timestamp is None:
            self.timestamp = timestamp

        needed = mediano

        # if self.currentMedia is empty, then we shouldn't have anything
        # mounted.  double-check by trying to unmount, but we don't want
        # to get into a loop of trying to unmount forever.  if
        # self.currentMedia is set, then it should still be mounted and
        # we want to loop until it unmounts successfully
        if not self.currentMedia:
            try:
                isys.umount("/mnt/source")
            except:
                pass
        else:
            self.unmountCD()

        done = 0

        cdlist = []
        for (dev, something, descript) in \
                kudzu.probe(kudzu.CLASS_CDROM, kudzu.BUS_UNSPEC, 0):
            cdlist.append(dev)

        for dev in cdlist:
            try:
                if not isys.mount(dev, "/mnt/source", fstype = "iso9660", 
                           readOnly = 1):
                    if os.access("/mnt/source/.discinfo", os.R_OK):
                        f = open("/mnt/source/.discinfo")
                        newStamp = f.readline().strip()
                        try:
                            descr = f.readline().strip()
                        except:
                            descr = None
                        try:
                            arch = f.readline().strip()
                        except:
                            arch = None
                        try:
                            discNum = getDiscNums(f.readline().strip())
                        except:
                            discNum = [ 0 ]
                        f.close()
                        if (newStamp == timestamp and
                            arch == _arch and
                            needed in discNum):
                            done = 1
                            self.currentMedia = discNum

                    if not done:
                        isys.umount("/mnt/source")
            except:
                pass

            if done:
                break

        if not done:
            if self.noeject:
                log.info("noeject in effect, not ejecting cdrom")
            else:
                isys.ejectCdrom(self.device)

        while not done:
            if self.intf is not None:
                self.intf.beep()

            self.messageWindow(_("Change CDROM"), 
                _("Please insert %s disc %d to continue.") % (productName,
                                                              needed))
            try:
                if isys.mount(self.device, "/mnt/source", 
                              fstype = "iso9660", readOnly = 1):
                    time.sleep(3)
                    isys.mount(self.device, "/mnt/source", 
                               fstype = "iso9660", readOnly = 1)
                

                if os.access("/mnt/source/.discinfo", os.R_OK):
                    f = open("/mnt/source/.discinfo")
                    newStamp = f.readline().strip()
                    try:
                        descr = f.readline().strip()
                    except:
                        descr = None
                    try:
                        arch = f.readline().strip()
                    except:
                        arch = None
                    try:
                        discNum = getDiscNums(f.readline().strip())
                    except:
                        discNum = [ 0 ]
                    f.close()
                    if (newStamp == timestamp and
                        arch == _arch and
                        needed in discNum):
                        done = 1
                        self.currentMedia = discNum
                        # make /tmp/cdrom again so cd gets ejected
                        isys.makeDevInode(self.device, "/tmp/cdrom")

                if not done:
                    self.messageWindow(_("Wrong CDROM"),
                            _("That's not the correct %s CDROM.")
                                       % (productName,))
                    isys.umount("/mnt/source")
                    if self.noeject:
                        log.info("noeject in effect, not ejecting cdrom")
                    else:
                        isys.ejectCdrom(self.device)
            except:
                self.messageWindow(_("Error"), 
                        _("Unable to access the CDROM."))

    def unlinkFilename(self, fullName):
        pass

    def filesDone(self):
        # we're trying to unmount the CD here.  if it fails, oh well,
        # they'll reboot soon enough I guess :)
        try:
            isys.umount("/mnt/source")
        except Exception, e:
            log.error("unable to unmount source in filesDone: %s" %(e,))
        
        if not self.loopbackFile: return

	try:
	    # this isn't the exact right place, but it's close enough
	    os.unlink(self.loopbackFile)
	except SystemError:
	    pass

    def __init__(self, method, rootPath, intf, noeject=False):
        """@param method cdrom://device:/path"""
        url = method[8:]
	(self.device, tree) = string.split(url, ":", 1)
        if not tree.startswith("/"):
            tree = "/%s" %(tree,)
	self.messageWindow = intf.messageWindow
	self.progressWindow = intf.progressWindow
	self.waitWindow = intf.waitWindow
        self.loopbackFile = None
        self.noeject = noeject

        # figure out which disc is in.  if we fail for any reason,
        # assume it's just disc1.
        if os.access("/mnt/source/.discinfo", os.R_OK):
            try:
                f = open("/mnt/source/.discinfo")
                self.timestamp = f.readline().strip()
                f.readline() # descr
                f.readline() # arch
                self.currentMedia = getDiscNums(f.readline().strip())
                f.close()
            except:
                self.currentMedia = [ 1 ]
                self.timestamp = None
        else:                
            self.currentMedia = [ 1 ]
        
	ImageInstallMethod.__init__(self, tree, rootPath, intf)

class NfsInstallMethod(ImageInstallMethod):

    def badPackageError(self, pkgname):
        return _("The file %s cannot be opened.  This is due to a missing "
                 "file or perhaps a corrupt package.  Please verify your "
                 "installation tree contains all required packages.\n\n"
                 "If you reboot, your system will be left in an inconsistent "
                 "state that will likely require reinstallation.\n\n") % pkgname

    def __init__(self, method, rootPath, intf):
        """@param method: nfs:/mnt/source"""
        tree = method[5:]
	ImageInstallMethod.__init__(self, tree, rootPath, intf)
        self.splitmethod = False
        self.currentMedia = []

def getDiscNums(line):
    # get the disc numbers for this disc
    nums = line.split(",")
    discNums = []
    for num in nums:
        discNums.append(int(num))
    return discNums

def findIsoImages(path, messageWindow):
    flush = os.stat(path)
    files = os.listdir(path)
    arch = _arch
    discImages = {}

    for file in files:
	what = path + '/' + file
	if not isys.isIsoImage(what):
            continue

	isys.makeDevInode("loop2", "/tmp/loop2")

	try:
	    isys.losetup("/tmp/loop2", what, readOnly = 1)
	except SystemError:
	    continue

	try:
	    isys.mount("loop2", "/mnt/cdimage", fstype = "iso9660",
		       readOnly = 1)
	    for num in range(1, 10):
		if os.access("/mnt/cdimage/.discinfo", os.R_OK):
                    f = open("/mnt/cdimage/.discinfo")
                    try:
                        f.readline() # skip timestamp
                        f.readline() # skip release description
                        discArch = string.strip(f.readline()) # read architecture
                        discNum = getDiscNums(f.readline().strip())
                    except:
                        discArch = None
                        discNum = [ 0 ]

                    f.close()

                    if num not in discNum or discArch != arch:
                        continue

                    # if it's disc1, it needs to have images/stage2.img
                    if (num == 1 and not
                        os.access("/mnt/cdimage/images/stage2.img", os.R_OK)):
                        log.warning("%s doesn't have a stage2.img, skipping" %(what,))
                        continue
                    # we only install binary packages, so let's look for a
                    # product/ dir and hope that this avoids getting
                    # discs from the src.rpm set
                    if not os.path.isdir("/mnt/cdimage/%s" %(productPath,)):
                        log.warning("%s doesn't have binary RPMS, skipping" %(what,))
                        continue
                    
		    # warn user if images appears to be wrong size
		    if os.stat(what)[stat.ST_SIZE] % 2048:
			rc = messageWindow(_("Warning"),
	       "The ISO image %s has a size which is not "
	       "a multiple of 2048 bytes.  This may mean "
	       "it was corrupted on transfer to this computer."
	       "\n\n"
               "It is recommended that you reboot and abort your "
               "installation, but you can choose to continue if "
               "you think this is in error." % (file,),
                                           type="custom",
                                           custom_icon="warning",
                                           custom_buttons= [_("_Reboot"),
                                                            _("_Continue")])
                        if rc == 0:
			    sys.exit(0)

		    discImages[num] = file

	    isys.umount("/mnt/cdimage")
	except SystemError:
	    pass

	isys.makeDevInode("loop2", '/tmp/' + "loop2")
	isys.unlosetup("/tmp/loop2")

    return discImages

class NfsIsoInstallMethod(NfsInstallMethod):

    def getMethodUri(self):
        return "file:///tmp/isomedia/"

    def getFilename(self, filename, callback=None, destdir=None, retry=1):
	return self.mntPoint + "/" + filename

    def switchMedia(self, mediano, filename=""):
	if mediano not in self.currentMedia:
            log.info("switching from iso %s to %s for %s" %(self.currentMedia, mediano, filename))
	    self.umountImage()
	    self.mountImage(mediano)

    def badPackageError(self, pkgname):
        return _("The file %s cannot be opened.  This is due to a missing "
                 "file or perhaps a corrupt package.  Please verify your "
                 "installation images and that you have all the required "
                 "media.\n\n"
                 "If you reboot, your system will be left in an inconsistent "
                 "state that will likely require reinstallation.\n\n") % pkgname

    def umountImage(self):
	if self.currentMedia:
	    isys.umount(self.mntPoint)
	    isys.makeDevInode("loop3", "/tmp/loop3")
	    isys.unlosetup("/tmp/loop3")
	    self.mntPoint = None
	    self.currentMedia = []

    def mountImage(self, cdNum):
	if (self.currentMedia):
	    raise SystemError, "trying to mount already-mounted iso image!"

	retrymount = True
	while retrymount:
	    try:
	        isoImage = self.isoPath + '/' + self.discImages[cdNum]

	        isys.makeDevInode("loop3", "/tmp/loop3")
	        isys.losetup("/tmp/loop3", isoImage, readOnly = 1)
	
	        isys.mount("loop3", "/tmp/isomedia", fstype = 'iso9660', readOnly = 1);
	        self.mntPoint = "/tmp/isomedia/"
	        self.currentMedia = [ cdNum ]

	        retrymount = False
	    except:
	        ans = self.messageWindow( _("Missing ISO 9660 Image"),
	                                  _("The installer has tried to mount "
	                                    "image #%s, but cannot find it on "
	                                    "the server.\n\n"
	                                    "Please copy this image to the "
	                                    "remote server's share path and "
	                                    "click Retry. Click Reboot to "
	                                    "abort the installation.")
	                                    % (cdNum,), type="custom",
	                                    custom_icon="warning",
	                                    custom_buttons=[_("_Reboot"),
	                                                    _("Re_try")])
	        if ans == 0:
	            sys.exit(0)
	        elif ans == 1:
	            self.discImages = findIsoImages(self.isoPath, self.messageWindow)

    def filesDone(self):
        # if we can't unmount the cd image, we really don't care much
        # let them go along and don't complain
        try:
            self.umountImage()
        except Exception, e:
            log.error("unable to unmount image in filesDone: %s" %(e,))
            pass

    def __init__(self, method, rootPath, intf):
        """@param method: nfsiso:/mnt/source"""
        tree = method[8:]
	ImageInstallMethod.__init__(self, "/%s" % tree, rootPath, intf)
	self.messageWindow = intf.messageWindow

	# the tree points to the directory that holds the iso images
	# even though we already have the main one mounted once, it's
	# easiest to just mount it again so that we can treat all of the
	# images the same way -- we use loop3 for everything
        self.currentMedia = []

	self.discImages = findIsoImages(tree, self.messageWindow)
	self.mountImage(1)
