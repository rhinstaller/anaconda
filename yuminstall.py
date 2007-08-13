#
# Copyright (c) 2005-2007 Red Hat, Inc.
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
import os.path
import shutil
import timer
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
import rhpl
from yum.constants import *
from yum.Errors import RepoError, YumBaseError, PackageSackError
from yum.yumRepo import YumRepository
from backend import AnacondaBackend
from product import productName, productStamp
from sortedtransaction import SplitMediaTransactionData
from constants import *
from rhpl.translate import _

# specspo stuff
rpm.addMacro("_i18ndomains", "redhat-dist")

import logging
log = logging.getLogger("anaconda")

import urlparse
urlparse.uses_fragment.append('media')


import iutil
import isys

import whiteout

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

    def __init__(self, ayum, anaconda, method, instLog, modeText):
        self.method = method
        self.repos = ayum.repos
        self.ts = ayum.ts
        self.ayum = ayum
        
        self.messageWindow = anaconda.intf.messageWindow
        self.waitWindow = anaconda.intf.waitWindow        
        self.progress = anaconda.id.instProgress
        self.progressWindowClass = anaconda.intf.progressWindow

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
        # first time here means we should pop the window telling
        # user to wait until we get here
        if self.initWindow is not None:
            self.initWindow.pop()
            self.initWindow = None

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

            s = str(_("<b>Installing %s</b> (%s)\n") %(po, size_string(hdr['size'])))
            s += (hdr['summary'] or "")
            self.progress.set_label(s)

            nvra = str("%s" %(po,))
            self.instLog.write(self.modeText % (nvra,))

            self.instLog.flush()
            self.openfile = None

            while self.openfile is None:
                try:
                    fn = repo.getPackage(po)

                    f = open(fn, 'r')
                    self.openfile = f
                except yum.Errors.RepoError, e:
                    if repo.nomoremirrors:
                        self.ayum._handleFailure(po)
                        repo.nomoremirrors = False
                    continue
            self.inProgressPo = po

            return self.openfile.fileno()

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            (hdr, rpmloc) = h

            fn = self.openfile.name
            self.openfile.close()
            self.openfile = None

            repo = self.repos.getRepo(self.inProgressPo.repoid)
            if len(filter(lambda u: u.startswith("file:"), repo.baseurl)) == 0:
                try:
                    os.remove(fn)
                except OSError, e:
                    log.debug("unable to remove file %s" %(e,))
            self.inProgressPo = None

            self.donepkgs += 1
            self.doneSize += hdr['size']/1024.0
            self.doneFiles += len(hdr[rpm.RPMTAG_BASENAMES])

            self.progress.set_label("")
            self.progress.set_text(_("%s of %s packages completed")
                                   %(self.donepkgs, self.numpkgs))
            self.progress.set_fraction(float(self.doneSize / self.totalSize))
            self.progress.processEvents()

        # FIXME: we should probably integrate this into the progress bar
        # and actually show progress on cleanups.....
        elif what in (rpm.RPMCALLBACK_UNINST_START,
                      rpm.RPMCALLBACK_UNINST_STOP):
            if self.initWindow is None:
                self.initWindow = self.waitWindow(_("Finishing upgrade"),
                                                  _("Finishing upgrade process.  This may take a little while..."))
            else:
                self.initWindow.refresh()

        else:
            pass

        self.progress.processEvents()

class AnacondaYumRepo(YumRepository):
    def __init__( self, uri=None, mirrorlist=None,
                  repoid='anaconda%s' % productStamp,
                  root = "/mnt/sysimage/", method=None, addon=True):
        YumRepository.__init__(self, repoid)
        self.method = method
        self.nomoremirrors = False
        conf = yum.config.RepoConf()
        for k, v in conf.iteritems():
            if v or not self.getAttribute(k):
                self.setAttribute(k, v)
        self.gpgcheck = False
        #self.gpgkey = "%s/RPM-GPG-KEY-fedora" % (method, )
        self.keepalive = False
        self.addon = addon

        if type(uri) == types.ListType:
            self.baseurl = uri
        else:
            self.baseurl = [ uri ]

        if mirrorlist:
            self.mirrorlist = mirrorlist

        self.setAttribute('cachedir', '/tmp/cache/')
        self.setAttribute('pkgdir', root)
        self.setAttribute('hdrdir', '/tmp/cache/headers')

    def dirSetup(self):
        YumRepository.dirSetup(self)
        if not os.path.isdir(self.hdrdir):
            os.makedirs(self.hdrdir, mode=0755)

    #XXX: FIXME duplicated from YumRepository due to namespacing
    def __headersListFromDict(self):
        """Convert our dict of headers to a list of 2-tuples for urlgrabber."""
        headers = []

        keys = self.http_headers.keys()
        for key in keys:
            headers.append((key, self.http_headers[key]))

        return headers

    # adds handling of "no more mirrors" exception
    def _getFile(self, url=None, relative=None, local=None, start=None, end=None,
            copy_local=0, checkfunc=None, text=None, reget='simple', cache=True):
        """retrieve file from the mirrorgroup for the repo
           relative to local, optionally get range from
           start to end, also optionally retrieve from a specific baseurl"""

        # if local or relative is None: raise an exception b/c that shouldn't happen
        # if url is not None - then do a grab from the complete url - not through
        # the mirror, raise errors as need be
        # if url is None do a grab via the mirror group/grab for the repo
        # return the path to the local file

        # Turn our dict into a list of 2-tuples
        headers = self.__headersListFromDict()

        # We will always prefer to send no-cache.
        if not (cache or self.http_headers.has_key('Pragma')):
            headers.append(('Pragma', 'no-cache'))

        headers = tuple(headers)

        if local is None or relative is None:
            raise yum.Errors.RepoError, \
                  "get request for Repo %s, gave no source or dest" % self.id

        if self.cache == 1:
            if os.path.exists(local): # FIXME - we should figure out a way
                return local          # to run the checkfunc from here

            else: # ain't there - raise
                raise yum.Errors.RepoError, \
                    "Caching enabled but no local cache of %s from %s" % (local,
                           self)

        if url:
            (scheme, netloc, path, query, fragid) = urlparse.urlsplit(url)

        if url is not None and scheme != "media":
            ug = URLGrabber(keepalive = False,
                            bandwidth = self.bandwidth,
                            retry = self.retries,
                            throttle = self.throttle,
                            progres_obj = self.callback,
                            copy_local = copy_local,
                            reget = reget,
                            proxies = self.proxy_dict,
                            failure_callback = self.failure_obj,
                            interrupt_callback=self.interrupt_callback,
                            timeout=self.timeout,
                            checkfunc=checkfunc,
                            http_headers=headers,
                            )

            remote = url + '/' + relative

            try:
                result = ug.urlgrab(remote, local,
                                    text=text,
                                    range=(start, end),
                                    )
            except URLGrabError, e:
                if e.errno == 256: # no more mirrors
                    self.nomoremirrors = True
                raise yum.Errors.RepoError, \
                    "failed to retrieve %s from %s\nerror was %s" % (relative, self.id, e)

        else:
            try:
                result = self.grab.urlgrab(relative, local,
                                           keepalive = False,
                                           text = text,
                                           range = (start, end),
                                           copy_local=copy_local,
                                           reget = reget,
                                           checkfunc=checkfunc,
                                           http_headers=headers,
                                           )
            except URLGrabError, e:
                if e.errno == 256: # no more mirrors
                    self.nomoremirrors = True
                    
                raise yum.Errors.RepoError, "failure: %s from %s: %s" % (relative, self.id, e)

        return result

class YumSorter(yum.YumBase):
    
    def __init__(self):
        yum.YumBase.__init__(self)
        self.deps = {}
        self.path = []
        self.loops = []

    def _undoDepInstalls(self):
        # clean up after ourselves in the case of failures
        for txmbr in self.tsInfo:
            if txmbr.isDep:
                self.tsInfo.remove(txmbr.pkgtup)

    def _transactionDataFactory(self):
        return SplitMediaTransactionData()
  
class AnacondaYum(YumSorter):
    def __init__(self, anaconda):
        YumSorter.__init__(self)
        self.anaconda = anaconda
        self.method = anaconda.method
        self.prevmedia = None
        self.doConfigSetup(root=anaconda.rootPath)
        self.conf.installonlypkgs = []
        self.macros = {}
        if flags.selinux:
            for directory in ("/tmp/updates", "/mnt/source/RHupdates",
                        "/etc/selinux/targeted/contexts/files",
                        "/etc/security/selinux/src/policy/file_contexts",
                        "/etc/security/selinux"):
                fn = "%s/file_contexts" %(directory,)
                if os.access(fn, os.R_OK):
                    break
            self.macros["__file_context_path"] = fn
        else:
            self.macros["__file_context_path"]  = "%{nil}"

        self.macros["_dependency_whiteout"] = whiteout.whiteout

        self.updates = []
        self.localPackages = []

    def doConfigSetup(self, fn='/etc/yum.conf', root='/'):
        self.conf = yum.config.YumConf()
        self.conf.installroot = root
        self.conf.reposdir=["/tmp/repos.d"]
        self.conf.logfile="/tmp/yum.log"
        self.conf.obsoletes=True
        self.conf.cache=0
        self.conf.cachedir = '/tmp/cache/'
        self.conf.metadata_expire = 0

        # set up logging to log to our logs
        ylog = logging.getLogger("yum")
        map(lambda x: ylog.addHandler(x), log.handlers)

        # add default repos
        for (name, uri) in self.anaconda.id.instClass.getPackagePaths(self.method.getMethodUri()).items():
            repo = AnacondaYumRepo(uri, addon=False,
                                   repoid="anaconda-%s-%s" %(name,
                                                             productStamp),
                                   root = root, method=self.method)
            repo.enable()
            self.repos.add(repo)

        extraRepos = []

        # add some additional not enabled by default repos.
        # FIXME: this is a hack and should probably be integrated
        # with the above
        for (name, (uri, mirror)) in self.anaconda.id.instClass.repos.items():
            rid = name.replace(" ", "")
            repo = AnacondaYumRepo(uri=uri, mirrorlist=mirror, repoid=rid,
                                   root=root, addon=False)
            repo.name = name
            repo.disable()
            extraRepos.append(repo)

        if self.anaconda.id.extraModules:
            for d in glob.glob("/tmp/ramfs/DD-*/rpms"):
                dirname = os.path.basename(os.path.dirname(d))
                rid = "anaconda-%s" % dirname

                repo = AnacondaYumRepo(uri="file:///%s" % d, repoid=rid,
                                       root=root, addon=False)
                repo.name = "Driver Disk %s" % dirname.split("-")[1]
                repo.enable()
                extraRepos.append(repo)

        if self.anaconda.isKickstart:
            for ksrepo in self.anaconda.id.ksdata.repo.repoList:
                repo = AnacondaYumRepo(uri=ksrepo.baseurl,
                                       mirrorlist=ksrepo.mirrorlist,
                                       repoid=ksrepo.name)
                repo.name = name
                repo.enable()
                extraRepos.append(repo)

        for repo in extraRepos:
            try:
                self.repos.add(repo)
                log.info("added repository %s with source URL %s" % (repo.name, repo.baseurl or repo.mirrorlist))
            except yum.Errors.DuplicateRepoError, e:
                log.warning("ignoring duplicate repository %s with source URL %s" % (repo.name, repo.baseurl or repo.mirrorlist))

        self.doPluginSetup(searchpath=["/usr/lib/yum-plugins",
                                       "/tmp/updates/yum-plugins"], 
                           confpath=["/etc/yum/pluginconf.d",
                                     "/tmp/updates/pluginconf.d"])
        self.plugins.run('init')

        self.repos.setCacheDir('/tmp/cache')

    def _handleFailure(self, package):
        pkgFile = os.path.basename(package.returnSimple('relativepath'))
        rc = self.anaconda.intf.messageWindow(_("Error"),
                                    self.method.badPackageError(pkgFile),
                                    type="custom", custom_icon="error",
                                    custom_buttons=[_("Re_boot"), _("_Retry")])

        if rc == 0:
            sys.exit(0)
        else:
            if self.prevmedia:
                self.method.switchMedia(self.prevmedia)

    def mirrorFailureCB (self, obj, *args, **kwargs):
        # This gets called when a mirror fails, but it cannot know whether
        # or not there are other mirrors left to try, since it cannot know
        # which mirror we were on when we started this particular download. 
        # Whenever we have run out of mirrors the grabber's get/open/retrieve
        # method will raise a URLGrabError exception with errno 256.
        grab = self.repos.getRepo(kwargs["repo"]).grab
        log.warning("Failed to get %s from mirror %d/%d" % (obj.url, 
                                                            grab._next + 1,
                                                            len(grab.mirrors)))
        
        if self.method.currentMedia:
            if kwargs.get("tsInfo") and kwargs["tsInfo"].curmedia > 0:
                self.prevmedia = kwargs["tsInfo"].curmedia

            self.method.unmountCD()

    def urlgrabberFailureCB (self, obj, *args, **kwargs):
        log.warning("Try %s/%s for %s failed" % (obj.tries, obj.retry, obj.url))

    # copied from YumBase to insert handling for "no more mirrors" failure
    def downloadHeader(self, po):
        """download a header from a package object.
           output based on callback, raise yum.Errors.YumBaseError on problems"""

        if hasattr(po, 'pkgtype') and po.pkgtype == 'local':
            return
                
        errors = {}
        local =  po.localHdr()
        repo = self.repos.getRepo(po.repoid)
        if os.path.exists(local):
            try:
                result = self.verifyHeader(local, po, raiseError=1)
            except URLGrabError, e:
                # might add a check for length of file - if it is < 
                # required doing a reget
                try:
                    os.unlink(local)
                except OSError, e:
                    pass
            else:
                po.hdrpath = local
                return
        else:
            if self.conf.cache:
                raise yum.Errors.RepoError, \
                'Header not in local cache and caching-only mode enabled. Cannot download %s' % po.hdrpath
        
        if self.dsCallback: self.dsCallback.downloadHeader(po.name)
        
        while 1:
            try:
                checkfunc = (self.verifyHeader, (po, 1), {})
                hdrpath = repo.getHeader(po, checkfunc=checkfunc,
                                         cache=repo.http_caching != 'none')
            except yum.Errors.RepoError, e:
                if repo.nomoremirrors:
                    self._handleFailure(po)
                    repo.nomoremirrors = False
                    continue
                saved_repo_error = e
                try:
                    os.unlink(local)
                except OSError, e:
                    raise yum.Errors.RepoError, saved_repo_error
                else:
                    raise
            else:
                po.hdrpath = hdrpath
                return

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
        if not self.method.splitmethod:
            self.populateTs(keepold=0)
            self.ts.check()
            self.ts.order()
            self._run(instLog, cb, intf)
        else:
            # If we don't have any required media assume single disc
            if self.tsInfo.reqmedia == {}:
                self.tsInfo.reqmedia[0] = None
            mkeys = self.tsInfo.reqmedia.keys()
            mkeys.sort(mediasort)
            for i in mkeys:
                self.tsInfo.curmedia = i
                if i > 0:
                    pkgtup = self.tsInfo.reqmedia[i][0]
                    self.method.switchMedia(i, filename=pkgtup)
                self.populateTs(keepold=0)
                self.ts.check()
                self.ts.order()
                self._run(instLog, cb, intf)

    def _run(self, instLog, cb, intf):
        # set log fd.  FIXME: this is ugly.  see changelog entry from 2005-09-13
        self.ts.ts.scriptFd = instLog.fileno()
        rpm.setLogFile(instLog)

        spaceneeded = {}

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
            uniqueProbs = {}
            for (descr, (type, mount, need)) in probs.value: # FIXME: probs.value???
                log.error("%s: %s" %(probTypes[type], descr))
                if not uniqueProbs.has_key(type) and probTypes.has_key(type):
                    uniqueProbs[type] = probTypes[type]

                if type == rpm.RPMPROB_DISKSPACE:
                    spaceneeded[mount] = need

                log.error("error running transaction: %s" %(descr,))

            if spaceneeded:
                spaceprob = _("You need more space on the following "
                              "file systems:\n")

                for (mount, need) in spaceneeded.items():
                    log.info("(%s, %s)" %(mount, need))

                    if mount.startswith("/mnt/sysimage/"):
                        mount.replace("/mnt/sysimage", "")
                    elif mount.startswith("/mnt/sysimage"):
                        mount = "/" + mount.replace("/mnt/sysimage", "")

                    spaceprob = spaceprob + "%d M on %s\n" % (need / (1024*1024), mount)
            else:
                spaceprob = ""

            probString = ', '.join(uniqueProbs.values()) + "\n\n" + spaceprob
            intf.messageWindow(_("Error running transaction"),
                               _("There was an error running your transaction, "
                                "for the following reason(s): %s")
                               %(probString,),
                               type="custom", custom_icon="error",
                               custom_buttons=[_("Re_boot")])
            sys.exit(1)

    def doMacros(self):
        for (key, val) in self.macros.items():
            rpm.addMacro(key, val)

    def isGroupInstalled(self, grp):
        # FIXME: move down to yum itself.
        # note that this is the simple installer only version that doesn't
        # worry with installed and toremove...
        if grp.selected:
            return True
        return False

    def simpleDBInstalled(self, name):
        # FIXME: this is used in pirut because of slow stuff in yum
        # given that we're on a new system, nothing is ever installed in the
        # rpmdb
        return False

class YumBackend(AnacondaBackend):
    def __init__ (self, method, instPath):
        AnacondaBackend.__init__(self, method, instPath)
        self.supportsPackageSelection = True

    def doInitialSetup(self, anaconda):
        if anaconda.id.getUpgrade():
           # FIXME: make sure that the rpmdb doesn't have stale locks :/
            for rpmfile in ["__db.000", "__db.001", "__db.002", "__db.003"]:
                try:
                    os.unlink("%s/var/lib/rpm/%s" %(anaconda.rootPath, rpmfile))
                except:
                    log.error("failed to unlink /var/lib/rpm/%s" %(rpmfile,))

        iutil.writeRpmPlatform()
        self.ayum = AnacondaYum(anaconda)

    def doGroupSetup(self):
        # FIXME: this is a pretty ugly hack to make it so that we don't lose
        # groups being selected (#237708)
        sel = filter(lambda g: g.selected, self.ayum.comps.get_groups())
        self.ayum.doGroupSetup()
        # now we'll actually reselect groups..
        map(lambda g: self.selectGroup(g.groupid), sel)

        # FIXME: this is a bad hack to remove support for xen on xen (#179387)
        if os.path.exists("/proc/xen"):
            if self.ayum.comps._groups.has_key("virtualization"):
                del self.ayum.comps._groups["virtualization"]

        # FIXME: and another bad hack since our xen kernel is PAE
        if rpmUtils.arch.getBaseArch() == "i386" and "pae" not in iutil.cpuFeatureFlags():
            if self.ayum.comps._groups.has_key("virtualization"):
                del self.ayum.comps._groups["virtualization"]


    def doRepoSetup(self, anaconda, thisrepo = None, fatalerrors = True):
        # We want to call ayum.doRepoSetup one repo at a time so we have
        # some concept of which repo didn't set up correctly.
        repos = []

        # Don't do this if we're being called as a dispatcher step (instead
        # of being called when a repo is added via the UI) and we're going
        # back.
        if thisrepo is None and anaconda.dir == DISPATCH_BACK:
            return

        if thisrepo is not None:
            repos.append(self.ayum.repos.getRepo(thisrepo))
        else:
            repos.extend(self.ayum.repos.listEnabled())

        anaconda.method.switchMedia(1)

        if not os.path.exists("/tmp/cache"):
            iutil.mkdirChain("/tmp/cache/headers")

        self.ayum.doMacros()
        self.ayum.doTsSetup()
        self.ayum.doRpmDBSetup()

        longtasks = ( (self.ayum.doRepoSetup, 4),
                      (self.ayum.doSackSetup, 6) )

        tot = 0
        for t in longtasks:
            tot += t[1]

        for repo in repos:
            if repo.name is None:
                txt = _("Retrieving installation information...")
            else:
                txt = _("Retrieving installation information for %s...")%(repo.name)
            while 1:
                waitwin = YumProgress(anaconda.intf, txt, tot)
                self.ayum.repos.callback = waitwin

                try:
                    for (task, incr) in longtasks:
                        waitwin.set_incr(incr)
                        task(thisrepo = repo.id)
                        waitwin.next_task()
                    waitwin.pop()
                except RepoError, e:
                    if repo.nomoremirrors:
                        buttons = [_("_Abort"), _("_Retry")]
                        repo.nomoremirrors = False
                    else:
                        buttons = [_("_Abort")]

                    if anaconda.isKickstart:
                        buttons.append(_("_Continue"))
                else:
                    break # success

                waitwin.pop()
                if not fatalerrors:
                    raise RepoError, e

                rc = anaconda.intf.messageWindow(_("Error"),
                                   _("Unable to read package metadata. This may be "
                                     "due to a missing repodata directory.  Please "
                                     "ensure that your install tree has been "
                                     "correctly generated.  %s" % e),
                                     type="custom", custom_icon="error",
                                     custom_buttons=buttons)
                if rc == 0:
                    sys.exit(0)
                elif rc == 2:
                    self.ayum.repos.delete(repo.id)
                    break
                else:
                    continue

            # if we're in kickstart the repo may have been deleted just above
            try:
                self.ayum.repos.getRepo(repo.id)
            except RepoError:
                log.debug("repo %s has been removed" % (repo.id,))
                continue

            repo.setFailureObj(self.ayum.urlgrabberFailureCB)
            repo.setMirrorFailureObj((self.ayum.mirrorFailureCB, (),
                                     {"tsInfo":self.ayum.tsInfo, 
                                      "repo": repo.id}))

        while 1:
            try:
                self.doGroupSetup()
            except (yum.Errors.GroupsError, yum.Errors.RepoError):
                buttons = [_("Re_boot")]
                for repo in self.ayum.repos.listEnabled():
                    if repo.nomoremirrors:
                        buttons = [_("Re_boot"), _("_Retry")]
                        repo.nomoremirrors = False
                        break
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

    # XXX: need to check that the version of the module matches the version of
    # the kernel package.
    def selectModulePackages(self, anaconda):
        def inProvides(provides, po):
           return provides in map(lambda p: p[0], po.provides)

        for (path, name) in anaconda.id.extraModules:
            xenProvides = "kmod-%s-xen" % name
            regularProvides = "%s-kmod" % name

            if self.ayum.tsInfo.matchNaevr(name="kernel-xen"):
                moduleProvides = xenProvides
            else:
                moduleProvides = regularProvides

            pkgs = self.ayum.returnPackagesByDep(moduleProvides)

            if not pkgs:
                log.warning("Didn't find any package for module %s" % name)

            for pkg in pkgs:
                # The xen module includes the non-xen provides, so we need to
                # make sure we're not trying to select the xen module on a
                # non-xen kernel.
                if moduleProvides == regularProvides and inProvides(xenProvides, pkg):
                    continue
                else:
                    log.info("selecting %s package for %s module" % (pkg.name, name))
                    self.ayum.install(po=pkg)


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

        # FIXME: this is a bit of a hack.  we shouldn't hard-code and
        # instead check by provides.  but alas.
        for k in ("kernel", "kernel-smp", "kernel-xen0", "kernel-xen"):
            if len(self.ayum.tsInfo.matchNaevr(name=k)) > 0:
                foundkernel = True

        if not foundkernel and os.path.exists("/proc/xen"):
            try:
                kxen = getBestKernelByArch("kernel-xen", self.ayum)
                log.info("selecting kernel-xen package for kernel")
                foundkernel = True
            except PackageSackError:
                kxen = None
                log.debug("no kernel-xen package")
            else:
                self.ayum.install(po = kxen)
                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-xen-devel")
                    self.selectPackage("kernel-xen-devel.%s" % (kxen.arch,))

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
                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-PAE-devel")
                    self.selectPackage("kernel-PAE-devel.%s" % (kpkg.arch,))

        if not foundkernel:
            log.info("selected kernel package for kernel")
            self.ayum.install(po=kpkg)
            if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                log.debug("selecting kernel-devel")
                self.selectPackage("kernel-devel.%s" % (kpkg.arch,))

    def selectBootloader(self):
        if rhpl.getArch() in ("i386", "x86_64"):
            self.selectPackage("grub")
        elif rhpl.getArch() == "s390":
            self.selectPackage("s390utils")
        elif rhpl.getArch() == "ppc":
            self.selectPackage("yaboot")
        elif rhpl.getArch() == "ia64":
            self.selectPackage("elilo")

    def selectFSPackages(self, fsset, diskset):
        for entry in fsset.entries:
            map(self.selectPackage, entry.fsystem.getNeededPackages())

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
                    'system-config-securitylevel-tui']:
            self.selectPackage(pkg)

    def doPostSelection(self, anaconda):
        # Only solve dependencies on the way through the installer, not the way back.
        if anaconda.dir == DISPATCH_BACK:
            return

        dscb = YumDepSolveProgress(anaconda.intf, self.ayum)
        self.ayum.dsCallback = dscb

        # do some sanity checks for kernel and bootloader
        self.selectBestKernel()
        self.selectBootloader()
        self.selectFSPackages(anaconda.id.fsset, anaconda.id.diskset)
        self.selectModulePackages(anaconda)

        self.selectAnacondaNeeds()

        if anaconda.id.getUpgrade():
            from upgrade import upgrade_remove_blacklist
            self.upgradeFindPackages()
            for pkg in upgrade_remove_blacklist:
                pkgarch = None
                pkgnames = None
                if len(pkg) == 1:
                    pkgname = pkg[0]
                elif len(pkg) == 2:
                    pkgname, pkgarch = pkg
                if pkgname is None:
                    continue
                self.ayum.remove(name=pkgname, arch=pkgarch)
            self.ayum.update()

        try:
            while 1:
                try:
                    (code, msgs) = self.ayum.buildTransaction()
                except RepoError, e:
                    buttons = [_("Re_boot")]
                    for repo in self.ayum.repos.listEnabled():
                        if repo.nomoremirrors:
                            buttons = [_("Re_boot"), _("_Retry")]
                            repo.nomoremirrors = False
                            break
                    # FIXME: this message isn't ideal, but it'll do for now
                    rc = anaconda.intf.messageWindow(_("Error"),
                               _("Unable to read package metadata. This may be "
                                 "due to a missing repodata directory.  Please "
                                 "ensure that your install tree has been "
                                 "correctly generated.  %s" % e),
                                 type="custom", custom_icon="error",
                                 custom_buttons=buttons)
                    if rc == 0:
                        sys.exit(0)
                    else:
                        continue
                else:
                    break

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
                

        if self.method.systemMounted (anaconda.id.fsset, anaconda.rootPath):
            anaconda.id.fsset.umountFilesystems(anaconda.rootPath)
            return DISPATCH_BACK

        dirList = ['/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev', '/etc',
                   '/etc/sysconfig', '/etc/sysconfig/network-scripts',
                   '/etc/X11', '/root', '/var/tmp', '/etc/rpm', '/var/cache',
                   '/var/cache/yum']

        # If there are any protected partitions we want to mount, create their
        # mount points now.
        protected = self.method.protectedPartitions()
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
            if os.access("/tmp/modprobe.conf", os.R_OK):
                shutil.copyfile("/tmp/modprobe.conf", 
                                anaconda.rootPath + "/etc/modprobe.conf")
            anaconda.id.network.write(anaconda.rootPath)
            anaconda.id.iscsi.write(anaconda.rootPath)
            anaconda.id.zfcp.write(anaconda.rootPath)

        # make a /etc/mtab so mkinitrd can handle certain hw (usb) correctly
        f = open(anaconda.rootPath + "/etc/mtab", "w+")
        f.write(anaconda.id.fsset.mtab())
        f.close()

    def checkSupportedUpgrade(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            return

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
                for rpmfile in ["__db.000", "__db.001", "__db.002", "__db.003"]:
                    try:
                        os.unlink("%s/var/lib/rpm/%s" %(anaconda.rootPath, rpmfile))
                    except:
                        log.info("error %s removing file: /var/lib/rpm/%s" %(e,rpmfile))
                        pass
                sys.exit(0)

    def doInstall(self, anaconda):
        log.info("Preparing to install packages")
        if flags.test:
            log.info("Test mode - not performing install")
            return

        if not anaconda.id.upgrade:
            rpm.addMacro("__dbi_htconfig",
                         "hash nofsync %{__dbi_other} %{__dbi_perms}")        

        cb = AnacondaCallback(self.ayum, anaconda, self.method,
                              self.instLog, self.modeText)
        cb.setSizes(len(self.dlpkgs), self.totalSize, self.totalFiles)

        cb.initWindow = anaconda.intf.waitWindow(_("Install Starting"),
                                        _("Starting install process.  This may take several minutes..."))

        self.ayum.run(self.instLog, cb, anaconda.intf, anaconda.id)

        if cb.initWindow is not None:
            cb.initWindow.pop()

        self.instLog.close ()

        anaconda.id.instProgress = None

    def doPostInstall(self, anaconda):
        if flags.test:
            return

        if anaconda.id.getUpgrade():
            w = anaconda.intf.waitWindow(_("Post Upgrade"),
                                    _("Performing post upgrade configuration..."))
        else:
            w = anaconda.intf.waitWindow(_("Post Install"),
                                    _("Performing post install configuration..."))

        for tsmbr in self.ayum.tsInfo.matchNaevr(name='rhgb'):
            anaconda.id.bootloader.args.append("rhgb quiet")
            break

        for tsmbr in self.ayum.tsInfo.matchNaevr(name='gdm') + self.ayum.tsInfo.matchNaevr(name='kdm'):
            if anaconda.id.displayMode == 'g' and not flags.usevnc:
                anaconda.id.desktop.setDefaultRunLevel(5)
                break

        # XXX: write proper lvm config

        AnacondaBackend.doPostInstall(self, anaconda)
        w.pop()

    def kernelVersionList(self, rootPath="/"):
        kernelVersions = []
        
        # nick is used to generate the lilo name
        for (ktag, nick) in [ ('kernel-smp', 'smp'),
                              ('kernel-xen0', 'xen0'),
                              ('kernel-xenU', 'xenU'),
                              ('kernel-xen', 'xen')]:
            tag = ktag.rsplit('-', 1)[1]
            for tsmbr in self.ayum.tsInfo.matchNaevr(name=ktag):
                version = ( tsmbr.version + '-' + tsmbr.release + tag)
                kernelVersions.append((version, tsmbr.arch, nick))

        for tsmbr in self.ayum.tsInfo.matchNaevr(name='kernel'):
            version = ( tsmbr.version + '-' + tsmbr.release)
            kernelVersions.append((version, tsmbr.arch, 'base'))

        return kernelVersions

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

    def _selectDefaultOptGroup(self, grpid, default, optional):
        retval = 0
        grp = self.ayum.comps.return_group(grpid)

        if not default:
            for pkg in grp.default_packages.keys():
                self.deselectPackage(pkg)
                retval -= 1

        if optional:
            for pkg in grp.optional_packages.keys():
                self.selectPackage(pkg)
                retval += 1

        return retval

    def selectGroup(self, group, *args):
        if args:
            default = args[0][0]
            optional = args[0][1]
        else:
            default = True
            optional = False

        try:
            mbrs = self.ayum.selectGroup(group)
            if len(mbrs) == 0 and self.isGroupSelected(group):
                return 1

            extras = self._selectDefaultOptGroup(group, default, optional)

            return len(mbrs) + extras
        except yum.Errors.GroupsError, e:
            # try to find out if it's the name or translated name
            gid = self.__getGroupId(group)
            if gid is not None:
                mbrs = self.ayum.selectGroup(gid)
                if len(mbrs) == 0 and self.isGroupSelected(gid):
                    return 1

                extras = self._selectDefaultOptGroup(group, default, optional)

                return len(mbrs) + extras
            else:
                log.debug("no such group %s" %(group,))
                return 0

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
            txmbrs = self.ayum.tsInfo.matchNaevr(name=pkg)

        if len(txmbrs) > 0:
            map(lambda x: self.ayum.tsInfo.remove(x.pkgtup), txmbrs)
        else:
            log.debug("no such package %s" %(pkg,))

    def upgradeFindPackages(self):
        # check the installed system to see if the packages just
        # are not newer in this release.
        # Dictionary of newer package to tuple of old packages
        packageMap = { "firefox": ("mozilla", "netscape-navigator", "netscape-communicator") }

        for new, oldtup in packageMap.iteritems():
            if self.ayum.isPackageInstalled(new):
                continue
            found = 0
            for p in oldtup:
                if self.ayum.rpmdb.installed(name=p):
                    found = 1
                    break
            if found > 0:
                self.selectPackage(new)

    def writeKS(self, f):
        # Only write out lines for repositories that weren't added
        # automatically by anaconda.
        for repo in filter(lambda r: r.addon, self.ayum.repos.listEnabled()):
            line = "repo --name=%s " % (repo.name or repo.repoid)

            if repo.baseurl:
                line += " --baseurl=%s\n" % repo.baseurl[0]
            else:
                line += " --mirrorlist=%s\n" % repo.mirrorlist

            f.write(line)

    def writePackagesKS(self, f):
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
