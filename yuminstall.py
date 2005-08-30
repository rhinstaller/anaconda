#
# Copyright (c) 2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from flags import flags

import sys
import os
import timer

import rpm
import rpmUtils
import urlgrabber.progress
import yum
import yum.repos
import yum.packages
from syslogd import syslog
from backend import AnacondaBackend
from constants import *
from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

import iutil
import isys

class simpleCallback:

    def __init__(self, messageWindow, progress, pkgTimer, method,
                 progressWindowClass, instLog, modeText, ts):
        self.messageWindow = messageWindow
        self.progress = progress
        self.pkgTimer = pkgTimer
        self.method = method
        self.progressWindowClass = progressWindowClass
        self.progressWindow = None
        self.lastprogress = 0
        self.incr = 20
        self.instLog = instLog
        self.modeText = modeText
        self.beenCalled = 0
        self.initWindow = None
        self.ts = ts
        self.fdnos = {}

    def callback(self, what, amount, total, h, user):
        # first time here means we should pop the window telling
        # user to wait until we get here
        if not self.beenCalled:
            self.beenCalled = 1
            self.initWindow.pop()

        if what == rpm.RPMCALLBACK_TRANS_START:
            # step 6 is the bulk of the ts processing time
            if amount == 6:
                self.progressWindow = \
                    self.progressWindowClass (_("Processing"), 
                                              _("Preparing to install..."),
                                              total)
                try:
                    self.incr = total / 10
                except:
                    pass

        if what == rpm.RPMCALLBACK_TRANS_PROGRESS:
            if self.progressWindow and amount > self.lastprogress + self.incr:
                self.progressWindow.set(amount)
                self.lastprogress = amount

        if what == rpm.RPMCALLBACK_TRANS_STOP and self.progressWindow:
            self.progressWindow.pop()

        if what == rpm.RPMCALLBACK_INST_OPEN_FILE:
            self.pkgTimer.start()

            hdr, path = h

            self.progress.setPackage(hdr)
            self.progress.setPackageScale(0, 1)

            self.instLog.write(self.modeText % (hdr[rpm.RPMTAG_NAME],
                                                hdr[rpm.RPMTAG_VERSION],
                                                hdr[rpm.RPMTAG_RELEASE],
                                                hdr[rpm.RPMTAG_ARCH]))

            self.instLog.flush()
            self.size = hdr[rpm.RPMTAG_SIZE]

            fn = os.path.basename(path)
            fd = os.open('/mnt/source/Fedora/RPMS/' + fn, os.O_RDONLY)
            nvr = '%s-%s-%s' % ( hdr['name'], hdr['version'], hdr['release'] )
            self.fdnos[nvr] = fd
            return fd

        elif what == rpm.RPMCALLBACK_INST_PROGRESS:
            if amount > total:
                amount = total
            if not total or total == 0 or total == "0":
                total = amount
            self.progress.setPackageScale(amount, total)

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            hdr, path =h
            nvr = '%s-%s-%s' % ( hdr['name'], hdr['version'], hdr['release'] )
            os.close(self.fdnos[nvr])
            self.progress.completePackage(hdr, self.pkgTimer)
            self.progress.processEvents()

        else:
            pass

        self.progress.processEvents()


class AnacondaYumConf:
    """Dynamic yum configuration"""

    def __init__( self, configfile = None, root = '/'):
        yumconfstr = """
[main]
cachedir=/var/cache/yum
reposdir=/tmp/repos.d
debuglevel=2
logfile=/tmp/yum.log
pkgpolicy=newest
distroverpkg=redhat-release
tolerant=1
exactarch=1
retries=5
obsoletes=1
gpgcheck=0
installroot=/mnt/sysimage

[anaconda]
baseurl=file:///mnt/source
enabled=1
gpgcheck=0
gpgkey=file:///mnt/source/RPM-GPG-KEY-fedora
"""

        if configfile is None:
            configfile = "/tmp/yum.conf"

        self.file = configfile
        f = open(configfile, 'w')
        f.write(yumconfstr)
        f.close()

    
class AnacondaYum(yum.YumBase):
    def __init__(self, method, id, intf, instPath):
        self.method = method
        self.id = id
        self.intf = intf
        self.updates = []
        self.localPackages = []
        yum.YumBase.__init__(self)


    def setGroupSelection(self, grpset, intf):
        if grpset is None:
            return 0

        pkgs = []

        availpackages = {}
        d = yum.packages.buildPkgRefDict(self.pkgSack.returnPackages())
        for po in self.pkgSack.returnPackages():
            availpackages[po.name] = po
        
        for group in grpset:
            if not self.groupInfo.groupExists(group):
                continue
            pkglist = self.groupInfo.pkgTree(group)
            for pkg in pkglist:
                if availpackages.has_key(pkg):
                    pkgs.append(pkg)
                    self.tsInfo.addInstall(availpackages[pkg])

    def errorlog(self, value, msg):
        pass

    def filelog(self, value, msg):
        pass

    def log(self, value, msg):
        pass

    def getDownloadPkgs(self):
        downloadpkgs = []
        totalSize = 0
        totalFiles = 0
        for txmbr in self.tsInfo.getMembers():
            if txmbr.ts_state in ['i', 'u']:
                po = txmbr.po
            if po:
                totalSize += int(po.returnSimple("installedsize")) / 1024
                for filetype in po.returnFileTypes():
                    totalFiles += len(po.returnFileEntries(ftype=filetype))
                downloadpkgs.append(po)

        return (downloadpkgs, totalSize, totalFiles)

    def run(self, cb):
        self.initActionTs()
        self.populateTs(keepold=0)
        self.ts.check()
        self.ts.order()
        self.runTransaction(cb=cb)
        
    def setup(self, fn="/etc/yum.conf", root="/"):
        self.doConfigSetup(fn, root)
        self.doTsSetup()
        self.doRpmDBSetup()
        # XXX: handle RepoError
        self.doRepoSetup()
        for x in self.repos.repos.values():
            x.dirSetup()
        self.repos
        self.doGroupSetup()
        self.doSackSetup()
        self.repos.populateSack(with='filelists')

class YumBackend(AnacondaBackend):

    def doPreSelection(self, intf, id, instPath):
        self.ac = AnacondaYumConf(configfile="/tmp/yum.conf", root=instPath)
        self.ayum = AnacondaYum(self.method, id, intf, instPath)
        self.ayum.setup(fn="/tmp/yum.conf", root=instPath)

        self.ayum.setGroupSelection(["Core"], intf)
        self.ayum.setGroupSelection(["Base"], intf)
        self.ayum.setGroupSelection(["Text-based Internet"], intf)


    def doPostSelection(self, intf, id, instPath):
        self.initLog(id, instPath)
        win = intf.waitWindow(_("Dependency Check"),
        _("Checking dependencies in packages selected for installation..."))
           
        (code, msgs) = self.ayum.buildTransaction()
        (self.dlpkgs, self.totalSize, self.totalFiles)  = self.ayum.getDownloadPkgs()
        win.pop()

    def doPreInstall(self, intf, id, instPath, dir):
        if dir == DISPATCH_BACK:
            for d in ("/selinux", "/dev"):
                try:
                    isys.umount(instPath + d, removeDir = 0)
                except Exception, e:
                    log.error("unable to unmount %s: %s" %(d, e))
            return

            if flags.test:
                return

        # shorthand
        upgrade = id.getUpgrade()

        if upgrade:
            # An old mtab can cause confusion (esp if loop devices are
            # in it)
            f = open(instPath + "/etc/mtab", "w+")
            f.close()

            # we really started writing modprobe.conf out before things were
            # all completely ready.  so now we need to nuke old modprobe.conf's
            # if you're upgrading from a 2.4 dist so that we can get the
            # transition right
            if (os.path.exists(instPath + "/etc/modules.conf") and
                os.path.exists(instPath + "/etc/modprobe.conf") and
                not os.path.exists(instPath + "/etc/modprobe.conf.anacbak")):
                log.info("renaming old modprobe.conf -> modprobe.conf.anacbak")
                os.rename(instPath + "/etc/modprobe.conf",
                          instPath + "/etc/modprobe.conf.anacbak")
                

        if self.method.systemMounted (id.fsset, instPath):
            id.fsset.umountFilesystems(instPath)
            return DISPATCH_BACK

        for i in ( '/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev', '/etc',
                   '/etc/sysconfig', '/etc/sysconfig/network-scripts',
                   '/etc/X11', '/root', '/var/tmp', '/etc/rpm' ):
            try:
                os.mkdir(instPath + i)
            except os.error, (errno, msg):
                pass
#            log.error("Error making directory %s: %s" % (i, msg))


        if flags.setupFilesystems:
            # setup /etc/rpm/platform for the post-install environment
            iutil.writeRpmPlatform(instPath)
            
            try:
                # FIXME: making the /var/lib/rpm symlink here is a hack to
                # workaround db->close() errors from rpm
                iutil.mkdirChain("/var/lib")
                for path in ("/var/tmp", "/var/lib/rpm"):
                    if os.path.exists(path) and not os.path.islink(path):
                        iutil.rmrf(path)
                    if not os.path.islink(path):
                        os.symlink("/mnt/sysimage/%s" %(path,), "%s" %(path,))
                    else:
                        log.warning("%s already exists as a symlink to %s" %(path, os.readlink(path),))
            except Exception, e:
                # how this could happen isn't entirely clear; log it in case
                # it does and causes problems later
                log.error("error creating symlink, continuing anyway: %s" %(e,))

            # SELinux hackery (#121369)
            if flags.selinux:
                try:
                    os.mkdir(instPath + "/selinux")
                except Exception, e:
                    pass
                try:
                    isys.mount("/selinux", instPath + "/selinux", "selinuxfs")
                except Exception, e:
                    log.error("error mounting selinuxfs: %s" %(e,))

            # we need to have a /dev during install and now that udev is
            # handling /dev, it gets to be more fun.  so just bind mount the
            # installer /dev
            if 1:
                log.warning("no dev package, going to bind mount /dev")
                isys.mount("/dev", "/mnt/sysimage/dev", bindMount = 1)

        # write out the fstab
        if not upgrade:
            id.fsset.write(instPath)
            # rootpath mode doesn't have this file around
            if os.access("/tmp/modprobe.conf", os.R_OK):
                iutil.copyFile("/tmp/modprobe.conf", 
                               instPath + "/etc/modprobe.conf")
            if os.access("/tmp/zfcp.conf", os.R_OK):
                iutil.copyFile("/tmp/zfcp.conf", 
                               instPath + "/etc/zfcp.conf")

        # make a /etc/mtab so mkinitrd can handle certain hw (usb) correctly
        f = open(instPath + "/etc/mtab", "w+")
        f.write(id.fsset.mtab())
        f.close()

    def doInstall(self, intf, id, instPath):
        if flags.test:
            return

        pkgTimer = timer.Timer(start = 0)

        id.instProgress.setSizes(len(self.dlpkgs), self.totalSize, self.totalFiles)
        id.instProgress.processEvents()

        cb = simpleCallback(intf.messageWindow, id.instProgress, pkgTimer, self.method, intf.progressWindow, self.instLog, self.modeText, self.ayum.ts)

        cb.initWindow = intf.waitWindow(_("Install Starting"),
                                        _("Starting install process.  This may take several minutes..."))

        self.ayum.run(cb)

        if not cb.beenCalled:
            cb.initWindow.pop()

        self.method.filesDone()
        instLog.close ()

        id.instProgress = None
