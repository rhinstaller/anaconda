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
import warnings

import rpm
import rpmUtils
import urlgrabber.progress
import urlgrabber.grabber
import yum
from yum.constants import *
from yum.Errors import RepoError, YumBaseError
from repomd.mdErrors import PackageSackError
from installmethod import FileCopyException
from backend import AnacondaBackend
from sortedtransaction import *
from genheader import *
from constants import *
from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

import urlparse
urlparse.uses_fragment.append('media')


import iutil
import isys

import whiteout

#XXX: this needs to be somewhere better - probably method
def getcd(po):
    try: 
        uri = po.returnSimple('basepath')
        (scheme, netloc, path, query, fragid) = urlparse.urlsplit(uri)
        if scheme != "media" or not fragid:
            return 0
        else:
            return int(fragid)
    except (AttributeError, KeyError):
        return 0


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

            po = h
            hdr = po.returnLocalHeader()
            path = po.returnSimple('relativepath')

            self.progress.setPackage(hdr)
            self.progress.setPackageScale(0, 1)

            self.instLog.write(self.modeText % (po.returnSimple('name'),
                                                po.returnSimple('version'),
                                                po.returnSimple('release'),
                                                po.returnSimple('arch')))

            self.instLog.flush()
            nvra = po.returnNevraPrintable()
            self.fdnos[nvra] = -1

            self.size = po.returnSimple('installedsize')

            while self.fdnos[nvra] < 0:
                try:
                    fn = self.method.getRPMFilename(os.path.basename(path), getcd(po), None) 
                except FileCopyException, e:
                    log.info("Failed %s in %s" %(req[0], txmbr.name))
                    self.method.unmountCD()
                    rc = self.messageWindow(_("Error"),
                        _("The package %s-%s-%s.%s cannot be opened. This is due "
                          "to a missing file or perhaps a corrupt package.  "
                          "If you are installing from CD media this usually "
                          "means the CD media is corrupt, or the CD drive is "
                          "unable to read the media.\n\n"
                          "Press <return> to try again.") % (po.returnSimple('name'),
                                                po.returnSimple('version'),
                                                po.returnSimple('release'),
                                                po.returnSimple('arch')),
                                            type="custom",
                                            custom_icon="error",
                                            custom_buttons = [ _("Re_boot"),
                                                               _("_Retry") ])
                    if rc == 0:
                        rc = self.messageWindow(_("Warning"),
                                                _("If you reboot, your system "
                                                  "will be left in an "
                                                  "inconsistent state that "
                                                  "will likely require "
                                                  "reinstallation.  Are you "
                                                  "sure you wish to "
                                                  "continue?"),
                                                type = "custom",
                                                custom_icon="warning",
                                                custom_buttons = [_("_Cancel"),
                                                                  _("_Reboot")])
                        if rc == 1:
                            sys.exit(0)
                    
                fd = os.open(fn, os.O_RDONLY)
                self.fdnos[nvra] = fd

            return self.fdnos[nvra]

        elif what == rpm.RPMCALLBACK_INST_PROGRESS:
            if amount > total:
                amount = total
            if not total or total == 0 or total == "0":
                total = amount
            self.progress.setPackageScale(amount, total)

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            po = h
            hdr = po.returnLocalHeader()
            path = po.returnSimple('relativepath')

            fn = self.method.getRPMFilename(os.path.basename(path), getcd(po), None)
            nvra = po.returnNevraPrintable()

            os.close(self.fdnos[nvra])
            self.method.unlinkFilename(fn)
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

class YumSorter(yum.YumBase):
    
    def __init__(self):
        yum.YumBase.__init__(self)
        self.deps = {}
        self.path = []
        self.loops = []

    def isPackageInstalled(self, pkgname):
        # FIXME: this sucks.  we should probably suck it into yum proper
        # but it'll need a bit of cleanup first.  
        installed = False
        if self.rpmdb.installed(name = pkgname):
            installed = True
            
        lst = self.tsInfo.matchNaevr(name = pkgname)
        for txmbr in lst:
            if txmbr.po.state in TS_INSTALL_STATES:
                return True
        if installed and len(lst) > 0:
            # if we get here, then it was installed, but it's in the tsInfo
            # for an erase or obsoleted --> not going to be installed at end
            return False
        return installed

    def _provideToPkg(self, req):
        best = None
        (r, f, v) = req

        satisfiers = []
        for po in self.whatProvides(r, f, v):
            # if we already have something installed which does the provide
            # then that's obviously the one we want to use.  this takes
            # care of the case that we select, eg, kernel-smp and then
            # have something which requires kernel
            if self.tsInfo.getMembers(po.pkgtup):
                self.deps[req] = po
                return po
            if po.name not in satisfiers:
                satisfiers.append(po)

        if satisfiers:
            best = self.bestPackagesFromList(satisfiers)[0]
            self.deps[req] = best
            return best
        return None

    def prof_resolveDeps(self):
        fn = "anaconda.prof.0"
        import hotshot, hotshot.stats
        prof = hotshot.Profile(fn)
        rc = prof.runcall(self._resolveDeps)
        prof.close()
        print "done running depcheck"
        stats = hotshot.stats.load(fn)
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats(20)
        return rc

    def resolveDeps(self):
        if self.dsCallback: self.dsCallback.start()
        unresolved = self.tsInfo.getMembers()
        while len(unresolved) > 0:
            if self.dsCallback: self.dsCallback.tscheck(len(unresolved))
            unresolved = self.tsCheck(unresolved)
            if self.dsCallback: self.dsCallback.restartLoop()
        return (2, ['Success - deps resolved'])

    def tsCheck(self, tocheck):
        unresolved = []
        for txmbr in tocheck:
            if txmbr.name == "redhat-lsb": # FIXME: this speeds things up a lot
                continue
            if self.dsCallback: self.dsCallback.pkgAdded()
            if txmbr.output_state not in TS_INSTALL_STATES:
                continue
            reqs = txmbr.po.returnPrco('requires')
            provs = txmbr.po.returnPrco('provides')

            for req in reqs:
                if req[0].startswith('rpmlib(') or req[0].startswith('config('):
                    continue
                if req in provs:
                    continue
                dep = self.deps.get(req, None)
                if dep is None:
                    dep = self._provideToPkg(req)
                    if dep is None:
                        log.warning("Unresolvable dependancy %s in %s"
                                    %(req[0], txmbr.name))
                        continue

                # Skip filebased requires on self, etc
                if txmbr.name == dep.name:
                    continue

                if (dep.name, txmbr.name) in whiteout.whitetup:
                    log.debug("ignoring %s>%s in whiteout" %(dep.name, txmbr.name))
                    continue
                if self.tsInfo.exists(dep.pkgtup):
                    pkgs = self.tsInfo.getMembers(pkgtup=dep.pkgtup)
                    member = self.bestPackagesFromList(pkgs)[0]
                else:
                    member = self.tsInfo.addInstall(dep)
                    unresolved.append(member)

                #Add relationship
                found = False
                for (tup, rel) in txmbr.relatedto:
                    if member.po.pkgtup == tup:
                        found = True
                        break
                if not found:
                    txmbr.setAsDep(member.po)

        return unresolved

    def doTsSetup(self):
        if hasattr(self, 'read_ts'):
            return

        if not self.conf.installroot:
            raise yum.Errors.YumBaseError, 'Setting up TransactionSets before config class is up'

        installroot = self.conf.installroot
        self.read_ts = rpmUtils.transaction.initReadOnlyTransaction(root=installroot)
        self.tsInfo = SplitMediaTransactionData()
        self.rpmdb = rpmUtils.RpmDBHolder()
        self.initActionTs()
   
class AnacondaYum(YumSorter):
    def __init__(self, fn="/etc/yum.conf", root="/", method=None):
        YumSorter.__init__(self)
        self.doConfigSetup(fn, root)
        self.method = method
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
        if not self.method.splitmethod:
            self.populateTs(keepold=0)
            self.ts.check()
            self.ts.order()
            self._run(instLog, cb, intf)
        else:
            for i in self.tsInfo.reqmedia.keys():
                self.tsInfo.curmedia = i
                self.method.switchMedia(i)
                self.populateTs(keepold=0)
                self.ts.check()
                self.ts.order()
                self._run(instLog, cb, intf)

    def _run(self, instLog, cb, intf):
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

#From yum depsolve.py
    def populateTs(self, test=0, keepold=1):
        """take transactionData class and populate transaction set"""

        if self.dsCallback: self.dsCallback.transactionPopulation()
        ts_elem = {}
        if keepold:
            for te in self.ts:
                epoch = te.E()
                if epoch is None:
                    epoch = '0'
                pkginfo = (te.N(), te.A(), epoch, te.V(), te.R())
                if te.Type() == 1:
                    mode = 'i'
                elif te.Type() == 2:
                    mode = 'e'
                
                ts_elem[(pkginfo, mode)] = 1
                
        for txmbr in self.tsInfo.getMembers():
            self.log(6, 'Member: %s' % txmbr)
            if txmbr.ts_state in ['u', 'i']:
                if ts_elem.has_key((txmbr.pkgtup, 'i')):
                    continue
                self.downloadHeader(txmbr.po)
                hdr = txmbr.po.returnLocalHeader()
                rpmfile = txmbr.po.localPkg()
                
                if txmbr.ts_state == 'u':
                    if txmbr.po.name.startswith("kernel-module-"):
                        self.handleKernelModule(txmbr)
                    if self.allowedMultipleInstalls(txmbr.po):
                        self.log(5, '%s converted to install' % (txmbr.po))
                        txmbr.ts_state = 'i'
                        txmbr.output_state = TS_INSTALL

#XXX: Changed callback api to take a package object
                self.ts.addInstall(hdr, txmbr.po, txmbr.ts_state)
                self.log(4, 'Adding Package %s in mode %s' % (txmbr.po, txmbr.ts_state))
                if self.dsCallback: 
                    self.dsCallback.pkgAdded(txmbr.pkgtup, txmbr.ts_state)
            
            elif txmbr.ts_state in ['e']:
                if ts_elem.has_key((txmbr.pkgtup, txmbr.ts_state)):
                    continue
                indexes = self.rpmdb.returnIndexByTuple(txmbr.pkgtup)
                for idx in indexes:
                    self.ts.addErase(idx)
                    if self.dsCallback: self.dsCallback.pkgAdded(txmbr.pkgtup, 'e')
                    self.log(4, 'Removing Package %s' % txmbr.po)

class YumBackend(AnacondaBackend):
    def __init__(self, method, instPath):
        AnacondaBackend.__init__(self, method, instPath)

    def doInitialSetup(self, id, instPath):
        if id.getUpgrade():
           # FIXME: make sure that the rpmdb doesn't have stale locks :/
            for file in ["__db.000", "__db.001", "__db.002", "__db.003"]:
                try:
                    os.unlink("%s/var/lib/rpm/%s" %(instPath, file))
                except:
                    log.error("failed to unlink /var/lib/rpm/%s" %(file,))

        self.ac = AnacondaYumConf(self.method.getMethodUri(), 
                                 configfile="/tmp/yum.conf", root=instPath)
        self.ac.write()
        self.ayum = AnacondaYum(fn="/tmp/yum.conf", root=instPath, method=self.method)

    def doRepoSetup(self, intf, instPath):
        if not os.path.exists("/tmp/cache"):
            iutil.mkdirChain("/tmp/cache/headers")

        tasks = ( (self.ayum.doMacros, 1),
                  (self.ayum.doTsSetup, 1),
                  (self.ayum.doRpmDBSetup, 5),
                  (self.ayum.doRepoSetup, 15),
                  (self.ayum.doCacheSetup, 1),
                  (self.ayum.doGroupSetup, 1),
                  (self.ayum.doSackSetup, 50),
                  (self._catchallCategory, 1))

        tot = 0
        for t in tasks:
            tot += t[1]
	waitwin = YumProgress(intf, _("Retrieving installation information..."),
                              tot)
        self.ayum.repos.callback = waitwin

        try:
            at = 0
            for (task, amt) in tasks:
                waitwin.set_incr(amt)
                task()
                at += amt
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

        self.ayum.repos.callback = None

    def _catchallCategory(self):
        # FIXME: this is a bad hack, but catch groups which aren't in
        # a category yet are supposed to be user-visible somehow.
        # conceivably should be handled by yum
        grps = {}
        for g in self.ayum.comps.groups:
            if g.user_visible:
                grps[g.groupid] = g

        for cat in self.ayum.comps.categories:
            for g in cat.groups:
                if grps.has_key(g):
                    del grps[g]

        if len(grps.keys()) == 0:
            return
        c = yum.comps.Category()
        c.name = _("Uncategorized")
        c._groups = grps
        c.categoryid = "uncategorized"
        self.ayum.comps.categories.append(c)

    def getDefaultGroups(self):
        return map(lambda x: x.groupid,
                   filter(lambda x: x.default,
                          self.ayum.comps.groups))

    def selectBestKernel(self):
        """Find the best kernel package which is available and select it."""
        
        def getBestKernelByArch(pkgname, ayum):
            """Convenience func to find the best arch of a kernel by name"""
            pkgs = ayum.pkgSack.returnNewestByName(pkgname)
            if len(pkgs) == 0:
                return None
            pkgs = self.ayum.bestPackagesFromList(pkgs)
            if len(pkgs) == 0:
                return None
            return pkgs[0]

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
                self.ayum.install(po = kxen)
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
                self.ayum.install(po = kxen)
                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-xen-hypervisor-devel")
                    self.selectPackage("kernel-xen-hypervisor-devel")

        if not foundkernel and (isys.smpAvailable() or isys.htavailable()
                                or iutil.hasNX()):
            try:
                ksmp = getBestKernelByArch("kernel-smp", self.ayum)
                log.info("selected kernel-smp package for kernel")
                foundkernel = True
            except PackageSackError:
                ksmp = None
                log.debug("no kernel-smp package")

            if ksmp and ksmp.returnSimple("arch") == kpkg.returnSimple("arch"):
                self.ayum.install(po=ksmp)
                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-smp-devel")
                    self.selectPackage("kernel-smp-devel")
            
        if not foundkernel:
            log.info("selected kernel package for kernel")
            self.ayum.install(po=kpkg)
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

    def selectLanguageGroups(self):
        import language
        langToGroup = { "de": "german-support",
                        "es": "spanish-support",
                        "fr": "french-support",
                        "it": "italian-support",
                        "pt_BR": "brazilian-support",
                        "ru": "russian-support",
                        "ja": "japanese-support",
                        "ko": "korean-support",
                        "zh": "chinese-support",
                        "cz": "czech-support",
                        "hi": "hindi-suppot",
                        "gu": "gujarati-support",
                        "pa": "punjabi-support",
                        "ta": "tamil-support",
                        "bn": "bengali-support",
                        "ar": "arabic-support",
                        "ca": "catalan-support",
                        "uk": "ukranian-support",
                        "sv": "swedish-support" }
        lang = os.environ["LANG"]
        langs = language.expandLangs(lang)
        for l in langs:
            if langToGroup.has_key(l):
                self.selectGroup(langToGroup[l])

    def doPostSelection(self, intf, id, instPath):
        # do some sanity checks for kernel and bootloader
        self.selectBestKernel()
        self.selectBootloader()
        self.selectLanguageGroups()
        
        if id.getUpgrade():
            self.ayum.update()

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

        cb = simpleCallback(intf.messageWindow, id.instProgress, pkgTimer, self.method, intf.progressWindow, self.instLog, self.modeText, self.ayum.ts)

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

    def __getGroupId(self, group):
        """Get the groupid for the given name (english or translated)."""
        for g in self.ayum.comps.groups:
            if group == g.name:
                return g.groupid
            for trans in g.translated_name.values():
                if group == trans:
                    return g.groupid

    def selectGroup(self, group, *args):
        try:
            self.ayum.selectGroup(group)
        except yum.Errors.GroupsError, e:
            # try to find out if it's the name or translated name
            gid = self.__getGroupId(group)
            if gid is not None:
                self.ayum.selectGroup(gid)
            else:
                log.debug("no such group %s" %(group,))

    def deselectGroup(self, group, *args):
        try:
            self.ayum.deselectGroup(group)
        except yum.Errors.GroupsError, e:
            # try to find out if it's the name or translated name
            gid = self.__getGroupId(group)
            if gid is not None:
                self.ayum.deselectGroup(gid)
            else:
                log.debug("no such group %s" %(group,))

    def selectPackage(self, pkg, *args):
        sp = pkg.rsplit(".", 2)
        if len(sp) == 2:
            try:
                self.ayum.install(name = sp[0], arch = sp[1])
                return
            except yum.Errors.InstallError:
                # maybe the package has a . in the name
                pass

        try:
            self.ayum.install(name=pkg)
            return
        except yum.Errors.InstallError:
            log.debug("no such package %s" %(pkg,))
            return
        
    def deselectPackage(self, pkg, *args):
        sp = pkg.rsplit(".", 2)
        txmbrs = []
        if len(sp) == 2:
            txmbrs = self.ayum.tsInfo.matchNaevr(name=sp[0], arch=sp[1])

        if len(txmbrs) == 0:
            txmbrs = self.ayum.tsInfo.matchNaevr(name=pkg)

        if len(txmbrs) > 0:
            map(lambda x: self.ayum.tsInfo.remove(x), txmbrs)
        else:
            log.debug("no such package %s" %(pkg,))

class YumProgress:
    def __init__(self, intf, text, total):
        window = intf.progressWindow(_("Installation Progress"), text,
                                     total, 0.01)
        self.window = window
        self.current = 0
        self.incr = 1
        self.total = total
        self.popped = False

    def set_incr(self, incr):
        self.incr = incr

    def progressbar(self, current, total, name=None):
        if not self.popped:
            self.window.set(float(current)/total * self.incr + self.current)
        else:
            warnings.warn("YumProgress.progressbar called when popped",
                          RuntimeWarning, stacklevel=2) 

    def pop(self):
        self.window.pop()
        self.popped = True

    def next_task(self, current = None):
        if current:
            self.current = current
        else:
            self.current += self.incr
        if not self.popped:
            self.window.set(self.current)
        else:
            warnings.warn("YumProgress.set called when popped",
                          RuntimeWarning, stacklevel=2)             

    def errorlog(self, value, msg):
        log.error(msg)

    def filelog(self, value, msg):
        pass

    def log(self, value, msg):
        log.info(msg)

class YumDepSolveProgress:
    def __init__(self, intf):
        window = intf.progressWindow(_("Dependency Check"),
        _("Checking dependencies in packages selected for installation..."),
                                     1.0, 0.01)
        self.window = window

        self.numpkgs = None
        self.loopstart = None
        self.incr = None
        
        self.restartLoop = self.downloadHeader = self.transactionPopulation = self.refresh
        self.procReq = self.procConflict = self.unresolved = self.noop()

    def tscheck(self, num = None):
        self.refresh()
        if num is not None:
            self.numpkgs = num
            self.loopstart = self.current
            self.incr = (1.0 / num) * ((1.0 - self.loopstart) / 2)

    def pkgAdded(self, *args):
        if self.numpkgs:
            self.set(self.current + self.incr)

    def noop(self):
        pass

    def refresh(self, *args):
        self.window.refresh()

    def set(self, value):
        self.current = value
        self.window.set(self.current)

    def start(self):
        self.set(0.0)
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
