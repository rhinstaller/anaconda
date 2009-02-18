#
# bootloader.py - generic boot loader handling backend for up2date and anaconda
#
# Jeremy Katz <katzj@redhat.com>
# Adrian Likins <alikins@redhat.com>
# Peter Jones <pjones@redhat.com>
#
# Copyright 2001-2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""Module for manipulation and creation of boot loader configurations"""

import os, sys
import stat
import time
import shutil
import lilo

import checkbootloader
import rhpl
import rhpl.executil
from bootloaderInfo import *


# return instance of the appropriate bootloader for our arch
def getBootloader():
    """Get the bootloader info object for your architecture"""
    if rhpl.getArch() == 'i386':
        return x86BootloaderInfo()
    elif rhpl.getArch() == 'ia64':
        return ia64BootloaderInfo()
    elif rhpl.getArch() == 's390' or rhpl.getArch() == "s390x":
        return s390BootloaderInfo()
    elif rhpl.getArch() == "alpha":
        return alphaBootloaderInfo()
    elif rhpl.getArch() == "x86_64":
        return x86BootloaderInfo()
    elif rhpl.getPPCMachine() == "iSeries":
        return iseriesBootloaderInfo()
    elif rhpl.getArch() == "ppc":
        return ppcBootloaderInfo()
    elif rhpl.getArch() == "sparc":
        return sparcBootloaderInfo()
    else:
        return bootloaderInfo()

# path is the path to the new kernel image
# initrd is the path to the initrd (or None if it doesn't exist)
# label is the label for the image
# config is the full LiloConfigFile object for the config file
# default is the LiloConfigFile object for the default Linux-y entry
def addImage(path, initrd, label, config, default):
    # these directives must be on a per-image basis and are non-sensical
    # otherwise
    dontCopy = ['initrd', 'alias', 'label']
    
    entry = lilo.LiloConfigFile(imageType = "image", path = path)

    if label:
        entry.addEntry("label", label)
    else:
        raise RuntimeError, "Unable to determine a label for %s.  Aborting" % (path,)

    if initrd:
        entry.addEntry("initrd", initrd)

    # go through all of the things listed for the default
    # config entry and if they're not in our blacklist
    # of stuff not to copy, go ahead and copy it
    entries = default.listEntries()
    for key in entries.keys():
        if key in dontCopy:
            pass
        else:
            entry.addEntry(key, default.getEntry(key))

    config.addImage(entry, 1)


# note that this function no longer actually creates an initrd.
# the kernel's %post does this now
def makeInitrd (kernelTag, instRoot):
    if rhpl.getArch() == 'ia64':
        initrd = "/boot/efi/EFI/redhat/initrd%s.img" % (kernelTag, )
    else:
        initrd = "/boot/initrd%s.img" % (kernelTag, )

    return initrd
