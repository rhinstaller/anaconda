import os
import string
from comps import ComponentSet

class InstallMethod:

    def protectedPartitions(self):
        return None

    def readCompsViaMethod(self, hdlist):
	pass

    def readComps(self, hdlist):
	# see if there is a comps in PYTHONPATH, otherwise fall thru
	# to method dependent location
	path = None
	if os.environ.has_key('PYTHONPATH'):
	    for f in string.split(os.environ['PYTHONPATH'], ":"):
		if os.access (f+"/comps", os.X_OK):
		    path = f+"/comps"
		    break

	if path:
	    return ComponentSet(path, hdlist)
	else:
	    return self.readCompsViaMethod(hdlist)
	pass

    def getTempPath(self):
	root = self.rootPath
	pathlist = [ "/var/tmp", "/tmp",
		     "/." ]
        tmppath = None
	for p in pathlist:
	    if (os.access(root + p, os.X_OK)):
		tmppath = root + p + "/"
		break

        if tmppath is None:
            raise RuntimeError, "Unable to find temp path"

        return tmppath

    def getFilename(self, h, timer):
	pass

    def readHeaders(self):
	pass

    def systemUnmounted(self):
	pass

    def systemMounted(self, fstab, mntPoint, selected):
	pass

    def filesDone(self):
	pass

    def unlinkFilename(self, fullName):
	pass

    def __init__(self, rootpath):
        self.rootPath = rootpath
	pass

    def getSourcePath(self):
        pass
