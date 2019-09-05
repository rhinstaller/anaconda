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
import functools
from glob import glob
from fnmatch import fnmatch
from abc import ABCMeta

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import DRACUT_ISODIR, DRACUT_REPODIR, INSTALL_TREE, ISO_DIR
from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, GROUP_REQUIRED

from pyanaconda import isys
from pyanaconda.payload.image import findFirstIsoImage, mountImage, find_optical_install_media,\
    verifyMedia, verify_valid_installtree
from pyanaconda.core import util
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.util import ProxyString, ProxyStringError, decode_bytes
from pyanaconda.core.regexes import VERSION_DIGITS
from pyanaconda.payload.errors import PayloadError, PayloadSetupError, NoSuchGroup
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.install_tree_metadata import InstallTreeMetadata
from pyanaconda.payload.requirement import PayloadRequirements
from pyanaconda.product import productName, productVersion

from pykickstart.parser import Group

from blivet.errors import StorageError

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)
USER_AGENT = "%s (anaconda)/%s" % (productName, productVersion)


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
        log.info("setting up device %s and mounting on %s", device.name, mountpoint)
        # Is there a symlink involved?  If so, let's get the actual path.
        # This is to catch /run/install/isodir vs. /mnt/install/isodir, for
        # instance.
        real_mountpoint = os.path.realpath(mountpoint)
        mount_device_path = payload_utils.get_mount_device_path(real_mountpoint)

        if mount_device_path:
            log.warning("%s is already mounted on %s", mount_device_path, mountpoint)

            if mount_device_path == device.path:
                return
            else:
                payload_utils.unmount(real_mountpoint)

        try:
            payload_utils.setup_device(device)
            payload_utils.mount_device(device, mountpoint)
        except StorageError as e:
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
            log.warning("new-kernel-pkg does not exist - grubby wasn't installed? "
                        " using dracut instead.")
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


class PackagePayload(Payload, metaclass=ABCMeta):
    """A PackagePayload installs a set of packages onto the target system."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.install_device = None
        self._rpm_macros = []

        # Used to determine which add-ons to display for each environment.
        # The dictionary keys are environment IDs. The dictionary values are two-tuples
        # consisting of lists of add-on group IDs. The first list is the add-ons specific
        # to the environment, and the second list is the other add-ons possible for the
        # environment.
        self._environment_addons = {}

    def pre_install(self):
        super().pre_install()

        # Set rpm-specific options

        # nofsync speeds things up at the risk of rpmdb data loss in a crash.
        # But if we crash mid-install you're boned anyway, so who cares?
        self.rpm_macros.append(('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'))

        if self.data.packages.excludeDocs:
            self.rpm_macros.append(('_excludedocs', '1'))

        if self.data.packages.instLangs is not None:
            # Use nil if instLangs is empty
            self.rpm_macros.append(('_install_langs', self.data.packages.instLangs or '%{nil}'))

        if conf.security.selinux:
            for d in ["/tmp/updates",
                      "/etc/selinux/targeted/contexts/files",
                      "/etc/security/selinux/src/policy",
                      "/etc/security/selinux"]:
                f = d + "/file_contexts"
                if os.access(f, os.R_OK):
                    self.rpm_macros.append(('__file_context_path', f))
                    break
        else:
            self.rpm_macros.append(('__file_context_path', '%{nil}'))

        # Add platform specific group
        groupid = util.get_platform_groupid()
        if groupid and groupid in self.groups:
            self.requirements.add_groups([groupid], reason="platform")
        elif groupid:
            log.warning("Platform group %s not available.", groupid)

    @property
    def kernel_packages(self):
        if "kernel" in self.data.packages.excludedList:
            return []

        kernels = ["kernel"]

        if payload_utils.arch_is_x86() and isys.isPaeAvailable():
            kernels.insert(0, "kernel-PAE")

        # ARM systems use either the standard Multiplatform or LPAE platform
        if payload_utils.arch_is_arm():
            if isys.isLpaeAvailable():
                kernels.insert(0, "kernel-lpae")

        return kernels

    @property
    def kernel_version_list(self):
        # Find all installed rpms that provide 'kernel'

        # If a PackagePayload is in use, rpm needs to be available
        try:
            import rpm
        except ImportError:
            raise PayloadError("failed to import rpm-python, cannot determine kernel versions")

        files = []

        ts = rpm.TransactionSet(conf.target.system_root)
        mi = ts.dbMatch('providename', 'kernel')
        for hdr in mi:
            unicode_fnames = (decode_bytes(f) for f in hdr.filenames)
            # Find all /boot/vmlinuz- files and strip off vmlinuz-
            files.extend((f.split("/")[-1][8:] for f in unicode_fnames
                         if fnmatch(f, "/boot/vmlinuz-*") or
                         fnmatch(f, "/boot/efi/EFI/%s/vmlinuz-*" % conf.bootloader.efi_dir)))

        return sorted(files, key=functools.cmp_to_key(payload_utils.version_cmp))

    @property
    def rpm_macros(self):
        """A list of (name, value) pairs to define as macros in the rpm transaction."""
        return self._rpm_macros

    @rpm_macros.setter
    def rpm_macros(self, value):
        self._rpm_macros = value

    def reset(self):
        self.reset_install_device()
        self.reset_additional_repos()

    def reset_install_device(self):
        """Unmount the previous base repo and reset the install_device."""
        # cdrom: install_device.teardown (INSTALL_TREE)
        # hd: umount INSTALL_TREE, install_device.teardown (ISO_DIR)
        # nfs: umount INSTALL_TREE
        # nfsiso: umount INSTALL_TREE, umount ISO_DIR
        if os.path.ismount(INSTALL_TREE):
            if self.install_device and \
               payload_utils.get_mount_device_path(INSTALL_TREE) == self.install_device.path:
                payload_utils.teardown_device(self.install_device)
            else:
                payload_utils.unmount(INSTALL_TREE, raise_exc=True)

        if os.path.ismount(ISO_DIR):
            if self.install_device and \
               payload_utils.get_mount_device_path(ISO_DIR) == self.install_device.path:
                payload_utils.teardown_device(self.install_device)
            # The below code will fail when nfsiso is the stage2 source
            # But if we don't do this we may not be able to switch from
            # one nfsiso repo to another nfsiso repo.  We need to have a
            # way to detect the stage2 state and work around it.
            # Commenting out the below is a hack for F18.  FIXME
            # else:
            #     # NFS
            #     blivet.util.umount(ISO_DIR)

        self.install_device = None

    def reset_additional_repos(self):
        for name in self._find_mounted_additional_repos():
            installation_dir = INSTALL_TREE + "-" + name
            self._unmount_source_directory(installation_dir)

            iso_dir = ISO_DIR + "-" + name
            self._unmount_source_directory(iso_dir)

    def _find_mounted_additional_repos(self):
        prefix = ISO_DIR + "-"
        prefix_len = len(prefix)
        result = []

        for dir_path in glob(prefix + "*"):
            result.append(dir_path[prefix_len:])

        return result

    def _unmount_source_directory(self, mount_point):
        if os.path.ismount(mount_point):
            device_path = payload_utils.get_mount_device_path(mount_point)
            device = payload_utils.resolve_device(device_path)
            if device:
                payload_utils.teardown_device(device)
            else:
                payload_utils.unmount(mount_point, raise_exc=True)

    def _device_is_mounted_as_source(self, device):
        device_mounts = payload_utils.get_mount_paths(device.path)
        return INSTALL_TREE in device_mounts or DRACUT_REPODIR in device_mounts

    def _setup_media(self, device):
        method = self.data.method
        if method.method == "harddrive":
            try:
                method.dir = self._find_and_mount_iso(device, ISO_DIR, method.dir, INSTALL_TREE)
            except PayloadSetupError as ex:
                log.warning(str(ex))

                try:
                    self._setup_install_tree(device, method.dir, INSTALL_TREE)
                except PayloadSetupError as ex:
                    log.error(str(ex))
                    raise PayloadSetupError("failed to setup installation tree or ISO from HDD")
        elif not (method.method == "cdrom" and self._device_is_mounted_as_source(device)):
            payload_utils.mount_device(device, INSTALL_TREE)

    def _find_and_mount_iso(self, device, device_mount_dir, iso_path, iso_mount_dir):
        """Find and mount installation source from ISO on device.

        Return changed path to the iso to save looking for iso in the future call.
        """
        self._setup_device(device, mountpoint=device_mount_dir)

        # check for ISO images in the newly mounted dir
        path = device_mount_dir
        if iso_path:
            path = os.path.normpath("%s/%s" % (path, iso_path))

        # XXX it would be nice to streamline this when we're just setting
        #     things back up after storage activation instead of having to
        #     pretend we don't already know which ISO image we're going to
        #     use
        image = findFirstIsoImage(path)
        if not image:
            payload_utils.teardown_device(device)
            raise PayloadSetupError("failed to find valid iso image")

        if path.endswith(".iso"):
            path = os.path.dirname(path)

        # this could already be set up the first time through
        if not os.path.ismount(iso_mount_dir):
            # mount the ISO on a loop
            image = os.path.normpath("%s/%s" % (path, image))
            mountImage(image, iso_mount_dir)

        if not iso_path.endswith(".iso"):
            result_path = os.path.normpath("%s/%s" % (iso_path,
                                                      os.path.basename(image)))
            while result_path.startswith("/"):
                # ridiculous
                result_path = result_path[1:]

            return result_path

        return iso_path

    def _setup_install_tree(self, device, install_tree_path, device_mount_dir):
        self._setup_device(device, mountpoint=device_mount_dir)
        path = os.path.normpath("%s/%s" % (device_mount_dir, install_tree_path))

        if not verify_valid_installtree(path):
            payload_utils.teardown_device(device)
            raise PayloadSetupError("failed to find valid installation tree")

    def _setup_install_device(self, checkmount):
        # XXX FIXME: does this need to handle whatever was set up by dracut?
        method = self.data.method
        url = None
        mirrorlist = None
        metalink = None

        # See if we already have stuff mounted due to dracut
        iso_device_path = payload_utils.get_mount_device_path(DRACUT_ISODIR)
        repo_device_path = payload_utils.get_mount_device_path(DRACUT_REPODIR)

        if method.method == "harddrive":
            log.debug("Setting up harddrive install device")
            url = self._setup_harddrive_device(method, iso_device_path, repo_device_path)
        elif method.method == "nfs":
            log.debug("Setting up nfs install device")
            url = self._setup_nfs_device(method, iso_device_path, repo_device_path)
        elif method.method == "url":
            url = method.url
            mirrorlist = method.mirrorlist
            metalink = method.metalink
        elif method.method == "hmc":
            log.debug("Setting up hmc install device")
            url = self._setup_hmc_device(method, iso_device_path, repo_device_path)
        elif method.method == "cdrom" or (checkmount and not method.method):
            log.debug("Setting up cdrom install device")
            url = self._setup_cdrom_device(method, iso_device_path, repo_device_path)

        return url, mirrorlist, metalink

    def _setup_harddrive_device(self, method, iso_device_path, repo_device_path):
        url = None
        need_mount = False

        if method.biospart:
            log.warning("biospart support is not implemented")
            dev_spec = method.biospart
        else:
            dev_spec = method.partition
            need_mount = True
            # See if we used this method for stage2, thus dracut left it
            if iso_device_path and method.partition and \
               method.partition in iso_device_path and \
               DRACUT_ISODIR in repo_device_path:
                # Everything should be setup
                url = "file://" + DRACUT_REPODIR
                need_mount = False
                # We don't setup an install_device here
                # because we can't tear it down

        iso_device = payload_utils.resolve_device(dev_spec)
        if need_mount:
            if not iso_device:
                raise PayloadSetupError("device for HDISO install %s does not exist" % dev_spec)

            self._setup_media(iso_device)
            url = "file://" + INSTALL_TREE
            self.install_device = iso_device

        return url

    def _setup_nfs_device(self, method, iso_device_path, repo_device_path):
        # There are several possible scenarios here:
        # 1. dracut could have mounted both the nfs repo and an iso and used
        #    the stage2 from inside the iso to boot from.
        #    iso_device_path and repo_device_path will be set in this case.
        # 2. dracut could have mounted the nfs repo and used a stage2 from
        #    the NFS mount w/o mounting the iso.
        #    iso_device_path will be None and repo_device_path will be the nfs: path
        # 3. dracut did not mount the nfs (eg. stage2 came from elsewhere)
        #    iso_device_path and/or repo_device_path are None
        # 4. The repo may not contain an iso, in that case use it as is
        url = None
        path = None

        if iso_device_path and repo_device_path:
            path = util.parseNfsUrl('nfs:%s' % iso_device_path)[2]
            # See if the dir holding the iso is what we want
            # and also if we have an iso mounted to /run/install/repo
            if path and path in iso_device_path and DRACUT_ISODIR in repo_device_path:
                # Everything should be setup
                url = "file://" + DRACUT_REPODIR
        else:
            # see if the nfs dir is mounted
            need_mount = True
            if repo_device_path:
                _options, host, path = util.parseNfsUrl('nfs:%s' % repo_device_path)
                if method.server and method.server == host and \
                   method.dir and method.dir == path:
                    need_mount = False
                    path = DRACUT_REPODIR
            elif iso_device_path:
                # iso_device_path with no repo_device_path can happen when options on an existing
                # nfs mount have changed. It is already mounted, but on INSTALL_TREE
                # which is the same as DRACUT_ISODIR, making it hard for _setup_NFS
                # to detect that it is already mounted.
                _options, host, path = util.parseNfsUrl('nfs:%s' % iso_device_path)
                if path and path in iso_device_path:
                    need_mount = False
                    path = DRACUT_ISODIR

            if need_mount:
                # Mount the NFS share on INSTALL_TREE. If it ends up
                # being nfsiso we will move the mountpoint to ISO_DIR.
                if method.dir.endswith(".iso"):
                    nfs_dir = os.path.dirname(method.dir)
                else:
                    nfs_dir = method.dir

                self._setup_NFS(INSTALL_TREE, method.server, nfs_dir, method.opts)
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
            elif os.path.isdir(path):
                # Fall back to the mount path instead of a mounted iso
                url = "file://" + path
            else:
                # Do not try to use iso as source if it is not valid source
                raise PayloadSetupError("Not a valid ISO image!")

        return url

    def _setup_hmc_device(self, method, iso_device_path, repo_device_path):
        # Check if /dev/hmcdrv is already mounted.
        if repo_device_path == "/dev/hmcdrv":
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

    def _setup_cdrom_device(self, method, iso_device_path, repo_device_path):
        url = None

        # FIXME: We really should not talk about NFS here - regression from re-factorization?

        # Check for valid optical media if we didn't boot from one
        if not verifyMedia(DRACUT_REPODIR):
            self.install_device = find_optical_install_media()

        # Only look at the dracut mount if we don't already have a cdrom
        if repo_device_path and not self.install_device:
            self.install_device = payload_utils.resolve_device(repo_device_path)
            url = "file://" + DRACUT_REPODIR
            if not method.method:
                # See if this is a nfs mount
                if ':' in repo_device_path:
                    # prepend nfs: to the url as that's what the parser
                    # wants.  Note we don't get options from this, but
                    # that's OK for the UI at least.
                    _options, host, path = util.parseNfsUrl("nfs:%s" % repo_device_path)
                    method.method = "nfs"
                    method.server = host
                    method.dir = path
                else:
                    method.method = "cdrom"
        else:
            if self.install_device:
                if not method.method:
                    method.method = "cdrom"
                self._setup_media(self.install_device)
                url = "file://" + INSTALL_TREE
            elif method.method == "cdrom":
                raise PayloadSetupError("no usable optical media found")

        return url

    def _setup_harddrive_addon_repo(self, ksrepo):
        iso_device = payload_utils.resolve_device(ksrepo.partition)
        if not iso_device:
            raise PayloadSetupError("device for HDISO addon repo install %s does not exist" %
                                    ksrepo.partition)

        ksrepo.generate_mount_dir()

        device_mount_dir = ISO_DIR + "-" + ksrepo.mount_dir_suffix
        install_root_dir = INSTALL_TREE + "-" + ksrepo.mount_dir_suffix

        self._find_and_mount_iso(iso_device, device_mount_dir, ksrepo.iso_path, install_root_dir)
        url = "file://" + install_root_dir

        return url

    ###
    # METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def repos(self):
        """A list of repo identifiers, not objects themselves."""
        raise NotImplementedError()

    def add_driver_repos(self):
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
            if repo_name not in self.addons:
                ks_repo = self.data.RepoData(name=repo_name,
                                             baseurl="file://" + repo,
                                             enabled=True)
                self.add_repo(ks_repo)

        # Add packages
        if not os.path.exists("/run/install/dd_packages"):
            return
        with open("/run/install/dd_packages", "r") as f:
            for line in f:
                package = line.strip()
                self.requirements.add_packages([package], reason="driver disk")

    @property
    def ISO_image(self):
        """The location of a mounted ISO repo, or None."""
        if not self.data.method.method == "harddrive":
            return None

        # This could either be mounted to INSTALL_TREE or on
        # DRACUT_ISODIR if dracut did the mount.
        device_path = payload_utils.get_mount_device_path(INSTALL_TREE)
        if device_path:
            return device_path[len(ISO_DIR) + 1:]

        device_path = payload_utils.get_mount_device_path(DRACUT_ISODIR)
        if device_path:
            return device_path[len(DRACUT_ISODIR) + 1:]

        return None

    ###
    # METHODS FOR WORKING WITH ENVIRONMENTS
    ###
    @property
    def environments(self):
        raise NotImplementedError()

    def environment_has_option(self, environment_id, grpid):
        raise NotImplementedError()

    def environment_option_is_default(self, environment_id, grpid):
        raise NotImplementedError()

    def environment_description(self, environment_id):
        raise NotImplementedError()

    def select_environment(self, environment_id):
        if environment_id not in self.environments:
            raise NoSuchGroup(environment_id)

        self.data.packages.environment = environment_id

    @property
    def environment_addons(self):
        return self._environment_addons

    def _is_group_visible(self, grpid):
        raise NotImplementedError()

    def _refresh_environment_addons(self):
        log.info("Refreshing environment_addons")
        self._environment_addons = {}

        for environment in self.environments:
            self._environment_addons[environment] = ([], [])

            # Determine which groups are specific to this environment and which other groups
            # are available in this environment.
            for grp in self.groups:
                if self.environment_has_option(environment, grp):
                    self._environment_addons[environment][0].append(grp)
                elif self._is_group_visible(grp):
                    self._environment_addons[environment][1].append(grp)

    ###
    # METHODS FOR WORKING WITH GROUPS
    ###
    @property
    def groups(self):
        raise NotImplementedError()

    def selected_groups_IDs(self):
        """ Return list of selected group IDs.

        :return: List of selected group IDs.
        :raise PayloadError: If translation is not supported by payload.
        """
        # pylint: disable=try-except-raise
        try:
            ret = []
            for grp in self.selected_groups():
                ret.append(self.group_id(grp))
            return ret
        # Translation feature is not implemented for this payload.
        except NotImplementedError:
            raise PayloadError(("Can't translate group names to group ID - "
                                "Group translation is not implemented for %s payload." % self))
        except PayloadError as ex:
            raise PayloadError("Can't translate group names to group ID - {}".format(ex))

    def group_description(self, grpid):
        raise NotImplementedError()

    def group_id(self, group_name):
        """Return group id for translation of groups from a kickstart file."""
        raise NotImplementedError()
