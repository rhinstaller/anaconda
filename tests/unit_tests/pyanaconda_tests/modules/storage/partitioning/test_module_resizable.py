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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
import pytest

from unittest.mock import patch

from blivet.devices import StorageDevice, DiskDevice, PartitionDevice
from blivet.formats import get_format
from blivet.formats.fs import FS
from blivet.size import Size

from pyanaconda.modules.storage.partitioning.automatic.resizable_interface import \
    ResizableDeviceTreeInterface
from pyanaconda.modules.storage.partitioning.automatic.resizable_module import \
    ResizableDeviceTreeModule
from pyanaconda.modules.common.errors.storage import ProtectedDeviceError
from pyanaconda.modules.storage.devicetree import create_storage


class ResizableDeviceTreeTestCase(unittest.TestCase):
    """Test DBus interface of the auto partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = ResizableDeviceTreeModule()
        self.interface = ResizableDeviceTreeInterface(self.module)

    @property
    def storage(self):
        """Get the storage object."""
        return self.module.storage

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.storage.devicetree._add_device(device)

    def test_publication(self):
        """Test the DBus representation."""
        assert isinstance(self.module.for_publication(), ResizableDeviceTreeInterface)

    def test_is_device_partitioned(self):
        """Test IsDevicePartitioned."""
        self.module.on_storage_changed(create_storage())
        self._add_device(DiskDevice(
            "dev1"
        ))
        self._add_device(DiskDevice(
            "dev2",
            fmt=get_format("disklabel")
        ))

        assert self.interface.IsDevicePartitioned("dev1") is False
        assert self.interface.IsDevicePartitioned("dev2") is True

    @patch.object(FS, "update_size_info")
    def test_is_device_shrinkable(self, update_size_info):
        """Test IsDeviceShrinkable."""
        self.module.on_storage_changed(create_storage())

        dev1 = StorageDevice(
            "dev1",
            exists=True,
            size=Size("10 GiB"),
            fmt=get_format(None, exists=True)
        )

        self._add_device(dev1)
        assert self.interface.IsDeviceShrinkable("dev1") is False

        dev1._resizable = True
        dev1.format._resizable = True
        dev1.format._min_size = Size("1 GiB")
        assert self.interface.IsDeviceShrinkable("dev1") is True

        dev1.format._min_size = Size("10 GiB")
        assert self.interface.IsDeviceShrinkable("dev1") is False

    def test_get_device_partitions(self):
        """Test GetDevicePartitions."""
        self.module.on_storage_changed(create_storage())
        dev1 = DiskDevice(
            "dev1"
        )
        self._add_device(dev1)

        dev2 = DiskDevice(
            "dev2",
            fmt=get_format("disklabel")
        )
        self._add_device(dev2)

        dev3 = PartitionDevice(
            "dev3"
        )
        dev2.add_child(dev3)
        self._add_device(dev3)

        assert self.interface.GetDevicePartitions("dev1") == []
        assert self.interface.GetDevicePartitions("dev2") == ["dev3"]
        assert self.interface.GetDevicePartitions("dev3") == []

    def test_get_device_size_limits(self):
        """Test GetDeviceSizeLimits."""
        self.module.on_storage_changed(create_storage())
        self._add_device(StorageDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 MiB")
        ))

        min_size, max_size = self.interface.GetDeviceSizeLimits("dev1")
        assert min_size == 0
        assert max_size == 0

    def test_shrink_device(self):
        """Test ShrinkDevice."""
        self.module.on_storage_changed(create_storage())

        sda1 = StorageDevice(
            "sda1",
            exists=False,
            size=Size("10 GiB"),
            fmt=get_format("ext4")
        )
        self.module.storage.devicetree._add_device(sda1)

        def resize_device(device, size):
            device.size = size

        self.module.storage.resize_device = resize_device

        sda1.protected = True
        with pytest.raises(ProtectedDeviceError):
            self.interface.ShrinkDevice("sda1", Size("3 GiB").get_bytes())

        sda1.protected = False
        self.interface.ShrinkDevice("sda1", Size("3 GiB").get_bytes())
        assert sda1.size == Size("3 GiB")

        self.interface.ShrinkDevice("sda1", Size("5 GiB").get_bytes())
        assert sda1.size == Size("3 GiB")

    def test_remove_device(self):
        """Test RemoveDevice."""
        self.module.on_storage_changed(create_storage())

        dev1 = StorageDevice(
            "dev1",
            exists=False,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        )
        dev2 = StorageDevice(
            "dev2",
            exists=False,
            parents=[dev1],
            size=Size("6 GiB"),
            fmt=get_format("ext4")
        )
        dev3 = StorageDevice(
            "dev3",
            exists=False,
            parents=[dev1],
            size=Size("9 GiB"),
            fmt=get_format("ext4")
        )

        self.module.storage.devicetree._add_device(dev1)
        self.module.storage.devicetree._add_device(dev2)
        self.module.storage.devicetree._add_device(dev3)

        dev1.protected = True
        with pytest.raises(ProtectedDeviceError):
            self.interface.RemoveDevice("dev1")

        assert dev1 in self.module.storage.devices
        assert dev2 in self.module.storage.devices
        assert dev3 in self.module.storage.devices

        dev1.protected = False
        dev2.protected = True
        self.interface.RemoveDevice("dev1")

        assert dev1 in self.module.storage.devices
        assert dev2 in self.module.storage.devices
        assert dev3 not in self.module.storage.devices

        dev2.protected = False
        self.interface.RemoveDevice("dev1")

        assert dev1 not in self.module.storage.devices
        assert dev2 not in self.module.storage.devices
        assert dev3 not in self.module.storage.devices
