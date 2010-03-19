#
# image.py: Support methods for CD/DVD and ISO image installations.
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import isys, iutil
import os, os.path, stat, string, sys
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

_arch = iutil.getArch()

def findIsoImages(path, messageWindow):
    flush = os.stat(path)
    files = os.listdir(path)
    arch = _arch
    discImages = {}

    for file in files:
        what = path + '/' + file
        if not isys.isIsoImage(what):
            continue

        try:
            isys.losetup("/dev/loop2", what, readOnly = 1)
        except SystemError:
            continue

        try:
            isys.mount("/dev/loop2", "/mnt/cdimage", fstype = "iso9660",
                       readOnly = True)
            for num in range(1, 10):
                if os.access("/mnt/cdimage/.discinfo", os.R_OK):
                    f = open("/mnt/cdimage/.discinfo")
                    try:
                        f.readline() # skip timestamp
                        f.readline() # skip release description
                        discArch = string.strip(f.readline()) # read architecture
                        discNum = getDiscNums(f.readline().strip())
                    except:
                        discArch = None
                        discNum = [ 0 ]

                    f.close()

                    if num not in discNum or discArch != arch:
                        continue

                    # if it's disc1, it needs to have images/install.img
                    if (num == 1 and not
                        os.access("/mnt/cdimage/images/install.img", os.R_OK)):
                        log.warning("%s doesn't have a install.img, skipping" %(what,))
                        continue
                    # we only install binary packages, so let's look for a
                    # product/ dir and hope that this avoids getting
                    # discs from the src.rpm set
                    if not os.path.isdir("/mnt/cdimage/%s" %(productPath,)):
                        log.warning("%s doesn't have binary RPMS, skipping" %(what,))
                        continue

                    # warn user if images appears to be wrong size
                    if os.stat(what)[stat.ST_SIZE] % 2048:
                        rc = messageWindow(_("Warning"),
                             _("The ISO image %s has a size which is not "
                               "a multiple of 2048 bytes.  This may mean "
                               "it was corrupted on transfer to this computer."
                               "\n\n"
                               "It is recommended that you exit and abort your "
                               "installation, but you can choose to continue if "
                               "you think this is in error.") % (file,),
                               type="custom", custom_icon="warning",
                               custom_buttons= [_("_Exit installer"),
                                                _("_Continue")])
                        if rc == 0:
                            sys.exit(0)

                    discImages[num] = file

            isys.umount("/mnt/cdimage", removeDir=False)
        except SystemError:
            pass

        isys.unlosetup("/dev/loop2")

    return discImages

def getDiscNums(line):
    # get the disc numbers for this disc
    nums = line.split(",")
    if nums == ['ALL']: # Treat "ALL" DVD as disc 1
        return [1]
    discNums = []
    for num in nums:
        discNums.append(int(num))
    return discNums

def getMediaId(path):
    if os.access("%s/.discinfo" % path, os.R_OK):
        f = open("%s/.discinfo" % path)
        newStamp = f.readline().strip()
        f.close()

        return newStamp
    else:
        return None

# This mounts the directory containing the iso images, and places the
# mount point in /mnt/isodir.
def mountDirectory(methodstr, messageWindow):
    if methodstr.startswith("hd:"):
        method = methodstr[3:]
        if method.count(":") == 1:
            (device, path) = method.split(":")
            fstype = "auto"
        else:
            (device, fstype, path) = method.split(":")

        if not device.startswith("/dev/") and not device.startswith("UUID=") \
           and not device.startswith("LABEL="):
            device = "/dev/%s" % device
    elif methodstr.startswith("nfsiso:"):
        device = methodstr[7:]
        fstype = "nfs"
    else:
        return

    # No need to mount it again.
    if os.path.ismount("/mnt/isodir"):
        return

    while True:
        try:
            isys.mount(device, "/mnt/isodir", fstype = fstype)
            break
        except SystemError, msg:
            log.error("couldn't mount ISO source directory: %s" % msg)
            ans = messageWindow(_("Couldn't Mount ISO Source"),
                          _("An error occurred mounting the source "
                            "device %s.  This may happen if your ISO "
                            "images are located on an advanced storage "
                            "device like LVM or RAID, or if there was a "
                            "problem mounting a partition.  Click exit "
                            "to abort the installation.")
                          % (device,), type="custom", custom_icon="error",
                          custom_buttons=[_("_Exit"), _("_Retry")])

            if ans == 0:
                sys.exit(0)
            else:
                continue

def mountImage(isodir, tree, discnum, messageWindow, discImages={}):
    if os.path.ismount(tree):
        raise SystemError, "trying to mount already-mounted iso image!"

    if discImages == {}:
        discImages = findIsoImages(isodir, messageWindow)

    while True:
        try:
            isoImage = "%s/%s" % (isodir, discImages[discnum])
            isys.losetup("/dev/loop1", isoImage, readOnly = 1)
            isys.mount("/dev/loop1", tree, fstype = 'iso9660', readOnly = True)
            break
        except:
            ans = messageWindow(_("Missing ISO 9660 Image"),
                                _("The installer has tried to mount "
                                  "image #%s, but cannot find it on "
                                  "the hard drive.\n\n"
                                  "Please copy this image to the "
                                  "drive and click Retry.  Click Exit "
                                  "to abort the installation.")
                                  % (discnum,), type="custom",
                                  custom_icon="warning",
                                  custom_buttons=[_("_Exit"), _("_Retry")])
            if ans == 0:
                sys.exit(0)
            elif ans == 1:
                discImages = findIsoImages(isodir, messageWindow)

    return discImages

# given groupset containing information about selected packages, use
# the disc number info in the headers to come up with message describing
# the required CDs
#
# dialog returns a value of 0 if user selected to abort install
def presentRequiredMediaMessage(anaconda):
    reqcds = anaconda.backend.getRequiredMedia()

    # if only one CD required no need to pop up a message
    if len(reqcds) < 2:
        return

    # check what discs our currently mounted one provides
    if os.access("%s/.discinfo" % anaconda.backend.ayum.tree, os.R_OK):
        discNums = []
        try:
            f = open("%s/.discinfo" % anaconda.backend.ayum.tree)
            stamp = f.readline().strip()
            descr = f.readline().strip()
            arch = f.readline().strip()
            discNums = getDiscNums(f.readline().strip())
            f.close()
        except Exception, e:
            log.critical("Exception reading discinfo: %s" %(e,))

        log.info("discNums is %s" %(discNums,))
        haveall = 0
        s = set(reqcds)
        t = set(discNums)
        if s.issubset(t):
            haveall = 1

        if haveall == 1:
            return

    reqcds.sort()
    reqcds = map(lambda disc: "#%s" % disc, filter(lambda disc: disc != -99, reqcds))
    reqcdstr = ", ".join(reqcds)

    return anaconda.intf.messageWindow(_("Required Install Media"),
               _("The software you have selected to install will require the "
                 "following %(productName)s %(productVersion)s "
                 "discs:\n\n%(reqcdstr)s\nPlease have these ready "
                 "before proceeding with the installation.  If you need to "
                 "abort the installation and exit please select "
                 "\"Reboot\".") % {'productName': product.productName,
                                   'productVersion': product.productVersion,
                                   'reqcdstr': reqcdstr},
                 type="custom", custom_icon="warning",
                 custom_buttons=[_("_Reboot"), _("_Back"), _("_Continue")])

# Find an attached CD/DVD drive with media in it that contains packages,
# and return that device name.
def scanForMedia(tree, storage):
    for dev in storage.devicetree.devices:
        if dev.type != "cdrom":
            continue

        storage.devicetree.updateDeviceFormat(dev)
        try:
            dev.format.mount(mountpoint=tree)
        except:
            continue

        if not verifyMedia(tree, 1):
            dev.format.unmount()
            continue

        return dev.name

    return None

def umountImage(tree, currentMedia):
    if currentMedia is not None:
        isys.umount(tree, removeDir=False)
        isys.unlosetup("/dev/loop1")

def unmountCD(dev, messageWindow):
    if not dev:
        return

    while True:
        try:
            dev.format.unmount()
            break
        except Exception, e:
            log.error("exception in _unmountCD: %s" %(e,))
            messageWindow(_("Error"),
                          _("An error occurred unmounting the disc.  "
                            "Please make sure you're not accessing "
                            "%s from the shell on tty2 "
                            "and then click OK to retry.")
                          % (dev.path,))

def verifyMedia(tree, discnum, timestamp=None):
    if os.access("%s/.discinfo" % tree, os.R_OK):
        f = open("%s/.discinfo" % tree)

        newStamp = f.readline().strip()

        try:
            descr = f.readline().strip()
        except:
            descr = None

        try:
            arch = f.readline().strip()
        except:
            arch = None

        try:
            discs = getDiscNums(f.readline().strip())
        except:
            discs = [ 0 ]

        f.close()

        if timestamp is not None:
            if newStamp == timestamp and arch == _arch and discnum in discs:
                return True
        else:
            if arch == _arch and discnum in discs:
                return True

    return False
