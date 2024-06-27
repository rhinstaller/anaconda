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
from blivet.errors import StorageError
from blivet.formats import get_format

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.storage.partitioning.automatic.noninteractive_partitioning import \
    NonInteractivePartitioningTask

log = get_module_logger(__name__)

__all__ = ["ManualPartitioningTask"]


class ManualPartitioningTask(NonInteractivePartitioningTask):
    """A task for the manual partitioning configuration."""

    def __init__(self, storage, requests):
        """Create a task.

        :param storage: an instance of Blivet
        :param requests: a list of requests
        """
        super().__init__(storage)
        self._requests = requests

    def _configure_partitioning(self, storage):
        """Configure the partitioning.

        :param storage: an instance of Blivet
        """
        log.debug("Setting up the mount points.")
        for mount_data in self._requests:
            self._setup_mount_point(storage, mount_data)

    def _setup_mount_point(self, storage, mount_data):
        """Set up a mount point.

        :param storage: an instance of the Blivet's storage object
        :param mount_data: an instance of MountPointRequest
        """
        device_spec = mount_data.device_spec
        reformat = mount_data.reformat
        format_type = mount_data.format_type
        mount_point = mount_data.mount_point

        if not reformat and not mount_point:
            # XXX empty request, ignore
            return

        device = storage.devicetree.get_device_by_device_id(device_spec)
        if device is None:
            raise StorageError(
                _("Unknown or invalid device '{}' specified").format(device_spec)
            )

        if reformat:
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

                # recreating @device will remove all nested subvolumes of it, we cannot allow
                # using these nested subvolumes for other MountPointRequest without also
                # re-creating them
                if device.raw_device.type == "btrfs volume":
                    dep_subvolumes = device.raw_device.subvolumes
                elif device.raw_device.type == "btrfs subvolume":
                    dep_subvolumes = [sub.device_id for sub in device.raw_device.volume.subvolumes
                                      if sub.depends_on(device.raw_device)]
                problem_subvolumes = [req for req in self._requests if (req.mount_point
                                                                        and not req.reformat
                                                                        and req.device_spec in
                                                                        dep_subvolumes)]
                if problem_subvolumes:
                    err = (_("{} mounted as {}").format(dep.device_spec,
                                                        dep.mount_point) for dep in problem_subvolumes)
                    raise StorageError(
                        _("Reformatting the '{}' subvolume will remove the following nested "
                          "subvolumes which cannot be reused: {}").format(device.raw_device.name,
                                                                          ", ".join(err)))
                device = self._recreate_btrfs_device(storage, device_spec)
                mount_data.mount_options = device.format.options
            else:
                storage.format_device(device, fmt)

            # make sure swaps end up in /etc/fstab
            if fmt.type == "swap":
                storage.add_fstab_swap(device)

        # add "mounted" swaps to fstab
        if device.format.type == "swap" and mount_point == "swap":
            storage.add_fstab_swap(device)

        # only set mount points for mountable formats
        if device.format.mountable and mount_point and mount_point != "none":
            device.format.mountpoint = mount_point

        device.format.create_options = mount_data.format_options
        device.format.options = mount_data.mount_options

    def _recreate_btrfs_volume(self, storage, device):
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

    def _recreate_btrfs_subvolume(self, storage, device):
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

    def _recreate_btrfs_device(self, storage, dev_spec):
        """Recreate a device by destroying and adding it.

        :param storage: an instance of the Blivet's storage object
        :param dev_spec: a string describing a block device to be recreated
        """
        device = storage.devicetree.get_device_by_device_id(dev_spec)

        if device.type == "btrfs volume":
            # can't use device factory for just the volume
            return self._recreate_btrfs_volume(storage, device)
        elif device.type == "btrfs subvolume":
            # using the factory for subvolumes in some cases removes
            # the volume too, we don't want that
            return self._recreate_btrfs_subvolume(storage, device)
