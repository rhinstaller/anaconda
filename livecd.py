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

import selinux

from rhpl.translate import _, N_

from flags import flags
from constants import *

import backend
import isys
import iutil
import fsset

import packages

import logging
log = logging.getLogger("anaconda")

class Error(EnvironmentError):
    pass
def copytree(src, dst, symlinks=False, preserveOwner=False,
             preserveSelinux=False):
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
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, preserveOwner, preserveSelinux)
            else:
                shutil.copyfile(srcname, dstname)
                if preserveOwner:
                    try:
                        os.chown(dstname, os.stat(srcname)[stat.ST_UID], os.stat(srcname)[stat.ST_GID])
                    except OverflowError:
                        log.error("Could not set owner and group on file %s" % dstname)

                if preserveSelinux:
                    selinux.lsetfilecon(dstname, selinux.lgetfilecon(srcname)[1])
                shutil.copystat(srcname, dstname)
        except (IOError, os.error), why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error, err:
            errors.extend(err.args[0])
    try:
        if preserveOwner:
            os.chown(dst, os.stat(src)[stat.ST_UID], os.stat(src)[stat.ST_GID])            
        if preserveSelinux:
            selinux.lsetfilecon(dst, selinux.lgetfilecon(src)[1])
        shutil.copystat(src, dst)
    except OSError, why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise Error, errors

class LiveCDCopyBackend(backend.AnacondaBackend):
    def __init__(self, anaconda):
        backend.AnacondaBackend.__init__(self, anaconda)
        flags.livecdInstall = True
        self.supportsUpgrades = False
        self.supportsPackageSelection = False
        self.skipFormatRoot = True

        self.osimg = anaconda.methodstr[8:]
        if not stat.S_ISBLK(os.stat(self.osimg)[stat.ST_MODE]):
            anaconda.intf.messageWindow(_("Unable to find image"),
                               _("The given location isn't a valid %s "
                                 "live CD to use as an installation source.")
                               %(productName,), type = "custom",
                               custom_icon="error",
                               custom_buttons=[_("Exit installer")])
            sys.exit(0)

    def _getLiveBlockDevice(self):
        return os.path.normpath(self.osimg)

    def _getLiveSizeMB(self):
        def parseField(output, field):
            for line in output.split("\n"):
                if line.startswith(field + ":"):
                    return line[len(field) + 1:].strip()
            raise KeyError("Failed to find field '%s' in output" % field)

        output = subprocess.Popen(['/sbin/dumpe2fs', '-h', self.osimg],
                                  stdout=subprocess.PIPE,
                                  stderr=open('/dev/null', 'w')
                                  ).communicate()[0]
        blkcnt = int(parseField(output, "Block count"))
        blksize = int(parseField(output, "Block size"))        
        return blkcnt * blksize / 1024 / 1024

    def _unmountNonFstabDirs(self, anaconda):
        # unmount things that aren't listed in /etc/fstab.  *sigh*
        dirs = ["/dev"]
        if flags.selinux:
            dirs.append("/selinux")
        for dir in dirs:
            try:
                isys.umount("%s/%s" %(anaconda.rootPath,dir), removeDir = 0)
            except Exception, e:
                log.error("unable to unmount %s: %s" %(dir, e))

    def postAction(self, anaconda):
        self._unmountNonFstabDirs(anaconda)
        try:
            anaconda.id.fsset.umountFilesystems(anaconda.rootPath,
                                                swapoff = False)
            os.rmdir(anaconda.rootPath)
        except Exception, e:
            log.error("Unable to unmount filesystems.") 

    def doPreInstall(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            self._unmountNonFstabDirs(anaconda)
            return

        anaconda.id.fsset.umountFilesystems(anaconda.rootPath, swapoff = False)

    def doInstall(self, anaconda):
        log.info("Preparing to install packages")
        if flags.test:
            log.info("Test mode - not performing install")
            return

        progress = anaconda.id.instProgress
        progress.set_label(_("Copying live image to hard drive."))
        progress.processEvents()

        osimg = self._getLiveBlockDevice() # the real image
        osfd = os.open(osimg, os.O_RDONLY)

        r = anaconda.id.fsset.getEntryByMountPoint("/")
        rootfs = r.device.setupDevice()
        rootfd = os.open(rootfs, os.O_WRONLY)

        # set the rootfs to have the right type.  this lets things work
        # given ext2 or ext3 (and in the future, ext4)
        # FIXME: should we try to migrate if there isn't a match?
        roottype = isys.readFSType(osimg)
        if roottype is not None:
            r.fsystem = fsset.fileSystemTypeGet(roottype)

        readamt = 1024 * 1024 * 8 # 8 megs at a time
        size = float(self._getLiveSizeMB() * 1024 * 1024)
        copied = 0
        while copied < size:
            buf = os.read(osfd, readamt)
            written = os.write(rootfd, buf)
            if (written < readamt) and (written < len(buf)):
                raise RuntimeError, "error copying filesystem!"
            copied += written
            progress.set_fraction(pct = copied / size)
            progress.processEvents()

        os.close(osfd)
        os.close(rootfd)

        anaconda.id.instProgress = None

    def _doFilesystemMangling(self, anaconda):
        log.info("doing post-install fs mangling")
        wait = anaconda.intf.waitWindow(_("Doing post-installation"),
                                        _("Performing post-installation filesystem changes.  This may take several minutes..."))

        # resize rootfs first, since it is 100% full due to genMinInstDelta
        self._resizeRootfs(anaconda, wait)

        # remount filesystems
        anaconda.id.fsset.mountFilesystems(anaconda)

        # restore the label of / to what we think it is
        r = anaconda.id.fsset.getEntryByMountPoint("/")
        anaconda.id.fsset.labelEntry(r, anaconda.rootPath, True)
        # ensure we have a random UUID on the rootfs
        # FIXME: this should be abstracted per filesystem type
        iutil.execWithRedirect("tune2fs", ["-U", "random", "/dev/%s" % (r.device.getDevice())],
                               stdout="/dev/tty5", stderr="/dev/tty5",
                               searchPath = 1)

        # for any filesystem that's _not_ on the root, we need to handle
        # moving the bits from the livecd -> the real filesystems.
        # this is pretty distasteful, but should work with things like
        # having a separate /usr/local

        # get a list of fsset entries that are relevant
        entries = sorted(filter(lambda e: not e.fsystem.isKernelFS() and \
                                e.getMountPoint(), anaconda.id.fsset.entries))
        # now create a tree so that we know what's mounted under where
        fsdict = {"/": []}
        for entry in entries:
            tocopy = entry.getMountPoint()
            if tocopy.startswith("/mnt") or tocopy == "swap":
                continue
            keys = sorted(fsdict.keys(), reverse = True)
            for key in keys:
                if tocopy.startswith(key):
                    fsdict[key].append(entry)
                    break
            fsdict[tocopy] = []

        # and now let's do the real copies; and we don't want to copy /!
        copied = ["/"]
        for tocopy in sorted(fsdict.keys()):
            if tocopy in copied:
                continue
            copied.append(tocopy)
            copied.extend(map(lambda x: x.getMountPoint(), fsdict[tocopy]))
            entry = anaconda.id.fsset.getEntryByMountPoint(tocopy)

            # FIXME: all calls to wait.refresh() are kind of a hack... we
            # should do better about not doing blocking things in the
            # main thread.  but threading anaconda is a job for another
            # time.
            wait.refresh()

            # unmount subdirs + this one and then remount under /mnt
            for e in fsdict[tocopy] + [entry]:
                e.umount(anaconda.rootPath)
            for e in [entry] + fsdict[tocopy]:
                e.mount(anaconda.rootPath + "/mnt")                

            copytree("%s/%s" %(anaconda.rootPath, tocopy),
                     "%s/mnt/%s" %(anaconda.rootPath, tocopy), True, True,
                     flags.selinux)
            shutil.rmtree("%s/%s" %(anaconda.rootPath, tocopy))
            wait.refresh()

            # mount it back in the correct place
            for e in fsdict[tocopy] + [entry]:
                e.umount(anaconda.rootPath + "/mnt")
                try:
                    os.rmdir("%s/mnt/%s" %(anaconda.rootPath,
                                           e.getMountPoint()))
                except OSError, e:
                    log.debug("error removing %s" %(tocopy,))
            for e in [entry] + fsdict[tocopy]:                
                e.mount(anaconda.rootPath)                

            wait.refresh()

        # ensure that non-fstab filesystems are mounted in the chroot
        if flags.selinux:
            try:
                isys.mount("/selinux", anaconda.rootPath + "/selinux", "selinuxfs")
            except Exception, e:
                log.error("error mounting selinuxfs: %s" %(e,))
        isys.mount("/dev", "%s/dev" %(anaconda.rootPath,), bindMount = 1)

        wait.pop()

    def _resizeRootfs(self, anaconda, win = None):
        log.info("going to do resize")
        r = anaconda.id.fsset.getEntryByMountPoint("/")        
        rootdev = r.device.getDevice()

        # FIXME: we'd like to have progress here to give an idea of
        # how long it will take.  or at least, to give an indefinite
        # progress window.  but, not for this time
        cmd = ["resize2fs", "/dev/%s" %(rootdev,), "-p"]
        out = open("/dev/tty5", "w")
        proc = subprocess.Popen(cmd, stdout=out, stderr=out)
        rc = proc.poll()
        while rc is None:
            win and win.refresh()
            time.sleep(0.5)
            rc = proc.poll()

        if rc:
            log.error("error running resize2fs; leaving filesystem as is")

    def doPostInstall(self, anaconda):
        self._doFilesystemMangling(anaconda)

        # setup /etc/rpm/platform for the post-install environment
        iutil.writeRpmPlatform(anaconda.rootPath)

        # maybe heavy handed, but it'll do
        anaconda.id.bootloader.args.append("rhgb quiet")
        anaconda.id.desktop.setDefaultRunLevel(5)

        # now write out the "real" fstab and mtab
        anaconda.id.fsset.write(anaconda.rootPath)
        f = open(anaconda.rootPath + "/etc/mtab", "w+")
        f.write(anaconda.id.fsset.mtab())
        f.close()        
        
        # copy over the modprobe.conf
        if os.path.exists("/etc/modprobe.conf"):
            shutil.copyfile("/etc/modprobe.conf", 
                            anaconda.rootPath + "/etc/modprobe.conf")

        # rebuild the initrd(s)
        vers = self.kernelVersionList(anaconda.rootPath)
        for (n, arch, tag) in vers:
            packages.recreateInitrd(n, anaconda.rootPath)

    def writeConfiguration(self):
        pass

    def kernelVersionList(self, rootPath = "/"):
        return packages.rpmKernelVersionList(rootPath)

    def doInitialSetup(self, anaconda):
        pass
    def doRepoSetup(self, anaconda):
        # ensure there's enough space on the rootfs
        # FIXME: really, this should be in the general sanity checking, but
        # trying to weave that in is a little tricky at present.
        ossize = self._getLiveSizeMB()
        slash = anaconda.id.partitions.getRequestByMountPoint("/")
        if slash and \
           slash.getActualSize(anaconda.id.partitions, anaconda.id.diskset) < ossize:
            rc = anaconda.intf.messageWindow(_("Error"),
                                        _("The root filesystem you created is "
                                          "not large enough for this live "
                                          "image (%.2f MB required).") % ossize,
                                        type = "custom",
                                        custom_icon = "error",
                                        custom_buttons=[_("_Back"),
                                                        _("_Exit installer")])
            if rc == 0:
                return DISPATCH_BACK
            else:
                sys.exit(1)
        

    # package/group selection doesn't apply for this backend
    def groupExists(self, group):
        pass
    def selectGroup(self, group, *args):
        pass
    def deselectGroup(self, group, *args):
        pass
    def selectPackage(self, pkg, *args):
        pass
    def deselectPackage(self, pkg, *args):
        pass
    def packageExists(self, pkg):
        return True
    def getDefaultGroups(self, anaconda):
        return []
    def writePackagesKS(self, f, anaconda):
        pass
