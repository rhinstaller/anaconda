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
from unittest.mock import patch, Mock

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation

from blivet.devices import StorageDevice, DiskDevice, DASDDevice, ZFCPDiskDevice, PartitionDevice, \
    LUKSDevice
from blivet.errors import StorageError
from blivet.formats import get_format
from blivet.formats.fs import FS
from blivet.formats.luks import LUKS
from blivet.size import Size

from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.errors.storage import UnknownDeviceError
from pyanaconda.modules.storage.devicetree import DeviceTreeModule
from pyanaconda.modules.storage.devicetree.devicetree_interface import DeviceTreeInterface
from pyanaconda.modules.storage.devicetree.populate import FindDevicesTask
from pyanaconda.modules.storage.devicetree.rescue import FindExistingSystemsTask, \
    MountExistingSystemTask
from pyanaconda.storage.initialization import create_storage
from pyanaconda.storage.root import Root


class DeviceTreeInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the device tree handler."""

    def setUp(self):
        self.module = DeviceTreeModule()
        self.interface = DeviceTreeInterface(self.module)

        # Set the storage.
        self.module.on_storage_reset(create_storage())

    def publication_test(self):
        """Check the DBus representation."""
        self.assertIsInstance(self.module.for_publication(), DeviceTreeInterface)

    @property
    def storage(self):
        """Get the storage object."""
        return self.module.storage

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.storage.devicetree._add_device(device)

    def get_root_device_test(self):
        """Test GetRootDevice."""
        self.assertEqual(self.interface.GetRootDevice(), "")

        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/home")))

        self.assertEqual(self.interface.GetRootDevice(), "dev1")

    def get_devices_test(self):
        """Test GetDevices."""
        self.assertEqual(self.interface.GetDevices(), [])

        self._add_device(DiskDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB")
        ))

        self._add_device(StorageDevice(
            "dev2",
            fmt=get_format("ext4"),
            size=Size("10 GiB")
        ))

        self.assertEqual(self.interface.GetDevices(), ["dev1", "dev2"])

    def get_disks_test(self):
        """Test GetDisks."""
        self.assertEqual(self.interface.GetDisks(), [])

        self._add_device(DiskDevice(
            "dev1",
            fmt=get_format("ext4"),
            exists=True,
            size=Size("10 GiB"))
        )

        self.assertEqual(self.interface.GetDisks(), ["dev1"])

    def get_mount_points_test(self):
        """Test GetMountPoints."""
        self.assertEqual(self.interface.GetMountPoints(), {})

        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/home")))

        self.assertEqual(self.interface.GetMountPoints(), {
            "/": "dev1",
            "/home": "dev2"
        })

    def get_device_data_test(self):
        """Test GetDeviceData."""
        self._add_device(DiskDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 MiB"),
            serial="SERIAL_ID",
            vendor="VENDOR_ID",
            model="MODEL_ID",
            bus="BUS_ID",
            wwn="0x0000000000000000",
            uuid="1234-56-7890"
        ))

        self.assertEqual(self.interface.GetDeviceData("dev1"), {
            'type': get_variant(Str, 'disk'),
            'name': get_variant(Str, 'dev1'),
            'path': get_variant(Str, '/dev/dev1'),
            'size': get_variant(UInt64, Size("10 MiB").get_bytes()),
            'is-disk': get_variant(Bool, True),
            'parents': get_variant(List[Str], []),
            'attrs': get_variant(Dict[Str, Str], {
                "serial": "SERIAL_ID",
                "vendor": "VENDOR_ID",
                "model": "MODEL_ID",
                "bus": "BUS_ID",
                "wwn": "0x0000000000000000",
                "uuid": "1234-56-7890"
            }),
            'description': get_variant(
                Str, "VENDOR_ID MODEL_ID 0x0000000000000000"
            )
        })

    def get_unknown_device_data_test(self):
        """Test GetDeviceData for unknown."""
        with self.assertRaises(UnknownDeviceError):
            self.interface.GetDeviceData("dev1")

    def get_dasd_device_data_test(self):
        """Test GetDeviceData for DASD."""
        self._add_device(DASDDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB"),
            busid="0.0.0201",
            opts={}
        ))

        data = self.interface.GetDeviceData("dev1")
        self.assertEqual(data['type'], get_variant(Str, 'dasd'))
        self.assertEqual(data['attrs'], get_variant(Dict[Str, Str], {"busid": "0.0.0201"}))

    def get_zfcp_device_data_test(self):
        """Test GetDeviceData for zFCP."""
        self._add_device(ZFCPDiskDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB"),
            fcp_lun="0x5719000000000000",
            wwpn="0x5005076300c18154",
            hba_id="0.0.010a"
        ))

        data = self.interface.GetDeviceData("dev1")
        self.assertEqual(data['type'], get_variant(Str, 'zfcp'))
        self.assertEqual(data['attrs'], get_variant(Dict[Str, Str], {
            "fcp_lun": "0x5719000000000000",
            "wwpn": "0x5005076300c18154",
            "hba_id": "0.0.010a"
        }))

    def get_format_data_test(self):
        """Test GetFormatData."""
        fmt1 = get_format("ext4", uuid="1234-56-7890", label="LABEL")
        dev1 = StorageDevice("dev1", fmt=fmt1, size=Size("10 GiB"))

        self._add_device(dev1)

        self.assertEqual(self.interface.GetFormatData("dev1"), {
            'type': get_variant(Str, 'ext4'),
            'mountable': get_variant(Bool, True),
            'attrs': get_variant(Dict[Str, Str], {
                "uuid": "1234-56-7890",
                "label": "LABEL",
            }),
            'description': get_variant(Str, 'ext4'),
        })

        fmt2 = get_format("luks")
        dev2 = LUKSDevice("dev2", parents=[dev1], fmt=fmt2, size=Size("10 GiB"))

        self._add_device(dev2)

        self.assertEqual(self.interface.GetFormatData("dev2"), {
            'type': get_variant(Str, 'luks'),
            'mountable': get_variant(Bool, False),
            'attrs': get_variant(Dict[Str, Str], {}),
            'description': get_variant(Str, 'LUKS'),
        })

    def get_format_type_data_test(self):
        """Test GetFormatTypeData."""
        self.assertEqual(self.interface.GetFormatTypeData("swap"), {
            'type': get_variant(Str, 'swap'),
            'mountable': get_variant(Bool, False),
            'attrs': get_variant(Dict[Str, Str], {}),
            'description': get_variant(Str, 'swap'),
        })

    def get_actions_test(self):
        """Test GetActions."""
        self.assertEqual(self.interface.GetActions(), [])

        self._add_device(DiskDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 MiB"),
        ))

        device = self.storage.devicetree.get_device_by_name("dev1")
        self.storage.destroy_device(device)

        self.assertEqual(self.interface.GetActions(), [{
            'action-type': get_variant(Str, 'destroy'),
            'action-object': get_variant(Str, 'device'),
            'device-name': get_variant(Str, 'dev1'),
            'description': get_variant(Str, 'destroy device'),
        }])

    def get_supported_file_systems_test(self):
        """Test GetSupportedFileSystems."""
        result = self.interface.GetSupportedFileSystems()
        self.assertIsInstance(result, list)
        self.assertNotEqual(len(result), 0)

        for fs in result:
            fmt = get_format(fs)
            self.assertIsInstance(fs, str)
            self.assertIsNotNone(fmt.type)

    def get_required_device_size_test(self):
        """Test GetRequiredDeviceSize."""
        required_size = self.interface.GetRequiredDeviceSize(Size("1 GiB").get_bytes())
        self.assertEqual(Size("1280 MiB").get_bytes(), required_size, Size(required_size))

    def get_file_system_free_space_test(self):
        """Test GetFileSystemFreeSpace."""
        self._add_device(StorageDevice(
            "dev1",
            fmt=get_format("ext4", mountpoint="/"),
            size=Size("5 GiB"))
        )

        self._add_device(StorageDevice(
            "dev2",
            fmt=get_format("ext4", mountpoint="/usr"),
            size=Size("5 GiB"))
        )

        total_size = self.interface.GetFileSystemFreeSpace([])
        self.assertEqual(total_size, 0)

        total_size = self.interface.GetFileSystemFreeSpace(["/", "/usr"])
        self.assertLess(total_size, Size("10 GiB").get_bytes())
        self.assertGreater(total_size, Size("8 GiB").get_bytes())

    def get_disk_free_space_test(self):
        """Test GetDiskFreeSpace."""
        self._add_device(DiskDevice(
            "dev1",
            size=Size("5 GiB"))
        )

        self._add_device(DiskDevice(
            "dev2",
            size=Size("5 GiB"))
        )

        total_size = self.interface.GetDiskFreeSpace([])
        self.assertEqual(total_size, 0)

        total_size = self.interface.GetDiskFreeSpace(["dev1", "dev2"])
        self.assertEqual(total_size, Size("10 GiB").get_bytes())

        with self.assertRaises(UnknownDeviceError):
            self.interface.GetDiskFreeSpace(["dev1", "dev2", "dev3"])

    def get_disk_reclaimable_space_test(self):
        """Test GetDiskReclaimableSpace."""
        self._add_device(DiskDevice(
            "dev1",
            size=Size("5 GiB"))
        )

        self._add_device(DiskDevice(
            "dev2",
            size=Size("5 GiB"))
        )

        total_size = self.interface.GetDiskReclaimableSpace([])
        self.assertEqual(total_size, 0)

        # FIXME: Test on devices with a reclaimable space.
        total_size = self.interface.GetDiskReclaimableSpace(["dev1", "dev2"])
        self.assertEqual(total_size, 0)

        with self.assertRaises(UnknownDeviceError):
            self.interface.GetDiskReclaimableSpace(["dev1", "dev2", "dev3"])

    def resolve_device_test(self):
        """Test ResolveDevice."""
        self._add_device(DiskDevice("dev1"))

        self.assertEqual(self.interface.ResolveDevice("dev0"), "")
        self.assertEqual(self.interface.ResolveDevice("dev1"), "dev1")
        self.assertEqual(self.interface.ResolveDevice("/dev/dev1"), "dev1")

    def get_device_ancestors_test(self):
        """Test GetDeviceAncestors."""
        dev1 = StorageDevice("dev1")
        self._add_device(dev1)

        dev2 = StorageDevice("dev2", parents=[dev1])
        self._add_device(dev2)

        dev3 = StorageDevice("dev3", parents=[dev2])
        self._add_device(dev3)

        self.assertEqual(self.interface.GetDeviceAncestors("dev1"), [])
        self.assertEqual(self.interface.GetDeviceAncestors("dev2"), ["dev1"])
        self.assertEqual(self.interface.GetDeviceAncestors("dev3"), ["dev1", "dev2"])

    @patch.object(StorageDevice, "setup")
    def setup_device_test(self, setup):
        """Test SetupDevice."""
        self._add_device(StorageDevice("dev1"))

        self.interface.SetupDevice("dev1")
        setup.assert_called_once()

    @patch.object(StorageDevice, "teardown")
    def teardown_device_test(self, teardown):
        """Test TeardownDevice."""
        self._add_device(StorageDevice("dev1"))

        self.interface.TeardownDevice("dev1")
        teardown.assert_called_once()

    @patch.object(FS, "mount")
    def mount_device_test(self, mount):
        """Test MountDevice."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))

        with tempfile.TemporaryDirectory() as d:
            self.interface.MountDevice("dev1", d)
            mount.assert_called_once_with(mountpoint=d)

    @patch.object(FS, "unmount")
    def unmount_device_test(self, unmount):
        """Test UnmountDevice."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))

        with tempfile.TemporaryDirectory() as d:
            self.interface.UnmountDevice("dev1", d)
            unmount.assert_called_once_with(mountpoint=d)

    def find_install_media_test(self):
        """Test FindInstallMedia."""
        self.assertEqual(self.interface.FindOpticalMedia(), [])

    @patch.object(FS, "update_size_info")
    def find_mountable_partitions_test(self, update_size_info):
        """Test FindMountablePartitions."""
        self._add_device(StorageDevice(
            "dev1",
            fmt=get_format("ext4"))
        )
        self._add_device(PartitionDevice(
            "dev2",
            fmt=get_format("ext4", exists=True)
        ))

        self.assertEqual(self.interface.FindMountablePartitions(), ["dev2"])

    @patch("pyanaconda.storage.utils.try_populate_devicetree")
    @patch.object(LUKS, "setup")
    @patch.object(LUKSDevice, "teardown")
    @patch.object(LUKSDevice, "setup")
    def unlock_device_test(self, device_setup, device_teardown, format_setup, populate):
        """Test UnlockDevice."""
        dev1 = StorageDevice("dev1", fmt=get_format("ext4"), size=Size("10 GiB"))
        self._add_device(dev1)

        dev2 = LUKSDevice("dev2", parents=[dev1], fmt=get_format("luks"), size=Size("10 GiB"))
        self._add_device(dev2)

        self.assertEqual(self.interface.UnlockDevice("dev2", "passphrase"), True)

        device_setup.assert_called_once()
        format_setup.assert_called_once()
        populate.assert_called_once()
        device_teardown.assert_not_called()
        self.assertTrue(dev2.format.has_key)

        device_setup.side_effect = StorageError("Fake error")
        self.assertEqual(self.interface.UnlockDevice("dev2", "passphrase"), False)

        device_teardown.assert_called_once()
        self.assertFalse(dev2.format.has_key)

    def find_unconfigured_luks_test(self):
        """Test FindUnconfiguredLUKS."""
        self.assertEqual(self.interface.FindUnconfiguredLUKS(), [])

        dev1 = StorageDevice("dev1", fmt=get_format("ext4"), size=Size("10 GiB"))
        self._add_device(dev1)

        self.assertEqual(self.interface.FindUnconfiguredLUKS(), [])

        dev2 = LUKSDevice("dev2", parents=[dev1], fmt=get_format("luks"), size=Size("10 GiB"))
        self._add_device(dev2)

        self.assertEqual(self.interface.FindUnconfiguredLUKS(), ["dev2"])

    def set_device_passphrase_test(self):
        """Test SetDevicePassphrase."""
        dev1 = StorageDevice("dev1", fmt=get_format("ext4"), size=Size("10 GiB"))
        self._add_device(dev1)

        dev2 = LUKSDevice("dev2", parents=[dev1], fmt=get_format("luks"), size=Size("10 GiB"))
        self._add_device(dev2)

        self.assertEqual(self.interface.FindUnconfiguredLUKS(), ["dev2"])
        self.interface.SetDevicePassphrase("dev2", "123456")
        self.assertEqual(self.interface.FindUnconfiguredLUKS(), [])

    def get_fstab_spec_test(self):
        """Test GetFstabSpec."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", uuid="123")))
        self.assertEqual(self.interface.GetFstabSpec("dev1"), "UUID=123")

    def get_existing_systems_test(self):
        """Test GetExistingSystems."""
        self.assertEqual(self.interface.GetExistingSystems(), [])

        root_device = StorageDevice("dev1", fmt=get_format("ext4"))
        swap_device = StorageDevice("dev2", fmt=get_format("swap"))

        self.storage.roots = [Root(
            name="My Linux",
            mounts={"/": root_device},
            swaps=[swap_device]
        )]

        self.assertEqual(self.interface.GetExistingSystems(), [{
            'os-name': get_variant(Str, 'My Linux'),
            'mount-points': get_variant(Dict[Str, Str], {'/': 'dev1'}),
            'swap-devices': get_variant(List[Str], ['dev2'])
        }])

    @patch_dbus_publish_object
    def find_existing_systems_with_task_test(self, publisher):
        """Test FindExistingSystemsWithTask."""
        task_path = self.interface.FindExistingSystemsWithTask()

        obj = check_task_creation(self, task_path, publisher, FindExistingSystemsTask)

        self.assertEqual(obj.implementation._devicetree, self.module.storage.devicetree)

        roots = [Root(name="My Linux")]
        obj.implementation._set_result(roots)
        obj.implementation.succeeded_signal.emit()
        self.assertEqual(self.storage.roots, roots)

    @patch_dbus_publish_object
    def mount_existing_system_with_task_test(self, publisher):
        """Test MountExistingSystemWithTask."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))

        task_path = self.interface.MountExistingSystemWithTask("dev1", True)

        obj = check_task_creation(self, task_path, publisher, MountExistingSystemTask)

        self.assertEqual(obj.implementation._storage, self.module.storage)
        self.assertEqual(obj.implementation._device.name, "dev1")
        self.assertEqual(obj.implementation._read_only, True)

    @patch_dbus_publish_object
    def find_devices_with_task_test(self, publisher):
        """Test FindDevicesWithTask."""
        task_path = self.interface.FindDevicesWithTask()

        obj = check_task_creation(self, task_path, publisher, FindDevicesTask)

        self.assertEqual(obj.implementation._devicetree, self.module.storage.devicetree)


class DeviceTreeTasksTestCase(unittest.TestCase):
    """Test the storage tasks."""

    def find_existing_systems_test(self):
        storage = create_storage()
        task = FindExistingSystemsTask(storage.devicetree)
        self.assertEqual(task.run(), [])

    @patch('pyanaconda.modules.storage.devicetree.rescue.mount_existing_system')
    def mount_existing_system_test(self, mount):
        storage = create_storage()
        device = StorageDevice("dev1", fmt=get_format("ext4"))
        storage.devicetree._add_device(device)

        task = MountExistingSystemTask(storage, device, True)
        task.run()

        mount.assert_called_once_with(
            storage=storage,
            root_device=device,
            read_only=True
        )

    def find_devices_test(self):
        storage = Mock()

        task = FindDevicesTask(storage.devicetree)
        task.run()

        storage.devicetree.populate.assert_called_once_with()
