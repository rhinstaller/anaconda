# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderListFromFile
from installmethod import InstallMethod
import iutil
import os
import isys
import string
from translate import _
from log import log

class ImageInstallMethod(InstallMethod):

    def readComps(self, hdlist):
	return ComponentSet(self.tree + '/RedHat/base/comps', hdlist)

    def getFilename(self, h):
	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def readHeaders(self):
	return HeaderListFromFile(self.tree + "/RedHat/base/hdlist")

    def __init__(self, tree):
	InstallMethod.__init__(self)
	self.tree = tree

class CdromInstallMethod(ImageInstallMethod):

    def systemMounted(self, fstab, mntPoint):
	self.mntPoint = mntPoint
	target = "%s/rhinstall-stage2.img" % mntPoint
	iutil.copyFile("%s/RedHat/base/stage2.img" % self.tree, target,
			(self.progressWindow, _("Copying File"),
			_("Transferring install image to hard drive...")))
	isys.makeDevInode("loop0", "/tmp/loop")
	isys.lochangefd("/tmp/loop", target)

    def getFilename(self, h):
        if h[1000002] == None:
            log ("header for %s has no disc location tag, assuming it's"
                 "on the current CD", h[1000000])
        elif h[1000002] != self.currentDisc:
	    self.currentDisc = h[1000002]
	    isys.umount("/mnt/source")
	    isys.ejectCdrom(self.device)

	    key = ".disc%d-%s" % (self.currentDisc, iutil.getArch())

	    done = 0
	    while not done:
		self.messageWindow(_("Change CDROM"), 
		    _("Please insert disc %d to continue.") % self.currentDisc)

		try:
		    isys.mount(self.device, "/mnt/source", fstype = "iso9660",
			       readOnly = 1)
		    
		    if os.access("/mnt/source/%s" % key, os.O_RDONLY):
			done = 1
		    else:
			self.messageWindow(_("Wrong CDROM"),
				_("That's not the correct Red Hat CDROM."))
			isys.umount("/mnt/source")
			isys.ejectCdrom(self.device)
		except:
		    self.messageWindow(_("Error"), 
			    _("The CDROM could not be mounted."))

	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def filesDone(self):
	# this isn't the exact right place, but it's close enough
	target = "%s/rhinstall-stage2.img" % self.mntPoint
	os.unlink(target)

    def __init__(self, url, messageWindow, progressWindow):
	(self.device, tree) = string.split(url, "/", 1)
	self.messageWindow = messageWindow
	self.progressWindow = progressWindow
	self.currentDisc = 1
	ImageInstallMethod.__init__(self, "/" + tree)

class NfsInstallMethod(ImageInstallMethod):

    def __init__(self, tree):
	ImageInstallMethod.__init__(self, tree)
