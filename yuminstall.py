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
import time
import types
import glob
import re

import rpm
import rpmUtils
import urlgrabber.progress
import urlgrabber.grabber
from urlgrabber.grabber import URLGrabber, URLGrabError
import yum
import rhpl
from packages import recreateInitrd
from yum.constants import *
from yum.Errors import RepoError, YumBaseError, PackageSackError
from yum.yumRepo import YumRepository
from installmethod import FileCopyException
from backend import AnacondaBackend
from product import productName, productStamp
from sortedtransaction import SplitMediaTransactionData
from genheader import *
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

class NoMoreMirrorsRepoError(yum.Errors.RepoError):
    def __init__(self, value=None):
        yum.Errors.RepoError.__init__(self)
        self.value = value

class simpleCallback:

    def __init__(self, ayum, messageWindow, progress, pkgTimer,
                 progressWindowClass, instLog, modeText):
        self.ayum = ayum
        self.repos = ayum.repos
        self.messageWindow = messageWindow
        self.progress = progress
        self.pkgTimer = pkgTimer
        self.method = ayum.method
        self.progressWindowClass = progressWindowClass
        self.progressWindow = None
        self.lastprogress = 0
        self.incr = 20
        self.instLog = instLog
        self.modeText = modeText
        self.beenCalled = 0
        self.initWindow = None
        self.ts = ayum.ts
        self.files = {}

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
            self.pkgTimer.start()

            po = h
            hdr = po.returnLocalHeader()
            path = po.returnSimple('relativepath')
            repo = self.repos.getRepo(po.repoid)

            self.progress.setPackage(hdr)
            self.progress.setPackageScale(0, 1)

            nvra = "%s" %(po,)
            self.instLog.write(self.modeText % (nvra,))

            self.instLog.flush()
            self.files[nvra] = None

            self.size = po.returnSimple('installedsize')

            while self.files[nvra] == None:
                try:
                    fn = repo.getPackage(po)

                    f = open(fn, 'r')
                    self.files[nvra] = f
                except NoMoreMirrorsRepoError:
                    self.ayum._handleFailure(po)
                except yum.Errors.RepoError, e:
                    continue

            return self.files[nvra].fileno()

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

            nvra = "%s" %(po,)

            fn = self.files[nvra].name
            self.files[nvra].close()
            self.method.unlinkFilename(fn)
            self.progress.completePackage(hdr, self.pkgTimer)
            self.progress.processEvents()

        else:
            pass

        self.progress.processEvents()

class AnacondaYumRepo(YumRepository):
    def __init__( self, uri=None, mirrorlist=None,
                  repoid='anaconda%s' % productStamp,
                  root = "/mnt/sysimage/", method=None, addon=True):
        YumRepository.__init__(self, repoid)
        self.method = method
        conf = yum.config.RepoConf()
        for k, v in conf.iteritems():
            if v or not self.getAttribute(k):
                self.setAttribute(k, v)
        self.gpgcheck = False
        #self.gpgkey = "%s/RPM-GPG-KEY-fedora" % (method, )
        self.keepalive = False
        self.addon = addon
        
        if uri and not mirrorlist:
            if type(uri) == types.ListType:
                self.baseurl = uri
            else:
                self.baseurl = [ uri ]
        elif mirrorlist and not uri:
            self.mirrorlist = mirrorlist

    #XXX: FIXME duplicated from YumRepository due to namespacing
    def __headersListFromDict(self):
        """Convert our dict of headers to a list of 2-tuples for urlgrabber."""
        headers = []

        keys = self.http_headers.keys()
        for key in keys:
            headers.append((key, self.http_headers[key]))

        return headers

    #XXX: FIXME duplicated from YumRepository due to namespacing
    def __get(self, url=None, relative=None, local=None, start=None, end=None,
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

        if self.failure_obj:
            (f_func, f_args, f_kwargs) = self.failure_obj
            self.failure_obj = (f_func, f_args, f_kwargs)

        if self.cache == 1:
            if os.path.exists(local): # FIXME - we should figure out a way
                return local          # to run the checkfunc from here

            else: # ain't there - raise
                raise yum.Errors.RepoError, \
                    "Caching enabled but no local cache of %s from %s" % (local,
                           self)

        if url is not None:
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
                errstr = "failed to retrieve %s from %s\nerror was %s" % (relative, self.id, e)
                if e.errno == 256:
                    raise NoMoreMirrorsRepoError, errstr
                else:
                    raise yum.Errors.RepoError, errstr
                    
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
                errstr = "failure: %s from %s: %s" % (relative, self.id, e)
                if e.errno == 256:
                    raise NoMoreMirrorsRepoError, errstr
                else:
                    raise yum.Errors.RepoError, errstr

        return result

    def getHeader(self, package, checkfunc = None, reget = 'simple',
            cache = True):

        remote = package.returnSimple('relativepath')
        local =  package.localHdr()
        start = package.returnSimple('hdrstart')
        end = package.returnSimple('hdrend')
        url = None
        if self.method and self.method.splitmethod:
            from urlinstall import UrlInstallMethod
            if isinstance(self.method, UrlInstallMethod):
                if self.urls:
                    repourl = self.urls[0]
                    baseurl = self.method.pkgUrl
                    discurl = self.method.getMethodUri()
                    url = repourl.replace(baseurl, discurl)

        return self.__get(url=url, relative=remote, local=local, start=start,
                        reget=None, end=end, checkfunc=checkfunc, copy_local=1,
                        cache=cache,
                        )

    def getPackage(self, package, checkfunc = None, text = None, cache = True):
        remote = package.returnSimple('relativepath')
        local = package.localPkg()
        url = None
        if self.method and self.method.splitmethod:
            from urlinstall import UrlInstallMethod
            if isinstance(self.method, UrlInstallMethod):
                if self.urls:
                    repourl = self.urls[0]
                    baseurl = self.method.pkgUrl
                    discurl = self.method.getMethodUri()
                    url = repourl.replace(baseurl, discurl)

        return self.__get(url=url,
                          relative=remote,
                          local=local,
                          checkfunc=checkfunc,
                          text=text,
                          cache=cache
                         )

class YumSorter(yum.YumBase):
    
    def __init__(self):
        yum.YumBase.__init__(self)
        self.deps = {}
        self.path = []
        self.loops = []

        self.logger = log
        self.verbose_logger = log

    def isPackageInstalled(self, pkgname):
        # FIXME: this sucks.  we should probably suck it into yum proper
        # but it'll need a bit of cleanup first.  
        installed = False
        if self.rpmdb.installed(name = pkgname):
            installed = True
            
        lst = self.tsInfo.matchNaevr(name = pkgname)
        for txmbr in lst:
            if txmbr.output_state in TS_INSTALL_STATES:
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
            if po not in satisfiers:
                satisfiers.append(po)

        if satisfiers:
            best = self.bestPackagesFromList(satisfiers)[0]
            self.deps[req] = best
            return best
        return None

    def _undoDepInstalls(self):
        # clean up after ourselves in the case of failures
        for txmbr in self.tsInfo:
            if txmbr.isDep:
                self.tsInfo.remove(txmbr.pkgtup)

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

    def resolveDeps(self, *args, **kwargs):
        if self.dsCallback: self.dsCallback.start()
        unresolved = self.tsInfo.getMembers()
        while len(unresolved) > 0:
            if self.dsCallback: self.dsCallback.tscheck(len(unresolved))
            unresolved = self.tsCheck(unresolved)
            if self.dsCallback: self.dsCallback.restartLoop()
        self.deps = {}
        self.loops = []
        self.path = []
        return (2, ['Success - deps resolved'])

    def tsCheck(self, tocheck):
        unresolved = []

        hasOnlyRHLSB = True
        for txmbr in tocheck:
            if not txmbr.name == 'redhat-lsb':
                hasOnlyRHLSB = False

        for txmbr in tocheck:
            if txmbr.name == "redhat-lsb" and not hasOnlyRHLSB: # FIXME: this speeds things up a lot
                unresolved.append(txmbr)
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
                        log.warning("Unresolvable dependency %s in %s"
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
                elif self.rpmdb.installed(name = dep.name, arch = dep.arch,
                                          epoch = dep.epoch, ver = dep.version, rel = dep.release):
                     # If the dependency NAEVR matches what's already installed, skip it
                     continue
                else:
                    if dep.name != req[0]:
                        log.info("adding %s for %s, required by %s" %(dep.name, req[0], txmbr.name))

                    member = self.tsInfo.addInstall(dep)
                    unresolved.append(member)

                #Add relationship
                found = False
                for dependspo in txmbr.depends_on:
                    if member.po == dependspo:
                        found = True
                        break
                if not found:
                    member.setAsDep(txmbr.po)

        return unresolved

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
        self.conf.reposdir="/tmp/repos.d"
        self.conf.logfile="/tmp/yum.log"
        self.conf.obsoletes=True
        self.conf.exclude=[]
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

        # add some additional not enabled by default repos.
        # FIXME: this is a hack and should probably be integrated
        # with the above
        for (name, (uri, mirror)) in self.anaconda.id.instClass.repos.items():
            rid = name.replace(" ", "")
            repo = AnacondaYumRepo(uri=uri, mirrorlist=mirror, repoid=rid,
                                   root=root, addon=False)
            repo.name = name
            repo.disable()
            self.repos.add(repo)

        if self.anaconda.id.extraModules or flags.dlabel:
            for d in glob.glob("/tmp/ramfs/DD-*/rpms"):
                dirname = os.path.basename(os.path.dirname(d))
                rid = "anaconda-%s" % dirname

                repo = AnacondaYumRepo(uri="file://%s" % d, repoid=rid,
                                       root=root, addon=False)
                repo.name = "Driver Disk %s" % dirname.split("-")[1]
                repo.enable()

                try:
                    self.repos.add(repo)
                    log.info("added repository %s with source URL %s" % (repo.name, repo.baseurl))
                except yum.Errors.DuplicateRepoError, e:
                    log.warning("ignoring duplicate repository %s with source URL %s" % (repo.name, repo.baseurl or repo.mirrorlist))

        if self.anaconda.isKickstart:
            for ksrepo in self.anaconda.id.ksdata.repoList:
                repo = AnacondaYumRepo(uri=ksrepo.baseurl,
                                       mirrorlist=ksrepo.mirrorlist,
                                       repoid=ksrepo.name)
                repo.name = ksrepo.name
                repo.enable()

                try:
                    self.repos.add(repo)
                    log.info("added repository %s with source URL %s" % (ksrepo.name, ksrepo.baseurl or ksrepo.mirrorlist))
                except yum.Errors.DuplicateRepoError, e:
                    log.warning("ignoring duplicate repository %s with source URL %s" % (ksrepo.name, ksrepo.baseurl or ksrepo.mirrorlist))

        self.doPluginSetup(searchpath=["/usr/lib/yum-plugins", 
                                       "/tmp/updates/yum-plugins"], 
                           confpath=["/etc/yum/pluginconf.d", 
                                     "/tmp/updates/pluginconf.d"])
        self.plugins.run('init')

        self.repos.setCacheDir(self.conf.cachedir)

    def downloadHeader(self, po):
        while True:
            # retrying version of download header
            try:
                YumSorter.downloadHeader(self, po)
            except NoMoreMirrorsRepoError:
                self._handleFailure(po)
            except yum.Errors.RepoError, e:
                continue
            else:
                break

    def _handleFailure(self, package):
        pkgFile = os.path.basename(package.returnSimple('relativepath'))
        rc = self.anaconda.intf.messageWindow(_("Error"),
                   _("The file %s cannot be opened.  This is due to a missing "
                     "file, a corrupt package or corrupt media.  Please "
                     "verify your installation source.\n\n"
                     "If you exit, your system will be left in an inconsistent "
                     "state that will likely require reinstallation.\n\n") %
                                              (pkgFile,),
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

        delay = 0.25*(2**(obj.tries-1))
        if delay > 1:
            w = self.anaconda.intf.waitWindow(_("Retrying"), _("Retrying package download..."))
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
            elif b > a:
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
            rc = self.runTransaction(cb=cb)
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
            for (descr, (type, mount, need)) in probs.value:
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
        else:
            if rc.return_code == 1:
                msg = _("An error occurred while installing packages.  Please "
                        "examine /root/install.log on your installed system for "
                        "detailed information.")
                log.error(msg)

                if not self.anaconda.isKickstart:
                    intf.messageWindow(_("Error running transaction"),
                                       msg, type="warning")

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
            log.debug('Member: %s' % txmbr)
            if txmbr.ts_state in ['u', 'i']:
                if ts_elem.has_key((txmbr.pkgtup, 'i')):
                    continue

                self.downloadHeader(txmbr.po)
                hdr = txmbr.po.returnLocalHeader()
                rpmfile = txmbr.po.localPkg()
                
                if txmbr.ts_state == 'u':
                    # XXX: kernel-module-* support not in yum
                    #if txmbr.po.name.startswith("kernel-module-"):
                    #    self.handleKernelModule(txmbr)
                    if self.allowedMultipleInstalls(txmbr.po):
                        log.debug('%s converted to install' % (txmbr.po))
                        txmbr.ts_state = 'i'
                        txmbr.output_state = TS_INSTALL

#XXX: Changed callback api to take a package object
                self.ts.addInstall(hdr, txmbr.po, txmbr.ts_state)
                log.debug('Adding Package %s in mode %s' % (txmbr.po, txmbr.ts_state))
                if self.dsCallback: 
                    self.dsCallback.pkgAdded(txmbr.pkgtup, txmbr.ts_state)
            
            elif txmbr.ts_state in ['e']:
                if ts_elem.has_key((txmbr.pkgtup, txmbr.ts_state)):
                    continue
                indexes = self.rpmdb.returnIndexByTuple(txmbr.pkgtup)
                for idx in indexes:
                    self.ts.addErase(idx)
                    if self.dsCallback: self.dsCallback.pkgAdded(txmbr.pkgtup, 'e')
                    log.debug('Removing Package %s' % txmbr.po)

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
        self._installedDriverModules = []

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
        self.ayum.doGroupSetup()
        # FIXME: this is a bad hack to remove support for xen on xen (#179387)
        # FIXME: and another bad hack since our xen kernel is PAE
        # FIXME: and yet another for vmware.
        if iutil.inXen() or iutil.inVmware() or \
                (rpmUtils.arch.getBaseArch() == "i386" and "pae" not in iutil.cpuFeatureFlags()):
            if self.ayum.comps._groups.has_key("virtualization"):
                del self.ayum.comps._groups["virtualization"]

    def doRepoSetup(self, anaconda, thisrepo = None, fatalerrors = True):
        # We want to call ayum.doRepoSetup one repo at a time so we have
        # some concept of which repo didn't set up correctly.
        repos = []

        # Don't do this if we're going backwards
        if anaconda.dir == DISPATCH_BACK:
            return

        if thisrepo is not None:
            repos.append(self.ayum.repos.getRepo(thisrepo))
        else:
            repos.extend(self.ayum.repos.listEnabled())

        anaconda.method.switchMedia(1)

        if not os.path.exists("/tmp/cache"):
            iutil.mkdirChain("/tmp/cache/headers")

        self.ayum.doMacros()

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
            waitwin = YumProgress(anaconda.intf, txt, tot)
            self.ayum.repos.callback = waitwin

            try:
                for (task, incr) in longtasks:
                    waitwin.set_incr(incr)
                    task(thisrepo = repo.id)
                    waitwin.next_task()
                waitwin.pop()
            except RepoError, e:
                log.error("reading package metadata: %s" %(e,))
                waitwin.pop()
                if not fatalerrors:
                    raise RepoError, e

                if repo.id.find("-base-") == -1:
                    log.error("disabling non-base repo %s: %s" %(repo,e))
                    self.ayum.repos.disableRepo(repo.id)
                    continue

                if anaconda.isKickstart:
                    buttons = [_("_Abort"), _("_Continue")]
                else:
                    buttons = [_("_Abort")]

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
                    self.ayum.repos.delete(repo.id)
                    continue

            repo.setFailureObj((self.ayum.urlgrabberFailureCB, (), {}))
            repo.setMirrorFailureObj((self.ayum.mirrorFailureCB, (),
                                     {"tsInfo":self.ayum.tsInfo, 
                                      "repo": repo.id}))

        try:
            self.doGroupSetup()
        except yum.Errors.GroupsError:
            anaconda.intf.messageWindow(_("Error"),
                                        _("Unable to read group information "
                                          "from repositories.  This is "
                                          "a problem with the generation "
                                          "of your install tree."),
                                        type="custom", custom_icon="error",
                                        custom_buttons = [_("Re_boot")])
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

    def selectModulePackages(self, anaconda, kernelPkgName):
        ndx = kernelPkgName.find("-")

        if ndx != -1:
            ext = kernelPkgName[ndx+1:]
        else:
            ext = ""

        for (path, name) in anaconda.id.extraModules:
            if ext != "":
                moduleProvides = "dud-%s-%s" % (name, ext)
            else:
                moduleProvides = "dud-%s" % name

            pkgs = self.ayum.returnPackagesByDep(moduleProvides)

            if not pkgs:
                log.warning("Didn't find any package providing module %s" % name)

            for pkg in pkgs:
                log.info("selecting package %s for module %s" % (pkg.name, name))
                self.ayum.install(po=pkg)
                self._installedDriverModules.append((path, name))

    def copyExtraModules(self, anaconda, modulesList):
        kernelVersions = self.kernelVersionList()
        foundModule = 0

        try:
            f = open("/etc/arch")
            arch = f.readline().strip()
            del f
        except IOError:
            arch = os.uname()[2]

        for (path, name) in modulesList:
            if not path:
                path = "/modules.cgz"
            pattern = ""
            names = ""
            for (n, arch, tag) in kernelVersions:
                if tag == "base":
                    pkg = "kernel"
                else:
                    pkg = "kernel-%s" %(tag,)

                # version 1 path
                pattern = pattern + " %s/%s/%s.ko " % (n, arch, name)
                # version 0 path
                pattern = pattern + " %s/%s.ko " % (n, name)
                names = names + " %s.ko" % (name,)
            command = ("cd %s/lib/modules; gunzip < %s | "
                       "%s/bin/cpio --quiet -iumd %s" % 
                       (anaconda.rootPath, path, anaconda.rootPath, pattern))
            log.info("running: '%s'" % (command, ))
            os.system(command)

            for (n, arch, tag) in kernelVersions:
                if tag == "base":
                    pkg = "kernel"
                else:
                    pkg = "kernel-%s" %(tag,)
                
                toDir = "%s/lib/modules/%s/updates" % \
                        (anaconda.rootPath, n)
                to = "%s/%s.ko" % (toDir, name)

                if (os.path.isdir("%s/lib/modules/%s" %(anaconda.rootPath, n)) and not
                    os.path.isdir("%s/lib/modules/%s/updates" %(anaconda.rootPath, n))):
                    os.mkdir("%s/lib/modules/%s/updates" %(anaconda.rootPath, n))
                if not os.path.isdir(toDir):
                    continue

                for p in ("%s/%s.ko" %(arch, name), "%s.ko" %(name,)):
                    fromFile = "%s/lib/modules/%s/%s" % (anaconda.rootPath, n, p)

                    if (os.access(fromFile, os.R_OK)):
                        log.info("moving %s to %s" % (fromFile, to))
                        os.rename(fromFile, to)
                        # the file might not have been owned by root in the cgz
                        os.chown(to, 0, 0)
                        foundModule = 1
                    else:
                        log.warning("missing DD module %s (this may be okay)" % 
                            fromFile)

        if foundModule == 1:
            for (n, arch, tag) in kernelVersions:
                recreateInitrd(n, anaconda.rootPath)

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
        for k in ("kernel", "kernel-smp", "kernel-xen0", "kernel-xen"):
            if len(self.ayum.tsInfo.matchNaevr(name=k)) > 0:            
                kpkg = getBestKernelByArch(k, self.ayum)
                log.info("%s package selected for kernel" % k)
                foundkernel = True
                self.selectModulePackages(anaconda, k)

                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting %s-devel" % k)
                    self.selectPackage("%s-devel.%s" % (k, kpkg.arch))

        if not foundkernel and iutil.inXen():
            try:
                kxen = getBestKernelByArch("kernel-xen", self.ayum)
                log.info("selecting kernel-xen package for kernel")
                foundkernel = True
            except PackageSackError:
                kxen = None
                log.debug("no kernel-xen package")
            else:
                self.ayum.install(po = kxen)
                self.selectModulePackages(anaconda, kxen.name)
                if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                    log.debug("selecting kernel-xen-devel")
                    self.selectPackage("kernel-xen-devel.%s" % (kxen.arch,))

        if not foundkernel and flags.cmdline.has_key("xen0"):
            try:
                kxen = getBestKernelByArch("kernel-xen", self.ayum)
                log.info("selecting kernel-xen package for kernel")
                foundkernel = True
            except PackageSackError:
                kxen = None
                log.debug("no kernel-xen package")
            else:
                self.ayum.install(po = kxen)
                self.selectModulePackages(anaconda, kxen.name)
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
            self.selectPackage("%s.%s" % (pkg, rpmUtils.arch.canonArch))

    def doPostSelection(self, anaconda):
        # Only solve dependencies on the way through the installer, not the way back.
        if anaconda.dir == DISPATCH_BACK:
            return

        dscb = YumDepSolveProgress(anaconda.intf)
        self.ayum.dsCallback = dscb

        # do some sanity checks for kernel and bootloader
        self.selectBestKernel(anaconda)
        self.selectBootloader()
        self.selectFSPackages(anaconda.id.fsset, anaconda.id.diskset)

        self.selectAnacondaNeeds()

        if anaconda.id.getUpgrade():
            from upgrade import upgrade_remove_blacklist, upgrade_conditional_packages
            for condreq, cond in upgrade_conditional_packages.iteritems():
                pkgs = self.ayum.pkgSack.searchNevra(name=condreq)
                if pkgs:
                    pkgs = self.ayum.bestPackagesFromList(pkgs)
                    if self.ayum.tsInfo.conditionals.has_key(cond):
                        self.ayum.tsInfo.conditionals[cond].extend(pkgs)
                    else:
                        self.ayum.tsInfo.conditionals[cond] = pkgs
                
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
            (code, msgs) = self.ayum.buildTransaction()
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
                                              "reboot." % (self.totalSize / 1024)),
                                            type="custom", custom_icon="error",
                                            custom_buttons=[_("_Back"), _("Re_boot")])

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
            for d in ("/selinux", "/dev", "/proc/bus/usb"):
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
            # in it)
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

            # For usbfs
            try:
                isys.mount("/proc/bus/usb", anaconda.rootPath + "/proc/bus/usb", "usbfs")
            except Exception, e:
                log.error("error mounting usbfs: %s" %(e,))

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
            anaconda.id.keyboard.write(anaconda.rootPath)

        # make a /etc/mtab so mkinitrd can handle certain hw (usb) correctly
        f = open(anaconda.rootPath + "/etc/mtab", "w+")
        f.write(anaconda.id.fsset.mtab())
        f.close()

        # disable dmraid boot features if system isn't using dmraid
        if not flags.dmraid:
            mpfile = anaconda.rootPath + "/etc/sysconfig/mkinitrd/dmraid"
            leading = os.path.dirname(mpfile)

            if not os.path.isdir(leading):
                os.makedirs(leading, mode=0755)

            f = open(mpfile, "w")
            f.write("DMRAID=no\n")
            f.close()
            os.chmod(mpfile, 0755)

        # disable multipath boot features if system isn't using multipath
        if not flags.mpath:
            mpfile = anaconda.rootPath + "/etc/sysconfig/mkinitrd/multipath"
            leading = os.path.dirname(mpfile)

            if not os.path.isdir(leading):
                os.makedirs(leading, mode=0755)

            f = open(mpfile, "w")
            f.write("MULTIPATH=no\n")
            f.close()
            os.chmod(mpfile, 0755)

        # make sure multipath bindings file exists on final system
        bindings = '/var/lib/multipath/bindings'
        wwids = []
        if flags.mpath:
            d = os.path.dirname(bindings)

            if not os.path.isdir(d):
                os.makedirs(d, mode=0755)

            mpdevlst = []
            for mpdev in anaconda.id.diskset.mpList or []:
                mpdevlst.append(mpdev.name)

            for entry in anaconda.id.fsset.entries:
                dev = entry.device.getDevice()
                for mpdev in mpdevlst:
                    # eliminate the major number (ex. mpath0 -> mpath)
                    pos = 0
                    while pos < len(mpdev):
                        if mpdev[pos].isdigit():
                            mpdev = mpdev[:pos]
                            break
                        pos += 1
                    if dev.find(mpdev) != -1:
                        # grab just the basename of the device
                        mpathname = dev.replace('/dev/', '')
                        mpathname = mpathname.replace('mpath/', '')
                        mpathname = mpathname.replace('mapper/', '')

                        # In case of mpathNNNpMMM, we only want 'mpathNNN' where 
                        # NNN is an int, strip all trailing subdivisions of mpathNNN
                        mpregex = "^%s(\d*)" % mpdev
                        match = re.search(mpregex, mpathname)
                        if match is not None:
                            mpathname = match.group()
                            major = int(match.group(1))
                    else:
                        continue

                    # if we have seen this mpath device, continue
                    if wwids != []:
                        seen = False

                        for (m, s) in wwids:
                            if m == mpathname:
                                seen = True
                                break

                        if seen is True:
                            continue

                    fulldev = "/dev/mapper/%s" % (mpathname,)

                    # get minor number
                    if os.path.exists(fulldev):
                        minor = os.minor(os.stat(fulldev).st_rdev)
                    else:
                        continue

                    # gather [screaming] slaves
                    slaves = []
                    slavepath = "/sys/block/dm-%d/slaves" % (minor,)
                    if os.path.isdir(slavepath):
                        slaves = os.listdir(slavepath)
                    else:
                        continue

                    # collect WWIDs for each slave
                    idlist = []
                    for slave in slaves:
                       sarg = "/block/%s" % (slave,)

                       output = iutil.execWithCapture("scsi_id",
                                                      ["-g", "-u", "-s", sarg],
                                                      stderr = "/dev/tty5")

                       # may be an EMC device, try special option
                       if output == "":
                           output = iutil.execWithCapture("scsi_id",
                                    ["-g", "-u", "-ppre-spc3-83", "-s", sarg],
                                    stderr = "/dev/tty5")

                       if output != "":
                           for line in output.split("\n"):
                               if line == '':
                                   continue

                               try:
                                   i = idlist.index(line)
                               except:
                                   idlist.append(line)

                    if idlist != []:
                        if len(idlist) > 1:
                            log.error(_("Too many WWIDs collected for %s, found:") % (mpathname,))
                            for id in idlist:
                                log.error(_("    %s for %s") % (id, mpathname,))
                        else:
                            wwids.append((mpathname, idlist[0]))

            if wwids != []:
                f = open(bindings, 'w')

                f.write("# Multipath bindings, Version : 1.0\n")
                f.write("# NOTE: this file is automatically maintained by the multipath program.\n")
                f.write("# You should not need to edit this file in normal circumstances.\n")
                f.write("#\n")
                f.write("# This file was automatically generated by anaconda.\n")
                f.write("#\n")
                f.write("# Format:\n")
                f.write("# alias wwid\n")
                f.write("#\n")

                for (mpathname, id) in wwids:
                    f.write("%s %s\n" % (mpathname, id,))

                f.close()

            if os.path.isfile(bindings):
                leading = anaconda.rootPath + os.path.dirname(bindings)

                if not os.path.isdir(leading):
                    os.makedirs(leading, mode=0755)

                shutil.copy2(bindings, leading + '/bindings')

        # since all devices are blacklisted by default, add a
        # blacklist_exceptions block for the devices we want treated as
        # multipath devices  --dcantrell (BZ #243527)
        mpconf = "/etc/multipath.conf"
        if flags.mpath:
            # Read in base multipath.conf file.  First try target system (in
            # the case of upgrades, keep this file).  If that fails, read from
            # the anaconda environment.
            if os.path.isfile(anaconda.rootPath + mpconf):
                mpfile = anaconda.rootPath + mpconf
            elif os.path.isfile(mpconf):
                mpfile = mpconf
            else:
                mpfile = None

            if mpfile is None:
                log.error("%s not found on target system." % (mpconf,))
                return

            f = open(mpfile, "r")
            # remove newline from the end of each line
            mplines = map(lambda s: s[:-1], f.readlines())
            f.close()

            mpdest = anaconda.rootPath + mpconf
            if not os.path.isdir(os.path.dirname(mpdest)):
                os.makedirs(os.path.dirname(mpdest), 0755)

            f = open(anaconda.rootPath + mpconf, "w")

            blacklist = False
            blacklistExceptions = False
            depth = 0
            for line in mplines:
                if line.strip().startswith('#'):
                    f.write("%s\n" % (line,))
                else:
                    if line.strip().startswith('blacklist'):
                        depth += line.count('{')
                        depth -= line.count('}')
                        f.write("#%s\n" % (line,))

                        if depth != 0:
                            blacklist = True
                    elif line.strip().startswith('blacklist_exceptions'):
                        depth += line.count('{')
                        depth -= line.count('}')
                        f.write("#%s\n" % (line,))

                        if depth != 0:
                            blacklistExceptions = True
                    else:
                        if blacklist:
                            depth += line.count('{')
                            depth -= line.count('}')
                            f.write("#%s\n" % (line,))

                            if depth == 0:
                                blacklist = False
                        elif blacklistExceptions:
                            depth += line.count('{')
                            depth -= line.count('}')
                            f.write("#%s\n" % (line,))

                            if depth == 0:
                                blacklistExceptions = False
                        else:
                            f.write("%s\n" % (line,))

            # write out the catch-all blacklist section to
            # blacklist all device types
            f.write('\nblacklist {\n')
            f.write('        devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"\n')
            f.write('        devnode "^(hd|xvd|vd)[a-z]*"\n')
            f.write('        wwid "*"\n')
            f.write('}\n')

            # write out the blacklist exceptions with multipath WWIDs
            if wwids != []:
                f.write('\n# Make sure our multipath devices are enabled.\n')
                f.write('\nblacklist_exceptions {\n')

                for (mpathname, id) in wwids:
                    f.write("        wwid \"%s\"\n" % (id,))

                f.write('}\n\n')

                for (mpathname, id) in wwids:
                    if(mpathname.find("mpath") == -1):
                        # this mpath device was renamed 
                        f.write('\nmultipath {\n')
                        f.write("        wwid \"%s\"\n" % (id,))
                        f.write("        alias \"%s\"\n" % (mpathname,)) 
                        f.write('}\n\n')

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

        pkgTimer = timer.Timer(start = 0)

        anaconda.id.instProgress.setSizes(len(self.dlpkgs), self.totalSize, self.totalFiles)
        anaconda.id.instProgress.processEvents()

        cb = simpleCallback(self.ayum, anaconda.intf.messageWindow, anaconda.id.instProgress, pkgTimer, anaconda.intf.progressWindow, self.instLog, self.modeText)

        cb.initWindow = anaconda.intf.waitWindow(_("Install Starting"),
                                        _("Starting install process.  This may take several minutes..."))

        self.ayum.run(self.instLog, cb, anaconda.intf, anaconda.id)

        if not cb.beenCalled:
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

        # If we installed modules from packages using the new driver disk
        # method, we still need to remake the initrd.  Otherwise, drop back
        # to the old method.
        if len(self._installedDriverModules) > 0 and len(self._installedDriverModules) == len(anaconda.id.extraModules):
            for (n, arch, tag) in self.kernelVersionList():
                recreateInitrd(n, anaconda.rootPath)
        else:
            modulesList = filter(lambda m: m not in self._installedDriverModules, anaconda.id.extraModules)
            self.copyExtraModules(anaconda, modulesList)

        for tsmbr in self.ayum.tsInfo.matchNaevr(name='rhgb'):
            anaconda.id.bootloader.args.append("rhgb quiet")
            break

        for tsmbr in self.ayum.tsInfo.matchNaevr(name='gdm'):
            if anaconda.id.displayMode == 'g' and not flags.usevnc:
                anaconda.id.desktop.setDefaultRunLevel(5)
                break

# XXX: write proper lvm config

        w.pop()
        AnacondaBackend.doPostInstall(self, anaconda)

    def kernelVersionList(self):
        kernelVersions = []
        
        # nick is used to generate the lilo name
        for (ktag, nick) in [ ('kernel-PAE', 'PAE'),
                              ('kernel-smp', 'smp'),
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

    def selectGroup(self, group, *args):
        try:
            mbrs = self.ayum.selectGroup(group)
            if len(mbrs) == 0 and self.isGroupSelected(group):
                return 1
            return len(mbrs)
        except yum.Errors.GroupsError, e:
            # try to find out if it's the name or translated name
            gid = self.__getGroupId(group)
            if gid is not None:
                mbrs = self.ayum.selectGroup(gid)
                if len(mbrs) == 0 and self.isGroupSelected(gid):
                    return 1
                return len(mbrs)
            else:
                log.debug("no such group %s" %(group,))
                return 0

    def deselectGroup(self, group, *args):
        # This method is meant to deselect groups that have been previously
        # selected in the UI.  It does not handle groups removed via kickstart.
        # yum does not work that way (in 5.5).
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

    def removeGroupsPackages(self, grp):
        # This method removes all the groups of a package that has been
        # excluded via kickstart.  This is subtly different from removing
        # a group previously selected in the UI.
        groups = self.ayum.comps.return_groups(grp)
        for grp in groups:
            for pkgname in grp.packages:
                for txmbr in self.ayum.tsInfo:
                    if txmbr.po.name == pkgname and txmbr.po.state in TS_INSTALL_STATES:
                        self.ayum.tsInfo.remove(txmbr.po.pkgtup)

                        for pkg in self.ayum.tsInfo.conditionals.get(txmbr.name, []):
                            self.ayum.tsInfo.remove(pkg.pkgtup)

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

    def writePackagesKS(self, f, anaconda):
        if anaconda.isKickstart:
            groups = anaconda.id.ksdata.groupList
            installed = anaconda.id.ksdata.packageList
            removed = anaconda.id.ksdata.excludedList
        else:
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

            for grp in filter(lambda x: x.selected, self.ayum.comps.groups):
                groups.append(grp.groupid)

                defaults = grp.default_packages.keys() + grp.mandatory_packages.keys()
                optionals = grp.optional_packages.keys()

                for pkg in filter(lambda x: x in defaults and (not x in txmbrNames and x in allPkgNames), grp.packages):
                    removed.append(pkg)

                for pkg in filter(lambda x: x in txmbrNames, optionals):
                    installed.append(pkg)

        f.write("\n%packages\n")

        for grp in groups:
            f.write("@%s\n" % grp)

        for pkg in installed:
            f.write("%s\n" % pkg)

        for pkg in removed:
            f.write("-%s\n" % pkg)

    def writeConfiguration(self):
        return
#         emptyRepoConf = yum.config.RepoConf()
#         compulsorySettings = [ 'enabled' ]
#         for repo in self.ayum.repos.listEnabled():
#             repo.disable()
#             fn = "%s/etc/yum.repos.d/%s.repo" % (self.instPath, repo.id)
#             f = open(fn , 'w')
#             f.write('[%s]\n' % (repo.id,))
#             for k, v in emptyRepoConf.iteritems():
#                 repoval = repo.getAttribute(k)
#                 if k not in compulsorySettings:
#                     if not repoval or repoval == v:
#                         continue
#                 val = emptyRepoConf.optionobj(k).tostring(repoval)
#                 f.write("%s=%s\n" % (k,val))
#             repo.enable()
#             f.close()

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
