import os

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

    def __init__(self):
	pass

    def getSourcePath(self):
        pass
