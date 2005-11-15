#
# Copyright (c) 2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from flags import flags

import sys
import os
import shutil
import timer

import rpm
import rpmUtils
import urlgrabber.progress
import urlgrabber.grabber
import yum
import yum.repos
import yum.packages
import yum.groups
from yum.Errors import RepoError, YumBaseError
from yum.packages import returnBestPackages
from repomd.mdErrors import PackageSackError
from backend import AnacondaBackend
from constants import *
from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

import urlparse
urlparse.uses_fragment.append('media')


import iutil
import isys

from whiteout import whiteout

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

            fn = '%s/%s/RPMS/%s' % (self.method, productPath, os.path.basename(path))
            url = urlgrabber.grabber.urlopen(fn)
            f = open(path, 'w+')
            f.write(url.read()) 
            fd = os.open(path, os.O_RDONLY)
            nvra = '%s-%s-%s.%s' % ( hdr['name'], hdr['version'], hdr['release'], hdr['arch'] )
            self.fdnos[nvra] = fd
            return fd

        elif what == rpm.RPMCALLBACK_INST_PROGRESS:
            if amount > total:
                amount = total
            if not total or total == 0 or total == "0":
                total = amount
            self.progress.setPackageScale(amount, total)

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            hdr, path =h
            nvra = '%s-%s-%s.%s' % ( hdr['name'], hdr['version'], hdr['release'], hdr['arch'] )
            os.close(self.fdnos[nvra])
            os.unlink(path)
            self.progress.completePackage(hdr, self.pkgTimer)
            self.progress.processEvents()

        else:
            pass

        self.progress.processEvents()


class AnacondaYumConf:
    """Dynamic yum configuration"""

    def __init__( self, methodstr, configfile = "/tmp/yum.conf", root = '/'):
        self.methodstr = methodstr
        self.configfile = configfile
        self.root = root

        self.yumconfstr = """
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
installroot=%s
exclude=*debuginfo*

[anaconda]
baseurl=%s
enabled=1
gpgcheck=0
gpgkey=%s/RPM-GPG-KEY-fedora
""" % (self.root, self.methodstr, self.methodstr)

    def write(self):
        f = open(self.configfile, 'w')
        f.write(self.yumconfstr)
        f.close()
    
class AnacondaYum(yum.YumBase):
    def __init__(self, fn="/etc/yum.conf", root="/"):
        yum.YumBase.__init__(self)
        self.doConfigSetup(fn, root)
        self.macros = {}
        if flags.selinux:
            for dir in ("/tmp/updates", "/mnt/source/RHupdates",
                        "/etc/selinux/targeted/contexts/files",
                        "/etc/security/selinux/src/policy/file_contexts",
                        "/etc/security/selinux"):
                fn = "%s/file_contexts" %(dir,)
                if os.access(fn, os.R_OK):
                    break
            self.macros["__file_context_path"] = fn
        else:
            self.macros["__file_context_path"]  = "%{nil}"

        self.macros["_dependency_whiteout"] = whiteout

        self.updates = []
        self.localPackages = []

    def errorlog(self, value, msg):
        log.error(msg)

    def filelog(self, value, msg):
        pass

    def log(self, value, msg):
        if value >= 2:
            log.debug(msg)
        elif value == 1:
            log.info(msg)
        else:
            log.warning(msg)

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

    def setColor(self):
        if (rpmUtils.arch.canonArch.startswith("ppc64") or
        rpmUtils.arch.canonArch in ("s390x", "sparc64", "x86_64", "ia64")):
            self.ts.ts.setColor(3)

    def run(self, instLog, cb, intf):
        self.initActionTs()
        self.setColor()
        self.populateTs(keepold=0)
        self.ts.check()
        self.ts.order()

        # set log fd.  FIXME: this is ugly.  see changelog entry from 2005-09-13
        self.ts.ts.scriptFd = instLog.fileno()
        rpm.setLogFile(instLog)

        try:
            self.runTransaction(cb=cb)
        except YumBaseError, probs:
            # FIXME: we need to actually look at these problems...
            log.error("error running transaction: %s" %(probs,))
            intf.messageWindow(_("Error running transaction"),
                               ("There was an error running your transaction, "
                                "probably a disk space problem.  For now, "
                                "exiting on this although we should diagnose "
                                "and then let you go back."))
            sys.exit(1)

    def doCacheSetup(self):
        for repo in self.repos.repos.values():
            repo.set('cachedir', '/tmp/cache/')
            repo.set('pkgdir', '/mnt/sysimage/')
            repo.set('hdrdir', '/tmp/cache/headers')

    def doMacros(self):
        for (key, val) in self.macros.items():
            rpm.addMacro(key, val)

    def getBestPackages(self, pkgname, pkgarch = None):
        """Return a list of the packages which should be installed.
        Note that it's a list because of multilib!"""
        if pkgarch:
            pkgs = self.pkgSack.returnNewestByName(pkgname, pkgarch)
        else:
            pkgs = self.pkgSack.returnNewestByName(pkgname)
        if len(pkgs) <= 1: # 0 or 1, just return it
            return pkgs

        t = {}
        for pkg in pkgs:
            if not t.has_key(pkg.name): t[pkg.name] = []
            t[pkg.name].append(pkg.pkgtup)
        pkgs = returnBestPackages(t)
        return map(lambda x: self.getPackageObject(x), pkgs)

class AnacondaYumMedia(AnacondaYum):
    def __init__(self, fn="/etc/yum.conf", root="/"):
        AnacondaYum.__init__(self, fn=fn, root=root)

    def _getcd(self, po):
        try: 
            uri = po.returnSimple('basepath'):
            (scheme, netloc, path, query, fragid) = urlparse.urlsplit(url)
            if scheme != "media" or not fragid:
                return 0
            else:
                return fragid
        except KeyError:
            return 0

    def downloadHeader(self, po):
        h = YumHeader(po)
        hdrpath = po.localHdr()
        cd = self._getcd(po)
#XXX: Hack, make yum pass around po in callback so we don't have to do this
        if cd > 0:
            pkgpath = po.returnSimple('relativepath')
            pkgname = os.path.basename(pkgpath)
            h.addTag(1000000, RPM_STRING, pkgname)
            h.addTag(1000002, RPM_INT32, cd)
        f = open(hdrpath, 'w')
        f.write(h.str())
        f.close()
        del(h)

class YumBackend(AnacondaBackend):
    def __init__(self, method, instPath):
        AnacondaBackend.__init__(self, method, instPath)
        self.ac = AnacondaYumConf(self.methodstr, configfile="/tmp/yum.conf",
                                  root=instPath)
        self.ac.write()

        self.ayum = AnacondaYum(fn="/tmp/yum.conf", root=instPath)
        # FIXME: this is a bad hack until we can get something better into yum
        self.anaconda_grouplist = []

    def doRepoSetup(self, intf, instPath):
        if not os.path.exists("/tmp/cache"):
            iutil.mkdirChain("/tmp/cache/headers")
        tasks = (self.ayum.doMacros,
                 self.ayum.doTsSetup,
                 self.ayum.doRpmDBSetup,
                 self.ayum.doRepoSetup,
                 self.ayum.doCacheSetup,
                 self.ayum.doGroupSetup,
                 self.ayum.doSackSetup )

	waitwin = YumProgress(intf, _("Retrieving installation information"),
                              len(tasks))
        self.ayum.repos.callback = waitwin

        try:
            for task in tasks:
                task()
                waitwin.next_task()
	    waitwin.pop()
        except RepoError, e:
            log.error("reading package metadata: %s" %(e,))
	    waitwin.pop()
            intf.messageWindow(_("Error"),
                               _("Unable to read package metadata. This may be "
                                 "due to a missing repodata directory.  Please "
                                 "ensure that your install tree has been "
                                 "correctly generated.  %s" % e),
                                 type="custom", custom_icon="error",
                                 custom_buttons=[_("_Exit")])
            sys.exit(0)

    def selectBestKernel(self):
        """Find the best kernel package which is available and select it."""
        
        def getBestKernelByArch(pkgname, ayum):
            """Convenience func to find the best arch of a kernel by name"""
            pkgs = ayum.pkgSack.returnNewestByName(pkgname)
            if len(pkgs) == 0:
                return None
        
            archs = {}
            for pkg in pkgs:
                (n, a, e, v, r) = pkg.pkgtup
                archs[a] = pkg
            a = rpmUtils.arch.getBestArchFromList(archs.keys())
            return archs[a]

        foundkernel = False

        kpkg = getBestKernelByArch("kernel", self.ayum)

        if not foundkernel and os.path.exists("/proc/xen"):
            try:
                kxen = getBestKernelByArch("kernel-xen-guest", self.ayum)
                log.info("selecting kernel-xen-guest package for kernel")
                foundkernel = True
            except PackageSackError:
                kxen = None
                log.debug("no kernel-xen-guest package")
            else:
                self.ayum.tsInfo.addInstall(kxen)
                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-xen-guest-devel")
                    self.selectPackage("kernel-xen-guest-devel")

        if not foundkernel and \
               (open("/proc/cmdline").read().find("xen0") != -1):
            try:
                kxen = getBestKernelByArch("kernel-xen-hypervisor", self.ayum)
                log.info("selecting kernel-xen-hypervisor package for kernel")
                foundkernel = True
            except PackageSackError:
                kxen = None
                log.debug("no kernel-xen-hypervisor package")
            else:
                self.ayum.tsInfo.addInstall(kxen)
                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-xen-hypervisor-devel")
                    self.selectPackage("kernel-xen-hypervisor-devel")

        if not foundkernel and (isys.smpAvailable() or isys.htavailable()):
            try:
                ksmp = getBestKernelByArch("kernel-smp", self.ayum)
                log.info("selected kernel-smp package for kernel")
                foundkernel = True
            except PackageSackError:
                ksmp = None
                log.debug("no kernel-smp package")

            if ksmp and ksmp.returnSimple("arch") == kpkg.returnSimple("arch"):
                self.ayum.tsInfo.addInstall(ksmp)
                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-smp-devel")
                    self.selectPackage("kernel-smp-devel")
            
        if not foundkernel:
            log.info("selected kernel package for kernel")
            self.ayum.tsInfo.addInstall(kpkg)
            if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                log.debug("selecting kernel-devel")
                self.selectPackage("kernel-devel")

    def selectBootloader(self):
        if iutil.getArch() in ("i386", "x86_64"):
            self.selectPackage("grub")
        elif iutil.getArch() == "s390":
            self.selectPackage("s390utils")
        elif iutil.getArch() == "ppc":
            self.selectPackage("yaboot")
        elif iutil.getArch() == "ia64":
            self.selectPackage("elilo")

    def doPostSelection(self, intf, id, instPath):
        # do some sanity checks for kernel and bootloader
        self.selectBestKernel()
        self.selectBootloader()

        dscb = YumDepSolveProgress(intf)
        self.ayum.dsCallback = dscb
        try:
            (code, msgs) = self.ayum.buildTransaction()
            (self.dlpkgs, self.totalSize, self.totalFiles)  = self.ayum.getDownloadPkgs()
        finally:
            dscb.pop()
            

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
                   '/etc/X11', '/root', '/var/tmp', '/etc/rpm', '/var/cache', '/var/cache/yum' ):
            try:
                os.mkdir(instPath + i)
            except os.error, (errno, msg):
                pass
#            log.error("Error making directory %s: %s" % (i, msg))

        self.initLog(id, instPath)

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
	log.info("Preparing to install packages")
        if flags.test:
	    log.info("Test mode - not performing install")
            return

        if not id.upgrade:
            rpm.addMacro("__dbi_htconfig",
                         "hash nofsync %{__dbi_other} %{__dbi_perms}")        

        pkgTimer = timer.Timer(start = 0)

        id.instProgress.setSizes(len(self.dlpkgs), self.totalSize, self.totalFiles)
        id.instProgress.processEvents()

        cb = simpleCallback(intf.messageWindow, id.instProgress, pkgTimer, self.methodstr, intf.progressWindow, self.instLog, self.modeText, self.ayum.ts)

        cb.initWindow = intf.waitWindow(_("Install Starting"),
                                        _("Starting install process.  This may take several minutes..."))

        self.ayum.run(self.instLog, cb, intf)

        if not cb.beenCalled:
            cb.initWindow.pop()

        self.method.filesDone()
        self.instLog.close ()

        id.instProgress = None

    def doPostInstall(self, intf, id, instPath):
        if flags.test:
            return

        w = intf.progressWindow(_("Post Install"),
                                _("Performing post install configuration..."), 6)

        id.network.write(instPath)

        for tsmbr in self.ayum.tsInfo.matchNaevr(name='rhgb'):
            id.bootloader.args.append("rhgb quiet")
            break

        for tsmbr in self.ayum.tsInfo.matchNaevr(name='gdm'):
            id.desktop.setDefaultRunLevel(5)
            break

# XXX: write proper lvm config

        w.pop()
        AnacondaBackend.doPostInstall(self, intf, id, instPath) 

    def kernelVersionList(self):
        kernelVersions = []

        # nick is used to generate the lilo name
        for (ktag, nick) in [ ('kernel-smp', 'smp'),
                              ('kernel-xen-hypervisor', 'hypervisor'),
                              ('kernel-xen-guest', 'guest') ]:
            tag = ktag.rsplit('-', 1)[1]
            for tsmbr in self.ayum.tsInfo.matchNaevr(name=ktag):
                version = ( tsmbr.version + '-' + tsmbr.release + tag)
                kernelVersions.append((version, nick))

        for tsmbr in self.ayum.tsInfo.matchNaevr(name='kernel'):
            version = ( tsmbr.version + '-' + tsmbr.release)
            kernelVersions.append((version, 'up'))

        return kernelVersions

    def groupExists(self, group):
        return self.ayum.groupInfo.groupExists(group)

    def selectGroup(self, group, *args):
        if not self.groupExists(group):
            log.debug("no such group %s" %(group,))
            return

        pkgs = self.ayum.groupInfo.pkgTree(group)
        for pkg in pkgs:
            try:
                map(lambda x: self.ayum.tsInfo.addInstall(x),
                    self.ayum.getBestPackages(pkg))
            except PackageSackError:
                log.debug("no such package %s" %(pkg,))

        for grp in self.ayum.groupInfo.groupTree(group):
            if grp not in self.anaconda_grouplist:
                self.anaconda_grouplist.append(grp)

    def deselectGroup(self, group, *args):
        if not self.groupExists(group):
            log.debug("no such group %s" %(group,))
            return

        gid = self.ayum.groupInfo.matchGroup(group)
        for pkg in self.ayum.groupInfo.default_pkgs[gid] + \
                self.ayum.groupInfo.mandatory_pkgs[gid]:
            try:
                map(lambda x: self.ayum.tsInfo.remove(x.pkgtup),
                    self.ayum.getBestPackages(pkg))
            except PackageSackError:
                log.debug("no such package %s" %(pkg,))

        for grp in self.ayum.groupInfo.groupTree(group):
            if grp in self.anaconda_grouplist:
                self.anaconda_grouplist.remove(grp)

    def selectPackage(self, pkg, *args):
        sp = pkg.rsplit(".", 2)
        p = None
        if len(sp) == 2:
            try:
                map(lambda x: self.ayum.tsInfo.addInstall(x),
                    self.ayum.getBestPackages(sp[0], sp[1]))
                return
            except PackageSackError:
                # maybe the package has a . in the name
                pass

        if p is None:
            try:
                map(lambda x: self.ayum.tsInfo.addInstall(x),
                    self.ayum.getBestPackages(pkg))
            except PackageSackError:
                log.debug("no such package %s" %(pkg,))
                return
        
    def deselectPackage(self, pkg, *args):
        sp = pkg.rsplit(".", 2)
        p = None
        if len(sp) == 2:
            try:
                map(lambda x: self.ayum.tsInfo.remove(x),
                    self.ayum.getBestPackages(sp[0], sp[1]))
                return
            except PackageSackError:
                # maybe the package has a . in the name
                pass

        if p is None:
            try:
                map(lambda x: self.ayum.tsInfo.remove(x),
                    self.ayum.getBestPackages(pkg))
            except PackageSackError:
                log.debug("no such package %s" %(pkg,))
                return

class YumProgress:
    def __init__(self, intf, text, total):
        window = intf.progressWindow(_("Installation Progress"), text ,total)
        self.window = window
        self.total = float(total)
        self.num = 0
        self.popped = False

    def progressbar(self, current, total, name=None):
        if not self.popped:
            self.window.set(current)

    def pop(self):
        self.window.pop()
        self.popped = True

    def next_task(self):
        self.num += 1
        if not self.popped:
            self.window.set(self.num/self.total)

    def errorlog(self, value, msg):
        log.error(msg)

    def filelog(self, value, msg):
        pass

    def log(self, value, msg):
        log.info(msg)

class YumDepSolveProgress:
    def __init__(self, intf):
        window = intf.progressWindow(_("Dependency Check"),
        _("Checking dependencies in packages selected for installation..."), 1.0)
        self.window = window
        self.total = 1.0
        
        self.pkgAdded = self.procReq = self.transactionPopulation = self.downloadHeader = self.tscheck = self.unresolved = self.procConflict = self.refresh

    def refresh(self, *args):
        self.window.refresh()

    def set(self, value):
        self.current = value
        self.window.set(self.current)

    def start(self):
        self.set(0.1)
        self.refresh()

    def restartLoop(self):
        new = ((1.0 - self.current) / 2) + self.current
        self.set(new)
        self.refresh()
    
    def end(self):
        self.window.set(1.0)
        self.window.refresh()

    def pop(self):
        self.window.pop()

    def errorlog(self, value, msg):
        log.error(msg)

    def filelog(self, value, msg):
        pass

    def log(self, value, msg):
        log.info(msg)
