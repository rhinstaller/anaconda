# Install method for disk image installs (CD & NFS)

import rpm
from comps import ComponentSet

class InstallMethod:

    def readComps(self, hdlist):
	return ComponentSet('i386', self.tree + '/RedHat/base/comps', hdlist)

    def getFilename(self, h):
	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def readHeaders(self):
	return rpm.readHeaderList(self.tree + "/RedHat/base/hdlist")

    def __init__(self, tree):
	self.tree = tree
