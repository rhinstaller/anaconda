#
# image.py - Install method for disk image installs (CD & NFS)
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
import iutil
import os
import isys
import time
import stat
import kudzu
import string
import shutil
from constants import *

from rhpl.log import log
from rhpl.translate import _

# this sucks, but we want to consider s390x as s390x in here but generally
# don't.  *sigh*
if os.uname()[4] == "s390x":
    _arch = "s390x"
else:
    _arch = iutil.getArch()

class ImageInstallMethod(InstallMethod):

    def readCompsViaMethod(self, hdlist):
	fname = self.findBestFileMatch(self.tree, 'comps.xml')
        if fname is None:
            raise FileCopyException
	return groupSetFromCompsFile(fname, hdlist)

    def getFilename(self, h, timer):
        if h[1000005] is not None and self.updatesCopied == 1:
            log ("going to use cached package for %s" %(h[1000000],))
            return "/var/spool/anaconda-updates/" + h[1000000]
        if self.currentIso is not None and self.currentIso != h[1000002]:
            log("switching from iso %s to %s for %s-%s-%s.%s" %(self.currentIso, h[1000002], h['name'], h['version'], h['release'], h['arch']))
            
        self.currentIso = h[1000002]
        if h[1000005] is not None:
            path = "/RedHat/Updates/"
        else:
            path = "/RedHat/RPMS/"
	return self.tree + path + h[1000000]

    def readHeaders(self):
        if not os.access(self.tree + "/RedHat/base/hdlist", os.R_OK):
            raise FileCopyException
	return HeaderListFromFile(self.tree + "/RedHat/base/hdlist")

    def mergeFullHeaders(self, hdlist):
        if not os.access(self.tree + "/RedHat/base/hdlist2", os.R_OK):
            raise FileCopyException
	hdlist.mergeFullHeaders(self.tree + "/RedHat/base/hdlist2")

    def getSourcePath(self):
        return self.tree

    def copyFileToTemp(self, filename):
        tmppath = self.getTempPath()
        path = tmppath + os.path.basename(filename)
        shutil.copy(self.tree + "/" + filename, path)
        
        return path

    def __init__(self, tree, rootPath):
	InstallMethod.__init__(self, rootPath)
	self.tree = tree
        self.currentIso = None

class CdromInstallMethod(ImageInstallMethod):

    def unmountCD(self):
        done = 0
        while done == 0:
            try:
                isys.umount("/mnt/source")
                self.currentDisc = []
                break
            except:
                self.messageWindow(_("Error"),
                                   _("An error occurred unmounting the CD.  "
                                     "Please make sure you're not accessing "
                                     "%s from the shell on tty2 "
                                     "and then click OK to retry.")
                                   % ("/mnt/source",))

    def ejectCD(self):
	log("ejecting CD")

	# make /tmp/cdrom again so cd gets ejected
	isys.makeDevInode(self.device, "/tmp/cdrom")
	    
        try:
            isys.ejectCdrom("/tmp/cdrom", makeDevice = 0)
        except Exception, e:
	    log("eject failed %s" % (e,))
            pass

    def systemUnmounted(self):
	if self.loopbackFile:
	    isys.makeDevInode("loop0", "/tmp/loop")
	    isys.lochangefd("/tmp/loop", 
			"%s/RedHat/base/stage2.img" % self.tree)
	    self.loopbackFile = None

    def systemMounted(self, fsset, chroot):
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
        if h[1000005] is not None and self.updatesCopied == 1:
            log ("going to use cached package for %s" %(h[1000000],))
            return "/var/spool/anaconda-updates/" + h[1000000]
        if h[1000002] == None:
            log ("header for %s has no disc location tag, assuming it's"
                 "on the current CD", h[1000000])
        elif h[1000002] not in self.currentDisc:
	    timer.stop()
            log("switching from iso %s to %s for %s-%s-%s.%s" %(self.currentDisc, h[1000002], h['name'], h['version'], h['release'], h['arch']))

            if os.access("/mnt/source/.discinfo", os.R_OK):
                f = open("/mnt/source/.discinfo")
                timestamp = f.readline().strip()
                f.close()
            else:
                timestamp = self.timestamp

            if self.timestamp is None:
                self.timestamp = timestamp

	    needed = h[1000002]

            # if self.currentDisc is empty, then we shouldn't have anything
            # mounted.  double-check by trying to unmount, but we don't want
            # to get into a loop of trying to unmount forever.  if
            # self.currentDisc is set, then it should still be mounted and
            # we want to loop until it unmounts successfully
            if not self.currentDisc:
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
                                self.currentDisc = discNum

			if not done:
			    isys.umount("/mnt/source")
		except:
		    pass

		if done:
		    break

	    if not done:
		isys.ejectCdrom(self.device)

	    while not done:
		self.messageWindow(_("Change CDROM"), 
		    _("Please insert disc %d to continue.") % needed)

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
                            self.currentDisc = discNum
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

        # if we haven't read a timestamp yet, let's try to get one
        if (self.timestamp is None and
            os.access("/mnt/source/.discinfo", os.R_OK)):
            try:
                f = open("/mnt/source/.discinfo")
                self.timestamp = f.readline().strip()
                f.close()
            except:
                pass

        tmppath = self.getTempPath()
        tries = 0
        # FIXME: should retry a few times then prompt for new cd
        while tries < 5:
            try:
                if h[1000005] is not None:
                    path = "/RedHat/Updates/"
                else:
                    path = "/RedHat/RPMS/"
                
                shutil.copy(self.tree + path + h[1000000],
                            tmppath + h[1000000])
            except IOError, (errnum, msg):
                log("IOError %s occurred copying %s: %s",
                    errnum, h[1000000], str(msg))
                time.sleep(5)
            else:
                break
            tries = tries + 1

        if tries >= 5:
            raise FileCopyException
                        
	return tmppath + h[1000000]

    def unlinkFilename(self, fullName):
        os.remove(fullName)

    def filesDone(self):
        # we're trying to unmount the CD here.  if it fails, oh well,
        # they'll reboot soon enough I guess :)
        try:
            isys.umount("/mnt/source")
        except:
            log("unable to unmount source in filesDone")
        
        if not self.loopbackFile: return

	try:
	    # this isn't the exact right place, but it's close enough
	    os.unlink(self.loopbackFile)
	except SystemError:
	    pass
        

    def __init__(self, url, messageWindow, progressWindow, rootPath):
	(self.device, tree) = string.split(url, ":", 1)
        if not tree.startswith("/"):
            tree = "/%s" %(tree,)
	self.messageWindow = messageWindow
	self.progressWindow = progressWindow
        self.loopbackFile = None

        # figure out which disc is in.  if we fail for any reason,
        # assume it's just disc1.
        if os.access("/mnt/source/.discinfo", os.R_OK):
            try:
                f = open("/mnt/source/.discinfo")
                self.timestamp = f.readline().strip()
                f.readline() # descr
                f.readline() # arch
                self.currentDisc = getDiscNums(f.readline().strip())
                f.close()
            except:
                self.currentDisc = [ 1 ]
                self.timestamp = None
        else:                
            self.currentDisc = [ 1 ]
        
	ImageInstallMethod.__init__(self, tree, rootPath)
        self.needUpdateCache = 1        

class NfsInstallMethod(ImageInstallMethod):

    def __init__(self, tree, rootPath):
	ImageInstallMethod.__init__(self, tree, rootPath)

def getDiscNums(line):
    # get the disc numbers for this disc
    nums = line.split(",")
    discNums = []
    for num in nums:
        discNums.append(int(num))
    return discNums

def findIsoImages(path, messageWindow):
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

                    # if it's disc1, it needs to have RedHat/base/stage2.img
                    if (num == 1 and not
                        os.access("/mnt/cdimage/RedHat/base/stage2.img",
                                  os.R_OK)):
                        continue
                    
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
            log("switching from iso %s to %s for %s-%s-%s.%s" %(self.imageMounted, h[1000002], h['name'], h['version'], h['release'], h['arch']))
	    self.umountImage()
	    self.mountImage(h[1000002])

        if h[1000005] is not None:
            path = "/RedHat/Updates/"
        else:
            path = "/RedHat/RPMS/"

	return self.mntPoint + path + h[1000000]

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
        # if we can't unmount the cd image, we really don't care much
        # let them go along and don't complain
        try:
            self.umountImage()
        except:
            log("unable to unmount iimage in filesDone")
            pass

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

