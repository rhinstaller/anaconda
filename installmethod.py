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
from hdrlist import groupSetFromCompsFile
import isys
import iutil
import shutil

from rhpl.log import log
from rhpl.translate import _

class FileCopyException(Exception):
    def __init__(self, s = ""):
        self.args = s
        

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
	    return groupSetFromCompsFile(path, hdlist)
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
            log("Unable to find temp path, going to use ramfs path")
            return "/tmp/"

        return tmppath

    def getFilename(self, h, timer):
	pass

    def readHeaders(self):
	pass

    def systemUnmounted(self):
	pass

    def systemMounted(self, fstab, mntPoint):
	pass

    def cacheUpdates(self, chroot, hdlist, intf):
        if self.needUpdateCache == 0:
            log("not caching updates")
            return
        log("going to cache updates")
        size = 0
        num = 0
        for h in hdlist.values():
            if h.isSelected() and h[1000005] is not None:
                log("%s is selected, size is %s" %(h.nevra(), h[1000001]))
                size += h[1000001] # FILESIZE_TAG
                num += 1
        # make sure it looks like we have space + a fudge factor
        if not (size / 1024.0 / 1024.0) > (isys.fsSpaceAvailable("/mnt/sysimage/var") + 50):
            log("only %s free on var and want %s, not caching updates" %(isys.fsSpaceAvailable, size))
            return
        if num == 0:
            return

        if intf:
            win = intf.progressWindow(_("Copying Files"),
                                      _("Transferring updated packages"), num)
        iutil.mkdirChain(chroot + "/var/spool/anaconda-updates")
        num = 0
        for h in hdlist.values():
            if h.isSelected() and h[1000005] is not None:
                path = "/RedHat/Updates/"
                shutil.copy(self.tree + path + h[1000000],
                            "%s/var/spool/anaconda-updates/%s" % (chroot, h[1000000]))
                num += 1
                if intf:
                    win.set(num)
        if intf:
            win.pop()
        self.updatesCopied = 1

    def filesDone(self):
	pass

    def unlinkFilename(self, fullName):
	pass

    def __init__(self, rootpath):
        self.rootPath = rootpath
        self.needUpdateCache = 0
        self.updatesCopied = 0
        try:
            f = open("/proc/cmdline")
            line = f.readline()
            if string.find(line, " cacheupdates") != -1:
                self.needUpdateCache = 1
            f.close()
        except:
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
