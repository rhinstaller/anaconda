# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderListFromFile

class InstallMethod:

    def readComps(self, hdlist):
	return ComponentSet(self.tree + '/RedHat/base/comps', hdlist)

    def getFilename(self, h):
	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def readHeaders(self):
	return HeaderListFromFile(self.tree + "/RedHat/base/hdlist")

    def targetFstab(self, fstab):
	pass

    def filesDone(self):
	pass

    def unlinkFilename(self, fullName):
	pass

    def __init__(self, tree):
	self.tree = tree
