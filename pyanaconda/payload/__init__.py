# __init__.py
# Entry point for anaconda's software management module.
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

"""
    TODO
        - error handling!!!
        - document all methods

"""
import os
import requests
import shutil
from glob import glob
from fnmatch import fnmatch
import threading
import re
import functools
import time
from collections import OrderedDict, namedtuple

from productmd.treeinfo import TreeInfo

from blivet.size import Size, ROUND_HALF_UP

if __name__ == "__main__":
    from pyanaconda import anaconda_logging
    anaconda_logging.init()

from pyanaconda.core.constants import DRACUT_ISODIR, DRACUT_REPODIR, DD_ALL, DD_FIRMWARE, \
    DD_RPMS, INSTALL_TREE, ISO_DIR, THREAD_STORAGE, THREAD_PAYLOAD, THREAD_PAYLOAD_RESTART, \
    THREAD_WAIT_FOR_CONNECTING_NM, PayloadRequirementType, GRAPHICAL_TARGET, TEXT_ONLY_TARGET
from pyanaconda.modules.common.constants.services import SERVICES
from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, GROUP_REQUIRED
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _, N_

from pyanaconda.core import util
from pyanaconda import isys
from pyanaconda.platform import platform
from pyanaconda.image import findFirstIsoImage
from pyanaconda.image import mountImage
from pyanaconda.image import opticalInstallMedia, verifyMedia
from pyanaconda.core.util import ProxyString, ProxyStringError
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.core.regexes import VERSION_DIGITS

from pykickstart.parser import Group

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

from blivet.errors import StorageError
import blivet.util
import blivet.arch

from pyanaconda.product import productName, productVersion
USER_AGENT = "%s (anaconda)/%s" % (productName, productVersion)

from distutils.version import LooseVersion

MAX_TREEINFO_DOWNLOAD_RETRIES = 6


def versionCmp(v1, v2):
    """Compare two version number strings."""
    firstVersion = LooseVersion(v1)
    secondVersion = LooseVersion(v2)
    return (firstVersion > secondVersion) - (firstVersion < secondVersion)


###
### ERROR HANDLING
###
class PayloadError(Exception):
    pass


class MetadataError(PayloadError):
    pass


# setup
class PayloadSetupError(PayloadError):
    pass


# software selection
class NoSuchGroup(PayloadError):
    def __init__(self, group, adding=True, required=False):
        super().__init__(group)
        self.group = group
        self.adding = adding
        self.required = required

    def __str__(self):
        return "The group '{}' does not exist".format(self.group)


class NoSuchPackage(PayloadError):
    def __init__(self, package, required=False):
        super().__init__(package)
        self.package = package
        self.required = required

    def __str__(self):
        return "The package '{}' does not exist".format(self.package)


class DependencyError(PayloadError):
    pass


# installation
class PayloadInstallError(PayloadError):
    pass

PayloadRequirementReason = namedtuple('PayloadRequirementReason', ['reason', 'strong'])

class PayloadRequirement(object):
    """An object to store a payload requirement with info about its reasons.

    For each requirement multiple reasons together with their strength
    can be stored in this object using the add_reason method.
    A reason should be just a string with description (ie for tracking purposes).
    Strength is a boolean flag that can be used to indicate whether missing the
    requirement should be considered fatal. Strength of the requirement is
    given by strength of all its reasons.
    """
    def __init__(self, req_id, reasons=None):
        self._id = req_id
        self._reasons = reasons or []

    @property
    def id(self):
        """Identifier of the requirement (eg a package name)"""
        return self._id

    @property
    def reasons(self):
        """List of reasons for the requirement"""
        return [reason for reason, strong in self._reasons]

    @property
    def strong(self):
        """Strength of the requirement (ie should it be considered fatal?)"""
        return any(strong for reason, strong in self._reasons)

    def add_reason(self, reason, strong=False):
        """Adds a reason to the requirement with optional strength of the reason"""
        self._reasons.append(PayloadRequirementReason(reason, strong))

    def __str__(self):
        return "PayloadRequirement(id=%s, reasons=%s, strong=%s)" % (self.id, self.reasons, self.strong)

    def __repr__(self):
        return 'PayloadRequirement(id=%s, reasons=%s)' % (self.id, self._reasons)


class PayloadRequirementsMissingApply(Exception):
    pass

class PayloadRequirements(object):
    """A container for payload requirements imposed by installed functionality.

    Stores names of packages and groups required by used installer features,
    together with descriptions of reasons why the object is required and if the
    requirement is strong. Not satisfying strong requirement would be fatal for
    installation.
    """

    def __init__(self):
        self._apply_called_for_all_requirements = True
        self._apply_cb = None
        self._reqs = {}
        for req_type in PayloadRequirementType:
            self._reqs[req_type] = OrderedDict()

    def add_packages(self, package_names, reason, strong=True):
        """Add packages required for the reason.

        If a package is already required, the new reason will be
        added and the strength of the requirement will be updated.

        :param package_names: names of packages to be added
        :type package_names: list of str
        :param reason: description of reason for adding the packages
        :type reason: str
        :param strong: is the requirement strong (ie is not satisfying it fatal?)
        :type strong: bool
        """
        self._add(PayloadRequirementType.package, package_names, reason, strong)

    def add_groups(self, group_ids, reason, strong=True):
        """Add groups required for the reason.

        If a group is already required, the new reason will be
        added and the strength of the requirement will be updated.

        :param group_ids: ids of groups to be added
        :type group_ids: list of str
        :param reason: descripiton of reason for adding the groups
        :type reason: str
        :param strong: is the requirement strong
        :type strong: bool
        """
        self._add(PayloadRequirementType.group, group_ids, reason, strong)

    def _add(self, req_type, ids, reason, strong):
        if not ids:
            log.debug("no %s requirement added for %s", req_type.value, reason)
        reqs = self._reqs[req_type]
        for r_id in ids:
            if r_id not in reqs:
                reqs[r_id] = PayloadRequirement(r_id)
            reqs[r_id].add_reason(reason, strong)
            self._apply_called_for_all_requirements = False
            log.debug("added %s requirement '%s' for %s, strong=%s",
                      req_type.value, r_id, reason, strong)

    @property
    def packages(self):
        """List of package requirements.

        return: list of package requirements
        rtype: list of PayloadRequirement
        """
        return list(self._reqs[PayloadRequirementType.package].values())

    @property
    def groups(self):
        """List of group requirements.

        return: list of group requirements
        rtype: list of PayloadRequirement
        """
        return list(self._reqs[PayloadRequirementType.group].values())

    def set_apply_callback(self, callback):
        """Set the callback for applying requirements.

        The callback will be called by apply() method.
        param callback: callback function to be called by apply() method
        type callback: a function taking one argument (requirements object)
        """
        self._apply_cb = callback

    def apply(self):
        """Apply requirements using callback function.

        Calls the callback supplied via set_apply_callback() method. If no
        callback was set, an axception is raised.

        return: return value of the callback
        rtype: type of the callback return value
        raise PayloadRequirementsMissingApply: if there is no callback set

        """
        if self._apply_cb:
            self._apply_called_for_all_requirements = True
            rv = self._apply_cb(self)
            log.debug("apply with result %s called on requirements %s", rv, self)
            return rv
        else:
            raise PayloadRequirementsMissingApply

    @property
    def applied(self):
        """Was all requirements applied?

        return: Was apply called for all current requirements?
        rtype: bool
        """
        return self.empty or self._apply_called_for_all_requirements

    @property
    def empty(self):
        """Are requirements empty?

        return: True if there are no requirements, else False
        rtype: bool
        """
        return not any(self._reqs.values())

    def __str__(self):
        r = []
        for req_type in PayloadRequirementType:
            for rid, req in self._reqs[req_type].items():
                r.append((req_type.value, rid, req))
        return str(r)

class Payload(object):
    """Payload is an abstract class for OS install delivery methods."""
    def __init__(self, data):
        """Initialize Payload class

        :param data: This param is a kickstart.AnacondaKSHandler class.
        """
        if self.__class__ is Payload:
            raise TypeError("Payload is an abstract class")

        self.data = data
        self.storage = None
        self.instclass = None
        self.txID = None

        self._treeinfo = None

        self._first_payload_reset = True

        # A list of verbose error strings from the subclass
        self.verbose_errors = []

        self._session = util.requests_session()

        # Additional packages required by installer based on used features
        self.requirements = PayloadRequirements()

        # are mirrors available ?
        # - this is an initial default value that will
        #   be overridden by value from the current
        #   install class in the setup() method
        self._mirrors_available = True

    @property
    def first_payload_reset(self):
        return self._first_payload_reset

    def setup(self, storage, instClass):
        """Do any payload-specific setup."""
        self.storage = storage
        self.instclass = instClass
        self.verbose_errors = []
        # At the moment we set if mirrors are expected to be
        # available just based on an current install class.
        self._mirrors_available = instClass.mirrors_available

    def unsetup(self):
        """Invalidate a previously setup payload."""
        self.storage = None
        self.instclass = None
        self._treeinfo = None

    def postSetup(self):
        """Run specific payload post-configuration tasks on the end of
        the restartThread call.

        This method could be overriden.
        """
        self._first_payload_reset = False

    def preStorage(self):
        """Do any payload-specific work necessary before writing the storage
        configuration.  This method need not be provided by all payloads.
        """
        pass

    def release(self):
        """Release any resources in use by this object, but do not do final
        cleanup.  This is useful for dealing with payload backends that do
        not get along well with multithreaded programs.
        """
        pass

    def reset(self):
        """Reset the instance, not including ksdata."""
        pass

    def prepareMountTargets(self, storage):
        """Run when physical storage is mounted, but other mount points may
        not exist.  Used by the RPMOSTreePayload subclass.
        """
        pass

    def requiredDeviceSize(self, format_class):
        """We need to provide information how big device is required to have successful
        installation. ``format_class`` should be filesystem format
        class for the **root** filesystem this class carry information about
        metadata size.

        :param format_class: Class of the filesystem format.
        :type format_class: Class which inherits :class:`blivet.formats.fs.FS`
        :returns: Size of the device with given filesystem format.
        :rtype: :class:`blivet.size.Size`
        """
        device_size = format_class.get_required_size(self.spaceRequired)
        return device_size.round_to_nearest(Size("1 MiB"), ROUND_HALF_UP)

    ###
    ### METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def addOns(self):
        """A list of addon repo identifiers."""
        return [r.name for r in self.data.repo.dataList()]

    @property
    def baseRepo(self):
        """Get the identifier of the current base repo or None."""
        return None

    @property
    def mirrors_available(self):
        """Is the closest/fastest mirror option enabled?  This does not make
        sense for those payloads that do not support this concept.
        """
        return self._mirrors_available

    @property
    def disabledRepos(self):
        """A list of disabled repos."""
        disabled = []
        for repo in self.addOns:
            if not self.isRepoEnabled(repo):
                disabled.append(repo)

        return disabled

    @property
    def enabledRepos(self):
        """A list of enabled repos."""
        enabled = []
        for repo in self.addOns:
            if self.isRepoEnabled(repo):
                enabled.append(repo)

        return enabled

    def isRepoEnabled(self, repo_id):
        """Return True if repo is enabled."""
        repo = self.getAddOnRepo(repo_id)
        if repo:
            return repo.enabled
        else:
            return False

    def getAddOnRepo(self, repo_id):
        """Return a ksdata Repo instance matching the specified repo id."""
        repo = None
        for r in self.data.repo.dataList():
            if r.name == repo_id:
                repo = r
                break

        return repo

    def _repoNeedsNetwork(self, repo):
        """Returns True if the ksdata repo requires networking."""
        urls = [repo.baseurl]
        if repo.mirrorlist:
            urls.extend(repo.mirrorlist)
        elif repo.metalink:
            urls.extend(repo.metalink)
        return self._sourceNeedsNetwork(urls)

    def _sourceNeedsNetwork(self, sources):
        """Return True if the source requires network.

        :param sources: Source paths for testing
        :type sources: list
        :returns: True if any source requires network
        """
        network_protocols = ["http:", "ftp:", "nfs:", "nfsiso:"]
        for s in sources:
            if s and any(s.startswith(p) for p in network_protocols):
                log.debug("Source %s needs network for installation", s)
                return True

        log.debug("Source doesn't require network for installation")
        return False

    @property
    def needsNetwork(self):
        """Test base and additional repositories if they require network."""
        url = ""
        if self.data.method.method is None:
            # closest mirror set
            return True
        elif self.data.method.method == "nfs":
            # NFS is always on network
            return True
        elif self.data.method.method == "url":
            if self.data.url.url:
                url = self.data.url.url
            elif self.data.url.mirrorlist:
                url = self.data.url.mirrorlist
            elif self.data.url.metalink:
                url = self.data.url.metalink

        return (self._sourceNeedsNetwork([url]) or
                any(self._repoNeedsNetwork(repo) for repo in self.data.repo.dataList()))

    def updateBaseRepo(self, fallback=True, checkmount=True):
        """Update the base repository from ksdata.method."""
        pass

    def gatherRepoMetadata(self):
        pass

    def addRepo(self, ksrepo):
        """Add the repo given by the pykickstart Repo object ksrepo to the
        system.  The repo will be automatically enabled and its metadata
        fetched.

        Duplicate repos will not raise an error.  They should just silently
        take the place of the previous value.
        """
        # Add the repo to the ksdata so it'll appear in the output ks file.
        ksrepo.enabled = True
        self.data.repo.dataList().append(ksrepo)

    def addDisabledRepo(self, ksrepo):
        """Add the repo given by the pykickstart Repo object ksrepo to the
        system.

        Duplicate repos will not raise an error.  They should just silently
        take the place of the previous value.
        """
        ksrepo.enabled = False
        self.data.repo.dataList().append(ksrepo)

    def removeRepo(self, repo_id):
        repos = self.data.repo.dataList()
        try:
            idx = [repo.name for repo in repos].index(repo_id)
        except ValueError:
            log.error("failed to remove repo %s: not found", repo_id)
        else:
            repos.pop(idx)

    def enableRepo(self, repo_id):
        repo = self.getAddOnRepo(repo_id)
        if repo:
            repo.enabled = True

    def disableRepo(self, repo_id):
        repo = self.getAddOnRepo(repo_id)
        if repo:
            repo.enabled = False

    def verifyAvailableRepositories(self):
        """Verify availability of existing repositories.

        This method tests if URL links from active repositories can be reached.
        It is useful when network settings is changed so that we can verify if repositories
        are still reachable.

        This method should be overriden.
        """
        log.debug("Install method %s is not able to verify availability",
                  self.__class__.__name__)
        return False

    ###
    ### METHODS FOR WORKING WITH GROUPS
    ###
    def languageGroups(self):
        return []

    def langpacks(self):
        return []

    def selectedGroups(self):
        """Return list of selected group names from kickstart.

        NOTE:
        This group names can be mix of group IDs and other valid identifiers.
        If you want group IDs use `selectedGroupsIDs` instead.

        :return: list of group names in a format specified by a kickstart file.
        """
        return [grp.name for grp in self.data.packages.groupList]


    def selectedGroupsIDs(self):
        """Return list of IDs for selected groups.

        Implementation depends on a specific payload class.
        """
        return self.selectedGroups()

    def groupSelected(self, groupid):
        return Group(groupid) in self.data.packages.groupList

    def selectGroup(self, groupid, default=True, optional=False):
        if optional:
            include = GROUP_ALL
        elif default:
            include = GROUP_DEFAULT
        else:
            include = GROUP_REQUIRED

        grp = Group(groupid, include=include)

        if grp in self.data.packages.groupList:
            # I'm not sure this would ever happen, but ensure that re-selecting
            # a group with a different types set works as expected.
            if grp.include != include:
                grp.include = include

            return

        if grp in self.data.packages.excludedGroupList:
            self.data.packages.excludedGroupList.remove(grp)

        self.data.packages.groupList.append(grp)

    def deselectGroup(self, groupid):
        grp = Group(groupid)

        if grp in self.data.packages.excludedGroupList:
            return

        if grp in self.data.packages.groupList:
            self.data.packages.groupList.remove(grp)

        self.data.packages.excludedGroupList.append(grp)

    ###
    ### METHODS FOR QUERYING STATE
    ###
    @property
    def spaceRequired(self):
        """The total disk space (Size) required for the current selection."""
        raise NotImplementedError()

    @property
    def kernelVersionList(self):
        """An iterable of the kernel versions installed by the payload."""
        raise NotImplementedError()

    ##
    ## METHODS FOR TREE VERIFICATION
    ##
    def _refreshTreeInfo(self, url):
        """Retrieve treeinfo and store it in the self._treeinfo.

        :param url: url of the repo
        :type url: string
        """
        if not url:
            return

        if hasattr(self.data.method, "proxy"):
            proxy_url = self.data.method.proxy
        else:
            proxy_url = None

        sslverify = not flags.noverifyssl

        log.debug("retrieving treeinfo from %s (proxy: %s ; sslverify: %s)",
                  url, proxy_url, sslverify)

        proxies = {}
        if proxy_url:
            try:
                proxy = ProxyString(proxy_url)
                proxies = {"http": proxy.url,
                           "https": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy for _getTreeInfo %s: %s",
                         proxy_url, e)

        # Retry treeinfo downloads with a progressively longer pause,
        # so NetworkManager have a chance setup a network and we have
        # full connectivity before trying to download things. (#1292613)
        xdelay = util.xprogressive_delay()
        response = None
        ret_code = [None, None]
        headers = {"user-agent": USER_AGENT}

        for retry_count in range(0, MAX_TREEINFO_DOWNLOAD_RETRIES + 1):
            if retry_count > 0:
                time.sleep(next(xdelay))
            # Downloading .treeinfo
            log.info("Trying to download '.treeinfo'")
            (response, ret_code[0]) = self._download_treeinfo_file(url, ".treeinfo",
                                                                   headers, proxies, sslverify)
            if response:
                break
            # Downloading treeinfo
            log.info("Trying to download 'treeinfo'")
            (response, ret_code[1]) = self._download_treeinfo_file(url, "treeinfo",
                                                                   headers, proxies, sslverify)
            if response:
                break

            # The [.]treeinfo wasn't downloaded. Try it again if [.]treeinfo
            # is on the server.
            #
            # Server returned HTTP 404 code -> no need to try again
            if (ret_code[0] is not None and ret_code[0] == 404 and ret_code[1] is not None and ret_code[1] == 404):
                response = None
                log.error("Got HTTP 404 Error when downloading [.]treeinfo files")
                break
            if retry_count < MAX_TREEINFO_DOWNLOAD_RETRIES:
                # retry
                log.info("Retrying repo info download for %s, retrying (%d/%d)",
                         url, retry_count + 1, MAX_TREEINFO_DOWNLOAD_RETRIES)
            else:
                # run out of retries
                err_msg = ("Repo info download for %s failed after %d retries" %
                           (url, retry_count))
                log.error(err_msg)
                self.verbose_errors.append(err_msg)
                response = None

        if response:
            # get the treeinfo contents
            text = response.text

            response.close()

            self._treeinfo = TreeInfo()
            self._treeinfo.loads(text)
        else:
            self._treeinfo = None

    def _download_treeinfo_file(self, url, file_name, headers, proxies, verify):
        try:
            result = self._session.get("%s/%s" % (url, file_name), headers=headers,
                                       proxies=proxies, verify=verify)
            # Server returned HTTP 4XX or 5XX codes
            if result.status_code >= 400 and result.status_code < 600:
                log.info("Server returned %i code", result.status_code)
                return (None, result.status_code)
            log.debug("Retrieved '%s' from %s", file_name, url)
        except requests.exceptions.RequestException as e:
            log.info("Error downloading '%s': %s", file_name, e)
            return (None, None)
        return (result, result.status_code)

    def _getReleaseVersion(self, url):
        """Return the release version of the tree at the specified URL."""
        try:
            version = re.match(VERSION_DIGITS, productVersion).group(1)
        except AttributeError:
            version = "rawhide"

        log.debug("getting release version from tree at %s (%s)", url, version)

        if self._treeinfo:
            version = self._treeinfo.release.version.lower()
            log.debug("using treeinfo release version of %s", version)
        else:
            log.debug("using default release version of %s", version)

        return version

    ##
    ## METHODS FOR MEDIA MANAGEMENT (XXX should these go in another module?)
    ##
    @staticmethod
    def _setupDevice(device, mountpoint):
        """Prepare an install CD/DVD for use as a package source."""
        log.info("setting up device %s and mounting on %s", device.name, mountpoint)
        # Is there a symlink involved?  If so, let's get the actual path.
        # This is to catch /run/install/isodir vs. /mnt/install/isodir, for
        # instance.
        realMountpoint = os.path.realpath(mountpoint)

        if os.path.ismount(realMountpoint):
            mdev = blivet.util.get_mount_device(realMountpoint)
            if mdev:
                log.warning("%s is already mounted on %s", mdev, mountpoint)

            if mdev == device.path:
                return
            else:
                try:
                    blivet.util.umount(realMountpoint)
                except OSError as e:
                    log.error(str(e))
                    log.info("umount failed -- mounting on top of it")

        try:
            device.setup()
            device.format.setup(mountpoint=mountpoint)
        except StorageError as e:
            log.error("mount failed: %s", e)
            device.teardown(recursive=True)
            raise PayloadSetupError(str(e))

    @staticmethod
    def _setupNFS(mountpoint, server, path, options):
        """Prepare an NFS directory for use as a package source."""
        log.info("mounting %s:%s:%s on %s", server, path, options, mountpoint)
        if os.path.ismount(mountpoint):
            dev = blivet.util.get_mount_device(mountpoint)
            _server, colon, _path = dev.partition(":")
            if colon == ":" and server == _server and path == _path:
                log.debug("%s:%s already mounted on %s", server, path, mountpoint)
                return
            else:
                log.debug("%s already has something mounted on it", mountpoint)
                try:
                    blivet.util.umount(mountpoint)
                except OSError as e:
                    log.error(str(e))
                    log.info("umount failed -- mounting on top of it")

        # mount the specified directory
        url = "%s:%s" % (server, path)

        if not options:
            options = "nolock"
        elif "nolock" not in options:
            options += ",nolock"

        try:
            blivet.util.mount(url, mountpoint, fstype="nfs", options=options)
        except OSError as e:
            raise PayloadSetupError(str(e))

    ###
    ### METHODS FOR INSTALLING THE PAYLOAD
    ###
    def preInstall(self):
        """Perform pre-installation tasks."""
        util.mkdirChain(util.getSysroot() + "/root")

        self._writeModuleBlacklist()


    def install(self):
        """Install the payload."""
        raise NotImplementedError()

    def _writeModuleBlacklist(self):
        """Copy modules from modprobe.blacklist=<module> on cmdline to
        /etc/modprobe.d/anaconda-blacklist.conf so that modules will
        continue to be blacklisted when the system boots.
        """
        if "modprobe.blacklist" not in flags.cmdline:
            return

        util.mkdirChain(util.getSysroot() + "/etc/modprobe.d")
        with open(util.getSysroot() + "/etc/modprobe.d/anaconda-blacklist.conf", "w") as f:
            f.write("# Module blacklists written by anaconda\n")
            for module in flags.cmdline["modprobe.blacklist"].split():
                f.write("blacklist %s\n" % module)

    def _copyDriverDiskFiles(self):
        # Multiple driver disks may be loaded, so we need to glob for all
        # the firmware files in the common DD firmware directory
        for f in glob(DD_FIRMWARE + "/*"):
            try:
                shutil.copyfile(f, "%s/lib/firmware/" % util.getSysroot())
            except IOError as e:
                log.error("Could not copy firmware file %s: %s", f, e.strerror)

        #copy RPMS
        for d in glob(DD_RPMS):
            shutil.copytree(d, util.getSysroot() + "/root/" + os.path.basename(d))

        #copy modules and firmware into root's home directory
        if os.path.exists(DD_ALL):
            try:
                shutil.copytree(DD_ALL, util.getSysroot() + "/root/DD")
            except IOError as e:
                log.error("failed to copy driver disk files: %s", e.strerror)
                # XXX TODO: real error handling, as this is probably going to
                #           prevent boot on some systems

    @property
    def handlesBootloaderConfiguration(self):
        """Whether this payload backend writes the bootloader configuration itself; if
        False (the default), the generic bootloader configuration code will be used.
        """
        return False


    def recreateInitrds(self):
        """Recreate the initrds by calling new-kernel-pkg

        This needs to be done after all configuration files have been
        written, since dracut depends on some of them.

        :returns: None
        """
        if not os.path.exists(util.getSysroot() + "/usr/sbin/new-kernel-pkg"):
            log.error("new-kernel-pkg does not exist - grubby wasn't installed?  skipping")
            return

        for kernel in self.kernelVersionList:
            log.info("recreating initrd for %s", kernel)
            if not flags.imageInstall:
                util.execInSysroot("new-kernel-pkg",
                                   ["--mkinitrd", "--dracut",
                                    "--depmod", "--update", kernel])
            else:
                # hostonly is not sensible for disk image installations
                # using /dev/disk/by-uuid/ is necessary due to disk image naming
                util.execInSysroot("dracut",
                                   ["-N",
                                     "--persistent-policy", "by-uuid",
                                     "-f", "/boot/initramfs-%s.img" % kernel,
                                    kernel])


    def _setDefaultBootTarget(self):
        """Set the default systemd target for the system."""
        if not os.path.exists(util.getSysroot() + "/etc/systemd/system"):
            log.error("systemd is not installed -- can't set default target")
            return

        # If the target was already set, we don't have to continue.
        services_proxy = SERVICES.get_proxy()
        if services_proxy.DefaultTarget:
            log.debug("The default target is already set.")
            return

        try:
            import rpm
        except ImportError:
            log.info("failed to import rpm -- not adjusting default runlevel")
        else:
            ts = rpm.TransactionSet(util.getSysroot())

            # XXX one day this might need to account for anaconda's display mode
            if ts.dbMatch("provides", 'service(graphical-login)').count() and \
               ts.dbMatch('provides', 'xorg-x11-server-Xorg').count() and \
               not flags.usevnc:
                # We only manipulate the ksdata.  The symlink is made later
                # during the config write out.
                services_proxy.SetDefaultTarget(GRAPHICAL_TARGET)
            else:
                services_proxy.SetDefaultTarget(TEXT_ONLY_TARGET)

    def dracutSetupArgs(self):
        args = []
        try:
            import rpm
        except ImportError:
            pass
        else:
            util.resetRpmDb()
            ts = rpm.TransactionSet(util.getSysroot())

            # Only add "rhgb quiet" on non-s390, non-serial installs
            if util.isConsoleOnVirtualTerminal() and \
               (ts.dbMatch('provides', 'rhgb').count() or \
                ts.dbMatch('provides', 'plymouth').count()):
                args.extend(["rhgb", "quiet"])

        return args

    def postInstall(self):
        """Perform post-installation tasks."""

        # set default systemd target
        self._setDefaultBootTarget()

        # write out static config (storage, modprobe, keyboard, ??)
        #   kickstart should handle this before we get here

        self._copyDriverDiskFiles()

        log.info("Installation requirements: %s", self.requirements)
        if not self.requirements.applied:
            log.info("Some of the requirements were not applied.")

    def writeStorageEarly(self):
        """Some payloads require that the storage configuration be written out
        before doing installation.  Right now, this is basically just the
        dnfpayload.  Payloads should only implement one of these methods
        by overriding the unneeded one with a pass.
        """
        if not flags.dirInstall:
            self.storage.write()

    def writeStorageLate(self):
        """Some payloads require that the storage configuration be written out
        after doing installation.  Right now, this is basically every payload
        except for dnf.  Payloads should only implement one of these methods
        by overriding the unneeded one with a pass.
        """
        if util.getSysroot() != util.getTargetPhysicalRoot():
            self.prepareMountTargets(self.storage)
        if not flags.dirInstall:
            self.storage.write()



# Inherit abstract methods from Payload
# pylint: disable=abstract-method
class ImagePayload(Payload):
    """An ImagePayload installs an OS image to the target system."""

    def __init__(self, data):
        if self.__class__ is ImagePayload:
            raise TypeError("ImagePayload is an abstract class")

        super().__init__(data)


# Inherit abstract methods from ImagePayload
# pylint: disable=abstract-method
class ArchivePayload(ImagePayload):
    """An ArchivePayload unpacks source archives onto the target system."""

    def __init__(self, data):
        if self.__class__ is ArchivePayload:
            raise TypeError("ArchivePayload is an abstract class")

        super().__init__(data)


class PackagePayload(Payload):
    """A PackagePayload installs a set of packages onto the target system."""

    DEFAULT_REPOS = [productName.split('-')[0].lower(),
                     "fedora-modular-server",
                     "rawhide",
                     "BaseOS"]  # pylint: disable=no-member

    def __init__(self, data):
        if self.__class__ is PackagePayload:
            raise TypeError("PackagePayload is an abstract class")

        super().__init__(data)
        self.install_device = None
        self._rpm_macros = []

        # Used to determine which add-ons to display for each environment.
        # The dictionary keys are environment IDs. The dictionary values are two-tuples
        # consisting of lists of add-on group IDs. The first list is the add-ons specific
        # to the environment, and the second list is the other add-ons possible for the
        # environment.
        self._environmentAddons = {}

    def preInstall(self):
        super().preInstall()

        # Set rpm-specific options

        # nofsync speeds things up at the risk of rpmdb data loss in a crash.
        # But if we crash mid-install you're boned anyway, so who cares?
        self.rpmMacros.append(('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'))

        if self.data.packages.excludeDocs:
            self.rpmMacros.append(('_excludedocs', '1'))

        if self.data.packages.instLangs is not None:
            # Use nil if instLangs is empty
            self.rpmMacros.append(('_install_langs', self.data.packages.instLangs or '%{nil}'))

        if flags.selinux:
            for d in ["/tmp/updates",
                      "/etc/selinux/targeted/contexts/files",
                      "/etc/security/selinux/src/policy",
                      "/etc/security/selinux"]:
                f = d + "/file_contexts"
                if os.access(f, os.R_OK):
                    self.rpmMacros.append(('__file_context_path', f))
                    break
        else:
            self.rpmMacros.append(('__file_context_path', '%{nil}'))

        # Add platform specific group
        groupid = util.get_platform_groupid()
        if groupid and groupid in self.groups:
            self.requirements.add_groups([groupid], reason="platform")
        elif groupid:
            log.warning("Platform group %s not available.", groupid)

    @property
    def kernelPackages(self):
        if "kernel" in self.data.packages.excludedList:
            return []

        kernels = ["kernel"]

        if blivet.arch.is_x86(32) and isys.isPaeAvailable():
            kernels.insert(0, "kernel-PAE")

        # most ARM systems use platform-specific kernels
        if blivet.arch.is_arm():
            if platform.arm_machine is not None:
                kernels = ["kernel-%s" % platform.arm_machine]

            if isys.isLpaeAvailable():
                kernels.insert(0, "kernel-lpae")

        return kernels

    @property
    def kernelVersionList(self):
        # Find all installed rpms that provide 'kernel'

        # If a PackagePayload is in use, rpm needs to be available
        try:
            import rpm
        except ImportError:
            raise PayloadError("failed to import rpm-python, cannot determine kernel versions")

        files = []

        ts = rpm.TransactionSet(util.getSysroot())
        mi = ts.dbMatch('providename', 'kernel')
        for hdr in mi:
            unicode_fnames = (f.decode("utf-8") for f in hdr.filenames)
            # Find all /boot/vmlinuz- files and strip off vmlinuz-
            files.extend((f.split("/")[-1][8:] for f in unicode_fnames
                if fnmatch(f, "/boot/vmlinuz-*") or
                   fnmatch(f, "/boot/efi/EFI/%s/vmlinuz-*" % self.instclass.efi_dir)))

        return sorted(files, key=functools.cmp_to_key(versionCmp))

    @property
    def rpmMacros(self):
        """A list of (name, value) pairs to define as macros in the rpm transaction."""
        return self._rpm_macros

    @rpmMacros.setter
    def rpmMacros(self, value):
        self._rpm_macros = value

    def reset(self):
        self.reset_install_device()

    def reset_install_device(self):
        """Unmount the previous base repo and reset the install_device."""
        # cdrom: install_device.teardown (INSTALL_TREE)
        # hd: umount INSTALL_TREE, install_device.teardown (ISO_DIR)
        # nfs: umount INSTALL_TREE
        # nfsiso: umount INSTALL_TREE, umount ISO_DIR
        if os.path.ismount(INSTALL_TREE) and not flags.testing:
            if self.install_device and \
               blivet.util.get_mount_device(INSTALL_TREE) == self.install_device.path:
                self.install_device.teardown(recursive=True)
            else:
                blivet.util.umount(INSTALL_TREE)

        if os.path.ismount(ISO_DIR) and not flags.testing:
            if self.install_device and \
               blivet.util.get_mount_device(ISO_DIR) == self.install_device.path:
                self.install_device.teardown(recursive=True)
            # The below code will fail when nfsiso is the stage2 source
            # But if we don't do this we may not be able to switch from
            # one nfsiso repo to another nfsiso repo.  We need to have a
            # way to detect the stage2 state and work around it.
            # Commenting out the below is a hack for F18.  FIXME
            #else:
            #    # NFS
            #    blivet.util.umount(ISO_DIR)

        self.install_device = None

    def _setupMedia(self, device):
        method = self.data.method
        if method.method == "harddrive":
            self._setupDevice(device, mountpoint=ISO_DIR)

            # check for ISO images in the newly mounted dir
            path = ISO_DIR
            if method.dir:
                path = os.path.normpath("%s/%s" % (path, method.dir))

            # XXX it would be nice to streamline this when we're just setting
            #     things back up after storage activation instead of having to
            #     pretend we don't already know which ISO image we're going to
            #     use
            image = findFirstIsoImage(path)
            if not image:
                device.teardown(recursive=True)
                raise PayloadSetupError("failed to find valid iso image")

            if path.endswith(".iso"):
                path = os.path.dirname(path)

            # this could already be set up the first time through
            if not os.path.ismount(INSTALL_TREE):
                # mount the ISO on a loop
                image = os.path.normpath("%s/%s" % (path, image))
                mountImage(image, INSTALL_TREE)

            if not method.dir.endswith(".iso"):
                method.dir = os.path.normpath("%s/%s" % (method.dir,
                                                         os.path.basename(image)))
                while method.dir.startswith("/"):
                    # riduculous
                    method.dir = method.dir[1:]
        # Check to see if the device is already mounted, in which case
        # we don't need to mount it again
        elif method.method == "cdrom" and blivet.util.get_mount_paths(device.path):
            return
        else:
            device.format.setup(mountpoint=INSTALL_TREE)

    def _setupInstallDevice(self, storage, checkmount):
        # XXX FIXME: does this need to handle whatever was set up by dracut?
        method = self.data.method
        url = None
        mirrorlist = None
        metalink = None

        # See if we already have stuff mounted due to dracut
        isodev = blivet.util.get_mount_device(DRACUT_ISODIR)
        device = blivet.util.get_mount_device(DRACUT_REPODIR)

        if method.method == "harddrive":
            log.debug("Setting up harddrive install device")
            url = self._setup_harddrive_device(storage, method, isodev, device)
        elif method.method == "nfs":
            log.debug("Setting up nfs install device")
            url = self._setup_nfs_device(storage, method, isodev, device)
        elif method.method == "url":
            url = method.url
            mirrorlist = method.mirrorlist
            metalink = method.metalink
        elif method.method == "hmc":
            log.debug("Setting up hmc install device")
            url = self._setup_hmc_device(storage, method, isodev, device)
        elif method.method == "cdrom" or (checkmount and not method.method):
            log.debug("Setting up cdrom install device")
            url = self._setup_cdrom_device(storage, method, isodev, device)

        return url, mirrorlist, metalink

    def _setup_harddrive_device(self, storage, method, isodev, device):
        url = None
        needmount = False

        if method.biospart:
            log.warning("biospart support is not implemented")
            devspec = method.biospart
        else:
            devspec = method.partition
            needmount = True
            # See if we used this method for stage2, thus dracut left it
            if isodev and method.partition and method.partition in isodev and DRACUT_ISODIR in device:
                # Everything should be setup
                url = "file://" + DRACUT_REPODIR
                needmount = False
                # We don't setup an install_device here
                # because we can't tear it down

        isodevice = storage.devicetree.resolve_device(devspec)
        if needmount:
            if not isodevice:
                raise PayloadSetupError("device for HDISO install %s does not exist" % devspec)

            self._setupMedia(isodevice)
            url = "file://" + INSTALL_TREE
            self.install_device = isodevice

        return url

    def _setup_nfs_device(self, storage, method, isodev, device):
        # There are several possible scenarios here:
        # 1. dracut could have mounted both the nfs repo and an iso and used
        #    the stage2 from inside the iso to boot from.
        #    isodev and device will be set in this case.
        # 2. dracut could have mounted the nfs repo and used a stage2 from
        #    the NFS mount w/o mounting the iso.
        #    isodev will be None and device will be the nfs: path
        # 3. dracut did not mount the nfs (eg. stage2 came from elsewhere)
        #    isodev and/or device are None
        # 4. The repo may not contain an iso, in that case use it as is
        url = None
        path = None

        if isodev and device:
            path = util.parseNfsUrl('nfs:%s' % isodev)[2]
            # See if the dir holding the iso is what we want
            # and also if we have an iso mounted to /run/install/repo
            if path and path in isodev and DRACUT_ISODIR in device:
                # Everything should be setup
                url = "file://" + DRACUT_REPODIR
        else:
            # see if the nfs dir is mounted
            needmount = True
            if device:
                _options, host, path = util.parseNfsUrl('nfs:%s' % device)
                if method.server and method.server == host and \
                   method.dir and method.dir == path:
                    needmount = False
                    path = DRACUT_REPODIR
            elif isodev:
                # isodev with no device can happen when options on an existing
                # nfs mount have changed. It is already mounted, but on INSTALL_TREE
                # which is the same as DRACUT_ISODIR, making it hard for _setupNFS
                # to detect that it is already mounted.
                _options, host, path = util.parseNfsUrl('nfs:%s' % isodev)
                if path and path in isodev:
                    needmount = False
                    path = DRACUT_ISODIR

            if needmount:
                # Mount the NFS share on INSTALL_TREE. If it ends up
                # being nfsiso we will move the mountpoint to ISO_DIR.
                if method.dir.endswith(".iso"):
                    nfsdir = os.path.dirname(method.dir)
                else:
                    nfsdir = method.dir
                self._setupNFS(INSTALL_TREE, method.server, nfsdir,
                               method.opts)
                path = INSTALL_TREE

            # check for ISO images in the newly mounted dir
            if method.dir.endswith(".iso"):
                # if the given URL includes a specific ISO image file, use it
                image_file = os.path.basename(method.dir)
                path = os.path.normpath("%s/%s" % (path, image_file))

            image = findFirstIsoImage(path)

            # An image was found, mount it on INSTALL_TREE
            if image:
                if path.startswith(INSTALL_TREE):
                    # move the INSTALL_TREE mount to ISO_DIR so we can
                    # mount the contents of the iso there.
                    # work around inability to move shared filesystems
                    util.execWithRedirect("mount",
                                          ["--make-rprivate", "/"])
                    util.execWithRedirect("mount",
                                          ["--move", INSTALL_TREE, ISO_DIR])
                    # The iso is now under ISO_DIR
                    path = ISO_DIR
                elif path.endswith(".iso"):
                    path = os.path.dirname(path)

                # mount the ISO on a loop
                image = os.path.normpath("%s/%s" % (path, image))
                mountImage(image, INSTALL_TREE)

                url = "file://" + INSTALL_TREE
            else:
                # Fall back to the mount path instead of a mounted iso
                url = "file://" + path

        return url

    def _setup_hmc_device(self, storage, method, isodev, device):
        # Check if /dev/hmcdrv is already mounted.
        if device == "/dev/hmcdrv":
            log.debug("HMC is already mounted at %s.", DRACUT_REPODIR)
            url = "file://" + DRACUT_REPODIR
        else:
            log.debug("Trying to mount the content of HMC media drive.")

            # Test the SE/HMC file access.
            if util.execWithRedirect("/usr/sbin/lshmc", []):
                raise PayloadSetupError("The content of HMC media drive couldn't be accessed.")

            # Test if a path is a mount point.
            if os.path.ismount(INSTALL_TREE):
                log.debug("Don't mount the content of HMC media drive yet.")
            else:
                # Make sure that the directories exists.
                util.mkdirChain(INSTALL_TREE)

                # Mount the device.
                if util.execWithRedirect("/usr/bin/hmcdrvfs", [INSTALL_TREE]):
                    raise PayloadSetupError("The content of HMC media drive couldn't be mounted.")

            log.debug("We are ready to use the HMC at %s.", INSTALL_TREE)
            url = "file://" + INSTALL_TREE

        return url

    def _setup_cdrom_device(self, storage, method, isodev, device):
        url = None

        # Did dracut leave the DVD or NFS mounted for us?
        device = blivet.util.get_mount_device(DRACUT_REPODIR)

        # Check for valid optical media if we didn't boot from one
        if not verifyMedia(DRACUT_REPODIR):
            self.install_device = opticalInstallMedia(storage.devicetree)

        # Only look at the dracut mount if we don't already have a cdrom
        if device and not self.install_device:
            self.install_device = storage.devicetree.get_device_by_path(device)
            url = "file://" + DRACUT_REPODIR
            if not method.method:
                # See if this is a nfs mount
                if ':' in device:
                    # prepend nfs: to the url as that's what the parser
                    # wants.  Note we don't get options from this, but
                    # that's OK for the UI at least.
                    _options, host, path = util.parseNfsUrl("nfs:%s" % device)
                    method.method = "nfs"
                    method.server = host
                    method.dir = path
                else:
                    method.method = "cdrom"
        else:
            if self.install_device:
                if not method.method:
                    method.method = "cdrom"
                self._setupMedia(self.install_device)
                url = "file://" + INSTALL_TREE
            elif method.method == "cdrom":
                raise PayloadSetupError("no usable optical media found")

        return url

    ###
    ### METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def repos(self):
        """A list of repo identifiers, not objects themselves."""
        raise NotImplementedError()

    def addDriverRepos(self):
        """Add driver repositories and packages."""
        # Drivers are loaded by anaconda-dracut, their repos are copied
        # into /run/install/DD-X where X is a number starting at 1. The list of
        # packages that were selected is in /run/install/dd_packages

        # Add repositories
        dir_num = 0
        while True:
            dir_num += 1
            repo = "/run/install/DD-%d/" % dir_num
            if not os.path.isdir(repo):
                break

            # Run createrepo if there are rpms and no repodata
            if not os.path.isdir(repo + "/repodata"):
                rpms = glob(repo + "/*rpm")
                if not rpms:
                    continue
                log.info("Running createrepo on %s", repo)
                util.execWithRedirect("createrepo_c", [repo])

            repo_name = "DD-%d" % dir_num
            if repo_name not in self.addOns:
                ks_repo = self.data.RepoData(name=repo_name,
                                             baseurl="file://" + repo,
                                             enabled=True)
                self.addRepo(ks_repo)

        # Add packages
        if not os.path.exists("/run/install/dd_packages"):
            return
        with open("/run/install/dd_packages", "r") as f:
            for line in f:
                package = line.strip()
                self.requirements.add_packages([package], reason="driver disk")

    @property
    def ISOImage(self):
        """The location of a mounted ISO repo, or None."""
        if not self.data.method.method == "harddrive":
            return None
        # This could either be mounted to INSTALL_TREE or on
        # DRACUT_ISODIR if dracut did the mount.
        dev = blivet.util.get_mount_device(INSTALL_TREE)
        if dev:
            return dev[len(ISO_DIR) + 1:]
        dev = blivet.util.get_mount_device(DRACUT_ISODIR)
        if dev:
            return dev[len(DRACUT_ISODIR) + 1:]
        return None

    ###
    ### METHODS FOR WORKING WITH ENVIRONMENTS
    ###
    @property
    def environments(self):
        raise NotImplementedError()

    def environmentHasOption(self, environmentid, grpid):
        raise NotImplementedError()

    def environmentOptionIsDefault(self, environmentid, grpid):
        raise NotImplementedError()

    def environmentDescription(self, environmentid):
        raise NotImplementedError()

    def selectEnvironment(self, environmentid):
        if environmentid not in self.environments:
            raise NoSuchGroup(environmentid)

        self.data.packages.environment = environmentid

    def environmentGroups(self, environmentid, optional=True):
        raise NotImplementedError()

    @property
    def environmentAddons(self):
        return self._environmentAddons

    def _isGroupVisible(self, grpid):
        raise NotImplementedError()

    def _groupHasInstallableMembers(self, grpid):
        raise NotImplementedError()

    def _refreshEnvironmentAddons(self):
        log.info("Refreshing environmentAddons")
        self._environmentAddons = {}

        for environment in self.environments:
            self._environmentAddons[environment] = ([], [])

            # Determine which groups are specific to this environment and which other groups
            # are available in this environment.
            for grp in self.groups:
                if not self._groupHasInstallableMembers(grp):
                    continue
                elif self.environmentHasOption(environment, grp):
                    self._environmentAddons[environment][0].append(grp)
                elif self._isGroupVisible(grp):
                    self._environmentAddons[environment][1].append(grp)

    ###
    ### METHODS FOR WORKING WITH GROUPS
    ###
    @property
    def groups(self):
        raise NotImplementedError()

    def selectedGroupsIDs(self):
        """ Return list of selected group IDs.

        :return: List of selected group IDs.
        :raise PayloadError: If translation is not supported by payload.
        """
        # pylint: disable=try-except-raise
        try:
            ret = []
            for grp in self.selectedGroups():
                ret.append(self.groupId(grp))
            return ret
        # Translation feature is not implemented for this payload.
        except NotImplementedError:
            raise PayloadError(("Can't translate group names to group ID - "
                                "Group translation is not implemented for %s payload." % self))
        except PayloadError as ex:
            raise PayloadError("Can't translate group names to group ID - {}".format(ex))

    def groupDescription(self, grpid):
        raise NotImplementedError()

    def groupId(self, group_name):
        """Return group id for translation of groups from a kickstart file."""
        raise NotImplementedError()


class PayloadManager(object):
    """Framework for starting and watching the payload thread.

    This class defines several states, and events can be triggered upon
    reaching a state. Depending on whether a state has already been reached
    when a listener is added, the event code may be run in either the
    calling thread or the payload thread. The event code will block the
    payload thread regardless, so try not to run anything that takes a long
    time.

    All states except STATE_ERROR are expected to happen linearly, and adding
    a listener for a state that has already been reached or passed will
    immediately trigger that listener. For example, if the payload thread is
    currently in STATE_GROUP_MD, adding a listener for STATE_NETWORK will
    immediately run the code being added for STATE_NETWORK.

    The payload thread data should be accessed using the payloadMgr object,
    and the running thread can be accessed using threadMgr with the
    THREAD_PAYLOAD constant, if you need to wait for it or something. The
    thread should be started using payloadMgr.restartThread.
    """

    STATE_START = 0
    # Waiting on storage
    STATE_STORAGE = 1
    # Waiting on network
    STATE_NETWORK = 2
    # Verify repository availability
    STATE_TEST_AVAILABILITY = 3
    # Downloading package metadata
    STATE_PACKAGE_MD = 4
    # Downloading group metadata
    STATE_GROUP_MD = 5
    # All done
    STATE_FINISHED = 6

    # Error
    STATE_ERROR = -1

    # Error strings
    ERROR_SETUP = N_("Failed to set up installation source")
    ERROR_MD = N_("Error downloading package metadata")

    def __init__(self):
        self._event_lock = threading.Lock()
        self._event_listeners = {}
        self._thread_state = self.STATE_START
        self._error = None

        # Initialize a list for each event state
        for event_id in range(self.STATE_ERROR, self.STATE_FINISHED + 1):
            self._event_listeners[event_id] = []

    @property
    def error(self):
        return _(self._error)

    def addListener(self, event_id, func):
        """Add a listener for an event.

        :param int event_id: The event to listen for, one of the EVENT_* constants
        :param function func: An object to call when the event is reached
        """

        # Check that the event_id is valid
        assert isinstance(event_id, int)
        assert event_id <= self.STATE_FINISHED
        assert event_id >= self.STATE_ERROR

        # Add the listener inside the lock in case we need to run immediately,
        # to make sure the listener isn't triggered twice
        with self._event_lock:
            self._event_listeners[event_id].append(func)

            # If an error event was requested, run it if currently in an error state
            if event_id == self.STATE_ERROR:
                if event_id == self._thread_state:
                    func()
            # Otherwise, run if the requested event has already occurred
            elif event_id <= self._thread_state:
                func()

    def restartThread(self, storage, ksdata, payload, instClass,
                      fallback=False, checkmount=True, onlyOnChange=False):
        """Start or restart the payload thread.

        This method starts a new thread to restart the payload thread, so
        this method's return is not blocked by waiting on the previous payload
        thread. If there is already a payload thread restart pending, this method
        has no effect.

        :param pyanaconda.storage.InstallerStorage storage: The blivet storage instance
        :param kickstart.AnacondaKSHandler ksdata: The kickstart data instance
        :param payload.Payload payload: The payload instance
        :param installclass.BaseInstallClass instClass: The install class instance
        :param bool fallback: Whether to fall back to the default repo in case of error
        :param bool checkmount: Whether to check for valid mounted media
        :param bool onlyOnChange: Restart thread only if existing repositories changed.
                                    This won't restart thread even when a new repository was added!!
        """
        log.debug("Restarting payload thread")

        # If a restart thread is already running, don't start a new one
        if threadMgr.get(THREAD_PAYLOAD_RESTART):
            return

        thread_args = (storage, ksdata, payload, instClass, fallback, checkmount, onlyOnChange)
        # Launch a new thread so that this method can return immediately
        threadMgr.add(AnacondaThread(name=THREAD_PAYLOAD_RESTART, target=self._restartThread,
                                     args=thread_args))

    @property
    def running(self):
        """Is the payload thread running right now?"""
        return threadMgr.exists(THREAD_PAYLOAD_RESTART) or threadMgr.exists(THREAD_PAYLOAD)

    def _restartThread(self, storage, ksdata, payload, instClass, fallback, checkmount, onlyOnChange):
        # Wait for the old thread to finish
        threadMgr.wait(THREAD_PAYLOAD)

        thread_args = (storage, ksdata, payload, instClass, fallback, checkmount, onlyOnChange)
        # Start a new payload thread
        threadMgr.add(AnacondaThread(name=THREAD_PAYLOAD, target=self._runThread,
                                     args=thread_args))

    def _setState(self, event_id):
        # Update the current state
        log.debug("Updating payload thread state: %d", event_id)
        with self._event_lock:
            # Update the state within the lock to avoid a race with listeners
            # currently being added
            self._thread_state = event_id

            # Run any listeners for the new state
            for func in self._event_listeners[event_id]:
                func()

    def _runThread(self, storage, ksdata, payload, instClass, fallback, checkmount, onlyOnChange):
        # This is the thread entry
        # Set the initial state
        self._error = None
        self._setState(self.STATE_START)

        # Wait for storage
        self._setState(self.STATE_STORAGE)
        threadMgr.wait(THREAD_STORAGE)

        # Wait for network
        self._setState(self.STATE_NETWORK)
        # FIXME: condition for cases where we don't want network
        # (set and use payload.needsNetwork ?)
        threadMgr.wait(THREAD_WAIT_FOR_CONNECTING_NM)

        payload.setup(storage, instClass)

        # If this is a non-package Payload, we're done
        if not isinstance(payload, PackagePayload):
            self._setState(self.STATE_FINISHED)
            return

        # Test if any repository changed from the last update
        if onlyOnChange:
            log.debug("Testing repositories availability")
            self._setState(self.STATE_TEST_AVAILABILITY)
            if payload.verifyAvailableRepositories():
                log.debug("Payload isn't restarted, repositories are still available.")
                self._setState(self.STATE_FINISHED)
                return

        # Keep setting up package-based repositories
        # Download package metadata
        self._setState(self.STATE_PACKAGE_MD)
        try:
            payload.updateBaseRepo(fallback=fallback, checkmount=checkmount)
            payload.addDriverRepos()
        except (OSError, PayloadError) as e:
            log.error("PayloadError: %s", e)
            self._error = self.ERROR_SETUP
            self._setState(self.STATE_ERROR)
            payload.unsetup()
            return

        # Gather the group data
        self._setState(self.STATE_GROUP_MD)
        payload.gatherRepoMetadata()
        payload.release()

        # Check if that failed
        if not payload.baseRepo:
            log.error("No base repo configured")
            self._error = self.ERROR_MD
            self._setState(self.STATE_ERROR)
            payload.unsetup()
            return

        # run payload specific post configuration tasks
        payload.postSetup()

        self._setState(self.STATE_FINISHED)


# Initialize the PayloadManager instance
payloadMgr = PayloadManager()
