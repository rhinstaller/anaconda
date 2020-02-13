#
# Copyright (C) 2020  Red Hat, Inc.
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
import copy
from unittest.mock import patch, Mock

from blivet.devicefactory import DEVICE_TYPE_LVM, SIZE_POLICY_AUTO, DEVICE_TYPE_PARTITION, \
    DEVICE_TYPE_LVM_THINP, DEVICE_TYPE_DISK, DEVICE_TYPE_MD
from blivet.devices import StorageDevice, DiskDevice, PartitionDevice, LUKSDevice, \
    BTRFSVolumeDevice
from blivet.formats import get_format
from blivet.formats.fs import FS
from blivet.size import Size
from dasbus.structure import compare_data
from dasbus.typing import get_native
from pykickstart.constants import AUTOPART_TYPE_PLAIN

from pyanaconda.modules.common.errors.configuration import StorageConfigurationError
from pyanaconda.modules.common.structures.device_factory import DeviceFactoryRequest
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.storage.partitioning.interactive.interactive_partitioning import \
    InteractiveAutoPartitioningTask
from pyanaconda.modules.storage.partitioning.interactive.scheduler_interface import \
    DeviceTreeSchedulerInterface
from pyanaconda.modules.storage.partitioning.interactive.scheduler_module import \
    DeviceTreeSchedulerModule
from pyanaconda.platform import EFI
from pyanaconda.storage.initialization import create_storage
from pyanaconda.storage.root import Root
from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation


class DeviceTreeSchedulerTestCase(unittest.TestCase):
    """Test DBus interface of the device tree scheduler."""

    def setUp(self):
        """Set up the module."""
        self.maxDiff = None
        self.module = DeviceTreeSchedulerModule()
        self.interface = DeviceTreeSchedulerInterface(self.module)
        self.module.on_storage_changed(create_storage())

    @property
    def storage(self):
        """Get the storage object."""
        return self.module.storage

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.storage.devicetree._add_device(device)

    def publication_test(self):
        """Test the DBus representation."""
        self.assertIsInstance(self.module.for_publication(), DeviceTreeSchedulerInterface)

    def generate_system_name_test(self):
        """Test GenerateSystemName."""
        self.assertEqual(
            self.interface.GenerateSystemName(),
            "New anaconda bluesky Installation"
        )

    def generate_system_data_test(self):
        """Test GenerateSystemData."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/boot")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev3", fmt=get_format("swap")))

        os_data = self.interface.GenerateSystemData("dev1")
        self.assertEqual(get_native(os_data), {
            'mount-points': {'/boot': 'dev1', '/': 'dev2'},
            'os-name': 'New anaconda bluesky Installation',
            'swap-devices': ['dev3']
        })

    def get_partitioned_test(self):
        """Test GetPartitioned."""
        self._add_device(DiskDevice(
            "dev1",
            exists=True,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        ))
        self._add_device(DiskDevice(
            "dev2",
            exists=True,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        ))
        self._add_device(StorageDevice(
            "dev3",
            exists=True,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        ))
        self.assertEqual(self.interface.GetPartitioned(), ["dev1", "dev2"])

    def collect_new_devices_test(self):
        """Test CollectNewDevices."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/boot")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev3", fmt=get_format("swap")))
        self.assertEqual(self.interface.CollectNewDevices("dev1"), ["dev1", "dev2", "dev3"])

    def collect_unused_devices_test(self):
        """Test CollectUnusedDevices."""
        dev1 = DiskDevice(
            "dev1",
            fmt=get_format("disklabel")
        )
        dev2 = StorageDevice(
            "dev2",
            parents=[dev1],
            fmt=get_format("ext4")
        )
        dev3 = StorageDevice(
            "dev3",
            parents=[dev1],
            fmt=get_format("ext4")
        )
        dev4 = StorageDevice(
            "dev4",
            parents=[dev1],
            fmt=get_format("ext4", mountpoint="/")
        )

        self._add_device(dev1)
        self._add_device(dev2)
        self._add_device(dev3)
        self._add_device(dev4)

        self.assertEqual(self.interface.CollectUnusedDevices(), ["dev2", "dev3"])

    def collect_boot_loader_devices_test(self):
        """Test CollectBootLoaderDevices."""
        self._add_device(StorageDevice("dev1", fmt=get_format("biosboot")))
        self._add_device(StorageDevice("dev2", fmt=get_format("prepboot")))
        self._add_device(StorageDevice("dev3", fmt=get_format("ext4")))
        self.assertEqual(self.interface.CollectBootLoaderDevices(""), ["dev1", "dev2"])

    @patch.object(FS, "update_size_info")
    def collect_supported_systems_test(self, update_size_info):
        """Test CollectSupportedSystems."""
        dev1 = DiskDevice(
            "dev1",
            fmt=get_format("disklabel")
        )
        dev2 = StorageDevice(
            "dev2",
            parents=[dev1],
            fmt=get_format("ext4", mountpoint="/", exists=True),
        )
        dev3 = StorageDevice(
            "dev3",
            parents=[dev1],
            fmt=get_format("swap", exists=True)
        )

        self._add_device(dev1)
        self._add_device(dev2)
        self._add_device(dev3)

        self.storage.roots = [Root(
            name="My Linux",
            mounts={"/": dev2},
            swaps=[dev3]
        )]

        os_data_list = self.interface.CollectSupportedSystems()
        self.assertEqual(get_native(os_data_list), [{
            'os-name': 'My Linux',
            'mount-points': {'/': 'dev2'},
            'swap-devices': ['dev3']
        }])

    def get_default_file_system_test(self):
        """Test GetDefaultFileSystem."""
        self.assertEqual(self.interface.GetDefaultFileSystem(), "ext4")

    def get_supported_raid_levels_test(self):
        """Test GetSupportedRaidLevels."""
        self.assertEqual(
            self.interface.GetSupportedRaidLevels(DEVICE_TYPE_LVM),
            ['linear', 'raid1', 'raid10', 'raid4', 'raid5', 'raid6', 'striped']
        )

    @patch('pyanaconda.modules.storage.partitioning.interactive.utils.get_format')
    @patch('pyanaconda.modules.storage.partitioning.interactive.utils.platform', new_callable=EFI)
    def collect_unused_mount_points_test(self, platform, format_getter):
        """Test CollectUnusedMountPoints."""
        format_getter.side_effect = lambda fmt: Mock(supported=(fmt == "biosboot"))

        self._add_device(StorageDevice(
            "dev1",
            fmt=get_format("ext4", mountpoint="/boot")
        ))
        self._add_device(StorageDevice(
            "dev2",
            fmt=get_format("ext4", mountpoint="/")
        ))
        self.assertEqual(self.interface.CollectUnusedMountPoints(), [
            '/boot/efi', '/home', '/var', 'swap', 'biosboot'
        ])

    def _check_report(self, report, error_message=None):
        """Check the given validation report."""
        errors = [error_message] if error_message else []
        warnings = []

        self.assertEqual(get_native(report), {
            "error-messages": errors,
            "warning-messages": warnings
        })

    def validate_mount_point_test(self):
        """Test ValidateMountPoint."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/boot")))

        report = self.interface.ValidateMountPoint("/boot")
        self._check_report(report, "That mount point is already in use. Try something else?")

        report = self.interface.ValidateMountPoint("")
        self._check_report(report, "Please enter a valid mount point.")

        report = self.interface.ValidateMountPoint("/dev")
        self._check_report(report, "That mount point is invalid. Try something else?")

        report = self.interface.ValidateMountPoint("/home/")
        self._check_report(report, "That mount point is invalid. Try something else?")

        report = self.interface.ValidateMountPoint("/home/")
        self._check_report(report, "That mount point is invalid. Try something else?")

        report = self.interface.ValidateMountPoint("home")
        self._check_report(report, "That mount point is invalid. Try something else?")

        report = self.interface.ValidateMountPoint("/ho me")
        self._check_report(report, "That mount point is invalid. Try something else?")

        report = self.interface.ValidateMountPoint("/home/../")
        self._check_report(report, "That mount point is invalid. Try something else?")

        report = self.interface.ValidateMountPoint("/home/..")
        self._check_report(report, "That mount point is invalid. Try something else?")

        report = self.interface.ValidateMountPoint("/home")
        self._check_report(report, None)

    def add_device_test(self):
        """Test AddDevice."""
        self._add_device(DiskDevice(
            "dev1",
            exists=True,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        ))

        request = DeviceFactoryRequest()
        request.device_type = DEVICE_TYPE_LVM
        request.mount_point = "/home"
        request.size = Size("5 GiB")
        request.disks = ["dev1"]

        self.storage.factory_device = Mock()
        self.interface.AddDevice(DeviceFactoryRequest.to_structure(request))
        self.storage.factory_device.assert_called_once()

    def change_device_test(self):
        """Test ChangeDevice."""
        dev1 = DiskDevice(
            "dev1"
        )
        dev2 = PartitionDevice(
            "dev2",
            size=Size("5 GiB"),
            parents=[dev1],
            fmt=get_format("ext4", mountpoint="/", label="root")
        )

        self._add_device(dev1)
        self._add_device(dev2)

        original_request = self.module.generate_device_factory_request("dev2")
        request = copy.deepcopy(original_request)

        request.device_type = DEVICE_TYPE_LVM
        request.mount_point = "/home"
        request.size = Size("4 GiB")
        request.label = "home"

        self.storage.factory_device = Mock()
        self.interface.ChangeDevice(
            DeviceFactoryRequest.to_structure(request),
            DeviceFactoryRequest.to_structure(original_request)
        )
        self.storage.factory_device.assert_called_once()

    def validate_container_name_test(self):
        """Test ValidateContainerName."""
        report = self.interface.ValidateContainerName("_my/contain$er")
        self._check_report(report, "Invalid container name.")

        report = self.interface.ValidateContainerName("my_container")
        self._check_report(report, None)

    def validate_raid_level_test(self):
        """Test ValidateRaidLevel."""
        report = self.interface.ValidateRaidLevel("raid6", 2)
        self._check_report(report, "The RAID level you have selected (raid6) requires more "
                                   "disks (4) than you currently have selected (2).")

        report = self.interface.ValidateRaidLevel("raid6", 4)
        self._check_report(report, None)

    def generate_device_factory_request_test(self):
        """Test GenerateDeviceFactoryRequest."""
        dev1 = DiskDevice(
            "dev1"
        )
        dev2 = PartitionDevice(
            "dev2",
            size=Size("5 GiB"),
            parents=[dev1],
            fmt=get_format("ext4", mountpoint="/", label="root")
        )

        self._add_device(dev1)
        self._add_device(dev2)

        request = self.interface.GenerateDeviceFactoryRequest("dev2")
        self.assertEqual(get_native(request), {
            'device-spec': 'dev2',
            'disks': ['dev1'],
            'mount-point': '/',
            'reformat': True,
            'format-type': 'ext4',
            'label': 'root',
            'luks-version': '',
            'device-type': DEVICE_TYPE_PARTITION,
            'device-name': 'dev2',
            'device-size': Size("5 GiB").get_bytes(),
            'device-encrypted': False,
            'device-raid-level': '',
            'container-name': '',
            'container-size-policy': SIZE_POLICY_AUTO,
            'container-encrypted': False,
            'container-raid-level': '',
        })

    def get_default_luks_version_test(self):
        """Test GetDefaultLUKSVersion."""
        self.assertEqual(self.interface.GetDefaultLUKSVersion(), "luks2")

    def generate_device_name_test(self):
        """Test GenerateDeviceName."""
        self.assertEqual(self.interface.GenerateDeviceName("/home", "ext4"), "home")

    def get_raw_device_test(self):
        """Test GetRawDevice."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB")
        )
        dev2 = LUKSDevice(
            "dev2",
            parents=[dev1],
            fmt=get_format("luks"),
            size=Size("10 GiB")
        )

        self._add_device(dev1)
        self._add_device(dev2)

        self.assertEqual(self.interface.GetRawDevice("dev1"), "dev1")
        self.assertEqual(self.interface.GetRawDevice("dev2"), "dev1")

    def get_file_systems_for_device_test(self):
        """Test GetFileSystemsForDevice."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))
        result = self.interface.GetFileSystemsForDevice("dev1")

        self.assertIsInstance(result, list)
        self.assertNotEqual(len(result), 0)
        self.assertIn("ext4", result)

        for fs in result:
            self.assertIsInstance(fs, str)
            self.assertEqual(fs, get_format(fs).type)

    def get_device_types_for_device_test(self):
        """Test GetDeviceTypesForDevice."""
        self._add_device(DiskDevice("dev1"))
        self.assertEqual(self.interface.GetDeviceTypesForDevice("dev1"), [
            DEVICE_TYPE_LVM,
            DEVICE_TYPE_MD,
            DEVICE_TYPE_PARTITION,
            DEVICE_TYPE_DISK,
            DEVICE_TYPE_LVM_THINP,
        ])

    def validate_device_factory_request_test(self):
        """Test ValidateDeviceFactoryRequest."""
        dev1 = DiskDevice(
            "dev1"
        )
        dev2 = DiskDevice(
            "dev2"
        )
        dev3 = PartitionDevice(
            "dev3",
            size=Size("10 GiB"),
            parents=[dev1]
        )

        self._add_device(dev1)
        self._add_device(dev2)
        self._add_device(dev3)

        request = self.module.generate_device_factory_request("dev3")
        request.device_type = DEVICE_TYPE_LVM
        request.disks = ["dev1", "dev2"]
        request.format_type = "ext4"
        request.mount_point = "/boot"
        request.label = "root"
        request.reformat = True
        request.luks_version = "luks1"
        request.device_size = Size("5 GiB").get_bytes()
        request.device_encrypted = True
        request.device_raid_level = "raid1"

        result = self.interface.ValidateDeviceFactoryRequest(
            DeviceFactoryRequest.to_structure(request)
        )
        self._check_report(result, "/boot cannot be encrypted")

        request.mount_point = "/"
        result = self.interface.ValidateDeviceFactoryRequest(
            DeviceFactoryRequest.to_structure(request)
        )
        self._check_report(result, None)

    def generate_device_factory_permissions_test(self):
        """Test GenerateDeviceFactoryPermissions."""
        dev1 = DiskDevice(
            "dev1",
            fmt=get_format("disklabel"),
            size=Size("10 GiB"),
            exists=True
        )
        dev2 = PartitionDevice(
            "dev2",
            size=Size("5 GiB"),
            parents=[dev1],
            fmt=get_format("ext4", mountpoint="/", label="root")
        )

        self._add_device(dev1)
        self._add_device(dev2)

        request = self.interface.GenerateDeviceFactoryRequest("dev1")
        permissions = self.interface.GenerateDeviceFactoryPermissions(request)
        self.assertEqual(get_native(permissions), {
            'mount-point': False,
            'reformat': True,
            'format-type': True,
            'label': True,
            'device-type': False,
            'device-name': False,
            'device-size': False,
            'device-encrypted': True,
            'device-raid-level': False,
            'disks': False,
        })

        request = self.interface.GenerateDeviceFactoryRequest("dev2")
        permissions = self.interface.GenerateDeviceFactoryPermissions(request)
        self.assertEqual(get_native(permissions), {
            'mount-point': True,
            'reformat': False,
            'format-type': True,
            'label': True,
            'device-type': True,
            'device-name': False,
            'device-size': True,
            'device-encrypted': True,
            'device-raid-level': True,
            'disks': True,
        })

        dev2.protected = True
        permissions = self.interface.GenerateDeviceFactoryPermissions(request)
        for value in get_native(permissions).values():
            self.assertEqual(value, False)

    def generate_device_factory_permissions_btrfs_test(self):
        """Test GenerateDeviceFactoryPermissions with btrfs."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("btrfs"),
            size=Size("10 GiB")
        )
        dev2 = BTRFSVolumeDevice(
            "dev2",
            size=Size("5 GiB"),
            parents=[dev1]
        )

        self._add_device(dev1)
        self._add_device(dev2)

        request = self.interface.GenerateDeviceFactoryRequest(dev2.name)
        permissions = self.interface.GenerateDeviceFactoryPermissions(request)
        self.assertEqual(get_native(permissions), {
            'mount-point': True,
            'reformat': False,
            'format-type': False,
            'label': True,
            'device-type': True,
            'device-name': False,
            'device-size': False,
            'device-encrypted': False,
            'device-raid-level': True,
            'disks': False,
        })

    @patch_dbus_publish_object
    def schedule_partitions_with_task_test(self, publisher):
        """Test SchedulePartitionsWithTask."""
        self.module.on_storage_changed(Mock())

        request = PartitioningRequest()
        request.partitioning_scheme = AUTOPART_TYPE_PLAIN

        task_path = self.interface.SchedulePartitionsWithTask(
            PartitioningRequest.to_structure(request)
        )

        obj = check_task_creation(self, task_path, publisher, InteractiveAutoPartitioningTask)
        self.assertEqual(obj.implementation._storage, self.module.storage)
        self.assertTrue(compare_data(obj.implementation._request, request))

    def destroy_device_test(self):
        """Test DestroyDevice."""
        dev1 = StorageDevice(
            "dev1",
            exists=False,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        )

        dev2 = StorageDevice(
            "dev2",
            exists=False,
            parents=[dev1],
            size=Size("6 GiB"),
            fmt=get_format("ext4")
        )

        dev3 = StorageDevice(
            "dev3",
            exists=False,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        )

        self.module.on_storage_changed(create_storage())
        self.module.storage.devicetree._add_device(dev1)
        self.module.storage.devicetree._add_device(dev2)
        self.module.storage.devicetree._add_device(dev3)

        with self.assertRaises(StorageConfigurationError):
            self.interface.DestroyDevice("dev1")

        self.assertIn(dev1, self.module.storage.devices)
        self.assertIn(dev2, self.module.storage.devices)
        self.assertIn(dev3, self.module.storage.devices)

        self.interface.DestroyDevice("dev2")

        self.assertNotIn(dev1, self.module.storage.devices)
        self.assertNotIn(dev2, self.module.storage.devices)
        self.assertIn(dev3, self.module.storage.devices)

        self.interface.DestroyDevice("dev3")

        self.assertNotIn(dev1, self.module.storage.devices)
        self.assertNotIn(dev2, self.module.storage.devices)
        self.assertNotIn(dev3, self.module.storage.devices)

    def reset_device_test(self):
        """Test ResetDevice."""
        dev1 = StorageDevice(
            "dev1",
            exists=False,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        )

        dev2 = StorageDevice(
            "dev2",
            exists=False,
            parents=[dev1],
            size=Size("6 GiB"),
            fmt=get_format("ext4")
        )

        dev3 = StorageDevice(
            "dev3",
            exists=True,
            size=Size("6 GiB")
        )

        dev3.original_format = get_format("ext4")
        dev3.format = get_format("xfs")

        self.module.on_storage_changed(create_storage())
        self.module.storage.devicetree._add_device(dev1)
        self.module.storage.devicetree._add_device(dev2)
        self.module.storage.devicetree._add_device(dev3)

        with self.assertRaises(StorageConfigurationError):
            self.interface.ResetDevice("dev1")

        self.assertIn(dev1, self.module.storage.devices)
        self.assertIn(dev2, self.module.storage.devices)
        self.assertIn(dev3, self.module.storage.devices)
        self.assertEqual(dev3.format.type, "xfs")

        self.interface.ResetDevice("dev2")

        self.assertNotIn(dev1, self.module.storage.devices)
        self.assertNotIn(dev2, self.module.storage.devices)
        self.assertIn(dev3, self.module.storage.devices)
        self.assertEqual(dev3.format.type, "xfs")

        self.interface.ResetDevice("dev3")

        self.assertNotIn(dev1, self.module.storage.devices)
        self.assertNotIn(dev2, self.module.storage.devices)
        self.assertIn(dev3, self.module.storage.devices)
        self.assertEqual(dev3.format.type, "ext4")
