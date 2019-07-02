#
# Utilities for the interactive partitioning module
#
# Copyright (C) 2019 Red Hat, Inc.
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
from blivet import devicefactory
from blivet.devicelibs import crypto
from blivet.devices import LUKSDevice
from blivet.errors import StorageError
from blivet.formats import get_format

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import UNSUPPORTED_FILESYSTEMS
from pyanaconda.product import translated_new_install_name
from pyanaconda.storage.root import Root
from pyanaconda.storage.utils import filter_unsupported_disklabel_devices, bound_size, \
    get_supported_filesystems, PARTITION_ONLY_FORMAT_TYPES, SUPPORTED_DEVICE_TYPES

log = get_module_logger(__name__)


def collect_used_devices(storage):
    """Collect devices used in existing or new installations.

    :param storage: an instance of Blivet
    :return: a list of devices
    """
    used_devices = []

    for root in storage.roots:
        for device in list(root.mounts.values()) + root.swaps:
            if device not in storage.devices:
                continue

            used_devices.extend(device.ancestors)

    for new in [d for d in storage.devicetree.leaves if not d.format.exists]:
        if new.format.mountable and not new.format.mountpoint:
            continue

        used_devices.extend(new.ancestors)

    for device in storage.partitions:
        if getattr(device, "is_logical", False):
            extended = device.disk.format.extended_partition.path
            used_devices.append(storage.devicetree.get_device_by_path(extended))

    return used_devices


def collect_unused_devices(storage):
    """Collect devices that are not used in existing or new installations.

    :param storage: an instance of Blivet
    :return: a list of devices
    """
    used_devices = set(collect_used_devices(storage))

    unused = [
        d for d in storage.devices
        if d.disks
        and d.media_present
        and not d.partitioned
        and (d.direct or d.isleaf)
        and d not in used_devices
    ]

    # Add incomplete VGs and MDs
    incomplete = [
        d for d in storage.devicetree._devices
        if not getattr(d, "complete", True)
    ]

    # Add partitioned devices with unsupported format.
    unsupported = [
        d for d in storage.partitioned
        if not d.format.supported
    ]

    return unused + incomplete + unsupported


def collect_bootloader_devices(storage, drive):
    """Collect the bootloader devices.

    :param storage: an instance of Blivet
    :param drive: a name of the bootloader drive
    :return: a list of devices
    """
    devices = []
    boot_drive = drive

    for device in storage.devices:
        if device.format.type not in ["biosboot", "prepboot"]:
            continue

        # Boot drive may not be setup because it IS one of these.
        if not boot_drive or boot_drive in (d.name for d in device.disks):
            devices.append(device)

    return devices


def collect_new_devices(storage, drive):
    """Collect new devices.

    :param storage: an instance of Blivet
    :param drive: a name of the bootloader drive
    :return: a list of devices
    """
    # A device scheduled for formatting only belongs in the new root.
    new_devices = [
        d for d in storage.devices
        if d.direct
        and not d.format.exists
        and not d.partitioned
    ]

    # If mount points have been assigned to any existing devices, go ahead
    # and pull those in along with any existing swap devices. It doesn't
    # matter if the formats being mounted exist or not.
    new_mounts = [
        d for d in storage.mountpoints.values() if d.exists
    ]

    if new_mounts or new_devices:
        new_devices.extend(storage.mountpoints.values())
        new_devices.extend(collect_bootloader_devices(storage, drive))

    return list(set(new_devices))


def collect_selected_disks(storage, selection):
    """Collect selected disks.

    FIXME: Is this method really necessary? Remove it.

    :param storage: an instance of Blivet
    :param selection: names of selected disks
    :return: a list of devices
    """
    return [
        d for d in storage.devices
        if d.name in selection and d.partitioned
    ]


def collect_roots(storage):
    """Collect roots of existing installations.

    :param storage: an instance of Blivet
    :return: a list of roots
    """
    roots = []
    supported_devices = set(filter_unsupported_disklabel_devices(storage.devices))

    for root in storage.roots:
        # Get the name.
        name = root.name

        # Get the supported swap devices.
        swaps = [
            d for d in root.swaps
            if d in supported_devices
            and (d.format.exists or root.name == translated_new_install_name())
        ]

        # Get the supported mount points.
        mounts = {
            m: d for m, d in root.mounts.items()
            if d in supported_devices
            and (d.format.exists or root.name == translated_new_install_name())
            and d.disks
        }

        if not swaps and not mounts:
            continue

        # Add a root with supported devices.
        roots.append(Root(
            name=name,
            mounts=mounts,
            swaps=swaps
        ))

    return roots


def create_new_root(storage, drive):
    """Create a new root from the given devices.

    :param storage: an instance of Blivet
    :param drive: a name of the bootloader drive
    :return: a new root
    """
    devices = filter_unsupported_disklabel_devices(
        collect_new_devices(
            storage=storage,
            drive=drive
        )
    )

    bootloader_devices = filter_unsupported_disklabel_devices(
        collect_bootloader_devices(
            storage=storage,
            drive=drive
        )
    )

    swaps = [
        d for d in devices
        if d.format.type == "swap"
    ]

    mounts = {
        d.format.mountpoint: d for d in devices
        if getattr(d.format, "mountpoint", None)
    }

    for device in devices:
        if device in bootloader_devices:
            mounts[device.format.name] = device

    return Root(
        name=translated_new_install_name(),
        mounts=mounts,
        swaps=swaps
    )


def revert_reformat(storage, device):
    """Revert reformat of the given device.

    :param storage: an instance of Blivet
    :param device: a device to reset
    """
    # Figure out the existing device.
    if not device.raw_device.format.exists:
        original_device = device.raw_device
    else:
        original_device = device

    # Reset it.
    storage.reset_device(original_device)


def resize_device(storage, device, new_size, old_size):
    """Resize the given device.

    :param storage: an instance of Blivet
    :param device: a device to resize
    :param new_size: a new size
    :param old_size: an old size
    :return: True if the device changed its size, otherwise False
    :raise: StorageError if we fail to schedule the device resize
    """
    # If a LUKS device is being displayed, adjust the size
    # to the appropriate size for the raw device.
    use_size = new_size
    use_old_size = old_size

    if device.raw_device is not device:
        use_size = new_size + crypto.LUKS_METADATA_SIZE
        use_old_size = device.raw_device.size

    # Bound size to boundaries given by the device.
    use_size = device.raw_device.align_target_size(use_size)
    use_size = bound_size(use_size, device.raw_device, use_old_size)
    use_size = device.raw_device.align_target_size(use_size)

    # And then we need to re-check that the max size is actually
    # different from the current size.

    if use_size == device.size or use_size == device.raw_device.size:
        # The size hasn't changed.
        log.debug("canceled resize of device %s to %s", device.raw_device.name, use_size)
        return False

    if new_size == device.current_size or use_size == device.current_size:
        # The size has been set back to its original value.
        log.debug("removing resize of device %s", device.raw_device.name)

        actions = storage.devicetree.actions.find(
            action_type="resize",
            devid=device.raw_device.id
        )

        for action in reversed(actions):
            storage.devicetree.actions.remove(action)

        return bool(actions)
    else:
        # the size has changed
        log.debug("scheduling resize of device %s to %s", device.raw_device.name, use_size)

        try:
            storage.resize_device(device.raw_device, use_size)
        except (StorageError, ValueError) as e:
            log.error("failed to schedule device resize: %s", e)
            device.raw_device.size = use_old_size
            raise StorageError(str(e)) from None

        log.debug("new size: %s", device.raw_device.size)
        log.debug("target size: %s", device.raw_device.target_size)
        return True


def change_encryption(storage, device, encrypted, luks_version):
    """Change encryption of the given device.

    :param storage: an instance of Blivet
    :param device: a device to change
    :param encrypted: should we encrypt the device?
    :param luks_version: a version of LUKS
    :return: a LUKS device or a device slave
    """
    if not encrypted:
        log.info("removing encryption from %s", device.name)
        storage.destroy_device(device)
        return device.slave
    else:
        log.info("applying encryption to %s", device.name)
        new_fmt = get_format("luks", device=device.path, luks_version=luks_version)
        storage.format_device(device, new_fmt)
        luks_dev = LUKSDevice("luks-" + device.name, parents=[device])
        storage.create_device(luks_dev)
        return luks_dev


def reformat_device(storage, device, fstype, mountpoint, label):
    """Reformat the given device.

    :param storage: an instance of Blivet
    :param device: a device to reformat
    :param fstype: a file system type
    :param mountpoint: a mount point
    :param label: a label
    :raise: StorageError if we fail to format the device
    """
    log.info("scheduling reformat of %s as %s", device.name, fstype)

    old_format = device.format
    new_format = get_format(
        fstype,
        mountpoint=mountpoint,
        label=label,
        device=device.path
    )

    try:
        storage.format_device(device, new_format)
    except (StorageError, ValueError) as e:
        log.error("failed to register device format action: %s", e)
        device.format = old_format
        raise StorageError(str(e)) from None


def get_device_luks_version(device):
    """Get the LUKS version of the given device.

    :param device: a device
    :return: a LUKS version or None
    """
    device = device.raw_device

    if device.format.type == "luks":
        return device.format.luks_version

    return None


def get_device_raid_level(device):
    """Get the RAID level of the given device.

    :param device: a device
    :return: a RAID level
    """
    device = device.raw_device

    if hasattr(device, "level"):
        return device.level

    if hasattr(device, "data_level"):
        return device.data_level

    if hasattr(device, "volume"):
        return device.volume.data_level

    if not hasattr(device, "vg") and hasattr(device, "lvs") and len(device.parents) == 1:
        return get_device_raid_level(device.parents[0])

    return None


def collect_file_system_types(device):
    """Collect supported file system types for the given device.

    :param device: a device
    :return: a list of file system names
    """
    # Collect the supported filesystem types.
    supported_types = {
        fs.name for fs in get_supported_filesystems()
        if fs.name not in UNSUPPORTED_FILESYSTEMS
    }

    # Add possibly unsupported but still required file system types:
    # Add the device format type.
    supported_types.add(device.format.name)

    # Add the original device format type.
    if device.exists:
        supported_types.add(device.original_format.name)

    return list(supported_types)


def collect_device_types(device, disks):
    """Collect supported device types for the given device.

    :param device: a device
    :param disks: a list of selected disks
    :return: a list of device types
    """
    # Collect the supported device types.
    supported_types = set(SUPPORTED_DEVICE_TYPES)

    # Include the type of the given device.
    supported_types.add(devicefactory.get_device_type(device))

    # Include md only if there are two or more disks.
    if len(disks) > 1:
        supported_types.discard(devicefactory.DEVICE_TYPE_MD)

    # Include btrfs if it is both allowed and supported.
    fmt = get_format("btrfs")

    if fmt.supported \
            and fmt.formattable \
            and device.raw_device.format.type not in PARTITION_ONLY_FORMAT_TYPES + ("swap",):
        supported_types.add(devicefactory.DEVICE_TYPE_BTRFS)

    return sorted(filter(devicefactory.is_supported_device_type, supported_types))
