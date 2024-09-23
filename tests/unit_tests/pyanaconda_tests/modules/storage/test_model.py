#
# Copyright (C) 2022  Red Hat, Inc.
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
import unittest

from blivet.devices import StorageDevice

from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.modules.storage.devicetree.root import Root


class InstallerStorageTestCase(unittest.TestCase):
    """Test the InstallerStorage class."""

    def setUp(self):
        """Set up the test."""
        self.maxDiff = None
        self.storage = create_storage()

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.storage.devicetree._add_device(device)

    def _check_device_copy(self, original_device, device):
        """Check a copy of the device."""
        assert device
        assert device.name == original_device.name
        assert device.id == original_device.id
        assert device is not original_device

    def test_copy_no_devices(self):
        """Test the copy method with no devices."""
        storage_copy = self.storage.copy()
        assert not storage_copy.devices
        assert not storage_copy.roots

    def test_copy_devices(self):
        """Test the copy method with some devices."""
        dev1 = StorageDevice("dev1")
        self._add_device(dev1)

        dev2 = StorageDevice("dev2")
        self._add_device(dev2)

        storage_copy = self.storage.copy()
        assert len(storage_copy.devices) == 2
        assert len(storage_copy.roots) == 0

        dev1_copy = storage_copy.devicetree.get_device_by_name("dev1")
        self._check_device_copy(dev1, dev1_copy)

        dev2_copy = storage_copy.devicetree.get_device_by_name("dev2")
        self._check_device_copy(dev2, dev2_copy)

    def test_copy_root_no_devices(self):
        """Test the copy method with a root and no devices."""
        root1 = Root(name="Linux 1")
        self.storage.roots.append(root1)

        storage_copy = self.storage.copy()
        assert len(storage_copy.roots) == 1

        root1_copy = storage_copy.roots[0]
        assert root1_copy.name == root1.name
        assert not root1_copy.devices
        assert not root1_copy.mounts

    def test_copy_root_missing_devices(self):
        """Test the copy method with a root and missing devices."""
        dev1 = StorageDevice("dev1")
        self._add_device(dev1)

        dev2 = StorageDevice("dev2")
        dev3 = StorageDevice("dev3")

        root1 = Root(
            name="Linux 1",
            devices=[dev1, dev2, dev3],
            mounts={"/": dev1, "/home": dev2},
        )
        self.storage.roots.append(root1)

        storage_copy = self.storage.copy()
        assert len(storage_copy.roots) == 1
        root1_copy = storage_copy.roots[0]
        assert root1_copy.name == "Linux 1"

        assert len(root1_copy.devices) == 1
        dev1_copy = root1_copy.devices[0]
        assert dev1_copy in storage_copy.devices
        self._check_device_copy(dev1, dev1_copy)

        assert len(root1_copy.mounts) == 1
        dev1_copy = root1_copy.mounts["/"]
        assert dev1_copy in storage_copy.devices
        self._check_device_copy(dev1, dev1_copy)

    def test_copy_roots(self):
        """Test the copy method with several roots and devices."""
        dev1 = StorageDevice("dev1")
        self._add_device(dev1)

        dev2 = StorageDevice("dev2")
        self._add_device(dev2)

        dev3 = StorageDevice("dev3")
        self._add_device(dev3)

        root1 = Root(
            name="Linux 1",
            devices=[dev2],
            mounts={"/": dev2},
        )
        self.storage.roots.append(root1)

        root2 = Root(
            name="Linux 2",
            devices=[dev1, dev3],
            mounts={"/": dev1, "/home": dev3},
        )
        self.storage.roots.append(root2)

        storage_copy = self.storage.copy()
        assert len(storage_copy.roots) == 2

        root1_copy = storage_copy.roots[0]
        assert root1_copy.name == "Linux 1"
        assert len(root1_copy.devices) == 1
        assert len(root1_copy.mounts) == 1
        assert "/" in root1_copy.mounts

        root2_copy = storage_copy.roots[1]
        assert root2_copy.name == "Linux 2"
        assert len(root2_copy.devices) == 2
        assert len(root2_copy.mounts) == 2
        assert "/" in root2_copy.mounts
        assert "/home" in root2_copy.mounts

    def test_copy_mountopts(self):
        """Test the copy of mount options."""
        dev1 = StorageDevice("dev1")
        self._add_device(dev1)

        dev2 = StorageDevice("dev2")
        self._add_device(dev2)

        dev3 = StorageDevice("dev3")
        self._add_device(dev3)

        root1 = Root(
            name="Linux 1",
            devices=[dev2],
            mounts={"/": dev2},
        )
        self.storage.roots.append(root1)

        root2 = Root(
            name="Linux 2",
            devices=[dev1, dev3],
            mounts={"/": dev1, "/home": dev3},
            mountopts={"/home": "opt1"}
        )
        self.storage.roots.append(root2)

        storage_copy = self.storage.copy()
        assert len(storage_copy.roots) == 2

        root1_copy = storage_copy.roots[0]
        assert root1_copy.name == "Linux 1"
        assert len(root1_copy.mountopts) == 0

        root2_copy = storage_copy.roots[1]
        assert root2_copy.name == "Linux 2"
        assert len(root2_copy.mountopts) == 1
