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
from constants import *

import logging
log = logging.getLogger("anaconda")

class FileCopyException(Exception):
    def __init__(self, s = ""):
        self.args = s
        

class InstallMethod:
    def protectedPartitions(self):
        return None

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
            log.warning("Unable to find temp path, going to use ramfs path")
            return "/tmp/"

        return tmppath

    def getFilename(self, filename, callback=None, destdir=None, retry=1):
	pass

    def systemUnmounted(self):
	pass

    def systemMounted(self, fstab, mntPoint):
	pass

    def filesDone(self):
	pass

    def unlinkFilename(self, fullName):
	pass

    def __init__(self, method, rootpath, intf):
        self.rootPath = rootpath
        self.intf = intf
        self.tree = None
        self.splitmethod = False

    def getMethodUri(self):
        pass

    def getSourcePath(self):
        pass

    def unmountCD(self):
        pass

    def ejectCD(self):
        pass

    def badPackageError(self, pkgname):
        pass


# this handles any cleanup needed for the method.  it occurs *very* late
# (ie immediately before the congratulations screen).  main use right now
# is ejecting the cdrom
def doMethodComplete(anaconda):
    anaconda.method.filesDone()
    anaconda.method.ejectCD()

    mtab = "/dev/root / ext3 ro 0 0\n"
    for ent in anaconda.id.fsset.entries:
        if ent.mountpoint == "/":
            mtab = "/dev/root / %s ro 0 0\n" %(ent.fsystem.name,)
    
    f = open(anaconda.rootPath + "/etc/mtab", "w+")
    f.write(mtab)
    f.close()
