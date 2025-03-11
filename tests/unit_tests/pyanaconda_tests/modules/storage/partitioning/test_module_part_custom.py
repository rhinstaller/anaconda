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
from unittest.mock import Mock, PropertyMock, patch

import pytest
from blivet.devices import PartitionDevice
from blivet.formats import get_format
from blivet.size import Size

from pyanaconda.modules.common.errors.storage import UnavailableDataError
from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.modules.storage.devicetree.model import InstallerStorage
from pyanaconda.modules.storage.partitioning.custom.custom_interface import (
    CustomPartitioningInterface,
)
from pyanaconda.modules.storage.partitioning.custom.custom_module import (
    CustomPartitioningModule,
)
from pyanaconda.modules.storage.partitioning.custom.custom_partitioning import (
    CustomPartitioningTask,
)
from pyanaconda.modules.storage.storage import StorageService
from tests.unit_tests.pyanaconda_tests import (
    check_task_creation,
    patch_dbus_get_proxy,
    patch_dbus_publish_object,
)


class CustomPartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the custom partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = CustomPartitioningModule()
        self.interface = CustomPartitioningInterface(self.module)

    def test_publication(self):
        """Test the DBus representation."""
        assert isinstance(self.module.for_publication(), CustomPartitioningInterface)

    def test_data(self, ):
        """Test the data property."""
        with pytest.raises(UnavailableDataError):
            if self.module.data:
                self.fail("The data should not be available.")

        data = Mock()
        self.module.process_kickstart(data)
        assert self.module.data == data

    @patch_dbus_publish_object
    def test_configure_with_task(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_changed(Mock())
        self.module.process_kickstart(Mock())
        task_path = self.interface.ConfigureWithTask()

        obj = check_task_creation(task_path, publisher, CustomPartitioningTask)

        assert obj.implementation._storage == self.module.storage


class CustomPartitioningKickstartTestCase(unittest.TestCase):
    """Test the custom partitioning module with kickstart."""

    def setUp(self):
        """Set up the module."""
        self.module = CustomPartitioningModule()
        self.interface = CustomPartitioningInterface(self.module)

    def _process_kickstart(self, ks_in):
        """Process the kickstart."""
        storage_module = StorageService()
        handler = storage_module.get_kickstart_handler()
        parser = storage_module.get_kickstart_parser(handler)
        parser.readKickstartFromString(ks_in)
        self.module.process_kickstart(handler)

    def _setup_kickstart(self):
        """Set up the kickstart."""
        storage_module = StorageService()
        handler = storage_module.get_kickstart_handler()
        self.module.setup_kickstart(handler)
        return handler

    @patch_dbus_publish_object
    def test_requires_passphrase(self, publisher):
        """Test RequiresPassphrase."""
        self._process_kickstart("part /")
        assert self.interface.RequiresPassphrase() is False
        self._process_kickstart("part / --encrypted")
        assert self.interface.RequiresPassphrase() is True
        self.interface.SetPassphrase("123456")
        assert self.interface.RequiresPassphrase() is False

    @patch_dbus_get_proxy
    @patch.object(InstallerStorage, 'mountpoints', new_callable=PropertyMock)
    def test_prepboot_bootloader_in_kickstart(self, mock_mountpoints, dbus):
        """Test that a prepboot bootloader shows up in the ks data."""
        # set up prepboot partition
        bootloader_device_obj = PartitionDevice("test_partition_device")
        bootloader_device_obj.size = Size('5 MiB')
        bootloader_device_obj.format = get_format("prepboot")

        # mountpoints must exist for update_ksdata to run
        mock_mountpoints.values.return_value = []

        # set up the storage
        self.module.on_storage_changed(create_storage())
        assert self.module.storage

        self.module.storage.bootloader.stage1_device = bootloader_device_obj

        # initialize ksdata
        ksdata = self._setup_kickstart()
        assert "part prepboot" in str(ksdata)

    @patch_dbus_get_proxy
    @patch.object(InstallerStorage, 'devices', new_callable=PropertyMock)
    @patch.object(InstallerStorage, 'mountpoints', new_callable=PropertyMock)
    def test_biosboot_bootloader_in_kickstart(self, mock_mountpoints, mock_devices, dbus):
        """Test that a biosboot bootloader shows up in the ks data."""
        # set up biosboot partition
        biosboot_device_obj = PartitionDevice("biosboot_partition_device")
        biosboot_device_obj.size = Size('1MiB')
        biosboot_device_obj.format = get_format("biosboot")

        # mountpoints must exist for updateKSData to run
        mock_devices.return_value = [biosboot_device_obj]
        mock_mountpoints.values.return_value = []

        # set up the storage
        self.module.on_storage_changed(create_storage())
        assert self.module.storage

        # initialize ksdata
        ksdata = self._setup_kickstart()
        assert "part biosboot" in str(ksdata)
