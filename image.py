# Install method for disk image installs (CD & NFS)

import rpm

class InstallMethod:

    def readHeaders(self):
	return rpm.readHeaderList(self.tree + "/RedHat/base/hdlist")

    def __init__(self, tree):
	self.tree = tree
