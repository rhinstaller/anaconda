#
# livecd.py: An anaconda backend to do an install from a live CD image
#
# The basic idea is that with a live CD, we already have an install
# and should be able to just copy those bits over to the disk.  So we dd
# the image, move things to the "right" filesystem as needed, and then
# resize the rootfs to the size of its container.
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import os, sys
import stat
import shutil
import time
import subprocess
import storage

import selinux

from flags import flags
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import backend
import isys
import iutil

import packages

import logging
log = logging.getLogger("anaconda")

class Error(EnvironmentError):
    pass
def copytree(src, dst, symlinks=False, preserveOwner=False,
             preserveSelinux=False):
    def tryChown(src, dest):
        try:
            os.chown(dest, os.stat(src)[stat.ST_UID], os.stat(src)[stat.ST_GID])
        except OverflowError:
            log.error("Could not set owner and group on file %s" % dest)

    def trySetfilecon(src, dest):
        try:
            selinux.lsetfilecon(dest, selinux.lgetfilecon(src)[1])
        except OSError:
            log.error("Could not set selinux context on file %s" % dest)

    # copy of shutil.copytree which doesn't require dst to not exist
    # and which also has options to preserve the owner and selinux contexts
    names = os.listdir(src)
    if not os.path.isdir(dst):
        os.makedirs(dst)
    errors = []
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
                if preserveSelinux:
                    trySetfilecon(srcname, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, preserveOwner, preserveSelinux)
            else:
                shutil.copyfile(srcname, dstname)
                if preserveOwner:
                    tryChown(srcname, dstname)

                if preserveSelinux:
                    trySetfilecon(srcname, dstname)

                shutil.copystat(srcname, dstname)
        except (IOError, OSError) as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error as err:
            errors.extend(err.args[0])
    try:
        if preserveOwner:
            tryChown(src, dst)
        if preserveSelinux:
            trySetfilecon(src, dst)

        shutil.copystat(src, dst)
    except OSError as e:
        errors.extend((src, dst, e.strerror))
    if errors:
        raise Error, errors

class LiveCDCopyBackend(backend.AnacondaBackend):
    def __init__(self, anaconda):
        backend.AnacondaBackend.__init__(self, anaconda)
        flags.livecdInstall = True
        self.supportsUpgrades = False
        self.supportsPackageSelection = False
        self.skipFormatRoot = True

        osimg_path = anaconda.methodstr[9:]
        if not stat.S_ISBLK(os.stat(osimg_path)[stat.ST_MODE]):
            anaconda.intf.messageWindow(_("Unable to find image"),
                               _("The given location isn't a valid %s "
                                 "live CD to use as an installation source.")
                               %(productName,), type = "custom",
                               custom_icon="error",
                               custom_buttons=[_("Exit installer")])
            sys.exit(0)

    def postAction(self, anaconda):
        try:
            anaconda.storage.umountFilesystems(swapoff = False)
            os.rmdir(anaconda.rootPath)
        except Exception as e:
            log.error("Unable to unmount filesystems: %s" % e) 

    def doPreInstall(self, anaconda):
        anaconda.storage.umountFilesystems(swapoff = False)

    def doInstall(self, anaconda):
        log.info("Preparing to install packages")

        progress = anaconda.intf.instProgress
        progress.set_label(_("Copying live image to hard drive."))
        progress.processEvents()

        osfd = os.open(self.anaconda.storage.liveImage.path, os.O_RDONLY)

        rootDevice = anaconda.storage.rootDevice
        rootDevice.setup()
        rootfd = os.open(rootDevice.path, os.O_WRONLY)

        readamt = 1024 * 1024 * 8 # 8 megs at a time
        size = self.anaconda.storage.liveImage.format.currentSize * 1024 * 1024
        copied = 0
        done = False
        while not done:
            try:
                buf = os.read(osfd, readamt)
                written = os.write(rootfd, buf)
            except (IOError, OSError):
                rc = anaconda.intf.messageWindow(_("Error"),
                        _("There was an error installing the live image to "
                          "your hard drive.  This could be due to bad media.  "
                          "Please verify your installation media.\n\nIf you "
                          "exit, your system will be left in an inconsistent "
                          "state that will require reinstallation."),
                        type="custom", custom_icon="error",
                        custom_buttons=[_("_Exit installer"), _("_Retry")])

                if rc == 0:
                    sys.exit(0)
                else:
                    os.lseek(osfd, 0, 0)
                    os.lseek(rootfd, 0, 0)
                    copied = 0
                    continue

            if (written < readamt):
                # Either something went wrong with the write
                if (written < len(buf)):
                    raise RuntimeError, "error copying filesystem!"
                else:
                    # Or we're done
                    done = True
            copied += written
            progress.set_fraction(pct = copied / float(size))
            progress.processEvents()

        os.close(osfd)
        os.close(rootfd)

        anaconda.intf.setInstallProgressClass(None)

    def _doFilesystemMangling(self, anaconda):
        log.info("doing post-install fs mangling")
        wait = anaconda.intf.waitWindow(_("Post-Installation"),
                                        _("Performing post-installation filesystem changes.  This may take several minutes."))

        # resize rootfs first, since it is 100% full due to genMinInstDelta
        rootDevice = anaconda.storage.rootDevice
        rootDevice.setup()
        rootDevice.format.targetSize = rootDevice.size
        rootDevice.format.doResize(intf=anaconda.intf)

        # ensure we have a random UUID on the rootfs
        rootDevice.format.writeRandomUUID()

        # remount filesystems
        anaconda.storage.mountFilesystems()

        # and now set the uuid in the storage layer
        rootDevice.updateSysfsPath()
        iutil.notify_kernel("/sys%s" %rootDevice.sysfsPath)
        storage.udev.udev_settle()
        rootDevice.updateSysfsPath()
        info = storage.udev.udev_get_block_device(rootDevice.sysfsPath)
        rootDevice.format.uuid = storage.udev.udev_device_get_uuid(info)
        log.info("reset the rootdev (%s) to have a uuid of %s" %(rootDevice.sysfsPath, rootDevice.format.uuid))

        # for any filesystem that's _not_ on the root, we need to handle
        # moving the bits from the livecd -> the real filesystems.
        # this is pretty distasteful, but should work with things like
        # having a separate /usr/local

        def _setupFilesystems(mounts, chroot="", teardown=False):
            """ Setup or teardown all filesystems except for "/" """
            mountpoints = sorted(mounts.keys(),
                                 reverse=teardown is True)
            if teardown:
                method = "teardown"
                kwargs = {}
            else:
                method = "setup"
                kwargs = {"chroot": chroot}

            mountpoints.remove("/")
            for mountpoint in mountpoints:
                device = mounts[mountpoint]
                getattr(device.format, method)(**kwargs)

        # Start by sorting the mountpoints in decreasing-depth order.
        # Only include ones that exist on the original livecd filesystem
        mountpoints = filter(os.path.exists,
                             sorted(anaconda.storage.mountpoints.keys(),
                             reverse=True))
        # We don't want to copy the root filesystem.
        mountpoints.remove("/")
        stats = {} # mountpoint: posix.stat_result

        # unmount the filesystems, except for /
        _setupFilesystems(anaconda.storage.mountpoints, teardown=True)

        # mount all of the filesystems under /mnt so we can copy in content
        _setupFilesystems(anaconda.storage.mountpoints,
                          chroot="/mnt")

        # And now let's do the real copies
        for tocopy in mountpoints:
            device = anaconda.storage.mountpoints[tocopy]
            source = "%s/%s" % (anaconda.rootPath, tocopy)
            dest   = "/mnt/%s" % (tocopy,)

            # FIXME: all calls to wait.refresh() are kind of a hack... we
            # should do better about not doing blocking things in the
            # main thread.  but threading anaconda is a job for another
            # time.
            wait.refresh()

            try:
                log.info("Gathering stats on %s" % (source,))
                stats[tocopy]= os.stat(source)
            except Exception as e:
                log.info("failed to get stat info for mountpoint %s: %s"
                            % (source, e))

            log.info("Copying %s to %s" % (source, dest))
            copytree(source, dest, True, True, flags.selinux)
            wait.refresh()

            log.info("Removing %s" % (source,))
            shutil.rmtree(source)
            wait.refresh()

        # unmount the target filesystems and remount in their final locations
        # so that post-install writes end up where they're supposed to end up
        _setupFilesystems(anaconda.storage.mountpoints, teardown=True)
        _setupFilesystems(anaconda.storage.mountpoints,
                          chroot=anaconda.rootPath)

        # restore stat info for each mountpoint
        for mountpoint in reversed(mountpoints):
            dest = "%s/%s" % (anaconda.rootPath, mountpoint)
            log.info("Restoring stats on %s" % (dest,))
            st = stats[mountpoint]

            # restore the correct stat info for this mountpoint
            os.utime(dest, (st.st_atime, st.st_mtime))
            os.chown(dest, st.st_uid, st.st_gid)
            os.chmod(dest, stat.S_IMODE(st.st_mode))

        wait.pop()

    def doPostInstall(self, anaconda):
        import rpm

        self._doFilesystemMangling(anaconda)

        storage.writeEscrowPackets(anaconda)

        packages.rpmSetupGraphicalSystem(anaconda)

        # now write out the "real" fstab and mtab
        anaconda.storage.write(anaconda.rootPath)

        # copy over the modprobe.conf
        if os.path.exists("/etc/modprobe.conf"):
            shutil.copyfile("/etc/modprobe.conf", 
                            anaconda.rootPath + "/etc/modprobe.conf")
        # set the same keyboard the user selected in the keyboard dialog:
        anaconda.keyboard.write(anaconda.rootPath)

        # rebuild the initrd(s)
        vers = self.kernelVersionList(anaconda.rootPath)
        for (n, arch, tag) in vers:
            packages.recreateInitrd(n, anaconda.rootPath)

    def kernelVersionList(self, rootPath = "/"):
        return packages.rpmKernelVersionList(rootPath)

    def getMinimumSizeMB(self, part):
        if part == "/":
            return self.anaconda.storage.liveImage.format.size
        return 0


