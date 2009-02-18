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


# install the kernels in kernelList to your bootloader's config file
# (if needed)
# kernelList is a python list of (kernelVersion, extraInfo) tuples
# backupSuffix is the suffix to use backing up the config file if
#       we change it
# test is whether or not this is test mode
# filename is a filename to use instead of the default (testing only)
def installNewKernelImages(kernelList, backupSuffix = "rpmsave", test = 0,
                           filename = None):
    """Add the kernels in kernelList to the current boot loader config file"""

    if rhpl.getArch() == 'i386':
        return __installNewKernelImagesX86(kernelList, backupSuffix, test,
                                         filename)
    elif rhpl.getArch() == 'ia64':
        return __installNewKernelImagesIA64(kernelList, backupSuffix, test,
                                          filename)
    elif rhpl.getArch() == 'ppc':
        return __installNewKernelImagesPPC(kernelList, backupSuffix, test,
                                          filename)
    elif rhpl.getArch() == 'sparc':
        return __installNewKernelImagesSparc(kernelList, backupSuffix, test,
                                            filename)
    else:
        raise RuntimeError, "Don't know how to add new kernels for %s" % \
              (rhpl.getArch(),)


def __installNewKernelImagesX86(kernelList, backupSuffix, test, filename):
    theBootloader = checkbootloader.whichBootLoader()
    if theBootloader == "GRUB":
        __installNewKernelImagesX86Grub(kernelList, backupSuffix, test)
    else:
        raise RuntimeError, "Cannot determine x86 bootloader in use."
    
def __installNewKernelImagesX86Grub(kernelList, backupSuffix, test):
    # get the current default kernel in the grub config
    def getGrubDefault():
        pipe = os.popen("/sbin/grubby --default-kernel")
        ret = pipe.read()
        ret = string.strip(ret)

        return ret

    # set the default kernel in grub to the one at path
    def setGrubDefault(path, instRoot="/"):
        args = [instRoot + "/sbin/grubby", "--set-default", path]
        ret = rhpl.executil.execWithRedirect(args[0], args,
                                     stdout = None, stderr = None)

        return ret

    defaultImage = getGrubDefault()
    if test:
        print "defaultImage is %s" % (defaultImage,)
    
    # if we don't get any sort of answer back, do nothing
    if defaultImage:
        defaultType = getDefaultKernelType(defaultImage)

        # look for a kernel image of the same type
        for (newVersion, imageType) in kernelList:
            if defaultType == imageType:
                if test:
                    print "Would have set default to /boot/vmlinuz-%s" % (newVersion,)
                else:
                    setGrubDefault("/boot/vmlinuz-%s" % (newVersion,))
            
    

def __installNewKernelImagesIA64(kernelList, backupSuffix, test, filename):
    if not filename:
        filename = "/boot/efi/elilo.conf"
        
    config = updateLiloishConfigFile(kernelList, "/boot/efi/vmlinuz-%s",
                                     test, filename)

    backup = writeConfig(config, filename, backupSuffix, test)    

def __installNewKernelImagesPPC(kernelList, backupSuffix, test, filename):
    if not filename:
        filename = "/etc/yaboot.conf"
    
    config = updateLiloishConfigFile(kernelList, "/boot/vmlinu-%s",
                                     test, filename)

    backup = writeConfig(config, filename, backupSuffix, test)

    ret = yabootInstall("/")
    if ret:
        restoreBackup(filename, backup)
        raise RuntimeError, "Real install of yaboot failed"

def __installNewKernelImagesSparc(kernelList, backupSuffix, test, filename):
    if not filename:
        filename = "/etc/silo.conf"

    config = updateLiloishConfigFile(kernelList, "/boot/vmlinuz-%s",
                                    test, filename)

    backup = writeConfig(config, filename, backupSuffix, test)

    ret = siloInstall("/")
    if ret:
        restoreBackup(filename, backup)
        raise RuntimeError, "Real install of silo failed"

# used for updating lilo-ish config files (eg elilo as well)
def updateLiloishConfigFile(kernelList, kernelPathFormat, test, configFile):
    config = lilo.LiloConfigFile()

    # XXX should be able to create if one doesn't exist
    if not os.access(configFile, os.R_OK):
        return None

    # read in the config file and make sure we don't have any unsupported
    # options
    config.read(configFile)
    if len(config.unsupported):
        raise RuntimeError, ("Unsupported options in config file: %s" % 
                           (config.unsupported,))

    default = config.getDefaultLinux()
    if not default:
        raise RuntimeError, "Unable to find default linux entry"

    realDefault = config.getDefault()
    setdefault = None

    defaultType = getDefaultKernelType(default.path)
    rootDev = default.getEntry("root")

    for (newVersion, imageType) in kernelList:
        path = kernelPathFormat % (newVersion,)
        
        initrd = makeInitrd("-%s" % (newVersion,), "/")

        if not os.access(initrd, os.R_OK):
            initrd = None

        if imageType and imageType != defaultType:
            # linux-smp.linux-BOOT, etc
            label = "linux-"+imageType
        elif not imageType and defaultType:
            label = "linux-up"
        else:
            label = "linux"

        if label in config.listImages():
            backup = backupLabel(label, config.listImages())
            oldImage = config.getImage(label)[1]
            oldImage.addEntry("label", backup)
            if test:
                print "Renamed %s to %s" % (label, backup)

        # alikins did this once, I'm not doing it again - katzj
        if defaultType:
            if imageType:
                if defaultType == imageType:
                    setdefault = label
        else:
            if not imageType:
                setdefault = label
            
        addImage(path, initrd, label, config, default)

    # if the default linux image's label is the same as the real default's
    # label, then set what we've figured out as the default to be the
    # default
    if (default.getEntry('label') == realDefault.getEntry('label')) \
           and setdefault:
        config.addEntry("default", setdefault)
    else: # make sure the default entry is explicitly set
        config.addEntry("default", realDefault.getEntry('label'))

    if test:
        print config
    return config


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


# determine the type of the default kernel
# kernelPath is the path of the current default
def getDefaultKernelType(kernelPath):
    # XXX this isn't an ideal way to do this.  up2date was poking at the
    # rpmdb.  this is a simple but stupid way to figure out the simple
    # cases for now
    defaultType = None
    if kernelPath[-3:] == "smp":
        defaultType = "smp"
    elif kernelPath[-10:] == "enterprise":
        defaultType = "enterprise"
    elif kernelPath[-4:] == "BOOT":
        defaultType = "BOOT"
    elif kernelPath[-3:] == "ans":
        defaultType = "ans"
    elif kernelPath[-4:] == "briq":
        defaultType = "briq"
    elif kernelPath[-5:] == "teron":
        defaultType = "teron"
    elif kernelPath[-7:] == "pseries":
        defaultType = "pseries"
    elif kernelPath[-7:] == "iseries":
        defaultType = "iseries"
    else:
        defaultType = None

    return defaultType


# make a silly .bak entry
def backupLabel(label, imageList):
    backup = "%s.bak" % (label,)
    while backup in imageList:
        backup = backup + "_"

    # truncate long names.
    if len(backup) > 32:
        backup = backup[:28]+".bak"

    if backup in imageList:
        raise RuntimeError, "Attempts to create unique backup label for %s failed" % (label,)
        
    return backup


def writeConfig(config, filename, backupSuffix, test = 0):
    # write out the LILO config
    try:
        backup = backupFile(filename, backupSuffix)
        liloperms = stat.S_IMODE(os.stat(filename)[stat.ST_MODE])
        if test:
            filename = "/tmp/lilo.conf"

        config.write(filename, perms = liloperms)
    except:
        restoreBackup(filename, backup)
        raise RuntimeError, "Error installing updated config file.  Aborting"

    return backup


def backupFile(filename, suffix):
    backup = "%s.%s-%s" % (filename, suffix, repr(time.time()))

    # make sure the backup file doesn't exist... add _'s until it doesn't
    while os.access(backup, os.F_OK):
        backup = backup + "_"

    shutil.copy(filename, backup)

    return backup


def restoreBackup(filename, backup):
    shutil.copy(backup, filename)
    os.remove(backup)
    

def liloInstall(instRoot, test = 0, filename = None, testFlag = 0):
    args = [ instRoot + "/sbin/lilo", "-r", instRoot ]

    if test:
        args.extend(["-t"])

    if testFlag:
        print args
        ret = 0
    else:
        ret = rhpl.executil.execWithRedirect(args[0], args,
                                     stdout = None, stderr = None)

    return ret

def yabootInstall(instRoot, filename = None):
    args = [ instRoot + "/usr/sbin/ybin", "-r", instRoot ]

    ret = rhpl.executil.execWithRedirect(args[0], args,
                                         stdout = None, stderr = None)

    return ret

def siloInstall(instRoot, filename = None):
    args = [instRoot + "/sbin/silo", "-r", instRoot]

    ret = rhpl.executil.execWithRedirect(args[0], args,
                                         stdout = None, stderr = None)

    return ret
