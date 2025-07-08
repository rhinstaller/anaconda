#
# Copyright (C) 2020  Red Hat, Inc.
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
import os
from decimal import Decimal
from enum import IntEnum

from blivet import udev

try:
    from blivet.devicefactory import DeviceTypes
except ImportError:
    # Compatibility with older versions of blivet which do not have
    # DeviceTypes.  Get rid of this code once we have a new enough blivet
    # everywhere.
    DeviceTypes = IntEnum('DeviceTypes', [
        ('LVM', 0),
        ('MD', 1),
        ('PARTITION', 2),
        ('BTRFS', 3),
        ('DISK', 4),
        ('LVM_THINP', 5),
        ('LVM_VDO', 6),
        ('STRATIS', 7),
    ])

from blivet.size import Size
from blivet.util import total_memory
from pykickstart.constants import (
    AUTOPART_TYPE_BTRFS,
    AUTOPART_TYPE_LVM,
    AUTOPART_TYPE_LVM_THINP,
    AUTOPART_TYPE_PLAIN,
)

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import N_

log = get_module_logger(__name__)

# Maximum ratio of swap size to disk size (10 %).
MAX_SWAP_DISK_RATIO = Decimal('0.1')

SIZE_POLICY_MAX = -1
SIZE_POLICY_AUTO = 0

# Use blivet values plus Unsupported which contains info about devices without
# a supported type.
DEVICE_TYPES = IntEnum('DEVICE_TYPES',
                       [(dt.name, dt.value) for dt in DeviceTypes] + [('UNSUPPORTED', -1)])

# Backwards compat, make DEVICE_TYPE_* constants that mirror the contents of
# the Enum.
for dt_pair in DEVICE_TYPES:
    globals()['DEVICE_TYPE_%s' % dt_pair.name] = dt_pair.value

NAMED_DEVICE_TYPES = (
    DEVICE_TYPES.BTRFS,
    DEVICE_TYPES.LVM,
    DEVICE_TYPES.MD,
    DEVICE_TYPES.LVM_THINP
)

CONTAINER_DEVICE_TYPES = (
    DEVICE_TYPES.LVM,
    DEVICE_TYPES.BTRFS,
    DEVICE_TYPES.LVM_THINP
)

SUPPORTED_DEVICE_TYPES = (
    DEVICE_TYPES.PARTITION,
    DEVICE_TYPES.LVM,
    DEVICE_TYPES.LVM_THINP
)

PARTITION_ONLY_FORMAT_TYPES = (
    "macefi",
    "prepboot",
    "biosboot",
    "appleboot"
)

PROTECTED_FORMAT_TYPES = (
    "efi",
    "macefi",
    "prepboot",
    "appleboot"
)


DEVICE_TEXT_MAP = {dt.value: N_("Unsupported") for dt in DEVICE_TYPES}
DEVICE_TEXT_MAP.update({
    DEVICE_TYPES.LVM: N_("LVM"),
    DEVICE_TYPES.MD: N_("RAID"),
    DEVICE_TYPES.PARTITION: N_("Standard Partition"),
    DEVICE_TYPES.BTRFS: N_("Btrfs"),
    DEVICE_TYPES.LVM_THINP: N_("LVM Thin Provisioning"),
    DEVICE_TYPES.DISK: N_("Disk")
})

AUTOPART_CHOICES = (
    (N_("Standard Partition"), AUTOPART_TYPE_PLAIN),
    (N_("Btrfs"), AUTOPART_TYPE_BTRFS),
    (N_("LVM"), AUTOPART_TYPE_LVM),
    (N_("LVM Thin Provisioning"), AUTOPART_TYPE_LVM_THINP)
)

AUTOPART_DEVICE_TYPES = {
    AUTOPART_TYPE_LVM: DEVICE_TYPES.LVM,
    AUTOPART_TYPE_LVM_THINP: DEVICE_TYPES.LVM_THINP,
    AUTOPART_TYPE_PLAIN: DEVICE_TYPES.PARTITION,
    AUTOPART_TYPE_BTRFS: DEVICE_TYPES.BTRFS
}

MOUNTPOINT_DESCRIPTIONS = {
    "Swap": N_("The 'swap' area on your computer is used by the operating\n"
               "system when running low on memory."),
    "Boot": N_("The 'boot' area on your computer is where files needed\n"
               "to start the operating system are stored."),
    "Root": N_("The 'root' area on your computer is where core system\n"
               "files and applications are stored."),
    "Home": N_("The 'home' area on your computer is where all your personal\n"
               "data is stored."),
    "BIOS Boot": N_("The BIOS boot partition is required to enable booting\n"
                    "from GPT-partitioned disks on BIOS hardware."),
    "PReP Boot": N_("The PReP boot partition is required as part of the\n"
                    "boot loader configuration on some PPC platforms.")
}

# Private cache for the function device_matches.
_udev_device_dict_cache = None


def device_type_from_autopart(autopart_type):
    """Get device type matching the given autopart type."""
    return AUTOPART_DEVICE_TYPES.get(autopart_type, DEVICE_TYPES.LVM)


def get_supported_autopart_choices():
    """Get the supported autopart choices.

    # FIXME: Move this function to the Storage module.
    """
    from blivet.devicefactory import is_supported_device_type
    return [c for c in AUTOPART_CHOICES if is_supported_device_type(AUTOPART_DEVICE_TYPES[c[1]])]


def device_matches(spec, devicetree=None, disks_only=False):
    """Return names of block devices matching the provided specification.

    :param str spec: a device identifier (name, UUID=<uuid>, &c)
    :keyword devicetree: device tree to look up devices in (optional)
    :type devicetree: :class:`blivet.DeviceTree`
    :param bool disks_only: if only disk devices matching the spec should be returned
    :returns: names of matching devices
    :rtype: list of str

    The spec can contain multiple "sub specs" delimited by a |, for example:

    "sd*|hd*|vd*"

    In such case we resolve the specs from left to right and return all
    unique matches, for example:

    ["sda", "sda1", "sda2", "sdb", "sdb1", "vdb"]

    If disks_only is specified we only return
    disk devices matching the spec. For the example above
    the output with disks_only=True would be:

    ["sda", "sdb", "vdb"]

    Also note that parse methods will not have access to a devicetree, while execute
    methods will. The devicetree is superior in that it can resolve md
    array names and in that it reflects scheduled device removals, but for
    normal local disks udev.resolve_devspec should suffice.
    """

    matches = []
    # the device specifications might contain multiple "sub specs" separated by a |
    # - the specs are processed from left to right
    for single_spec in spec.split("|"):
        full_spec = single_spec
        if not full_spec.startswith("/dev/"):
            full_spec = os.path.normpath("/dev/" + full_spec)

        # the regular case
        single_spec_matches = udev.resolve_glob(full_spec)
        for match in single_spec_matches:
            if match not in matches:
                # skip non-disk devices in disk-only mode
                if disks_only and not _is_device_name_disk(match):
                    continue
                matches.append(match)

        dev_name = None
        # Use spec here instead of full_spec to preserve the spec and let the
        # called code decide whether to treat the spec as a path instead of a name.
        if devicetree is None:
            # we run the spec through resolve_devspec() here as unlike resolve_glob()
            # it can also resolve labels and UUIDs
            dev_name = udev.resolve_devspec(single_spec)
            if disks_only and dev_name:
                if not _is_device_name_disk(dev_name):
                    dev_name = None  # not a disk
        else:
            # devicetree can also handle labels and UUIDs
            device = devicetree.resolve_device(single_spec)
            if device:
                dev_name = device.name
                if disks_only and not _is_device_name_disk(dev_name, devicetree=devicetree):
                    dev_name = None  # not a disk

        # The dev_name variable can be None if the spec is not not found or is not valid,
        # but we don't want that ending up in the list.
        if dev_name and dev_name not in matches:
            matches.append(dev_name)

    log.debug("%s matches %s for devicetree=%s and disks_only=%s",
              spec, matches, devicetree, disks_only)

    return matches


def _is_device_name_disk(device_name, devicetree=None, refresh_udev_cache=False):
    """Report if the given device name corresponds to a disk device.

    Check if the device name is a disk device or not. This function uses
    the provided Blivet devicetree for the checking and Blivet udev module
    if no devicetree is provided.

    Please note that the udev based check uses an internal cache that is generated
    when this function is first called in the udev checking mode. This basically
    means that udev devices added later will not be taken into account.
    If this is a problem for your usecase then use the refresh_udev_cache option
    to force a refresh of the udev cache.

    :param str device_name: name of the device to check
    :param devicetree: device tree to look up devices in (optional)
    :type devicetree: :class:`blivet.DeviceTree`
    :param bool refresh_udev_cache: governs if the udev device cache should be refreshed
    :returns: True if the device name corresponds to a disk, False if not
    :rtype: bool
    """
    if devicetree is None:
        global _udev_device_dict_cache
        if device_name:
            if _udev_device_dict_cache is None or refresh_udev_cache:
                # Lazy load the udev dick that contains the {device_name : udev_device,..,}
                # mappings. The operation could be quite costly due to udev_settle() calls,
                # so we cache it in this non-elegant way.
                # An unfortunate side effect of this is that udev devices that show up after
                # this function is called for the first time will not be taken into account.
                _udev_device_dict_cache = {}

                for d in udev.get_devices():
                    # Add the device name to the cache.
                    _udev_device_dict_cache[udev.device_get_name(d)] = d
                    # If the device is md, add the md name as well.
                    if udev.device_is_md(d) and udev.device_get_md_name(d):
                        _udev_device_dict_cache[udev.device_get_md_name(d)] = d

            udev_device = _udev_device_dict_cache.get(device_name)
            return udev_device and udev.device_is_disk(udev_device)
        else:
            return False
    else:
        device = devicetree.get_device_by_name(device_name)
        return device and device.is_disk


def suggest_swap_size(hibernation=False, disk_space=None):
    """Suggest the size of the swap partition that will be created.

    :param bool hibernation: calculate swap size big enough for hibernation
    :param disk_space: how much disk space is available
    :return: calculated swap size
    """
    mem = total_memory()
    mem = ((mem / 16) + 1) * 16
    log.info("Detected %s of memory", mem)

    sixty_four_gib = Size("64 GiB")

    # the succeeding if-statement implements the following formula for
    # suggested swap size.
    #
    # swap(mem) = 2 * mem, if mem < 2 GiB
    #           = mem,     if 2 GiB <= mem < 8 GiB
    #           = mem / 2, if 8 GIB <= mem < 64 GiB
    #           = 32 GiB,  if mem >= 64 GiB
    if mem < Size("2 GiB"):
        swap = 2 * mem

    elif mem < Size("8 GiB"):
        swap = mem

    elif mem < sixty_four_gib:
        swap = mem / 2

    else:
        swap = Size("32 GiB")

    if hibernation:
        if mem <= sixty_four_gib:
            swap = mem + swap
        else:
            log.info("Ignoring --hibernation option on systems with greater than %s of RAM",
                     sixty_four_gib)

    elif disk_space is not None:
        max_swap = disk_space * MAX_SWAP_DISK_RATIO

        if swap > max_swap:
            log.info("Suggested swap size (%(swap)s) exceeds %(percent)d %% of "
                     "disk space, using %(percent)d %% of disk space (%(size)s) "
                     "instead.", {"percent": MAX_SWAP_DISK_RATIO * 100,
                                  "swap": swap,
                                  "size": max_swap})
            swap = max_swap

    log.info("Swap attempt of %s", swap)
    return swap
