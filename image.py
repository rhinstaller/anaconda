# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderListFromFile
from installmethod import InstallMethod
import iutil
import os
import isys

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
	target = "%s/rhinstall-stage2.img" % mntPoint
	iutil.copyFile("%s/RedHat/base/stage2.img" % self.tree, target)
	isys.makeDevInode("loop0", "/tmp/loop")
	isys.lochangefd("/tmp/loop", target)

    def filesDone(self):
	# this isn't the exact right place, but it's close enough
	target = "%s/rhinstall-stage2.img" % mntPoint
	os.unlink(target)

    def __init__(self, tree):
	ImageInstallMethod.__init__(self, tree)

class NfsInstallMethod(ImageInstallMethod):

    def __init__(self, tree):
	ImageInstallMethod.__init__(self, tree)
