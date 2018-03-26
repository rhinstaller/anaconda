#
# Copyright (C) 2018  Red Hat, Inc.
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

from pyanaconda.core.constants import CLEAR_PARTITIONS_LINUX
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION, \
    DISK_SELECTION
from pyanaconda.modules.storage.disk_initialization import DiskInitializationModule
from pyanaconda.modules.storage.disk_initialization.initialization_interface import \
    DiskInitializationInterface
from pyanaconda.modules.storage.disk_selection import DiskSelectionModule
from pyanaconda.modules.storage.disk_selection.selection_interface import DiskSelectionInterface
from pyanaconda.modules.storage.storage import StorageModule
from pyanaconda.modules.storage.storage_interface import StorageInterface
from tests.pyanaconda_tests import check_kickstart_interface, check_dbus_property


class StorageInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the storage module."""

    def setUp(self):
        """Set up the module."""
        self.storage_module = StorageModule()
        self.storage_interface = StorageInterface(self.storage_module)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.storage_interface.KickstartCommands,
                         ["zerombr", "clearpart", "ignoredisk"])

        self.assertEqual(self.storage_interface.KickstartSections, [])
        self.assertEqual(self.storage_interface.KickstartAddons, [])

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.storage_interface, ks_in, ks_out)

    def no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def kickstart_empty_test(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def zerombr_kickstart_test(self):
        """Test the zerombr command."""
        ks_in = """
        zerombr
        """
        ks_out = """
        # Clear the Master Boot Record
        zerombr
        """
        self._test_kickstart(ks_in, ks_out)

    def clearpart_none_kickstart_test(self):
        """Test the clearpart command with the none option."""
        ks_in = """
        clearpart --none
        """
        ks_out = """
        # Partition clearing information
        clearpart --none
        """
        self._test_kickstart(ks_in, ks_out)

    def clearpart_all_kickstart_test(self):
        """Test the clearpart command with the all option."""
        ks_in = """
        clearpart --all
        """
        ks_out = """
        # Partition clearing information
        clearpart --all
        """
        self._test_kickstart(ks_in, ks_out)

    def clearpart_linux_kickstart_test(self):
        """Test the clearpart command with the linux option."""
        ks_in = """
        clearpart --linux
        """
        ks_out = """
        # Partition clearing information
        clearpart --linux
        """
        self._test_kickstart(ks_in, ks_out)

    def clearpart_cdl_kickstart_test(self):
        """Test the clearpart command with the cdl option."""
        ks_in = """
        clearpart --all --cdl
        """
        ks_out = """
        # Partition clearing information
        clearpart --all --cdl
        """
        self._test_kickstart(ks_in, ks_out)

    def clearpart_initlabel_kickstart_test(self):
        """Test the clearpart command with the initlabel option."""
        ks_in = """
        clearpart --all --initlabel
        """
        ks_out = """
        # Partition clearing information
        clearpart --all --initlabel
        """
        self._test_kickstart(ks_in, ks_out)

    def clearpart_disklabel_kickstart_test(self):
        """Test the clearpart command with the disklabel option."""
        ks_in = """
        clearpart --all --disklabel=msdos
        """
        ks_out = """
        # Partition clearing information
        clearpart --all --disklabel=msdos
        """
        self._test_kickstart(ks_in, ks_out)

    def clearpart_list_kickstart_test(self):
        """Test the clearpart command with the list option."""
        ks_in = """
        clearpart --list=sda2,sda3,sdb1
        """
        ks_out = """
        # Partition clearing information
        clearpart --list=sda2,sda3,sdb1
        """
        self._test_kickstart(ks_in, ks_out)

    def clearpart_drives_kickstart_test(self):
        """Test the clearpart command with the drives option."""
        ks_in = """
        clearpart --all --drives=sda,sdb
        """
        ks_out = """
        # Partition clearing information
        clearpart --all --drives=sda,sdb
        """
        self._test_kickstart(ks_in, ks_out)

    def ignoredisk_drives_kickstart_test(self):
        """Test the ignoredisk command with the drives option."""
        ks_in = """
        ignoredisk --drives=sda,sdb
        """
        ks_out = """
        ignoredisk --drives=sda,sdb
        """
        self._test_kickstart(ks_in, ks_out)


class DiskInitializationInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the disk initialization module."""

    def setUp(self):
        """Set up the module."""
        self.disk_init_module = DiskInitializationModule()
        self.disk_init_interface = DiskInitializationInterface(self.disk_init_module)

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


class DiskSelectionInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the disk selection module."""

    def setUp(self):
        """Set up the module."""
        self.disk_selection_module = DiskSelectionModule()
        self.disk_selection_interface = DiskSelectionInterface(self.disk_selection_module)

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            DISK_SELECTION,
            self.disk_selection_interface,
            *args, **kwargs
        )

    def selected_disks_property_test(self):
        """Test the selected disks property."""
        self._test_dbus_property(
            "SelectedDisks",
            ["sda", "sdb"]
        )

    def ignored_disks_property_test(self):
        """Test the ignored disks property."""
        self._test_dbus_property(
            "IgnoredDisks",
            ["sda", "sdb"]
        )
