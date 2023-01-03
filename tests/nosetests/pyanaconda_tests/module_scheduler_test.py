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
    DEVICE_TYPE_LVM_THINP, DEVICE_TYPE_DISK, DEVICE_TYPE_MD, DEVICE_TYPE_BTRFS
from blivet.devices import StorageDevice, DiskDevice, PartitionDevice, LUKSDevice, \
    BTRFSVolumeDevice, MDRaidArrayDevice, LVMVolumeGroupDevice, LVMLogicalVolumeDevice
from blivet.errors import StorageError
from blivet.formats import get_format
from blivet.formats.fs import FS, BTRFS
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
from pyanaconda.modules.storage.platform import EFI
from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.modules.storage.devicetree.root import Root
from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation, \
    patch_dbus_get_proxy


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
            'os-name': 'New anaconda bluesky Installation',
            'devices': ['dev1', 'dev2', 'dev3'],
            'mount-points': {'/boot': 'dev1', '/': 'dev2'},
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
            devices=[dev2, dev3],
            mounts={"/": dev2},
        )]

        os_data_list = self.interface.CollectSupportedSystems()
        self.assertEqual(get_native(os_data_list), [{
            'os-name': 'My Linux',
            'devices': ['dev2', 'dev3'],
            'mount-points': {'/': 'dev2'},
        }])

    def get_default_file_system_test(self):
        """Test GetDefaultFileSystem."""
        self.assertEqual(self.interface.GetDefaultFileSystem(), "ext4")

    def get_supported_raid_levels_test(self):
        """Test GetSupportedRaidLevels."""
        self.assertEqual(
            self.interface.GetSupportedRaidLevels(DEVICE_TYPE_LVM),
            ['linear', 'raid0', 'raid1', 'raid10', 'raid4', 'raid5', 'raid6', 'striped']
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
        dev1 = DiskDevice(
            "dev1"
        )
        self._add_device(dev1)

        report = self.interface.ValidateContainerName("dev1")
        self._check_report(report, "Name is already in use.")

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
            'container-spec': '',
            'container-name': '',
            'container-size-policy': SIZE_POLICY_AUTO,
            'container-encrypted': False,
            'container-raid-level': '',
        })

    def reset_device_factory_request_test(self):
        """Test reset_container_data."""
        default = DeviceFactoryRequest()
        request = DeviceFactoryRequest()

        request.container_spec = "dev1"
        request.container_name = "dev1"
        request.container_size_policy = 123
        request.container_encrypted = True
        request.container_raid_level = "raid1"
        request.reset_container_data()

        self.assertEqual(compare_data(request, default), True)

    def get_default_luks_version_test(self):
        """Test GetDefaultLUKSVersion."""
        self.assertEqual(self.interface.GetDefaultLUKSVersion(), "luks2")

    def generate_device_name_test(self):
        """Test GenerateDeviceName."""
        self.assertEqual(self.interface.GenerateDeviceName("/home", "ext4"), "home")

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
            'label': False,
            'device-type': False,
            'device-name': False,
            'device-size': False,
            'device-encrypted': True,
            'device-raid-level': False,
            'disks': False,
            'container-spec': False,
            'container-name': False,
            'container-size-policy': False,
            'container-encrypted': False,
            'container-raid-level': False,
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
            'container-spec': False,
            'container-name': False,
            'container-size-policy': False,
            'container-encrypted': False,
            'container-raid-level': False,
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

        # Make the btrfs format not mountable.
        with patch.object(BTRFS, "_mount_class", return_value=Mock(available=False)):
            request = self.interface.GenerateDeviceFactoryRequest(dev2.name)
            permissions = self.interface.GenerateDeviceFactoryPermissions(request)

        self.assertEqual(get_native(permissions), {
            'mount-point': False,
            'reformat': False,
            'format-type': False,
            'label': False,
            'device-type': True,
            'device-name': False,
            'device-size': False,
            'device-encrypted': False,
            'device-raid-level': True,
            'disks': False,
            'container-spec': False,
            'container-name': True,
            'container-size-policy': True,
            'container-encrypted': True,
            'container-raid-level': True,
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

    def is_device_locked_test(self):
        """Test IsDeviceLocked."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB")
        )
        dev2 = LUKSDevice(
            "dev2",
            parents=[dev1],
            fmt=get_format("luks"),
            size=Size("10 GiB"),
        )
        dev3 = LUKSDevice(
            "dev3",
            parents=[dev1],
            fmt=get_format("luks", exists=True),
            size=Size("10 GiB"),
        )

        self._add_device(dev1)
        self._add_device(dev2)
        self._add_device(dev3)

        self.assertEqual(self.interface.IsDeviceLocked("dev1"), False)
        self.assertEqual(self.interface.IsDeviceLocked("dev2"), False)
        self.assertEqual(self.interface.IsDeviceLocked("dev3"), True)

    def check_completeness_test(self):
        """Test CheckCompleteness."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB"),
            exists=True
        )
        dev2 = MDRaidArrayDevice(
            name="dev2",
            size=Size("500 MiB"),
            level=1,
            member_devices=2,
            total_devices=2,
            exists=True
        )
        dev3 = LVMVolumeGroupDevice(
            "dev3",
            pv_count=2,
            exists=True
        )

        self._add_device(dev1)
        self._add_device(dev2)
        self._add_device(dev3)

        self._check_report(
            self.interface.CheckCompleteness("dev1")
        )
        self._check_report(
            self.interface.CheckCompleteness("dev2"),
            "This Software RAID array is missing 2 of 2 member partitions. "
            "You can remove it or select a different device."
        )
        self._check_report(
            self.interface.CheckCompleteness("dev3"),
            "This LVM Volume Group is missing 2 of 2 physical volumes. "
            "You can remove it or select a different device."
        )
        dev1.complete = False
        self._check_report(
            self.interface.CheckCompleteness("dev1"),
            "This blivet device is missing member devices. "
            "You can remove it or select a different device."
        )

    def is_device_editable_test(self):
        """Test IsDeviceEditable."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB")
        )
        dev2 = DiskDevice(
            "dev2",
            fmt=get_format("disklabel"),
            size=Size("10 GiB")
        )

        self._add_device(dev1)
        self._add_device(dev2)

        self.assertEqual(self.interface.IsDeviceEditable("dev1"), False)
        self.assertEqual(self.interface.IsDeviceEditable("dev2"), True)

    def collect_containers_test(self):
        """Test CollectContainers."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("btrfs"),
            size=Size("10 GiB")
        )
        dev2 = BTRFSVolumeDevice(
            "dev2",
            parents=[dev1]
        )

        self._add_device(dev1)
        self._add_device(dev2)

        self.assertEqual(self.interface.CollectContainers(DEVICE_TYPE_BTRFS), [dev2.name])
        self.assertEqual(self.interface.CollectContainers(DEVICE_TYPE_LVM), [])

    def get_container_free_space_test(self):
        """Test GetContainerFreeSpace."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("lvmpv"),
            size=Size("10 GiB")
        )
        dev2 = LVMVolumeGroupDevice(
            "dev2",
            parents=[dev1]
        )

        self._add_device(dev1)
        self._add_device(dev2)

        free_space = self.interface.GetContainerFreeSpace("dev1")
        self.assertEqual(free_space, 0)

        free_space = self.interface.GetContainerFreeSpace("dev2")
        self.assertGreater(free_space, Size("9 GiB").get_bytes())
        self.assertLess(free_space, Size("10 GiB").get_bytes())

        dev2.reserved_percent = 110
        free_space = self.interface.GetContainerFreeSpace("dev2")
        self.assertEqual(free_space, Size("0 GiB").get_bytes())

    @patch_dbus_get_proxy
    def generate_container_name_test(self, proxy_getter):
        """Test GenerateContainerName."""
        network_proxy = Mock()
        proxy_getter.return_value = network_proxy

        network_proxy.Hostname = "localhost"
        network_proxy.GetCurrentHostname.return_value = "localhost"
        self.assertEqual(self.interface.GenerateContainerName(), "anaconda")

        network_proxy.GetCurrentHostname.return_value = "hostname"
        self.assertEqual(self.interface.GenerateContainerName(), "anaconda_hostname")

        network_proxy.Hostname = "best.hostname"
        self.assertEqual(self.interface.GenerateContainerName(), "anaconda_best")

    @patch_dbus_get_proxy
    def generate_container_data_test(self, proxy_getter):
        """Test GenerateContainerData."""
        network_proxy = Mock()
        network_proxy.Hostname = "localhost"
        network_proxy.GetCurrentHostname.return_value = "localhost"
        proxy_getter.return_value = network_proxy

        pv1 = StorageDevice(
            "pv1",
            size=Size("1025 MiB"),
            fmt=get_format("lvmpv")
        )
        pv2 = StorageDevice(
            "pv2",
            size=Size("513 MiB"),
            fmt=get_format("lvmpv")
        )
        vg = LVMVolumeGroupDevice(
            "testvg",
            parents=[pv1, pv2]
        )
        lv = LVMLogicalVolumeDevice(
            "testlv",
            size=Size("512 MiB"),
            parents=[vg],
            fmt=get_format("xfs"),
            exists=False,
            seg_type="raid1",
            pvs=[pv1, pv2]
        )

        self._add_device(pv1)
        self._add_device(pv2)
        self._add_device(vg)
        self._add_device(lv)

        request = DeviceFactoryRequest()
        request.device_spec = lv.name

        request.device_type = DEVICE_TYPE_LVM
        request = DeviceFactoryRequest.from_structure(
            self.interface.GenerateContainerData(
                DeviceFactoryRequest.to_structure(request)
            )
        )

        self.assertEqual(request.container_spec, "testvg")
        self.assertEqual(request.container_name, "testvg")
        self.assertEqual(request.container_encrypted, False)
        self.assertEqual(request.container_raid_level, "")
        self.assertEqual(request.container_size_policy, Size("1.5 GiB").get_bytes())

        request.device_type = DEVICE_TYPE_BTRFS
        request = DeviceFactoryRequest.from_structure(
            self.interface.GenerateContainerData(
                DeviceFactoryRequest.to_structure(request)
            )
        )

        self.assertEqual(request.container_spec, "")
        self.assertEqual(request.container_name, "anaconda")
        self.assertEqual(request.container_encrypted, False)
        self.assertEqual(request.container_raid_level, "single")
        self.assertEqual(request.container_size_policy, 0)

        request.device_type = DEVICE_TYPE_PARTITION
        request = DeviceFactoryRequest.from_structure(
            self.interface.GenerateContainerData(
                DeviceFactoryRequest.to_structure(request)
            )
        )

        self.assertEqual(request.container_spec, "")
        self.assertEqual(request.container_name, "")
        self.assertEqual(request.container_encrypted, False)
        self.assertEqual(request.container_raid_level, "")
        self.assertEqual(request.container_size_policy, 0)

    def update_container_data_test(self):
        """Test UpdateContainerData."""
        pv1 = StorageDevice(
            "pv1",
            size=Size("1025 MiB"),
            fmt=get_format("lvmpv")
        )
        pv2 = StorageDevice(
            "pv2",
            size=Size("513 MiB"),
            fmt=get_format("lvmpv")
        )
        vg = LVMVolumeGroupDevice(
            "testvg",
            parents=[pv1, pv2]
        )

        self._add_device(pv1)
        self._add_device(pv2)
        self._add_device(vg)

        request = DeviceFactoryRequest()
        request.device_type = DEVICE_TYPE_PARTITION

        with self.assertRaises(StorageError):
            self.interface.UpdateContainerData(
                    DeviceFactoryRequest.to_structure(request),
                    "anaconda"
            )

        request.device_type = DEVICE_TYPE_BTRFS
        request = DeviceFactoryRequest.from_structure(
            self.interface.UpdateContainerData(
                DeviceFactoryRequest.to_structure(request),
                "anaconda"
            )
        )

        self.assertEqual(request.container_spec, "")
        self.assertEqual(request.container_name, "anaconda")
        self.assertEqual(request.container_encrypted, False)
        self.assertEqual(request.container_raid_level, "single")
        self.assertEqual(request.container_size_policy, 0)
        self.assertEqual(request.disks, [])

        request.device_type = DEVICE_TYPE_LVM
        request = DeviceFactoryRequest.from_structure(
            self.interface.UpdateContainerData(
                DeviceFactoryRequest.to_structure(request),
                "testvg"
            )
        )

        self.assertEqual(request.container_spec, "testvg")
        self.assertEqual(request.container_name, "testvg")
        self.assertEqual(request.container_encrypted, False)
        self.assertEqual(request.container_raid_level, "")
        self.assertEqual(request.container_size_policy, Size("1.5 GiB").get_bytes())
        self.assertEqual(request.disks, [])

    def is_device_test(self):
        """Test IsDevice."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB"),
            exists=True
        )

        self.assertEqual(self.interface.IsDevice("dev1"), False)

        self._add_device(dev1)
        self.assertEqual(self.interface.IsDevice("dev1"), True)

        dev1.complete = False
        self.assertEqual(self.interface.IsDevice("dev1"), True)

        self.storage.devicetree.hide(dev1)
        self.assertEqual(self.interface.IsDevice("dev1"), True)
