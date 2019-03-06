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
import tempfile
import unittest
from unittest.mock import patch, call, Mock

from blivet.errors import StorageError
from blivet.size import Size

from pyanaconda.bootloader import BootLoaderError
from pykickstart.constants import AUTOPART_TYPE_LVM_THINP, AUTOPART_TYPE_PLAIN, AUTOPART_TYPE_LVM

from pyanaconda.core.constants import MOUNT_POINT_PATH, MOUNT_POINT_DEVICE, MOUNT_POINT_REFORMAT, \
    MOUNT_POINT_FORMAT, MOUNT_POINT_FORMAT_OPTIONS, MOUNT_POINT_MOUNT_OPTIONS
from pyanaconda.dbus.typing import get_variant, Str, Bool, ObjPath
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING, MANUAL_PARTITIONING
from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError, \
    StorageConfigurationError, BootloaderConfigurationError
from pyanaconda.modules.common.errors.storage import InvalidStorageError, UnavailableStorageError, \
    UnavailableDataError
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.storage.dasd import DASDModule
from pyanaconda.modules.storage.dasd.dasd_interface import DASDInterface
from pyanaconda.modules.storage.dasd.discover import DASDDiscoverTask
from pyanaconda.modules.storage.dasd.format import DASDFormatTask
from pyanaconda.modules.storage.fcoe import FCOEModule
from pyanaconda.modules.storage.fcoe.discover import FCOEDiscoverTask
from pyanaconda.modules.storage.fcoe.fcoe_interface import FCOEInterface
from pyanaconda.modules.storage.installation import ActivateFilesystemsTask, MountFilesystemsTask, \
    WriteConfigurationTask
from pyanaconda.modules.storage.partitioning import AutoPartitioningModule, \
    ManualPartitioningModule, CustomPartitioningModule
from pyanaconda.modules.storage.partitioning.automatic_interface import AutoPartitioningInterface
from pyanaconda.modules.storage.partitioning.base_interface import PartitioningInterface
from pyanaconda.modules.storage.partitioning.configure import StorageConfigureTask
from pyanaconda.modules.storage.partitioning.manual_interface import ManualPartitioningInterface
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.modules.storage.reset import StorageResetTask
from pyanaconda.modules.storage.storage import StorageModule
from pyanaconda.modules.storage.storage_interface import StorageInterface
from pyanaconda.modules.storage.zfcp import ZFCPModule
from pyanaconda.modules.storage.zfcp.discover import ZFCPDiscoverTask
from pyanaconda.modules.storage.zfcp.zfcp_interface import ZFCPInterface
from pyanaconda.storage.checker import StorageCheckerReport
from tests.nosetests.pyanaconda_tests import check_kickstart_interface, check_dbus_property


class StorageInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the storage module."""

    def setUp(self):
        """Set up the module."""
        self.storage_module = StorageModule()
        self.storage_interface = StorageInterface(self.storage_module)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def reset_with_task_test(self, publisher):
        """Test ResetWithTask."""
        task_path = self.storage_interface.ResetWithTask()

        # Check the task.
        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)
        self.assertIsInstance(obj.implementation, StorageResetTask)
        self.assertIsNotNone(obj.implementation._storage)

        # Check the side affects.
        storage_changed_callback = Mock()
        self.storage_module.storage_changed.connect(storage_changed_callback)

        obj.implementation.stopped_signal.emit()
        storage_changed_callback.called_once()

    def get_required_device_size_test(self):
        """Test GetRequiredDeviceSize."""
        required_size = self.storage_interface.GetRequiredDeviceSize(Size("1 GiB").get_bytes())
        self.assertEqual(Size("1280 MiB").get_bytes(), required_size, Size(required_size))

    @patch('pyanaconda.modules.storage.partitioning.validate.storage_checker')
    def apply_partitioning_test(self, storage_checker):
        """Test ApplyPartitioning."""
        storage_1 = Mock()
        storage_2 = storage_1.copy.return_value
        storage_3 = storage_2.copy.return_value

        report = StorageCheckerReport()
        storage_checker.check.return_value = report

        self.storage_module.set_storage(storage_1)
        self.assertEqual(self.storage_module.storage, storage_1)
        self.assertEqual(self.storage_module._auto_part_module.storage, storage_2)

        self.storage_interface.ApplyPartitioning(AUTO_PARTITIONING.object_path)
        self.assertEqual(self.storage_module.storage, storage_3)

        with self.assertRaises(ValueError):
            self.storage_interface.ApplyPartitioning(ObjPath("invalid"))

    @patch('pyanaconda.dbus.DBus.publish_object')
    def install_with_tasks_test(self, publisher):
        """Test InstallWithTask."""
        task_classes = [
            ActivateFilesystemsTask,
            MountFilesystemsTask,
            WriteConfigurationTask
        ]

        # Get the installation tasks.
        with tempfile.TemporaryDirectory() as sysroot:
            task_paths = self.storage_interface.InstallWithTasks(sysroot)

        # Check the number of installation tasks.
        task_number = len(task_classes)
        self.assertEqual(task_number, len(task_paths))
        self.assertEqual(task_number, publisher.call_count)

        # Check the tasks.
        for i in range(task_number):
            object_path, obj = publisher.call_args_list[i][0]
            self.assertEqual(object_path, task_paths[i])
            self.assertIsInstance(obj, TaskInterface)
            self.assertIsInstance(obj.implementation, task_classes[i])

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(
            self.storage_interface.KickstartCommands,
            [
                'autopart',
                'bootloader',
                'btrfs',
                'clearpart',
                'fcoe',
                'ignoredisk',
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
                'zfcp'
            ]
        )
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

    @patch("pyanaconda.modules.storage.kickstart.DiskLabel")
    def clearpart_disklabel_kickstart_test(self, disk_label):
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

    def autopart_kickstart_test(self):
        """Test the autopart command."""
        ks_in = """
        autopart
        """
        ks_out = """
        autopart
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_type_kickstart_test(self):
        """Test the autopart command with the type option."""
        ks_in = """
        autopart --type=thinp
        """
        ks_out = """
        autopart --type=thinp
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_fstype_kickstart_test(self):
        """Test the autopart command with the fstype option."""
        ks_in = """
        autopart --fstype=ext4
        """
        ks_out = """
        autopart --fstype=ext4
        """
        self._test_kickstart(ks_in, ks_out)

        ks_in = """
        autopart --fstype=invalid
        """
        ks_out = ""
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    def autopart_nopart_kickstart_test(self):
        """Test the autopart command with nohome, noboot and noswap options."""
        ks_in = """
        autopart --nohome --noboot --noswap
        """
        ks_out = """
        autopart --nohome --noboot --noswap
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_encrypted_kickstart_test(self):
        """Test the autopart command with the encrypted option."""
        ks_in = """
        autopart --encrypted
        """
        ks_out = """
        autopart --encrypted
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_cipher_kickstart_test(self):
        """Test the autopart command with the cipher option."""
        ks_in = """
        autopart --encrypted --cipher="aes-xts-plain64"
        """
        ks_out = """
        autopart --encrypted --cipher="aes-xts-plain64"
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_passphrase_kickstart_test(self):
        """Test the autopart command with the passphrase option."""
        ks_in = """
        autopart --encrypted --passphrase="123456"
        """
        ks_out = """
        autopart --encrypted --passphrase="123456"
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_escrowcert_kickstart_test(self):
        """Test the autopart command with the escrowcert option."""
        ks_in = """
        autopart --encrypted --escrowcert="file:///tmp/escrow.crt"
        """
        ks_out = """
        autopart --encrypted --escrowcert="file:///tmp/escrow.crt"
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_backuppassphrase_kickstart_test(self):
        """Test the autopart command with the backuppassphrase option."""
        ks_in = """
        autopart --encrypted --escrowcert="file:///tmp/escrow.crt" --backuppassphrase
        """
        ks_out = """
        autopart --encrypted --escrowcert="file:///tmp/escrow.crt" --backuppassphrase
        """
        self._test_kickstart(ks_in, ks_out)

    def mount_kickstart_test(self):
        """Test the mount command."""
        ks_in = """
        mount /dev/sda1 /boot
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 /boot
        """
        self._test_kickstart(ks_in, ks_out)

    def mount_none_kickstart_test(self):
        """Test the mount command with none."""
        ks_in = """
        mount /dev/sda1 none
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 none
        """
        self._test_kickstart(ks_in, ks_out)

    def mount_mountoptions_kickstart_test(self):
        """Test the mount command with the mountoptions."""
        ks_in = """
        mount /dev/sda1 /boot --mountoptions="user"
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 /boot --mountoptions="user"
        """
        self._test_kickstart(ks_in, ks_out)

    def mount_reformat_kickstart_test(self):
        """Test the mount command with the reformat option."""
        ks_in = """
        mount /dev/sda1 /boot --reformat
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 /boot --reformat
        """
        self._test_kickstart(ks_in, ks_out)

    def mount_mkfsoptions_kickstart_test(self):
        """Test the mount command with the mkfsoptions."""
        ks_in = """
        mount /dev/sda1 /boot --reformat=xfs --mkfsoptions="-L BOOT"
        """
        ks_out = """
        # Mount points configuration
        mount /dev/sda1 /boot --reformat=xfs --mkfsoptions="-L BOOT"
        """
        self._test_kickstart(ks_in, ks_out)

    def mount_multiple_kickstart_test(self):
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
        self._test_kickstart(ks_in, ks_out)

    def autopart_luks_version_kickstart_test(self):
        """Test the autopart command with the luks version option."""
        ks_in = """
        autopart --encrypted --luks-version=luks1
        """
        ks_out = """
        autopart --encrypted --luks-version=luks1
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_pbkdf_kickstart_test(self):
        """Test the autopart command with the pbkdf option."""
        ks_in = """
        autopart --encrypted --pbkdf=pbkdf2
        """
        ks_out = """
        autopart --encrypted --pbkdf=pbkdf2
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_pbkdf_memory_kickstart_test(self):
        """Test the autopart command with the pbkdf memory option."""
        ks_in = """
        autopart --encrypted --pbkdf-memory=256
        """
        ks_out = """
        autopart --encrypted --pbkdf-memory=256
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_pbkdf_time_kickstart_test(self):
        """Test the autopart command with the pbkdf time option."""
        ks_in = """
        autopart --encrypted --pbkdf-time=100
        """
        ks_out = """
        autopart --encrypted --pbkdf-time=100
        """
        self._test_kickstart(ks_in, ks_out)

    def autopart_pbkdf_iterations_kickstart_test(self):
        """Test the autopart command with the pbkdf iterations option."""
        ks_in = """
        autopart --encrypted --pbkdf-iterations=1000
        """
        ks_out = """
        autopart --encrypted --pbkdf-iterations=1000
        """
        self._test_kickstart(ks_in, ks_out)

    @patch("pyanaconda.modules.storage.kickstart.fcoe")
    @patch("pyanaconda.modules.storage.kickstart.get_supported_devices")
    def fcoe_kickstart_test(self, get_supported_devices, fcoe):
        """Test the fcoe command."""
        ks_in = """
        fcoe --nic=eth0 --dcb --autovlan
        """
        ks_out = """
        fcoe --nic=eth0 --dcb --autovlan
        """
        get_supported_devices.return_value = ["eth0"]
        self._test_kickstart(ks_in, ks_out)

        get_supported_devices.return_value = ["eth1"]
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch("pyanaconda.storage.initialization.load_plugin_s390")
    @patch("pyanaconda.modules.storage.kickstart.zfcp")
    @patch("pyanaconda.modules.storage.storage.arch.is_s390", return_value=True)
    def zfcp_kickstart_test(self, arch, zfcp, loader):
        """Test the zfcp command."""
        self.setUp()  # set up for s390x

        ks_in = """
        zfcp --devnum=0.0.fc00 --wwpn=0x401040a000000000 --fcplun=0x5105074308c212e9
        """
        ks_out = """
        zfcp --devnum=0.0.fc00 --wwpn=0x401040a000000000 --fcplun=0x5105074308c212e9
        """
        self._test_kickstart(ks_in, ks_out)

    @patch("pyanaconda.modules.storage.kickstart.nvdimm")
    def nvdimm_kickstart_test(self, nvdimm):
        """Test the nvdimm command."""
        ks_in = """
        nvdimm use --namespace=namespace0.0
        nvdimm reconfigure --namespace=namespace1.0 --mode=sector --sectorsize=512
        """
        ks_out = """
        # NVDIMM devices setup
        nvdimm use --namespace=namespace0.0
        nvdimm reconfigure --namespace=namespace1.0 --mode=sector --sectorsize=512
        """
        nvdimm.namespaces = ["namespace0.0", "namespace1.0"]
        self._test_kickstart(ks_in, ks_out)

        nvdimm.namespaces = ["namespace0.0"]
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

        nvdimm.namespaces = ["namespace1.0"]
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    @patch("pyanaconda.modules.storage.kickstart.device_matches")
    def nvdimm_blockdevs_kickstart_test(self, device_matches):
        """Test the nvdimm command with blockdevs."""
        ks_in = """
        nvdimm use --blockdevs=pmem0
        """
        ks_out = """
        # NVDIMM devices setup
        nvdimm use --blockdevs=pmem0
        """
        device_matches.return_value = ["pmem0"]
        self._test_kickstart(ks_in, ks_out)

        device_matches.return_value = []
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    def snapshot_kickstart_test(self):
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

    def snapshot_invalid_kickstart_test(self):
        """Test the snapshot command with invalid origin."""
        ks_in = """
        snapshot invalid --name=pre-snapshot --when=pre-install
        """
        ks_out = """
        snapshot invalid --name=pre-snapshot --when=pre-install
        """
        self._test_kickstart(ks_in, ks_out, ks_valid=False)

    def snapshot_warning_kickstart_test(self):
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

    @patch("pyanaconda.dbus.DBus.get_proxy")
    def custom_partitioning_kickstart_test(self, proxy_getter):
        """Smoke test for the custom partitioning."""
        # Make sure that the storage model is created.
        self.assertTrue(self.storage_module.storage)

        # Make sure that the storage playground is created.
        self.assertTrue(self.storage_module._custom_part_module.storage)

        # Try to get kickstart data.
        self._test_kickstart("", "")


class StorageTasksTestCase(unittest.TestCase):
    """Test the storage tasks."""

    def reset_test(self):
        """Test the reset."""
        storage = Mock()
        task = StorageResetTask(storage)
        task.run()
        storage.reset.called_once()


class AutopartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the auto partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.autopart_module = AutoPartitioningModule()
        self.autopart_interface = AutoPartitioningInterface(self.autopart_module)

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            AUTO_PARTITIONING,
            self.autopart_interface,
            *args, **kwargs
        )

    def enabled_property_test(self):
        """Test the property enabled."""
        self._test_dbus_property(
            "Enabled",
            True
        )

    def type_property_test(self):
        """Test the type property."""
        self._test_dbus_property(
            "Type",
            AUTOPART_TYPE_LVM_THINP
        )

        self._test_dbus_property(
            "Type",
            AUTOPART_TYPE_PLAIN
        )

        self._test_dbus_property(
            "Type",
            AUTOPART_TYPE_LVM
        )

    def filesystem_type_property_test(self):
        """Test the filesystem property."""
        self._test_dbus_property(
            "FilesystemType",
            "ext4"
        )

    def nohome_property_test(self):
        """Test the nohome property."""
        def setter(value):
            self.autopart_module.set_nohome(value)
            self.autopart_module.module_properties_changed.emit()

        self._test_dbus_property(
            "NoHome",
            True,
            setter=setter
        )

    def noboot_property_test(self):
        """Test the noboot property."""
        def setter(value):
            self.autopart_module.set_noboot(value)
            self.autopart_module.module_properties_changed.emit()

        self._test_dbus_property(
            "NoBoot",
            True,
            setter=setter
        )

    def noswap_property_test(self):
        """Test the noswap property."""
        def setter(value):
            self.autopart_module.set_noswap(value)
            self.autopart_module.module_properties_changed.emit()

        self._test_dbus_property(
            "NoSwap",
            True,
            setter=setter
        )

    def encrypted_property_test(self):
        """Test the encrypted property."""
        self._test_dbus_property(
            "Encrypted",
            True
        )

    def cipher_property_test(self):
        """Test the cipher property,"""
        self._test_dbus_property(
            "Cipher",
            "aes-xts-plain64"
        )

    def passphrase_property_test(self):
        """Test the passphrase property."""
        self._test_dbus_property(
            "Passphrase",
            "123456"
        )

    def luks_version_property_test(self):
        """Test the luks version property."""
        self._test_dbus_property(
            "LUKSVersion",
            "luks1"
        )

    def pbkdf_property_test(self):
        """Test the PBKDF property."""
        self._test_dbus_property(
            "PBKDF",
            "argon2i"
        )

    def pbkdf_memory_property_test(self):
        """Test the PBKDF memory property."""
        self._test_dbus_property(
            "PBKDFMemory",
            256
        )

    def pbkdf_time_property_test(self):
        """Test the PBKDF time property."""
        self._test_dbus_property(
            "PBKDFTime",
            100
        )

    def pbkdf_iterations_property_test(self):
        """Test the PBKDF iterations property."""
        self._test_dbus_property(
            "PBKDFIterations",
            1000
        )

    def escrowcert_property_test(self):
        """Test the escrowcert property."""
        self._test_dbus_property(
            "Escrowcert",
            "file:///tmp/escrow.crt"
        )

    def backup_passphrase_enabled_property_test(self):
        """Test the backup passphrase enabled property."""
        self._test_dbus_property(
            "BackupPassphraseEnabled",
            True
        )

    def reset_test(self):
        """Test the reset of the storage."""
        with self.assertRaises(UnavailableStorageError):
            if self.autopart_module.storage:
                self.fail("The storage shouldn't be available.")

        storage = Mock()
        self.autopart_module.on_storage_reset(storage)

        self.assertEqual(self.autopart_module._current_storage, storage)
        self.assertIsNone(self.autopart_module._storage_playground)

        self.assertNotEqual(self.autopart_module.storage, storage)
        self.assertIsNotNone(self.autopart_module._storage_playground)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.autopart_module.on_storage_reset(Mock())
        task_path = self.autopart_interface.ConfigureWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, StorageConfigureTask)
        self.assertEqual(obj.implementation._storage, self.autopart_module.storage)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def validate_with_task_test(self, publisher):
        """Test ValidateWithTask."""
        self.autopart_module.on_storage_reset(Mock())
        task_path = self.autopart_interface.ValidateWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, StorageValidateTask)
        self.assertEqual(obj.implementation._storage, self.autopart_module.storage)


class DASDInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the DASD module."""

    def setUp(self):
        """Set up the module."""
        self.dasd_module = DASDModule()
        self.dasd_interface = DASDInterface(self.dasd_module)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def discover_with_task_test(self, publisher):
        """Test DiscoverWithTask."""
        task_path = self.dasd_interface.DiscoverWithTask("0.0.A100")

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, DASDDiscoverTask)
        self.assertEqual(obj.implementation._device_number, "0.0.A100")

    @patch('pyanaconda.dbus.DBus.publish_object')
    def format_with_task_test(self, publisher):
        """Test the discover task."""
        task_path = self.dasd_interface.FormatWithTask(["/dev/sda", "/dev/sdb"])

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)
        self.assertIsInstance(obj.implementation, DASDFormatTask)
        self.assertEqual(obj.implementation._dasds, ["/dev/sda", "/dev/sdb"])


class DASDTasksTestCase(unittest.TestCase):
    """Test DASD tasks."""

    def discovery_fails_test(self):
        """Test the failing discovery task."""
        with self.assertRaises(StorageDiscoveryError):
            DASDDiscoverTask("x.y.z").run()

    @patch('pyanaconda.modules.storage.dasd.discover.blockdev')
    def discovery_test(self, blockdev):
        """Test the discovery task."""
        DASDDiscoverTask("0.0.A100").run()
        blockdev.s390.sanitize_dev_input.assert_called_once_with("0.0.A100")

        sanitized_input = blockdev.s390.sanitize_dev_input.return_value
        blockdev.s390.dasd_online.assert_called_once_with(sanitized_input)

    @patch('pyanaconda.modules.storage.dasd.format.blockdev')
    def format_test(self, blockdev):
        """Test the format task."""
        DASDFormatTask(["/dev/sda", "/dev/sdb"]).run()
        blockdev.s390.dasd_format.assert_has_calls([
            call("/dev/sda"),
            call("/dev/sdb")
        ])


class FCOEInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the FCoE module."""

    def setUp(self):
        """Set up the module."""
        self.fcoe_module = FCOEModule()
        self.fcoe_interface = FCOEInterface(self.fcoe_module)

    def get_nics_test(self):
        """Test the get nics method."""
        self.assertEqual(self.fcoe_interface.GetNics(), list())

    def get_dracut_arguments(self):
        """Test the get dracut arguments method."""
        self.assertEqual(self.fcoe_interface.GetDracutArguments("eth0"), list())

    @patch('pyanaconda.dbus.DBus.publish_object')
    def discover_with_task_test(self, publisher):
        """Test the discover task."""
        task_path = self.fcoe_interface.DiscoverWithTask(
            "eth0",  # nic
            False,  # dcb
            True  # auto_vlan
        )

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, FCOEDiscoverTask)
        self.assertEqual(obj.implementation._nic, "eth0")
        self.assertEqual(obj.implementation._dcb, False)
        self.assertEqual(obj.implementation._auto_vlan, True)

    @patch('pyanaconda.modules.storage.fcoe.fcoe.fcoe')
    def reload_module_test(self, fcoe):
        """Test ReloadModule."""
        self.fcoe_interface.ReloadModule()
        fcoe.startup.assert_called_once_with()

    @patch('pyanaconda.modules.storage.fcoe.fcoe.fcoe')
    def write_configuration_test(self, fcoe):
        """Test WriteConfiguration."""

        with tempfile.TemporaryDirectory() as root:
            self.fcoe_interface.WriteConfiguration(root)
            fcoe.write.assert_called_once_with(root)


class FCOETasksTestCase(unittest.TestCase):
    """Test FCoE tasks."""

    @patch('pyanaconda.modules.storage.fcoe.discover.fcoe')
    def discovery_fails_test(self, fcoe):
        """Test the failing discovery task."""
        fcoe.add_san.return_value = "Fake error message"

        with self.assertRaises(StorageDiscoveryError) as cm:
            FCOEDiscoverTask(nic="eth0", dcb=False, auto_vlan=True).run()

        self.assertEqual(str(cm.exception), "Fake error message")

    @patch('pyanaconda.modules.storage.fcoe.discover.fcoe')
    def discovery_test(self, fcoe):
        """Test the discovery task."""
        fcoe.add_san.return_value = ""

        FCOEDiscoverTask(nic="eth0", dcb=False, auto_vlan=True).run()

        fcoe.add_san.assert_called_once_with("eth0", False, True)
        fcoe.added_nics.append.assert_called_once_with("eth0")


class ZFCPInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the zFCP module."""

    def setUp(self):
        """Set up the module."""
        self.zfcp_module = ZFCPModule()
        self.zfcp_interface = ZFCPInterface(self.zfcp_module)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def discover_with_task_test(self, publisher):
        """Test the discover task."""
        task_path = self.zfcp_interface.DiscoverWithTask(
            "0.0.fc00",
            "0x5105074308c212e9",
            "0x401040a000000000"
        )

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, ZFCPDiscoverTask)
        self.assertEqual(obj.implementation._device_number, "0.0.fc00")
        self.assertEqual(obj.implementation._wwpn, "0x5105074308c212e9")
        self.assertEqual(obj.implementation._lun, "0x401040a000000000")

    @patch('pyanaconda.modules.storage.zfcp.zfcp.zfcp')
    def reload_module_test(self, zfcp):
        """Test ReloadModule."""
        self.zfcp_interface.ReloadModule()
        zfcp.startup.assert_called_once_with()

    @patch('pyanaconda.modules.storage.zfcp.zfcp.zfcp')
    def write_configuration_test(self, zfcp):
        """Test WriteConfiguration."""

        with tempfile.TemporaryDirectory() as root:
            self.zfcp_interface.WriteConfiguration(root)
            zfcp.write.assert_called_once_with(root)


class ZFCPTasksTestCase(unittest.TestCase):
    """Test zFCP tasks."""

    def discovery_fails_test(self):
        """Test the failing discovery task."""

        with self.assertRaises(StorageDiscoveryError):
            ZFCPDiscoverTask("", "", "").run()

        with self.assertRaises(StorageDiscoveryError):
            ZFCPDiscoverTask("0.0.fc00", "", "").run()

        with self.assertRaises(StorageDiscoveryError):
            ZFCPDiscoverTask("0.0.fc00", "0x5105074308c212e9", "").run()

    @patch('pyanaconda.modules.storage.zfcp.discover.zfcp')
    @patch('pyanaconda.modules.storage.zfcp.discover.blockdev')
    def discovery_test(self, blockdev, zfcp):
        """Test the discovery task."""
        ZFCPDiscoverTask("0.0.fc00", "0x5105074308c212e9", "0x401040a000000000").run()

        blockdev.s390.sanitize_dev_input.assert_called_once_with("0.0.fc00")
        blockdev.s390.zfcp_sanitize_wwpn_input.assert_called_once_with("0x5105074308c212e9")
        blockdev.s390.zfcp_sanitize_lun_input.assert_called_once_with("0x401040a000000000")

        sanitized_dev = blockdev.s390.sanitize_dev_input.return_value
        sanitized_wwpn = blockdev.s390.zfcp_sanitize_wwpn_input.return_value
        sanitized_lun = blockdev.s390.zfcp_sanitize_lun_input.return_value

        zfcp.add_fcp.assert_called_once_with(sanitized_dev, sanitized_wwpn, sanitized_lun)


class ManualPartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the manual partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.manual_part_module = ManualPartitioningModule()
        self.manual_part_interface = ManualPartitioningInterface(self.manual_part_module)

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            MANUAL_PARTITIONING,
            self.manual_part_interface,
            *args, **kwargs
        )

    def enabled_property_test(self):
        """Test the enabled property."""
        self._test_dbus_property(
            "Enabled",
            True
        )

        self._test_dbus_property(
            "Enabled",
            False
        )

    def mount_points_property_test(self):
        """Test the mount points property."""
        self._test_dbus_property(
            "MountPoints",
            []
        )

        in_value = [
            {
                "mount-point": "/boot",
                "device": "/dev/sda1"
            }
        ]

        out_value = [
            {
                MOUNT_POINT_PATH: get_variant(Str, "/boot"),
                MOUNT_POINT_DEVICE: get_variant(Str, "/dev/sda1"),
                MOUNT_POINT_REFORMAT: get_variant(Bool, False),
                MOUNT_POINT_FORMAT: get_variant(Str, ""),
                MOUNT_POINT_FORMAT_OPTIONS: get_variant(Str, ""),
                MOUNT_POINT_MOUNT_OPTIONS: get_variant(Str, "")
            }
        ]

        self._test_dbus_property(
            "MountPoints",
            in_value,
            out_value
        )

        in_value = [
            {
                "mount-point":  "/boot",
                "device": "/dev/sda1",
                "reformat": True,
                "format": "xfs",
                "format-options": "-L BOOT",
                "mount-options": "user"
            }
        ]

        out_value = [
            {
                MOUNT_POINT_PATH: get_variant(Str, "/boot"),
                MOUNT_POINT_DEVICE: get_variant(Str, "/dev/sda1"),
                MOUNT_POINT_REFORMAT: get_variant(Bool, True),
                MOUNT_POINT_FORMAT: get_variant(Str, "xfs"),
                MOUNT_POINT_FORMAT_OPTIONS: get_variant(Str, "-L BOOT"),
                MOUNT_POINT_MOUNT_OPTIONS: get_variant(Str, "user")
            }
        ]

        self._test_dbus_property(
            "MountPoints",
            in_value,
            out_value,
        )

        in_value = [
            {
                "mount-point": "/boot",
                "device": "/dev/sda1"
            },
            {
                "mount-point": "/",
                "device": "/dev/sda2",
                "reformat": True
            }
        ]

        out_value = [
            {
                MOUNT_POINT_PATH: get_variant(Str, "/boot"),
                MOUNT_POINT_DEVICE: get_variant(Str, "/dev/sda1"),
                MOUNT_POINT_REFORMAT: get_variant(Bool, False),
                MOUNT_POINT_FORMAT: get_variant(Str, ""),
                MOUNT_POINT_FORMAT_OPTIONS: get_variant(Str, ""),
                MOUNT_POINT_MOUNT_OPTIONS: get_variant(Str, "")
            },
            {
                MOUNT_POINT_PATH: get_variant(Str, "/"),
                MOUNT_POINT_DEVICE: get_variant(Str, "/dev/sda2"),
                MOUNT_POINT_REFORMAT: get_variant(Bool, True),
                MOUNT_POINT_FORMAT: get_variant(Str, ""),
                MOUNT_POINT_FORMAT_OPTIONS: get_variant(Str, ""),
                MOUNT_POINT_MOUNT_OPTIONS: get_variant(Str, "")
            }
        ]

        self._test_dbus_property(
            "MountPoints",
            in_value,
            out_value
        )

    @patch('pyanaconda.dbus.DBus.publish_object')
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.manual_part_module.on_storage_reset(Mock())
        task_path = self.manual_part_interface.ConfigureWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, StorageConfigureTask)
        self.assertEqual(obj.implementation._storage, self.manual_part_module.storage)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def validate_with_task_test(self, publisher):
        """Test ValidateWithTask."""
        self.manual_part_module.on_storage_reset(Mock())
        task_path = self.manual_part_interface.ValidateWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, StorageValidateTask)
        self.assertEqual(obj.implementation._storage, self.manual_part_module.storage)


class CustomPartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the custom partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.custom_part_module = CustomPartitioningModule()
        self.custom_part_interface = PartitioningInterface(self.custom_part_module)

    def data_test(self, ):
        """Test the data property."""
        with self.assertRaises(UnavailableDataError):
            if self.custom_part_module.data:
                self.fail("The data should not be available.")

        data = Mock()
        self.custom_part_module.process_kickstart(data)
        self.assertEqual(self.custom_part_module.data, data)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.custom_part_module.on_storage_reset(Mock())
        self.custom_part_module.process_kickstart(Mock())
        task_path = self.custom_part_interface.ConfigureWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, StorageConfigureTask)
        self.assertEqual(obj.implementation._storage, self.custom_part_module.storage)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def validate_with_task_test(self, publisher):
        """Test ValidateWithTask."""
        self.custom_part_module.on_storage_reset(Mock())
        task_path = self.custom_part_interface.ValidateWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, StorageValidateTask)
        self.assertEqual(obj.implementation._storage, self.custom_part_module.storage)


class StorageConfigurationTasksTestCase(unittest.TestCase):
    """Test the storage configuration tasks."""

    @patch('pyanaconda.modules.storage.partitioning.configure.do_kickstart_storage')
    def configuration_test(self, do_kickstart_storage):
        """Test the configuration task."""
        storage = Mock()
        partitioning = Mock()

        StorageConfigureTask(storage, partitioning).run()
        do_kickstart_storage.called_once_with(storage, partitioning)

    @patch('pyanaconda.modules.storage.partitioning.configure.do_kickstart_storage')
    def configuration_failed_test(self, do_kickstart_storage):
        """Test the failing configuration task."""
        storage = Mock()
        partitioning = Mock()
        do_kickstart_storage.side_effect = StorageError("Fake storage error.")

        with self.assertRaises(StorageConfigurationError) as cm:
            StorageConfigureTask(storage, partitioning).run()

        self.assertEqual(str(cm.exception), "Fake storage error.")
        do_kickstart_storage.side_effect = BootLoaderError("Fake bootloader error.")

        with self.assertRaises(BootloaderConfigurationError) as cm:
            StorageConfigureTask(storage, partitioning).run()

        self.assertEqual(str(cm.exception), "Fake bootloader error.")


class StorageValidationTasksTestCase(unittest.TestCase):
    """Test the storage validation tasks."""

    @patch('pyanaconda.modules.storage.partitioning.validate.storage_checker')
    def validation_test(self, storage_checker):
        """Test the validation task."""
        storage = Mock()

        report = StorageCheckerReport()
        storage_checker.check.return_value = report

        StorageValidateTask(storage).run()

    @patch('pyanaconda.modules.storage.partitioning.validate.storage_checker')
    def validation_failed_test(self, storage_checker):
        """Test the validation task."""
        storage = Mock()

        report = StorageCheckerReport()
        report.add_error("Fake error.")
        storage_checker.check.return_value = report

        with self.assertRaises(InvalidStorageError) as cm:
            StorageValidateTask(storage).run()

        self.assertEqual(str(cm.exception), "Fake error.")
