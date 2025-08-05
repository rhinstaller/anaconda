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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet.errors import StorageError
from blivet.partitioning import do_partitioning, grow_lvm
from blivet.static_data import luks_data
from pykickstart.constants import (
    AUTOPART_TYPE_BTRFS,
    AUTOPART_TYPE_LVM,
    AUTOPART_TYPE_LVM_THINP,
    AUTOPART_TYPE_PLAIN,
)

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.storage import suggest_swap_size
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.storage.devicetree.root import find_existing_installations
from pyanaconda.modules.storage.partitioning.automatic.noninteractive_partitioning import (
    NonInteractivePartitioningTask,
)
from pyanaconda.modules.storage.partitioning.automatic.utils import (
    get_candidate_disks,
    get_default_partitioning,
    get_disks_for_implicit_partitions,
    get_part_spec,
    get_pbkdf_args,
    schedule_implicit_partitions,
    schedule_partitions,
    schedule_volumes,
)
from pyanaconda.modules.storage.partitioning.interactive.utils import destroy_device
from pyanaconda.modules.storage.partitioning.manual.utils import reformat_device
from pyanaconda.modules.storage.platform import platform

log = get_module_logger(__name__)

__all__ = ["AutomaticPartitioningTask"]


class AutomaticPartitioningTask(NonInteractivePartitioningTask):
    """A task for the automatic partitioning configuration."""

    def __init__(self, storage, request: PartitioningRequest):
        """Create a task.

        :param storage: an instance of Blivet
        :param request: an instance of PartitioningRequest
        """
        super().__init__(storage)
        self._request = request

    def _get_initialization_config(self):
        """Get the initialization config.

        FIXME: This is a temporary method.
        """
        config = super()._get_initialization_config()
        # If autopart is selected we want to remove whatever has been created/scheduled
        # to make room for autopart. If custom is selected, we want to leave alone any
        # storage layout the user may have set up before now.
        config.clear_non_existent = True
        return config

    @staticmethod
    def _get_mountpoint_device(storage, mountpoint, required=True):
        devices = []
        for root in storage.roots:
            if mountpoint in root.mounts:
                devices.append(root.mounts[mountpoint])
        if len(devices) > 1:
            raise StorageError(_("Multiple devices found for mount point '{}': {}")
                               .format(mountpoint,
                                       ", ".join([device.name for device in devices])))
        if not devices:
            if required:
                raise StorageError(_("No devices found for mount point '{}'").format(mountpoint))
            else:
                return None

        return devices[0]

    @staticmethod
    def _get_mountpoint_options(storage, mountpoint):
        for root in storage.roots:
            if mountpoint in root.mountopts:
                return root.mountopts[mountpoint]
        return None

    @staticmethod
    def _reused_devices_mountpoints(request):
        return request.reused_mount_points + request.reformatted_mount_points

    @classmethod
    def _get_reused_device_names(cls, storage, request):
        reused_devices = {}
        for mountpoint in cls._reused_devices_mountpoints(request):
            device = cls._get_mountpoint_device(storage, mountpoint)
            reused_devices[device.name] = mountpoint
        return reused_devices

    @classmethod
    def _reformat_mountpoint(cls, storage, mountpoint, request):
        device = cls._get_mountpoint_device(storage, mountpoint)
        log.debug("reformat device %s for  mountpoint: %s", device, mountpoint)
        reused_devices = cls._get_reused_device_names(storage, request)
        reformat_device(storage, device, dependencies=reused_devices)

    @classmethod
    def _remove_mountpoint(cls, storage, mountpoint):
        device = cls._get_mountpoint_device(storage, mountpoint, required=False)
        if device:
            log.debug("remove device %s for mountpoint %s", device, mountpoint)
            destroy_device(storage, device)
        else:
            log.debug("device to be removed for mountpoint %s not found", mountpoint)

    @staticmethod
    def _remove_bootloader_partitions(storage, required=True):
        bootloader_types = ["efi", "biosboot", "appleboot", "prepboot"]
        bootloader_parts = [part for part in platform.partitions
                            if part.fstype in bootloader_types]
        if len(bootloader_parts) > 1:
            raise StorageError(_("Multiple boot loader partitions required: %(bootparts)s") %
                               {"bootparts": bootloader_parts})
        if not bootloader_parts:
            log.debug("No bootloader partition required")
            return False
        part_type = bootloader_parts[0].fstype

        partition_table_types = {disk.format.parted_disk.type for disk in storage.disks if disk.partitioned and not disk.protected}
        devices = []

        for device in storage.devices:
            if device.format.type == part_type:
                devices.append(device)
        if len(devices) > 1:
            raise StorageError(_("Multiple devices found for boot loader partition '{}': {}")
                               .format(part_type,
                                       ", ".join([device.name for device in devices])))

        if devices and "msdos" in partition_table_types:
            raise StorageError(_("Both boot loader partition '{}' and MBR partitioned disk found")
                               .format(part_type))

        if not devices:
            log.debug("No devices found for boot loader partition %s", part_type)
            if "msdos" in partition_table_types:
                log.debug("Continuing because MBR partitioned disk was found")
            elif required:
                raise StorageError(_("No devices found for boot loader partition '{}'")
                                   .format(part_type))
            return False
        device = devices[0]
        log.debug("remove device %s for bootloader partition %s", device, part_type)
        destroy_device(storage, device)
        return True

    def _clear_partitions(self, storage):
        super()._clear_partitions(storage)

        # Make sure disk selection is taken into account when finding installations
        storage.roots = find_existing_installations(storage.devicetree)
        log.debug("storage.roots.mounts %s", [root.mounts for root in storage.roots])

        # Check that partitioning scheme matches
        self._check_reused_scheme(storage, self._request)

        self._clear_existing_mountpoints(storage, self._request)

    @classmethod
    def _check_reused_scheme(cls, storage, request):
        scheme = request.partitioning_scheme
        required_home_device_type = {
            AUTOPART_TYPE_BTRFS: "btrfs subvolume",
            AUTOPART_TYPE_LVM: "lvmlv",
            AUTOPART_TYPE_LVM_THINP: "lvmthinlv",
            AUTOPART_TYPE_PLAIN: "partition",
        }
        for mountpoint in request.reused_mount_points:
            if mountpoint in ["bootloader", "/boot/efi"]:
                continue
            device = cls._get_mountpoint_device(storage, mountpoint)
            if device.type != required_home_device_type[scheme]:
                raise StorageError(_("Reused device type '{}' of mount point '{}' does not "
                                     "match the required automatic partitioning scheme.")
                                   .format(device.type, mountpoint))

    @classmethod
    def _clear_existing_mountpoints(cls, storage, request):
        for mountpoint in request.removed_mount_points:
            if mountpoint == "bootloader":
                cls._remove_bootloader_partitions(storage)
            else:
                cls._remove_mountpoint(storage, mountpoint)
        for mountpoint in request.reformatted_mount_points:
            cls._reformat_mountpoint(storage, mountpoint, request)

    @classmethod
    def _schedule_reused_mountpoint(cls, storage, mountpoint):
        device = cls._get_mountpoint_device(storage, mountpoint)
        mountopts = cls._get_mountpoint_options(storage, mountpoint)
        log.debug("add mount device request for reused mountpoint: %s device: %s "
                  "with mountopts: %s",
                  mountpoint, device, mountopts)
        device.format.mountpoint = mountpoint
        if mountopts:
            device.format.options = mountopts

    @classmethod
    def _schedule_reformatted_mountpoint(cls, storage, mountpoint):
        old_device = cls._get_mountpoint_device(storage, mountpoint)
        # The device might have been recreated (btrfs)
        device = storage.devicetree.resolve_device(old_device.name)
        if device:
            log.debug("add mount device request for reformatted mountpoint: %s device: %s",
                      mountpoint, device)
            device.format.mountpoint = mountpoint
        else:
            log.debug("device for reformatted mountpoint %s not found", mountpoint)

    def _configure_partitioning(self, storage):
        """Configure the partitioning.

        :param storage: an instance of Blivet
        """
        log.debug("Executing the automatic partitioning.")

        # Get the partitioning scheme.
        scheme = self._request.partitioning_scheme

        # Set the filesystem type.
        fstype = self._request.file_system_type

        if fstype:
            storage.set_default_fstype(fstype)

        # Get the encryption configuration.
        encrypted = self._request.encrypted

        # Get LUKS format args.
        luks_format_args = self._get_luks_format_args(self._storage, self._request)

        # Set the default pbkdf args.
        pbkdf_args = luks_format_args.get('pbkdf_args', None)

        if pbkdf_args and not luks_data.pbkdf_args:
            luks_data.pbkdf_args = pbkdf_args

        # Get the autopart requests.
        requests = self._get_partitioning(storage, scheme, self._request)

        # Do the autopart.
        create_implicit_partitions = not self._implicit_partitions_reused(storage, self._request)
        self._do_autopart(storage, scheme, requests, encrypted, luks_format_args,
                          create_implicit_partitions)

        self._schedule_existing_mountpoints(storage, self._request)

    @classmethod
    def _schedule_existing_mountpoints(cls, storage, request):
        for mountpoint in request.reused_mount_points:
            cls._schedule_reused_mountpoint(storage, mountpoint)
        for mountpoint in request.reformatted_mount_points:
            cls._schedule_reformatted_mountpoint(storage, mountpoint)

    @staticmethod
    def _get_luks_format_args(storage, request):
        """Arguments for the LUKS format constructor.

        :param storage: blivet.Blivet instance
        :param request: a partitioning request
        :return: a dictionary of arguments
        """
        if not request.encrypted:
            return {}

        luks_version = request.luks_version or storage.default_luks_version
        escrow_cert = storage.get_escrow_certificate(request.escrow_certificate)

        pbkdf_args = get_pbkdf_args(
            luks_version=luks_version,
            pbkdf_type=request.pbkdf or None,
            max_memory_kb=request.pbkdf_memory,
            iterations=request.pbkdf_iterations,
            time_ms=request.pbkdf_time
        )

        return {
            "passphrase": request.passphrase,
            "cipher": request.cipher,
            "luks_version": luks_version,
            "pbkdf_args": pbkdf_args,
            "escrow_cert": escrow_cert,
            "add_backup_passphrase": request.backup_passphrase_enabled,
            "opal_admin_passphrase": request.opal_admin_passphrase,
        }

    @staticmethod
    def _get_partitioning(storage, scheme, request: PartitioningRequest):
        """Get the partitioning requests for autopart.

        :param storage: blivet.Blivet instance
        :param scheme: a type of the partitioning scheme
        :param request: partitioning parameters
        :return: a list of full partitioning specs
        """
        specs = []
        swap = None

        # Create partitioning specs based on the default configuration.
        for spec in get_default_partitioning():
            # Skip mount points excluded from the chosen scheme.
            if spec.schemes and scheme not in spec.schemes:
                continue

            # Skip excluded or reused mount points.
            skipped = request.excluded_mount_points
            skipped.extend(request.reused_mount_points)
            skipped.extend(request.reformatted_mount_points)
            if (spec.mountpoint or spec.fstype) in skipped:
                continue

            # Detect swap.
            if spec.fstype == "swap":
                swap = spec

            specs.append(spec)

        # Add a swap if hibernation was requested in kickstart.
        if request.hibernation and swap is None:
            swap = get_part_spec({"name": "swap"})
            specs.append(swap)

        # Configure specs.
        for spec in specs:
            # Set the default filesystem type.
            if spec.fstype is None:
                spec.fstype = storage.get_fstype(spec.mountpoint)

            # Update the size of swap.
            if spec.fstype == "swap":
                disk_space = storage.get_disk_free_space()
                swap.size = suggest_swap_size(hibernation=request.hibernation,
                                              disk_space=disk_space)

        return specs

    @classmethod
    def _implicit_partitions_reused(cls, storage, request):
        for mountpoint in cls._reused_devices_mountpoints(request):
            device = cls._get_mountpoint_device(storage, mountpoint)
            if hasattr(device, "vg"):
                log.debug("reusing volume group %s for %s", device.vg, mountpoint)
                return True
            if hasattr(device, "volume"):
                log.debug("reusing volume %s for %s", device.volume, mountpoint)
                return True
        return False

    @staticmethod
    def _do_autopart(storage, scheme, requests, encrypted=False, luks_fmt_args=None,
                     create_implicit_partitions=True):
        """Perform automatic partitioning.

        :param storage: an instance of Blivet
        :param scheme: a type of the partitioning scheme
        :param requests: list of partitioning requests
        :param encrypted: encrypt the scheduled partitions
        :param luks_fmt_args: arguments for the LUKS format constructor
        """
        log.debug("scheme: %s", scheme)
        log.debug("requests:\n%s", "".join([str(p) for p in requests]))
        log.debug("encrypted: %s", encrypted)
        log.debug("storage.disks: %s", [d.name for d in storage.disks])
        log.debug("storage.partitioned: %s",
                  [d.name for d in storage.partitioned if d.format.supported])
        log.debug("all names: %s", [d.name for d in storage.devices])
        log.debug("boot disk: %s", getattr(storage.bootloader.stage1_disk, "name", None))

        disks = get_candidate_disks(storage)
        log.debug("candidate disks: %s", [d.name for d in disks])

        # Schedule implicit partitions.
        devs = []
        if create_implicit_partitions:
            extra_disks = get_disks_for_implicit_partitions(disks, scheme, requests)
            devs = schedule_implicit_partitions(
                storage, extra_disks, scheme, encrypted, luks_fmt_args
            )

        # Schedule requested partitions.
        devs = schedule_partitions(storage, disks, devs, scheme, requests, encrypted, luks_fmt_args)

        # run the autopart function to allocate and grow partitions
        do_partitioning(storage, boot_disk=storage.bootloader.stage1_disk)
        schedule_volumes(storage, devs, scheme, requests, encrypted)

        # grow LVs
        grow_lvm(storage)

        # only newly added swaps should appear in the fstab
        new_swaps = (dev for dev in storage.swaps if not dev.format.exists)
        storage.set_fstab_swaps(new_swaps)
