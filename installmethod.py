#
# installmethod.py - Base class for install methods
#
# Copyright 1999-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import string
from comps import ComponentSet

from rhpl.log import log

class FileCopyException(Exception):
    def __init__(self, s = ""):
        self.str = s
        

class InstallMethod:

    # find best match from several locations for a file
    def findBestFileMatch(self, treebase, file):
	# look in /tmp/updates first
	rc = None
	tryloc = ["/tmp/updates"]
	if treebase is not None:
	    tryloc.append(treebase + "/RHupdates")
	    tryloc.append(treebase + "/RedHat/base")
	    
	for pre in tryloc:
	    tmpname = pre + "/" + file
	    if os.access(tmpname, os.R_OK):
		log("Using file://%s", tmpname)
		return "file://%s" %(tmpname,)

	log("Unable to find %s", file)
	return None
	
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

    def unmountCD(self):
        pass

    def ejectCD(self):
        pass


# this handles any cleanup needed for the method.  it occurs *very* late
# (ie immediately before the congratulations screen).  main use right now
# is ejecting the cdrom
def doMethodComplete(method):
    method.ejectCD()
