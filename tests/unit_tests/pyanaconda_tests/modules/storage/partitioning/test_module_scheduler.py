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
import copy
import unittest
from unittest.mock import Mock, patch

import pytest
from blivet.devicefactory import (
    SIZE_POLICY_AUTO,
)
from blivet.devices import (
    BTRFSVolumeDevice,
    DiskDevice,
    LUKSDevice,
    LVMLogicalVolumeDevice,
    LVMVolumeGroupDevice,
    MDRaidArrayDevice,
    PartitionDevice,
    StorageDevice,
)
from blivet.errors import StorageError
from blivet.formats import get_format
from blivet.formats.fs import BTRFS, FS
from blivet.size import Size
from dasbus.structure import compare_data
from dasbus.typing import get_native
from pykickstart.constants import AUTOPART_TYPE_PLAIN

from pyanaconda.core.storage import DEVICE_TYPES
from pyanaconda.modules.common.errors.configuration import StorageConfigurationError
from pyanaconda.modules.common.structures.device_factory import DeviceFactoryRequest
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.modules.storage.devicetree.root import Root
from pyanaconda.modules.storage.partitioning.interactive.interactive_partitioning import (
    InteractiveAutoPartitioningTask,
)
from pyanaconda.modules.storage.partitioning.interactive.scheduler_interface import (
    DeviceTreeSchedulerInterface,
)
from pyanaconda.modules.storage.partitioning.interactive.scheduler_module import (
    DeviceTreeSchedulerModule,
)
from pyanaconda.modules.storage.platform import EFI
from tests.unit_tests.pyanaconda_tests import (
    check_task_creation,
    patch_dbus_get_proxy,
    patch_dbus_publish_object,
)


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

    def test_publication(self):
        """Test the DBus representation."""
        assert isinstance(self.module.for_publication(), DeviceTreeSchedulerInterface)

    def test_generate_system_name(self):
        """Test GenerateSystemName."""
        assert self.interface.GenerateSystemName() == \
            "New anaconda bluesky Installation"

    def test_generate_system_data(self):
        """Test GenerateSystemData."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/boot")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev3", fmt=get_format("swap")))

        os_data = self.interface.GenerateSystemData("dev1")
        assert get_native(os_data) == {
            'os-name': 'New anaconda bluesky Installation',
            'devices': ['dev1', 'dev2', 'dev3'],
            'mount-points': {'/boot': 'dev1', '/': 'dev2'},
        }

    def test_collect_new_devices(self):
        """Test CollectNewDevices."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/boot")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev3", fmt=get_format("swap")))
        assert self.interface.CollectNewDevices("dev1") == ["dev1", "dev2", "dev3"]

    def test_collect_unused_devices(self):
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

        assert self.interface.CollectUnusedDevices() == ["dev2", "dev3"]

    @patch.object(FS, "update_size_info")
    def test_collect_supported_systems(self, update_size_info):
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
        assert get_native(os_data_list) == [{
            'os-name': 'My Linux',
            'devices': ['dev2', 'dev3'],
            'mount-points': {'/': 'dev2'},
        }]

    def test_get_default_file_system(self):
        """Test GetDefaultFileSystem."""
        assert self.interface.GetDefaultFileSystem() == "ext4"

    def test_get_supported_raid_levels(self):
        """Test GetSupportedRaidLevels."""
        assert self.interface.GetSupportedRaidLevels(DEVICE_TYPES.MD) == \
            ['linear', 'raid0', 'raid1', 'raid10', 'raid4', 'raid5', 'raid6']

    @patch('pyanaconda.modules.storage.partitioning.interactive.utils.get_format')
    @patch('pyanaconda.modules.storage.partitioning.interactive.utils.platform', new_callable=EFI)
    def test_collect_unused_mount_points(self, platform, format_getter):
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
        assert self.interface.CollectUnusedMountPoints() == [
            '/boot/efi', '/home', '/var', 'swap', 'biosboot'
        ]

    def _check_report(self, report, error_message=None):
        """Check the given validation report."""
        errors = [error_message] if error_message else []
        warnings = []

        assert get_native(report) == {
            "error-messages": errors,
            "warning-messages": warnings
        }

    def test_validate_mount_point(self):
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

    def test_add_device(self):
        """Test AddDevice."""
        self._add_device(DiskDevice(
            "dev1",
            exists=True,
            size=Size("15 GiB"),
            fmt=get_format("disklabel")
        ))

        request = DeviceFactoryRequest()
        request.device_type = DEVICE_TYPES.LVM
        request.mount_point = "/home"
        request.size = Size("5 GiB")
        request.disks = ["dev1"]

        self.storage.factory_device = Mock()
        self.interface.AddDevice(DeviceFactoryRequest.to_structure(request))
        self.storage.factory_device.assert_called_once()

    def test_change_device(self):
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

        request.device_type = DEVICE_TYPES.LVM
        request.mount_point = "/home"
        request.size = Size("4 GiB")
        request.label = "home"

        self.storage.factory_device = Mock()
        self.interface.ChangeDevice(
            DeviceFactoryRequest.to_structure(request),
            DeviceFactoryRequest.to_structure(original_request)
        )
        self.storage.factory_device.assert_called_once()

    def test_validate_container_name(self):
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

    def test_validate_raid_level(self):
        """Test ValidateRaidLevel."""
        report = self.interface.ValidateRaidLevel("raid6", 2)
        self._check_report(report, "The RAID level you have selected (raid6) requires more "
                                   "disks (4) than you currently have selected (2).")

        report = self.interface.ValidateRaidLevel("raid6", 4)
        self._check_report(report, None)

    def test_generate_device_factory_request(self):
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
        assert get_native(request) == {
            'device-spec': 'dev2',
            'disks': ['dev1'],
            'mount-point': '/',
            'reformat': True,
            'format-type': 'ext4',
            'label': 'root',
            'luks-version': '',
            'device-type': DEVICE_TYPES.PARTITION,
            'device-name': 'dev2',
            'device-size': Size("5 GiB").get_bytes(),
            'device-encrypted': False,
            'device-raid-level': '',
            'container-spec': '',
            'container-name': '',
            'container-size-policy': SIZE_POLICY_AUTO,
            'container-encrypted': False,
            'container-raid-level': '',
        }

    def test_reset_device_factory_request(self):
        """Test reset_container_data."""
        default = DeviceFactoryRequest()
        request = DeviceFactoryRequest()

        request.container_spec = "dev1"
        request.container_name = "dev1"
        request.container_size_policy = 123
        request.container_encrypted = True
        request.container_raid_level = "raid1"
        request.reset_container_data()

        assert compare_data(request, default) is True

    def test_get_default_luks_version(self):
        """Test GetDefaultLUKSVersion."""
        assert self.interface.GetDefaultLUKSVersion() == "luks2"

    def test_generate_device_name(self):
        """Test GenerateDeviceName."""
        assert self.interface.GenerateDeviceName("/home", "ext4") == "home"

    def test_get_file_systems_for_device(self):
        """Test GetFileSystemsForDevice."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))
        result = self.interface.GetFileSystemsForDevice("dev1")

        assert isinstance(result, list)
        assert len(result) != 0
        assert "ext4" in result

        for fs in result:
            assert isinstance(fs, str)
            assert fs == get_format(fs).type

    def test_get_device_types_for_device(self):
        """Test GetDeviceTypesForDevice."""
        self._add_device(DiskDevice("dev1"))
        assert self.interface.GetDeviceTypesForDevice("dev1") == [
            DEVICE_TYPES.LVM,
            DEVICE_TYPES.MD,
            DEVICE_TYPES.PARTITION,
            DEVICE_TYPES.DISK,
            DEVICE_TYPES.LVM_THINP,
        ]

    def test_validate_device_factory_request(self):
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
        request.device_type = DEVICE_TYPES.LVM
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

    def test_generate_device_factory_permissions(self):
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
        assert get_native(permissions) == {
            'mount-point': False,
            'reformat': False,
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
        }

        request = self.interface.GenerateDeviceFactoryRequest("dev2")
        permissions = self.interface.GenerateDeviceFactoryPermissions(request)
        assert get_native(permissions) == {
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
        }

        dev2.protected = True
        permissions = self.interface.GenerateDeviceFactoryPermissions(request)
        for value in get_native(permissions).values():
            assert value is False

    def test_generate_device_factory_permissions_btrfs(self):
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

        assert get_native(permissions) == {
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
        }

    @patch_dbus_publish_object
    def test_schedule_partitions_with_task(self, publisher):
        """Test SchedulePartitionsWithTask."""
        self.module.on_storage_changed(Mock())

        request = PartitioningRequest()
        request.partitioning_scheme = AUTOPART_TYPE_PLAIN

        task_path = self.interface.SchedulePartitionsWithTask(
            PartitioningRequest.to_structure(request)
        )

        obj = check_task_creation(task_path, publisher, InteractiveAutoPartitioningTask)
        assert obj.implementation._storage == self.module.storage
        assert compare_data(obj.implementation._request, request)

    def test_destroy_device(self):
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

        with pytest.raises(StorageConfigurationError):
            self.interface.DestroyDevice("dev1")

        assert dev1 in self.module.storage.devices
        assert dev2 in self.module.storage.devices
        assert dev3 in self.module.storage.devices

        self.interface.DestroyDevice("dev2")

        assert dev1 not in self.module.storage.devices
        assert dev2 not in self.module.storage.devices
        assert dev3 in self.module.storage.devices

        self.interface.DestroyDevice("dev3")

        assert dev1 not in self.module.storage.devices
        assert dev2 not in self.module.storage.devices
        assert dev3 not in self.module.storage.devices

    def test_reset_device(self):
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

        with pytest.raises(StorageConfigurationError):
            self.interface.ResetDevice("dev1")

        assert dev1 in self.module.storage.devices
        assert dev2 in self.module.storage.devices
        assert dev3 in self.module.storage.devices
        assert dev3.format.type == "xfs"

        self.interface.ResetDevice("dev2")

        assert dev1 not in self.module.storage.devices
        assert dev2 not in self.module.storage.devices
        assert dev3 in self.module.storage.devices
        assert dev3.format.type == "xfs"

        self.interface.ResetDevice("dev3")

        assert dev1 not in self.module.storage.devices
        assert dev2 not in self.module.storage.devices
        assert dev3 in self.module.storage.devices
        assert dev3.format.type == "ext4"

    def test_is_device_locked(self):
        """Test IsDeviceLocked."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("luks"),
            size=Size("10 GiB")
        )
        dev2 = LUKSDevice(
            "dev2",
            parents=[dev1],
            fmt=get_format("ext4"),
            size=Size("10 GiB"),
        )
        dev3 = StorageDevice(
            "dev3",
            parents=[dev1],
            fmt=get_format("luks", exists=True),
            size=Size("10 GiB"),
        )

        self._add_device(dev1)
        self._add_device(dev2)
        self._add_device(dev3)

        assert self.interface.IsDeviceLocked("dev1") is False
        assert self.interface.IsDeviceLocked("dev2") is False
        assert self.interface.IsDeviceLocked("dev3") is True

    def test_check_completeness(self):
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

    def test_is_device_editable(self):
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

        assert self.interface.IsDeviceEditable("dev1") is False
        assert self.interface.IsDeviceEditable("dev2") is True

    def test_collect_containers(self):
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

        assert self.interface.CollectContainers(DEVICE_TYPES.BTRFS) == [dev2.name]
        assert self.interface.CollectContainers(DEVICE_TYPES.LVM) == []

    def test_get_container_free_space(self):
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
        assert free_space == 0

        free_space = self.interface.GetContainerFreeSpace("dev2")
        assert free_space > Size("9 GiB").get_bytes()
        assert free_space < Size("10 GiB").get_bytes()

    @patch_dbus_get_proxy
    def test_generate_container_name(self, proxy_getter):
        """Test GenerateContainerName."""
        network_proxy = Mock()
        proxy_getter.return_value = network_proxy

        network_proxy.Hostname = "localhost"
        network_proxy.GetCurrentHostname.return_value = "localhost"
        assert self.interface.GenerateContainerName() == "anaconda"

        network_proxy.GetCurrentHostname.return_value = "hostname"
        assert self.interface.GenerateContainerName() == "anaconda_hostname"

        network_proxy.Hostname = "best.hostname"
        assert self.interface.GenerateContainerName() == "anaconda_best"

    @patch_dbus_get_proxy
    def test_generate_container_data(self, proxy_getter):
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

        request.device_type = DEVICE_TYPES.LVM
        request = DeviceFactoryRequest.from_structure(
            self.interface.GenerateContainerData(
                DeviceFactoryRequest.to_structure(request)
            )
        )

        assert request.container_spec == "testvg"
        assert request.container_name == "testvg"
        assert request.container_encrypted is False
        assert request.container_raid_level == ""
        assert request.container_size_policy == Size("1.5 GiB").get_bytes()

        request.device_type = DEVICE_TYPES.BTRFS
        request = DeviceFactoryRequest.from_structure(
            self.interface.GenerateContainerData(
                DeviceFactoryRequest.to_structure(request)
            )
        )

        assert request.container_spec == ""
        assert request.container_name == "anaconda"
        assert request.container_encrypted is False
        assert request.container_raid_level == "single"
        assert request.container_size_policy == 0

        request.device_type = DEVICE_TYPES.PARTITION
        request = DeviceFactoryRequest.from_structure(
            self.interface.GenerateContainerData(
                DeviceFactoryRequest.to_structure(request)
            )
        )

        assert request.container_spec == ""
        assert request.container_name == ""
        assert request.container_encrypted is False
        assert request.container_raid_level == ""
        assert request.container_size_policy == 0

    def test_update_container_data(self):
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
        request.device_type = DEVICE_TYPES.PARTITION

        with pytest.raises(StorageError):
            self.interface.UpdateContainerData(
                    DeviceFactoryRequest.to_structure(request),
                    "anaconda"
            )

        request.device_type = DEVICE_TYPES.BTRFS
        request = DeviceFactoryRequest.from_structure(
            self.interface.UpdateContainerData(
                DeviceFactoryRequest.to_structure(request),
                "anaconda"
            )
        )

        assert request.container_spec == ""
        assert request.container_name == "anaconda"
        assert request.container_encrypted is False
        assert request.container_raid_level == "single"
        assert request.container_size_policy == 0
        assert request.disks == []

        request.device_type = DEVICE_TYPES.LVM
        request = DeviceFactoryRequest.from_structure(
            self.interface.UpdateContainerData(
                DeviceFactoryRequest.to_structure(request),
                "testvg"
            )
        )

        assert request.container_spec == "testvg"
        assert request.container_name == "testvg"
        assert request.container_encrypted is False
        assert request.container_raid_level == ""
        assert request.container_size_policy == Size("1.5 GiB").get_bytes()
        assert request.disks == []

    def test_is_device(self):
        """Test IsDevice."""
        dev1 = StorageDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB"),
            exists=True
        )

        assert self.interface.IsDevice("dev1") is False

        self._add_device(dev1)
        assert self.interface.IsDevice("dev1") is True

        dev1.complete = False
        assert self.interface.IsDevice("dev1") is True

        self.storage.devicetree.hide(dev1)
        assert self.interface.IsDevice("dev1") is True
