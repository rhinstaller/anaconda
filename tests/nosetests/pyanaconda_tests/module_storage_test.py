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
from mock import patch

from pyanaconda.core.constants import CLEAR_PARTITIONS_LINUX, BOOTLOADER_SKIPPED, \
    BOOTLOADER_TYPE_EXTLINUX, BOOTLOADER_LOCATION_PARTITION
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION, \
    DISK_SELECTION, BOOTLOADER
from pyanaconda.modules.storage.bootloader import BootloaderModule
from pyanaconda.modules.storage.bootloader.bootloader_interface import BootloaderInterface
from pyanaconda.modules.storage.disk_initialization import DiskInitializationModule
from pyanaconda.modules.storage.disk_initialization.initialization_interface import \
    DiskInitializationInterface
from pyanaconda.modules.storage.disk_selection import DiskSelectionModule
from pyanaconda.modules.storage.disk_selection.selection_interface import DiskSelectionInterface
from pyanaconda.modules.storage.storage import StorageModule
from pyanaconda.modules.storage.storage_interface import StorageInterface
from tests.nosetests.pyanaconda_tests import check_kickstart_interface, check_dbus_property


class StorageInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the storage module."""

    def setUp(self):
        """Set up the module."""
        self.storage_module = StorageModule()
        self.storage_interface = StorageInterface(self.storage_module)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.storage_interface.KickstartCommands,
                         ["bootloader", "clearpart", "ignoredisk", "zerombr"])

        self.assertEqual(self.storage_interface.KickstartSections, [])
        self.assertEqual(self.storage_interface.KickstartAddons, [])

    def _test_kickstart(self, ks_in, ks_out, **kwargs):
        check_kickstart_interface(self, self.storage_interface, ks_in, ks_out, **kwargs)

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

    @patch("pyanaconda.modules.storage.kickstart.device_matches")
    def clearpart_list_kickstart_test(self, device_matches):
        """Test the clearpart command with the list option."""
        ks_in = """
        clearpart --list=sdb1
        """
        ks_out = """
        # Partition clearing information
        clearpart --list=sdb1
        """
        device_matches.return_value = ["sdb1"]
        self._test_kickstart(ks_in, ks_out)

        device_matches.return_value = []
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch("pyanaconda.modules.storage.kickstart.device_matches")
    def clearpart_drives_kickstart_test(self, device_matches):
        """Test the clearpart command with the drives option."""
        ks_in = """
        clearpart --all --drives=sda
        """
        ks_out = """
        # Partition clearing information
        clearpart --all --drives=sda
        """
        device_matches.return_value = ["sda"]
        self._test_kickstart(ks_in, ks_out)

        device_matches.return_value = []
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch("pyanaconda.modules.storage.kickstart.device_matches")
    def ignoredisk_drives_kickstart_test(self, device_matches):
        """Test the ignoredisk command with the onlyuse option."""
        ks_in = """
        ignoredisk --only-use=sda
        """
        ks_out = """
        ignoredisk --only-use=sda
        """
        device_matches.return_value = ["sda"]
        self._test_kickstart(ks_in, ks_out)

        device_matches.return_value = []
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch("pyanaconda.modules.storage.kickstart.device_matches")
    def ignoredisk_onlyuse_kickstart_test(self, device_matches):
        """Test the ignoredisk command with the drives option."""
        ks_in = """
        ignoredisk --drives=sdb
        """
        ks_out = """
        ignoredisk --drives=sdb
        """
        device_matches.return_value = ["sdb"]
        self._test_kickstart(ks_in, ks_out)

        device_matches.return_value = []
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    def bootloader_disabled_kickstart_test(self):
        """Test the bootloader command with the disabled option."""
        ks_in = """
        bootloader --disabled
        """
        ks_out = """
        # System bootloader configuration
        bootloader --disabled
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_none_kickstart_test(self):
        """Test the bootloader command with the none option."""
        ks_in = """
        bootloader --location=none
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=none
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_mbr_kickstart_test(self):
        """Test the bootloader command with the MBR option."""
        ks_in = """
        bootloader --location=mbr
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_partition_kickstart_test(self):
        """Test the bootloader command with the partition option."""
        ks_in = """
        bootloader --location=partition
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=partition
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_append_kickstart_test(self):
        """Test the bootloader command with the append option."""
        ks_in = """
        bootloader --append="hdd=ide-scsi ide=nodma"
        """
        ks_out = """
        # System bootloader configuration
        bootloader --append="hdd=ide-scsi ide=nodma" --location=mbr
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_password_kickstart_test(self):
        """Test the bootloader command with the password option."""
        ks_in = """
        bootloader --password="12345"
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --password="12345"
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_encrypted_password_kickstart_test(self):
        """Test the bootloader command with the encrypted password option."""
        ks_in = """
        bootloader --password="12345" --iscrypted
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --password="12345" --iscrypted
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_driveorder_kickstart_test(self):
        """Test the bootloader command with the driveorder option."""
        ks_in = """
        bootloader --driveorder="sda,sdb"
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --driveorder="sda,sdb"
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_timeout_kickstart_test(self):
        """Test the bootloader command with the timeout option."""
        ks_in = """
        bootloader --timeout=10
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --timeout=10
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_md5pass_kickstart_test(self):
        """Test the bootloader command with the md5pass option."""
        ks_in = """
        bootloader --md5pass="12345"
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --password="12345" --iscrypted
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_bootdrive_kickstart_test(self):
        """Test the bootloader command with the boot drive option."""
        ks_in = """
        bootloader --boot-drive="sda"
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --boot-drive=sda
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_leavebootorder_kickstart_test(self):
        """Test the bootloader command with the leavebootorder option."""
        ks_in = """
        bootloader --leavebootorder
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --leavebootorder
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_extlinux_kickstart_test(self):
        """Test the bootloader command with the extlinux option."""
        ks_in = """
        bootloader --extlinux
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --extlinux
        """
        self._test_kickstart(ks_in, ks_out)

    def bootloader_nombr_kickstart_test(self):
        """Test the bootloader command with the nombr option."""
        ks_in = """
        bootloader --nombr
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --nombr
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
