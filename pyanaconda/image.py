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

from errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

_arch = iutil.getArch()

def findFirstIsoImage(path):
    """
    Find the first iso image in path
    This also supports specifying a specific .iso image

    Returns the basename of the image
    """
    try:
        flush = os.stat(path)
    except OSError:
        return None

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
            log.warning("%s appears to be corrupted" % what)
            exn = InvalidImageSizeError("size is not a multiple of 2048 bytes")
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn

        log.info("Found disc at %s" % fn)
        isys.umount("/mnt/install/cdimage", removeDir=False)
        return fn

    return None

def getMediaId(path):
    if os.access("%s/.discinfo" % path, os.R_OK):
        f = open("%s/.discinfo" % path)
        newStamp = f.readline().strip()
        f.close()

        return newStamp
    else:
        return None

# This mounts the directory containing the iso images on ISO_DIR.
def mountImageDirectory(method, storage):
    # No need to mount it again.
    if os.path.ismount(ISO_DIR):
        return

    if method.method == "harddrive":
        if method.biospart:
            log.warning("biospart support is not implemented")
            devspec = method.biospart
        else:
            devspec = method.partition

        # FIXME: teach DeviceTree.resolveDevice about biospart
        device = storage.devicetree.resolveDevice(devspec)

        while True:
            try:
                device.setup()
                device.format.setup(mountpoint=ISO_DIR)
            except StorageError as e:
                log.error("couldn't mount ISO source directory: %s" % e)
                exn = MediaMountError(str(e))
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn
    elif methodstr.startswith("nfsiso:"):
        # XXX what if we mount it on ISO_DIR and then create a symlink
        #     if there are no isos instead of the remount?

        # mount the specified directory
        path = method.dir
        if method.dir.endswith(".iso"):
            path = os.path.dirname(method.dir)

        url = "%s:%s" % (method.server, path)

        while True:
            try:
                isys.mount(url, ISO_DIR, options=method.options)
            except SystemError as e:
                log.error("couldn't mount ISO source directory: %s" % e)
                exn = MediaMountError(str(e))
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn

def mountImage(isodir, tree):
    while True:
        if os.path.isfile(isodir):
            image = isodir
        else:
            image = findFirstIsoImage(isodir)
            if image is None:
                exn = MissingImageError()
                if errorHandler.cb(exn) == ERROR_RAISE:
                    raise exn
                else:
                    continue

            image = os.path.normpath("%s/%s" % (isodir, image))

        try:
            isys.mount(image, tree, fstype = 'iso9660', readOnly = True)
        except SystemError:
            exn = MissingImageError()
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn
            else:
                continue
        else:
            break

# Return the first Device instance containing valid optical install media
# for this product.
def opticalInstallMedia(devicetree, mountpoint=INSTALL_TREE):
    retval = None

    for dev in devicetree.getDevicesByType("cdrom"):
        devicetree.updateDeviceFormat(dev)
        try:
            dev.format.mount(mountpoint=mountpoint)
        except Exception:
            continue

        if not verifyMedia(mountpoint):
            dev.format.unmount()
            continue

        dev.format.unmount()
        retval = dev
        break

    return retval

# Return a list of Device instances that may have HDISO install media
# somewhere.  Candidate devices are simply any that we can mount.
def potentialHdisoSources(devicetree):
    return filter(lambda d: d.format.exists and d.format.mountable, devicetree.getDevicesByType("partition"))

def umountImage(tree):
    if os.path.ismount(tree):
        isys.umount(tree, removeDir=False)

def unmountCD(dev):
    if not dev:
        return

    while True:
        try:
            dev.format.unmount()
        except Exception as e:
            log.error("exception in _unmountCD: %s" %(e,))
            exn = MediaUnmountError()
            errorHandler.cb(exn, dev)
        else:
            break

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
