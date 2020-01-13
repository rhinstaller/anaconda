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

from blivet.devices import DiskDevice
from blivet.formats import get_format
from blivet.size import Size

from pyanaconda.modules.common.constants.objects import DISK_SELECTION
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.storage.disk_selection import DiskSelectionModule
from pyanaconda.modules.storage.disk_selection.selection_interface import DiskSelectionInterface
from pyanaconda.storage.initialization import create_storage
from tests.nosetests.pyanaconda_tests import check_dbus_property


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

    def validate_selected_disks_test(self):
        """Test ValidateSelectedDisks."""
        storage = create_storage()
        self.disk_selection_module.on_storage_changed(storage)

        dev1 = DiskDevice(
            "dev1",
            exists=False,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        )
        dev2 = DiskDevice(
            "dev2",
            exists=False,
            parents=[dev1],
            size=Size("6 GiB"),
            fmt=get_format("disklabel")
        )
        dev3 = DiskDevice(
            "dev3",
            exists=False,
            parents=[dev2],
            size=Size("6 GiB"),
            fmt=get_format("disklabel")
        )
        storage.devicetree._add_device(dev1)
        storage.devicetree._add_device(dev2)
        storage.devicetree._add_device(dev3)

        report = ValidationReport.from_structure(
            self.disk_selection_interface.ValidateSelectedDisks([])
        )

        self.assertEqual(report.is_valid(), True)

        report = ValidationReport.from_structure(
            self.disk_selection_interface.ValidateSelectedDisks(["dev1"])
        )

        self.assertEqual(report.is_valid(), False)
        self.assertEqual(report.error_messages, [
            "You selected disk dev1, which contains devices that also use "
            "unselected disks dev2, dev3. You must select or de-select "
            "these disks as a set."
        ])
        self.assertEqual(report.warning_messages, [])

        report = ValidationReport.from_structure(
            self.disk_selection_interface.ValidateSelectedDisks(["dev1", "dev2"])
        )

        self.assertEqual(report.is_valid(), False)
        self.assertEqual(report.error_messages, [
            "You selected disk dev1, which contains devices that also "
            "use unselected disk dev3. You must select or de-select "
            "these disks as a set.",
            "You selected disk dev2, which contains devices that also "
            "use unselected disk dev3. You must select or de-select "
            "these disks as a set."
        ])
        self.assertEqual(report.warning_messages, [])

        report = ValidationReport.from_structure(
            self.disk_selection_interface.ValidateSelectedDisks(["dev1", "dev2", "dev3"])
        )

        self.assertEqual(report.is_valid(), True)

    def exclusive_disks_property_test(self):
        """Test the exclusive disks property."""
        self._test_dbus_property(
            "ExclusiveDisks",
            ["sda", "sdb"]
        )

    def ignored_disks_property_test(self):
        """Test the ignored disks property."""
        self._test_dbus_property(
            "IgnoredDisks",
            ["sda", "sdb"]
        )

    def protected_disks_property_test(self):
        """Test the protected disks property."""
        self._test_dbus_property(
            "ProtectedDevices",
            ["sda", "sdb"]
        )

    def disk_images_property_test(self):
        """Test the protected disks property."""
        self._test_dbus_property(
            "DiskImages",
            {
                "image_1": "/path/1",
                "image_2": "/path/2"
             }
        )

    def get_usable_disks_test(self):
        """Test the GetUsableDisks method."""
        with self.assertRaises(UnavailableStorageError):
            self.disk_selection_interface.GetUsableDisks()

        self.disk_selection_module.on_storage_changed(create_storage())
        self.assertEqual(self.disk_selection_interface.GetUsableDisks(), [])
