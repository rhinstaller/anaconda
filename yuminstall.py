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
import tempfile
import itertools
import re


import anaconda_log
import rpm
import rpmUtils
import urlgrabber.progress
import urlgrabber.grabber
from urlgrabber.grabber import URLGrabber, URLGrabError
import yum
import iniparse
from yum.constants import *
from yum.Errors import *
from yum.misc import to_unicode
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
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

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

    retval = None

    if size > 1024 * 1024:
        size = size / (1024*1024)
        retval = _("%s MB") %(number_format(size),)
    elif size > 1024:
        size = size / 1024
        retval = _("%s KB") %(number_format(size),)
    else:
        retval = P_("%s Byte", "%s Bytes", size) % (number_format(size),)

    return to_unicode(retval)

class AnacondaCallback:

    def __init__(self, ayum, anaconda, instLog, modeText):
        self.repos = ayum.repos
        self.ts = ayum.ts
        self.ayum = ayum

        self.messageWindow = anaconda.intf.messageWindow
        self.pulseWindow = anaconda.intf.progressWindow
        self.progress = anaconda.intf.instProgress
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
                    self.progressWindowClass (_("Preparing to install"),
                                              _("Preparing transaction from installation source"),
                                              total)
                self.incr = total / 10

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
            s = to_unicode(_("<b>Installing %(pkgStr)s</b> (%(size)s)\n")) \
                    % {'pkgStr': pkgStr, 'size': size_string(hdr['size'])}
            summary = to_unicode(gettext.ldgettext("redhat-dist", hdr['summary'] or ""))
            s += summary.strip()
            self.progress.set_label(s)

            self.instLog.write(self.modeText % str(pkgStr))

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

            if os.path.dirname(fn).startswith("%s/var/cache/yum/" % self.rootPath):
                try:
                    os.unlink(fn)
                except OSError as e:
                    log.debug("unable to remove file %s" %(e.strerror,))

            self.donepkgs += 1
            self.doneSize += self.inProgressPo.returnSimple("installedsize") / 1024.0
            self.doneFiles += len(hdr[rpm.RPMTAG_BASENAMES])

            if self.donepkgs <= self.numpkgs:
                self.progress.set_text(P_("Packages completed: "
                                          "%(donepkgs)d of %(numpkgs)d",
                                          "Packages completed: "
                                          "%(donepkgs)d of %(numpkgs)d",
                                          self.numpkgs)
                                       % {'donepkgs': self.donepkgs,
                                          'numpkgs': self.numpkgs})
            self.progress.set_fraction(float(self.doneSize / self.totalSize))
            self.progress.processEvents()

            self.inProgressPo = None

        elif what in (rpm.RPMCALLBACK_UNINST_START,
                      rpm.RPMCALLBACK_UNINST_STOP):
            if self.initWindow is None:
                self.initWindow = self.pulseWindow(_("Finishing upgrade"),
                                                   _("Finishing upgrade process.  This may take a little while."),
                                                   0, pulse=True)
            else:
                self.initWindow.pulse()

        elif what in (rpm.RPMCALLBACK_CPIO_ERROR,
                      rpm.RPMCALLBACK_UNPACK_ERROR,
                      rpm.RPMCALLBACK_SCRIPT_ERROR):
            if not isinstance(h, types.TupleType):
                h = (h, None)

            (hdr, rpmloc) = h

            # If this is a cleanup/remove, then hdr is a string not a header.
            if isinstance(hdr, rpm.hdr):
                name = hdr['name']
            else:
                name = hdr

            # Script errors store whether or not they're fatal in "total".  So,
            # we should only error out for fatal script errors or the cpio and
            # unpack problems.
            if what != rpm.RPMCALLBACK_SCRIPT_ERROR or total:
                self.messageWindow(_("Error Installing Package"),
                    _("A fatal error occurred when installing the %s "
                      "package.  This could indicate errors when reading "
                      "the installation media.  Installation cannot "
                      "continue.") % name,
                    type="custom", custom_icon="error",
                    custom_buttons=[_("_Exit installer")])
                sys.exit(1)

        if self.initWindow is None:
            self.progress.processEvents()

class AnacondaYumRepo(YumRepository):
    def __init__(self, *args, **kwargs):
        YumRepository.__init__(self, *args, **kwargs)
        self.enablegroups = True
        self._anacondaBaseURLs = []

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

    # needed to store nfs: repo url that yum doesn't know
    def _getAnacondaBaseURLs(self):
        return self._anacondaBaseURLs or self.baseurl or [self.mirrorlist]

    def _setAnacondaBaseURLs(self, value):
        self._anacondaBaseURLs = value

    anacondaBaseURLs = property(_getAnacondaBaseURLs, _setAnacondaBaseURLs,
                                doc="Extends AnacondaYum.baseurl to store non-yum urls:")

class YumSorter(yum.YumBase):
    def _transactionDataFactory(self):
        return SplitMediaTransactionData()

class AnacondaYum(YumSorter):
    def __init__(self, anaconda):
        YumSorter.__init__(self)
        self.anaconda = anaconda
        self._timestamp = None

        self.repoIDcounter = itertools.count()

        # Only needed for hard drive and nfsiso installs.
        self._discImages = {}
        self.isodir = None

        # Only needed for media installs.
        self.currentMedia = None
        self.mediagrabber = None

        # Where is the source media mounted?  This is the directory
        # where Packages/ is located.
        self.tree = "/mnt/source"

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

    def setup(self):
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
                      "installation repository:\n\n%(e)s\n\nPlease provide the "
                      "correct information for installing %(productName)s.")
                    % {'e': e, 'productName': productName})

                self.anaconda.methodstr = self.anaconda.intf.methodstrRepoWindow(self.anaconda.methodstr or "cdrom:")

        self.doConfigSetup(root=self.anaconda.rootPath)
        self.conf.installonlypkgs = []

    def _switchCD(self, discnum):
        if os.access("%s/.discinfo" % self.tree, os.R_OK):
            f = open("%s/.discinfo" % self.tree)
            self._timestamp = f.readline().strip()
            f.close()

        dev = self.anaconda.storage.devicetree.getDeviceByName(self.anaconda.mediaDevice)
        dev.format.mountpoint = self.tree

        # If self.currentMedia is None, then there shouldn't be anything
        # mounted.  Before going further, see if the correct disc is already
        # in the drive.  This saves a useless eject and insert if the user
        # has for some reason already put the disc in the drive.
        if self.currentMedia is None:
            try:
                dev.format.mount()

                if verifyMedia(self.tree, discnum, None):
                    self.currentMedia = discnum
                    return

                dev.format.unmount()
            except:
                pass
        else:
            unmountCD(dev, self.anaconda.intf.messageWindow)
            self.currentMedia = None

        dev.eject()

        while True:
            if self.anaconda.intf:
                self.anaconda.intf.beep()

            self.anaconda.intf.messageWindow(_("Change Disc"),
                _("Please insert %(productName)s disc %(discnum)d to continue.")
                % {'productName': productName, 'discnum': discnum})

            try:
                dev.format.mount()

                if verifyMedia(self.tree, discnum, self._timestamp):
                    self.currentMedia = discnum
                    break

                self.anaconda.intf.messageWindow(_("Wrong Disc"),
                        _("That's not the correct %s disc.")
                          % (productName,))

                dev.format.unmount()
                dev.eject()
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
        if flags.cmdline.has_key("preupgrade"):
            path = "/var/cache/yum/preupgrade"
            self.anaconda.methodstr = "hd::%s" % path 
            self._baseRepoURL = "file:///mnt/sysimage/%s" % path
        elif self.anaconda.methodstr:
            m = self.anaconda.methodstr

            if m.startswith("hd:"):
                if m.count(":") == 2:
                    (device, path) = m[3:].split(":")
                else:
                    (device, fstype, path) = m[3:].split(":")

                self.isodir = "/mnt/isodir/%s" % path

                # This takes care of mounting /mnt/isodir first.
                self._switchImage(1)
                self.mediagrabber = self.mediaHandler
            elif m.startswith("nfsiso:"):
                self.isodir = "/mnt/isodir"

                # Calling _switchImage takes care of mounting /mnt/isodir first.
                if not network.hasActiveNetDev():
                    if not self.anaconda.intf.enableNetwork():
                        self._baseRepoURL = None
                        return

                    urlgrabber.grabber.reset_curl_obj()

                self._switchImage(1)
                self.mediagrabber = self.mediaHandler
            elif m.startswith("http") or m.startswith("ftp:"):
                self._baseRepoURL = m
            elif m.startswith("nfs:"):
                if not network.hasActiveNetDev():
                    if not self.anaconda.intf.enableNetwork():
                        self._baseRepoURL = None

                    urlgrabber.grabber.reset_curl_obj()

                (opts, server, path) = iutil.parseNfsUrl(m)
                isys.mount(server+":"+path, self.tree, "nfs", options=opts)

                # This really should be fixed in loader instead but for now see
                # if there's images and if so go with this being an NFSISO
                # install instead.
                images = findIsoImages(self.tree, self.anaconda.intf.messageWindow)
                if images != {}:
                    isys.umount(self.tree, removeDir=False)
                    self.anaconda.methodstr = "nfsiso:%s" % m[4:]
                    self.configBaseURL()
                    return
            elif m.startswith("cdrom:"):
                self._switchCD(1)
                self.mediagrabber = self.mediaHandler
                self._baseRepoURL = "file://%s" % self.tree
        else:
            # No methodstr was given.  In order to find an installation source,
            # we should first check to see if there's a CD/DVD with packages
            # on it, and then default to the mirrorlist URL.  The user can
            # always change the repo with the repo editor later.
            cdr = scanForMedia(self.tree, self.anaconda.storage)
            if cdr:
                self.mediagrabber = self.mediaHandler
                self.anaconda.mediaDevice = cdr
                self.currentMedia = 1
                log.info("found installation media on %s" % cdr)
            else:
                # No CD with media on it and no repo=/method= parameter, so
                # default to using whatever's enabled in /etc/yum.repos.d/
                self._baseRepoURL = None

    def configBaseRepo(self, root='/'):
        # Create the "base" repo object, assuming there is one.  Otherwise we
        # just skip all this and use the defaults from /etc/yum.repos.d.
        if not self._baseRepoURL:
            return

        # add default repos
        anacondabaseurl = (self.anaconda.methodstr or
                           "cdrom:%s" % (self.anaconda.mediaDevice))
        anacondabasepaths = self.anaconda.instClass.getPackagePaths(anacondabaseurl)
        for (name, uri) in self.anaconda.instClass.getPackagePaths(self._baseRepoURL).items():
            rid = name.replace(" ", "")

            repo = AnacondaYumRepo("anaconda-%s-%s" % (rid, productStamp))
            repo.baseurl = uri
            repo.anacondaBaseURLs = anacondabasepaths[name]

            repo.name = name
            repo.cost = 100

            if self.anaconda.mediaDevice or self.isodir:
                repo.mediaid = getMediaId(self.tree)
                log.info("set mediaid of repo %s to: %s" % (rid, repo.mediaid))

            repo.enable()
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

        if "-source" in repo.id or "-debuginfo" in repo.id:
            name = repo.name
            del(repo)
            raise RepoError, "Repo %s contains -source or -debuginfo, excluding" % name

        # this is a little hard-coded, but it's effective
        if not BETANAG and ("rawhide" in repo.id or "development" in repo.id):
            name = repo.name
            del(repo)
            raise RepoError, "Excluding devel repo %s for non-devel anaconda" % name

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
    def _getReleasever(self):
        from ConfigParser import ConfigParser
        c = ConfigParser()

        try:
            if os.access("%s/.treeinfo" % self.anaconda.methodstr, os.R_OK):
                ConfigParser.read(c, "%s/.treeinfo" % self.anaconda.methodstr)
            else:
                ug = URLGrabber()
                ug.urlgrab("%s/.treeinfo" % self.anaconda.methodstr,
                           "/tmp/.treeinfo", copy_local=1)
                ConfigParser.read(c, "/tmp/.treeinfo")

            return c.get("general", "version")
        except:
            return productVersion

    # Override this method so yum doesn't nuke our existing logging config.
    def doLoggingSetup(self, *args, **kwargs):

        import yum.logginglevels

        file_handler = logging.FileHandler("/tmp/yum.log")
        file_formatter = logging.Formatter("[%(asctime)s] %(levelname)-8s: %(message)s")
        file_handler.setFormatter(file_formatter)

        tty3_handler = logging.FileHandler("/dev/tty3")
        tty3_formatter = logging.Formatter(anaconda_log.TTY_FORMAT,
                                           anaconda_log.DATE_FORMAT)
        tty3_handler.setFormatter(tty3_formatter)

        verbose = logging.getLogger("yum.verbose")
        verbose.setLevel(logging.DEBUG)
        verbose.propagate = False
        verbose.addHandler(file_handler)

        logger = logging.getLogger("yum")
        logger.propagate = False
        logger.setLevel(yum.logginglevels.INFO_2)
        logger.addHandler(file_handler)
        anaconda_log.autoSetLevel(tty3_handler, True)
        tty3_handler.setLevel(anaconda_log.logger.tty_loglevel)
        logger.addHandler(tty3_handler)

        # XXX filelogger is set in setFileLog - do we or user want it?
        filelogger = logging.getLogger("yum.filelogging")
        filelogger.setLevel(logging.INFO)
        filelogger.propagate = False


    def doConfigSetup(self, fn='/tmp/anaconda-yum.conf', root='/'):
        if hasattr(self, "preconf"):
            self.preconf.fn = fn
            self.preconf.root = root
            self.preconf.releasever = self._getReleasever()
            self.preconf.enabled_plugins = ["whiteout", "blacklist"]
            YumSorter._getConfig(self)
        else:
            YumSorter._getConfig(self, fn=fn, root=root,
                                 enabled_plugins=["whiteout", "blacklist"])
        self.configBaseRepo(root=root)

        extraRepos = []

        ddArch = os.uname()[4]

        #Add the Driver disc repos to Yum
        for d in glob.glob(DD_RPMS):
            dirname = os.path.basename(d)
            rid = "anaconda-%s" % dirname

            repo = AnacondaYumRepo(rid)
            repo.baseurl = [ "file:///%s" % d ]
            repo.name = "Driver Disk %s" % dirname.split("-")[1]
            repo.enable()
            extraRepos.append(repo)

        if self.anaconda.ksdata:
            # This is the same pattern as from loader/urls.c:splitProxyParam.
            pattern = re.compile("([[:alpha:]]+://)?(([[:alnum:]]+)(:[^:@]+)?@)?([^:]+)(:[[:digit:]]+)?(/.*)?")

            for ksrepo in self.anaconda.ksdata.repo.repoList:
                anacondaBaseURLs = [ksrepo.baseurl]

                # yum doesn't understand nfs:// and doesn't want to.  We need
                # to first do the mount, then translate it into a file:// that
                # yum does understand.
                # "nfs:" and "nfs://" prefixes are accepted in ks repo --baseurl
                if ksrepo.baseurl and ksrepo.baseurl.startswith("nfs:"):
                    if not network.hasActiveNetDev() and not self.anaconda.intf.enableNetwork():
                        self.anaconda.intf.messageWindow(_("No Network Available"),
                            _("Some of your software repositories require "
                              "networking, but there was an error enabling the "
                              "network on your system."),
                            type="custom", custom_icon="error",
                            custom_buttons=[_("_Exit installer")])
                        sys.exit(1)

                    urlgrabber.grabber.reset_curl_obj()

                    dest = tempfile.mkdtemp("", ksrepo.name.replace(" ", ""), "/mnt")

                    # handle "nfs://" prefix
                    if ksrepo.baseurl[4:6] == '//':
                        ksrepo.baseurl = ksrepo.baseurl.replace('//', '', 1)
                        anacondaBaseURLs = [ksrepo.baseurl]
                    try:
                        isys.mount(ksrepo.baseurl[4:], dest, "nfs")
                    except Exception as e:
                        log.error("error mounting NFS repo: %s" % e)

                    ksrepo.baseurl = "file://%s" % dest

                repo = AnacondaYumRepo(ksrepo.name)
                repo.mirrorlist = ksrepo.mirrorlist
                repo.name = ksrepo.name

                if not ksrepo.baseurl:
                    repo.baseurl = []
                else:
                    repo.baseurl = [ ksrepo.baseurl ]
                repo.anacondaBaseURLs = anacondaBaseURLs

                if ksrepo.cost:
                    repo.cost = ksrepo.cost

                if ksrepo.excludepkgs:
                    repo.exclude = ksrepo.excludepkgs

                if ksrepo.includepkgs:
                    repo.include = ksrepo.includepkgs

                if ksrepo.proxy:
                    m = pattern.match(ksrepo.proxy)

                    if m and m.group(5):
                        # If both a host and port was found, just paste them
                        # together using the colon at the beginning of the port
                        # match as a separator.  Otherwise, just use the host.
                        if m.group(6):
                            repo.proxy = m.group(5) + m.group(6)
                        else:
                            repo.proxy = m.group(5)

                        # yum also requires a protocol.  If none was given,
                        # default to http.
                        if m.group(1):
                            repo.proxy = m.group(1) + repo.proxy
                        else:
                            repo.proxy = "http://" + repo.proxy

                    if m and m.group(3):
                        repo.proxy_username = m.group(3)

                    if m and m.group(4):
                        # Skip the leading colon.
                        repo.proxy_password = m.group(4)[1:]

                repo.enable()
                extraRepos.append(repo)

        for repo in extraRepos:
            try:
                self.repos.add(repo)
                log.info("added repository %s with URL %s" % (repo.name, repo.mirrorlist or repo.baseurl))
            except:
                log.warning("ignoring duplicate repository %s with URL %s" % (repo.name, repo.mirrorlist or repo.baseurl))

        self.repos.setCacheDir(self.conf.cachedir)

        if os.path.exists("%s/boot/upgrade/install.img" % self.anaconda.rootPath):
            log.info("REMOVING stage2 image from %s /boot/upgrade" % self.anaconda.rootPath )
            try:
                os.unlink("%s/boot/upgrade/install.img" % self.anaconda.rootPath)
            except:
                log.warning("failed to clean /boot/upgrade")

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
        if not self.isodir and self.currentMedia:
            buttons = [_("Re_boot"), _("_Eject")]
        else:
            buttons = [_("Re_boot"), _("_Retry")]

        pkgFile = to_unicode(os.path.basename(package.remote_path))
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
            if os.path.exists(package.localPkg()):
                os.unlink(package.localPkg())

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
            dev = self.anaconda.storage.devicetree.getDeviceByName(self.anaconda.mediaDevice)
            dev.format.mountpoint = self.tree
            unmountCD(dev, self.anaconda.intf.messageWindow)
            self.currentMedia = None

    def urlgrabberFailureCB (self, obj, *args, **kwargs):
        if hasattr(obj, "exception"):
            log.warning("Try %s/%s for %s failed: %s" % (obj.tries, obj.retry, obj.url, obj.exception))
        else:
            log.warning("Try %s/%s for %s failed" % (obj.tries, obj.retry, obj.url))

        if obj.tries == obj.retry:
            return

        delay = 0.25*(2**(obj.tries-1))
        if delay > 1:
            w = self.anaconda.intf.waitWindow(_("Retrying"), _("Retrying download."))
            time.sleep(delay)
            w.pop()
        else:
            time.sleep(delay)

    def getDownloadPkgs(self):
        downloadpkgs = []
        totalSize = 0
        totalFiles = 0
        for txmbr in self.tsInfo.getMembersWithState(output_states=TS_INSTALL_STATES):
            if txmbr.po:
                totalSize += int(txmbr.po.returnSimple("installedsize")) / 1024
                for filetype in txmbr.po.returnFileTypes():
                    totalFiles += len(txmbr.po.returnFileEntries(ftype=filetype))
                downloadpkgs.append(txmbr.po)

        return (downloadpkgs, totalSize, totalFiles)

    def setColor(self):
        if rpmUtils.arch.isMultiLibArch():
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
        if self.anaconda.upgrade:
            self.ts.ts.setProbFilter(~rpm.RPMPROB_FILTER_DISKSPACE)
        self.setColor()

        # If we don't have any required media assume single disc
        if self.tsInfo.reqmedia == {}:
            self.tsInfo.reqmedia[0] = None
        mkeys = self.tsInfo.reqmedia.keys()
        mkeys.sort(mediasort)

        stage2img = "%s/images/install.img" % self.tree
        if os.path.exists(stage2img):
            if self.anaconda.backend.mountInstallImage(self.anaconda, stage2img):
                self.anaconda.storage.umountFilesystems()
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
                msg = _("There was an error running your transaction for "
                        "the following reason: %s\n") % str(e)

                if self.anaconda.upgrade:
                    rc = intf.messageWindow(_("Error"), msg, type="custom",
                                            custom_icon="error",
                                            custom_buttons=[_("_Exit installer")])
                    sys.exit(1)
                else:
                    rc = intf.messageWindow(_("Error"), msg,
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

            spaceprob = to_unicode(spaceprob)
            fileprob = to_unicode(fileprob)

            if len(self.anaconda.backend.getRequiredMedia()) > 1 or self.anaconda.upgrade:
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

    def _pkgExists(self, pkg):
        """Whether or not a given package exists in our universe."""
        try:
            pkgs = self.pkgSack.returnNewestByName(pkg)
            return True
        except yum.Errors.PackageSackError:
            pass
        try:
            pkgs = self.rpmdb.returnNewestByName(pkg)
            return True
        except (IndexError, yum.Errors.PackageSackError):
            pass
        return False

    def _groupHasPackages(self, grp):
        # this checks to see if the given group has any packages available
        # (ie, already installed or in the sack of available packages)
        # so that we don't show empty groups.  also, if there are mandatory
        # packages and we have none of them, don't show
        for pkg in grp.mandatory_packages.keys():
            if self._pkgExists(pkg):
                return True
        if len(grp.mandatory_packages) > 0:
            return False
        for pkg in grp.default_packages.keys() + grp.optional_packages.keys():
            if self._pkgExists(pkg):
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

        if anaconda.proxy:
            buf += "proxy=%s\n" % anaconda.proxy

            if anaconda.proxyUsername:
                buf += "proxy_username=%s\n" % anaconda.proxyUsername

            if anaconda.proxyPassword:
                buf += "proxy_password=%s\n" % anaconda.proxyPassword

        fd = open("/tmp/anaconda-yum.conf", "w")
        fd.write(buf)
        fd.close()

    def complete(self, anaconda):
        if not anaconda.mediaDevice and os.path.ismount(self.ayum.tree):
            isys.umount(self.ayum.tree)

        anaconda.backend.removeInstallImage()

        # clean up rpmdb locks so that kickstart %post scripts aren't
        # unhappy (#496961)
        iutil.resetRpmDb(anaconda.rootPath)

    def doBackendSetup(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            return DISPATCH_BACK

        if anaconda.upgrade:
           # FIXME: make sure that the rpmdb doesn't have stale locks :/
           iutil.resetRpmDb(anaconda.rootPath)

        iutil.writeRpmPlatform()
        anaconda.backend.freetmp(anaconda)
        self.ayum = AnacondaYum(anaconda)
        self.ayum.setup()

        self.ayum.doMacros()

        # If any enabled repositories require networking, go ahead and bring
        # it up now.  No need to have people wait for the timeout when we
        # know this in advance.
        for repo in self.ayum.repos.listEnabled():
            if repo.needsNetwork() and not network.hasActiveNetDev():
                if not anaconda.intf.enableNetwork():
                    anaconda.intf.messageWindow(_("No Network Available"),
                        _("Some of your software repositories require "
                          "networking, but there was an error enabling the "
                          "network on your system."),
                        type="custom", custom_icon="error",
                        custom_buttons=[_("_Exit installer")])
                    sys.exit(1)

                urlgrabber.grabber.reset_curl_obj()
                break

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
                txt = _("Retrieving installation information.")
            else:
                txt = _("Retrieving installation information for %s.")%(repo.name)

            waitwin = anaconda.intf.waitWindow(_("Installation Progress"), txt)

            while True:
                try:
                    fn(repo)
                    waitwin.pop()
                except RepoError, e:
                    waitwin.pop()
                    buttons = [_("_Exit installer"), _("Edit"), _("_Retry")]
                else:
                    break # success

                if anaconda.ksdata:
                    buttons.append(_("_Continue"))

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
                    anaconda.intf.editRepoWindow(repo)
                    break
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

    def getDefaultGroups(self, anaconda):
        langs = anaconda.instLanguage.getCurrentLangSearchList()
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
        for grp in self.ayum.comps.groups:
            grp.selected = False

    def selectModulePackages(self, anaconda, kernelPkgName):
        (base, sep, ext) = kernelPkgName.partition("-")

        moduleProvides = []

        for (path, name) in anaconda.extraModules:
            if ext != "":
                moduleProvides.append("dud-%s-%s" % (name, ext))
            else:
                moduleProvides.append("dud-%s" % name)

        #We need to install the packages which contain modules from DriverDiscs
        for modPath in isys.modulesWithPaths():
            if modPath.startswith(DD_EXTRACTED):
                moduleProvides.append(modPath[len(DD_EXTRACTED):])
            else:
                continue

        for module in moduleProvides:
            pkgs = self.ayum.returnPackagesByDep(module)

            if not pkgs:
                log.warning("Didn't find any package providing %s" % module)

            for pkg in pkgs:
                log.info("selecting package %s for %s" % (pkg.name, module))
                self.ayum.install(po=pkg)

    def selectBestKernel(self, anaconda):
        """Find the best kernel package which is available and select it."""

        def getBestKernelByArch(pkgname, ayum):
            """Convenience func to find the best arch of a kernel by name"""
            try:
                pkgs = ayum.pkgSack.returnNewestByName(pkgname)
            except yum.Errors.PackageSackError:
                return None

            pkgs = self.ayum.bestPackagesFromList(pkgs)
            if len(pkgs) == 0:
                return None
            return pkgs[0]

        def selectKernel(pkgname):
            try:
                pkg = getBestKernelByArch(pkgname, self.ayum)
            except PackageSackError:
                log.debug("no %s package" % pkgname)
                return False

            if not pkg:
                return False

            log.info("selected %s package for kernel" % pkg.name)
            self.ayum.install(po=pkg)
            self.selectModulePackages(anaconda, pkg.name)

            if len(self.ayum.tsInfo.matchNaevr(name="gcc")) > 0:
                log.debug("selecting %s-devel" % pkg.name)
                self.selectPackage("%s-devel.%s" % (pkg.name, pkg.arch))

            return True

        foundkernel = False

        if not foundkernel and isys.isPaeAvailable():
            if selectKernel("kernel-PAE"):
                foundkernel = True

        if not foundkernel:
            selectKernel("kernel")

    def selectFSPackages(self, storage):
        for device in storage.fsset.devices:
            # this takes care of device and filesystem packages
            map(self.selectPackage, device.packages)

    # anaconda requires several programs on the installed system to complete
    # installation, but we have no guarantees that some of these will be
    # installed (they could have been removed in kickstart).  So we'll force
    # it.
    def selectAnacondaNeeds(self):
        for pkg in ['authconfig', 'chkconfig', 'system-config-firewall-base']:
            self.selectPackage(pkg)

    def doPostSelection(self, anaconda):
        # Only solve dependencies on the way through the installer, not the way back.
        if anaconda.dir == DISPATCH_BACK:
            return

        dscb = YumDepSolveProgress(anaconda.intf, self.ayum)
        self.ayum.dsCallback = dscb

        # do some sanity checks for kernel and bootloader
        if not anaconda.upgrade:
            # New installs only - upgrades will already have all this stuff.
            self.selectBestKernel(anaconda)
            map(self.selectPackage, anaconda.platform.packages)
            self.selectFSPackages(anaconda.storage)
            self.selectAnacondaNeeds()
        else:
            self.ayum.update()

        while True:
            try:
                (code, msgs) = self.ayum.buildTransaction()

                # If %packages --ignoremissing was given, don't bother
                # prompting for missing dependencies.
                if anaconda.ksdata and anaconda.ksdata.packages.handleMissing == KS_MISSING_IGNORE:
                    break

                if code == 1 and not anaconda.upgrade:
                    # resolveDeps returns 0 if empty transaction, 1 if error,
                    # 2 if success
                    depprob = "\n".join(msgs)

                    rc = anaconda.intf.detailedMessageWindow(_("Warning"),
                            _("Some of the packages you have selected for "
                              "install are missing dependencies.  You can "
                              "exit the installation, go back and change "
                              "your package selections, or continue "
                              "installing these packages without their "
                              "dependencies."),
                            depprob + "\n", type="custom", custom_icon="error",
                            custom_buttons=[_("_Exit installer"), _("_Back"),
                                            _("_Continue")])
                    dscb.pop()

                    if rc == 0:
                        sys.exit(1)
                    elif rc == 1:
                        self.ayum._undoDepInstalls()
                        return DISPATCH_BACK

                break
            except RepoError, e:
                # FIXME: would be nice to be able to recover here
                rc = anaconda.intf.messageWindow(_("Error"),
                               _("Unable to read package metadata. This may be "
                                 "due to a missing repodata directory.  Please "
                                 "ensure that your install tree has been "
                                 "correctly generated.\n\n%s" % e),
                                 type="custom", custom_icon="error",
                                 custom_buttons=[_("_Exit installer"), _("_Retry")])
                dscb.pop()

                if rc == 0:
                    sys.exit(0)
                else:
                    continue
            else:
                break

        (self.dlpkgs, self.totalSize, self.totalFiles)  = self.ayum.getDownloadPkgs()

        if not anaconda.upgrade:
            largePart = anaconda.storage.mountpoints.get("/usr", anaconda.storage.rootDevice)

            if largePart and largePart.size < self.totalSize / 1024:
                rc = anaconda.intf.messageWindow(_("Error"),
                                        _("Your selected packages require %d MB "
                                          "of free space for installation, but "
                                          "you do not have enough available.  "
                                          "You can change your selections or "
                                          "exit the installer." % (self.totalSize / 1024)),
                                        type="custom", custom_icon="error",
                                        custom_buttons=[_("_Back"), _("_Exit installer")])

                dscb.pop()

                if rc == 1:
                    sys.exit(1)
                else:
                    self.ayum._undoDepInstalls()
                    return DISPATCH_BACK

        dscb.pop()

        if anaconda.mediaDevice and not anaconda.ksdata:
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
            for d in ("/selinux", "/dev", "/proc/bus/usb"):
                try:
                    isys.umount(anaconda.rootPath + d, removeDir = False)
                except Exception, e:
                    log.error("unable to unmount %s: %s" %(d, e))
            return

        if anaconda.upgrade:
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
        for protected in anaconda.storage.protectedDevices:
            if getattr(protected.format, "mountpoint", None):
                dirList.append(protected.format.mountpoint)

        for i in dirList:
            try:
                os.mkdir(anaconda.rootPath + i)
            except os.error, (errno, msg):
                pass
#            log.error("Error making directory %s: %s" % (i, msg))

        self.initLog(anaconda.rootPath)

        # setup /etc/rpm/ for the post-install environment
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

        # write out the fstab
        if not anaconda.upgrade:
            anaconda.storage.fsset.write(anaconda.rootPath)
            if os.access("/etc/modprobe.d/anaconda.conf", os.R_OK):
                shutil.copyfile("/etc/modprobe.d/anaconda.conf", 
                                anaconda.rootPath + "/etc/modprobe.d/anaconda.conf")
            anaconda.network.write(instPath=anaconda.rootPath, anaconda=anaconda)
            anaconda.storage.write(anaconda.rootPath)
            if not anaconda.isHeadless:
                anaconda.keyboard.write(anaconda.rootPath)

        # make a /etc/mtab so mkinitrd can handle certain hw (usb) correctly
        f = open(anaconda.rootPath + "/etc/mtab", "w+")
        f.write(anaconda.storage.mtab)
        f.close()

    def checkSupportedUpgrade(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            return
        self._checkUpgradeVersion(anaconda)
        self._checkUpgradeArch(anaconda)

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

        if "Red Hat Enterprise Linux" not in productName:
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
                iutil.resetRpmDb(anaconda.rootPath)
                sys.exit(0)

    def _checkUpgradeArch(self, anaconda):
        def compareArch(a, b):
            if re.match("i.86", a) and re.match("i.86", b):
                return True
            else:
                return a == b

        # get the arch of the initscripts package
        try:
            pkgs = self.ayum.pkgSack.returnNewestByName('initscripts')
        except yum.Errors.PackageSackError:
            log.info("no packages named initscripts")
            return None

        pkgs = self.ayum.bestPackagesFromList(pkgs)
        if len(pkgs) == 0:
            log.info("no best package")
            return
        myarch = pkgs[0].arch

        log.info("initscripts is arch: %s" %(myarch,))
        for po in self.ayum.rpmdb.getProvides('initscripts'):
            log.info("po.arch is arch: %s" %(po.arch,))
            if not compareArch(po.arch, myarch):
                rc = anaconda.intf.messageWindow(_("Warning"),
                         _("The arch of the release of %(productName)s you "
                           "are upgrading to appears to be %(myarch)s which "
                           "does not match your previously installed arch of "
                           "%(arch)s.  This is likely to not succeed.  Are "
                           "you sure you wish to continue the upgrade "
                           "process?")
                         % {'productName': productName,
                            'myarch': myarch,
                            'arch': po.arch},
                         type="yesno")
                if rc == 0:
                    iutil.resetRpmDb(anaconda.rootPath)
                    sys.exit(0)
                else:
                    log.warning("upgrade between possibly incompatible "
                                "arches %s -> %s" %(po.arch, myarch))
                    break

    def doInstall(self, anaconda):
        log.info("Preparing to install packages")

        if not anaconda.upgrade:
            rpm.addMacro("__dbi_htconfig",
                         "hash nofsync %{__dbi_other} %{__dbi_perms}")

        if anaconda.ksdata and anaconda.ksdata.packages.excludeDocs:
            rpm.addMacro("_excludedocs", "1")

        cb = AnacondaCallback(self.ayum, anaconda,
                              self.instLog, self.modeText)
        cb.setSizes(len(self.dlpkgs), self.totalSize, self.totalFiles)

        rc = self.ayum.run(self.instLog, cb, anaconda.intf, anaconda.id)

        if cb.initWindow is not None:
            cb.initWindow.pop()

        self.instLog.write("*** FINISHED INSTALLING PACKAGES ***")
        self.instLog.close ()

        anaconda.intf.setInstallProgressClass(None)

        if rc == DISPATCH_BACK:
            return DISPATCH_BACK

    def doPostInstall(self, anaconda):
        if anaconda.upgrade:
            w = anaconda.intf.waitWindow(_("Post Upgrade"),
                                    _("Performing post-upgrade configuration"))
        else:
            w = anaconda.intf.waitWindow(_("Post Installation"),
                                    _("Performing post-installation configuration"))

        packages.rpmSetupGraphicalSystem(anaconda)

        for repo in self.ayum.repos.listEnabled():
            repo.dirCleanup()

        # expire yum caches on upgrade
        if anaconda.upgrade and os.path.exists("%s/var/cache/yum" %(anaconda.rootPath,)):
            log.info("Expiring yum caches")
            try:
                iutil.execWithRedirect("yum", ["clean", "all"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       root = anaconda.rootPath)
            except:
                pass

        # nuke preupgrade
        if flags.cmdline.has_key("preupgrade") and os.path.exists("%s/var/cache/yum/anaconda-upgrade" %(anaconda.rootPath,)):
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
                log.debug("no such group %s" % (gid,))
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
        if anaconda.ksdata:
            f.write(anaconda.ksdata.packages.__str__())
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

        f.write("%end")

    def writeConfiguration(self):
        return

    def getRequiredMedia(self):
        return self.ayum.tsInfo.reqmedia.keys()

class DownloadHeaderProgress:
    def __init__(self, intf, ayum=None):
        window = intf.progressWindow(_("Installation Starting"),
                                     _("Starting installation process"),
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
                                     _("Checking dependencies in packages selected for installation"),
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
