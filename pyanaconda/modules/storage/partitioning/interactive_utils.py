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
from pyanaconda.product import translated_new_install_name
from pyanaconda.storage.utils import filter_unsupported_disklabel_devices


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
    all_devices = set(filter_unsupported_disklabel_devices(storage.devices))

    for root in storage.roots:
        # Collect root devices.
        root_devices = []
        root_devices.extend(root.swaps)
        root_devices.extend(root.mounts.values())

        # Don't add the root if none of the root's devices are left.
        if not filter_unsupported_disklabel_devices(root_devices):
            continue

        # Also, only include devices in an old page if the format is intact.
        if not any(d for d in root_devices if d in all_devices and d.disks
                   and (root.name == translated_new_install_name() or d.format.exists)):
            continue

        roots.append(root)

    return roots
