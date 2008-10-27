#
# yuminstall.py
#
# Copyright (C) 2005, 2006, 2007  Red Hat, Inc.  All rights reserved.
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

from flags import flags
from errors import *

import sys
import os
import os.path
import shutil
import time
import warnings
import types
import locale
import glob

import rpm
import rpmUtils
import urlgrabber.progress
import urlgrabber.grabber
from urlgrabber.grabber import URLGrabber, URLGrabError
import yum
import iniparse
from yum.constants import *
from yum.Errors import *
from yum.yumRepo import YumRepository
from backend import AnacondaBackend
from product import *
from sortedtransaction import SplitMediaTransactionData
from constants import *
from image import *
from compssort import *
import packages

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import network

# specspo stuff
rpm.addMacro("_i18ndomains", "redhat-dist")

import logging
log = logging.getLogger("anaconda")

import urlparse
urlparse.uses_fragment.append('media')

urlgrabber.grabber.default_grabber.opts.user_agent = "%s (anaconda)/%s" %(productName, productVersion)

import iutil
import isys

def size_string (size):
    def number_format(s):
        return locale.format("%s", s, 1)

    if size > 1024 * 1024:
        size = size / (1024*1024)
        return _("%s MB") %(number_format(size),)
    elif size > 1024:
        size = size / 1024
        return _("%s KB") %(number_format(size),)        
    else:
        if size == 1:
            return _("%s Byte") %(number_format(size),)                    
        else:
            return _("%s Bytes") %(number_format(size),)

class AnacondaCallback:

    def __init__(self, ayum, anaconda, instLog, modeText):
        self.repos = ayum.repos
        self.ts = ayum.ts
        self.ayum = ayum

        self.messageWindow = anaconda.intf.messageWindow
        self.pulseWindow = anaconda.intf.progressWindow
        self.progress = anaconda.id.instProgress
        self.progressWindowClass = anaconda.intf.progressWindow
        self.rootPath = anaconda.rootPath

        self.initWindow = None

        self.progressWindow = None
        self.lastprogress = 0
        self.incr = 20

        self.instLog = instLog
        self.modeText = modeText

        self.openfile = None
        self.inProgressPo = None

    def setSizes(self, numpkgs, totalSize, totalFiles):
        self.numpkgs = numpkgs
        self.totalSize = totalSize
        self.totalFiles = totalFiles

        self.donepkgs = 0
        self.doneSize = 0
        self.doneFiles = 0
        

    def callback(self, what, amount, total, h, user):
        if what == rpm.RPMCALLBACK_TRANS_START:
            # step 6 is the bulk of the ts processing time
            if amount == 6:
                self.progressWindow = \
                    self.progressWindowClass (_("Processing"), 
                                              _("Preparing transaction from installation source..."),
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
            (hdr, rpmloc) = h
            # hate hate hate at epochs...
            epoch = hdr['epoch']
            if epoch is not None:
                epoch = str(epoch)
            txmbrs = self.ayum.tsInfo.matchNaevr(hdr['name'], hdr['arch'],
                                                 epoch, hdr['version'],
                                                 hdr['release'])
            if len(txmbrs) == 0:
                raise RuntimeError, "Unable to find package %s-%s-%s.%s" %(hdr['name'], hdr['version'], hdr['release'], hdr['arch'])
            po = txmbrs[0].po

            repo = self.repos.getRepo(po.repoid)

            pkgStr = "%s-%s-%s.%s" % (po.name, po.version, po.release, po.arch)
            s = _("<b>Installing %s</b> (%s)\n") %(pkgStr, size_string(hdr['size']))
            summary = gettext.ldgettext("redhat-dist", hdr['summary'] or "")
            if type(summary) != unicode:
                summary = unicode(summary, encoding='utf-8')
            s += summary.strip()
            self.progress.set_label(s)

            self.instLog.write(self.modeText % pkgStr)

            self.instLog.flush()
            self.openfile = None

            while self.openfile is None:
                try:
                    fn = repo.getPackage(po)

                    f = open(fn, 'r')
                    self.openfile = f
                except yum.Errors.NoMoreMirrorsRepoError:
                    self.ayum._handleFailure(po)
                except IOError:
                    self.ayum._handleFailure(po)
                except yum.Errors.RepoError, e:
                    continue
            self.inProgressPo = po

            return self.openfile.fileno()

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            if self.initWindow:
                self.initWindow.pop()
                self.initWindow = None

            (hdr, rpmloc) = h

            fn = self.openfile.name
            self.openfile.close()
            self.openfile = None

            repo = self.repos.getRepo(self.inProgressPo.repoid)
            if os.path.dirname(fn).startswith("%s/var/cache/yum/" % self.rootPath):
                try:
                    os.unlink(fn)
                except OSError, e:
                    log.debug("unable to remove file %s" %(e,))

            self.donepkgs += 1
            self.doneSize += self.inProgressPo.returnSimple("installedsize") / 1024.0
            self.doneFiles += len(hdr[rpm.RPMTAG_BASENAMES])

            if self.donepkgs <= self.numpkgs:
                self.progress.set_text(_("%s of %s packages completed")
                                       %(self.donepkgs, self.numpkgs))
            self.progress.set_fraction(float(self.doneSize / self.totalSize))
            self.progress.processEvents()

            self.inProgressPo = None

        elif what in (rpm.RPMCALLBACK_UNINST_START,
                      rpm.RPMCALLBACK_UNINST_STOP):
            if self.initWindow is None:
                self.initWindow = self.pulseWindow(_("Finishing upgrade"),
                                                   _("Finishing upgrade process.  This may take a little while..."),
                                                   0, pulse=True)
            else:
                self.initWindow.pulse()

        else:
            pass

        if self.initWindow is None:
            self.progress.processEvents()

class AnacondaYumRepo(YumRepository):
    def __init__(self, *args, **kwargs):
        YumRepository.__init__(self, *args, **kwargs)
        self.enablegroups = True

    def needsNetwork(self):
        def _isURL(s):
            return s.startswith("http") or s.startswith("ftp")

        if len(self.baseurl) > 0:
            return len(filter(lambda s: _isURL(s), self.baseurl)) > 0
        elif self.mirrorlist:
            return _isURL(self.mirrorlist)
        else:
            return False

    def dirCleanup(self):
        cachedir = self.getAttribute('cachedir')

        if os.path.isdir(cachedir):
            if not self.needsNetwork() or self.name == "Installation Repo":
                shutil.rmtree(cachedir)
            else:
                if os.path.exists("%s/headers" % cachedir):
                    shutil.rmtree("%s/headers" % cachedir)
                if os.path.exists("%s/packages" % cachedir):
                    shutil.rmtree("%s/packages" % cachedir)

class YumSorter(yum.YumBase):
    def _transactionDataFactory(self):
        return SplitMediaTransactionData()

class AnacondaYum(YumSorter):
    def __init__(self, anaconda):
        YumSorter.__init__(self)
        self.anaconda = anaconda
        self._timestamp = None

        # Only needed for hard drive and nfsiso installs.
        self._discImages = {}
        self.isodir = None

        # Only needed for media installs.
        self.currentMedia = None
        self.mediagrabber = None

        # Where is the source media mounted?  This is the directory
        # where Packages/ is located.
        self.tree = "/mnt/source"

        # yum doesn't understand all our method URLs, so use this for all
        # except FTP and HTTP installs.
        self._baseRepoURL = "file://%s" % self.tree

        while True:
            try:
                self.configBaseURL()
                break
            except SystemError, e:
                self.anaconda.intf.messageWindow(_("Error Setting Up Repository"),
                    _("The following error occurred while setting up the "
                      "installation repository:\n\n%s\n\nPlease provide the "
                      "correct information for installing %s.") % (e, productName))

                self.anaconda.methodstr = self.anaconda.intf.methodstrRepoWindow(anaconda)

        self.doConfigSetup(root=anaconda.rootPath)
        self.conf.installonlypkgs = []
        self.macros = {}

        if flags.selinux:
            for directory in ("/tmp/updates",
                        "/etc/selinux/targeted/contexts/files",
                        "/etc/security/selinux/src/policy/file_contexts",
                        "/etc/security/selinux"):
                fn = "%s/file_contexts" %(directory,)
                if os.access(fn, os.R_OK):
                    break
            self.macros["__file_context_path"] = fn
        else:
            self.macros["__file_context_path"]  = "%{nil}"

        self.updates = []
        self.localPackages = []

    def _switchCD(self, discnum):
        if os.access("%s/.discinfo" % self.tree, os.R_OK):
            f = open("%s/.discinfo" % self.tree)
            self._timestamp = f.readline().strip()
            f.close()

        # If self.currentMedia is None, then there shouldn't be anything
        # mounted.  Before going further, see if the correct disc is already
        # in the drive.  This saves a useless eject and insert if the user
        # has for some reason already put the disc in the drive.
        if self.currentMedia is None:
            try:
                isys.mount(self.anaconda.mediaDevice, self.tree,
                           fstype="iso9660", readOnly=1)

                if verifyMedia(self.tree, discnum, None):
                    self.currentMedia = discnum
                    return

                isys.umount(self.tree)
            except:
                pass
        else:
            unmountCD(self.tree, self.anaconda.intf.messageWindow)
            self.currentMedia = None

        isys.ejectCdrom(self.anaconda.mediaDevice)

        while True:
            if self.anaconda.intf:
                self.anaconda.intf.beep()

            self.anaconda.intf.messageWindow(_("Change Disc"),
                _("Please insert %s disc %d to continue.") % (productName,
                                                              discnum))

            try:
                isys.mount(self.anaconda.mediaDevice, self.tree,
                           fstype = "iso9660", readOnly = 1)

                if verifyMedia(self.tree, discnum, self._timestamp):
                    self.currentMedia = discnum
                    break

                self.anaconda.intf.messageWindow(_("Wrong Disc"),
                        _("That's not the correct %s disc.")
                          % (productName,))
                isys.umount(self.tree)
                isys.ejectCdrom(self.anaconda.mediaDevice)
            except:
                self.anaconda.intf.messageWindow(_("Error"),
                        _("Unable to access the disc."))

    def _switchImage(self, discnum):
        umountImage(self.tree, self.currentMedia)
        self.currentMedia = None

        # mountDirectory checks before doing anything, so it's safe to
        # call this repeatedly.
        mountDirectory(self.anaconda.methodstr,
                       self.anaconda.intf.messageWindow)

        self._discImages = mountImage(self.isodir, self.tree, discnum,
                                      self.anaconda.intf.messageWindow,
                                      discImages=self._discImages)
        self.currentMedia = discnum

    def configBaseURL(self):
        # We only have a methodstr if method= or repo= was passed to
        # anaconda.  No source for this base repo (the CD media, NFS,
        # whatever) is mounted yet since loader only mounts the source
        # for the stage2 image.  We need to set up the source mount
        # now.
        if self.anaconda.methodstr:
            m = self.anaconda.methodstr

            if m.startswith("hd:"):
                if m.count(":") == 2:
                    (device, path) = m[3:].split(":")
                else:
                    (device, fstype, path) = m[3:].split(":")

                if flags.cmdline.has_key("preupgrade"):
                    self._baseRepoURL = "file:///mnt/sysimage/%s" % path
                else:
                    self.isodir = "/mnt/isodir/%s" % path

                    # This takes care of mounting /mnt/isodir first.
                    self._switchImage(1)
                    self.mediagrabber = self.mediaHandler
            elif m.startswith("nfsiso:"):
                self.isodir = "/mnt/isodir"

                # Calling _switchImage takes care of mounting /mnt/isodir first.
                if not network.hasActiveNetDev():
                    if not self.anaconda.intf.enableNetwork(self.anaconda):
                        self._baseRepoURL = None
                        return

                self._switchImage(1)
                self.mediagrabber = self.mediaHandler
            elif m.startswith("http:") or m.startswith("ftp:"):
                self._baseRepoURL = m
            elif m.startswith("nfs:"):
                if not network.hasActiveNetDev():
                    if not self.anaconda.intf.enableNetwork(self.anaconda):
                        self._baseRepoURL = None

                isys.mount(m[4:], self.tree, "nfs")
            elif m.startswith("cdrom:"):
                self._switchCD(1)
                self.mediagrabber = self.mediaHandler
                self._baseRepoURL = "file://%s" % self.tree
        else:
            # No methodstr was given.  In order to find an installation source,
            # we should first check to see if there's a CD/DVD with packages
            # on it, and then default to the mirrorlist URL.  The user can
            # always change the repo with the repo editor later.
            cdr = scanForMedia(self.tree)
            if cdr:
                self.mediagrabber = self.mediaHandler
                self.anaconda.mediaDevice = cdr
                self.currentMedia = 1
                log.info("found installation media on %s" % cdr)
            else:
                # No CD with media on it and no repo=/method= parameter, so
                # default to using whatever's enabled in /etc/yum.repos.d/
                self._baseRepoURL = None

    def configBaseRepo(self, root='/', replace=False):
        # Create the "base" repo object, assuming there is one.  Otherwise we
        # just skip all this and use the defaults from /etc/yum.repos.d.
        if not self._baseRepoURL:
            return

        # add default repos
        for (name, uri) in self.anaconda.id.instClass.getPackagePaths(self._baseRepoURL).items():
            rid = name.replace(" ", "")

            if replace:
                try:
                    repo = self.repos.getRepo("anaconda-%s-%s" % (rid, productStamp))
                    repo.baseurl = uri
                except RepoError:
                    replace = False
            else:
                # If there was an error finding the "base" repo, create a new one now.
                repo = AnacondaYumRepo("anaconda-%s-%s" % (rid, productStamp))
                repo.baseurl = uri

            repo.name = name
            repo.cost = 100

            if self.anaconda.mediaDevice or self.isodir:
                repo.mediaid = getMediaId(self.tree)
                log.info("set mediaid of repo %s to: %s" % (rid, repo.mediaid))

            repo.enable()

            if not replace:
                self.repos.add(repo)

    def mediaHandler(self, *args, **kwargs):
        mediaid = kwargs["mediaid"]
        discnum = kwargs["discnum"]
        relative = kwargs["relative"]

        # The package exists on media other than what's mounted right now.
        if discnum != self.currentMedia:
            log.info("switching from media #%s to #%s for %s" %
                     (self.currentMedia, discnum, relative))

            # Unmount any currently mounted ISO images and mount the one
            # containing the requested packages.
            if self.isodir:
                self._switchImage(discnum)
            else:
                self._switchCD(discnum)

        ug = URLGrabber(checkfunc=kwargs["checkfunc"])
        ug.urlgrab("%s/%s" % (self.tree, kwargs["relative"]), kwargs["local"],
                   text=kwargs["text"], range=kwargs["range"], copy_local=1)
        return kwargs["local"]

    # XXX: This is straight out of yum, but we need to override it here in
    # order to use our own repo class.
    def readRepoConfig(self, parser, section):
        '''Parse an INI file section for a repository.

        @param parser: ConfParser or similar to read INI file values from.
        @param section: INI file section to read.
        @return: YumRepository instance.
        '''
        repo = AnacondaYumRepo(section)
        repo.populate(parser, section, self.conf)

        # Ensure that the repo name is set
        if not repo.name:
            repo.name = section
            self.logger.error(_('Repository %r is missing name in configuration, '
                    'using id') % section)

        # Set attributes not from the config file
        repo.yumvar.update(self.conf.yumvar)
        repo.cfg = parser

        if repo.id.find("-source") != -1 or repo.id.find("-debuginfo") != -1:
            name = repo.name
            del(repo)
            raise RepoError, "Repo %s contains -source or -debuginfo, excluding" % name

        if BETANAG and not repo.enabled:
            name = repo.name
            del(repo)
            raise RepoError, "Excluding disabled repo %s for prerelease" % name

        # If repo=/method= was passed in, we want to default these extra
        # repos to off.
        if self._baseRepoURL:
            repo.enabled = False

        return repo

    # We need to make sure $releasever gets set up before .repo files are
    # read.  Since there's no redhat-release package in /mnt/sysimage (and
    # won't be for quite a while), we need to do our own substutition.
    def getReposFromConfig(self):
        def _getReleasever():
            from ConfigParser import ConfigParser
            c = ConfigParser()

            if os.access("%s/.treeinfo" % self.anaconda.methodstr, os.R_OK):
                ConfigParser.read(c, "%s/.treeinfo" % self.anaconda.methodstr)
            else:
                ug = URLGrabber()
                ug.urlgrab("%s/.treeinfo" % self.anaconda.methodstr,
                           "/tmp/.treeinfo", copy_local=1)
                ConfigParser.read(c, "/tmp/.treeinfo")

            return c.get("general", "version")

        try:
            self.yumvar["releasever"] = _getReleasever()
        except:
            self.yumvar["releasever"] = productVersion

        YumSorter.getReposFromConfig(self)

    # Override this method so yum doesn't nuke our existing logging config.
    def doLoggingSetup(self, debuglevel, errorlevel, syslog_indent=None,
                       syslog_facility=None):
        pass

    def doConfigSetup(self, fn='/tmp/anaconda-yum.conf', root='/'):
        YumSorter._getConfig(self, fn=fn, root=root,
                             enabled_plugins=["whiteout", "blacklist"])
        self.configBaseRepo(root=root)

        extraRepos = []

        if self.anaconda.id.extraModules:
            for d in glob.glob("/tmp/DD-*/rpms"):
                dirname = os.path.basename(os.path.dirname(d))
                rid = "anaconda-%s" % dirname

                repo = AnacondaYumRepo(rid)
                repo.baseurl = [ "file:///%s" % d ]
                repo.name = "Driver Disk %s" % dirname.split("-")[1]
                repo.enable()
                extraRepos.append(repo)

        if self.anaconda.isKickstart:
            for ksrepo in self.anaconda.id.ksdata.repo.repoList:
                repo = AnacondaYumRepo(ksrepo.name)
                repo.baseurl = [ ksrepo.baseurl ]
                repo.mirrorlist = ksrepo.mirrorlist
                repo.name = ksrepo.name

                if ksrepo.cost:
                    repo.cost = ksrepo.cost

                if ksrepo.excludepkgs:
                    repo.exclude = ksrepo.excludepkgs

                if ksrepo.includepkgs:
                    repo.include = ksrepo.includepkgs

                repo.enable()
                extraRepos.append(repo)

        for repo in extraRepos:
            try:
                self.repos.add(repo)
                log.info("added repository %s with URL %s" % (repo.name, repo.mirrorlist or repo.baseurl))
            except:
                log.warning("ignoring duplicate repository %s with URL %s" % (repo.name, repo.mirrorlist or repo.baseurl))

        self.repos.setCacheDir(self.conf.cachedir)

    def downloadHeader(self, po):
        while True:
            # retrying version of download header
            try:
                YumSorter.downloadHeader(self, po)
                break
            except yum.Errors.NoMoreMirrorsRepoError:
                self._handleFailure(po)
            except IOError:
                self._handleFailure(po)
            except yum.Errors.RepoError, e:
                continue

    def _handleFailure(self, package):
        if not network.hasActiveNetDev():
            if not self.anaconda.intf.enableNetwork(self.anaconda):
                return

        if not self.isodir and self.currentMedia:
            buttons = [_("Re_boot"), _("_Eject")]
        else:
            buttons = [_("Re_boot"), _("_Retry")]

        pkgFile = os.path.basename(package.returnSimple('relativepath'))
        if type(pkgFile) != unicode:
            pkgFile = unicode(pkgFile, encoding='utf-8')

        rc = self.anaconda.intf.messageWindow(_("Error"),
                   _("The file %s cannot be opened.  This is due to a missing "
                     "file, a corrupt package or corrupt media.  Please "
                     "verify your installation source.\n\n"
                     "If you exit, your system will be left in an inconsistent "
                     "state that will likely require reinstallation.\n\n") %
                                              (pkgFile,),
                                    type="custom", custom_icon="error",
                                    custom_buttons=buttons)

        if rc == 0:
            sys.exit(0)
        else:
            if not self.isodir and self.currentMedia:
                self._switchCD(self.currentMedia)
            else:
                return

    def mirrorFailureCB (self, obj, *args, **kwargs):
        # This gets called when a mirror fails, but it cannot know whether
        # or not there are other mirrors left to try, since it cannot know
        # which mirror we were on when we started this particular download. 
        # Whenever we have run out of mirrors the grabber's get/open/retrieve
        # method will raise a URLGrabError exception with errno 256.
        grab = self.repos.getRepo(kwargs["repo"]).grab
        log.warning("Failed to get %s from mirror %d/%d, "
                    "or downloaded file is corrupt" % (obj.url, grab._next + 1,
                                                       len(grab.mirrors)))

        if self.currentMedia:
            unmountCD(self.tree, self.anaconda.intf.messageWindow)
            self.currentMedia = None

    def urlgrabberFailureCB (self, obj, *args, **kwargs):
        log.warning("Try %s/%s for %s failed" % (obj.tries, obj.retry, obj.url))

        if obj.tries == obj.retry:
            return

        delay = 0.25*(2**(obj.tries-1))
        if delay > 1:
            w = self.anaconda.intf.waitWindow(_("Retrying"), _("Retrying download..."))
            time.sleep(delay)
            w.pop()
        else:
            time.sleep(delay)

    def getDownloadPkgs(self):
        downloadpkgs = []
        totalSize = 0
        totalFiles = 0
        for txmbr in self.tsInfo.getMembers():
            if txmbr.ts_state in ['i', 'u']:
                po = txmbr.po
            else:
                continue

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

    def run(self, instLog, cb, intf, id):
        def mediasort(a, b):
            # sort so that first CD comes first, etc.  -99 is a magic number
            # to tell us that the cd should be last
            if a == -99:
                return 1
            elif b == -99:
                return -1
            if a < b:
                return -1
            elif a > b:
                return 1
            return 0

        self.initActionTs()
        if id.getUpgrade():
            self.ts.ts.setProbFilter(~rpm.RPMPROB_FILTER_DISKSPACE)
        self.setColor()

        # If we don't have any required media assume single disc
        if self.tsInfo.reqmedia == {}:
            self.tsInfo.reqmedia[0] = None
        mkeys = self.tsInfo.reqmedia.keys()
        mkeys.sort(mediasort)

        if len(mkeys) > 1:
            stage2img = "%s/images/install.img" % self.tree
            if self.anaconda.backend.mountInstallImage(self.anaconda, stage2img):
                self.anaconda.id.fsset.unmountFilesystems(self.anaconda.rootPath)
                return DISPATCH_BACK

        for i in mkeys:
            self.tsInfo.curmedia = i
            if i > 0:
                pkgtup = self.tsInfo.reqmedia[i][0]

            try:
                self.dsCallback = DownloadHeaderProgress(intf, self)
                self.populateTs(keepold=0)
                self.dsCallback.pop()
                self.dsCallback = None
            except RepoError, e:
                rc = intf.messageWindow(_("Error"),
                          _("There was an error running your transaction for "
                            "the following reason: %s\n") % str(e),
                            type="custom", custom_icon="error",
                            custom_buttons=[_("_Back"), _("_Exit installer")])

                if rc == 1:
                    sys.exit(1)
                else:
                    self.tsInfo.curmedia = None
                    return DISPATCH_BACK

            self.ts.check()
            self.ts.order()

            if self._run(instLog, cb, intf) == DISPATCH_BACK:
                self.tsInfo.curmedia = None
                return DISPATCH_BACK

            self.ts.close()

    def _run(self, instLog, cb, intf):
        # set log fd.  FIXME: this is ugly.  see changelog entry from 2005-09-13
        self.ts.ts.scriptFd = instLog.fileno()
        rpm.setLogFile(instLog)

        uniqueProbs = {}
        spaceneeded = {}
        spaceprob = ""
        fileConflicts = []
        fileprob = ""

        try:
            self.runTransaction(cb=cb)
        except YumBaseError, probs:
            # FIXME: we need to actually look at these problems...
            probTypes = { rpm.RPMPROB_NEW_FILE_CONFLICT : _('file conflicts'),
                          rpm.RPMPROB_FILE_CONFLICT : _('file conflicts'),
                          rpm.RPMPROB_OLDPACKAGE: _('older package(s)'),
                          rpm.RPMPROB_DISKSPACE: _('insufficient disk space'),
                          rpm.RPMPROB_DISKNODES: _('insufficient disk inodes'),
                          rpm.RPMPROB_CONFLICT: _('package conflicts'),
                          rpm.RPMPROB_PKG_INSTALLED: _('package already installed'),
                          rpm.RPMPROB_REQUIRES: _('required package'),
                          rpm.RPMPROB_BADARCH: _('package for incorrect arch'),
                          rpm.RPMPROB_BADOS: _('package for incorrect os'),
            }

            for (descr, (ty, mount, need)) in probs.value: # FIXME: probs.value???
                log.error("%s: %s" %(probTypes[ty], descr))
                if not uniqueProbs.has_key(ty) and probTypes.has_key(ty):
                    uniqueProbs[ty] = probTypes[ty]

                if ty == rpm.RPMPROB_DISKSPACE:
                    spaceneeded[mount] = need
                elif ty in [rpm.RPMPROB_NEW_FILE_CONFLICT, rpm.RPMPROB_FILE_CONFLICT]:
                    fileConflicts.append(descr)

            if spaceneeded:
                spaceprob = _("You need more space on the following "
                              "file systems:\n")

                for (mount, need) in spaceneeded.items():
                    log.info("(%s, %s)" %(mount, need))

                    if mount.startswith("/mnt/sysimage/"):
                        mount.replace("/mnt/sysimage", "")
                    elif mount.startswith("/mnt/sysimage"):
                        mount = "/" + mount.replace("/mnt/sysimage", "")

                    spaceprob += "%d M on %s\n" % (need / (1024*1024), mount)
            elif fileConflicts:
                fileprob = _("There were file conflicts when checking the "
                             "packages to be installed:\n%s\n") % ("\n".join(fileConflicts),)

            msg = _("There was an error running your transaction for "
                    "the following reason(s): %s.\n") % ', '.join(uniqueProbs.values())

            if type(spaceprob) != unicode:
                spaceprob = unicode(spaceprob, encoding='utf-8')

            if type(fileprob) != unicode:
                fileprob = unicode(fileprob, encoding='utf-8')

            if len(self.anaconda.backend.getRequiredMedia()) > 1:
                intf.detailedMessageWindow(_("Error Running Transaction"),
                   msg, spaceprob + "\n" + fileprob, type="custom",
                   custom_icon="error", custom_buttons=[_("_Exit installer")])
                sys.exit(1)
            else:
                rc = intf.detailedMessageWindow(_("Error Running Transaction"),
                        msg, spaceprob + "\n" + fileprob, type="custom",
                        custom_icon="error",
                        custom_buttons=[_("_Back"), _("_Exit installer")])

            if rc == 1:
                sys.exit(1)
            else:
                self._undoDepInstalls()
                return DISPATCH_BACK

    def doMacros(self):
        for (key, val) in self.macros.items():
            rpm.addMacro(key, val)

    def simpleDBInstalled(self, name, arch=None):
        # FIXME: doing this directly instead of using self.rpmdb.installed()
        # speeds things up by 400%
        mi = self.ts.ts.dbMatch('name', name)
        if mi.count() == 0:
            return False
        if arch is None:
            return True
        if arch in map(lambda h: h['arch'], mi):
            return True
        return False

    def isPackageInstalled(self, name = None, epoch = None, version = None,
                           release = None, arch = None, po = None):
        # FIXME: this sucks.  we should probably suck it into yum proper
        # but it'll need a bit of cleanup first.
        if po is not None:
            (name, epoch, version, release, arch) = po.returnNevraTuple()

        installed = False
        if name and not (epoch or version or release or arch):
            installed = self.simpleDBInstalled(name)
        elif self.rpmdb.installed(name = name, epoch = epoch, ver = version,
                                rel = release, arch = arch):
            installed = True

        lst = self.tsInfo.matchNaevr(name = name, epoch = epoch,
                                     ver = version, rel = release,
                                     arch = arch)
        for txmbr in lst:
            if txmbr.output_state in TS_INSTALL_STATES:
                return True
        if installed and len(lst) > 0:
            # if we get here, then it was installed, but it's in the tsInfo
            # for an erase or obsoleted --> not going to be installed at end
            return False
        return installed

    def isGroupInstalled(self, grp):
        if grp.selected:
            return True
        elif grp.installed and not grp.toremove:
            return True
        return False

class YumBackend(AnacondaBackend):
    def __init__ (self, anaconda):
        AnacondaBackend.__init__(self, anaconda)
        self.supportsPackageSelection = True

        buf = """
[main]
installroot=%s
cachedir=/var/cache/yum
keepcache=0
logfile=/tmp/yum.log
metadata_expire=0
obsoletes=True
pluginpath=/usr/lib/yum-plugins,/tmp/updates/yum-plugins
pluginconfpath=/etc/yum/pluginconf.d,/tmp/updates/pluginconf.d
plugins=1
reposdir=/etc/anaconda.repos.d,/tmp/updates/anaconda.repos.d,/tmp/product/anaconda.repos.d
""" % (anaconda.rootPath)

        fd = open("/tmp/anaconda-yum.conf", "w")
        fd.write(buf)
        fd.close()

    def complete(self, anaconda):
        try:
            isys.umount(self.ayum.tree)
        except Exception:
            pass

        if anaconda.mediaDevice:
            try:
                shutil.copyfile("%s/media.repo" % self.ayum.tree,
                                "%s/etc/anaconda.repos.d/%s-install-media.repo" %(anaconda.rootPath, productName))
            except Exception, e:
                log.debug("Error copying media.repo: %s" %(e,))

            try:
                i = iniparse.ConfigParser()
                i.read("%s/media.repo" % self.ayum.tree)
                repo = i.sections()[0]
                del i
                shutil.copytree("%s/repodata" % self.ayum.tree,
                                "%s/var/cache/yum/%s" %(anaconda.rootPath, repo))
            except Exception, e:
                log.debug("Error setting up media repository: %s" %(e,))

        anaconda.backend.removeInstallImage()

    def doBackendSetup(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            return DISPATCH_BACK

        if anaconda.id.getUpgrade():
           # FIXME: make sure that the rpmdb doesn't have stale locks :/
           self._resetRpmDb(anaconda.rootPath)

        iutil.writeRpmPlatform()
        self.ayum = AnacondaYum(anaconda)

        self.ayum.doMacros()

        # If any enabled repositories require networking, go ahead and bring
        # it up now.  No need to have people wait for the timeout when we
        # know this in advance.
        if len(filter(lambda r: r.needsNetwork(), self.ayum.repos.listEnabled())) > 0 and \
           not network.hasActiveNetDev():
               if not anaconda.intf.enableNetwork(anaconda):
                   anaconda.intf.messageWindow(_("No Network Available"),
                       _("Some of your software repositories require "
                         "networking, but there was an error enabling the "
                         "network on your system."),
                       type="custom", custom_icon="error",
                       custom_buttons=[_("_Exit installer")])
                   sys.exit(1)

        self.doRepoSetup(anaconda)
        self.doSackSetup(anaconda)
        self.doGroupSetup(anaconda)

        self.ayum.doMacros()

    def doGroupSetup(self, anaconda):
        while True:
            try:
                # FIXME: this is a pretty ugly hack to make it so that we don't lose
                # groups being selected (#237708)
                sel = filter(lambda g: g.selected, self.ayum.comps.get_groups())
                self.ayum.doGroupSetup()
                # now we'll actually reselect groups..
                map(lambda g: self.selectGroup(g.groupid), sel)

                # and now, to add to the hacks, we'll make sure that packages don't
                # have groups double-listed.  this avoids problems with deselecting
                # groups later
                for txmbr in self.ayum.tsInfo.getMembers():
                    txmbr.groups = yum.misc.unique(txmbr.groups)
            except (GroupsError, NoSuchGroup, RepoError), e:
                buttons = [_("_Exit installer"), _("_Retry")]
            else:
                break # success

            rc = anaconda.intf.messageWindow(_("Error"),
                                        _("Unable to read group information "
                                          "from repositories.  This is "
                                          "a problem with the generation "
                                          "of your install tree."),
                                        type="custom", custom_icon="error",
                                        custom_buttons = buttons)
            if rc == 0:
                sys.exit(0)
            else:
                self.ayum._setGroups(None)
                continue

        self._catchallCategory()

    def doRepoSetup(self, anaconda, thisrepo = None, fatalerrors = True):
        self.__withFuncDo(anaconda, lambda r: self.ayum.doRepoSetup(thisrepo=r.id),
                          thisrepo=thisrepo, fatalerrors=fatalerrors)

    def doSackSetup(self, anaconda, thisrepo = None, fatalerrors = True):
        self.__withFuncDo(anaconda, lambda r: self.ayum.doSackSetup(thisrepo=r.id),
                          thisrepo=thisrepo, fatalerrors=fatalerrors)

    def __withFuncDo(self, anaconda, fn, thisrepo=None, fatalerrors=True):
        # Don't do this if we're being called as a dispatcher step (instead
        # of being called when a repo is added via the UI) and we're going
        # back.
        if thisrepo is None and anaconda.dir == DISPATCH_BACK:
            return

        # We want to call the function one repo at a time so we have some
        # concept of which repo didn't set up correctly.
        if thisrepo is not None:
            repos = [self.ayum.repos.getRepo(thisrepo)]
        else:
            repos = self.ayum.repos.listEnabled()

        for repo in repos:
            if repo.name is None:
                txt = _("Retrieving installation information...")
            else:
                txt = _("Retrieving installation information for %s...")%(repo.name)

                waitwin = anaconda.intf.waitWindow(_("Installation Progress"), txt)

            while True:
                try:
                    fn(repo)
                    waitwin.pop()
                except RepoError, e:
                    waitwin.pop()
                    if repo.needsNetwork() and not network.hasActiveNetDev():
                        if anaconda.intf.enableNetwork(anaconda):
                            repo.mirrorlistparsed = False
                            continue

                    buttons = [_("_Exit installer"), _("Edit"), _("_Retry")]
                else:
                    break # success

                if anaconda.isKickstart:
                    buttons.append(_("_Continue"))

                waitwin.pop()

                if not fatalerrors:
                    raise RepoError, e

                rc = anaconda.intf.messageWindow(_("Error"),
                                   _("Unable to read package metadata. This may be "
                                     "due to a missing repodata directory.  Please "
                                     "ensure that your install tree has been "
                                     "correctly generated.\n\n%s" % e),
                                     type="custom", custom_icon="error",
                                     custom_buttons=buttons)
                if rc == 0:
                    # abort
                    sys.exit(0)
                elif rc == 1:
                    # edit
                    anaconda.intf.editRepoWindow(anaconda, repo)
                elif rc == 2:
                    # retry, but only if button is present
                    continue
                else:
                    # continue, but only if button is present
                    self.ayum.repos.delete(repo.id)
                    break

            # if we're in kickstart the repo may have been deleted just above
            try:
                self.ayum.repos.getRepo(repo.id)
            except RepoError:
                log.debug("repo %s has been removed" % (repo.id,))
                continue

            repo.setFailureObj(self.ayum.urlgrabberFailureCB)
            repo.setMirrorFailureObj((self.ayum.mirrorFailureCB, (),
                                     {"repo": repo.id}))

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
            log.info("no groups missing")
            return
        c = yum.comps.Category()
        c.name = _("Uncategorized")
        c._groups = grps
        c.categoryid = "uncategorized"
        self.ayum.comps._categories[c.categoryid] = c

    def getDefaultGroups(self, anaconda):
        langs = anaconda.id.instLanguage.getCurrentLangSearchList()
        rc = map(lambda x: x.groupid,
                 filter(lambda x: x.default, self.ayum.comps.groups))
        for g in self.ayum.comps.groups:
            if g.langonly in langs:
                rc.append(g.groupid)
        return rc

    def resetPackageSelections(self):
        """Reset the package selection to an empty state."""
        for txmbr in self.ayum.tsInfo:
            self.ayum.tsInfo.remove(txmbr.pkgtup)

    def selectModulePackages(self, anaconda, kernelPkgName):
        (base, sep, ext) = kernelPkgName.partition("-")

        for (path, name) in anaconda.id.extraModules:
            if ext != "":
                moduleProvides = "kmod-%s-%s" % (name, ext)
            else:
                moduleProvides = "%s-kmod" % name

            pkgs = self.ayum.returnPackagesByDep(moduleProvides)

            if not pkgs:
                log.warning("Didn't find any package providing module %s" % name)

            for pkg in pkgs:
                if ext == "" and pkg.name == "kmod"+name:
                    log.info("selecting package %s for module %s" % (pkg.name, name))
                    self.ayum.install(po=pkg)
                elif ext != "" and pkg.name.find("-"+ext) != -1:
                    log.info("selecting package %s for module %s" % (pkg.name, name))
                    self.ayum.install(po=pkg)
                else:
                    continue

    def selectBestKernel(self, anaconda):
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

        # FIXME: this is a bit of a hack.  we shouldn't hard-code and
        # instead check by provides.  but alas.
        for k in ("kernel", "kernel-smp", "kernel-PAE"):
            if len(self.ayum.tsInfo.matchNaevr(name=k)) > 0:
                self.selectModulePackages(anaconda, k)
                foundkernel = True

        if not foundkernel and (isys.smpAvailable() or isys.htavailable()):
            try:
                ksmp = getBestKernelByArch("kernel-smp", self.ayum)
            except PackageSackError:
                ksmp = None
                log.debug("no kernel-smp package")

            if ksmp and ksmp.returnSimple("arch") == kpkg.returnSimple("arch"):
                foundkernel = True
                log.info("selected kernel-smp package for kernel")
                self.ayum.install(po=ksmp)
                self.selectModulePackages(anaconda, ksmp.name)

                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-smp-devel")
                    self.selectPackage("kernel-smp-devel.%s" % (kpkg.arch,))

        if not foundkernel and isys.isPaeAvailable():
            try:
                kpae = getBestKernelByArch("kernel-PAE", self.ayum)
            except PackageSackError:
                kpae = None
                log.debug("no kernel-PAE package")

            if kpae and kpae.returnSimple("arch") == kpkg.returnSimple("arch"):
                foundkernel = True
                log.info("select kernel-PAE package for kernel")
                self.ayum.install(po=kpae)
                self.selectModulePackages(anaconda, kpae.name)

                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-PAE-devel")
                    self.selectPackage("kernel-PAE-devel.%s" % (kpkg.arch,))

        if not foundkernel:
            log.info("selected kernel package for kernel")
            self.ayum.install(po=kpkg)
            self.selectModulePackages(anaconda, kpkg.name)

            if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                log.debug("selecting kernel-devel")
                self.selectPackage("kernel-devel.%s" % (kpkg.arch,))

    def selectBootloader(self):
        if iutil.isX86():
            self.selectPackage("grub")
        elif iutil.isS390():
            self.selectPackage("s390utils")
        elif iutil.isPPC():
            self.selectPackage("yaboot")
        # XXX this needs to become grub, and we need an upgrade path...
        elif iutil.isIA64():
            self.selectPackage("elilo")

    def selectFSPackages(self, fsset, diskset):
        for entry in fsset.entries:
            map(self.selectPackage, entry.fsystem.getNeededPackages())
            if entry.device.crypto:
                self.selectPackage("cryptsetup-luks")

        for disk in diskset.disks.keys():
            if isys.driveIsIscsi(disk):
                log.info("ensuring iscsi is installed")
                self.selectPackage("iscsi-initiator-utils")
                break

        if diskset.__class__.mpList:
            log.info("ensuring device-mapper-multipath is installed")
            self.selectPackage("device-mapper-multipath")
        if diskset.__class__.dmList:
            log.info("ensuring dmraid is installed")
            self.selectPackage("dmraid")


    # anaconda requires several programs on the installed system to complete
    # installation, but we have no guarantees that some of these will be
    # installed (they could have been removed in kickstart).  So we'll force
    # it.
    def selectAnacondaNeeds(self):
        for pkg in ['authconfig', 'chkconfig', 'mkinitrd', 'rhpl',
                    'system-config-firewall-tui']:
            self.selectPackage(pkg)

    def doPostSelection(self, anaconda):
        # Only solve dependencies on the way through the installer, not the way back.
        if anaconda.dir == DISPATCH_BACK:
            return

        dscb = YumDepSolveProgress(anaconda.intf, self.ayum)
        self.ayum.dsCallback = dscb

        # do some sanity checks for kernel and bootloader
        self.selectBestKernel(anaconda)
        self.selectBootloader()
        self.selectFSPackages(anaconda.id.fsset, anaconda.id.diskset)

        self.selectAnacondaNeeds()

        if anaconda.id.getUpgrade():
            self.ayum.update()

        try:
            while 1:
                try:
                    (code, msgs) = self.ayum.buildTransaction()
                except RepoError, e:
                    buttons = [_("_Exit installer"), _("_Retry")]
                else:
                    break

                # FIXME: would be nice to be able to recover here
                rc = anaconda.intf.messageWindow(_("Error"),
                               _("Unable to read package metadata. This may be "
                                 "due to a missing repodata directory.  Please "
                                 "ensure that your install tree has been "
                                 "correctly generated.\n\n%s" % e),
                                 type="custom", custom_icon="error",
                                 custom_buttons=buttons)
                if rc == 0:
                    sys.exit(0)
                else:
                    continue

            (self.dlpkgs, self.totalSize, self.totalFiles)  = self.ayum.getDownloadPkgs()

            if not anaconda.id.getUpgrade():
                usrPart = anaconda.id.partitions.getRequestByMountPoint("/usr")
                if usrPart is not None:
                    largePart = usrPart
                else:
                    largePart = anaconda.id.partitions.getRequestByMountPoint("/")

                if largePart and \
                   largePart.getActualSize(anaconda.id.partitions, anaconda.id.diskset) < self.totalSize / 1024:
                    rc = anaconda.intf.messageWindow(_("Error"),
                                            _("Your selected packages require %d MB "
                                              "of free space for installation, but "
                                              "you do not have enough available.  "
                                              "You can change your selections or "
                                              "exit the installer." % (self.totalSize / 1024)),
                                            type="custom", custom_icon="error",
                                            custom_buttons=[_("_Back"), _("_Exit installer")])

                    if rc == 1:
                        sys.exit(1)
                    else:
                        self.ayum._undoDepInstalls()
                        return DISPATCH_BACK
        finally:
            dscb.pop()

        if anaconda.mediaDevice and not anaconda.isKickstart:
           rc = presentRequiredMediaMessage(anaconda)
           if rc == 0:
               rc2 = anaconda.intf.messageWindow(_("Reboot?"),
                                       _("The system will be rebooted now."),
                                       type="custom", custom_icon="warning",
                                       custom_buttons=[_("_Back"), _("_Reboot")])
               if rc2 == 1:
                   sys.exit(0)
               else:
                   return DISPATCH_BACK
           elif rc == 1: # they asked to go back
               return DISPATCH_BACK

        self.ayum.dsCallback = None

    def doPreInstall(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            for d in ("/selinux", "/dev"):
                try:
                    isys.umount(anaconda.rootPath + d, removeDir = 0)
                except Exception, e:
                    log.error("unable to unmount %s: %s" %(d, e))
            return

            if flags.test:
                return

        # shorthand
        upgrade = anaconda.id.getUpgrade()

        if upgrade:
            # An old mtab can cause confusion (esp if loop devices are
            # in it).  Be extra special careful and delete any mtab first,
            # in case the user has done something funny like make it into
            # a symlink.
            if os.access(anaconda.rootPath + "/etc/mtab", os.F_OK):
                os.remove(anaconda.rootPath + "/etc/mtab")

            f = open(anaconda.rootPath + "/etc/mtab", "w+")
            f.close()

            # we really started writing modprobe.conf out before things were
            # all completely ready.  so now we need to nuke old modprobe.conf's
            # if you're upgrading from a 2.4 dist so that we can get the
            # transition right
            if (os.path.exists(anaconda.rootPath + "/etc/modules.conf") and
                os.path.exists(anaconda.rootPath + "/etc/modprobe.conf") and
                not os.path.exists(anaconda.rootPath + "/etc/modprobe.conf.anacbak")):
                log.info("renaming old modprobe.conf -> modprobe.conf.anacbak")
                os.rename(anaconda.rootPath + "/etc/modprobe.conf",
                          anaconda.rootPath + "/etc/modprobe.conf.anacbak")

        dirList = ['/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev', '/etc',
                   '/etc/sysconfig', '/etc/sysconfig/network-scripts',
                   '/etc/X11', '/root', '/var/tmp', '/etc/rpm', '/var/cache',
                   '/var/cache/yum', '/etc/modprobe.d']

        # If there are any protected partitions we want to mount, create their
        # mount points now.
        protected = anaconda.id.partitions.protectedPartitions()
        if protected:
            for protectedDev in protected:
                request = anaconda.id.partitions.getRequestByDeviceName(protectedDev)
                if request and request.mountpoint:
                    dirList.append(request.mountpoint)

        for i in dirList:
            try:
                os.mkdir(anaconda.rootPath + i)
            except os.error, (errno, msg):
                pass
#            log.error("Error making directory %s: %s" % (i, msg))

        self.initLog(anaconda.id, anaconda.rootPath)

        if flags.setupFilesystems:
            # setup /etc/rpm/platform for the post-install environment
            iutil.writeRpmPlatform(anaconda.rootPath)
            
            try:
                # FIXME: making the /var/lib/rpm symlink here is a hack to
                # workaround db->close() errors from rpm
                iutil.mkdirChain("/var/lib")
                for path in ("/var/tmp", "/var/lib/rpm"):
                    if os.path.exists(path) and not os.path.islink(path):
                        shutil.rmtree(path)
                    if not os.path.islink(path):
                        os.symlink("%s/%s" %(anaconda.rootPath, path), "%s" %(path,))
                    else:
                        log.warning("%s already exists as a symlink to %s" %(path, os.readlink(path),))
            except Exception, e:
                # how this could happen isn't entirely clear; log it in case
                # it does and causes problems later
                log.error("error creating symlink, continuing anyway: %s" %(e,))

            # SELinux hackery (#121369)
            if flags.selinux:
                try:
                    os.mkdir(anaconda.rootPath + "/selinux")
                except Exception, e:
                    pass
                try:
                    isys.mount("/selinux", anaconda.rootPath + "/selinux", "selinuxfs")
                except Exception, e:
                    log.error("error mounting selinuxfs: %s" %(e,))

            # we need to have a /dev during install and now that udev is
            # handling /dev, it gets to be more fun.  so just bind mount the
            # installer /dev
            log.warning("no dev package, going to bind mount /dev")
            isys.mount("/dev", "%s/dev" %(anaconda.rootPath,), bindMount = 1)
            if not upgrade:
                anaconda.id.fsset.mkDevRoot(anaconda.rootPath)

        # write out the fstab
        if not upgrade:
            anaconda.id.fsset.write(anaconda.rootPath)
            # rootpath mode doesn't have this file around
            if os.access("/etc/modprobe.d/anaconda", os.R_OK):
                shutil.copyfile("/etc/modprobe.d/anaconda", 
                                anaconda.rootPath + "/etc/modprobe.d/anaconda")
            anaconda.id.network.write(instPath=anaconda.rootPath, anaconda=anaconda)
            anaconda.id.iscsi.write(anaconda.rootPath, anaconda)
            anaconda.id.zfcp.write(anaconda.rootPath)
            if not anaconda.id.isHeadless:
                anaconda.id.keyboard.write(anaconda.rootPath)

        # make a /etc/mtab so mkinitrd can handle certain hw (usb) correctly
        f = open(anaconda.rootPath + "/etc/mtab", "w+")
        f.write(anaconda.id.fsset.mtab())
        f.close()

    def checkSupportedUpgrade(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            return
        self._checkUpgradeVersion(anaconda)
        self._checkUpgradeArch(anaconda)

    def _resetRpmDb(self, rootPath):
        for rpmfile in glob.glob("%s/var/lib/rpm/__db.*" % rootPath):
            try:
                os.unlink(rpmfile)
            except Exception, e:
                log.debug("error %s removing file: %s" %(e,rpmfile))

    def _checkUpgradeVersion(self, anaconda):
        # Figure out current version for upgrade nag and for determining weird
        # upgrade cases
        supportedUpgradeVersion = -1
        for pkgtup in self.ayum.rpmdb.whatProvides('redhat-release', None, None):
            n, a, e, v, r = pkgtup
            if supportedUpgradeVersion <= 0:
                val = rpmUtils.miscutils.compareEVR((None, '3', '1'),
                                                    (e, v,r))
                if val > 0:
                    supportedUpgradeVersion = 0
                else:
                    supportedUpgradeVersion = 1
                    break

        if productName.find("Red Hat Enterprise Linux") == -1:
            supportedUpgradeVersion = 1

        if supportedUpgradeVersion == 0:
            rc = anaconda.intf.messageWindow(_("Warning"),
                                    _("You appear to be upgrading from a system "
                                      "which is too old to upgrade to this "
                                      "version of %s.  Are you sure you wish to "
                                      "continue the upgrade "
                                      "process?") %(productName,),
                                    type = "yesno")
            if rc == 0:
                self._resetRpmDb(anaconda.rootPath)
                sys.exit(0)

    def _checkUpgradeArch(self, anaconda):
        # get the arch of the initscripts package
        pkgs = self.ayum.pkgSack.returnNewestByName('initscripts')
        if len(pkgs) == 0:
            log.info("no packages named initscripts")
            return
        pkgs = self.ayum.bestPackagesFromList(pkgs)
        if len(pkgs) == 0:
            log.info("no best package")
            return
        myarch = pkgs[0].arch

        log.info("initscripts is arch: %s" %(myarch,))
        for po in self.ayum.rpmdb.getProvides('initscripts'):
            log.info("po.arch is arch: %s" %(po.arch,))
            if po.arch != myarch:
                rc = anaconda.intf.messageWindow(_("Warning"),
                                        _("The arch of the release of %s you "
                                          "are upgrading to appears to be %s "
                                          "which does not match your previously "
                                          "installed arch of %s.  This is likely "
                                          "to not succeed.  Are you sure you "
                                          "wish to continue the upgrade process?")
                                        %(productName, myarch, po.arch),
                                        type="yesno")
                if rc == 0:
                    self._resetRpmDb(anaconda.rootPath)
                    sys.exit(0)
                else:
                    log.warning("upgrade between possibly incompatible "
                                "arches %s -> %s" %(po.arch, myarch))
                    break

    def doInstall(self, anaconda):
        log.info("Preparing to install packages")
        if flags.test:
            log.info("Test mode - not performing install")
            return

        if not anaconda.id.upgrade:
            rpm.addMacro("__dbi_htconfig",
                         "hash nofsync %{__dbi_other} %{__dbi_perms}")

        if anaconda.isKickstart and anaconda.id.ksdata.packages.excludeDocs:
            rpm.addMacro("_excludedocs", "1")

        cb = AnacondaCallback(self.ayum, anaconda,
                              self.instLog, self.modeText)
        cb.setSizes(len(self.dlpkgs), self.totalSize, self.totalFiles)

        rc = self.ayum.run(self.instLog, cb, anaconda.intf, anaconda.id)

        if cb.initWindow is not None:
            cb.initWindow.pop()

        self.instLog.close ()

        anaconda.id.instProgress = None

        if rc == DISPATCH_BACK:
            return DISPATCH_BACK

    def doPostInstall(self, anaconda):
        if flags.test:
            return

        if anaconda.id.getUpgrade():
            w = anaconda.intf.waitWindow(_("Post Upgrade"),
                                    _("Performing post upgrade configuration..."))
        else:
            w = anaconda.intf.waitWindow(_("Post Install"),
                                    _("Performing post install configuration..."))

        if len(self.ayum.tsInfo.matchNaevr(name='rhgb')) > 0:
            anaconda.id.bootloader.args.append("rhgb quiet")
        elif len(self.ayum.tsInfo.matchNaevr(name='plymouth')) > 0:
            anaconda.id.bootloader.args.append("rhgb quiet")

        for tsmbr in self.ayum.tsInfo.matchNaevr(name='gdm') + self.ayum.tsInfo.matchNaevr(name='kdebase-workspace'):
            if anaconda.id.displayMode == 'g' and not flags.usevnc:
                anaconda.id.desktop.setDefaultRunLevel(5)
                break

        for repo in self.ayum.repos.listEnabled():
            repo.dirCleanup()

        # expire yum caches on upgrade
        if anaconda.id.getUpgrade() and os.path.exists("%s/var/cache/yum" %(anaconda.rootPath,)):
            log.info("Expiring yum caches")
            try:
                iutil.execWithRedirect("yum", ["clean", "all"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       searchPath = 1,
                                       root = anaconda.rootPath)
            except:
                pass

        # nuke preupgrade
        if flags.cmdline.has_key("preupgrade") and anaconda.id.getUpgrade() and os.path.exists("%s/var/cache/yum/anaconda-upgrade" %(anaconda.rootPath,)):
            try:
                shutil.rmtree("%s/var/cache/yum/anaconda-upgrade" %(anaconda.rootPath,))
            except:
                pass

        # XXX: write proper lvm config

        AnacondaBackend.doPostInstall(self, anaconda)
        w.pop()

    def kernelVersionList(self, rootPath="/"):
        # FIXME: using rpm here is a little lame, but otherwise, we'd
        # be pulling in filelists
        return packages.rpmKernelVersionList(rootPath)

    def __getGroupId(self, group):
        """Get the groupid for the given name (english or translated)."""
        for g in self.ayum.comps.groups:
            if group == g.name:
                return g.groupid
            for trans in g.translated_name.values():
                if group == trans:
                    return g.groupid

    def isGroupSelected(self, group):
        try:
            grp = self.ayum.comps.return_group(group)
            if grp.selected: return True
        except yum.Errors.GroupsError, e:
            pass
        return False

    def selectGroup(self, group, *args):
        if not self.ayum.comps.has_group(group):
            log.debug("no such group %s" % group)
            raise NoSuchGroup, group

        types = ["mandatory"]

        if args:
            if args[0][0]:
                types.append("default")
            if args[0][1]:
                types.append("optional")
        else:
            types.append("default")

        try:
            mbrs = self.ayum.selectGroup(group, group_package_types=types)
            if len(mbrs) == 0 and self.isGroupSelected(group):
                return
        except yum.Errors.GroupsError, e:
            # try to find out if it's the name or translated name
            gid = self.__getGroupId(group)
            if gid is not None:
                mbrs = self.ayum.selectGroup(gid, group_package_types=types)
                if len(mbrs) == 0 and self.isGroupSelected(gid):
                    return
            else:
                log.debug("no such group %s" %(group,))
                raise NoSuchGroup, group

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
        try:
            mbrs = self.ayum.install(pattern=pkg)
            return len(mbrs)
        except yum.Errors.InstallError:
            log.debug("no package matching %s" %(pkg,))
            return 0

    def deselectPackage(self, pkg, *args):
        sp = pkg.rsplit(".", 2)
        txmbrs = []
        if len(sp) == 2:
            txmbrs = self.ayum.tsInfo.matchNaevr(name=sp[0], arch=sp[1])

        if len(txmbrs) == 0:
            exact, match, unmatch = yum.packages.parsePackages(self.ayum.pkgSack.returnPackages(), [pkg], casematch=1)
            for p in exact + match:
                txmbrs.append(p)

        if len(txmbrs) > 0:
            for x in txmbrs:
                self.ayum.tsInfo.remove(x.pkgtup)
                # we also need to remove from the conditionals
                # dict so that things don't get pulled back in as a result
                # of them.  yes, this is ugly.  conditionals should die.
                for req, pkgs in self.ayum.tsInfo.conditionals.iteritems():
                    if x in pkgs:
                        pkgs.remove(x)
                        self.ayum.tsInfo.conditionals[req] = pkgs
            return len(txmbrs)
        else:
            log.debug("no such package %s to remove" %(pkg,))
            return 0

    def groupListExists(self, grps):
        """Returns bool of whether all of the given groups exist."""
        for gid in grps:
            g = self.ayum.comps.return_group(gid)
            if not g:
                return False
        return True

    def groupListDefault(self, grps):
        """Returns bool of whether all of the given groups are default"""
        rc = False
        for gid in grps:
            g = self.ayum.comps.return_group(gid)
            if g and not g.default:
                return False
            elif g:
                rc = True
        return rc

    def writeKS(self, f):
        for repo in self.ayum.repos.listEnabled():
            if repo.name == "Installation Repo":
                continue

            line = "repo --name=\"%s\" " % (repo.name or repo.repoid)

            if repo.baseurl:
                line += " --baseurl=%s\n" % repo.baseurl[0]
            else:
                line += " --mirrorlist=%s\n" % repo.mirrorlist

            f.write(line)

    def writePackagesKS(self, f, anaconda):
        if anaconda.isKickstart:
            f.write(anaconda.id.ksdata.packages.__str__())
            return

        groups = []
        installed = []
        removed = []

        # Faster to grab all the package names up front rather than call
        # searchNevra in the loop below.
        allPkgNames = map(lambda pkg: pkg.name, self.ayum.pkgSack.returnPackages())
        allPkgNames.sort()

        # On CD/DVD installs, we have one transaction per CD and will end up
        # checking allPkgNames against a very short list of packages.  So we
        # have to reset to media #0, which is an all packages transaction.
        old = self.ayum.tsInfo.curmedia
        self.ayum.tsInfo.curmedia = 0

        self.ayum.tsInfo.makelists()
        txmbrNames = map (lambda x: x.name, self.ayum.tsInfo.getMembers())

        self.ayum.tsInfo.curmedia = old

        if len(self.ayum.tsInfo.instgroups) == 0 and len(txmbrNames) == 0:
            return

        f.write("\n%packages\n")

        for grp in filter(lambda x: x.selected, self.ayum.comps.groups):
            groups.append(grp.groupid)

            defaults = grp.default_packages.keys() + grp.mandatory_packages.keys()
            optionals = grp.optional_packages.keys()

            for pkg in filter(lambda x: x in defaults and (not x in txmbrNames and x in allPkgNames), grp.packages):
                removed.append(pkg)

            for pkg in filter(lambda x: x in txmbrNames, optionals):
                installed.append(pkg)

        for grp in groups:
            f.write("@%s\n" % grp)

        for pkg in installed:
            f.write("%s\n" % pkg)

        for pkg in removed:
            f.write("-%s\n" % pkg)

    def writeConfiguration(self):
        return

    def getRequiredMedia(self):
        return self.ayum.tsInfo.reqmedia.keys()

class DownloadHeaderProgress:
    def __init__(self, intf, ayum=None):
        window = intf.progressWindow(_("Install Starting"),
                                     _("Starting install process.  This may take several minutes..."),
                                     1.0, 0.01)
        self.window = window
        self.ayum = ayum
        self.current = self.loopstart = 0
        self.incr = 1

        if self.ayum is not None and self.ayum.tsInfo is not None:
            self.numpkgs = len(self.ayum.tsInfo.getMembers())
            if self.numpkgs != 0:
                self.incr = (1.0 / self.numpkgs) * (1.0 - self.loopstart)
        else:
            self.numpkgs = 0

        self.refresh()

        self.restartLoop = self.downloadHeader = self.transactionPopulation = self.refresh
        self.procReq = self.procConflict = self.unresolved = self.noop

    def noop(self, *args, **kwargs):
        pass

    def pkgAdded(self, *args):
        if self.numpkgs:
            self.set(self.current + self.incr)

    def pop(self):
        self.window.pop()

    def refresh(self, *args):
        self.window.refresh()

    def set(self, value):
        self.current = value
        self.window.set(self.current)

class YumDepSolveProgress:
    def __init__(self, intf, ayum = None):
        window = intf.progressWindow(_("Dependency Check"),
                                     _("Checking dependencies in packages selected for installation..."),
                                     1.0, 0.01)
        self.window = window

        self.numpkgs = None
        self.loopstart = None
        self.incr = None
        self.ayum = ayum
        self.current = 0

        self.restartLoop = self.downloadHeader = self.transactionPopulation = self.refresh
        self.procReq = self.procConflict = self.unresolved = self.noop

    def tscheck(self, num = None):
        self.refresh()
        if num is None and self.ayum is not None and self.ayum.tsInfo is not None:
            num = len(self.ayum.tsInfo.getMembers())

        if num:
            self.numpkgs = num
            self.loopstart = self.current
            self.incr = (1.0 / num) * ((1.0 - self.loopstart) / 2)

    def pkgAdded(self, *args):
        if self.numpkgs:
            self.set(self.current + self.incr)

    def noop(self, *args, **kwargs):
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
