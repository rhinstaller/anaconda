#
# Handler of the device tree
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

log = get_module_logger(__name__)

__all__ = ["DeviceTreeHandler"]


class DeviceTreeHandler(ABC):
    """The viewer of the device tree."""

    @property
    @abstractmethod
    def storage(self):
        """The storage model.

        :return: an instance of Blivet
        """
        return None

    @abstractmethod
    def _get_device(self, name):
        """Find a device by its name.

        :param name: a name of the device
        :return: an instance of the Blivet's device
        :raise: UnknownDeviceError if no device is found
        """
        raise UnknownDeviceError(name)

    def setup_device(self, device_name):
        """Open, or set up, a device.

        :param device_name: a name of the device
        """
        device = self._get_device(device_name)
        device.setup()

    def teardown_device(self, device_name):
        """Close, or tear down, a device.

        :param device_name: a name of the device
        """
        device = self._get_device(device_name)
        device.teardown(recursive=True)

    def mount_device(self, device_name, mount_point):
        """Mount a filesystem on the device.

        :param device_name: a name of the device
        :param mount_point: a path to the mount point
        """
        device = self._get_device(device_name)
        device.format.mount(mountpoint=mount_point)

    def unmount_device(self, device_name, mount_point):
        """Unmount a filesystem on the device.

        :param device_name: a name of the device
        :param mount_point: a path to the mount point
        """
        device = self._get_device(device_name)
        device.format.unmount(mountpoint=mount_point)
