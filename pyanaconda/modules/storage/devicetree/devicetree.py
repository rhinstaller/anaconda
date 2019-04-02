#
# Handler of the device tree.
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

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.errors.storage import UnknownDeviceError
from pyanaconda.modules.common.structures.storage import DeviceData, DeviceActionData

log = get_module_logger(__name__)

__all__ = ["DeviceTreeHandler"]


class DeviceTreeHandler(ABC):
    """The device tree handler."""

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

        if not device:
            raise UnknownDeviceError(name)

        # Collect the device data.
        data = DeviceData()
        data.type = device.type
        data.name = device.name
        data.path = device.path
        data.size = device.size.get_bytes()
        data.parents = [d.name for d in device.parents]
        data.is_disk = device.is_disk

        # Get the device description.
        # FIXME: We should generate the description from the device data.
        data.description = getattr(device, "description", "")

        # Collect the additional attributes.
        attrs = self._get_device_attrs(device)
        data.attrs = attrs

        return data

    def _get_device(self, name):
        """Find a device by its name.

        :param name: a name of the device
        :return: an instance of the Blivet's device
        """
        return self.storage.devicetree.get_device_by_name(name, hidden=True)

    def _get_device_attrs(self, device):
        """Get the device attributes.

        :param device: an instance of the device
        :return: a dictionary of attributes
        """
        attrs = {}

        for name in DeviceData.SUPPORTED_ATTRIBUTES:
            try:
                value = getattr(device, name)
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

        :return: a list of DeviceActionData
        """
        actions = []

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
