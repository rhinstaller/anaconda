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

from pyanaconda.core.constants import CLEAR_PARTITIONS_LINUX
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION
from pyanaconda.modules.storage.constants import InitializationMode
from pyanaconda.modules.storage.disk_initialization import DiskInitializationModule
from pyanaconda.modules.storage.disk_initialization.initialization_interface import \
    DiskInitializationInterface
from pyanaconda.storage.initialization import create_storage
from tests.nosetests.pyanaconda_tests import check_dbus_property


class DiskInitializationInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the disk initialization module."""

    def setUp(self):
        """Set up the module."""
        self.disk_init_module = DiskInitializationModule()
        self.disk_init_interface = DiskInitializationInterface(self.disk_init_module)

    def on_partitioning_changed_test(self):
        """Smoke test for on_partitioning_changed callback."""
        # Set up the module.
        self.disk_init_module.set_initialization_mode(InitializationMode.CLEAR_NONE)

        mode_changed_callback = Mock()
        self.disk_init_module.initialization_mode_changed.connect(mode_changed_callback)

        devices_changed_callback = Mock()
        self.disk_init_module.devices_to_clear_changed.connect(devices_changed_callback)

        drives_changed_callback = Mock()
        self.disk_init_module.drives_to_clear_changed.connect(drives_changed_callback)

        # Change the partitioning.
        self.disk_init_module.on_partitioning_changed(create_storage())

        # Check the module.
        mode_changed_callback.assert_called_once()
        self.assertEqual(self.disk_init_module.initialization_mode, InitializationMode.CLEAR_NONE)

        devices_changed_callback.assert_called_once()
        self.assertEqual(self.disk_init_module.devices_to_clear, [])

        drives_changed_callback.assert_called_once()
        self.assertEqual(self.disk_init_module.drives_to_clear, [])

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            DISK_INITIALIZATION,
            self.disk_init_interface,
            *args, **kwargs
        )

    def default_disk_label_property_test(self):
        """Test the default disk label property."""
        self._test_dbus_property(
            "DefaultDiskLabel",
            "msdos"
        )

    def format_unrecognized_enabled_property_test(self):
        """Test the can format unrecognized property."""
        self._test_dbus_property(
            "FormatUnrecognizedEnabled",
            False
        )

    def can_initialize_label_property_test(self):
        """Test the can initialize label property."""
        self._test_dbus_property(
            "InitializeLabelsEnabled",
            False
        )

    def format_ldl_enabled_property_test(self):
        """Test the can format LDL property."""
        self._test_dbus_property(
            "FormatLDLEnabled",
            True
        )

    def initialization_mode_property_test(self):
        """Test the type to clear property."""
        self._test_dbus_property(
            "InitializationMode",
            CLEAR_PARTITIONS_LINUX
        )

    def devices_to_clear_property_test(self):
        """Test the devices to clear property."""
        self._test_dbus_property(
            "DevicesToClear",
            ["sda2", "sda3", "sdb1"]
        )

    def drives_to_clear_property_test(self):
        """Test the drives to clear property."""
        self._test_dbus_property(
            "DrivesToClear",
            ["sda", "sdb"]
        )
