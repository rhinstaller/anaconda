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

from rhpl.log import log
from rhpl.translate import _

import iutil

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

            fd = os.open(path, os.O_RDONLY)
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
                totalSize += int(po.getSimple("installedsize"))
                for filetype in po.returnFileTypes():
                    totalFiles += len(po.returnFileEntries(ftype=filetype)
                downloadpkgs.append(po)

        return (downloadpkgs, totalSize, totalFiles)

    def run(self, cb):
        self.initActionTs()
        self.populateTs(keepold=0)
        self.ts.check()
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

def doYumInstall(method, id, intf, instPath):
    if flags.test:
        return

# XXX: Only operate on nfs trees for now
    if not id.methodstr.startswith('nfs:/'):
        from packages import doInstall
        return doInstall(method, id, intf, instPath)

    upgrade = id.getUpgrade()

    if upgrade:
        logname = '/root/upgrade.log'
    else:
        logname = '/root/install.log'

    instLogName = instPath + logname
    try:
        iutil.rmrf (instLogName)
    except OSError:
        pass

    instLog = open(instLogName, "w+")
    if upgrade:
        logname = '/root/upgrade.log'
    else:
        logname = '/root/install.log'

    instLogName = instPath + logname
    try:
        iutil.rmrf (instLogName)
    except OSError:
        pass

    instLog = open(instLogName, "w+")

   # dont start syslogd if we arent creating filesystems
    if flags.setupFilesystems:
        syslogname = "%s%s.syslog" % (instPath, logname)
        try:
            iutil.rmrf (syslogname)
        except OSError:
            pass
        syslog.start (instPath, syslogname)
    else:
        syslogname = None

    if upgrade:
        modeText = _("Upgrading %s-%s-%s.%s.\n")
    else:
        modeText = _("Installing %s-%s-%s.%s.\n")

    ac = AnacondaYumConf(configfile="/tmp/yum.conf", root=instPath)
    ayum = AnacondaYum(method, id, intf, instPath)
    ayum.setup(fn="/tmp/yum.conf", root=instPath)
    
    ayum.setGroupSelection(["Core"], intf)

    pkgTimer = timer.Timer(start = 0)

    (dlpkgs, totalSize, totalFiles)  = ayum.getDownloadPkgs()

    id.instProgress.setSizes(len(dlpkgs), totalSize, totalFiles)
    id.instProgress.processEvents()

    cb = simpleCallback(intf.messageWindow, id.instProgress, pkgTimer, method, intf.progressWindow, instLog, modeText, ayum.ts)

    cb.initWindow = intf.waitWindow(_("Install Starting"),
                                    _("Starting install process.  This may take several minutes..."))

    ayum.run(cb)

    if not cb.beenCalled:
        cb.initWindow.pop()

    method.filesDone()
    instLog.close ()

    id.instProgress = None


