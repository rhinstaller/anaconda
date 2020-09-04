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
from unittest.mock import patch

from blivet import devicefactory
from blivet.devicelibs import raid
from blivet.devices import StorageDevice, DiskDevice, PartitionDevice, LVMVolumeGroupDevice, \
    LVMLogicalVolumeDevice
from blivet.formats import get_format
from blivet.size import Size

from pyanaconda.core.constants import PARTITIONING_METHOD_INTERACTIVE
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.containers import DeviceTreeContainer
from pyanaconda.modules.common.errors.storage import UnsupportedDeviceError
from pyanaconda.modules.common.structures.device_factory import DeviceFactoryRequest
from pyanaconda.modules.storage.devicetree.devicetree_interface import DeviceTreeInterface
from pyanaconda.modules.storage.partitioning.interactive.interactive_module import \
    InteractivePartitioningModule
from pyanaconda.modules.storage.partitioning.interactive import utils
from pyanaconda.modules.storage.partitioning.interactive.interactive_interface import \
    InteractivePartitioningInterface
from pyanaconda.modules.storage.partitioning.interactive.interactive_partitioning import \
    InteractivePartitioningTask
from pyanaconda.modules.storage.partitioning.interactive.scheduler_module import \
    DeviceTreeSchedulerModule
from pyanaconda.modules.storage.devicetree import create_storage

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation, \
    check_dbus_object_creation


class InteractivePartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the interactive partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = InteractivePartitioningModule()
        self.interface = InteractivePartitioningInterface(self.module)

    def publication_test(self):
        """Test the DBus representation."""
        self.assertIsInstance(self.module.for_publication(), InteractivePartitioningInterface)

    @patch_dbus_publish_object
    def device_tree_test(self, publisher):
        """Test the device tree."""
        self.module.on_storage_changed(create_storage())
        path = self.interface.GetDeviceTree()
        check_dbus_object_creation(self, path, publisher, DeviceTreeSchedulerModule)

    def method_property_test(self):
        """Test Method property."""
        self.assertEqual(self.interface.PartitioningMethod, PARTITIONING_METHOD_INTERACTIVE)

    @patch_dbus_publish_object
    def lazy_storage_test(self, publisher):
        """Make sure that the storage playground is created lazily."""
        self.module.on_storage_changed(create_storage())

        device_tree_module = self.module.get_device_tree()
        self.assertIsNone(self.module._storage_playground)

        device_tree_module.get_disks()
        self.assertIsNotNone(self.module._storage_playground)

        self.module.on_partitioning_reset()
        self.module.on_storage_changed(create_storage())
        self.assertIsNone(self.module._storage_playground)

        device_tree_module.get_actions()
        self.assertIsNotNone(self.module._storage_playground)

    @patch_dbus_publish_object
    def get_device_tree_test(self, publisher):
        """Test GetDeviceTree."""
        DeviceTreeContainer._counter = 0
        self.module.on_storage_changed(create_storage())

        tree_path = self.interface.GetDeviceTree()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(tree_path, object_path)
        self.assertIsInstance(obj, DeviceTreeInterface)

        self.assertEqual(obj.implementation, self.module._device_tree_module)
        self.assertEqual(obj.implementation.storage, self.module.storage)
        self.assertTrue(tree_path.endswith("/DeviceTree/1"))

        publisher.reset_mock()

        self.assertEqual(tree_path, self.interface.GetDeviceTree())
        self.assertEqual(tree_path, self.interface.GetDeviceTree())
        self.assertEqual(tree_path, self.interface.GetDeviceTree())

        publisher.assert_not_called()

    @patch_dbus_publish_object
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_changed(create_storage())
        task_path = self.interface.ConfigureWithTask()

        obj = check_task_creation(self, task_path, publisher, InteractivePartitioningTask)

        self.assertEqual(obj.implementation._storage, self.module.storage)


class InteractiveUtilsTestCase(unittest.TestCase):
    """Test utilities for the interactive partitioning."""

    def setUp(self):
        self.maxDiff = None
        self.storage = create_storage()

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.storage.devicetree._add_device(device)

    @patch("blivet.devices.dm.blockdev")
    def generate_device_factory_request_test(self, blockdev):
        device = StorageDevice("dev1")
        with self.assertRaises(UnsupportedDeviceError):
            utils.generate_device_factory_request(self.storage, device)

        disk = DiskDevice("dev2")

        request = utils.generate_device_factory_request(self.storage, disk)
        self.assertEqual(DeviceFactoryRequest.to_structure(request), {
            "device-spec": get_variant(Str, "dev2"),
            "disks": get_variant(List[Str], ["dev2"]),
            "mount-point": get_variant(Str, ""),
            "reformat": get_variant(Bool, False),
            "format-type": get_variant(Str, ""),
            "label": get_variant(Str, ""),
            "luks-version": get_variant(Str, ""),
            "device-type": get_variant(Int, devicefactory.DEVICE_TYPE_DISK),
            "device-name": get_variant(Str, "dev2"),
            "device-size": get_variant(UInt64, 0),
            "device-encrypted": get_variant(Bool, False),
            "device-raid-level": get_variant(Str, ""),
            "container-spec": get_variant(Str, ""),
            "container-name": get_variant(Str, ""),
            "container-size-policy": get_variant(Int64, devicefactory.SIZE_POLICY_AUTO),
            "container-encrypted": get_variant(Bool, False),
            "container-raid-level": get_variant(Str, ""),
        })

        partition = PartitionDevice(
            "dev3",
            size=Size("5 GiB"),
            parents=[disk],
            fmt=get_format("ext4", mountpoint="/", label="root")
        )

        request = utils.generate_device_factory_request(self.storage, partition)
        self.assertEqual(DeviceFactoryRequest.to_structure(request), {
            "device-spec": get_variant(Str, "dev3"),
            "disks": get_variant(List[Str], ["dev2"]),
            "mount-point": get_variant(Str, "/"),
            "reformat": get_variant(Bool, True),
            "format-type": get_variant(Str, "ext4"),
            "label": get_variant(Str, "root"),
            "luks-version": get_variant(Str, ""),
            "device-type": get_variant(Int, devicefactory.DEVICE_TYPE_PARTITION),
            "device-name": get_variant(Str, "dev3"),
            "device-size": get_variant(UInt64, Size("5 GiB").get_bytes()),
            "device-encrypted": get_variant(Bool, False),
            "device-raid-level": get_variant(Str, ""),
            "container-spec": get_variant(Str, ""),
            "container-name": get_variant(Str, ""),
            "container-size-policy": get_variant(Int64, devicefactory.SIZE_POLICY_AUTO),
            "container-encrypted": get_variant(Bool, False),
            "container-raid-level": get_variant(Str, ""),
        })

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

        request = utils.generate_device_factory_request(self.storage, lv)
        self.assertEqual(DeviceFactoryRequest.to_structure(request), {
            "device-spec": get_variant(Str, "testvg-testlv"),
            "disks": get_variant(List[Str], []),
            "mount-point": get_variant(Str, ""),
            "reformat": get_variant(Bool, True),
            "format-type": get_variant(Str, "xfs"),
            "label": get_variant(Str, ""),
            "luks-version": get_variant(Str, ""),
            "device-type": get_variant(Int, devicefactory.DEVICE_TYPE_LVM),
            "device-name": get_variant(Str, "testlv"),
            "device-size": get_variant(UInt64, Size("508 MiB").get_bytes()),
            "device-encrypted": get_variant(Bool, False),
            "device-raid-level": get_variant(Str, ""),
            "container-spec": get_variant(Str, "testvg"),
            "container-name": get_variant(Str, "testvg"),
            "container-size-policy": get_variant(Int64, Size("1.5 GiB")),
            "container-encrypted": get_variant(Bool, False),
            "container-raid-level": get_variant(Str, ""),
        })

    def get_device_factory_arguments_test(self):
        """Test get_device_factory_arguments."""
        dev1 = StorageDevice("dev1")
        self._add_device(dev1)

        dev2 = StorageDevice("dev2")
        self._add_device(dev2)

        dev3 = StorageDevice("dev3")
        self._add_device(dev3)

        request = DeviceFactoryRequest()
        request.device_spec = "dev3"
        request.disks = ["dev1", "dev2"]
        request.device_name = "dev3"
        request.device_type = devicefactory.DEVICE_TYPE_LVM_THINP
        request.device_size = Size("10 GiB").get_bytes()
        request.mount_point = "/"
        request.format_type = "xfs"
        request.label = "root"
        request.device_encrypted = True
        request.luks_version = "luks1"
        request.device_raid_level = "raid1"

        self.assertEqual(utils.get_device_factory_arguments(self.storage, request), {
            "device": dev3,
            "disks": [dev1, dev2],
            "device_type": devicefactory.DEVICE_TYPE_LVM_THINP,
            "device_name": "dev3",
            "size": Size("10 GiB"),
            "mountpoint": "/",
            "fstype": "xfs",
            "label": "root",
            "encrypted": True,
            "luks_version": "luks1",
            "raid_level": raid.RAID1,
            "container_name": None,
            "container_size": devicefactory.SIZE_POLICY_AUTO,
            "container_raid_level": None,
            "container_encrypted": False
        })

        request = DeviceFactoryRequest()
        request.device_spec = "dev3"
        request.disks = ["dev1", "dev2"]
        request.device_name = "dev3"
        request.container_name = "container1"
        request.container_size_policy = Size("10 GiB").get_bytes()
        request.container_encrypted = True
        request.container_raid_level = "raid1"

        self.assertEqual(utils.get_device_factory_arguments(self.storage, request), {
            "device": dev3,
            "disks": [dev1, dev2],
            "device_type": devicefactory.DEVICE_TYPE_LVM,
            "device_name": "dev3",
            "size": None,
            "mountpoint": None,
            "fstype": None,
            "label": None,
            "encrypted": False,
            "luks_version": None,
            "raid_level": None,
            "container_name": "container1",
            "container_size": Size("10 GiB"),
            "container_raid_level": raid.RAID1,
            "container_encrypted": True
        })
