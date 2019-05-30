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
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.constants.interfaces import DEVICE_TREE_HANDLER
from pyanaconda.modules.common.errors.storage import UnknownDeviceError
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.storage.devicetree.populate import FindDevicesTask
from pyanaconda.modules.storage.devicetree.rescue import FindExistingSystemsTask, \
    MountExistingSystemTask
from pyanaconda.storage.utils import find_optical_media, find_mountable_partitions, unlock_device, \
    find_unconfigured_luks

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

    @abstractmethod
    def publish_task(self, namespace, task, interface=TaskInterface, message_bus=DBus):
        """Publish a task.

        :param namespace: a DBus namespace
        :param task: an instance of task
        :param interface: an interface class
        :param message_bus: a message bus
        :return: a DBus path of the published task
        """
        raise NotImplementedError()

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

    def unlock_device(self, device_name, passphrase):
        """Unlock a device.

        :param device_name: a name of the device
        :param passphrase: a passphrase
        :return: True if success, otherwise False
        """
        device = self._get_device(device_name)
        return unlock_device(self.storage, device, passphrase)

    def find_unconfigured_luks(self):
        """Find all unconfigured LUKS devices.

        Returns a list of devices that require to set up
        a passphrase to complete their configuration.

        :return: a list of device names
        """
        devices = find_unconfigured_luks(self.storage)
        return [d.name for d in devices]

    def set_device_passphrase(self, device_name, passphrase):
        """Set a passphrase for the unconfigured LUKS device.

        :param device_name: a name of the device
        :param passphrase: a passphrase
        """
        device = self._get_device(device_name)
        device.format.passphrase = passphrase
        self.storage.save_passphrase(device)

    def find_devices_with_task(self):
        """Find new devices.

        The task will populate the device tree with new devices.

        :return: a path to the task
        """
        task = FindDevicesTask(self.storage.devicetree)
        path = self.publish_task(DEVICE_TREE_HANDLER.namespace, task)
        return path

    def find_optical_media(self):
        """Find all devices with mountable optical media.

        :return: a list of device names
        """
        devices = find_optical_media(self.storage.devicetree)
        return [d.name for d in devices]

    def find_mountable_partitions(self):
        """Find all mountable partitions.

        :return: a list of device names
        """
        devices = find_mountable_partitions(self.storage.devicetree)
        return [d.name for d in devices]

    def find_existing_systems_with_task(self):
        """"Find existing GNU/Linux installations.

        The task will update data about existing installations.

        :return: a path to the task
        """
        task = FindExistingSystemsTask(self.storage.devicetree)
        task.succeeded_signal.connect(
            lambda: self._update_existing_systems(task.get_result())
        )
        path = self.publish_task(DEVICE_TREE_HANDLER.namespace, task)
        return path

    def _update_existing_systems(self, roots):
        """Update existing GNU/Linux installations.

        :param roots: a list of found OS installations
        """
        self.storage.roots = roots

    def mount_existing_system_with_task(self, sysroot, device_name, read_only):
        """Mount existing GNU/Linux installation.

        :param sysroot: a path to the root of the system
        :param device_name: a name of the root device
        :param read_only: mount the system in read-only mode
        :return: a path to the task
        """
        task = MountExistingSystemTask(
            storage=self.storage,
            sysroot=sysroot,
            device=self._get_device(device_name),
            read_only=read_only
        )

        path = self.publish_task(DEVICE_TREE_HANDLER.namespace, task)
        return path
