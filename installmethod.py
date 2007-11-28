#
# installmethod.py - Base class for install methods
#
# Copyright 1999-2007 Red Hat, Inc.
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

## The base installation method class.
# This is an abstract class that defines the methods that make up an
# installation method.  This class should not be used except as the superclass
# for a specific method.  Most methods in this class should be redefined by
# subclasses, though things like mountCD, unmountCD, ejectCD, and the cleanup
# methods may not need to be redefined.  By default, most methods pass.
class InstallMethod:
    ## Perform method-specific actions to mount any installation media.
    # @param fsset An instance of FileSystemSet.
    # @param mntPoint The root of the filesystem to mount the media onto.
    def systemMounted(self, fsset, mntPoint):
	pass

    ## Method-specific cleanup function to be called at the end of installation.
    # @see doMethodComplete
    # @see postAction
    def filesDone(self):
	pass

    ## The constructor.
    # @param method The --method= parameter passed to anaconda from loader.
    # @param rootpath The --rootpath= parameter passed to anaconda from loader.
    # @param intf An instance of the InstallInterface class.
    def __init__(self, method, rootpath, intf):
        self.rootPath = rootpath
        self.intf = intf
        self.tree = None

    ## Get the base URI for the method.
    # @return The base URI for this installation method.
    def getMethodUri(self):
        pass

    ## Unmount any CD media.
    def unmountCD(self):
        pass

    ## Switch CDs.
    # @param mediano The CD media number to switch to.
    # @param filename The file to be read that requires switching media.
    def switchMedia(self, mediano, filename=""):
	pass

    ## Method to be run at the very end of installation.
    #
    # This method is run very late.  It's the last step to be run before
    # showing the completion screen.  Only use this if you really know what
    # you're doing.
    # @param anaconda An instance of the Anaconda class.
    # @see filesDone
    # @see doMethodComplete
    def postAction(self, anaconda):
        pass

## Do method-specific cleanups.
#
# This occurs very late and is mainly used for unmounting media and ejecting
# the CD.  If we're on a kickstart install, don't eject the CD since there's
# a kickstart command to do that.
# @param anaconda An instance of the Anaconda class.
# @see InstallMethod::postAction
# @see InstallMethod::filesDone
def doMethodComplete(anaconda):
    anaconda.method.filesDone()

    if not anaconda.isKickstart:
        isys.ejectCdrom(anaconda.method.device, makeDevice=1)

    mtab = "/dev/root / ext3 ro 0 0\n"
    for ent in anaconda.id.fsset.entries:
        if ent.mountpoint == "/":
            mtab = "/dev/root / %s ro 0 0\n" %(ent.fsystem.name,)

    f = open(anaconda.rootPath + "/etc/mtab", "w+")
    f.write(mtab)
    f.close()
