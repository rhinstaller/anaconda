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
import logging
import os
import tempfile
import unittest
from unittest.mock import Mock, PropertyMock, patch

import pytest
from blivet.formats.fs import BTRFS
from dasbus.server.container import DBusContainerError
from dasbus.typing import *  # pylint: disable=wildcard-import
from pykickstart.base import RemovedCommand
from pykickstart.errors import KickstartParseError

from pyanaconda.core.constants import (
    PARTITIONING_METHOD_AUTOMATIC,
    PARTITIONING_METHOD_CUSTOM,
    PARTITIONING_METHOD_INTERACTIVE,
    PARTITIONING_METHOD_MANUAL,
)
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.containers import PartitioningContainer
from pyanaconda.modules.common.errors.storage import InvalidStorageError
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.storage.bootloader import BootLoaderFactory
from pyanaconda.modules.storage.bootloader.extlinux import EXTLINUX
from pyanaconda.modules.storage.bootloader.grub2 import GRUB2, IPSeriesGRUB2
from pyanaconda.modules.storage.bootloader.zipl import ZIPL
from pyanaconda.modules.storage.checker.utils import StorageCheckerReport
from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.modules.storage.initialization import enable_installer_mode
from pyanaconda.modules.storage.installation import (
    CreateStorageLayoutTask,
    MountFilesystemsTask,
    WriteConfigurationTask,
)
from pyanaconda.modules.storage.kickstart import (
    StorageKickstartSpecification,
    fips_check_luks_passphrase,
)
from pyanaconda.modules.storage.partitioning.automatic.automatic_module import (
    AutoPartitioningModule,
)
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod
from pyanaconda.modules.storage.partitioning.interactive.interactive_module import (
    InteractivePartitioningModule,
)
from pyanaconda.modules.storage.partitioning.manual.manual_module import (
    ManualPartitioningModule,
)
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.modules.storage.platform import S390
from pyanaconda.modules.storage.reset import ScanDevicesTask
from pyanaconda.modules.storage.storage import StorageService
from pyanaconda.modules.storage.storage_interface import StorageInterface
from pyanaconda.modules.storage.teardown import (
    TeardownDiskImagesTask,
    UnmountFilesystemsTask,
)
from tests.unit_tests.pyanaconda_tests import (
    check_dbus_property,
    check_kickstart_interface,
    check_task_creation,
    patch_dbus_get_proxy,
    patch_dbus_publish_object,
    reset_boot_loader_factory,
    reset_dbus_container,
)


class StorageInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the storage module."""

    def setUp(self):
        """Set up the module."""
        self.maxDiff = None
        self.storage_module = StorageService()
        self.storage_interface = StorageInterface(self.storage_module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            STORAGE,
            self.storage_interface,
            *args, **kwargs
        )

    def _check_dbus_partitioning(self, publisher, expected_method):
        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        partitioning_modules = self.storage_module.created_partitioning
        assert len(partitioning_modules) == 1, "Too many partitioning modules."

        partitioning_module = partitioning_modules[-1]
        assert partitioning_module.partitioning_method == expected_method

        partitioning_path = self.storage_interface.CreatedPartitioning[-1]
        assert partitioning_path == object_path
        assert isinstance(obj.implementation, PartitioningModule)
        assert partitioning_module == obj.implementation

    def _apply_partitioning_when_created(self):
        """Apply each partitioning emitted by created_partitioning_changed.

        This helps with testing of parsing and generating kickstart with
        check_kickstart_interface, because the partitioning created from
        the kickstart data will be used to generate a new kickstart data.
        """
        self.storage_module.created_partitioning_changed.connect(
            self.storage_module._set_applied_partitioning
        )

    def test_initialization(self):
        """Test the Blivet initialization."""
        enable_installer_mode()

    def test_create_storage(self):
        """Test the storage created by default."""
        storage_changed_callback = Mock()
        self.storage_module.storage_changed.connect(storage_changed_callback)

        storage_reset_callback = Mock()
        self.storage_module.partitioning_reset.connect(storage_reset_callback)

        assert self.storage_module.storage is not None
        storage_changed_callback.assert_not_called()
        storage_reset_callback.assert_not_called()

        self.storage_module._current_storage = None
        assert self.storage_module.storage is not None
        storage_changed_callback.assert_called_once()
        storage_reset_callback.assert_not_called()

    @patch_dbus_publish_object
    def test_scan_devices_with_task(self, publisher):
        """Test ScanDevicesWithTask."""
        task_path = self.storage_interface.ScanDevicesWithTask()

        obj = check_task_creation(task_path, publisher, ScanDevicesTask)

        assert obj.implementation._storage is not None

        # Check the side affects.
        storage_changed_callback = Mock()
        self.storage_module.storage_changed.connect(storage_changed_callback)

        partitioning_reset_callback = Mock()
        self.storage_module.partitioning_reset.connect(partitioning_reset_callback)

        obj.implementation.succeeded_signal.emit()
        storage_changed_callback.assert_called_once()
        partitioning_reset_callback.assert_not_called()

    @patch_dbus_publish_object
    def test_create_partitioning(self, published):
        """Test CreatePartitioning."""
        reset_dbus_container(PartitioningContainer)

        path = self.storage_interface.CreatePartitioning(PARTITIONING_METHOD_AUTOMATIC)
        assert path == "/org/fedoraproject/Anaconda/Modules/Storage/Partitioning/1"

        published.assert_called_once()
        published.reset_mock()

        obj = PartitioningContainer.from_object_path(path)
        assert isinstance(obj, AutoPartitioningModule)

        path = self.storage_interface.CreatePartitioning(PARTITIONING_METHOD_MANUAL)
        assert path == "/org/fedoraproject/Anaconda/Modules/Storage/Partitioning/2"

        published.assert_called_once()
        published.reset_mock()

        obj = PartitioningContainer.from_object_path(path)
        assert isinstance(obj, ManualPartitioningModule)

        path = self.storage_interface.CreatePartitioning(PARTITIONING_METHOD_INTERACTIVE)
        assert path == "/org/fedoraproject/Anaconda/Modules/Storage/Partitioning/3"

        published.assert_called_once()

        obj = PartitioningContainer.from_object_path(path)
        assert isinstance(obj, InteractivePartitioningModule)

    @patch_dbus_publish_object
    def test_created_partitioning(self, publisher):
        """Test the property CreatedPartitioning."""
        reset_dbus_container(PartitioningContainer)

        self._check_dbus_property(
            "CreatedPartitioning",
            in_value=PARTITIONING_METHOD_MANUAL,
            out_value=["/org/fedoraproject/Anaconda/Modules/Storage/Partitioning/1"],
            setter=self.storage_interface.CreatePartitioning
        )

        self._check_dbus_property(
            "CreatedPartitioning",
            in_value=PARTITIONING_METHOD_CUSTOM,
            out_value=["/org/fedoraproject/Anaconda/Modules/Storage/Partitioning/1",
                       "/org/fedoraproject/Anaconda/Modules/Storage/Partitioning/2"],
            setter=self.storage_interface.CreatePartitioning
        )

    @patch_dbus_publish_object
    @patch('pyanaconda.modules.storage.partitioning.validate.storage_checker')
    def test_apply_partitioning(self, storage_checker, published):
        """Test ApplyPartitioning."""
        storage_1 = Mock()
        storage_2 = storage_1.copy.return_value
        storage_3 = storage_2.copy.return_value

        report = StorageCheckerReport()
        storage_checker.check.return_value = report

        self.storage_module._set_storage(storage_1)
        assert self.storage_module.storage == storage_1

        object_path = self.storage_interface.CreatePartitioning(PARTITIONING_METHOD_AUTOMATIC)
        partitioning = self.storage_module.created_partitioning[-1]
        assert partitioning.storage == storage_2

        self.storage_interface.ApplyPartitioning(object_path)
        assert self.storage_module.storage == storage_3

        with pytest.raises(DBusContainerError):
            self.storage_interface.ApplyPartitioning(ObjPath("invalid"))

        report.add_warning("The partitioning might not be valid.")
        self.storage_interface.ApplyPartitioning(object_path)

        report.add_error("The partitioning is not valid.")
        with pytest.raises(InvalidStorageError):
            self.storage_interface.ApplyPartitioning(object_path)

    @patch_dbus_publish_object
    @patch('pyanaconda.modules.storage.partitioning.validate.storage_checker')
    def test_applied_partitioning(self, storage_checker, publisher):
        """Test the property AppliedPartitioning."""
        storage = Mock()

        report = StorageCheckerReport()
        storage_checker.check.return_value = report

        self.storage_module._set_storage(storage)
        assert self.storage_interface.AppliedPartitioning == ""

        self._check_dbus_property(
            "AppliedPartitioning",
            in_value=self.storage_interface.CreatePartitioning(PARTITIONING_METHOD_MANUAL),
            setter=self.storage_interface.ApplyPartitioning
        )

    @patch_dbus_publish_object
    @patch('pyanaconda.modules.storage.partitioning.validate.storage_checker')
    def test_reset_partitioning(self, storage_checker, published):
        """Test ResetPartitioning."""
        storage_1 = Mock()
        storage_2 = storage_1.copy.return_value
        storage_3 = storage_2.copy.return_value

        report = StorageCheckerReport()
        storage_checker.check.return_value = report

        self.storage_module._set_storage(storage_1)
        assert self.storage_module.storage == storage_1

        partitioning = self.storage_interface.CreatePartitioning(
            PARTITIONING_METHOD_AUTOMATIC
        )
        partitioning_module = self.storage_module.created_partitioning[-1]
        assert partitioning_module.storage == storage_2

        self.storage_interface.ApplyPartitioning(partitioning)
        assert self.storage_interface.AppliedPartitioning == partitioning
        assert self.storage_module.storage == storage_3

        storage_4 = Mock()
        storage_1.copy.return_value = storage_4

        self.storage_interface.ResetPartitioning()
        assert self.storage_interface.AppliedPartitioning == ""
        assert self.storage_module.storage == storage_1
        assert partitioning_module.storage == storage_4

    @patch("pyanaconda.modules.storage.storage.platform", S390())
    def test_collect_requirements(self):
        """Test CollectRequirements."""
        storage = Mock()
        storage.bootloader = GRUB2()
        storage.packages = ["lvm2"]

        self.storage_module._set_storage(storage)
        assert self.storage_interface.CollectRequirements() == [
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "lvm2"),
                "reason": get_variant(Str, "Required to manage storage devices.")
            },
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "grub2"),
                "reason": get_variant(Str, "Necessary for the bootloader configuration.")
            },
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "grub2-tools"),
                "reason": get_variant(Str, "Necessary for the bootloader configuration.")
            }
        ]

    @patch_dbus_publish_object
    def test_install_with_tasks(self, publisher):
        """Test InstallWithTask."""
        task_classes = [
            CreateStorageLayoutTask,
            MountFilesystemsTask
        ]

        task_paths = self.storage_interface.InstallWithTasks()

        # Check the number of installation tasks.
        task_number = len(task_classes)
        assert task_number == len(task_paths)
        assert task_number == publisher.call_count

        # Check the tasks.
        for i in range(task_number):
            object_path, obj = publisher.call_args_list[i][0]
            assert object_path == task_paths[i]
            assert isinstance(obj, TaskInterface)
            assert isinstance(obj.implementation, task_classes[i])

    @patch_dbus_publish_object
    def test_write_configuration_with_task(self, publisher):
        """Test WriteConfigurationWithTask."""
        task_path = self.storage_interface.WriteConfigurationWithTask()
        check_task_creation(task_path, publisher, WriteConfigurationTask)

    @patch_dbus_publish_object
    def test_teardown_with_tasks(self, publisher):
        """Test TeardownWithTask."""
        task_classes = [
            UnmountFilesystemsTask,
            TeardownDiskImagesTask
        ]

        # Get the teardown tasks.
        task_paths = self.storage_interface.TeardownWithTasks()

        # Check the number of teardown tasks.
        task_number = len(task_classes)
        assert task_number == len(task_paths)
        assert task_number == publisher.call_count

        # Check the tasks.
        for i in range(task_number):
            object_path, obj = publisher.call_args_list[i][0]
            assert object_path == task_paths[i]
            assert isinstance(obj, TaskInterface)
            assert isinstance(obj.implementation, task_classes[i])

    def test_kickstart_properties(self):
        """Test kickstart properties."""
        assert self.storage_interface.KickstartCommands == \
            [
                'autopart',
                'bootloader',
                'btrfs',
                'clearpart',
                'fcoe',
                'ignoredisk',
                'iscsi',
                'iscsiname',
                'logvol',
                'mount',
                'nvdimm',
                'part',
                'partition',
                'raid',
                'reqpart',
                'snapshot',
                'volgroup',
                'zerombr',
                'zfcp',
                'zipl',
            ]
        assert self.storage_interface.KickstartSections == []
        assert self.storage_interface.KickstartAddons == []

    def _test_kickstart(self, ks_in, ks_out, **kwargs):
        check_kickstart_interface(self.storage_interface, ks_in, ks_out, **kwargs)

    def test_no_kickstart(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_empty(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def test_zerombr_kickstart(self):
        """Test the zerombr command."""
        ks_in = """
        zerombr
        """
        ks_out = """
        # Clear the Master Boot Record
        zerombr
        """
        self._test_kickstart(ks_in, ks_out)

    def test_clearpart_none_kickstart(self):
        """Test the clearpart command with the none option."""
        ks_in = """
        clearpart --none
        """
        ks_out = """
        # Partition clearing information
        clearpart --none
        """
        self._test_kickstart(ks_in, ks_out)

    def test_clearpart_all_kickstart(self):
        """Test the clearpart command with the all option."""
        ks_in = """
        clearpart --all
        """
        ks_out = """
        # Partition clearing information
        clearpart --all
        """
        self._test_kickstart(ks_in, ks_out)

    def test_clearpart_linux_kickstart(self):
        """Test the clearpart command with the linux option."""
        ks_in = """
        clearpart --linux
        """
        ks_out = """
        # Partition clearing information
        clearpart --linux
        """
        self._test_kickstart(ks_in, ks_out)

    def test_clearpart_cdl_kickstart(self):
        """Test the clearpart command with the cdl option."""
        ks_in = """
        clearpart --all --cdl
        """
        ks_out = """
        # Partition clearing information
        clearpart --all --cdl
        """
        self._test_kickstart(ks_in, ks_out)

    def test_clearpart_initlabel_kickstart(self):
        """Test the clearpart command with the initlabel option."""
        ks_in = """
        clearpart --all --initlabel
        """
        ks_out = """
        # Partition clearing information
        clearpart --all --initlabel
        """
        self._test_kickstart(ks_in, ks_out)

    @patch("pyanaconda.modules.storage.kickstart.DiskLabel")
    def test_clearpart_disklabel_kickstart(self, disk_label):
        """Test the clearpart command with the disklabel option."""
        ks_in = """
        clearpart --all --disklabel=msdos
        """
        ks_out = """
        # Partition clearing information
        clearpart --all --disklabel=msdos
        """
        disk_label.get_platform_label_types.return_value = ["msdos", "gpt"]
        self._test_kickstart(ks_in, ks_out)

        disk_label.get_platform_label_types.return_value = ["gpt"]
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch("pyanaconda.modules.storage.kickstart.device_matches")
    def test_clearpart_list_kickstart(self, device_matches):
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
    def test_clearpart_drives_kickstart(self, device_matches):
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
    def test_ignoredisk_drives_kickstart(self, device_matches):
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
    def test_ignoredisk_onlyuse_kickstart(self, device_matches):
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

    def test_bootloader_disabled_kickstart(self):
        """Test the bootloader command with the disabled option."""
        ks_in = """
        bootloader --disabled
        """
        ks_out = """
        # System bootloader configuration
        bootloader --disabled
        """
        self._test_kickstart(ks_in, ks_out)

    def test_bootloader_none_kickstart(self):
        """Test the bootloader command with the none option."""
        ks_in = """
        bootloader --location=none
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=none
        """
        self._test_kickstart(ks_in, ks_out)

    def test_bootloader_mbr_kickstart(self):
        """Test the bootloader command with the MBR option."""
        ks_in = """
        bootloader --location=mbr
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr
        """
        self._test_kickstart(ks_in, ks_out)

    @reset_boot_loader_factory()
    def test_bootloader_partition_kickstart(self):
        """Test the bootloader command with the partition option."""
        ks_in = """
        bootloader --location=partition
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=partition
        """
        BootLoaderFactory.set_default_class(ZIPL)
        self._test_kickstart(ks_in, ks_out)

        BootLoaderFactory.set_default_class(IPSeriesGRUB2)
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    def test_bootloader_append_kickstart(self):
        """Test the bootloader command with the append option."""
        ks_in = """
        bootloader --append="hdd=ide-scsi ide=nodma"
        """
        ks_out = """
        # System bootloader configuration
        bootloader --append="hdd=ide-scsi ide=nodma" --location=mbr
        """
        self._test_kickstart(ks_in, ks_out)

    def test_bootloader_password_kickstart(self):
        """Test the bootloader command with the password option."""
        ks_in = """
        bootloader --password="12345"
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --password="12345"
        """
        self._test_kickstart(ks_in, ks_out)

    @reset_boot_loader_factory()
    def test_bootloader_encrypted_password_kickstart(self):
        """Test the bootloader command with the encrypted password option."""
        ks_in = """
        bootloader --password="12345" --iscrypted
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --password="12345" --iscrypted
        """
        BootLoaderFactory.set_default_class(ZIPL)
        self._test_kickstart(ks_in, ks_out)

        BootLoaderFactory.set_default_class(GRUB2)
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @reset_boot_loader_factory()
    def test_bootloader_encrypted_grub2_kickstart(self):
        """Test the bootloader command with encrypted GRUB2."""
        ks_in = """
        bootloader --password="grub.pbkdf2.12345" --iscrypted
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --password="grub.pbkdf2.12345" --iscrypted
        """
        BootLoaderFactory.set_default_class(GRUB2)
        self._test_kickstart(ks_in, ks_out)

    def test_bootloader_driveorder_kickstart(self):
        """Test the bootloader command with the driveorder option."""
        ks_in = """
        bootloader --driveorder="sda,sdb"
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --driveorder="sda,sdb"
        """
        self._test_kickstart(ks_in, ks_out)

    def test_bootloader_timeout_kickstart(self):
        """Test the bootloader command with the timeout option."""
        ks_in = """
        bootloader --timeout=10
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --timeout=10
        """
        self._test_kickstart(ks_in, ks_out)

    @reset_boot_loader_factory()
    def test_bootloader_md5pass_kickstart(self):
        """Test the bootloader command with the md5pass option."""
        ks_in = """
        bootloader --md5pass="12345" --extlinux
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --password="12345" --iscrypted --extlinux
        """
        self._test_kickstart(ks_in, ks_out)

    def test_bootloader_bootdrive_kickstart(self):
        """Test the bootloader command with the boot drive option."""
        ks_in = """
        bootloader --boot-drive="sda"
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --boot-drive=sda
        """
        self._test_kickstart(ks_in, ks_out)

    def test_bootloader_leavebootorder_kickstart(self):
        """Test the bootloader command with the leavebootorder option."""
        ks_in = """
        bootloader --leavebootorder
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --leavebootorder
        """
        self._test_kickstart(ks_in, ks_out)

    @reset_boot_loader_factory()
    def test_bootloader_extlinux_kickstart(self):
        """Test the bootloader command with the extlinux option."""
        ks_in = """
        bootloader --extlinux
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --extlinux
        """
        self._test_kickstart(ks_in, ks_out)
        assert BootLoaderFactory.get_default_class() == EXTLINUX

    def test_bootloader_nombr_kickstart(self):
        """Test the bootloader command with the nombr option."""
        ks_in = """
        bootloader --nombr
        """
        ks_out = """
        # System bootloader configuration
        bootloader --location=mbr --nombr
        """
        self._test_kickstart(ks_in, ks_out)

    def test_zipl_secure_boot_kickstart(self):
        """Test the zipl command with the secure boot option."""
        ks_in = """
        zipl --secure-boot
        """
        ks_out = """
        # ZIPL configuration
        zipl --secure-boot
        """
        self._test_kickstart(ks_in, ks_out)

    def test_zipl_disable_secure_boot_kickstart(self):
        """Test the zipl command with the disable secure boot option."""
        ks_in = """
        zipl --no-secure-boot
        """
        ks_out = """
        # ZIPL configuration
        zipl --no-secure-boot
        """
        self._test_kickstart(ks_in, ks_out)

    def test_zipl_enable_secure_boot_kickstart(self):
        """Test the zipl command with the force secure boot option."""
        ks_in = """
        zipl --force-secure-boot
        """
        ks_out = """
        # ZIPL configuration
        zipl --force-secure-boot
        """
        self._test_kickstart(ks_in, ks_out)

    @patch_dbus_publish_object
    def test_autopart_kickstart(self, publisher):
        """Test the autopart command."""
        ks_in = """
        autopart
        """
        ks_out = """
        autopart
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_type_kickstart(self, publisher):
        """Test the autopart command with the type option."""
        ks_in = """
        autopart --type=thinp
        """
        ks_out = """
        autopart --type=thinp
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_fstype_kickstart(self, publisher):
        """Test the autopart command with the fstype option."""
        ks_in = """
        autopart --fstype=ext4
        """
        ks_out = """
        autopart --fstype=ext4
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

        ks_in = """
        autopart --fstype=invalid
        """
        ks_out = ""
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch_dbus_publish_object
    def test_autopart_nopart_kickstart(self, publisher):
        """Test the autopart command with nohome, noboot and noswap options."""
        ks_in = """
        autopart --nohome --noboot --noswap
        """
        ks_out = """
        autopart --nohome --noboot --noswap
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_encrypted_kickstart(self, publisher):
        """Test the autopart command with the encrypted option."""
        ks_in = """
        autopart --encrypted
        """
        ks_out = """
        autopart --encrypted
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_cipher_kickstart(self, publisher):
        """Test the autopart command with the cipher option."""
        ks_in = """
        autopart --encrypted --cipher="aes-xts-plain64"
        """
        ks_out = """
        autopart --encrypted --cipher="aes-xts-plain64"
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_passphrase_kickstart(self, publisher):
        """Test the autopart command with the passphrase option."""
        ks_in = """
        autopart --encrypted --passphrase="123456"
        """
        ks_out = """
        autopart --encrypted
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_escrowcert_kickstart(self, publisher):
        """Test the autopart command with the escrowcert option."""
        ks_in = """
        autopart --encrypted --escrowcert="file:///tmp/escrow.crt"
        """
        ks_out = """
        autopart --encrypted --escrowcert="file:///tmp/escrow.crt"
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_backuppassphrase_kickstart(self, publisher):
        """Test the autopart command with the backuppassphrase option."""
        ks_in = """
        autopart --encrypted --escrowcert="file:///tmp/escrow.crt" --backuppassphrase
        """
        ks_out = """
        autopart --encrypted --escrowcert="file:///tmp/escrow.crt" --backuppassphrase
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_hibernation_kickstart(self, publisher):
        """Test the autopart command with the hibernation option."""
        ks_in = """
        autopart --hibernation
        """
        ks_out = """
        autopart --hibernation
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_mount_kickstart(self, publisher):
        """Test the mount command."""
        ks_in = """
        mount /dev/sda1 /boot
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 /boot
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.MANUAL)

    @patch_dbus_publish_object
    def test_mount_none_kickstart(self, publisher):
        """Test the mount command with none."""
        ks_in = """
        mount /dev/sda1 none
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 none
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.MANUAL)

    @patch_dbus_publish_object
    def test_mount_mountoptions_kickstart(self, publisher):
        """Test the mount command with the mountoptions."""
        ks_in = """
        mount /dev/sda1 /boot --mountoptions="user"
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 /boot --mountoptions="user"
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.MANUAL)

    @patch_dbus_publish_object
    def test_mount_reformat_kickstart(self, publisher):
        """Test the mount command with the reformat option."""
        ks_in = """
        mount /dev/sda1 /boot --reformat
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 /boot --reformat
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.MANUAL)

    @patch_dbus_publish_object
    def test_mount_mkfsoptions_kickstart(self, publisher):
        """Test the mount command with the mkfsoptions."""
        ks_in = """
        mount /dev/sda1 /boot --reformat=xfs --mkfsoptions="-L BOOT"
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 /boot --reformat=xfs --mkfsoptions="-L BOOT"
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.MANUAL)

    @patch_dbus_publish_object
    def test_mount_multiple_kickstart(self, publisher):
        """Test multiple mount commands."""
        ks_in = """
        mount /dev/sda1 /boot
        mount /dev/sda2 /
        mount /dev/sdb1 /home
        mount /dev/sdb2 none
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 /boot
        mount /dev/sda2 /
        mount /dev/sdb1 /home
        mount /dev/sdb2 none
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.MANUAL)

    @patch_dbus_publish_object
    def test_autopart_luks_version_kickstart(self, publisher):
        """Test the autopart command with the luks version option."""
        ks_in = """
        autopart --encrypted --luks-version=luks1
        """
        ks_out = """
        autopart --encrypted --luks-version=luks1
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_pbkdf_kickstart(self, publisher):
        """Test the autopart command with the pbkdf option."""
        ks_in = """
        autopart --encrypted --pbkdf=pbkdf2
        """
        ks_out = """
        autopart --encrypted --pbkdf=pbkdf2
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_pbkdf_memory_kickstart(self, publisher):
        """Test the autopart command with the pbkdf memory option."""
        ks_in = """
        autopart --encrypted --pbkdf-memory=256
        """
        ks_out = """
        autopart --encrypted --pbkdf-memory=256
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_pbkdf_time_kickstart(self, publisher):
        """Test the autopart command with the pbkdf time option."""
        ks_in = """
        autopart --encrypted --pbkdf-time=100
        """
        ks_out = """
        autopart --encrypted --pbkdf-time=100
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch_dbus_publish_object
    def test_autopart_pbkdf_iterations_kickstart(self, publisher):
        """Test the autopart command with the pbkdf iterations option."""
        ks_in = """
        autopart --encrypted --pbkdf-iterations=1000
        """
        ks_out = """
        autopart --encrypted --pbkdf-iterations=1000
        """
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.AUTOMATIC)

    @patch("pyanaconda.modules.storage.kickstart.fcoe")
    @patch("pyanaconda.modules.storage.kickstart.get_supported_devices")
    def test_fcoe_kickstart(self, get_supported_devices, fcoe):
        """Test the fcoe command."""
        ks_in = """
        fcoe --nic=eth0 --dcb --autovlan
        """
        ks_out = """
        fcoe --nic=eth0 --dcb --autovlan
        """
        dev_info = Mock()
        dev_info.device_name = "eth0"
        get_supported_devices.return_value = [dev_info]
        self._test_kickstart(ks_in, ks_out)

        dev_info.device_name = "eth1"
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch("pyanaconda.modules.storage.iscsi.iscsi.iscsi")
    @patch("pyanaconda.modules.storage.kickstart.iscsi")
    @patch_dbus_get_proxy
    @patch("pyanaconda.modules.storage.kickstart.wait_for_network_devices")
    def test_iscsi_kickstart(self, wait_for_network_devices, proxy_getter, iscsi, module_iscsi):
        """Test the iscsi command."""
        ks_in = """
        iscsiname iqn.1994-05.com.redhat:blabla
        iscsi --target=iqn.2014-08.com.example:t1 --ipaddr=10.43.136.51 --iface=ens3
        """
        ks_out = """
        iscsiname iqn.1994-05.com.redhat:blabla
        iscsi --target=iqn.2014-08.com.example:t1 --ipaddr=10.43.136.51 --iface=ens3
        """
        module_iscsi.initiator = "iqn.1994-05.com.redhat:blabla"
        iscsi.mode = "none"
        wait_for_network_devices.return_value = True
        self._test_kickstart(ks_in, ks_out)

    @patch("pyanaconda.modules.storage.iscsi.iscsi.iscsi")
    @patch("pyanaconda.modules.storage.kickstart.iscsi")
    @patch_dbus_get_proxy
    @patch("pyanaconda.modules.storage.kickstart.wait_for_network_devices")
    def test_iscsi_kickstart_with_ui(self, wait_for_network_devices, proxy_getter, kickstart_iscsi, iscsi):
        """Test the iscsi command taking targets attached in GUI into account."""
        wait_for_network_devices.return_value = True

        # One node from kickstart one node from GUI
        kickstart_iscsi.mode = "bind"
        ks_in = """
        iscsiname iqn.1994-05.com.redhat:blabla
        iscsi --target=iqn.2014-08.com.example:t1 --ipaddr=10.43.136.51 --iface=ens3
        """
        ks_out = """
        iscsiname iqn.1994-05.com.redhat:blabla
        iscsi --target=iqn.2014-08.com.example:t1 --ipaddr=10.43.136.51 --iface=ens3
        iscsi --target=iqn.2014-08.com.example:t2 --ipaddr=10.43.136.51 --iface=ens3
        """
        iscsi.initiator = "iqn.1994-05.com.redhat:blabla"
        self._mock_active_nodes(
            iscsi,
            ibft_nodes=[],
            nodes=[
                # Attached by kickstart
                Mock(
                    nname="iqn.2014-08.com.example:t1",
                    address="10.43.136.51",
                    port=3260,
                    iface="iface0",
                    username=None,
                    password=None,
                    r_username=None,
                    r_password=None,
                ),
                # Attached in GUI
                Mock(
                    # we can use 'name' attribute which is a reserved kwarg of Mock
                    nname="iqn.2014-08.com.example:t2",
                    address="10.43.136.51",
                    port=3260,
                    iface="iface0",
                    username=None,
                    password=None,
                    r_username=None,
                    r_password=None,
                )
            ],
            ifaces={
                "iface0": "ens3",
                "iface1": "ens7"
            }
        )
        self._test_kickstart(ks_in, ks_out)

        # Node added from ibft
        kickstart_iscsi.mode = "bind"
        ks_in = """
        """
        ks_out = """
        """
        iscsi.initiator = ""
        node_from_ibft = Mock(
            nname="iqn.2014-08.com.example:t1",
            address="10.43.136.51",
            port=3260,
            iface="iface0",
            username=None,
            password=None,
            r_username=None,
            r_password=None,
        )
        self._mock_active_nodes(
            iscsi,
            ibft_nodes=[
                node_from_ibft
            ],
            nodes=[
                node_from_ibft
            ],
            ifaces={
                "iface0": "ens3",
                "iface1": "ens7"
            }
        )
        self._test_kickstart(ks_in, ks_out)

        # One node from kickstart one node from GUI.
        # Nodes actually attached from a portal don't override generic
        # kickstart request to attach all nodes from the portal.
        kickstart_iscsi.mode = "default"
        ks_in = """
        iscsiname iqn.1994-05.com.redhat:blabla
        iscsi --ipaddr=10.43.136.51
        """
        ks_out = """
        iscsiname iqn.1994-05.com.redhat:blabla
        iscsi --ipaddr=10.43.136.51
        iscsi --target=iqn.2014-08.com.example:t3 --ipaddr=10.43.136.55
        """
        iscsi.initiator = "iqn.1994-05.com.redhat:blabla"
        self._mock_active_nodes(
            iscsi,
            ibft_nodes=[],
            nodes=[
                # Attached by kickstart
                Mock(
                    nname="iqn.2014-08.com.example:t1",
                    address="10.43.136.51",
                    port=3260,
                    iface="default",
                    username=None,
                    password=None,
                    r_username=None,
                    r_password=None,
                ),
                # Attached in GUI
                Mock(
                    # we can use 'name' attribute which is a reserved kwarg of Mock
                    nname="iqn.2014-08.com.example:t3",
                    address="10.43.136.55",
                    port=3260,
                    iface="default",
                    username=None,
                    password=None,
                    r_username=None,
                    r_password=None,
                )
            ],
            ifaces={}
        )
        self._test_kickstart(ks_in, ks_out)

        # Node attached in GUI
        # Credentials are put into generated kickstart.
        kickstart_iscsi.mode = "default"
        ks_in = """
        """
        ks_out = """
        iscsiname iqn.1994-05.com.redhat:blabla
        iscsi --target=iqn.2014-08.com.example:t3 --ipaddr=10.43.136.55 --user=uname --password=pwd --reverse-user=r_uname --reverse-password=r_pwd
        """
        iscsi.initiator = "iqn.1994-05.com.redhat:blabla"
        self._mock_active_nodes(
            iscsi,
            ibft_nodes=[],
            nodes=[
                # Attached in GUI
                Mock(
                    # we can use 'name' attribute which is a reserved kwarg of Mock
                    nname="iqn.2014-08.com.example:t3",
                    address="10.43.136.55",
                    port=3260,
                    iface="default",
                    username="uname",
                    password="pwd",
                    r_username="r_uname",
                    r_password="r_pwd",
                )
            ],
            ifaces={}
        )
        self._test_kickstart(ks_in, ks_out)

    def _mock_active_nodes(self, iscsi_mock, ibft_nodes, nodes, ifaces):
        iscsi_mock.ifaces = ifaces
        # We can't use reserved 'name' attribute when creating the node Mock instance
        # so set it here from 'nname'.
        for node in ibft_nodes:
            node.name = node.nname
        for node in nodes:
            node.name = node.nname
        iscsi_mock.active_nodes.return_value = nodes + ibft_nodes
        iscsi_mock.ibft_nodes = ibft_nodes

    @patch("pyanaconda.modules.storage.kickstart.zfcp")
    def test_zfcp_kickstart(self, zfcp):
        """Test the zfcp command."""
        ks_in = """
        zfcp --devnum=0.0.fc00 --wwpn=0x401040a000000000 --fcplun=0x5105074308c212e9
        """
        ks_out = """
        zfcp --devnum=0.0.fc00 --wwpn=0x401040a000000000 --fcplun=0x5105074308c212e9
        """
        self._test_kickstart(ks_in, ks_out)

    def test_snapshot_kickstart(self):
        """Test the snapshot command."""
        ks_in = """
        snapshot fedora/root --name=pre-snapshot --when=pre-install
        snapshot fedora/root --name=post-snapshot --when=post-install
        """
        ks_out = """
        snapshot fedora/root --name=pre-snapshot --when=pre-install
        snapshot fedora/root --name=post-snapshot --when=post-install
        """
        self._test_kickstart(ks_in, ks_out)

    def test_snapshot_invalid_kickstart(self):
        """Test the snapshot command with invalid origin."""
        ks_in = """
        snapshot invalid --name=pre-snapshot --when=pre-install
        """
        ks_out = """
        snapshot invalid --name=pre-snapshot --when=pre-install
        """
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    def test_snapshot_warning_kickstart(self):
        """Test the snapshot command with warnings."""
        ks_in = """
        zerombr
        clearpart --all
        snapshot fedora/root --name=pre-snapshot --when=pre-install
        """
        ks_out = """
        # Clear the Master Boot Record
        zerombr
        # Partition clearing information
        clearpart --all
        snapshot fedora/root --name=pre-snapshot --when=pre-install
        """
        with self.assertLogs(level=logging.WARN):
            self._test_kickstart(ks_in, ks_out)

    @patch_dbus_publish_object
    def test_reqpart_kickstart(self, publisher):
        """Test the reqpart command."""
        ks_in = """
        reqpart
        """
        ks_out = ""
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.CUSTOM)

    @patch_dbus_publish_object
    def test_partition_kickstart(self, publisher):
        """Test the part command."""
        ks_in = """
        part / --fstype=ext4 --size=3000
        """
        ks_out = ""
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.CUSTOM)

    @patch_dbus_publish_object
    def test_logvol_kickstart(self, publisher):
        """Test the logvol command."""
        ks_in = """
        logvol / --name=root --vgname=fedora --size=4000
        """
        ks_out = ""
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.CUSTOM)

    @patch_dbus_publish_object
    def test_volgroup_kickstart(self, publisher):
        """Test the volgroup command."""
        ks_in = """
        volgroup fedora pv.1 pv.2
        """
        ks_out = ""
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.CUSTOM)

    @patch_dbus_publish_object
    def test_raid_kickstart(self, publisher):
        """Test the raid command."""
        ks_in = """
        raid / --level=1 --device=0 raid.01 raid.02
        """
        ks_out = ""
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.CUSTOM)

    @unittest.skipIf(isinstance(StorageKickstartSpecification.commands["btrfs"](), RemovedCommand), "btrfs is not supported")
    @patch_dbus_publish_object
    @patch.object(BTRFS, "supported", new_callable=PropertyMock)
    @patch.object(BTRFS, "formattable", new_callable=PropertyMock)
    def test_btrfs_kickstart(self, supported, formattable, publisher):
        """Test the btrfs command."""
        ks_in = """
        btrfs / --subvol --name=root fedora-btrfs
        """
        ks_out = ""

        supported.return_value = True
        formattable.return_value = True
        self._apply_partitioning_when_created()
        self._test_kickstart(ks_in, ks_out)
        self._check_dbus_partitioning(publisher, PartitioningMethod.CUSTOM)

        supported.return_value = False
        formattable.return_value = True
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

        supported.return_value = True
        formattable.return_value = False
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch_dbus_publish_object
    @patch("pyanaconda.modules.storage.kickstart.kernel_arguments")
    def test_autopart_fips_passphrase_bad_kickstart(self, kargs, publisher):
        """Test the autopart command with too weak LUKS password in FIPS mode."""
        kargs.is_enabled.return_value=True
        ks_in = """
        autopart --passphrase=weak
        """
        ks_out = """
        autopart --passphrase=weak
        """
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch_dbus_publish_object
    @patch("pyanaconda.modules.storage.kickstart.kernel_arguments")
    def test_logvol_fips_passphrase_bad_kickstart(self, kargs, publisher):
        """Test the logvol command with too weak LUKS password in FIPS mode."""
        kargs.is_enabled.return_value = True
        ks_in = """
        logvol / --name=root  --vgname=fedora --size=4000 --passphrase=weak
        """
        ks_out = ""
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch_dbus_publish_object
    @patch("pyanaconda.modules.storage.kickstart.kernel_arguments")
    def test_raid_fips_passphrase_bad_kickstart(self, kargs, publisher):
        """Test the raid command with too weak LUKS password in FIPS mode."""
        kargs.is_enabled.return_value = True
        ks_in = """
        raid / --level=1 --device=0 raid.01 raid.02 --passphrase=weak
        """
        ks_out = ""
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch_dbus_publish_object
    @patch("pyanaconda.modules.storage.kickstart.kernel_arguments")
    def test_part_fips_passphrase_bad_kickstart(self, kargs, publisher):
        """Test the part command with too weak LUKS password in FIPS mode."""
        kargs.is_enabled.return_value = True
        ks_in = """
        part / --fstype=ext4 --size=3000 --passphrase=weak
        """
        ks_out = ""
        self._test_kickstart(ks_in, ks_out, ks_valid=False)


class StorageModuleTestCase(unittest.TestCase):
    """Test the storage module."""

    def setUp(self):
        """Set up the module."""
        self.storage_module = StorageService()

    def test_on_protected_devices(self):
        """Test on_protected_devices_changed."""
        # Don't fail without the storage.
        assert self.storage_module._storage_playground is None
        self.storage_module._disk_selection_module.set_protected_devices(["a"])

        # Create the storage.
        assert self.storage_module.storage is not None

        # Protect the devices.
        self.storage_module._disk_selection_module.set_protected_devices(["a", "b"])
        assert self.storage_module.storage.protected_devices == ["a", "b"]

        self.storage_module._disk_selection_module.set_protected_devices(["b", "c"])
        assert self.storage_module.storage.protected_devices == ["b", "c"]


class StorageTasksTestCase(unittest.TestCase):
    """Test the storage tasks."""

    def test_reset(self):
        """Test the reset."""
        storage = Mock()
        task = ScanDevicesTask(storage)
        task.run()
        storage.reset.assert_called_once()

    @patch("pyanaconda.modules.storage.installation.conf")
    def test_activate_filesystems(self, patched_conf):
        """Test ActivateFilesystemsTask."""
        storage = create_storage()
        storage._bootloader = Mock()
        patched_conf.target.is_directory = False
        CreateStorageLayoutTask(storage).run()

        storage = Mock()
        patched_conf.target.is_directory = True
        CreateStorageLayoutTask(storage).run()
        storage.assert_not_called()

    @patch("os.chmod")
    @patch("os.makedirs")
    @patch("blivet.tasks.fsmount.FSMount.do_task")
    @patch("pyanaconda.core.util._run_program")
    def test_mount_filesystems(self, core_run_program, blivet_mount, makedirs, chmod):
        """Test MountFilesystemsTask."""
        storage = create_storage()
        storage._bootloader = Mock()
        blivet_mount.return_value = None
        core_run_program.return_value = (0, "")

        task = MountFilesystemsTask(storage)
        task.run()

        # created mount points
        makedirs.assert_any_call('/mnt/sysimage/tmp')

        # fixed permissions
        chmod.assert_any_call('/mnt/sysimage/tmp', 0o1777)

        # mounted devices
        blivet_mount.assert_any_call('/mnt/sysimage/dev', options='defaults')

        # remounted the root filesystem
        core_run_program.assert_any_call(
                ['mount', '--rbind', '/mnt/sysimage', '/mnt/sysroot'],
                stdin=None, stdout=None, root='/', env_prune=None,
                log_output=True, binary_output=False, do_preexec=True)

    @patch_dbus_get_proxy
    @patch("pyanaconda.modules.storage.installation.conf")
    def test_write_configuration(self, patched_conf, dbus):
        """Test WriteConfigurationTask."""
        storage = Mock(devices=[], devicetree=Mock(_hidden=[]))

        with tempfile.TemporaryDirectory() as d:
            patched_conf.target.system_root = d
            patched_conf.target.physical_root = d

            patched_conf.target.is_directory = True
            WriteConfigurationTask(storage).run()
            assert not os.path.exists("{}/etc".format(d))

            patched_conf.target.is_directory = False
            WriteConfigurationTask(storage).run()
            assert os.path.exists("{}/etc".format(d))

    @patch("pyanaconda.modules.storage.installation.conf")
    @patch("pyanaconda.modules.storage.installation.os.path.exists", return_value=False)
    def test_lvm_devices_file(self, exists_mock, patched_conf):
        """Test writing the LVM devices file"""
        dev1 = Mock()
        dev1.format.type = "lvmpv"
        dev2 = Mock()
        dev2.format.type = "blah"
        dev3 = Mock()
        dev3.format.type = "lvmpv"
        dev4 = Mock()
        dev4.format.type = "ext4"
        storage = Mock(devices=[dev1, dev2], devicetree=Mock(_hidden=[dev3, dev4]))

        with tempfile.TemporaryDirectory() as tmp:
            # lvm devices file: disabled, image installation: False
            with patch("pyanaconda.modules.storage.installation.HAVE_LVMDEVICES", new=False):
                patched_conf.target.is_image = False
                WriteConfigurationTask._write_lvm_devices_file(storage, tmp)
                dev1.format.lvmdevices_add.assert_not_called()
                dev2.format.lvmdevices_add.assert_not_called()
                dev3.format.lvmdevices_add.assert_not_called()
                dev4.format.lvmdevices_add.assert_not_called()
                exists_mock.assert_not_called()

            # lvm devices file: enabled, image installation: True
            with patch("pyanaconda.modules.storage.installation.HAVE_LVMDEVICES", new=True):
                patched_conf.target.is_image = True
                WriteConfigurationTask._write_lvm_devices_file(storage, tmp)
                dev1.format.lvmdevices_add.assert_not_called()
                dev2.format.lvmdevices_add.assert_not_called()
                dev3.format.lvmdevices_add.assert_not_called()
                dev4.format.lvmdevices_add.assert_not_called()
                exists_mock.assert_not_called()

            # lvm devices file: enabled, image installation: False
            with patch("pyanaconda.modules.storage.installation.HAVE_LVMDEVICES", new=True):
                patched_conf.target.is_image = False
                WriteConfigurationTask._write_lvm_devices_file(storage, tmp)
                dev1.format.lvmdevices_add.assert_called_once_with()
                dev2.format.lvmdevices_add.assert_not_called()
                dev3.format.lvmdevices_add.assert_called_once_with()
                dev4.format.lvmdevices_add.assert_not_called()
                exists_mock.assert_called_once_with("/etc/lvm/devices/system.devices")


class StorageValidationTasksTestCase(unittest.TestCase):
    """Test the storage validation tasks."""

    @patch('pyanaconda.modules.storage.partitioning.validate.storage_checker')
    def test_validation(self, storage_checker):
        """Test the validation task."""
        storage = Mock()

        report = StorageCheckerReport()
        storage_checker.check.return_value = report

        report = StorageValidateTask(storage).run()
        assert report.is_valid() is True
        assert report.error_messages == []
        assert report.warning_messages == []

    @patch('pyanaconda.modules.storage.partitioning.validate.storage_checker')
    def test_validation_failed(self, storage_checker):
        """Test the validation task."""
        storage = Mock()

        report = StorageCheckerReport()
        report.add_error("Fake error.")
        report.add_warning("Fake warning.")
        report.add_warning("Fake another warning.")
        storage_checker.check.return_value = report

        report = StorageValidateTask(storage).run()
        assert report.is_valid() is False
        assert report.error_messages == ["Fake error."]
        assert report.warning_messages == ["Fake warning.", "Fake another warning."]


class StorageHelpersTestCase(unittest.TestCase):
    """Test the storage module helpers."""

    @patch("pyanaconda.modules.storage.kickstart.kernel_arguments")
    def test_fips_luks_passphrase_nofips(self, mock_kargs):
        """Test fips_check_luks_passphrase without FIPS."""
        mock_kargs.is_enabled.return_value = False

        fips_check_luks_passphrase("", "command name", 0)
        mock_kargs.is_enabled.assert_not_called()

        fips_check_luks_passphrase("a", "command name", 0)
        mock_kargs.is_enabled.assert_called_once_with("fips")

        fips_check_luks_passphrase("weak", "command name", 0)

        fips_check_luks_passphrase("whatever", "command name", 0)

        fips_check_luks_passphrase("king kong strong", "command name", 0)

    @patch("pyanaconda.modules.storage.kickstart.kernel_arguments")
    def test_fips_luks_passphrase_fips(self, mock_kargs):
        """Test fips_check_luks_passphrase with FIPS."""
        mock_kargs.is_enabled.return_value = True

        fips_check_luks_passphrase("", "command name", 0)
        mock_kargs.is_enabled.assert_not_called()

        with pytest.raises(KickstartParseError):
            fips_check_luks_passphrase("a", "command name", 0)
        mock_kargs.is_enabled.assert_called_once_with("fips")

        with pytest.raises(KickstartParseError):
            fips_check_luks_passphrase("weak", "command name", 0)

        with pytest.raises(KickstartParseError):
            fips_check_luks_passphrase("short", "command name", 0)

        fips_check_luks_passphrase("whatever", "command name", 0)

        fips_check_luks_passphrase("king kong strong", "command name", 0)
