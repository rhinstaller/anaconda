#
# Utilities for the manual partitioning module
#
# Copyright (C) 2024 Red Hat, Inc.
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
from blivet.formats import get_format

from pyanaconda.core.i18n import _


def _recreate_btrfs_volume(storage, device):
    """Recreate a btrfs volume device by destroying and adding it.

    :param storage: an instance of the Blivet's storage object
    :param device: a BtrfsVolumeDevice to recreate
    """
    if device.children:
        raise StorageError(
            _("Cannot reformat Btrfs volume '{}' with "
              "existing subvolumes").format(device.name))
    storage.destroy_device(device)
    for parent in device.parents:
        storage.format_device(parent, get_format("btrfs"))
    new_btrfs = storage.new_btrfs(parents=device.parents[:],
                                  name=device.name)
    storage.create_device(new_btrfs)
    return new_btrfs


def _recreate_btrfs_subvolume(storage, device):
    """Recreate a btrfs subvolume device by destroying and adding it.
    :param storage: an instance of the Blivet's storage object
    :param device: a BtrfsSubVolumeDevice to recreate
    """
    storage.recursive_remove(device)
    new_btrfs = storage.new_btrfs(parents=device.parents[:],
                                  name=device.name,
                                  subvol=True)
    storage.create_device(new_btrfs)
    return new_btrfs


def recreate_btrfs_device(storage, device):
    """Recreate a device by destroying and adding it.

    :param storage: an instance of the Blivet's storage object
    :param device: a block device to be recreated
    """
    if device.type == "btrfs volume":
        # can't use device factory for just the volume
        return _recreate_btrfs_volume(storage, device)
    elif device.type == "btrfs subvolume":
        # using the factory for subvolumes in some cases removes
        # the volume too, we don't want that
        return _recreate_btrfs_subvolume(storage, device)


def reformat_device(storage, device, format_type=None, dependencies=None):
    dependencies = dependencies or {}
    mount_options = None
    if format_type:
        fmt = get_format(format_type)

        if not fmt:
            raise StorageError(
                _("Unknown or invalid format '{}' specified for "
                    "device '{}'").format(format_type, device.name)
            )
    else:
        old_fmt = device.format

        if not old_fmt or old_fmt.type is None:
            raise StorageError(_("No format on device '{}'").format(device.name))

        fmt = get_format(old_fmt.type)

    if device.raw_device.type in ("btrfs volume", "btrfs subvolume"):
        # 'Format', or rather clear the device by recreating it

        # recreating @device will remove all nested subvolumes of it,
        # so guard the list of dependencies
        if device.raw_device.type == "btrfs volume":
            dep_subvolumes = device.raw_device.subvolumes
        elif device.raw_device.type == "btrfs subvolume":
            dep_subvolumes = [sub.name for sub in device.raw_device.volume.subvolumes
                              if sub.depends_on(device.raw_device)]
        problem_subvolumes = [(device_name, mountpoint)
                              for device_name, mountpoint in dependencies.items()
                              if device_name in dep_subvolumes]

        if problem_subvolumes:
            err = (_("{} mounted as {}").format(*dep) for dep in problem_subvolumes)
            raise StorageError(
                _("Reformatting the '{}' subvolume will remove the following nested "
                  "subvolumes which cannot be reused: {}").format(device.raw_device.name,
                                                                  ", ".join(err)))
        device = recreate_btrfs_device(storage, device)
        mount_options = device.format.options
    else:
        storage.format_device(device, fmt)

    # make sure swaps end up in /etc/fstab
    if fmt.type == "swap":
        storage.add_fstab_swap(device)

    return device, mount_options
