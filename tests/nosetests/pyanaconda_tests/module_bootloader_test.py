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

from pyanaconda.core.constants import BOOTLOADER_SKIPPED, BOOTLOADER_TYPE_EXTLINUX, \
    BOOTLOADER_LOCATION_PARTITION
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.storage.bootloader import BootloaderModule
from pyanaconda.modules.storage.bootloader.bootloader_interface import BootloaderInterface
from tests.nosetests.pyanaconda_tests import check_dbus_property


class BootloaderInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the bootloader module."""

    def setUp(self):
        """Set up the module."""
        self.bootloader_module = BootloaderModule()
        self.bootloader_interface = BootloaderInterface(self.bootloader_module)

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            BOOTLOADER,
            self.bootloader_interface,
            *args, **kwargs
        )

    def bootloader_mode_property_test(self):
        """Test the bootloader mode property."""
        self._test_dbus_property(
            "BootloaderMode",
            BOOTLOADER_SKIPPED
        )

    def bootloader_type_property_test(self):
        """Test the bootloader type property."""
        self._test_dbus_property(
            "BootloaderType",
            BOOTLOADER_TYPE_EXTLINUX
        )

    def preferred_location_property_test(self):
        """Test the preferred location property."""
        self._test_dbus_property(
            "PreferredLocation",
            BOOTLOADER_LOCATION_PARTITION
        )

    def drive_property_test(self):
        """Test the drive property."""
        self._test_dbus_property(
            "Drive",
            "sda"
        )

    def drive_order_property_test(self):
        """Test the drive order property."""
        self._test_dbus_property(
            "DriveOrder",
            ["sda", "sdb"]
        )

    def keep_mbr_property_test(self):
        """Test the keep MBR property."""
        self._test_dbus_property(
            "KeepMBR",
            True
        )

    def keep_boot_order_test(self):
        """Test the keep boot order property."""
        self._test_dbus_property(
            "KeepBootOrder",
            True
        )

    def extra_arguments_property_test(self):
        """Test the extra arguments property."""
        self._test_dbus_property(
            "ExtraArguments",
            ["hdd=ide-scsi", "ide=nodma"]
        )

    def timeout_property_test(self):
        """Test the timeout property."""
        self._test_dbus_property(
            "Timeout",
            25
        )

    def password_property_test(self):
        """Test the password property."""
        self._test_dbus_property(
            "Password",
            "12345",
            setter=self.bootloader_interface.SetEncryptedPassword,
            changed={'IsPasswordSet': True}
        )
