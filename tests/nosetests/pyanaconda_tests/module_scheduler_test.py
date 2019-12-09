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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest

from blivet.devices import StorageDevice, DiskDevice
from blivet.formats import get_format
from blivet.size import Size
from dasbus.typing import get_native
from pyanaconda.modules.storage.partitioning.interactive.scheduler_interface import \
    DeviceTreeSchedulerInterface
from pyanaconda.modules.storage.partitioning.interactive.scheduler_module import \
    DeviceTreeSchedulerModule
from pyanaconda.storage.initialization import create_storage


class DeviceTreeSchedulerTestCase(unittest.TestCase):
    """Test DBus interface of the device tree scheduler."""

    def setUp(self):
        """Set up the module."""
        self.module = DeviceTreeSchedulerModule()
        self.interface = DeviceTreeSchedulerInterface(self.module)
        self.module.on_storage_changed(create_storage())

    @property
    def storage(self):
        """Get the storage object."""
        return self.module.storage

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.storage.devicetree._add_device(device)

    def publication_test(self):
        """Test the DBus representation."""
        self.assertIsInstance(self.module.for_publication(), DeviceTreeSchedulerInterface)

    def generate_system_name_test(self):
        """Test GenerateSystemName."""
        self.assertEqual(
            self.interface.GenerateSystemName(),
            "New anaconda bluesky Installation"
        )

    def generate_system_data_test(self):
        """Test GenerateSystemData."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/boot")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev3", fmt=get_format("swap")))

        os_data = self.interface.GenerateSystemData("dev1")
        self.assertEqual(get_native(os_data), {
            'mount-points': {'/boot': 'dev1', '/': 'dev2'},
            'os-name': 'New anaconda bluesky Installation',
            'swap-devices': ['dev3']
        })

    def get_partitioned_test(self):
        """Test GetPartitioned."""
        self._add_device(DiskDevice(
            "dev1",
            exists=True,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        ))
        self._add_device(DiskDevice(
            "dev2",
            exists=True,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        ))
        self._add_device(StorageDevice(
            "dev3",
            exists=True,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        ))
        self.assertEqual(self.interface.GetPartitioned(), ["dev1", "dev2"])

    def collect_new_devices_test(self):
        """Test CollectNewDevices."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/boot")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev3", fmt=get_format("swap")))
        self.assertEqual(self.interface.CollectNewDevices("dev1"), ["dev1", "dev2", "dev3"])

    def collect_unused_devices_test(self):
        """Test CollectUnusedDevices."""
        dev1 = DiskDevice(
            "dev1",
            fmt=get_format("disklabel")
        )
        dev2 = StorageDevice(
            "dev2",
            parents=[dev1],
            fmt=get_format("ext4")
        )
        dev3 = StorageDevice(
            "dev3",
            parents=[dev1],
            fmt=get_format("ext4")
        )
        dev4 = StorageDevice(
            "dev4",
            parents=[dev1],
            fmt=get_format("ext4", mountpoint="/")
        )

        self._add_device(dev1)
        self._add_device(dev2)
        self._add_device(dev3)
        self._add_device(dev4)

        self.assertEqual(self.interface.CollectUnusedDevices(), ["dev2", "dev3"])
