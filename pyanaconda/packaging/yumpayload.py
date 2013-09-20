# yumpayload.py
# Yum/rpm software payload management.
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#                    Chris Lumens <clumens@redhat.com>
#

"""
    TODO
        - document all methods
        - YumPayload
            - write test cases
            - more logging in key methods
            - handling of proxy needs cleanup
                - passed to anaconda as --proxy, --proxyUsername, and
                  --proxyPassword
                    - drop the use of a file for proxy and ftp auth info
                - specified via KS as a URL

"""

import ConfigParser
import os
import shutil
import sys
import time
from pyanaconda.iutil import execReadlines

import logging
log = logging.getLogger("packaging")

try:
    import rpm
except ImportError:
    log.error("import of rpm failed")
    rpm = None

try:
    import yum
    # This is a bit of a hack to short circuit yum's internal logging
    # handler setup.  We already set one up so we don't need it to run.
    # yum may give us an API to fiddle this at a later time.
    yum.logginglevels._added_handlers = True
except ImportError:
    log.error("import of yum failed")
    yum = None

from pyanaconda.constants import BASE_REPO_NAME, DRACUT_ISODIR, INSTALL_TREE, ISO_DIR, MOUNT_DIR, ROOT_PATH
from pyanaconda.flags import flags

from pyanaconda import iutil
from pyanaconda.iutil import ProxyString, ProxyStringError
from pyanaconda.i18n import _
from pyanaconda.nm import nm_is_connected
from pyanaconda.product import productName, isFinal
from blivet.size import Size
import blivet.util
import blivet.arch

from pyanaconda.errors import ERROR_RAISE, errorHandler
from pyanaconda.packaging import DependencyError, MetadataError, NoNetworkError, NoSuchGroup, \
                                 NoSuchPackage, PackagePayload, PayloadError, PayloadInstallError, \
                                 PayloadSetupError
from pyanaconda.progress import progressQ

from pyanaconda.localization import langcode_matches_locale

from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, KS_MISSING_IGNORE

YUM_PLUGINS = ["blacklist", "whiteout", "fastestmirror", "langpacks"]
default_repos = [productName.lower(), "rawhide"]

import inspect
import threading
_private_yum_lock = threading.RLock()

class YumLock(object):
    def __enter__(self):
        if isFinal:
            _private_yum_lock.acquire()
            return _private_yum_lock

        frame = inspect.stack()[2]
        threadName = threading.currentThread().name

        log.info("about to acquire _yum_lock for %s at %s:%s (%s)", threadName, frame[1], frame[2], frame[3])
        _private_yum_lock.acquire()
        log.info("have _yum_lock for %s", threadName)
        return _private_yum_lock

    def __exit__(self, exc_type, exc_val, exc_tb):
        _private_yum_lock.release()

        if not isFinal:
            log.info("gave up _yum_lock for %s", threading.currentThread().name)

_yum_lock = YumLock()
_yum_cache_dir = "/tmp/yum.cache"

class YumPayload(PackagePayload):
    """ A YumPayload installs packages onto the target system using yum.

        User-defined (aka: addon) repos exist both in ksdata and in yum. They
        are the only repos in ksdata.repo. The repos we find in the yum config
        only exist in yum. Lastly, the base repo exists in yum and in
        ksdata.method.
    """
    def __init__(self, data):
        if rpm is None or yum is None:
            raise PayloadError("unsupported payload type")

        PackagePayload.__init__(self, data)

        self._root_dir = "/tmp/yum.root"
        self._repos_dir = "/etc/yum.repos.d,/etc/anaconda.repos.d,/tmp/updates/anaconda.repos.d,/tmp/product/anaconda.repos.d"
        self._yum = None
        self._setup = False

        self._requiredPackages = []
        self._requiredGroups = []

        self.reset()

    def reset(self, root=None):
        """ Reset this instance to its initial (unconfigured) state. """

        super(YumPayload, self).reset()
        # This value comes from a default install of the x86_64 Fedora 18.  It
        # is meant as a best first guess only.  Once package metadata is
        # available we can use that as a better value.
        self._space_required = Size(spec="3000 MB")

        self._groups = None
        self._packages = []

        self._resetYum(root=root)

    def setup(self, storage):
        super(YumPayload, self).setup(storage)

        self._writeYumConfig()
        self._setup = True

        self.updateBaseRepo(fallback=not flags.automatedInstall)

        # When setup is called, it's already in a separate thread. That thread
        # will try to select groups right after this returns, so make sure we
        # have group info ready.
        self.gatherRepoMetadata()

    def _resetYum(self, root=None, keep_cache=False):
        """ Delete and recreate the payload's YumBase instance. """
        if root is None:
            root = self._root_dir

        with _yum_lock:
            if self._yum:
                if not keep_cache:
                    for repo in self._yum.repos.listEnabled():
                        if repo.name == BASE_REPO_NAME and \
                           os.path.isdir(repo.cachedir):
                            shutil.rmtree(repo.cachedir)

                del self._yum

            self._writeYumConfig()
            self._yum = yum.YumBase()

            self._yum.use_txmbr_in_callback = True

            # Set some configuration parameters that don't get set through a config
            # file.  yum will know what to do with these.
            # Enable all types of yum plugins. We're somewhat careful about what
            # plugins we put in the environment.
            self._yum.preconf.plugin_types = yum.plugins.ALL_TYPES
            self._yum.preconf.enabled_plugins = YUM_PLUGINS
            self._yum.preconf.fn = "/tmp/anaconda-yum.conf"
            self._yum.preconf.root = root
            # set this now to the best default we've got ; we'll update it if/when
            # we get a base repo set up
            self._yum.preconf.releasever = self._getReleaseVersion(None)

        self.txID = None

    def _writeLangpacksConfig(self):
        langs = [self.data.lang.lang] + self.data.lang.addsupport
        log.debug("configuring langpacks for %s", langs)
        with open("/etc/yum/pluginconf.d/langpacks.conf", "a") as f:
            f.write("# Added by Anaconda\n")
            f.write("langpack_locales = %s\n" % ", ".join(langs))

    def _writeYumConfig(self):
        """ Write out anaconda's main yum configuration file. """
        buf = """
[main]
cachedir=%s
keepcache=0
logfile=/tmp/yum.log
metadata_expire=never
pluginpath=/usr/lib/yum-plugins,/tmp/updates/yum-plugins
pluginconfpath=/etc/yum/pluginconf.d,/tmp/updates/pluginconf.d
plugins=1
debuglevel=3
errorlevel=6
reposdir=%s
""" % (_yum_cache_dir, self._repos_dir)

        if flags.noverifyssl:
            buf += "sslverify=0\n"

        if self.data.packages.multiLib:
            buf += "multilib_policy=all\n"

        if hasattr(self.data.method, "proxy") and self.data.method.proxy:
            try:
                proxy = ProxyString(self.data.method.proxy)
                buf += "proxy=%s\n" % (proxy.noauth_url,)
                if proxy.username:
                    buf += "proxy_username=%s\n" % (proxy.username,)
                if proxy.password:
                    buf += "proxy_password=%s\n" % (proxy.password,)
            except ProxyStringError as e:
                log.error("Failed to parse proxy for _writeYumConfig %s: %s",
                          self.data.method.proxy, e)

        open("/tmp/anaconda-yum.conf", "w").write(buf)

    # YUMFIXME: yum should allow a cache dir outside of the installroot
    def _yumCacheDirHack(self):
        # This is what it takes to get yum to use a cache dir outside the
        # install root. We do this so we don't have to re-gather repo meta-
        # data after we change the install root to ROOT_PATH, which can only
        # happen after we've enabled the new storage configuration.
        with _yum_lock:
            if not self._yum.conf.cachedir.startswith(self._yum.conf.installroot):
                return

            root = self._yum.conf.installroot
            self._yum.conf.cachedir = self._yum.conf.cachedir[len(root):]

    def _writeInstallConfig(self):
        """ Write out the yum config that will be used to install packages.

            Write out repo config files for all enabled repos, then
            create a new YumBase instance with the new filesystem tree as its
            install root.

            This needs to be called from inside a yum_lock
        """
        self._repos_dir = "/tmp/yum.repos.d"
        if not os.path.isdir(self._repos_dir):
            os.mkdir(self._repos_dir)

        for repo in self._yum.repos.listEnabled():
            cfg_path = "%s/%s.repo" % (self._repos_dir, repo.id)
            ks_repo = self.getAddOnRepo(repo.id)
            with open(cfg_path, "w") as f:
                f.write("[%s]\n" % repo.id)
                f.write("name=Install - %s\n" % repo.id)
                f.write("enabled=1\n")
                if repo.mirrorlist:
                    f.write("mirrorlist=%s" % repo.mirrorlist)
                elif repo.metalink:
                    f.write("metalink=%s" % repo.metalink)
                elif repo.baseurl:
                    f.write("baseurl=%s\n" % repo.baseurl[0])
                else:
                    log.error("repo %s has no baseurl, mirrorlist or metalink", repo.id)
                    f.close()
                    os.unlink(cfg_path)
                    continue

                # kickstart repo modifiers
                if ks_repo:
                    if ks_repo.noverifyssl:
                        f.write("sslverify=0\n")

                    if ks_repo.proxy:
                        try:
                            proxy = ProxyString(ks_repo.proxy)
                            f.write("proxy=%s\n" % (proxy.noauth_url,))
                            if proxy.username:
                                f.write("proxy_username=%s\n" % (proxy.username,))
                            if proxy.password:
                                f.write("proxy_password=%s\n" % (proxy.password,))
                        except ProxyStringError as e:
                            log.error("Failed to parse proxy for _writeInstallConfig %s: %s",
                                      ks_repo.proxy, e)

                    if ks_repo.cost:
                        f.write("cost=%d\n" % ks_repo.cost)

                    if ks_repo.includepkgs:
                        f.write("includepkgs=%s\n"
                                % ",".join(ks_repo.includepkgs))

                    if ks_repo.excludepkgs:
                        f.write("exclude=%s\n"
                                % ",".join(ks_repo.excludepkgs))

                    if ks_repo.ignoregroups:
                        f.write("enablegroups=0\n")

        releasever = self._yum.conf.yumvar['releasever']
        self._writeYumConfig()
        self._writeLangpacksConfig()
        self._resetYum(root=ROOT_PATH, keep_cache=True)
        log.debug("setting releasever to previous value of %s", releasever)
        self._yum.preconf.releasever = releasever

        self._yumCacheDirHack()
        self.gatherRepoMetadata()

        # trigger setup of self._yum.config
        log.debug("installation yum config repos: %s",
                  ",".join(r.id for r in self._yum.repos.listEnabled()))

    # YUMFIXME: there should be a way to reset package sacks without all this
    #           knowledge of the yum internals or, better yet, some convenience
    #           functions for multi-threaded applications
    def release(self):
        from yum.packageSack import MetaSack
        with _yum_lock:
            log.debug("deleting package sacks")
            if hasattr(self._yum, "_pkgSack"):
                self._yum._pkgSack = None

            self._yum.repos.pkgSack = MetaSack()

            for repo in self._yum.repos.repos.values():
                repo._sack = None

    def deleteYumTS(self):
        with _yum_lock:
            log.debug("deleting yum transaction info")
            self._yum.closeRpmDB()
            del self._yum.tsInfo
            del self._yum.ts

    def preStorage(self):
        self.release()
        with _yum_lock:
            self._yum.close()

    ###
    ### METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def repos(self):
        if not self._setup:
            return []

        _repos = []
        with _yum_lock:
            _repos = self._yum.repos.repos.keys()

        return _repos

    @property
    def baseRepo(self):
        repo_names = [BASE_REPO_NAME] + default_repos
        base_repo_name = None
        with _yum_lock:
            for repo_name in repo_names:
                if repo_name in self.repos and \
                   self._yum.repos.getRepo(repo_name).enabled:
                    base_repo_name = repo_name
                    break

        return base_repo_name

    @property
    def mirrorEnabled(self):
        with _yum_lock:
            return "fastestmirror" in self._yum.plugins.enabledPlugins

    def getRepo(self, repo_id):
        """ Return the yum repo object. """
        with _yum_lock:
            repo = self._yum.repos.getRepo(repo_id)

        return repo

    def isRepoEnabled(self, repo_id):
        """ Return True if repo is enabled. """
        from yum.Errors import RepoError

        try:
            return self.getRepo(repo_id).enabled
        except RepoError:
            return super(YumPayload, self).isRepoEnabled(repo_id)

    # pylint: disable-msg=W0221
    def updateBaseRepo(self, fallback=True, root=None, checkmount=True):
        """ Update the base repo based on self.data.method.

            - Tear down any previous base repo devices, symlinks, &c.
            - Reset the YumBase instance.
            - Try to convert the new method to a base repo.
            - If that fails, we'll use whatever repos yum finds in the config.
            - Set up addon repos.
            - Filter out repos that don't make sense to have around.
            - Get metadata for all enabled repos, disabling those for which the
              retrieval fails.
        """
        log.info("updating base repo")

        # start with a fresh YumBase instance
        self.reset(root=root)

        # If this is a kickstart install and no method has been set up, or
        # askmethod was given on the command line, we don't want to do
        # anything.  Just disable all repos and return.  This should avoid
        # metadata fetching.
        if (not self.data.method.method and flags.automatedInstall) or \
           flags.askmethod:
            with _yum_lock:
                for repo in self._yum.repos.repos.values():
                    self.disableRepo(repo.id)

            self._yumCacheDirHack()
            return

        # see if we can get a usable base repo from self.data.method
        try:
            self._configureBaseRepo(self.storage, checkmount=checkmount)
        except (MetadataError, PayloadError) as e:
            if not fallback:
                with _yum_lock:
                    for repo in self._yum.repos.repos.values():
                        if repo.enabled:
                            self.disableRepo(repo.id)

                return

            # this preserves the method details while disabling it
            self.data.method.method = None
            self.install_device = None
        finally:
            self._yumCacheDirHack()

        with _yum_lock:
            if BASE_REPO_NAME not in self._yum.repos.repos.keys():
                log.info("using default repos from local yum configuration")
                if self._yum.conf.yumvar['releasever'] == "rawhide" and \
                   "rawhide" in self.repos:
                    self.enableRepo("rawhide")

        # set up addon repos
        # FIXME: driverdisk support
        for repo in self.data.repo.dataList():
            if not repo.enabled:
                continue
            try:
                self._configureAddOnRepo(repo)
            except NoNetworkError as e:
                log.error("repo %s needs an active network connection", repo.name)
                self.disableRepo(repo.name)
            except PayloadError as e:
                log.error("repo %s setup failed: %s", repo.name, e)
                self.disableRepo(repo.name)

        # now disable and/or remove any repos that don't make sense
        with _yum_lock:
            for repo in self._yum.repos.repos.values():
                # Rules for which repos to enable/disable/remove
                #
                # - always remove
                #     - source, debuginfo
                # - disable if isFinal
                #     - rawhide, development
                # - disable all other built-in repos if rawhide is enabled
                # - remove any repo when not isFinal and repo not enabled
                # - if a base repo is defined, disable any repo not defined by
                #   the user that is not the base repo
                #
                # FIXME: updates needs special handling
                if repo.id in self.addOns:
                    continue

                if "-source" in repo.id or "-debuginfo" in repo.id:
                    self._removeYumRepo(repo.id)
                elif isFinal and ("rawhide" in repo.id or "development" in repo.id):
                    # XXX the "development" part seems a bit heavy handed
                    self._removeYumRepo(repo.id)
                elif self._yum.conf.yumvar['releasever'] == "rawhide" and \
                     "rawhide" in self.repos and \
                     self._yum.repos.getRepo("rawhide").enabled and \
                     repo.id != "rawhide":
                    self.disableRepo(repo.id)
                elif self.data.method.method and \
                     repo.id != BASE_REPO_NAME and \
                     repo.id not in (r.name for r in self.data.repo.dataList()):
                    # if a method/repo was given, disable all default repos
                    self.disableRepo(repo.id)

    def gatherRepoMetadata(self):
        # now go through and get metadata for all enabled repos
        log.info("gathering repo metadata")
        for repo_id in self.repos:
            with _yum_lock:
                repo = self._yum.repos.getRepo(repo_id)
                if repo.enabled:
                    try:
                        self._getRepoMetadata(repo)
                    except PayloadError as e:
                        log.error("failed to grab repo metadata for %s: %s",
                                  repo_id, e)
                        self.disableRepo(repo_id)

        log.info("metadata retrieval complete")

    @property
    def ISOImage(self):
        if not self.data.method.method == "harddrive":
            return None
        # This could either be mounted to INSTALL_TREE or on
        # DRACUT_ISODIR if dracut did the mount.
        dev = blivet.util.get_mount_device(INSTALL_TREE)
        if dev:
            return dev[len(ISO_DIR)+1:]
        dev = blivet.util.get_mount_device(DRACUT_ISODIR)
        if dev:
            return dev[len(DRACUT_ISODIR)+1:]
        return None

    def _configureBaseRepo(self, storage, checkmount=True):
        """ Configure the base repo.

            If self.data.method.method is set, failure to configure a base repo
            should generate a PayloadError exception.

            If self.data.method.method is unset, no exception should be raised
            and no repo should be configured.

            If checkmount is true, check the dracut mount to see if we have
            usable media mounted.
        """
        log.info("configuring base repo")
        url, mirrorlist, sslverify = self._setupInstallDevice(storage, checkmount)
        method = self.data.method
        if method.method:
            with _yum_lock:
                try:
                    self._yum.preconf.releasever = self._getReleaseVersion(url)
                except ConfigParser.MissingSectionHeaderError as e:
                    log.error("couldn't set releasever from base repo (%s): %s",
                              method.method, e)
                    self._removeYumRepo(BASE_REPO_NAME)
                    raise PayloadSetupError("base repo is unusable")

            self._yumCacheDirHack()

            if hasattr(method, "proxy"):
                proxyurl = method.proxy
            else:
                proxyurl = None

            try:
                self._addYumRepo(BASE_REPO_NAME, url, mirrorlist=mirrorlist,
                                 proxyurl=proxyurl, sslverify=sslverify)
            except MetadataError as e:
                log.error("base repo (%s/%s) not valid -- removing it",
                          method.method, url)
                self._removeYumRepo(BASE_REPO_NAME)
                raise

    def _configureAddOnRepo(self, repo):
        """ Configure a single ksdata repo. """
        url = repo.baseurl
        if url and url.startswith("nfs:"):
            (opts, server, path) = iutil.parseNfsUrl(url)
            mountpoint = "%s/%s.nfs" % (MOUNT_DIR, repo.name)
            self._setupNFS(mountpoint, server, path, opts)

            url = "file://" + mountpoint

        if self._repoNeedsNetwork(repo) and not nm_is_connected():
            raise NoNetworkError

        if repo.proxy:
            proxy = repo.proxy
        elif hasattr(self.data.method, "proxy"):
            proxy = self.data.method.proxy
        else:
            proxy = None

        sslverify = not (flags.noverifyssl or repo.noverifyssl)

        # this repo is already in ksdata, so we only add it to yum here
        self._addYumRepo(repo.name, url, repo.mirrorlist, cost=repo.cost,
                         exclude=repo.excludepkgs, includepkgs=repo.includepkgs,
                         proxyurl=proxy, sslverify=sslverify)

        addons = self._getAddons(url or repo.mirrorlist,
                                 proxy,
                                 sslverify)

        # Addons are added to the kickstart, but are disabled by default
        for addon in addons:
            # Does this repo already exist? If so, it was already added and may have
            # been edited by the user so skip adding it again.
            if self.getAddOnRepo(addon[1]):
                log.debug("Skipping %s, already exists.", addon[1])
                continue

            log.info("Adding addon repo %s", addon[1])
            ks_repo = self.data.RepoData(name=addon[1],
                                         baseurl=addon[2],
                                         proxy=repo.proxy,
                                         enabled=False)
            self.data.repo.dataList().append(ks_repo)

    def _getAddons(self, baseurl, proxy_url, sslverify):
        """ Check the baseurl or mirrorlist for a repository, see if it has any
            valid addon repos and if so, return a list of (repo name, repo URL).

            :param baseurl: url of the repo
            :type baseurl: string
            :param proxy_url: Full URL of optional proxy or ""
            :type proxy_url: string
            :param sslverify: True if SSL certificate should be varified
            :type sslverify: bool
            :returns: list of tuples of addons (id, name, url)
            :rtype: list of tuples
        """
        retval = []

        # If there's no .treeinfo for this repo, don't bother looking for addons.
        treeinfo = self._getTreeInfo(baseurl, proxy_url, sslverify)
        if not treeinfo:
            return retval

        # We need to know which variant is being installed so we know what addons
        # are valid options.
        try:
            c = ConfigParser.ConfigParser()
            ConfigParser.ConfigParser.read(c, treeinfo)
            variant = c.get("general", "variant")
        except ConfigParser.Error:
            return retval

        section = "variant-%s" % variant
        if c.has_section(section) and c.has_option(section, "addons"):
            validAddons = c.get(section, "addons").split(",")
        else:
            return retval
        log.debug("Addons found: %s", validAddons)

        for addon in validAddons:
            addonSection = "addon-%s" % addon
            if not c.has_section(addonSection) or not c.has_option(addonSection, "repository"):
                continue

            url = "%s/%s" % (baseurl, c.get(addonSection, "repository"))
            retval.append((addon, c.get(addonSection, "name"), url))

        return retval

    def _getRepoMetadata(self, yumrepo):
        """ Retrieve repo metadata if we don't already have it. """
        from yum.Errors import RepoError, RepoMDError

        # And try to grab its metadata.  We do this here so it can be done
        # on a per-repo basis, so we can then get some finer grained error
        # handling and recovery.
        log.debug("getting repo metadata for %s", yumrepo.id)
        with _yum_lock:
            try:
                yumrepo.getPrimaryXML()
            except RepoError as e:
                raise MetadataError(e.value)

            # Not getting group info is bad, but doesn't seem like a fatal error.
            # At the worst, it just means the groups won't be displayed in the UI
            # which isn't too bad, because you may be doing a kickstart install and
            # picking packages instead.
            log.debug("getting group info for %s", yumrepo.id)
            try:
                yumrepo.getGroups()
            except RepoMDError:
                log.error("failed to get groups for repo %s", yumrepo.id)

    def _replaceVars(self, url):
        """ Replace url variables with their values

            :param url: url string to do replacement on
            :type url:  string
            :returns:   string with variables substituted
            :rtype:     string or None

            Currently supports $releasever and $basearch
        """
        if not url:
            return url

        with _yum_lock:
            url = url.replace("$releasever", self._yum.conf.yumvar['releasever'])
        url = url.replace("$basearch", blivet.arch.getArch())

        return url

    def _addYumRepo(self, name, baseurl, mirrorlist=None, proxyurl=None, **kwargs):
        """ Add a yum repo to the YumBase instance. """
        from yum.Errors import RepoError

        needsAdding = True

        # First, delete any pre-existing repo with the same name.
        # First, check for any pre-existing repo with the same name.
        with _yum_lock:
            if name in self._yum.repos.repos:
                if not baseurl and not mirrorlist:
                    # This is a repo we already have a config file in /etc/anaconda.repos.d,
                    # so we just need to enable it here.  See the kickstart docs for the repo
                    # command.
                    self.enableRepo(name)
                    obj = self._yum.repos.repos[name]
                    needsAdding = False
                else:
                    self._yum.repos.delete(name)

        if proxyurl and needsAdding:
            try:
                proxy = ProxyString(proxyurl)
                kwargs["proxy"] = proxy.noauth_url
                if proxy.username:
                    kwargs["proxy_username"] = proxy.username
                if proxy.password:
                    kwargs["proxy_password"] = proxy.password
            except ProxyStringError as e:
                log.error("Failed to parse proxy for _addYumRepo %s: %s",
                          proxyurl, e)

        if baseurl:
            baseurl = self._replaceVars(baseurl)
        if mirrorlist:
            mirrorlist = self._replaceVars(mirrorlist)
        log.debug("adding yum repo %s with baseurl %s and mirrorlist %s",
                  name, baseurl, mirrorlist)
        with _yum_lock:
            if needsAdding:
                # Then add it to yum's internal structures.
                obj = self._yum.add_enable_repo(name,
                                                baseurl=[baseurl],
                                                mirrorlist=mirrorlist,
                                                **kwargs)

            # this will trigger retrieval of repomd.xml, which is small and yet
            # gives us some assurance that the repo config is sane
            # YUMFIXME: yum's instant policy doesn't work as advertised
            obj.mdpolicy = "meh"
            try:
                obj.repoXML
            except RepoError as e:
                raise MetadataError(e.value)

        # Adding a new repo means the cached packages and groups lists
        # are out of date.  Clear them out now so the next reference to
        # either will cause it to be regenerated.
        self._groups = None
        self._packages = []

    def addRepo(self, newrepo):
        """ Add a ksdata repo. """
        log.debug("adding new repo %s", newrepo.name)
        self._addYumRepo(newrepo.name, newrepo.baseurl, newrepo.mirrorlist, newrepo.proxy)   # FIXME: handle MetadataError
        super(YumPayload, self).addRepo(newrepo)

    def _removeYumRepo(self, repo_id):
        if repo_id in self.repos:
            with _yum_lock:
                self._yum.repos.delete(repo_id)
                self._groups = None
                self._packages = []

    def removeRepo(self, repo_id):
        """ Remove a repo as specified by id. """
        log.debug("removing repo %s", repo_id)

        # if this is an NFS repo, we'll want to unmount the NFS mount after
        # removing the repo
        mountpoint = None
        with _yum_lock:
            yum_repo = self._yum.repos.getRepo(repo_id)
            ks_repo = self.getAddOnRepo(repo_id)
            if yum_repo and ks_repo and ks_repo.baseurl.startswith("nfs:"):
                mountpoint = yum_repo.baseurl[0][7:]    # strip leading "file://"

        self._removeYumRepo(repo_id)
        super(YumPayload, self).removeRepo(repo_id)

        if mountpoint and os.path.ismount(mountpoint):
            try:
                blivet.util.umount(mountpoint)
            except SystemError as e:
                log.error("failed to unmount nfs repo %s: %s", mountpoint, e)

    def enableRepo(self, repo_id):
        """ Enable a repo as specified by id. """
        log.debug("enabling repo %s", repo_id)
        if repo_id in self.repos:
            with _yum_lock:
                self._yum.repos.enableRepo(repo_id)
        super(YumPayload, self).enableRepo(repo_id)

    def disableRepo(self, repo_id):
        """ Disable a repo as specified by id. """
        log.debug("disabling repo %s", repo_id)
        if repo_id in self.repos:
            with _yum_lock:
                self._yum.repos.disableRepo(repo_id)

            self._groups = None
            self._packages = []
        super(YumPayload, self).disableRepo(repo_id)

    ###
    ### METHODS FOR WORKING WITH ENVIRONMENTS
    ###
    @property
    def environments(self):
        """ List of environment ids. """
        environments = []
        yum_groups = self._yumGroups
        if yum_groups:
            with _yum_lock:
                environments = [i.environmentid for i in yum_groups.get_environments()]

        return environments

    def environmentSelected(self, environmentid):
        groups = self._yumGroups
        if not groups:
            return False

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            for group in environment.groups:
                if not self.groupSelected(group):
                    return False
            return True

    def environmentHasOption(self, environmentid, grpid):
        groups = self._yumGroups
        if not groups:
            return False

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            if grpid in environment.options:
                return True
        return False

    def environmentOptionIsDefault(self, environmentid, grpid):
        groups = self._yumGroups
        if not groups:
            return False

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            if grpid in environment.defaultoptions:
                return True
        return False

    def environmentDescription(self, environmentid):
        """ Return name/description tuple for the environment specified by id. """
        groups = self._yumGroups
        if not groups:
            return (environmentid, environmentid)

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)

            return (environment.ui_name, environment.ui_description)

    def selectEnvironment(self, environmentid):
        groups = self._yumGroups
        if not groups:
            return

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            for group in environment.groups:
                self.selectGroup(group)

    def deselectEnvironment(self, environmentid):
        groups = self._yumGroups
        if not groups:
            return

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            for group in environment.groups:
                self.deselectGroup(group)
            for group in environment.options:
                self.deselectGroup(group)

    def environmentGroups(self, environmentid):
        groups = self._yumGroups
        if not groups:
            return []

        with _yum_lock:
            if not groups.has_environment(environmentid):
                raise NoSuchGroup(environmentid)

            environment = groups.return_environment(environmentid)
            return environment.groups + environment.options

    ###
    ### METHODS FOR WORKING WITH GROUPS
    ###
    @property
    def _yumGroups(self):
        """ yum.comps.Comps instance. """
        from yum.Errors import RepoError, GroupsError
        with _yum_lock:
            if not self._groups:
                if not self.needsNetwork or nm_is_connected():
                    try:
                        self._groups = self._yum.comps
                    except (RepoError, GroupsError) as e:
                        log.error("failed to get group info: %s", e)

        return self._groups

    @property
    def groups(self):
        """ List of group ids. """
        groups = []
        yum_groups = self._yumGroups
        if yum_groups:
            with _yum_lock:
                groups = [g.groupid for g in yum_groups.get_groups()]

        return groups

    def languageGroups(self):
        yum_groups = self._yumGroups
        if not yum_groups:
            return []

        lang_codes = [self.data.lang.lang] + self.data.lang.addsupport
        lang_groups = set()

        with _yum_lock:
            groups = yum_groups.get_groups()
            for lang_code in lang_codes:
                for group in groups:
                    if langcode_matches_locale(group.langonly, lang_code):
                        lang_groups.add(group.groupid)

        return list(lang_groups)

    def groupDescription(self, groupid):
        """ Return name/description tuple for the group specified by id. """
        groups = self._yumGroups
        if not groups:
            return (groupid, groupid)

        with _yum_lock:
            if not groups.has_group(groupid):
                raise NoSuchGroup(groupid)

            group = groups.return_group(groupid)

            return (group.ui_name, group.ui_description)

    def _isGroupVisible(self, groupid):
        groups = self._yumGroups
        if not groups:
            return False

        with _yum_lock:
            if not groups.has_group(groupid):
                return False

            group = groups.return_group(groupid)
            return group.user_visible

    def _groupHasInstallableMembers(self, groupid):
        groups = self._yumGroups
        if not groups:
            return False

        with _yum_lock:
            if not groups.has_group(groupid):
                return False

            group = groups.return_group(groupid)
            pkgs = group.mandatory_packages.keys() + group.default_packages.keys()
            if pkgs:
                return True
            return False

    def _selectYumGroup(self, groupid, default=True, optional=False):
        # select the group in comps
        pkg_types = ['mandatory']
        if default:
            pkg_types.append("default")

        if optional:
            pkg_types.append("optional")

        log.debug("select group %s", groupid)
        with _yum_lock:
            try:
                self._yum.selectGroup(groupid, group_package_types=pkg_types)
            except yum.Errors.GroupsError:
                raise NoSuchGroup(groupid)

    def _deselectYumGroup(self, groupid):
        # deselect the group in comps
        log.debug("deselect group %s", groupid)
        with _yum_lock:
            try:
                self._yum.deselectGroup(groupid, force=True)
            except yum.Errors.GroupsError:
                raise NoSuchGroup(groupid)

    ###
    ### METHODS FOR WORKING WITH PACKAGES
    ###
    @property
    def packages(self):
        from yum.Errors import RepoError

        with _yum_lock:
            if not self._packages:
                if self.needsNetwork and not nm_is_connected():
                    raise NoNetworkError

                try:
                    self._packages = self._yum.pkgSack.returnPackages()
                except RepoError as e:
                    log.error("failed to get package list: %s", e)

            return self._packages

    def _selectYumPackage(self, pkgid):
        """Mark a package for installation.

           pkgid - The name of a package to be installed.  This could include
                   a version or architecture component.
        """
        log.debug("select package %s", pkgid)
        with _yum_lock:
            try:
                self._yum.install(pattern=pkgid)
            except yum.Errors.InstallError:
                raise NoSuchPackage(pkgid)

    def _deselectYumPackage(self, pkgid):
        """Mark a package to be excluded from installation.

           pkgid - The name of a package to be excluded.  This could include
                   a version or architecture component.
        """
        log.debug("deselect package %s", pkgid)
        with _yum_lock:
            self._yum.tsInfo.deselect(pkgid)

    ###
    ### METHODS FOR QUERYING STATE
    ###
    @property
    def spaceRequired(self):
        """ The total disk space (Size) required for the current selection. """
        return self._space_required

    def calculateSpaceNeeds(self):
        # XXX this will only be useful if you've run checkSoftwareSelection
        total = 0
        with _yum_lock:
            for txmbr in self._yum.tsInfo.getMembers():
                total += getattr(txmbr.po, "installedsize", 0)

        total += total * 0.35   # add 35% to account for the fact that the above
                                # method is laughably inaccurate
        self._space_required = Size(bytes=total)

        return self._space_required

    ###
    ### METHODS FOR INSTALLING THE PAYLOAD
    ###
    def _removeTxSaveFile(self):
        # remove the transaction save file
        with _yum_lock:
            if self._yum._ts_save_file:
                try:
                    os.unlink(self._yum._ts_save_file)
                except (OSError, IOError):
                    pass
                else:
                    self._yum._ts_save_file = None

    def _handleMissing(self, exn):
        if self.data.packages.handleMissing == KS_MISSING_IGNORE:
            return

        if errorHandler.cb(exn, str(exn)) == ERROR_RAISE:
            # The progress bar polls kind of slowly, thus installation could
            # still continue for a bit before the quit message is processed.
            # Let's sleep forever to prevent any further actions and wait for
            # the main thread to quit the process.
            progressQ.send_quit(1)
            while True:
                time.sleep(100000)

    def _applyYumSelections(self):
        """ Apply the selections in ksdata to yum.

            This follows the same ordering/pattern as kickstart.py.
        """
        self._selectYumGroup("core")

        if self.data.packages.default and self.environments:
            self.selectEnvironment(self.environments[0])

        for package in self.data.packages.packageList:
            try:
                self._selectYumPackage(package)
            except NoSuchPackage as e:
                self._handleMissing(e)

        for group in self.data.packages.groupList:
            default = False
            optional = False
            if group.include == GROUP_DEFAULT:
                default = True
            elif group.include == GROUP_ALL:
                default = True
                optional = True

            try:
                self._selectYumGroup(group.name, default=default, optional=optional)
            except NoSuchGroup as e:
                self._handleMissing(e)

        for package in self.data.packages.excludedList:
            try:
                self._deselectYumPackage(package)
            except NoSuchPackage as e:
                self._handleMissing(e)

        for group in self.data.packages.excludedGroupList:
            try:
                self._deselectYumGroup(group.name)
            except NoSuchGroup as e:
                self._handleMissing(e)

        self._select_kernel_package()
        self.selectRequiredPackages()

    def _addDriverRepos(self):
        """ Add driver repositories and packages
        """
        # Drivers are loaded by anaconda-dracut, their repos are copied
        # into /run/install/DD-X where X is a number starting at 1. The list of
        # packages that were selected is in /run/install/dd_packages

        # Add repositories
        dir_num = 1
        repo_template="/run/install/DD-%d/%s/"
        while True:
            repo = repo_template % (dir_num, blivet.arch.getArch())
            if not os.path.isdir(repo+"repodata"):
                break
            ks_repo = self.data.RepoData(name="DD-%d" % dir_num,
                                         baseurl="file://"+repo,
                                         enabled=True)
            self.addRepo(ks_repo)
            dir_num += 1

        # Add packages
        if not os.path.exists("/run/install/dd_packages"):
            return
        with open("/run/install/dd_packages", "r") as f:
            for line in f:
                self._requiredPackages.append(line.strip())

    def checkSoftwareSelection(self):
        log.info("checking software selection")
        self.txID = time.time()

        self.release()
        self.deleteYumTS()

        self._applyYumSelections()

        with _yum_lock:
            # doPostSelection
            # select kernel packages
            # select packages needed for storage, bootloader

            # check dependencies
            log.info("checking dependencies")
            (code, msgs) = self._yum.buildTransaction(unfinished_transactions_check=False)
            log.debug("buildTransaction = (%s, %s)", code, msgs)
            self._removeTxSaveFile()
            if code == 0:
                # empty transaction?
                log.debug("empty transaction")
            elif code == 2:
                # success
                log.debug("success")
            else:
                for msg in msgs:
                    log.warning(msg)

                raise DependencyError(msgs)

        self.calculateSpaceNeeds()
        with _yum_lock:
            log.info("%d packages selected totalling %s",
                     len(self._yum.tsInfo.getMembers()), self.spaceRequired)

    def _select_kernel_package(self):
        kernels = self.kernelPackages
        selected = None
        # XXX This is optimistic. I'm curious if yum will DTRT if I just say
        #     "select this kernel" without jumping through hoops to figure out
        #     which arch it should use.
        for kernel in kernels:
            try:
                # XXX might need explicit arch specification
                self._selectYumPackage(kernel)
            except NoSuchPackage:
                log.info("no %s package", kernel)
                continue
            else:
                log.info("selected %s", kernel)
                selected = kernel
                # select module packages for this kernel

                # select the devel package if gcc will be installed
                with _yum_lock:
                    if self._yum.tsInfo.matchNaevr(name="gcc"):
                        log.info("selecting %s-devel", kernel)
                        # XXX might need explicit arch specification
                        self._selectYumPackage("%s-devel" % kernel)
                break

        if not selected:
            log.error("failed to select a kernel from %s", kernels)

    def selectRequiredPackages(self):
        if self._requiredPackages:
            map(self._selectYumPackage, self._requiredPackages)

        if self._requiredGroups:
            map(self._selectYumGroup, self._requiredGroups)

    def preInstall(self, packages=None, groups=None):
        """ Perform pre-installation tasks. """
        super(YumPayload, self).preInstall()
        progressQ.send_message(_("Starting package installation process"))

        self._requiredPackages = packages
        self._requiredGroups = groups

        self._addDriverRepos()

        if self.install_device:
            self._setupMedia(self.install_device)

        with _yum_lock:
            self._writeInstallConfig()

        # We have this block twice.  For kickstart installs, this is the only
        # place dependencies will be checked.  If a dependency error is hit
        # here, there's nothing the user can do about it since you cannot go
        # back to the first hub.
        try:
            self.checkSoftwareSelection()
        except DependencyError as e:
            if errorHandler.cb(e) == ERROR_RAISE:
                progressQ.send_quit(1)
                while True:
                    time.sleep(100000)

        # doPreInstall
        # create mountpoints for protected device mountpoints (?)
        # write static configs (storage, modprobe.d/anaconda.conf, network, keyboard)

        # nofsync speeds things up at the risk of rpmdb data loss in a crash.
        # But if we crash mid-install you're boned anyway, so who cares?
        rpm.addMacro("__dbi_htconfig",
                     "hash nofsync %{__dbi_other} %{__dbi_perms}")

        if self.data.packages.excludeDocs:
            rpm.addMacro("_excludedocs", "1")

        if flags.selinux:
            for d in ["/tmp/updates",
                      "/etc/selinux/targeted/contexts/files",
                      "/etc/security/selinux/src/policy",
                      "/etc/security/selinux"]:
                f = d + "/file_contexts"
                if os.access(f, os.R_OK):
                    rpm.addMacro("__file_context_path", f)
                    break
        else:
            rpm.addMacro("__file_context_path", "%{nil}")

    def _transactionErrors(self, errors):
        spaceNeeded = {}
        retval = ""

        # RPM can give us a bunch of potential errors, but we really only
        # care about a handful.
        for (descr, (ty, mount, need)) in errors:
            log.error(descr)

            if ty == rpm.RPMPROB_DISKSPACE:
                spaceNeeded[mount] = need

        # Now that we've found the ones we are interested in, create an
        # error string to match.
        if spaceNeeded:
            retval += _("You need more space on the following "
                        "file systems:\n")

            for (mount, need) in spaceNeeded.items():
                retval += "%s on %s\n" % (Size(need), mount)

        return retval

    def install(self):
        """ Install the payload.

            This writes out the yum transaction and then uses a Process thread
            to execute it in a totally separate process.

            It monitors the status of the install and logs debug info, updates
            the progress meter and cleans up when it is done.
        """
        progress_map = {
            "PROGRESS_PREP"    : _("Preparing transaction from installation source"),
            "PROGRESS_INSTALL" : _("Installing"),
            "PROGRESS_POST"    : _("Performing post-installation setup tasks")
        }

        ts_file = ROOT_PATH+"/anaconda-yum.yumtx"
        with _yum_lock:
            # Save the transaction, this will be loaded and executed by the new
            # process.
            self._yum.save_ts(ts_file)

            # Try and clean up yum before the fork
            self.release()
            self.deleteYumTS()
            self._yum.close()

        script_log = "/tmp/rpm-script.log"
        release = self._getReleaseVersion(None)

        args = ["--config", "/tmp/anaconda-yum.conf",
                "--tsfile", ts_file,
                "--rpmlog", script_log,
                "--installroot", ROOT_PATH,
                "--release", release,
                "--arch", blivet.arch.getArch()]

        log.info("Running anaconda-yum to install packages")
        # Watch output for progress, debug and error information
        install_errors = []
        try:
            for line in execReadlines("/usr/libexec/anaconda/anaconda-yum", args):
                if line.startswith("PROGRESS_"):
                    key, text = line.split(":", 2)
                    msg = progress_map[key] + text
                    progressQ.send_message(msg)
                    log.debug(msg)
                elif line.startswith("DEBUG:"):
                    log.debug(line[6:])
                elif line.startswith("INFO:"):
                    log.info(line[5:])
                elif line.startswith("WARN:"):
                    log.warn(line[5:])
                elif line.startswith("ERROR:"):
                    log.error(line[6:])
                    install_errors.append(line[6:])
                else:
                    log.debug(line)
        except IOError as e:
            log.error("Error running anaconda-yum: %s", e)
            exn = PayloadInstallError(str(e))
            if errorHandler.cb(exn) == ERROR_RAISE:
                progressQ.send_quit(1)
                sys.exit(1)
        finally:
            # log the contents of the scriptlet logfile if any
            if os.path.exists(script_log):
                log.info("==== start rpm scriptlet logs ====")
                with open(script_log) as f:
                    for l in f:
                        log.info(l)
                log.info("==== end rpm scriptlet logs ====")
                os.unlink(script_log)

        if install_errors:
            exn = PayloadInstallError("\n".join(install_errors))
            if errorHandler.cb(exn) == ERROR_RAISE:
                progressQ.send_quit(1)
                sys.exit(1)

    def writeMultiLibConfig(self):
        if not self.data.packages.multiLib:
            return

        # write out the yum config with the new multilib_policy value
        # FIXME: switch to using yum-config-manager once it stops expanding
        #        all yumvars and writing out the expanded pairs to the conf
        yb = yum.YumBase()
        yum_conf_path = "/etc/yum.conf"
        yb.preconf.fn = ROOT_PATH + yum_conf_path
        yb.conf.multilib_policy = "all"

        # this will appear in yum.conf, which is silly
        yb.conf.config_file_path = yum_conf_path

        # hack around yum having expanded $basearch in the cachedir value
        cachedir = yb.conf.cachedir.replace("/%s/" % yb.arch.basearch,
                                            "/$basearch/")
        yb.conf.cachedir = cachedir
        yum_conf = ROOT_PATH + yum_conf_path
        if os.path.exists(yum_conf):
            try:
                os.rename(yum_conf, yum_conf + ".anacbak")
            except OSError as e:
                log.error("failed to back up yum.conf: %s", e)

        try:
            yb.conf.write(open(yum_conf, "w"))
        except IOError as e:
            log.error("failed to write out yum.conf: %s", e)

    def postInstall(self):
        """ Perform post-installation tasks. """
        with _yum_lock:
            # clean up repo tmpdirs
            self._yum.cleanPackages()
            self._yum.cleanHeaders()

            # remove cache dirs of install-specific repos
            for repo in self._yum.repos.listEnabled():
                if repo.name == BASE_REPO_NAME or repo.id.startswith("anaconda-"):
                    shutil.rmtree(repo.cachedir)

        self._removeTxSaveFile()

        self.writeMultiLibConfig()

        super(YumPayload, self).postInstall()

        # Make sure yum is really done and gone and lets go of the yum.log
        self._yum.close()
        del self._yum
