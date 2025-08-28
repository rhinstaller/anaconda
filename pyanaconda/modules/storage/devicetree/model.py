#
# Copyright (C) 2009-2017  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#
import logging
import os

from blivet.blivet import Blivet
from blivet.devicelibs.crypto import DEFAULT_LUKS_VERSION
from blivet.devices import BTRFSSubVolumeDevice
from blivet.flags import flags as blivet_flags
from blivet.formats import get_format
from blivet.formats.disklabel import DiskLabel
from blivet.size import Size

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import DRACUT_REPO_DIR, LIVE_MOUNT_POINT
from pyanaconda.core.path import set_system_root
from pyanaconda.core.product import get_product_short_name
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.storage.bootloader import BootLoaderFactory
from pyanaconda.modules.storage.devicetree.fsset import FSSet
from pyanaconda.modules.storage.devicetree.root import find_existing_installations
from pyanaconda.modules.storage.devicetree.utils import (
    download_escrow_certificate,
    find_backing_device,
    find_stage2_device,
)

log = logging.getLogger("anaconda.storage")

__all__ = ["create_storage"]


def create_storage():
    """Create the storage object.

    :return: an instance of the Blivet's storage object
    """
    return InstallerStorage()


class InstallerStorage(Blivet):
    """ Top-level class for managing installer-related storage configuration. """

    def __init__(self):
        super().__init__()
        self.roots = []
        self.protected_devices = []
        self._escrow_certificates = {}
        self._bootloader = None
        self.fsset = FSSet(self.devicetree)
        self._short_product_name = get_product_short_name()
        self._default_luks_version = DEFAULT_LUKS_VERSION

        # Set the default filesystem type.
        self.set_default_fstype(conf.storage.file_system_type or self.default_fstype)

        # Set the default LUKS version.
        self.set_default_luks_version(conf.storage.luks_version or self.default_luks_version)

        # Enable GPT discoverable partitions
        blivet_flags.gpt_discoverable_partitions = conf.storage.gpt_discoverable_partitions

    @property
    def bootloader(self):
        if self._bootloader is None:
            self._bootloader = BootLoaderFactory.create_boot_loader()

        return self._bootloader

    @property
    def boot_device(self):
        root_device = self.mountpoints.get("/")
        dev = self.mountpoints.get("/boot", root_device)
        return dev

    @property
    def default_boot_fstype(self):
        """The default filesystem type for the boot partition."""
        if self.default_fstype in self.bootloader.stage2_format_types:
            return self.default_fstype

        return self.bootloader.stage2_format_types[0]

    @property
    def default_luks_version(self):
        """The default LUKS version."""
        return self._default_luks_version

    def set_default_luks_version(self, version):
        """Set the default LUKS version.

        :param version: a string with LUKS version
        :raises: ValueError on invalid input
        """
        log.debug("trying to set new default luks version to '%s'", version)
        self._check_valid_luks_version(version)
        self._default_luks_version = version

    def _check_valid_luks_version(self, version):
        get_format("luks", luks_version=version)

    def get_fstype(self, mountpoint=None):
        """ Return the default filesystem type based on mountpoint. """
        fstype = super().get_fstype(mountpoint=mountpoint)

        if mountpoint == "/boot":
            fstype = self.default_boot_fstype

        return fstype

    def get_escrow_certificate(self, url):
        """Get the escrow certificate.

        :param url: an URL of the certificate
        :return: a content of the certificate
        """
        if not url:
            return None

        certificate = self._escrow_certificates.get(url, None)

        if not certificate:
            certificate = download_escrow_certificate(url)
            self._escrow_certificates[url] = certificate

        return certificate

    @property
    def mountpoints(self):
        return self.fsset.mountpoints

    @property
    def root_device(self):
        return self.fsset.root_device

    def _get_mount_points_free_space(self, mount_points, calculate):
        free = Size(0)
        btrfs_volumes = []

        for mount_point in mount_points:
            device = self.mountpoints.get(mount_point)
            if not device:
                continue

            # don't count the size of btrfs volumes repeatedly when multiple
            # subvolumes are present
            if isinstance(device, BTRFSSubVolumeDevice):
                if device.volume in btrfs_volumes:
                    continue
                else:
                    btrfs_volumes.append(device.volume)

            mp_size = calculate(device)
            log.debug("Free size of mount point %s: %s", mount_point, mp_size.get_bytes())
            free += mp_size

        return free

    def get_file_system_free_space(self, mount_points):
        """Get total file system free space on the given mount points.

        WARNING: For existing mount points the size available for resizing is
        obtained. It means that for non resizeable format types it returns the
        value 0.

        :param mount_points: a list of mount points
        :return: a total size
        """
        def calculate(device):
            if device.format.exists:
                return device.format.free
            else:
                return device.format.free_space_estimate(device.size)

        return self._get_mount_points_free_space(mount_points, calculate)

    def get_free_space_for_system(self, mount_points):
        """Get total space available for system on the given mount points.

        Counts the free space available on empty formatted devices.

        :param mount_points: a list of mount points
        :return: a total size
        """
        def calculate(device):
            if device.format.exists:
                log.debug("Free size calculation: %s considered as formatted", device)
            return device.format.free_space_estimate(device.size)

        return self._get_mount_points_free_space(mount_points, calculate)

    def get_disk_free_space(self, disks=None):
        """Get total free space on the given disks.

        Calculates free space available for use.

        :param disks: a list of disks or None
        :return: a total size
        """
        # Use all disks in the device tree by default.
        if disks is None:
            disks = self.disks

        # Get a list of disks with supported disk labels.
        disks = self._skip_unsupported_disk_labels(disks)

        # Get the dictionary of free spaces for each disk.
        snapshot = self.get_free_space(disks)

        # Calculate the total free space.
        return sum((disk_free for disk_free, fs_free in snapshot.values()), Size(0))

    def get_disk_reclaimable_space(self, disks=None):
        """Get total reclaimable space on the given disks.

        Calculates free space unavailable but reclaimable
        from existing partitions.

        :param disks: a list of disks or None
        :return: a total size
        """
        # Use all disks in the device tree by default.
        if disks is None:
            disks = self.disks

        # Get a list of disks with supported disk labels.
        disks = self._skip_unsupported_disk_labels(disks)

        # Get the dictionary of free spaces for each disk.
        snapshot = self.get_free_space(disks)

        # Calculate the total reclaimable free space.
        return sum((fs_free for disk_free, fs_free in snapshot.values()), Size(0))

    def _skip_unsupported_disk_labels(self, disks):
        """Get a list of disks with supported disk labels.

        Skip initialized disks with disk labels that are
        not supported on this platform.

        :param disks: a list of disks
        :return: a list of disks with supported disk labels
        """
        label_types = set(DiskLabel.get_platform_label_types())

        def is_supported(disk):
            if disk.format.type is None:
                return True

            return disk.format.type == "disklabel" \
                and disk.format.label_type in label_types

        return list(filter(is_supported, disks))

    def reset(self, cleanup_only=False):
        """ Reset storage configuration to reflect actual system state.

            This will cancel any queued actions and rescan from scratch but not
            clobber user-obtained information like passphrases, iscsi config, &c

            :keyword cleanup_only: prepare the tree only to deactivate devices
            :type cleanup_only: bool

            See :meth:`devicetree.Devicetree.populate` for more information
            about the cleanup_only keyword argument.
        """
        # set up the disk images
        if conf.target.is_image:
            self.setup_disk_images()

        # save passphrases for luks devices so we don't have to reprompt
        for device in self.devices:
            if device.format.type == "luks" and device.format.exists:
                self.save_passphrase(device)

        super().reset(cleanup_only=cleanup_only)

        # Protect devices from teardown.
        self._mark_protected_devices()
        self.devicetree.teardown_all()

        self.fsset = FSSet(self.devicetree)

        # Clear out attributes that refer to devices that are no longer in the tree.
        self.bootloader.reset()

        self.roots = []
        self.roots = find_existing_installations(self.devicetree)
        self.dump_state("initial")

    def _mark_protected_devices(self):
        """Mark protected devices.

        If a device is protected, mark it as such now. Once the tree
        has been populated, devices' protected attribute is how we will
        identify protected devices.
        """
        protected = []
        protected_with_subtree = []

        # Resolve the protected device specs to devices.
        for spec in self.protected_devices:
            dev = self.devicetree.resolve_device(spec)

            if dev is not None:
                log.debug("Protected device spec %s resolved to %s.", spec, dev.name)
                protected.append(dev)

        # Find the stage2 backing device and its parents.
        stage2_device = find_stage2_device(self.devicetree)

        if stage2_device:
            log.debug("Resolved stage2 device to %s.", stage2_device.name)
            protected.append(stage2_device)

        # Find the live backing device and its parents.
        live_device = find_backing_device(self.devicetree, LIVE_MOUNT_POINT)

        if live_device:
            log.debug("Resolved live device to %s.", live_device.name)
            protected_with_subtree.append(live_device)

        # Find the backing device of a stage2 source and its parents.
        source_device = find_backing_device(self.devicetree, DRACUT_REPO_DIR)

        if source_device:
            log.debug("Resolved a stage2 source device to %s.", source_device.name)
            protected.append(source_device)

        # For image installation setup_disk_images method marks all local
        # storage disks as ignored so they are protected from teardown.
        # Here we protect also cdrom devices from tearing down that, in case of
        # cdroms, involves unmounting which is undesirable (see bug #1671713).
        protected_with_subtree.extend(dev for dev in self.devicetree.devices
                                        if dev.type == "cdrom")

        # Protect also all devices with an iso9660 file system. It will protect
        # NVDIMM devices that can be used only as an installation source anyway
        # (see the bug #1856264).
        protected_with_subtree.extend(dev for dev in self.devicetree.devices
                                        if dev.format.type == "iso9660")

        # Mark the collected devices as protected.
        for dev in protected:
            self._mark_protected_device(dev)
        for dev in protected_with_subtree:
            self._mark_protected_device(dev, include_subtree=True)

    def protect_devices(self, protected_names):
        """Protect given devices.

        :param protected_names: a list of device names
        """
        protected = set(protected_names)
        unprotected = set(self.protected_devices)

        # Mark unprotected devices.
        # Skip devices that should stay protected.
        for spec in unprotected - protected:
            device = self.devicetree.resolve_device(spec)
            self._mark_unprotected_device(device)

        # Mark protected devices.
        # Skip devices that are already protected.
        for spec in protected - unprotected:
            device = self.devicetree.resolve_device(spec)
            self._mark_protected_device(device)

        # Update the list.
        self.protected_devices = protected_names

    def _mark_protected_device(self, device, include_subtree=False):
        """Mark a device as protected.

        :param include_subtree: if set also mark the whole subtree of devices as protected
        """
        if not device:
            return

        device.protected = True
        log.debug("Marking device %s as protected.", device.name)
        if include_subtree:
            for d in device.ancestors:
                log.debug("Marking ancestor %s of device %s as protected.",
                          d.name, device.name)
                d.protected = True

                for child in d.children:
                    if child.device_id != device.device_id:
                        log.debug("Marking sibling device %s of %s as protected.",
                                  child.name, device.name)
                        child.protected = True

    def _mark_unprotected_device(self, device, include_ancestors=False):
        """Mark a device and its ancestors as unprotected."""
        if not device:
            return

        device.protected = False
        log.debug("Marking device %s as unprotected.", device.name)
        if include_ancestors:
            for d in device.ancestors:
                log.debug("Marking ancestor %s of device %s as unprotected.",
                          d.name, device.name)
                d.protected = False

    @property
    def usable_disks(self):
        """Disks that can be used for the installation.

        :return: a list of disks
        """
        # Get all devices.
        devices = self.devicetree.devices

        # Add the hidden devices.
        if conf.target.is_image:
            devices += [
                d for d in self.devicetree._hidden
                if d.name in self.devicetree.disk_images
            ]
        else:
            devices += self.devicetree._hidden

        # Filter out the usable disks.
        disks = []
        for d in devices:
            if d.is_disk and not d.format.hidden and not d.protected:
                # Unformatted DASDs are detected with a size of 0, but they should
                # still show up as valid disks if this function is called, since we
                # can still use them; anaconda will know how to handle them, so they
                # don't need to be ignored anymore.
                if d.type == "dasd":
                    disks.append(d)
                elif d.size > 0 and d.media_present:
                    disks.append(d)

        # Remove duplicate names from the list.
        return sorted(set(disks), key=lambda d: d.name)

    def select_disks(self, selected_ids):
        """Select disks that should be used for the installation.

        Hide usable disks that are not selected.

        :param selected_names: a list of disk device IDs
        """
        for disk in self.usable_disks:
            if disk.device_id not in selected_ids:
                if disk in self.devices:
                    self.devicetree.hide(disk)
            else:
                if disk not in self.devices:
                    self.devicetree.unhide(disk)

    def _get_hostname(self):
        """Return a hostname."""
        ignored_hostnames = {None, "", 'localhost', 'localhost.localdomain', 'localhost-live'}

        network_proxy = NETWORK.get_proxy()
        hostname = network_proxy.Hostname

        if hostname in ignored_hostnames:
            hostname = network_proxy.GetCurrentHostname()

        if hostname in ignored_hostnames:
            hostname = None

        return hostname

    def _get_container_name_template(self, prefix=None):
        """Return a template for suggest_container_name method."""
        prefix = prefix or ""  # make sure prefix is a string instead of None

        # try to create a device name incorporating the hostname
        hostname = self._get_hostname()

        if hostname:
            template = "%s_%s" % (prefix, hostname.split('.')[0].lower())
            template = self.safe_device_name(template)
        else:
            template = prefix

        if conf.target.is_image:
            template = "%s_image" % template

        return template

    def turn_on_swap(self):
        self.fsset.turn_on_swap(root_path=conf.target.system_root)

    def mount_filesystems(self):
        root_path = conf.target.physical_root

        # Mount the root and the filesystems.
        self.fsset.mount_filesystems(root_path=root_path)

        # Set up the sysroot.
        set_system_root(root_path)

    def umount_filesystems(self, swapoff=True):
        # Unmount the root and the filesystems.
        self.fsset.umount_filesystems(swapoff=swapoff)

        # Unmount the sysroot.
        set_system_root(None)

    def parse_fstab(self, chroot=None):
        self.fsset.parse_fstab(chroot=chroot)

    def make_mtab(self, chroot=None):
        path = "/etc/mtab"
        target = "/proc/self/mounts"
        chroot = chroot or conf.target.system_root
        path = os.path.normpath("%s/%s" % (chroot, path))

        if os.path.islink(path):
            # return early if the mtab symlink is already how we like it
            current_target = os.path.normpath(os.path.dirname(path) +
                                              "/" + os.readlink(path))
            if current_target == target:
                return

        if os.path.exists(path):
            os.unlink(path)

        os.symlink(target, path)

    def add_fstab_swap(self, device):
        """
        Add swap device to the list of swaps that should appear in the fstab.

        :param device: swap device that should be added to the list
        :type device: blivet.devices.StorageDevice instance holding a swap format

        """

        self.fsset.add_fstab_swap(device)

    def set_fstab_swaps(self, devices):
        """
        Set swap devices that should appear in the fstab.

        :param devices: iterable providing devices that should appear in the fstab
        :type devices: iterable providing blivet.devices.StorageDevice instances holding
                       a swap format

        """

        self.fsset.set_fstab_swaps(devices)

    def copy(self):
        """Create a copy of the storage model."""
        log.debug("Creating a copy of the storage model.")

        # Create a copy of the Blivet object.
        new = super().copy()

        # Create proper copies of the collected installation roots.
        new.roots = [root.copy(storage=new) for root in new.roots]

        log.debug("Finished a copy of the storage model.")
        return new
