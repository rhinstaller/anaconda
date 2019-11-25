#
# Viewer of the device tree
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
from abc import abstractmethod, ABC

from blivet.formats import get_format
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.errors.storage import UnknownDeviceError
from pyanaconda.modules.common.structures.storage import DeviceData, DeviceActionData, \
    DeviceFormatData, OSData
from pyanaconda.storage.utils import get_required_device_size, get_supported_filesystems

log = get_module_logger(__name__)

__all__ = ["DeviceTreeViewer"]


class DeviceTreeViewer(ABC):
    """The viewer of the device tree."""

    @property
    @abstractmethod
    def storage(self):
        """The storage model.

        :return: an instance of Blivet
        """
        return None

    def get_root_device(self):
        """Get the root device.

        :return: a name of the root device
        """
        device = self.storage.root_device
        return device.name if device else ""

    def get_devices(self):
        """Get all devices in the device tree.

        :return: a list of device names
        """
        return [d.name for d in self.storage.devices]

    def get_disks(self):
        """Get all disks in the device tree.

        Ignored disks are excluded, as are disks with no media present.

        :return: a list of device names
        """
        return [d.name for d in self.storage.disks]

    def get_mount_points(self):
        """Get all mount points in the device tree.

        :return: a dictionary of mount points and device names
        """
        return {
            mount_point: device.name
            for mount_point, device in self.storage.mountpoints.items()
        }

    def get_device_data(self, name):
        """Get the device data.

        :param name: a device name
        :return: an instance of DeviceData
        :raise: UnknownDeviceError if the device is not found
        """
        # Find the device.
        device = self._get_device(name)

        # Collect the device data.
        data = DeviceData()
        data.type = device.type
        data.name = device.name
        data.path = device.path
        data.size = device.size.get_bytes()
        data.parents = [d.name for d in device.parents]
        data.is_disk = device.is_disk
        data.removable = device.removable

        # Get the device description.
        # FIXME: We should generate the description from the device data.
        data.description = getattr(device, "description", "")

        # Collect the additional attributes.
        attrs = self._get_attributes(device, DeviceData.SUPPORTED_ATTRIBUTES)
        data.attrs = attrs

        return data

    def get_format_data(self, device_name):
        """Get the device format data.

        :param device_name: a name of the device
        :return: an instance of DeviceFormatData
        """
        device = self._get_device(device_name)
        return self._get_format_data(device.format)

    def get_format_type_data(self, format_name):
        """Get the format type data.

        For example: ext4

        :param format_name: a name of the format type
        :return: an instance of DeviceFormatData
        """
        fmt = get_format(format_name)
        return self._get_format_data(fmt)

    def _get_format_data(self, fmt):
        """Get the format data.

        :param fmt: an instance of DeviceFormat
        :return: an instance of DeviceFormatData
        """
        # Collect the format data.
        data = DeviceFormatData()
        data.type = fmt.type or ""
        data.mountable = fmt.mountable
        data.description = fmt.name or ""

        # Collect the additional attributes.
        attrs = self._get_attributes(fmt, DeviceFormatData.SUPPORTED_ATTRIBUTES)
        data.attrs = attrs

        return data

    def _get_device(self, name):
        """Find a device by its name.

        :param name: a name of the device
        :return: an instance of the Blivet's device
        :raise: UnknownDeviceError if no device is found
        """
        device = self.storage.devicetree.get_device_by_name(name, hidden=True)

        if not device:
            raise UnknownDeviceError(name)

        return device

    def _get_devices(self, names):
        """Find devices by their names.

        :param names: names of the devices
        :return: a list of instances of the Blivet's device
        """
        return list(map(self._get_device, names))

    def _get_attributes(self, obj, names):
        """Get the attributes of the given object.

        :param obj: an object
        :param names: names of the supported attributes
        :return: a dictionary of attributes
        """
        attrs = {}

        for name in names:
            try:
                value = getattr(obj, name)
            except AttributeError:
                # Skip if the attribute doesn't exist.
                continue

            if not value:
                # Skip it the attribute is not set.
                continue

            attrs[name] = str(value)

        return attrs

    def get_actions(self):
        """Get the device actions.

        The actions are pruned and sorted.

        :return: a list of DeviceActionData
        """
        actions = []

        self.storage.devicetree.actions.prune()
        self.storage.devicetree.actions.sort()

        for action in self.storage.devicetree.actions.find():
            actions.append(self._get_action_data(action))

        return actions

    def _get_action_data(self, action):
        """Get the action data.

        :param action: an instance of DeviceAction
        :return: an instance of DeviceActionData
        """
        data = DeviceActionData()
        data.action_type = action.type_string.lower()
        data.action_object = action.object_string.lower()
        data.device_name = action.device.name
        data.description = action.type_desc
        return data

    def resolve_device(self, dev_spec):
        """Get the device matching the provided device specification.

        The spec can be anything from a device name (eg: 'sda3') to a
        device node path (eg: '/dev/mapper/fedora-root') to something
        like 'UUID=xyz-tuv-qrs' or 'LABEL=rootfs'.

        If no device is found, return an empty string.

        :param dev_spec: a string describing a block device
        :return: a device name or an empty string
        """
        device = self.storage.devicetree.resolve_device(dev_spec)

        if not device:
            return ""

        return device.name

    def get_device_ancestors(self, device_name):
        """Get all ancestors of the specified device.

        The specified device is not part of the list.
        The list is sorted by names of the devices.

        :param device_name: a device name
        :return: a list of device names
        """
        device = self._get_device(device_name)
        return list(sorted(ancestor.name for ancestor in device.ancestors if ancestor != device))

    def get_supported_file_systems(self):
        """Get the supported types of filesystems.

        :return: a list of filesystem names
        """
        return [fmt.type for fmt in get_supported_filesystems() if fmt.type]

    def get_required_device_size(self, required_space):
        """Get device size we need to get the required space on the device.

        :param int required_space: a required space in bytes
        :return int: a required device size in bytes
        """
        return get_required_device_size(Size(required_space)).get_bytes()

    def get_file_system_free_space(self, mount_points):
        """Get total file system free space on the given mount points.

        :param mount_points: a list of mount points
        :return: a total size in bytes
        """
        return self.storage.get_file_system_free_space(mount_points).get_bytes()

    def get_disk_free_space(self, disk_names):
        """Get total free space on the given disks.

        Calculates free space available for use.

        :param disk_names: a list of disk names
        :return: a total size in bytes
        """
        disks = self._get_devices(disk_names)
        return self.storage.get_disk_free_space(disks).get_bytes()

    def get_disk_reclaimable_space(self, disk_names):
        """Get total reclaimable space on the given disks.

        Calculates free space unavailable but reclaimable
        from existing partitions.

        :param disk_names: a list of disk names
        :return: a total size in bytes
        """
        disks = self._get_devices(disk_names)
        return self.storage.get_disk_reclaimable_space(disks).get_bytes()

    def get_fstab_spec(self, name):
        """Get the device specifier for use in /etc/fstab.

        :param name: a name of the device
        :return: a device specifier for /etc/fstab
        """
        device = self._get_device(name)
        return device.fstab_spec

    def get_existing_systems(self):
        """"Get existing GNU/Linux installations.

        :return: a list of data about found installations
        """
        return list(map(self._get_os_data, self.storage.roots))

    def _get_os_data(self, root):
        """Get the OS data.

        :param root: an instance of Root
        :return: an instance of OSData
        """
        data = OSData()
        data.os_name = root.name or ""
        data.swap_devices = [
            device.name for device in root.swaps
        ]
        data.mount_points = {
            path: device.name for path, device in root.mounts.items()
        }
        return data
