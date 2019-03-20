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
import tempfile
import unittest
from unittest.mock import Mock, patch

from pyanaconda.bootloader import EFIGRUB, GRUB2
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.storage.constants import BootloaderMode

from pyanaconda.bootloader.image import LinuxBootLoaderImage
from pyanaconda.core.constants import BOOTLOADER_SKIPPED, BOOTLOADER_TYPE_EXTLINUX, \
    BOOTLOADER_LOCATION_PARTITION
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.storage.bootloader import BootloaderModule
from pyanaconda.modules.storage.bootloader.bootloader_interface import BootloaderInterface
from pyanaconda.modules.storage.bootloader.installation import ConfigureBootloaderTask, \
    InstallBootloaderTask
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

    def is_efi_test(self):
        """Test IsEFI."""
        with self.assertRaises(UnavailableStorageError):
            self.bootloader_interface.IsEFI()

        storage = Mock()
        self.bootloader_module.on_storage_reset(storage)

        storage.bootloader = GRUB2()
        self.assertEqual(self.bootloader_interface.IsEFI(), False)

        storage.bootloader = EFIGRUB()
        self.assertEqual(self.bootloader_interface.IsEFI(), True)

    def get_arguments_test(self):
        """Test GetArguments."""
        with self.assertRaises(UnavailableStorageError):
            self.bootloader_interface.GetArguments()

        storage = Mock()
        self.bootloader_module.on_storage_reset(storage)

        storage.bootloader = GRUB2()
        storage.bootloader.boot_args.update(["x=1", "y=2"])
        self.assertEqual(self.bootloader_interface.GetArguments(), ["x=1", "y=2"])

    def detect_windows_test(self):
        """Test DetectWindows."""
        with self.assertRaises(UnavailableStorageError):
            self.bootloader_interface.DetectWindows()

        device = Mock()
        device.format.name = "ntfs"

        storage = Mock()
        storage.devices = [device]

        self.bootloader_module.on_storage_reset(storage)

        storage.bootloader.has_windows.return_value = False
        self.assertEqual(self.bootloader_interface.DetectWindows(), False)

        storage.bootloader.has_windows.return_value = True
        self.assertEqual(self.bootloader_interface.DetectWindows(), True)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        storage = Mock()
        sysroot = "/mnt/sysroot"
        version = "4.17.7-200.fc28.x86_64"

        self.bootloader_module.on_storage_reset(storage)
        task_path = self.bootloader_interface.ConfigureWithTask(sysroot, [version])

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, ConfigureBootloaderTask)
        self.assertEqual(obj.implementation._storage, storage)
        self.assertEqual(obj.implementation._sysroot, sysroot)
        self.assertEqual(obj.implementation._versions, [version])

    @patch('pyanaconda.dbus.DBus.publish_object')
    def install_with_task_test(self, publisher):
        """Test InstallWithTask."""
        storage = Mock()
        sysroot = "/mnt/sysroot"

        self.bootloader_module.on_storage_reset(storage)
        task_path = self.bootloader_interface.InstallWithTask(sysroot)

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, InstallBootloaderTask)
        self.assertEqual(obj.implementation._storage, storage)
        self.assertEqual(obj.implementation._sysroot, sysroot)


class BootloaderTasksTestCase(unittest.TestCase):
    """Test tasks for the boot loader."""

    def configure_test(self):
        """Test the final configuration of the boot loader."""
        bootloader = Mock()
        storage = Mock(bootloader=bootloader)

        version = "4.17.7-200.fc28.x86_64"

        with tempfile.TemporaryDirectory() as root:
            ConfigureBootloaderTask(storage, BootloaderMode.DISABLED, [version], root).run()

        bootloader.add_image.assert_not_called()

        with tempfile.TemporaryDirectory() as root:
            ConfigureBootloaderTask(storage, BootloaderMode.ENABLED, [version], root).run()

        bootloader.add_image.assert_called_once()
        image = bootloader.add_image.call_args[0][0]

        self.assertIsInstance(image, LinuxBootLoaderImage)
        self.assertEqual(image, bootloader.default)
        self.assertEqual(image.version, version)
        self.assertEqual(image.label, "anaconda")
        self.assertEqual(image.short_label, "linux")
        self.assertEqual(image.device, storage.root_device)

    def install_test(self):
        """Test the installation task for the boot loader."""
        bootloader = Mock()
        storage = Mock(bootloader=bootloader)

        with tempfile.TemporaryDirectory() as root:
            InstallBootloaderTask(storage, BootloaderMode.DISABLED, root).run()

        bootloader.write.assert_not_called()

        with tempfile.TemporaryDirectory() as root:
            InstallBootloaderTask(storage, BootloaderMode.SKIPPED, root).run()

        bootloader.write.assert_not_called()

        with tempfile.TemporaryDirectory() as root:
            InstallBootloaderTask(storage, BootloaderMode.ENABLED, root).run()

        bootloader.set_boot_args.assert_called_once()
        bootloader.write.assert_called_once()
