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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from unittest.mock import Mock

from pykickstart.constants import CLEARPART_TYPE_NONE

from pyanaconda.core.constants import CLEAR_PARTITIONS_LINUX
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.storage.constants import InitializationMode
from pyanaconda.modules.storage.disk_initialization import DiskInitializationModule
from pyanaconda.modules.storage.disk_initialization.initialization_interface import \
    DiskInitializationInterface
from pyanaconda.modules.storage.devicetree import create_storage
from tests.nosetests.pyanaconda_tests import check_dbus_property


class DiskInitializationInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the disk initialization module."""

    def setUp(self):
        """Set up the module."""
        self.disk_init_module = DiskInitializationModule()
        self.disk_init_interface = DiskInitializationInterface(self.disk_init_module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            DISK_INITIALIZATION,
            self.disk_init_interface,
            *args, **kwargs
        )

    def default_disk_label_property_test(self):
        """Test the default disk label property."""
        self._check_dbus_property(
            "DefaultDiskLabel",
            "msdos"
        )

    def format_unrecognized_enabled_property_test(self):
        """Test the can format unrecognized property."""
        self._check_dbus_property(
            "FormatUnrecognizedEnabled",
            False
        )

    def can_initialize_label_property_test(self):
        """Test the can initialize label property."""
        self._check_dbus_property(
            "InitializeLabelsEnabled",
            False
        )

    def format_ldl_enabled_property_test(self):
        """Test the can format LDL property."""
        self._check_dbus_property(
            "FormatLDLEnabled",
            True
        )

    def initialization_mode_property_test(self):
        """Test the type to clear property."""
        self._check_dbus_property(
            "InitializationMode",
            CLEAR_PARTITIONS_LINUX
        )

    def devices_to_clear_property_test(self):
        """Test the devices to clear property."""
        self._check_dbus_property(
            "DevicesToClear",
            ["sda2", "sda3", "sdb1"]
        )

    def drives_to_clear_property_test(self):
        """Test the drives to clear property."""
        self._check_dbus_property(
            "DrivesToClear",
            ["sda", "sdb"]
        )


class DiskInitializationModuleTestCase(unittest.TestCase):
    """Test the disk initialization module."""

    def setUp(self):
        """Set up the module."""
        self.disk_init_module = DiskInitializationModule()

    def storage_property_test(self):
        """Test the storage property."""
        with self.assertRaises(UnavailableStorageError):
            self.assertIsNotNone(self.disk_init_module.storage)

        storage = Mock()
        self.disk_init_module.on_storage_changed(storage)
        self.assertEqual(self.disk_init_module.storage, storage)

    def setup_kickstart_test(self):
        """Test setup_kickstart with storage."""
        storage = create_storage()
        data = Mock()

        self.disk_init_module.on_storage_changed(storage)
        self.disk_init_module.set_initialization_mode(InitializationMode.CLEAR_NONE)
        self.disk_init_module.setup_kickstart(data)

        self.assertEqual(data.clearpart.type, CLEARPART_TYPE_NONE)
        self.assertEqual(data.clearpart.devices, [])
        self.assertEqual(data.clearpart.drives, [])
