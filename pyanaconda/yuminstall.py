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

import ConfigParser
import sys
import os
import os.path
import shutil
import time
import types
import locale
import glob
import tempfile
import itertools
import re

class NoSuchGroup(Exception):
    pass

from flags import flags

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
from product import isFinal, productName, productVersion, productStamp
from constants import *
from image import *
import packages
from backend import AnacondaBackend

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

class NoSuchGroup(Exception):
    pass

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
        self.anaconda = anaconda
        self.repos = ayum.repos
        self.ts = ayum.ts
        self.ayum = ayum

        self.messageWindow = anaconda.intf.messageWindow
        self.progress = anaconda.intf.instProgress
        self.progressWindowClass = anaconda.intf.progressWindow
        self.rootPath = ROOT_PATH

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
            # Old-style (hdr, path) callback
            if isinstance(h, types.TupleType):
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
            # New-style callback, h is our txmbr
            else:
                po = h.po

            repo = self.repos.getRepo(po.repoid)

            pkgStr = "%s-%s-%s.%s" % (po.name, po.version, po.release, po.arch)

            if self.anaconda.upgrade:
                s = to_unicode(_("<b>Upgrading %(pkgStr)s</b> (%(size)s)\n")) \
                    % {'pkgStr': pkgStr, 'size': size_string(po.installedsize)}
            else:
                s = to_unicode(_("<b>Installing %(pkgStr)s</b> (%(size)s)\n")) \
                    % {'pkgStr': pkgStr, 'size': size_string(po.installedsize)}

            summary = to_unicode(gettext.ldgettext("redhat-dist", po.summary) or "")
            s += summary.strip()
            self.progress.set_label(s)

            self.instLog.write(self.modeText % (time.strftime("%H:%M:%S"), str(pkgStr)))

            self.instLog.flush()
            self.openfile = None

            while self.openfile is None:
                try:
                    fn = repo.getPackage(po)

                    f = open(fn, 'r')
                    self.openfile = f
                except (yum.Errors.NoMoreMirrorsRepoError, IOError):
                    self.ayum._handleFailure(po)
                except yum.Errors.RepoError:
                    continue
            self.inProgressPo = po

            return self.openfile.fileno()

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            if self.initWindow:
                self.initWindow.pop()
                self.initWindow = None

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

        elif what == rpm.RPMCALLBACK_UNINST_START:
            self.progress.set_text("")
            self.progress.set_label(_("<b>Cleaning up %s</b>" % h))

        elif what in (rpm.RPMCALLBACK_CPIO_ERROR,
                      rpm.RPMCALLBACK_UNPACK_ERROR,
                      rpm.RPMCALLBACK_SCRIPT_ERROR):
            # If this is a cleanup/remove, then h is just a string.
            # A tuple h means old-style (hdr, path) yum callback,
            # otherwise it's a new-style txmbr callback.
            if isinstance(h, basestring):
                name = h
            elif isinstance(h, types.TupleType):
                name = h[0]['name']
            else:
                name = h.name

            # Script errors store whether or not they're fatal in "total".  So,
            # we should only error out for fatal script errors or the cpio and
            # unpack problems.
            if what != rpm.RPMCALLBACK_SCRIPT_ERROR or total:
                if what == rpm.RPMCALLBACK_CPIO_ERROR:
                    error_type = _("cpio")
                elif what == rpm.RPMCALLBACK_UNPACK_ERROR:
                    error_type = _("unpack")
                else:
                    error_type = _("script")
                self.messageWindow(_("Error Installing Package"),
                    _("A %s error occurred when installing the %s "
                      "package.  This could indicate errors when reading "
                      "the installation media.  Installation cannot "
                      "continue.") % (error_type, name),
                    type="custom", custom_icon="error",
                    custom_buttons=[_("_Exit installer")])
                sys.exit(1)

        if self.initWindow is None:
            self.progress.processEvents()

class AnacondaYumRepo(YumRepository):
    def __init__(self, *args, **kwargs):
        YumRepository.__init__(self, *args, **kwargs)
        self.enablegroups = True
        self.sslverify = True
        self._anacondaBaseURLs = []
        self.proxy_url = None

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
            if not self.needsNetwork() or self.name == "Installation Repo" or self.id.startswith("anaconda-"):
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

class AnacondaYum(yum.YumBase):
    def __init__(self, anaconda):
        yum.YumBase.__init__(self)
        self.anaconda = anaconda
        self._timestamp = None

        self.repoIDcounter = itertools.count()

        # Only needed for hard drive and nfsiso installs.
        self.isodir = None

        # Only needed for media installs.
        self.mediagrabber = None

        # Where is the source media mounted?  This is the directory
        # where Packages/ is located.
        self.tree = "/mnt/install/source"

        if hasattr(self, "use_txmbr_in_callback"):
            log.debug("enabling new callback mode")
            self.use_txmbr_in_callback = True

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

        # Parse proxy values from anaconda
        self.proxy = None
        self.proxy_url = None
        self.proxy_username = None
        self.proxy_password = None
        if self.anaconda.proxy:
            self.setProxy(self.anaconda, self)

    def setup(self):
        # yum doesn't understand all our method URLs, so use this for all
        # except FTP and HTTP installs.
        self._baseRepoURL = "file://%s" % self.tree

        while True:
            try:
                self.configBaseURL()
                break
            except SystemError as exception:
                self.anaconda.methodstr = self.anaconda.intf.methodstrRepoWindow(self.anaconda.methodstr or "cdrom:",
                                                                                 exception)

        self.doConfigSetup(root=ROOT_PATH)
        if not self.anaconda.bootloader.update_only:
            self.conf.installonlypkgs = []

    def _mountInstallCD(self):
        if os.access("%s/.discinfo" % self.tree, os.R_OK):
            f = open("%s/.discinfo" % self.tree)
            self._timestamp = f.readline().strip()
            f.close()

        dev = self.anaconda.storage.devicetree.getDeviceByName(self.anaconda.mediaDevice)
        dev.format.mountpoint = self.tree

        # See if there's any media mounted on self.tree before continuing.
        # This saves a useless eject and insert if the user has already put
        # the disc in the drive.
        if not self.anaconda.storage.fsset.mountpoints.has_key(self.tree):
            try:
                dev.format.mount()

                if verifyMedia(self.tree, None):
                    return

                dev.format.unmount()
            except Exception:
                pass
        else:
            if verifyMedia(self.tree, None):
                return

        dev.format.unmount()

        log.error("Wrong disc found on %s" % (self.tree))
        if self.anaconda.intf:
            self.anaconda.intf.beep()

            self.messageWindow(_("Wrong Disc"),
                _("That's not the correct %s disc.") % (productName),
                type="custom", custom_icon="error",
                custom_buttons=[_("_Exit installer")])
        sys.exit(1)

    def _mountInstallImage(self):
        umountImage(self.tree)

        # mountDirectory checks before doing anything, so it's safe to
        # call this repeatedly.
        mountDirectory(self.anaconda.methodstr, self.anaconda.intf.messageWindow)
        mountImage(self.isodir, self.tree, self.anaconda.intf.messageWindow)

    def configBaseURL(self):
        # We only have a methodstr if method= or repo= was passed to
        # anaconda.  No source for this base repo (the CD media, NFS,
        # whatever) is mounted yet since initramfs only mounts the source
        # for the stage2 image.  We need to set up the source mount
        # now.
        # methodstr == cdrom is a special case, meaning the first cdrom found
        # by scanning or previously mounted as the install source.
        if flags.cmdline.has_key("preupgrade"):
            path = "/var/cache/yum/preupgrade"
            self.anaconda.methodstr = "hd::%s" % path 
            self._baseRepoURL = "file:///mnt/sysimage/%s" % path
        elif self.anaconda.methodstr and self.anaconda.methodstr != "cdrom":
            m = self.anaconda.methodstr

            if m.startswith("hd:"):
                if m.count(":") == 2:
                    (device, path) = m[3:].split(":")
                else:
                    (device, fstype, path) = m[3:].split(":")

                self.isodir = "/mnt/install/isodir/%s" % path

                # This takes care of mounting /mnt/install/isodir first.
                self._mountInstallImage()
                self.mediagrabber = self.mediaHandler
            elif m.startswith("nfsiso:"):
                self.isodir = "/mnt/install/isodir"

                # Calling _mountInstallImage takes care of mounting /mnt/install/isodir first.
                if not network.hasActiveNetDev():
                    if not self.anaconda.intf.enableNetwork():
                        self._baseRepoURL = None
                        return

                self._mountInstallImage()
                self.mediagrabber = self.mediaHandler
            elif m.startswith("http") or m.startswith("ftp:"):
                self._baseRepoURL = m
            elif m.startswith("nfs:"):
                if not network.hasActiveNetDev():
                    if not self.anaconda.intf.enableNetwork():
                        self._baseRepoURL = None

                (opts, server, path) = iutil.parseNfsUrl(m)
                isys.mount(server+":"+path, self.tree, "nfs", options=opts)

                # This really should be fixed in initrd instead but for now see
                # if there's images and if so go with this being an NFSISO
                # install instead.
                image = findFirstIsoImage(self.tree, self.anaconda.intf.messageWindow)
                if image:
                    isys.umount(self.tree, removeDir=False)
                    self.anaconda.methodstr = "nfsiso:%s" % m[4:]
                    self.configBaseURL()
                    return
            elif m.startswith("cdrom:"):
                self._mountInstallCD()
                self.mediagrabber = self.mediaHandler
                self._baseRepoURL = "file://%s" % self.tree
        elif os.path.isdir("/run/initramfs/live/repodata"):
            # No methodstr was given.  In order to find an installation source
            # we first check to see if dracut has already mounted the source
            # on /run/initramfs/live/ and if not we check to see if there's a
            # CD/DVD with packages on it. If both those fail we default to the
            # mirrorlist URL.  The user can always change the repo with the
            # repo editor later.
            isys.mount("/run/initramfs/live/", self.tree, bindMount=True)
            self.mediagrabber = self.mediaHandler
            self._baseRepoURL = "file://%s" % self.tree
        elif os.path.isdir("/run/install/repo/repodata"):
            # Same hack as above. FIXME: make scanForMedia do this, dammit
            isys.mount("/run/install/repo", self.tree, bindMount=True)
            self.mediagrabber = self.mediaHandler
            self._baseRepoURL = "file://%s" % self.tree
        else:
            # No methodstr was given.  In order to find an installation source,
            # we should first check to see if there's a CD/DVD with packages
            # on it, and then default to the mirrorlist URL.  The user can
            # always change the repo with the repo editor later.
            cdrs = opticalInstallMedia(self.anaconda.storage.devicetree, self.tree)
            if cdrs:
                self.mediagrabber = self.mediaHandler
                self.anaconda.mediaDevice = cdrs[0].name
                log.info("found installation media on %s" % cdrs[0].name)
            else:
                # No CD with media on it and no repo=/method= parameter, so
                # default to using whatever's enabled in /etc/yum.repos.d/
                self._baseRepoURL = None

    def configBaseRepo(self):
        # Create the "base" repo object, assuming there is one.  Otherwise we
        # just skip all this and use the defaults from /etc/yum.repos.d.
        if not self._baseRepoURL:
            return

        # add default repos
        anacondabaseurl = (self.anaconda.methodstr or
                           "cdrom:%s" % (self.anaconda.mediaDevice))
        anacondabasepaths = self.anaconda.instClass.getPackagePaths(anacondabaseurl)
        for (name, uri) in self.anaconda.instClass.getPackagePaths(self._baseRepoURL).items():
            repo = AnacondaYumRepo("anaconda-%s" % self.repoIDcounter.next())
            repo.baseurl = uri
            repo.anacondaBaseURLs = anacondabasepaths[name]

            repo.name = name
            repo.cost = 100

            if self.anaconda.mediaDevice or self.isodir:
                repo.mediaid = getMediaId(self.tree)
                log.info("set mediaid of repo %s to: %s" % (repo.name, repo.mediaid))

            if self.anaconda.proxy:
                self.setProxy(self.anaconda, repo)

            if flags.noverifyssl:
                repo.sslverify = False

            repo.enable()
            self.repos.add(repo)

    def mediaHandler(self, *args, **kwargs):
        relative = kwargs["relative"]

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
        if isFinal and ("rawhide" in repo.id or "development" in repo.id):
            name = repo.name
            del(repo)
            raise RepoError, "Excluding devel repo %s for non-devel anaconda" % name

        if not isFinal and not repo.enabled:
            name = repo.name
            del(repo)
            raise RepoError, "Excluding disabled repo %s for prerelease" % name

        # If repo=/method= was passed in, we want to default these extra
        # repos to off.
        if self._baseRepoURL:
            repo.enabled = False

        return repo

    def setProxy(self, src, dest):
        """
        Set the proxy settings from a string in src.proxy
        If the string includes un/pw use those, otherwise set the un/pw from
        src.proxyUsername and src.proxyPassword

        dest has dest.proxy set to the host and port (no un/pw)
        dest.proxy_username and dest.proxy_password are set if present in src
        """
        # NOTE: If this changes, update tests/regex/proxy.py
        #
        # proxy=[protocol://][username[:password]@]host[:port][path]
        pattern = re.compile("([A-Za-z]+://)?(([A-Za-z0-9]+)(:[^:@]+)?@)?([^:/]+)(:[0-9]+)?(/.*)?")

        m = pattern.match(src.proxy)

        if m and m.group(3):
            dest.proxy_username = m.group(3)
        elif getattr(src, "proxyUsername", None):
            dest.proxy_username = src.proxyUsername

        if m and m.group(4):
            # Skip the leading colon.
            dest.proxy_password = m.group(4)[1:]
        elif getattr(src, "proxyPassword", None):
            dest.proxy_password = src.proxyPassword

        if dest.proxy_username or dest.proxy_password:
            proxy_auth = "%s:%s@" % (dest.proxy_username or '',
                                     dest.proxy_password or '')
        else:
            proxy_auth = ""

        if m and m.group(5):
            # If both a host and port was found, just paste them
            # together using the colon at the beginning of the port
            # match as a separator.  Otherwise, just use the host.
            if m.group(6):
                proxy = m.group(5) + m.group(6)
            else:
                proxy = m.group(5)

            # yum also requires a protocol.  If none was given,
            # default to http.
            if m.group(1):
                dest.proxy_url = m.group(1) + proxy_auth + proxy
                proxy = m.group(1) + proxy
            else:
                dest.proxy_url = "http://" + proxy_auth + proxy
                proxy = "http://" + proxy

            # Set the repo proxy. NOTE: yum immediately parses this and
            # raises an error if it isn't correct
            dest.proxy = proxy

    def _getAddons(self, baseurl, proxy_url, sslverify):
        """
        Check the baseurl or mirrorlist for a repository, see if it has any
        valid addon repos and if so, return a list of (repo name, repo URL).
        """
        retval = []
        c = ConfigParser.ConfigParser()

        # If there's no .treeinfo for this repo, don't bother looking for addons.
        treeinfo = self._getTreeinfo(baseurl, proxy_url, sslverify)
        if not treeinfo:
            return retval

        # We need to know which variant is being installed so we know what addons
        # are valid options.
        try:
            ConfigParser.ConfigParser.read(c, treeinfo)
            variant = c.get("general", "variant")
        except ConfigParser.Error:
            return retval

        section = "variant-%s" % variant
        if c.has_section(section) and c.has_option(section, "addons"):
            validAddons = c.get(section, "addons").split(",")
        else:
            return retval

        for addon in validAddons:
            addonSection = "addon-%s" % addon
            if not c.has_section(addonSection) or not c.has_option(addonSection, "repository"):
                continue

            url = "%s/%s" % (baseurl, c.get(addonSection, "repository"))
            retval.append((addon, c.get(addonSection, "name"), url))

        return retval

    def _getTreeinfo(self, baseurl, proxy_url, sslverify):
        """
        Try to get .treeinfo file from baseurl, optionally using proxy_url
        Saves the file into /tmp/.treeinfo
        """
        if not baseurl:
            return None
        if baseurl.startswith("http") or baseurl.startswith("ftp"):
            if not network.hasActiveNetDev():
                if not self.anaconda.intf.enableNetwork():
                    log.error("Error downloading %s/.treeinfo: network enablement failed" % (baseurl))
                    return None
        ug = URLGrabber()
        ugopts = {
            "ssl_verify_peer" : sslverify,
            "ssl_verify_host" : sslverify
        }

        if proxy_url:
            proxies = { 'http'  : proxy_url,
                        'https' : proxy_url }
        else:
            proxies = {}

        try:
            ug.urlgrab("%s/.treeinfo" % baseurl, "/tmp/.treeinfo",
                       copy_local=1, proxies=proxies, **ugopts)
        except Exception as e:
            try:
                ug.urlgrab("%s/treeinfo" % baseurl, "/tmp/.treeinfo",
                           copy_local=1, proxies=proxies)
            except Exception as e:
                log.info("Error downloading treeinfo: %s" % e)
                return None

        return "/tmp/.treeinfo"

    def _getReleasever(self):
        """
        We need to make sure $releasever gets set up before .repo files are
        read.  Since there's no redhat-release package in /mnt/sysimage (and
        won't be for quite a while), we need to do our own substutition.
        """
        c = ConfigParser.ConfigParser()

        treeinfo = self._getTreeinfo(self._baseRepoURL,
                                     self.proxy_url,
                                     not flags.noverifyssl)
        if not treeinfo:
            return productVersion.split('-')[0]

        ConfigParser.ConfigParser.read(c, treeinfo)
        try:
            ver = c.get("general", "version")
            # Trim off any -Alpha or -Beta
            return ver.split('-')[0]
        except ConfigParser.Error:
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

    def doFileLogSetup(self, uid, logfile):
        # don't do the file log as it can lead to open fds
        # being left and an inability to clean up after ourself
        pass

    def doConfigSetup(self, fn='/tmp/anaconda-yum.conf', root='/'):
        if hasattr(self, "preconf"):
            self.preconf.fn = fn
            self.preconf.root = root
            self.preconf.releasever = self._getReleasever()
            self.preconf.enabled_plugins = ["whiteout", "blacklist"]
            yum.YumBase._getConfig(self)
        else:
            yum.YumBase._getConfig(self, fn=fn, root=root,
                                 enabled_plugins=["whiteout", "blacklist"])
        self.configBaseRepo()

        extraRepos = []

        ddArch = os.uname()[4]

        #Add the Driver disc repos to Yum
        for d in glob.glob(DD_RPMS):
            dirname = os.path.basename(d)

            repo = AnacondaYumRepo("anaconda-%s" % self.repoIDcounter.next())
            repo.baseurl = [ "file://%s" % d ]
            repo.name = "Driver Disk %s" % dirname.split("-")[1]
            repo.enable()
            extraRepos.append(repo)

        if self.anaconda.ksdata:
            for ksrepo in self.anaconda.ksdata.repo.repoList:
                # If no location was given, this must be a repo pre-configured
                # through /etc/yum.repos.d that we just want to enable.
                if not ksrepo.baseurl and not ksrepo.mirrorlist:
                    try:
                        repo = self.repos.getRepo(ksrepo.name)
                        repo.enable()
                        log.info("enabled repository %s with URL %s" % (repo.name, repo.mirrorlist or repo.baseurl[0]))
                    except RepoError:
                        log.error("Could not find the pre-configured repo %s, skipping" % ksrepo.name)

                    continue

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
                repo.yumvar.update(self.conf.yumvar)
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
                    repo.includepkgs = ksrepo.includepkgs

                if ksrepo.noverifyssl:
                    repo.sslverify = False

                if ksrepo.proxy:
                    self.setProxy(ksrepo, repo)

                repo.enable()
                extraRepos.append(repo)

        initialRepos = self.repos.repos.values() + extraRepos
        for repo in filter(lambda r: r.isEnabled(), initialRepos):
            addons = self._getAddons(repo.mirrorlist or repo.baseurl[0],
                                     repo.proxy_url or self.proxy_url,
                                     repo.sslverify)
            for addon in addons:
                addonRepo = AnacondaYumRepo(addon[0])
                addonRepo.name = addon[1]
                addonRepo.baseurl = [ addon[2] ]

                addonRepo.enable()

                if self.anaconda.proxy:
                    self.setProxy(self.anaconda, addonRepo)

                extraRepos.append(addonRepo)

        for repo in extraRepos:
            try:
                self.repos.add(repo)
                log.info("added repository %s with URL %s" % (repo.name, repo.mirrorlist or repo.baseurl[0]))
            except yum.Errors.DuplicateRepoError:
                log.warning("ignoring duplicate repository %s with URL %s" % (repo.name, repo.mirrorlist or repo.baseurl[0]))

        self.repos.setCacheDir(self.conf.cachedir)

    def downloadHeader(self, po):
        while True:
            # retrying version of download header
            try:
                yum.YumBase.downloadHeader(self, po)
                break
            except (yum.Errors.NoMoreMirrorsRepoError, IOError):
                self._handleFailure(po)
            except yum.Errors.RepoError:
                continue

    def _handleFailure(self, package):
        if package.repo.anacondaBaseURLs[0].startswith("cdrom:"):
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

            if package.repo.anacondaBaseURLs[0].startswith("cdrom:"):
                self._mountInstallCD()
            else:
                return

    def mirrorFailureCB (self, obj, *args, **kwargs):
        # This gets called when a mirror fails, but it cannot know whether
        # or not there are other mirrors left to try, since it cannot know
        # which mirror we were on when we started this particular download. 
        # Whenever we have run out of mirrors the grabber's get/open/retrieve
        # method will raise a URLGrabError exception with errno 256.
        repo = self.repos.getRepo(kwargs["repo"])
        log.warning("Failed to get %s from mirror %d/%d, "
                    "or downloaded file is corrupt" % (obj.url, repo.grab._next + 1,
                                                       len(repo.grab.mirrors)))

        if repo.anacondaBaseURLs[0].startswith("cdrom:"):
            dev = self.anaconda.storage.devicetree.getDeviceByName(self.anaconda.mediaDevice)
            dev.format.mountpoint = self.tree
            unmountCD(dev, self.anaconda.intf.messageWindow)

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

    def run(self, instLog, cb, intf):
        self.initActionTs()
        if self.anaconda.upgrade:
            self.ts.ts.setProbFilter(~rpm.RPMPROB_FILTER_DISKSPACE)
        self.setColor()

        try:
            self.dsCallback = DownloadHeaderProgress(intf, self)
            self.populateTs(keepold=0)
            self.dsCallback.pop()
            self.dsCallback = None
        except RepoError as e:
            msg = _("There was an error running your transaction for "
                    "the following reason: %s\n") % str(e)

            if self.anaconda.upgrade or self.anaconda.ksdata:
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
                return DISPATCH_BACK

        self.ts.check()
        self.ts.order()
        self.ts.clean()

        self.anaconda.bootloader.trusted_boot = self.isPackageInstalled(name="tboot")

        if self._run(instLog, cb, intf) == DISPATCH_BACK:
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
        except PackageSackError as e:
            log.error("AnacondaYum._run: PackageSackError: %s" % e)
            msg = _("There was an error running your transaction for "
                    "the following reason: %s.\n") % str(e)
            intf.messageWindow(_("Error Running Transaction"),
                               msg, type="custom",
                               custom_icon="error", custom_buttons=[_("_Exit installer")])
            sys.exit(1)
        except YumBaseError as probs:
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

            if self.anaconda.upgrade or self.anaconda.ksdata:
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
        for pkg in grp.default_packages.keys() + grp.optional_packages.keys() + \
                   grp.conditional_packages.keys():
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
cachedir=/var/cache/yum/$basearch/$releasever
keepcache=0
logfile=/tmp/yum.log
metadata_expire=0
obsoletes=True
pluginpath=/usr/lib/yum-plugins,/tmp/updates/yum-plugins
pluginconfpath=/etc/yum/pluginconf.d,/tmp/updates/pluginconf.d
plugins=1
reposdir=/etc/anaconda.repos.d,/tmp/updates/anaconda.repos.d,/tmp/product/anaconda.repos.d
""" % (ROOT_PATH)

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

        # clean up rpmdb locks so that kickstart %post scripts aren't
        # unhappy (#496961)
        iutil.resetRpmDb()

        if os.access(ROOT_PATH + "/tmp/yum.log", os.R_OK):
            os.unlink(ROOT_PATH + "/tmp/yum.log")

        self.ayum.history.close()

    def doBackendSetup(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            return DISPATCH_BACK

        if anaconda.upgrade:
           # FIXME: make sure that the rpmdb doesn't have stale locks :/
           iutil.resetRpmDb()

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
                break

        self.doRepoSetup(anaconda)
        self.doSackSetup(anaconda)
        self.doGroupSetup(anaconda)

        self.ayum.doMacros()

    def doGroupSetup(self, anaconda):
        while True:
            try:
                self.ayum.doGroupSetup()
            except (GroupsError, NoSuchGroup, RepoError) as e:
                buttons = [_("_Exit installer"), _("_Retry")]
                log.error("Unable to read group information: %s" % e)
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
                          thisrepo=thisrepo, fatalerrors=fatalerrors,
                          callback=RepoSetupPulseProgress(anaconda.intf))

    def doSackSetup(self, anaconda, thisrepo = None, fatalerrors = True):
        self.__withFuncDo(anaconda, lambda r: self.ayum.doSackSetup(thisrepo=r.id),
                          thisrepo=thisrepo, fatalerrors=fatalerrors,
                          callback=SackSetupProgress(anaconda.intf))

    def __withFuncDo(self, anaconda, fn, thisrepo=None, fatalerrors=True,
                     callback=None):
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
            if callback:
                callback.connect(repo)

            while True:
                try:
                    fn(repo)
                    if callback:
                        callback.disconnect()
                except RepoError as e:
                    if callback:
                        callback.disconnect()
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
        self.ayum.tsInfo.conditionals.clear()
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
            log.debug("Checking for DUD module "+modPath)
            match = DD_EXTRACTED.match(modPath)
            if match:
                log.info("Requesting install of kmod-%s" % (match.group("modulename")))
                moduleProvides.append("kmod-"+match.group("modulename"))
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

        if not foundkernel and iutil.isARM():
            if anaconda.platform.armMachine is not None:
                selectKernel("kernel-%s" % anaconda.platform.armMachine)
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
            map(self.selectPackage, anaconda.bootloader.packages)
            self.selectFSPackages(anaconda.storage)
            self.selectAnacondaNeeds()
        else:
            if not anaconda.bootloader.skip_bootloader:
                map(self.deselectPackage, anaconda.bootloader.obsoletes)
                map(self.selectPackage, anaconda.bootloader.packages)

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

                    for m in msgs:
                        log.warning(m)

                    custom_buttons = [_("_Exit installer"), _("_Continue")]
                    if not anaconda.ksdata:
                        custom_buttons.insert(1, _("_Back"))

                    rc = anaconda.intf.detailedMessageWindow(_("Warning"),
                            _("Some of the packages you have selected for "
                              "install are missing dependencies.  You can "
                              "exit the installation, go back and change "
                              "your package selections, or continue "
                              "installing these packages without their "
                              "dependencies.  If you continue, these packages "
                              "may not work correctly due to missing components."),
                            depprob + "\n", type="custom", custom_icon="error",
                            custom_buttons=custom_buttons)
                    dscb.pop()

                    if rc == 0:
                        sys.exit(1)
                    elif rc == 1 and not anaconda.ksdata:
                        self.ayum._undoDepInstalls()
                        return DISPATCH_BACK

                break
            except RepoError as e:
                log.critical(e)

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
        self.ayum.dsCallback = None

    def doPreInstall(self, anaconda):
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
                os.mkdir(ROOT_PATH + i)
            except OSError:
                pass
#            log.error("Error making directory %s: %s" % (i, msg))

        self.initLog(ROOT_PATH)

        # write out the fstab
        if not anaconda.upgrade:
            anaconda.storage.fsset.write()
            if os.access("/etc/modprobe.d/anaconda.conf", os.R_OK):
                shutil.copyfile("/etc/modprobe.d/anaconda.conf", 
                                ROOT_PATH + "/etc/modprobe.d/anaconda.conf")
            network.write_sysconfig_network()
            network.disableIPV6()
            network.copyConfigToPath(ROOT_PATH)
            if not anaconda.ksdata:
                anaconda.instClass.setNetworkOnbootDefault()
            anaconda.storage.write()
        else:
            # ensure that /etc/mtab is a symlink to /proc/self/mounts
            anaconda.storage.makeMtab()

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

        rc = self.ayum.run(self.instLog, cb, anaconda.intf)

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
        if anaconda.upgrade and os.path.exists("%s/var/cache/yum" %(ROOT_PATH,)):
            log.info("Expiring yum caches")
            try:
                iutil.execWithRedirect("yum", ["clean", "all"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       root = ROOT_PATH)
            except RuntimeError:
                pass

        # nuke preupgrade
        if flags.cmdline.has_key("preupgrade") and os.path.exists("%s/var/cache/yum/anaconda-upgrade" %(ROOT_PATH,)):
            try:
                shutil.rmtree("%s/var/cache/yum/anaconda-upgrade" %(ROOT_PATH,))
            except (OSError, IOError):
                pass

        # XXX: write proper lvm config

        AnacondaBackend.doPostInstall(self, anaconda)
        w.pop()

    def kernelVersionList(self):
        # FIXME: using rpm here is a little lame, but otherwise, we'd
        # be pulling in filelists
        return packages.rpmKernelVersionList()

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
        except yum.Errors.GroupsError:
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
        except yum.Errors.GroupsError:
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
            self.ayum.deselectGroup(group, force=True)
        except yum.Errors.GroupsError:
            # try to find out if it's the name or translated name
            gid = self.__getGroupId(group)
            if gid is not None:
                self.ayum.deselectGroup(gid, force=True)
            else:
                log.debug("no such group %s" %(group,))

    def selectPackage(self, pkg, *args):
        if self.ayum.tsInfo.matchNaevr(name=pkg):
            return 0

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

    def writeConfiguration(self):
        return

    def postAction(self, anaconda):
        self.ayum.close()
        self.ayum.closeRpmDB()
        iutil.resetRpmDb()

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

# We don't have reasonable hook for sackSetup, and it
# is fairly fast, so we use just waitWindow here
class SackSetupProgress:
    def __init__(self, intf):
        self.intf = intf

    def connect(self, repo):
        if repo.name is None:
            txt = _("Retrieving installation information.")
        else:
            txt = _("Retrieving installation information for %s.")%(repo.name)
        self.window = self.intf.waitWindow(_("Installation Progress"), txt)

    def disconnect(self):
        self.window.pop()

class RepoSetupPulseProgress:
    def __init__(self, intf):
        self.intf = intf
        self.repo = None

    def connect(self, repo):
        self.repo = repo
        if repo.name is None:
            txt = _("Retrieving installation information.")
        else:
            txt = _("Retrieving installation information for %s.")%(repo.name)
        self.window = self.intf.progressWindow(_("Installation Progress"),
                                               txt,
                                               1.0, pulse=True)
        repo.setCallback(self)

    def disconnect(self):
        self.window.pop()
        self.repo.setCallback(None)

    def refresh(self, *args):
        self.window.refresh()

    def set(self):
        self.window.pulse()

    def start(self, filename, url, basename, size, text):
        log.debug("Grabbing  %s" % url)
        self.set()
        self.refresh()

    def update(self, read):
        self.set()
        self.refresh()

    def end(self, read):
        self.set()
        self.window.refresh()
