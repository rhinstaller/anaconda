#
# image.py - Install method for disk image installs (CD & NFS)
#
# Copyright 1999-2004 Red Hat, Inc.
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
import sys
import isys
import time
import stat
import kudzu
import string
import shutil
import product

from constants import *

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

# this sucks, but we want to consider s390x as s390x in here but generally
# don't.  *sigh*
if os.uname()[4] == "s390x":
    _arch = "s390x"
else:
    _arch = iutil.getArch()

# given groupset containing information about selected packages, use
# the disc number info in the headers to come up with message describing
# the required CDs
#
# dialog returns a value of 0 if user selected to abort install
def presentRequiredMediaMessage(intf, grpset):
    reqcds = []
    for hdr in grpset.hdrlist.values():
        if not hdr.isSelected():
	    continue
	elif hdr[1000002] not in reqcds:
	    reqcds.append(hdr[1000002])
	else:
	    continue

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
        haveall = 1
        for cd in reqcds:
            if cd not in discNums:
                log.error("don't have %s" %(cd,))
                haveall = 0
                break

        if haveall == 1:
            return

    reqcds.sort()
    reqcdstr = ""
    for cdnum in reqcds:
	reqcdstr += "\t\t%s %s CD #%d\n" % (product.productName, product.productVersion, cdnum,)
		
    return intf.messageWindow( _("Required Install Media"),
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

    def readComps(self, hdlist):
	fname = self.findBestFileMatch('comps.xml')
        if fname is None:
            raise FileCopyException
	return groupSetFromCompsFile(fname, hdlist)

    def getFilename(self, filename, callback=None, destdir=None, retry=1):
	return self.tree + "/" + filename

    def getRPMFilename(self, h, timer, callback=None):
        if self.currentIso is not None and self.currentIso != h[1000002]:
            log.info("switching from iso %s to %s for %s-%s-%s.%s" %(self.currentIso, h[1000002], h['name'], h['version'], h['release'], h['arch']))
        self.currentIso = h[1000002]
	return self.getFilename("/%s/RPMS/%s" % (productPath, h[1000000]), callback=callback)
    def readHeaders(self):
        if not os.access("%s/%s/base/hdlist" % (self.tree, productPath), os.R_OK):
            raise FileCopyException
	hl = HeaderListFromFile("%s/%s/base/hdlist" % (self.tree, productPath))

	return hl
    
    def mergeFullHeaders(self, hdlist):
        if not os.access("%s/%s/base/hdlist2" % (self.tree, productPath), os.R_OK):
            raise FileCopyException
	hdlist.mergeFullHeaders("%s/%s/base/hdlist2" % (self.tree, productPath))

    def getSourcePath(self):
        return self.tree

    def copyFileToTemp(self, filename):
        tmppath = self.getTempPath()
        path = tmppath + os.path.basename(filename)
        shutil.copy(self.tree + "/" + filename, path)
        
        return path

    def __init__(self, tree, rootPath, intf):
	InstallMethod.__init__(self, tree, rootPath, intf)
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
            except Exception, e:
                log.error("exception in unmountCD: %s" %(e,))
                self.messageWindow(_("Error"),
                                   _("An error occurred unmounting the CD.  "
                                     "Please make sure you're not accessing "
                                     "%s from the shell on tty2 "
                                     "and then click OK to retry.")
                                   % ("/mnt/source",))

    def ejectCD(self):
	log.info("ejecting CD")

	# make /tmp/cdrom again so cd gets ejected
	isys.makeDevInode(self.device, "/tmp/cdrom")
	    
        try:
            isys.ejectCdrom("/tmp/cdrom", makeDevice = 0)
        except Exception, e:
	    log.error("eject failed %s" % (e,))
            pass

    def systemUnmounted(self):
	if self.loopbackFile:
	    isys.makeDevInode("loop0", "/tmp/loop")
	    isys.lochangefd("/tmp/loop", 
			"%s/%s/base/stage2.img" % (self.tree, productPath))
	    self.loopbackFile = None

    def systemMounted(self, fsset, chroot):
	self.loopbackFile = "%s%s%s" % (chroot,
                                        fsset.filesystemSpace(chroot)[0][0],
                                        "/rhinstall-stage2.img")

	try:
	    iutil.copyFile("%s/%s/base/stage2.img" % (self.tree, productPath), 
			    self.loopbackFile,
			    (self.progressWindow, _("Copying File"),
			    _("Transferring install image to hard drive...")))
	except Exception, e:
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

    def getRPMFilename(self, h, timer, callback=None):
        if h[1000002] == None or 1000002 not in h.keys():
            log.warning("header for %s has no disc location tag, assuming it's"
                        "on the current CD" %(h[1000000],))
        elif h[1000002] not in self.currentDisc:
	    timer.stop()
            log.info("switching from iso %s to %s for %s-%s-%s.%s" %(self.currentDisc, h[1000002], h['name'], h['version'], h['release'], h['arch']))

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
			    _("Unable to access the CDROM."))

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
                shutil.copy("%s/%s/RPMS/%s" % (self.tree, productPath,
                                               h[1000000]),
                            tmppath + h[1000000])
            except IOError, (errnum, msg):
                log.critical("IOError %s occurred copying %s: %s",
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
        except Exception, e:
            log.error("unable to unmount source in filesDone: %s" %(e,))
        
        if not self.loopbackFile: return

	try:
	    # this isn't the exact right place, but it's close enough
	    os.unlink(self.loopbackFile)
	except SystemError:
	    pass
        

    def __init__(self, url, rootPath, intf):
	(self.device, tree) = string.split(url, ":", 1)
        if not tree.startswith("/"):
            tree = "/%s" %(tree,)
	self.messageWindow = intf.messageWindow
	self.progressWindow = intf.progressWindow
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
        
	ImageInstallMethod.__init__(self, tree, rootPath, intf)

class NfsInstallMethod(ImageInstallMethod):

    def __init__(self, tree, rootPath, intf):
	ImageInstallMethod.__init__(self, tree, rootPath, intf)

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

                    # if it's disc1, it needs to have product/base/stage2.img
                    if (num == 1 and not
                        os.access("/mnt/cdimage/%s/base/stage2.img" % (productPath,),
                                  os.R_OK)):
                        log.warning("%s doesn't have a stage2.img, skipping" %(what,))
                        continue
                    # we only install binary packages and they have to be
                    # in the product/RPMS/ dir.  make sure it exists to
                    # avoid overwriting discs[2] with disc2 of the src.rpm set
                    if not os.path.isdir("/mnt/cdimage/%s/RPMS" %(productPath,)):
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
    def getFilename(self, filename, callback=None, destdir=None, retry=1):
	return self.mntPoint + "/" + filename
    
    def getRPMFilename(self, h, timer, callback=None):
	if self.imageMounted != h[1000002]:
            log.info("switching from iso %s to %s for %s-%s-%s.%s" %(self.imageMounted, h[1000002], h['name'], h['version'], h['release'], h['arch']))
	    self.umountImage()
	    self.mountImage(h[1000002])

	return self.getFilename("/%s/RPMS/%s" % (productPath, h[1000000]))

    def readHeaders(self):
	hl = NfsInstallMethod.readHeaders(self)

	# Make sure all of the correct CD images are available
	missing_images = []
	for h in hl.values():
	    if h[1000002] is None or 1000002 not in h.keys():
		continue
	    
	    if not self.discImages.has_key(h[1000002]):
		if h[1000002] not in missing_images:
		    missing_images.append(h[1000002])

	if len(missing_images) > 0:
	    missing_images.sort()
	    missing_string = ""
	    for missing in missing_images:
		missing_string += "\t\t\tCD #%d\n" % (missing,)

	    self.messageWindow(_("Error"),
			       _("The following ISO images are missing which "
                                 "are required for the install:\n\n%s\n"
                                 "The system will now reboot.") %
                               (missing_string,))
	    sys.exit(0)

	return hl


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
        except Exception, e:
            log.error("unable to unmount image in filesDone: %s" %(e,))
            pass

    def __init__(self, tree, rootPath, intf):
	self.messageWindow = intf.messageWindow
	self.imageMounted = None
	self.isoPath = tree

	# the tree points to the directory that holds the iso images
	# even though we already have the main one mounted once, it's
	# easiest to just mount it again so that we can treat all of the
	# images the same way -- we use loop3 for everything

	self.discImages = findIsoImages(tree, self.messageWindow)
	self.mountImage(1)

	ImageInstallMethod.__init__(self, self.mntPoint, rootPath, intf)

