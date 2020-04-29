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

from blivet.devices import BTRFSDevice, DiskDevice
from blivet.formats import get_format
from blivet.size import Size

from pyanaconda.modules.storage.devicetree import create_storage
from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_property, \
    check_task_creation, reset_boot_loader_factory

from pyanaconda.modules.storage import platform
from pyanaconda.modules.storage.bootloader import BootLoaderFactory
from pyanaconda.modules.storage.bootloader.base import BootLoader
from pyanaconda.modules.storage.bootloader.efi import EFIGRUB, MacEFIGRUB, Aarch64EFIGRUB, ArmEFIGRUB
from pyanaconda.modules.storage.bootloader.extlinux import EXTLINUX
from pyanaconda.modules.storage.bootloader.grub2 import GRUB2, IPSeriesGRUB2, PowerNVGRUB2
from pyanaconda.modules.storage.bootloader.zipl import ZIPL
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.storage.constants import BootloaderMode

from pyanaconda.modules.storage.bootloader.image import LinuxBootLoaderImage
from pyanaconda.core.constants import BOOTLOADER_SKIPPED, BOOTLOADER_LOCATION_PARTITION
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.storage.bootloader import BootloaderModule
from pyanaconda.modules.storage.bootloader.bootloader_interface import BootloaderInterface
from pyanaconda.modules.storage.bootloader.installation import ConfigureBootloaderTask, \
    InstallBootloaderTask, FixZIPLBootloaderTask, FixBTRFSBootloaderTask


class BootloaderInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the bootloader module."""

    def setUp(self):
        """Set up the module."""
        self.bootloader_module = BootloaderModule()
        self.bootloader_interface = BootloaderInterface(self.bootloader_module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            BOOTLOADER,
            self.bootloader_interface,
            *args, **kwargs
        )

    def get_default_type_test(self):
        """Test GetDefaultType."""
        self.assertEqual(self.bootloader_interface.GetDefaultType(), "DEFAULT")

    def bootloader_mode_property_test(self):
        """Test the bootloader mode property."""
        self._check_dbus_property(
            "BootloaderMode",
            BOOTLOADER_SKIPPED
        )

    def preferred_location_property_test(self):
        """Test the preferred location property."""
        self._check_dbus_property(
            "PreferredLocation",
            BOOTLOADER_LOCATION_PARTITION
        )

    def drive_property_test(self):
        """Test the drive property."""
        self._check_dbus_property(
            "Drive",
            "sda"
        )

    def drive_order_property_test(self):
        """Test the drive order property."""
        self._check_dbus_property(
            "DriveOrder",
            ["sda", "sdb"]
        )

    def keep_mbr_property_test(self):
        """Test the keep MBR property."""
        self._check_dbus_property(
            "KeepMBR",
            True
        )

    def keep_boot_order_test(self):
        """Test the keep boot order property."""
        self._check_dbus_property(
            "KeepBootOrder",
            True
        )

    def extra_arguments_property_test(self):
        """Test the extra arguments property."""
        self._check_dbus_property(
            "ExtraArguments",
            ["hdd=ide-scsi", "ide=nodma"]
        )

    def timeout_property_test(self):
        """Test the timeout property."""
        self._check_dbus_property(
            "Timeout",
            25
        )

    def secure_boot_property_test(self):
        """Test the secure boot property."""
        self._check_dbus_property(
            "ZIPLSecureBoot",
            "auto"
        )

    def password_property_test(self):
        """Test the password property."""
        self._check_dbus_property(
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
        self.bootloader_module.on_storage_changed(storage)

        storage.bootloader = GRUB2()
        self.assertEqual(self.bootloader_interface.IsEFI(), False)

        storage.bootloader = EFIGRUB()
        self.assertEqual(self.bootloader_interface.IsEFI(), True)

    def get_arguments_test(self):
        """Test GetArguments."""
        with self.assertRaises(UnavailableStorageError):
            self.bootloader_interface.GetArguments()

        storage = Mock()
        self.bootloader_module.on_storage_changed(storage)

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

        self.bootloader_module.on_storage_changed(storage)

        storage.bootloader.has_windows.return_value = False
        self.assertEqual(self.bootloader_interface.DetectWindows(), False)

        storage.bootloader.has_windows.return_value = True
        self.assertEqual(self.bootloader_interface.DetectWindows(), True)

    @patch_dbus_publish_object
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        storage = Mock()
        version = "4.17.7-200.fc28.x86_64"

        self.bootloader_module.on_storage_changed(storage)
        task_path = self.bootloader_interface.ConfigureWithTask([version])

        obj = check_task_creation(self, task_path, publisher, ConfigureBootloaderTask)

        self.assertEqual(obj.implementation._storage, storage)
        self.assertEqual(obj.implementation._versions, [version])

    @patch_dbus_publish_object
    def install_with_task_test(self, publisher):
        """Test InstallWithTask."""
        storage = Mock()

        self.bootloader_module.on_storage_changed(storage)
        task_path = self.bootloader_interface.InstallWithTask()

        obj = check_task_creation(self, task_path, publisher, InstallBootloaderTask)

        self.assertEqual(obj.implementation._storage, storage)

    @patch_dbus_publish_object
    def fix_btrfs_with_task_test(self, publisher):
        """Test FixBTRFSWithTask."""
        storage = Mock()
        version = "4.17.7-200.fc28.x86_64"

        self.bootloader_module.on_storage_changed(storage)
        task_path = self.bootloader_interface.FixBTRFSWithTask([version])

        obj = check_task_creation(self, task_path, publisher, FixBTRFSBootloaderTask)
        self.assertEqual(obj.implementation._storage, storage)
        self.assertEqual(obj.implementation._versions, [version])

    @patch_dbus_publish_object
    def fix_zipl_with_task_test(self, publisher):
        """Test FixZIPLWithTask."""
        storage = Mock()

        self.bootloader_module.on_storage_changed(storage)
        task_path = self.bootloader_interface.FixZIPLWithTask()

        obj = check_task_creation(self, task_path, publisher, FixZIPLBootloaderTask)
        self.assertEqual(obj.implementation._mode, self.bootloader_module.bootloader_mode)


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

        InstallBootloaderTask(storage, BootloaderMode.DISABLED).run()
        bootloader.write.assert_not_called()

        InstallBootloaderTask(storage, BootloaderMode.SKIPPED).run()
        bootloader.write.assert_not_called()

        InstallBootloaderTask(storage, BootloaderMode.ENABLED).run()
        bootloader.set_boot_args.assert_called_once()
        bootloader.write.assert_called_once()

    @patch('pyanaconda.modules.storage.bootloader.installation.conf')
    @patch('pyanaconda.modules.storage.bootloader.installation.InstallBootloaderTask')
    @patch('pyanaconda.modules.storage.bootloader.installation.ConfigureBootloaderTask')
    def fix_btrfs_test(self, configure, install, conf):
        """Test the final configuration of the boot loader."""
        storage = create_storage()
        sysroot = "/tmp/sysroot"
        version = "4.17.7-200.fc28.x86_64"

        conf.target.is_directory = True
        FixBTRFSBootloaderTask(storage, BootloaderMode.ENABLED, [version], sysroot).run()
        configure.assert_not_called()
        install.assert_not_called()

        conf.target.is_directory = False
        FixBTRFSBootloaderTask(storage, BootloaderMode.DISABLED, [version], sysroot).run()
        configure.assert_not_called()
        install.assert_not_called()

        conf.target.is_directory = False
        FixBTRFSBootloaderTask(storage, BootloaderMode.ENABLED, [version], sysroot).run()
        configure.assert_not_called()
        install.assert_not_called()

        dev1 = DiskDevice(
            "dev1",
            fmt=get_format("disklabel"),
            size=Size("10 GiB")
        )
        storage.devicetree._add_device(dev1)

        dev2 = BTRFSDevice(
            "dev2",
            fmt=get_format("btrfs", mountpoint="/"),
            size=Size("5 GiB"),
            parents=[dev1]
        )
        storage.devicetree._add_device(dev2)

        # Make the btrfs format mountable.
        dev2.format._mount = Mock(available=True)

        conf.target.is_directory = False
        FixBTRFSBootloaderTask(storage, BootloaderMode.ENABLED, [version], sysroot).run()
        configure.assert_called_once_with(storage, BootloaderMode.ENABLED, [version], sysroot)
        install.assert_called_once_with(storage, BootloaderMode.ENABLED)

    @patch('pyanaconda.modules.storage.bootloader.installation.conf')
    @patch("pyanaconda.modules.storage.bootloader.installation.arch.is_s390")
    @patch("pyanaconda.modules.storage.bootloader.installation.execInSysroot")
    def fix_zipl_test(self, execute, is_s390, conf):
        """Test the installation task for the ZIPL fix."""
        is_s390.return_value = False
        conf.target.is_directory = False
        FixZIPLBootloaderTask(BootloaderMode.ENABLED).run()
        execute.assert_not_called()

        is_s390.return_value = True
        conf.target.is_directory = True
        FixZIPLBootloaderTask(BootloaderMode.ENABLED).run()
        execute.assert_not_called()

        is_s390.return_value = True
        conf.target.is_directory = False
        FixZIPLBootloaderTask(BootloaderMode.DISABLED).run()
        execute.assert_not_called()

        is_s390.return_value = True
        conf.target.is_directory = False
        FixZIPLBootloaderTask(BootloaderMode.ENABLED).run()
        execute.assert_called_once_with("zipl", [])


class BootLoaderFactoryTestCase(unittest.TestCase):
    """Test the boot loader factory."""

    def create_boot_loader_test(self):
        """Test create_boot_loader."""
        boot_loader = BootLoaderFactory.create_boot_loader()
        self.assertIsNotNone(boot_loader)
        self.assertIsInstance(boot_loader, BootLoader)

    def get_generic_class_test(self):
        """Test get_generic_class."""
        cls = BootLoaderFactory.get_generic_class()
        self.assertEqual(cls, BootLoader)

    @reset_boot_loader_factory()
    def get_default_class_test(self):
        """Test get_default_class."""
        cls = BootLoaderFactory.get_default_class()
        self.assertEqual(cls, None)

        BootLoaderFactory.set_default_class(EXTLINUX)
        cls = BootLoaderFactory.get_default_class()
        self.assertEqual(cls, EXTLINUX)

    def get_class_by_name_test(self):
        """Test get_class_by_name."""
        cls = BootLoaderFactory.get_class_by_name("EXTLINUX")
        self.assertEqual(cls, EXTLINUX)

        cls = BootLoaderFactory.get_class_by_name("DEFAULT")
        self.assertEqual(cls, None)

    def get_class_by_platform_test(self):
        """Test get_class_by_platform."""
        # Test unknown platform.
        cls = BootLoaderFactory.get_class_by_platform(Mock())
        self.assertEqual(cls, None)

        # Test known platforms.
        boot_loader_by_platform = {
            platform.X86: GRUB2,
            platform.EFI: EFIGRUB,
            platform.MacEFI: MacEFIGRUB,
            platform.PPC: GRUB2,
            platform.IPSeriesPPC: IPSeriesGRUB2,
            platform.PowerNV: PowerNVGRUB2,
            platform.S390: ZIPL,
            platform.Aarch64EFI: Aarch64EFIGRUB,
            platform.ARM: EXTLINUX,
            platform.ArmEFI: ArmEFIGRUB
        }

        for platform_type, boot_loader_class in boot_loader_by_platform.items():
            # Get the boot loader class.
            cls = BootLoaderFactory.get_class_by_platform(platform_type)
            self.assertEqual(cls, boot_loader_class)

            # Get the boot loader instance.
            obj = cls()
            self.assertIsInstance(obj, BootLoader)
