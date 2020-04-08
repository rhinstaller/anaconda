# Entry point for anaconda's software management module.
#
# Copyright (C) 2019  Red Hat, Inc.
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
import os
import re
from abc import ABCMeta, abstractmethod

from pyanaconda.core.configuration.anaconda import conf
from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, GROUP_REQUIRED

from pyanaconda.modules.common.errors.storage import MountFilesystemError, DeviceSetupError
from pyanaconda.core import util
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.util import ProxyString, ProxyStringError
from pyanaconda.core.regexes import VERSION_DIGITS
from pyanaconda.payload.errors import PayloadSetupError
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.install_tree_metadata import InstallTreeMetadata
from pyanaconda.payload.requirement import PayloadRequirements
from pyanaconda.product import productName, productVersion

from pykickstart.parser import Group
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)
USER_AGENT = "%s (anaconda)/%s" % (productName, productVersion)

__all__ = ["Payload"]


class Payload(metaclass=ABCMeta):
    """Payload is an abstract class for OS install delivery methods."""
    def __init__(self, data):
        """Initialize Payload class

        :param data: This param is a kickstart.AnacondaKSHandler class.
        """
        self.data = data
        self.tx_id = None

        self._install_tree_metadata = None

        self._first_payload_reset = True

        # A list of verbose error strings from the subclass
        self.verbose_errors = []

        self._session = util.requests_session()

        # Additional packages required by installer based on used features
        self.requirements = PayloadRequirements()

    @property
    @abstractmethod
    def type(self):
        """The DBus type of the payload."""
        return None

    @property
    def first_payload_reset(self):
        return self._first_payload_reset

    @property
    def is_hmc_enabled(self):
        return self.data.method.method == "hmc"

    def setup(self):
        """Do any payload-specific setup."""
        self.verbose_errors = []

    def unsetup(self):
        """Invalidate a previously setup payload."""
        self._install_tree_metadata = None

    def post_setup(self):
        """Run specific payload post-configuration tasks on the end of
        the restart_thread call.

        This method could be overriden.
        """
        self._first_payload_reset = False

    def release(self):
        """Release any resources in use by this object, but do not do final
        cleanup.  This is useful for dealing with payload backends that do
        not get along well with multithreaded programs.
        """
        pass

    def reset(self):
        """Reset the instance, not including ksdata."""
        pass

    ###
    # METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def addons(self):
        """A list of addon repo names."""
        return [r.name for r in self.data.repo.dataList()]

    @property
    def base_repo(self):
        """Get the identifier of the current base repo or None."""
        return None

    @property
    def mirrors_available(self):
        """Is the closest/fastest mirror option enabled?  This does not make
        sense for those payloads that do not support this concept.
        """
        return conf.payload.enable_closest_mirror

    @property
    def disabled_repos(self):
        """A list of names of the disabled repos."""
        disabled = []
        for repo in self.addons:
            if not self.is_repo_enabled(repo):
                disabled.append(repo)

        return disabled

    @property
    def enabled_repos(self):
        """A list of names of the enabled repos."""
        enabled = []
        for repo in self.addons:
            if self.is_repo_enabled(repo):
                enabled.append(repo)

        return enabled

    def is_repo_enabled(self, repo_id):
        """Return True if repo is enabled."""
        repo = self.get_addon_repo(repo_id)
        if repo:
            return repo.enabled
        else:
            return False

    def get_addon_repo(self, repo_id):
        """Return a ksdata Repo instance matching the specified repo id."""
        repo = None
        for r in self.data.repo.dataList():
            if r.name == repo_id:
                repo = r
                break

        return repo

    def _repo_needs_network(self, repo):
        """Returns True if the ksdata repo requires networking."""
        urls = [repo.baseurl]
        if repo.mirrorlist:
            urls.extend(repo.mirrorlist)
        elif repo.metalink:
            urls.extend(repo.metalink)
        return self._source_needs_network(urls)

    def _source_needs_network(self, sources):
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
    def needs_network(self):
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

        return (self._source_needs_network([url]) or
                any(self._repo_needs_network(repo) for repo in self.data.repo.dataList()))

    def update_base_repo(self, fallback=True, checkmount=True):
        """Update the base repository from ksdata.method."""
        pass

    def gather_repo_metadata(self):
        pass

    def add_repo(self, ksrepo):
        """Add the repo given by the pykickstart Repo object ksrepo to the
        system.  The repo will be automatically enabled and its metadata
        fetched.

        Duplicate repos will not raise an error.  They should just silently
        take the place of the previous value.
        """
        # Add the repo to the ksdata so it'll appear in the output ks file.
        ksrepo.enabled = True
        self.data.repo.dataList().append(ksrepo)

    def add_disabled_repo(self, ksrepo):
        """Add the repo given by the pykickstart Repo object ksrepo to the
        list of known repos.  The repo will be automatically disabled.

        Duplicate repos will not raise an error.  They should just silently
        take the place of the previous value.
        """
        ksrepo.enabled = False
        self.data.repo.dataList().append(ksrepo)

    def remove_repo(self, repo_id):
        repos = self.data.repo.dataList()
        try:
            idx = [repo.name for repo in repos].index(repo_id)
        except ValueError:
            log.error("failed to remove repo %s: not found", repo_id)
        else:
            repos.pop(idx)

    def enable_repo(self, repo_id):
        repo = self.get_addon_repo(repo_id)
        if repo:
            repo.enabled = True

    def disable_repo(self, repo_id):
        repo = self.get_addon_repo(repo_id)
        if repo:
            repo.enabled = False

    def verify_available_repositories(self):
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
    # METHODS FOR WORKING WITH GROUPS
    ###
    def is_language_supported(self, language):
        """Is the given language supported by the payload?

        :param language: a name of the language
        """
        return True

    def is_locale_supported(self, language, locale):
        """Is the given locale supported by the payload?

        :param language: a name of the language
        :param locale: a name of the locale
        """
        return True

    def language_groups(self):
        return []

    def langpacks(self):
        return []

    def selected_groups(self):
        """Return list of selected group names from kickstart.

        NOTE:
        This group names can be mix of group IDs and other valid identifiers.
        If you want group IDs use `selected_groups_IDs` instead.

        :return: list of group names in a format specified by a kickstart file.
        """
        return [grp.name for grp in self.data.packages.groupList]

    def selected_groups_IDs(self):
        """Return list of IDs for selected groups.

        Implementation depends on a specific payload class.
        """
        return self.selected_groups()

    def group_selected(self, groupid):
        return Group(groupid) in self.data.packages.groupList

    def select_group(self, groupid, default=True, optional=False):
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

    def deselect_group(self, groupid):
        grp = Group(groupid)

        if grp in self.data.packages.excludedGroupList:
            return

        if grp in self.data.packages.groupList:
            self.data.packages.groupList.remove(grp)

        self.data.packages.excludedGroupList.append(grp)

    ###
    # METHODS FOR QUERYING STATE
    ###
    @property
    def space_required(self):
        """The total disk space (Size) required for the current selection."""
        raise NotImplementedError()

    @property
    def kernel_version_list(self):
        """An iterable of the kernel versions installed by the payload."""
        raise NotImplementedError()

    ###
    # METHODS FOR TREE VERIFICATION
    ###
    def _refresh_install_tree(self, url):
        """Refresh installation tree metadata.

        :param url: url of the repo
        :type url: string
        """
        if not url:
            return

        if hasattr(self.data.method, "proxy"):
            proxy_url = self.data.method.proxy
        else:
            proxy_url = None

        # ssl_verify can be:
        #   - the path to a cert file
        #   - True, to use the system's certificates
        #   - False, to not verify
        ssl_verify = getattr(self.data.method, "sslcacert", None) or conf.payload.verify_ssl

        ssl_client_cert = getattr(self.data.method, "ssl_client_cert", None)
        ssl_client_key = getattr(self.data.method, "ssl_client_key", None)
        ssl_cert = (ssl_client_cert, ssl_client_key) if ssl_client_cert else None

        log.debug("retrieving treeinfo from %s (proxy: %s ; ssl_verify: %s)",
                  url, proxy_url, ssl_verify)

        proxies = {}
        if proxy_url:
            try:
                proxy = ProxyString(proxy_url)
                proxies = {"http": proxy.url,
                           "https": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy for _getTreeInfo %s: %s",
                         proxy_url, e)

        headers = {"user-agent": USER_AGENT}
        self._install_tree_metadata = InstallTreeMetadata()
        try:
            ret = self._install_tree_metadata.load_url(url, proxies, ssl_verify, ssl_cert, headers)
        except IOError as e:
            self._install_tree_metadata = None
            self.verbose_errors.append(str(e))
            log.warning("Install tree metadata fetching failed: %s", str(e))
            return

        if not ret:
            log.warning("Install tree metadata can't be loaded!")
            self._install_tree_metadata = None

    def _get_release_version(self, url):
        """Return the release version of the tree at the specified URL."""
        try:
            version = re.match(VERSION_DIGITS, productVersion).group(1)
        except AttributeError:
            version = "rawhide"

        log.debug("getting release version from tree at %s (%s)", url, version)

        if self._install_tree_metadata:
            version = self._install_tree_metadata.get_release_version()
            log.debug("using treeinfo release version of %s", version)
        else:
            log.debug("using default release version of %s", version)

        return version

    ###
    # METHODS FOR MEDIA MANAGEMENT (XXX should these go in another module?)
    ###
    @staticmethod
    def _setup_device(device, mountpoint):
        """Prepare an install CD/DVD for use as a package source."""
        log.info("setting up device %s and mounting on %s", device, mountpoint)
        # Is there a symlink involved?  If so, let's get the actual path.
        # This is to catch /run/install/isodir vs. /mnt/install/isodir, for
        # instance.
        real_mountpoint = os.path.realpath(mountpoint)
        mount_device_path = payload_utils.get_mount_device_path(real_mountpoint)

        if mount_device_path:
            log.warning("%s is already mounted on %s", mount_device_path, mountpoint)

            if mount_device_path == payload_utils.get_device_path(device):
                return
            else:
                payload_utils.unmount(real_mountpoint)

        try:
            payload_utils.setup_device(device)
            payload_utils.mount_device(device, mountpoint)
        except (DeviceSetupError, MountFilesystemError) as e:
            log.error("mount failed: %s", e)
            payload_utils.teardown_device(device)
            raise PayloadSetupError(str(e))

    @staticmethod
    def _setup_NFS(mountpoint, server, path, options):
        """Prepare an NFS directory for use as an install source."""
        log.info("mounting %s:%s:%s on %s", server, path, options, mountpoint)
        device_path = payload_utils.get_mount_device_path(mountpoint)

        # test if the mountpoint is occupied already
        if device_path:
            _server, colon, _path = device_path.partition(":")
            if colon == ":" and server == _server and path == _path:
                log.debug("%s:%s already mounted on %s", server, path, mountpoint)
                return
            else:
                log.debug("%s already has something mounted on it", mountpoint)
                payload_utils.unmount(mountpoint)

        # mount the specified directory
        url = "%s:%s" % (server, path)

        if not options:
            options = "nolock"
        elif "nolock" not in options:
            options += ",nolock"

        payload_utils.mount(url, mountpoint, fstype="nfs", options=options)

    ###
    # METHODS FOR INSTALLING THE PAYLOAD
    ###
    def pre_install(self):
        """Perform pre-installation tasks."""
        from pyanaconda.modules.payloads.base.initialization import PrepareSystemForInstallationTask
        PrepareSystemForInstallationTask(conf.target.system_root).run()

    def install(self):
        """Install the payload."""
        raise NotImplementedError()

    @property
    def needs_storage_configuration(self):
        """Should we write the storage before doing the installation?

        Some payloads require that the storage configuration will be written out
        before doing installation. Right now, this is basically just the dnfpayload.
        """
        return False

    @property
    def handles_bootloader_configuration(self):
        """Whether this payload backend writes the bootloader configuration itself; if
        False (the default), the generic bootloader configuration code will be used.
        """
        return False

    def recreate_initrds(self):
        """Recreate the initrds by calling new-kernel-pkg or dracut

        This needs to be done after all configuration files have been
        written, since dracut depends on some of them.

        :returns: None
        """
        if os.path.exists(conf.target.system_root + "/usr/sbin/new-kernel-pkg"):
            use_dracut = False
        else:
            log.debug("new-kernel-pkg does not exist, using dracut instead.")
            use_dracut = True

        for kernel in self.kernel_version_list:
            log.info("recreating initrd for %s", kernel)
            if not conf.target.is_image:
                if use_dracut:
                    util.execInSysroot("depmod", ["-a", kernel])
                    util.execInSysroot("dracut",
                                       ["-f",
                                        "/boot/initramfs-%s.img" % kernel,
                                        kernel])
                else:
                    util.execInSysroot("new-kernel-pkg",
                                       ["--mkinitrd", "--dracut", "--depmod",
                                        "--update", kernel])

                # if the installation is running in fips mode then make sure
                # fips is also correctly enabled in the installed system
                if kernel_arguments.get("fips") == "1":
                    # We use the --no-bootcfg option as we don't want fips-mode-setup to
                    # modify the bootloader configuration.
                    # Anaconda already does everything needed & it would require grubby to
                    # be available on the system.
                    util.execInSysroot("fips-mode-setup", ["--enable", "--no-bootcfg"])

            else:
                # hostonly is not sensible for disk image installations
                # using /dev/disk/by-uuid/ is necessary due to disk image naming
                util.execInSysroot("dracut",
                                   ["-N",
                                    "--persistent-policy", "by-uuid",
                                    "-f", "/boot/initramfs-%s.img" % kernel,
                                    kernel])

    def post_install(self):
        """Perform post-installation tasks."""

        # write out static config (storage, modprobe, keyboard, ??)
        #   kickstart should handle this before we get here
        from pyanaconda.modules.payloads.base.initialization import CopyDriverDisksFilesTask
        CopyDriverDisksFilesTask(conf.target.system_root).run()

        log.info("Installation requirements: %s", self.requirements)
        if not self.requirements.applied:
            log.info("Some of the requirements were not applied.")
