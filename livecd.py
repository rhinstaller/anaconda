#
# An anaconda backend to do an install from a live CD image
#
# The basic idea is that with a live CD, we already have an install
# and should be able to just copy those bits over to the disk.  So we dd
# the image, move things to the "right" filesystem as needed, and then
# resize the rootfs to the size of its container.
#
# Copyright 2007  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, sys
import stat
import shutil

from rhpl.translate import _, N_

from flags import flags
from constants import *

import backend
import installmethod
import isys
import iutil

import packages

import logging
log = logging.getLogger("anaconda")

def copytree(src, dst, symlinks=False):
    # copy of shutil.copytree which doesn't require dst to not exist
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
                copytree(srcname, dstname, symlinks)
            else:
                shutil.copy2(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except (IOError, os.error), why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error, err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except OSError, why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise Error, errors

class LiveCDImageMethod(installmethod.InstallMethod):
    def __init__(self, method, rootpath, intf):
        """@param method livecd://mountedlocation """
        installmethod.InstallMethod.__init__(self, method, rootpath, intf)

        self.cdmntpt = method[8:]
        if not os.path.exists("%s/squashfs.img" %(self.cdmntpt,)):
            intf.messageWindow(_("Unable to find image"),
                               _("The given location isn't a valid %s "
                                 "live CD to use as an installation source.")
                               %(productName,), type = "custom",
                               custom_icon="error",
                               custom_buttons=[_("Exit installer")])
            sys.exit(0)

    def getLiveCDMountPoint(self):
        return self.cdmntpt
        

class LiveCDCopyBackend(backend.AnacondaBackend):
    def __init__(self, method, instPath):
        backend.AnacondaBackend.__init__(self, method, instPath)
        self.supportsUpgrades = False
        self.supportsPackageSelection = False

    def doPreInstall(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            for d in ("/selinux", "/dev"):
                try:
                    isys.umount(anaconda.rootPath + d, removeDir = 0)
                except Exception, e:
                    log.error("unable to unmount %s: %s" %(d, e))
            return

        anaconda.id.fsset.umountFilesystems(anaconda.rootPath, swapoff = False)

    def doInstall(self, anaconda):
        log.info("Preparing to install packages")
        if flags.test:
            log.info("Test mode - not performing install")
            return

        progress = anaconda.id.instProgress
        progress.processEvents()

        osimg = "/mnt/installer/squashed/os.img" # the real image
        osfd = os.open(osimg, os.O_RDONLY)

        r = anaconda.id.fsset.getEntryByMountPoint("/")
        rootfs = r.device.getDevice()
        rootfd = os.open("/dev/" + rootfs, os.O_WRONLY)

        readamt = 1024 * 1024 * 8 # 8 megs at a time
        size = float(os.stat(osimg)[stat.ST_SIZE])
        copied = 0
        while copied < size:
            buf = os.read(osfd, readamt)
            written = os.write(rootfd, buf)
            if (written < readamt) and (written < len(buf)):
                raise RuntimeError, "error copying filesystem!"
            copied += written
            progress.completePackage(pct = copied / size)
            progress.processEvents()

        os.close(osfd)
        os.close(rootfd)

        # unset-up the image
        isys.umount("/mnt/installer/squashed")
        isys.unlosetup("/dev/loop4")
        anaconda.id.instProgress = None

    def _doFilesystemMangling(self, anaconda):
        log.info("doing post-install fs mangling")
        wait = anaconda.intf.waitWindow(_("Doing post-installation"),
                                        _("Performing post-installation filesystem changes.  This may take several minutes..."))

        # remount filesystems
        anaconda.id.fsset.mountFilesystems(anaconda)

        # restore the label of / to what we think it is (XXX: UUID?)
        r = anaconda.id.fsset.getEntryByMountPoint("/")        
        r.fsystem.labelDevice(r, anaconda.rootPath)

        # for any filesystem that's _not_ on the root, we need to handle
        # moving the bits from the livecd -> the real filesystems.
        # this could be more clever by starting at the deepest part of
        # the fsys tree, but this will do for now
        for entry in anaconda.id.fsset.entries:
            if entry.fsystem.isKernelFS():
                continue

            tocopy = entry.getMountPoint()

            if tocopy is None or tocopy == "/" or tocopy.startswith("/mnt") or tocopy == "swap":
                continue

            log.info("doing the copy for %s" %(tocopy,))
            entry.umount(anaconda.rootPath)
            entry.mount(anaconda.rootPath + "/mnt")
            # XXX: should use something with selinux knowledge...
            copytree("%s/%s" %(anaconda.rootPath, tocopy),
                     "%s/mnt/%s" %(anaconda.rootPath, tocopy))
            shutil.rmtree("%s/%s" %(anaconda.rootPath, tocopy))
            entry.umount(anaconda.rootPath + "/mnt")
            entry.mount(anaconda.rootPath)
            try:
                os.rmdir("%s/mnt/%s" %(anaconda.rootPath, tocopy))
            except OSError, e:
                log.debug("error removing %s" %(tocopy,))
                pass

            # XXX: we should be preserving contexts on our copy, but
            # this will do for now
            for dir, subdirs, files in os.walk("%s/%s" %(anaconda.rootPath, tocopy)):
                dir = dir[anaconda.rootPath:]
                for f in map(lambda x: "%s/%s" %(dir, x), files):
                    if not os.access(f, os.R_OK):
                        continue
                    ret = isys.resetFileContext(os.path.normpath(f),
                                                anaconda.rootPath)
                    log.info("set fc of %s to %s" %(f, ret)

        # ensure that non-fstab filesystems are mounted in the chroot
        if flags.selinux:
            try:
                isys.mount("/selinux", anaconda.rootPath + "/selinux", "selinuxfs")
            except Exception, e:
                log.error("error mounting selinuxfs: %s" %(e,))
        isys.mount("/dev", "%s/dev" %(anaconda.rootPath,), bindMount = 1)

        self._resizeRootfs(anaconda)

        wait.pop()

    def _resizeRootfs(self, anaconda):
        log.info("going to do resize")
        r = anaconda.id.fsset.getEntryByMountPoint("/")        
        rootdev = r.device.getDevice()        
        rc = iutil.execWithRedirect("resize2fs",
                                    [ "/dev/%s" %(rootdev,), "-p" ],
                                    stdout = "/dev/tty5", stderr = "/dev/tty5",
                                    searchPath = 1)
        if rc:
            log.error("error running resize2fs; leaving filesystem as is")

    def doPostInstall(self, anaconda):
        self._doFilesystemMangling(anaconda)

        # maybe heavy handed, but it'll do
        anaconda.id.bootloader.args.append("rhgb quiet")
        anaconda.id.desktop.setDefaultRunLevel(5)

        # now write out the "real" fstab and mtab
        anaconda.id.fsset.write(anaconda.rootPath)
        f = open(anaconda.rootPath + "/etc/mtab", "w+")
        f.write(anaconda.id.fsset.mtab())
        f.close()        

        # rebuild the initrd(s)
        vers = self.kernelVersionList()
        for (n, arch, tag) in vers:
            packages.recreateInitrd(n, anaconda.rootPath)

    def writeConfiguration(self):
        pass

    def kernelVersionList(self):
        versions = []
        
        # FIXME: we should understand more types of kernel versions and not
        # be tied to rpm...  
        import rpm
        ts = rpm.TransactionSet()
        mi = ts.dbMatch('name', 'kernel')
        for h in mi:
            v = "%s-%s" %(h['version'], h['release'])
            versions.append( (v, h['arch'], "base") )

        return versions

    def doInitialSetup(self, anaconda):
        pass
    def doRepoSetup(self, anaconda):
        # mount the squashfs.img to find the real os.img
        iutil.mkdirChain("/mnt/installer/squashed")
        isys.losetup("/dev/loop4", "%s/squashfs.img"
                     %(anaconda.method.getLiveCDMountPoint(),), readOnly = 1)
        isys.mount("/dev/loop4", "/mnt/installer/squashed",
                   fstype="squashfs", readOnly = 1)

        if not os.path.exists("/mnt/installer/squashed/os.img"):
            anaconda.intf.messageWindow(_("Unable to find image"),
                               _("The given location isn't a valid %s "
                                 "live CD to use as an installation source.")
                               %(productName,), type = "custom",
                               custom_icon="error",
                               custom_buttons=[_("Exit installer")])

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
    def writePackagesKS(self, f):
        pass
