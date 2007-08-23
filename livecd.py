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
import time
import subprocess

import selinux

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
                    os.chown(dstname, os.stat(srcname)[stat.ST_UID], os.stat(srcname)[stat.ST_GID])
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

class LiveCDImageMethod(installmethod.InstallMethod):
    def __init__(self, method, rootpath, intf):
        """@param method livecd://live-block-device"""
        installmethod.InstallMethod.__init__(self, method, rootpath, intf)

        self.osimg = method[8:]
        if not stat.S_ISBLK(os.stat(self.osimg)[stat.ST_MODE]):
            intf.messageWindow(_("Unable to find image"),
                               _("The given location isn't a valid %s "
                                 "live CD to use as an installation source.")
                               %(productName,), type = "custom",
                               custom_icon="error",
                               custom_buttons=[_("Exit installer")])
            sys.exit(0)

    def postAction(self, anaconda):
        # unmount things that aren't listed in /etc/fstab.  *sigh*
        for dir in ("/selinux", "/dev"):
            try:
                isys.umount("%s/%s" %(anaconda.rootPath,dir), removeDir = 0)
            except Exception, e:
                log.error("unable to unmount %s: %s" %(dir, e))

        try:
            anaconda.id.fsset.umountFilesystems(anaconda.rootPath,
                                                swapoff = False)
            os.rmdir(anaconda.rootPath)
        except Exception, e:
            log.error("Unable to unmount filesystems.") 

    def protectedPartitions(self):
        if os.path.exists("/dev/live") and \
           stat.S_ISBLK(os.stat("/dev/live")[stat.ST_MODE]):
            target = os.readlink("/dev/live")
            return [target]
        return []

    def getFilename(self, filename, callback=None, destdir=None, retry=1):
        if filename.startswith("RELEASE-NOTES"):
            return "/usr/share/doc/HTML/" + filename

    def getLiveBlockDevice(self):
        return self.osimg

    def getLiveSizeMB(self):
        lnk = os.readlink(self.osimg)
        if lnk[0] != "/":
            lnk = os.path.join(os.path.dirname(self.osimg), lnk)
        blk = os.path.basename(lnk)

        if not os.path.exists("/sys/block/%s/size" %(blk,)):
            log.debug("Unable to determine the actual size of the live image")
            return 0

        size = open("/sys/block/%s/size" %(blk,), "r").read()
        try:
            size = int(size)
        except ValueError:
            log.debug("Unable to handle live size conversion: %s" %(size,))
            return 0

        return (size * 512) / 1024 / 1024
        

class LiveCDCopyBackend(backend.AnacondaBackend):
    def __init__(self, method, instPath):
        backend.AnacondaBackend.__init__(self, method, instPath)
        flags.livecdInstall = True
        self.supportsUpgrades = False
        self.supportsPackageSelection = False
        self.skipFormatRoot = True

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
        progress.set_label(_("Copying live image to hard drive."))
        progress.processEvents()

        osimg = anaconda.method.getLiveBlockDevice() # the real image
        osfd = os.open(osimg, os.O_RDONLY)

        r = anaconda.id.fsset.getEntryByMountPoint("/")
        rootfs = r.device.getDevice()
        rootfd = os.open("/dev/" + rootfs, os.O_WRONLY)

        readamt = 1024 * 1024 * 8 # 8 megs at a time
        size = float(anaconda.method.getLiveSizeMB() * 1024 * 1024)
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

        # remount filesystems
        anaconda.id.fsset.mountFilesystems(anaconda)

        # restore the label of / to what we think it is (XXX: UUID?)
        r = anaconda.id.fsset.getEntryByMountPoint("/")        
        r.fsystem.labelDevice(r, anaconda.rootPath)

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

        self._resizeRootfs(anaconda, wait)
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

    def kernelVersionList(self, rootPath = "/"):
        versions = []
        
        # FIXME: we should understand more types of kernel versions and not
        # be tied to rpm...  
        import rpm
        ts = rpm.TransactionSet(rootPath)

        # FIXME: and make sure that the rpmdb doesn't have stale locks :/
        for rpmfile in ["__db.000", "__db.001", "__db.002", "__db.003"]:
            try:
                os.unlink("%s/var/lib/rpm/%s" %(rootPath, rpmfile))
            except:
                log.debug("failed to unlink /var/lib/rpm/%s" %(rpmfile,))
                
        mi = ts.dbMatch('name', 'kernel')
        for h in mi:
            v = "%s-%s" %(h['version'], h['release'])
            versions.append( (v, h['arch'], "base") )

        return versions

    def doInitialSetup(self, anaconda):
        pass
    def doRepoSetup(self, anaconda):
        # ensure there's enough space on the rootfs
        # FIXME: really, this should be in the general sanity checking, but
        # trying to weave that in is a little tricky at present.
        ossize = anaconda.method.getLiveSizeMB()
        slash = anaconda.id.partitions.getRequestByMountPoint("/")
        if slash and \
           slash.getActualSize(anaconda.id.partitions, anaconda.id.diskset) < ossize:
            rc = anaconda.intf.messageWindow(_("Error"),
                                        _("The root filesystem you created is "
                                          "not large enough for this live "
                                          "image (%.2f MB required.") % ossize,
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
    def writePackagesKS(self, f):
        pass
