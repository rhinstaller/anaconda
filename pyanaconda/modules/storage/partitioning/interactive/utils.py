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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import itertools
import re

from blivet import devicefactory
from blivet.devicelibs import crypto, raid
from blivet.devices import LUKSDevice, LVMVolumeGroupDevice, MDRaidArrayDevice
from blivet.errors import StorageError
from blivet.formats import get_format
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.product import get_product_name, get_product_version
from pyanaconda.core.storage import (
    CONTAINER_DEVICE_TYPES,
    DEVICE_TEXT_MAP,
    DEVICE_TYPES,
    NAMED_DEVICE_TYPES,
    PARTITION_ONLY_FORMAT_TYPES,
    SUPPORTED_DEVICE_TYPES,
)
from pyanaconda.modules.common.errors.configuration import StorageConfigurationError
from pyanaconda.modules.common.errors.storage import (
    UnknownDeviceError,
    UnsupportedDeviceError,
)
from pyanaconda.modules.common.structures.device_factory import (
    DeviceFactoryPermissions,
    DeviceFactoryRequest,
)
from pyanaconda.modules.storage.devicetree.root import Root
from pyanaconda.modules.storage.devicetree.utils import (
    get_supported_filesystems,
    is_supported_filesystem,
)
from pyanaconda.modules.storage.disk_initialization import DiskInitializationConfig
from pyanaconda.modules.storage.platform import PLATFORM_MOUNT_POINTS, platform

log = get_module_logger(__name__)


def filter_unsupported_disklabel_devices(devices):
    """Return input list minus any devices that exist on an unsupported disklabel."""
    return [d for d in devices if not any(
        not getattr(p, "disklabel_supported", True) for p in d.ancestors
    )]


def collect_used_devices(storage):
    """Collect devices used in existing or new installations.

    :param storage: an instance of Blivet
    :return: a list of devices
    """
    used_devices = []

    for root in storage.roots:
        for device in root.devices:
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

    return filter_unsupported_disklabel_devices(unused + incomplete + unsupported)


def collect_bootloader_devices(storage, boot_drive):
    """Collect the bootloader devices.

    :param storage: an instance of Blivet
    :param boot_drive: a name of the bootloader drive
    :return: a list of devices
    """
    devices = []

    for device in storage.devices:
        if device.format.type not in ["biosboot", "prepboot"]:
            continue

        # Boot drive may not be setup because it IS one of these.
        if not boot_drive or boot_drive in (d.name for d in device.disks):
            devices.append(device)

    return filter_unsupported_disklabel_devices(devices)


def collect_new_devices(storage, boot_drive):
    """Collect new devices.

    :param storage: an instance of Blivet
    :param boot_drive: a name of the bootloader drive
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
        new_devices.extend(collect_bootloader_devices(storage, boot_drive))

    # Remove duplicates, but keep the order.
    return filter_unsupported_disklabel_devices(list(dict.fromkeys(new_devices)))


def collect_roots(storage):
    """Collect roots of existing installations.

    :param storage: an instance of Blivet
    :return: a list of roots
    """
    roots = []
    supported_devices = set(filter_unsupported_disklabel_devices(storage.devices))

    # Get the name of the new installation.
    new_root_name = get_new_root_name()

    for root in storage.roots:
        # Get the name.
        name = root.name

        # Get the supported devices.
        devices = [
            d for d in root.devices
            if d in supported_devices
            and (d.format.exists or root.name == new_root_name)
        ]

        # Get the supported mount points.
        mounts = {
            m: d for m, d in root.mounts.items()
            if d in supported_devices
            and (d.format.exists or root.name == new_root_name)
            and d.disks
        }

        if not devices and not mounts:
            continue

        # Add a root with supported devices.
        roots.append(Root(
            name=name,
            devices=devices,
            mounts=mounts,
        ))

    return roots


def get_new_root_name():
    """Get the name of the new installation.

    :return: a translated string
    """
    return _("New {name} {version} Installation").format(
        name=get_product_name(), version=get_product_version()
    )


def create_new_root(storage, boot_drive):
    """Create a new root from the given devices.

    :param storage: an instance of Blivet
    :param boot_drive: a name of the bootloader drive
    :return: a new root
    """
    devices = collect_new_devices(
        storage=storage,
        boot_drive=boot_drive
    )

    mounts = {
        d.format.mountpoint: d for d in devices
        if getattr(d.format, "mountpoint", None)
    }

    return Root(
        name=get_new_root_name(),
        devices=devices,
        mounts=mounts,
    )


def collect_mount_points():
    """Collect supported mount points.

    :return: a list of paths
    """
    paths = ["/", "/boot", "/home", "/var"]

    # Add the mount point requirements for bootloader stage1 devices.
    paths.extend(platform.stage1_constraints[PLATFORM_MOUNT_POINTS])

    # Sort the list now so all the real mount points go to the front,
    # then add all the pseudo mount points we have.
    paths.sort()
    paths += ["swap"]

    for fmt in ["appleboot", "biosboot", "prepboot"]:
        if get_format(fmt).supported:
            paths += [fmt]

    return paths


def validate_label(label, fmt):
    """Validate the label.

    :param str label: a label
    :param DeviceFormat fmt: a device format to label
    :return: an error message
    """
    if not label:
        return None

    if not fmt.labeling():
        return _("Cannot set label on file system.")

    if not fmt.label_format_ok(label):
        return _("Unacceptable label format for file system.")

    return None


def validate_mount_point(path, mount_points):
    """Validate the given path of a mount point.

    :param path: a path to validate
    :param mount_points: a list of existing mount points
    :return: an error message
    """
    system_mount_points = ["/dev", "/proc", "/run", "/sys"]

    if path in mount_points:
        return _("That mount point is already in use. Try something else?")

    if not path:
        return _("Please enter a valid mount point.")

    if path in system_mount_points:
        return _("That mount point is invalid. Try something else?")

    if ((len(path) > 1 and path.endswith("/")) or
            not path.startswith("/") or
            " " in path or
            re.search(r'/\.*/', path) or
            re.search(r'/\.+$', path)):
        # - does not end with '/' unless mountpoint _is_ '/'
        # - starts with '/' except for "swap", &c
        # - does not contain spaces
        # - does not contain pairs of '/' enclosing zero or more '.'
        # - does not end with '/' followed by one or more '.'
        return _("That mount point is invalid. Try something else?")

    return None


def validate_container_name(storage, name):
    """Validate the given container name.

    :param storage: an instance of Blivet
    :param name: a container name
    :return: an error message or None
    """
    safe_name = storage.safe_device_name(name)

    if name != safe_name:
        return _("Invalid container name.")

    if name in storage.names:
        return _("Name is already in use.")

    return None


def get_raid_level_by_name(name):
    """Get the RAID level object for the given name.

    :param name: a name of the RAID level
    :return: an instance of RAIDLevel
    """
    if not name:
        return None

    return raid.get_raid_level(name)


def validate_raid_level(raid_level, num_members):
    """Validate the given raid level.

    :param raid_level: a RAID level
    :param num_members: a number of members
    :return: an error message
    """
    if num_members < raid_level.min_members:
        return _("The RAID level you have selected ({level}) requires more disks "
                 "({min}) than you currently have selected ({count}).").format(
            level=raid_level,
            min=raid_level.min_members,
            count=num_members
        )

    return None


def validate_device_factory_request(storage, request: DeviceFactoryRequest):
    """Validate the given device info.

    :param storage: an instance of Blivet
    :param request: a device factory request to validate
    :return: an error message
    """
    device = storage.devicetree.get_device_by_device_id(request.device_spec)
    device_type = request.device_type
    reformat = request.reformat
    fs_type = request.format_type
    encrypted = request.device_encrypted
    raid_level = get_raid_level_by_name(request.device_raid_level)
    mount_point = request.mount_point
    label = request.label
    num_disk = len(request.disks)

    changed_label = label != getattr(device.format, "label", "")
    changed_fstype = fs_type != device.format.type

    if changed_label or changed_fstype:
        error = validate_label(
            label,
            get_format(fs_type)
        )
        if error:
            return error

    is_format_mountable = get_format(fs_type).mountable
    changed_mount_point = mount_point != getattr(device.format, "mountpoint", "")

    if reformat and is_format_mountable and not mount_point:
        return _("Please enter a mount point.")

    if changed_mount_point and mount_point:
        error = validate_mount_point(
            mount_point,
            storage.mountpoints.keys()
        )
        if error:
            return error

    supported_types = (DEVICE_TYPES.PARTITION, DEVICE_TYPES.MD)

    if mount_point == "/boot/efi" and device_type not in supported_types:
        return _("/boot/efi must be on a device of type {type} or {another}").format(
            type=_(DEVICE_TEXT_MAP[DEVICE_TYPES.PARTITION]),
            another=_(DEVICE_TEXT_MAP[DEVICE_TYPES.MD])
        )

    if device_type != DEVICE_TYPES.PARTITION and \
            fs_type in PARTITION_ONLY_FORMAT_TYPES:
        return _("{fs} must be on a device of type {type}").format(
            fs=fs_type,
            type=_(DEVICE_TEXT_MAP[DEVICE_TYPES.PARTITION])
        )

    if mount_point and encrypted and mount_point.startswith("/boot"):
        return _("{} cannot be encrypted").format(mount_point)

    if encrypted and fs_type in PARTITION_ONLY_FORMAT_TYPES:
        return _("{} cannot be encrypted").format(fs_type)

    if mount_point == "/" and device.format.exists and not reformat:
        return _("You must create a new file system on the root device.")

    if (raid_level is not None or device_type == DEVICE_TYPES.MD) and \
            raid_level not in get_supported_raid_levels(device_type):
        return _("Device does not support RAID level selection {}.").format(raid_level)

    if raid_level is not None:
        error = validate_raid_level(
            raid_level,
            num_disk
        )
        if error:
            return error

    return None


def suggest_device_name(storage, device):
    """Get a suggestion for a device name.

    :param storage: an instance of Blivet
    :param device: a device to name
    :return:
    """
    return storage.suggest_device_name(
        swap=bool(device.format.type == "swap"),
        mountpoint=getattr(device.format, "mountpoint", None)
    )


def revert_reformat(storage, device):
    """Revert reformat of the given device.

    :param storage: an instance of Blivet
    :param device: a device to reset
    """
    # Skip if formats exists.
    if device.format.exists and device.raw_device.format.exists:
        log.debug("Nothing to revert for %s.", device.name)
        return

    # Figure out the existing device.
    if not device.raw_device.format.exists:
        original_device = device.raw_device
    else:
        original_device = device

    # Reset it.
    log.debug("Resetting device %s.", original_device.name)
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
    log.debug("Resizing device %s to %s.", device, new_size)

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

    if use_size in (device.size, device.raw_device.size):
        # The size hasn't changed.
        log.debug("Canceled resize of device %s to %s.", device.raw_device.name, use_size)
        return False

    if device.current_size in (new_size, use_size):
        # The size has been set back to its original value.
        log.debug("Removing resize of device %s.", device.raw_device.name)

        actions = storage.devicetree.actions.find(
            action_type="resize",
            devid=device.raw_device.id
        )

        for action in reversed(actions):
            storage.devicetree.actions.remove(action)

        return bool(actions)
    else:
        # the size has changed
        log.debug("Scheduling resize of device %s to %s.", device.raw_device.name, use_size)

        try:
            storage.resize_device(device.raw_device, use_size)
        except (StorageError, ValueError) as e:
            log.exception("Failed to schedule device resize: %s", e)
            device.raw_device.size = use_old_size
            raise StorageError(str(e)) from None

        log.debug(
            "Device %s has size: %s (target %s)",
            device.raw_device.name,
            device.raw_device.size, device.raw_device.target_size
        )
        return True


def bound_size(size, device, old_size):
    """Returns a size bounded by the maximum and minimum size for the device.

    :param size: the candidate size
    :type size: :class:`blivet.size.Size`
    :param device: the device being displayed
    :type device: :class:`blivet.devices.StorageDevice`
    :param old_size: the fallback size
    :type old_size: :class:`blivet.size.Size`
    :returns: a size to which to set the device
    :rtype: :class:`blivet.size.Size`

    If size is 0, interpreted as set size to maximum possible.
    If no maximum size is available, reset size to old_size, but
    log a warning.
    """
    max_size = device.max_size
    min_size = device.min_size
    if not size:
        if max_size:
            log.info("No size specified, using maximum size for "
                     "this device (%d).", max_size)
            size = max_size
        else:
            log.warning("No size specified and no maximum size available, "
                        "setting size back to original size (%d).", old_size)
            size = old_size
    else:
        if max_size:
            if size > max_size:
                log.warning("Size specified (%d) is greater than the maximum "
                            "size for this device (%d), using maximum size.",
                            size, max_size)
                size = max_size
        else:
            log.warning("Unknown upper bound on size. Using requested size (%d).",
                        size)

        if size < min_size:
            log.warning("Size specified (%d) is less than the minimum size for "
                        "this device (%d), using minimum size.", size, min_size)
            size = min_size

    return size


def change_encryption(storage, device, encrypted, luks_version):
    """Change encryption of the given device.

    :param storage: an instance of Blivet
    :param device: a device to change
    :param encrypted: should we encrypt the device?
    :param luks_version: a version of LUKS
    :return: a LUKS device or a LUKS device parent device
    """
    if not encrypted:
        log.info("Removing encryption from %s.", device.name)
        storage.destroy_device(device)
        return device.raw_device
    else:
        log.info("Applying encryption to %s.", device.name)
        luks_version = luks_version or storage.default_luks_version
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
    log.info("Scheduling reformat of %s as %s.", device.name, fstype)

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
        log.exception("Failed to register device format action: %s", e)
        device.format = old_format
        raise StorageError(str(e)) from None


def get_device_luks_version(device):
    """Get the LUKS version of the given device.

    :param device: a device
    :return: a LUKS version or an empty string
    """
    device = device.raw_device

    if device.format.type == "luks":
        return device.format.luks_version

    return ""


def get_container_luks_version(container):
    """Get the LUKS version of the given container.

    :param container: a container
    :return: a LUKS version or an empty string
    """
    for device in itertools.chain([container], container.parents):
        luks_version = get_device_luks_version(device)

        if luks_version:
            return luks_version

    return ""


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

    return None


def get_device_raid_level_name(device):
    """Get the RAID level name of the given device."""
    raid_level = get_device_raid_level(device)
    return raid_level.name if raid_level else ""


def get_container_raid_level(container):
    """Get the RAID level of the given container.

    :param container: a container
    :return: a RAID level
    """
    # Try to get a RAID level of this device.
    raid_level = get_device_raid_level(container)

    if raid_level:
        return raid_level

    device = container.raw_device

    # Or get a RAID level of the LVM container.
    if hasattr(device, "lvs") and len(device.parents) == 1:
        return get_container_raid_level(device.parents[0])

    return None


def get_container_raid_level_name(device):
    """Get the RAID level name of the given container."""
    raid_level = get_container_raid_level(device)
    return raid_level.name if raid_level else ""


def collect_file_system_types(device):
    """Collect supported file system types for the given device.

    :param device: a device
    :return: a list of file system types
    """
    # Collect the supported filesystem types.
    supported_types = set(get_supported_filesystems())

    # Add possibly unsupported but still required file system types:
    # Add the device format type.
    if device.format.type:
        supported_types.add(device.format.type)

    # Add the original device format type.
    if device.exists and device.original_format.type:
        supported_types.add(device.original_format.type)

    return sorted(supported_types)


def collect_device_types(device):
    """Collect supported device types for the given device.

    :param device: a device
    :return: a list of device types
    """
    # Collect the supported device types.
    supported_types = set(SUPPORTED_DEVICE_TYPES)
    supported_types.add(DEVICE_TYPES.MD)

    # Include the type of the given device.
    supported_types.add(devicefactory.get_device_type(device))

    # Include btrfs if it is both allowed and supported.
    fmt = get_format("btrfs")

    if fmt.supported \
            and fmt.formattable \
            and device.raw_device.format.type not in PARTITION_ONLY_FORMAT_TYPES + ("swap",):
        supported_types.add(DEVICE_TYPES.BTRFS)

    return sorted(filter(devicefactory.is_supported_device_type, supported_types))


def get_device_factory_arguments(storage, request: DeviceFactoryRequest, subset=None):
    """Get the device factory arguments for the given request.

    :param storage: an instance of Blivet
    :param request: a device factory request
    :param subset: a subset of argument names to return or None
    :return: a dictionary of device factory arguments
    """
    args = {
        "device_type": request.device_type,
        "device": storage.devicetree.get_device_by_device_id(request.device_spec),
        "disks": [storage.devicetree.get_device_by_device_id(d) for d in request.disks],
        "mountpoint": request.mount_point or None,
        "fstype": request.format_type or None,
        "label": request.label or None,
        "luks_version": request.luks_version or storage.default_luks_version,
        "device_name": request.device_name or None,
        "size": Size(request.device_size) or None,
        "raid_level": get_raid_level_by_name(request.device_raid_level),
        "encrypted": request.device_encrypted,
        "container_name": request.container_name or None,
        "container_size": get_container_size_policy_by_number(request.container_size_policy),
        "container_raid_level": get_raid_level_by_name(request.container_raid_level),
        "container_encrypted": request.container_encrypted,
    }

    if subset:
        args = {name: value for name, value in args.items() if name in subset}

    log.debug(
        "Generated factory arguments: {\n%s\n}",
        ",\n".join("{} = {}".format(name, repr(value)) for name, value in args.items())
    )

    return args


def generate_device_factory_request(storage, device) -> DeviceFactoryRequest:
    """Generate a device info for the given device.

    :param storage: an instance of Blivet
    :param device: a device
    :return: a device factory request
    """
    device_type = devicefactory.get_device_type(device)

    if device_type is None:
        raise UnsupportedDeviceError("Unsupported type of {}.".format(device.name))

    # Generate the device data.
    request = DeviceFactoryRequest()
    request.device_spec = device.device_id
    request.device_name = getattr(device.raw_device, "lvname", device.raw_device.name)
    request.device_size = device.size.get_bytes()
    request.device_type = device_type
    request.reformat = not device.format.exists
    request.format_type = device.format.type or ""
    request.device_encrypted = isinstance(device, LUKSDevice)
    request.luks_version = get_device_luks_version(device)
    request.label = getattr(device.format, "label", "") or ""
    request.mount_point = getattr(device.format, "mountpoint", "") or ""
    request.device_raid_level = get_device_raid_level_name(device)

    if hasattr(device, "req_disks") and not device.exists:
        disks = device.req_disks
    else:
        disks = device.disks

    request.disks = [d.device_id for d in disks]

    if request.device_type not in CONTAINER_DEVICE_TYPES:
        return request

    # Generate the container data.
    factory = devicefactory.get_device_factory(
        storage,
        device_type=device_type,
        device=device.raw_device
    )
    container = factory.get_container()

    if container:
        set_container_data(request, container)

    return request


def set_container_data(request: DeviceFactoryRequest, container):
    """Set the container data in the device factory request.

    :param request: a device factory request
    :param container: a container
    """
    request.container_spec = container.device_id
    request.container_name = container.name
    request.container_encrypted = container.encrypted
    request.container_raid_level = get_container_raid_level_name(container)
    request.container_size_policy = get_container_size_policy(container)

    if request.container_encrypted:
        request.luks_version = get_container_luks_version(container)


def generate_container_data(storage, request: DeviceFactoryRequest):
    """Generate the container data for the device factory request.

    :param storage: an instance of Blivet
    :param request: a device factory request
    """
    # Reset all container data.
    request.reset_container_data()

    # Check the device type.
    if request.device_type not in CONTAINER_DEVICE_TYPES:
        return

    # Find a container of the requested type.
    device = storage.devicetree.get_device_by_device_id(request.device_spec)
    container = get_container(storage, request.device_type, device.raw_device)

    if container:
        # Set the request from the found container.
        set_container_data(request, container)
    else:
        # Set the request from a new container.
        request.container_name = storage.suggest_container_name()
        request.container_raid_level = get_default_container_raid_level_name(
            request.device_type
        )


def update_container_data(storage, request: DeviceFactoryRequest, container_name):
    """Update the container data in the device factory request.

    :param storage: an instance of Blivet
    :param request: a device factory request
    :param container_name: a container name to apply
    """
    # Reset all container data.
    request.reset_container_data()

    # Check the device type.
    if request.device_type not in CONTAINER_DEVICE_TYPES:
        raise StorageError("Invalid device type.")

    # Find the container in the device tree if any.
    container = storage.devicetree.get_device_by_name(container_name)

    if container:
        # Set the request from the found container.
        set_container_data(request, container)

        # Use the container's disks.
        request.disks = [d.device_id for d in container.disks]
    else:
        # Set the request from the new container.
        request.container_name = container_name
        request.container_raid_level = get_default_container_raid_level_name(
            request.device_type
        )


def generate_device_factory_permissions(storage, request: DeviceFactoryRequest):
    """Generate permissions for the requested device.

    :param storage: an instance of Blivet
    :param request: a device factory request
    :return: device factory permissions
    """
    permissions = DeviceFactoryPermissions()
    device = storage.devicetree.get_device_by_device_id(request.device_spec)
    container = storage.devicetree.get_device_by_device_id(request.container_spec)
    fmt = get_format(request.format_type)

    if not device:
        raise UnknownDeviceError(request.device_spec)

    if device.protected:
        return permissions

    permissions.device_type = not device.raw_device.exists
    permissions.device_raid_level = not device.raw_device.exists
    permissions.mount_point = fmt.mountable

    permissions.label = \
        request.reformat \
        and fmt.labeling()

    permissions.reformat = \
        device.raw_device.exists \
        and not device.raw_device.format_immutable \
        and is_supported_filesystem(request.format_type)

    permissions.device_size = \
        device.resizable or (
                not device.exists
                and request.device_type not in {
                    DEVICE_TYPES.BTRFS
                }
        )

    permissions.device_name = \
        not device.raw_device.exists \
        and device.raw_device.type != "btrfs volume" \
        and request.device_type in NAMED_DEVICE_TYPES

    permissions.format_type = \
        request.reformat \
        and request.device_type not in {
            DEVICE_TYPES.BTRFS
        }

    permissions.device_encrypted = \
        request.reformat \
        and not request.container_encrypted \
        and request.device_type not in {
            DEVICE_TYPES.BTRFS
        } \
        and not any(
            a.format.type == "luks" and a.format.exists
            for a in device.raw_device.ancestors if a != device
        )

    permissions.disks = \
        not device.exists \
        and not device.raw_device.exists \
        and request.device_type not in CONTAINER_DEVICE_TYPES

    can_change_container = \
        request.device_type in CONTAINER_DEVICE_TYPES \
        and not getattr(container, "exists", False)

    can_replace_container = \
        request.device_type in CONTAINER_DEVICE_TYPES \
        and not device.raw_device.exists \
        and device.raw_device != container

    permissions.container_spec = can_replace_container
    permissions.container_name = can_change_container
    permissions.container_encrypted = can_change_container
    permissions.container_raid_level = can_change_container
    permissions.container_size_policy = can_change_container

    return permissions


def reset_device(storage, device):
    """Reset the given device in the storage model.

    FIXME: Merge with destroy_device.

    :param storage: an instance of Blivet
    :param device: an instance of a device
    :raise: StorageConfigurationError in case of failure
    """
    log.debug("Reset device: %s", device.name)

    try:
        if device.exists:
            # Revert changes done to an existing device.
            storage.reset_device(device)
        else:
            # Destroy a non-existing device.
            _destroy_device(storage, device)
    except (StorageError, ValueError) as e:
        log.exception("Failed to reset a device: %s", e)
        raise StorageConfigurationError(str(e)) from None


def destroy_device(storage, device):
    """Destroy the given device in the storage model.

    :param storage: an instance of Blivet
    :param device: an instance of a device
    :raise: StorageConfigurationError in case of failure
    """
    log.debug("Destroy device: %s", device.name)

    try:
        _destroy_device(storage, device)
    except (StorageError, ValueError) as e:
        log.exception("Failed to destroy a device: %s", e)
        raise StorageConfigurationError(str(e)) from None


def _destroy_device(storage, device):
    """Destroy the given device in the storage model.

    :param storage: an instance of Blivet
    :param device: an instance of a device
    """
    # Remove the device.
    if device.is_disk:
        if device.partitioned and not device.format.supported:
            storage.recursive_remove(device)
        storage.initialize_disk(device)
    elif device.direct and not device.isleaf:
        # We shouldn't call this method for with non-leaf devices
        # except for those which are also directly accessible like
        # lvm snapshot origins and btrfs subvolumes that contain
        # other subvolumes.
        storage.recursive_remove(device)
    else:
        storage.destroy_device(device)

    # Remove empty extended partitions.
    if getattr(device, "is_logical", False):
        storage.remove_empty_extended_partitions()

    # If we've just removed the last partition and the disk label
    # is preexisting, reinitialize the disk.
    if device.type == "partition" and device.exists and device.disk.format.exists:
        config = DiskInitializationConfig()
        config.initialize_labels = True

        if config.can_initialize(storage, device.disk):
            storage.initialize_disk(device.disk)

    # Get the device container.
    if hasattr(device, "vg"):
        container = device.vg
        device_type = devicefactory.get_device_type(device)
    elif hasattr(device, "volume"):
        container = device.volume
        device_type = DEVICE_TYPES.BTRFS
    else:
        container = None
        device_type = None

    # Adjust container to size of remaining devices, if auto-sized.
    if (container and not container.exists and container.children and
            container.size_policy == devicefactory.SIZE_POLICY_AUTO):
        # Create the device factory.
        factory = devicefactory.get_device_factory(
            storage,
            device_type=device_type,
            size=Size(0),
            disks=container.disks,
            container_name=container.name,
            container_encrypted=container.encrypted,
            container_raid_level=get_container_raid_level(container),
            container_size=container.size_policy,
        )

        # Configure the factory's devices.
        factory.configure()

    # Finally, remove empty parents of the device, except for btrfs subvolumes.
    for parent in device.parents:
        if not parent.children and not parent.is_disk and parent.type != "btrfs subvolume":
            destroy_device(storage, parent)


def rename_container(storage, container, name):
    """Rename the given container.

    :param storage: an instance of Blivet
    :param container: an instance of a container
    :param name: a new name of the container
    """
    log.debug("Rename container %s to %s.", container.name, name)

    try:
        container.name = name
    except ValueError as e:
        log.exception("Failed to rename container: %s", str(e))
        raise StorageError(str(e)) from None

    # Fix the btrfs label.
    if container.format.type == "btrfs":
        container.format.label = name


def get_container(storage, device_type, device=None):
    """Get a container of the given type.

    :param storage: an instance of Blivet
    :param device_type: a device type
    :param device: a defined factory device or None
    :return: a container device
    """
    if device_type not in CONTAINER_DEVICE_TYPES:
        raise StorageError("Invalid device type {}".format(device_type))

    if device and devicefactory.get_device_type(device) != device_type:
        device = None

    factory = devicefactory.get_device_factory(
        storage,
        device_type=device_type,
        size=Size(0),
    )

    return factory.get_container(device=device)


def get_container_size_policy(container):
    """Get a container size policy."""
    size = getattr(container, "size_policy", container.size)

    if size is None:
        return devicefactory.SIZE_POLICY_AUTO

    if size > 0:
        return Size(size).get_bytes()

    return size


def get_container_size_policy_by_number(number):
    """Get a container size policy by the given number."""
    if number <= 0:
        return number

    return Size(number)


def get_default_container_raid_level_name(device_type):
    """Get the default RAID level for this device type's container type.

    :param int device_type: a device_type
    :return str: a name of the default RAID level or an empty string
    """
    if device_type == DEVICE_TYPES.BTRFS:
        return "single"

    return ""


def collect_containers(storage, device_type):
    """Collect containers of the given type.

    :param storage: an instance of Blivet
    :param device_type: a device type
    :return: a list of container devices
    """
    if device_type == DEVICE_TYPES.BTRFS:
        return storage.btrfs_volumes
    else:
        return storage.vgs


def get_supported_raid_levels(device_type):
    """Get RAID levels for the specified device type.

    :param device_type: a type of the device
    :return: a list of RAID levels
    """
    return devicefactory.get_supported_raid_levels(device_type)


def check_device_completeness(device):
    """Check that the specified device is complete.

    :param device: a device to check
    :return: an error message or None
    """
    if getattr(device, "complete", True):
        return None

    if isinstance(device, MDRaidArrayDevice):
        total = device.member_devices
        missing = total - len(device.parents)
        return _("This Software RAID array is missing %(missing)d of %(total)d "
                 "member partitions. You can remove it or select a different "
                 "device.") % {"missing": missing, "total": total}

    if isinstance(device, LVMVolumeGroupDevice):
        total = device.pv_count
        missing = total - len(device.parents)
        return _("This LVM Volume Group is missing %(missingPVs)d of %(totalPVs)d "
                 "physical volumes. You can remove it or select a different "
                 "device.") % {"missingPVs": missing, "totalPVs": total}

    return _("This %(type)s device is missing member devices. You can remove "
             "it or select a different device.") % {"type": device.type}
