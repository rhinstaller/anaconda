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
import os, os.path, stat, sys
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

_arch = iutil.getArch()

def findFirstIsoImage(path, messageWindow):
    """
    Find the first iso image in path
    This also supports specifying a specific .iso image

    Returns the full path to the image
    """
    flush = os.stat(path)
    arch = _arch

    if os.path.isfile(path) and path.endswith(".iso"):
        files = [os.path.basename(path)]
        path = os.path.dirname(path)
    else:
        files = os.listdir(path)

    for fn in files:
        what = path + '/' + fn
        log.debug("Checking %s" % (what))
        if not isys.isIsoImage(what):
            continue

        log.debug("mounting %s on /mnt/install/cdimage", what)
        try:
            isys.mount(what, "/mnt/install/cdimage", fstype="iso9660", readOnly=True)
        except SystemError:
            continue

        if not os.access("/mnt/install/cdimage/.discinfo", os.R_OK):
            isys.umount("/mnt/install/cdimage", removeDir=False)
            continue

        log.debug("Reading .discinfo")
        f = open("/mnt/install/cdimage/.discinfo")
        f.readline() # skip timestamp
        f.readline() # skip release description
        discArch = f.readline().strip() # read architecture
        f.close()

        log.debug("discArch = %s" % discArch)
        if discArch != arch:
            log.warning("findFirstIsoImage: architectures mismatch: %s, %s" %
                        (discArch, arch))
            isys.umount("/mnt/install/cdimage", removeDir=False)
            continue

        # If there's no repodata, there's no point in trying to
        # install from it.
        if not os.access("/mnt/install/cdimage/repodata", os.R_OK):
            log.warning("%s doesn't have repodata, skipping" %(what,))
            isys.umount("/mnt/install/cdimage", removeDir=False)
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
                   "you think this is in error.") % (fn,),
                   type="custom", custom_icon="warning",
                   custom_buttons= [_("_Exit installer"),
                                    _("_Continue")])
            if rc == 0:
                sys.exit(0)

        log.info("Found disc at %s" % fn)
        isys.umount("/mnt/install/cdimage", removeDir=False)
        return what

    return None

def getMediaId(path):
    if os.access("%s/.discinfo" % path, os.R_OK):
        f = open("%s/.discinfo" % path)
        newStamp = f.readline().strip()
        f.close()

        return newStamp
    else:
        return None

# This mounts the directory containing the iso images, and places the
# mount point in /mnt/install/isodir.
def mountDirectory(methodstr, messageWindow):
    # No need to mount it again.
    if os.path.ismount("/mnt/install/isodir"):
        return

    if methodstr.startswith("hd:"):
        method = methodstr[3:]
        options = ''
        if method.count(":") == 1:
            (device, path) = method.split(":")
            fstype = "auto"
        else:
            (device, fstype, path) = method.split(":")

        if not device.startswith("/dev/") and not device.startswith("UUID=") \
           and not device.startswith("LABEL="):
            device = "/dev/%s" % device
    elif methodstr.startswith("nfsiso:"):
        (options, host, path) = iutil.parseNfsUrl(methodstr)
        if path.endswith(".iso"):
            path = os.path.dirname(path)
        device = "%s:%s" % (host, path)
        fstype = "nfs"
    else:
        return

    while True:
        try:
            isys.mount(device, "/mnt/install/isodir", fstype=fstype, options=options)
            break
        except SystemError as msg:
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

def mountImage(isodir, tree, messageWindow):
    def complain():
        ans = messageWindow(_("Missing ISO 9660 Image"),
                            _("The installer has tried to mount the "
                              "installation image, but cannot find it on "
                              "the hard drive.\n\n"
                              "Please copy this image to the "
                              "drive and click Retry.  Click Exit "
                              "to abort the installation."),
                              type="custom",
                              custom_icon="warning",
                              custom_buttons=[_("_Exit"), _("_Retry")])
        if ans == 0:
            sys.exit(0)

    if os.path.ismount(tree):
        raise SystemError, "trying to mount already-mounted iso image!"
    while True:
        image = findFirstIsoImage(isodir, messageWindow)
        if image is None:
            complain()
            continue

        try:
            isys.mount(image, tree, fstype = 'iso9660', readOnly = True)
            break
        except SystemError:
            complain()

# Find an attached CD/DVD drive with media in it that contains packages,
# and return that device name.
def scanForMedia(tree, storage):
    for dev in storage.devicetree.devices:
        if dev.type != "cdrom":
            continue

        storage.devicetree.updateDeviceFormat(dev)
        try:
            dev.format.mount(mountpoint=tree)
        except Exception:
            continue

        if not verifyMedia(tree):
            dev.format.unmount()
            continue

        return dev.name

    return None

def umountImage(tree):
    if os.path.ismount(tree):
        isys.umount(tree, removeDir=False)

def unmountCD(dev, messageWindow):
    if not dev:
        return

    while True:
        try:
            dev.format.unmount()
            break
        except Exception as e:
            log.error("exception in _unmountCD: %s" %(e,))
            messageWindow(_("Error"),
                          _("An error occurred unmounting the disc.  "
                            "Please make sure you're not accessing "
                            "%s from the shell on tty2 "
                            "and then click OK to retry.")
                          % (dev.path,))

def verifyMedia(tree, timestamp=None):
    if os.access("%s/.discinfo" % tree, os.R_OK):
        f = open("%s/.discinfo" % tree)

        newStamp = f.readline().strip()
        descr = f.readline().strip()
        arch = f.readline().strip()
        f.close()

        if timestamp is not None:
            if newStamp == timestamp and arch == _arch:
                return True
        else:
            if arch == _arch:
                return True

    return False
