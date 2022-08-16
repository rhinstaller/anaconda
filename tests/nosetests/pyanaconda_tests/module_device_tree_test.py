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
from unittest.mock import patch, Mock, PropertyMock

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation

from blivet.devices import StorageDevice, DiskDevice, DASDDevice, ZFCPDiskDevice, PartitionDevice, \
    LUKSDevice, iScsiDiskDevice, NVDIMMNamespaceDevice, FcoeDiskDevice, OpticalDevice
from blivet.errors import StorageError, FSError
from blivet.formats import get_format
from blivet.formats.fs import FS, Iso9660FS
from blivet.formats.luks import LUKS
from blivet.size import Size

from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.errors.storage import UnknownDeviceError, MountFilesystemError
from pyanaconda.modules.storage.devicetree import DeviceTreeModule, create_storage
from pyanaconda.modules.storage.devicetree.devicetree_interface import DeviceTreeInterface
from pyanaconda.modules.storage.devicetree.populate import FindDevicesTask
from pyanaconda.modules.storage.devicetree.rescue import FindExistingSystemsTask, \
    MountExistingSystemTask
from pyanaconda.modules.storage.devicetree.root import Root


class DeviceTreeInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the device tree handler."""

    def setUp(self):
        self.maxDiff = None
        self.module = DeviceTreeModule()
        self.interface = DeviceTreeInterface(self.module)

        # Set the storage.
        self.module.on_storage_changed(create_storage())

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
            'protected': get_variant(Bool, False),
            'removable': get_variant(Bool, False),
            'parents': get_variant(List[Str], []),
            'children': get_variant(List[Str], []),
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
        self.assertEqual(data['attrs'], get_variant(Dict[Str, Str], {
            "bus-id": "0.0.0201"
        }))

    def get_fcoe_device_data_test(self):
        """Test GetDeviceData for FCoE."""
        self._add_device(FcoeDiskDevice(
            "dev1",
            fmt=get_format("disklabel"),
            size=Size("10 GiB"),
            nic=None,
            identifier=None,
            id_path="pci-0000:00:00.0-bla-1"
        ))

        data = self.interface.GetDeviceData("dev1")
        self.assertEqual(data['type'], get_variant(Str, 'fcoe'))
        self.assertEqual(data['attrs'], get_variant(Dict[Str, Str], {
            "path-id": "pci-0000:00:00.0-bla-1"
        }))

    def get_iscsi_device_data_test(self):
        """Test GetDeviceData for iSCSI."""
        self._add_device(iScsiDiskDevice(
            "dev1",
            fmt=get_format("disklabel"),
            size=Size("10 GiB"),
            port="3260",
            initiator="iqn.1994-05.com.redhat:blabla",
            lun="0",
            target="iqn.2014-08.com.example:t1",
            id_path="pci-0000:00:00.0-bla-1",
            node=None,
            ibft=None,
            nic=None,
            offload=None,
            name=None,
            address=None,
            iface=None
        ))

        data = self.interface.GetDeviceData("dev1")
        self.assertEqual(data['type'], get_variant(Str, 'iscsi'))
        self.assertEqual(data['attrs'], get_variant(Dict[Str, Str], {
            "port": "3260",
            "initiator": "iqn.1994-05.com.redhat:blabla",
            "lun": "0",
            "target": "iqn.2014-08.com.example:t1",
            "path-id": "pci-0000:00:00.0-bla-1"
        }))

    def get_nvdimm_device_data_test(self):
        """Test GetDeviceData for NVDIMM."""
        self._add_device(NVDIMMNamespaceDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB"),
            mode="sector",
            devname="namespace0.0",
            sector_size=512,
            id_path="pci-0000:00:00.0-bla-1"
        ))

        data = self.interface.GetDeviceData("dev1")
        self.assertEqual(data['type'], get_variant(Str, 'nvdimm'))
        self.assertEqual(data['attrs'], get_variant(Dict[Str, Str], {
            "mode": "sector",
            "namespace": "namespace0.0",
            "path-id": "pci-0000:00:00.0-bla-1"
        }))

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
            "fcp-lun": "0x5719000000000000",
            "wwpn": "0x5005076300c18154",
            "hba-id": "0.0.010a"
        }))

    def get_format_data_test(self):
        """Test GetFormatData."""
        fmt1 = get_format(
            "ext4",
            uuid="1234-56-7890",
            label="LABEL",
            mountpoint="/home"
        )
        dev1 = StorageDevice(
            "dev1",
            fmt=fmt1,
            size=Size("10 GiB")
        )
        self._add_device(dev1)

        self.assertEqual(self.interface.GetFormatData("dev1"), {
            'type': get_variant(Str, 'ext4'),
            'mountable': get_variant(Bool, True),
            'attrs': get_variant(Dict[Str, Str], {
                "uuid": "1234-56-7890",
                "label": "LABEL",
                "mount-point": "/home"
            }),
            'description': get_variant(Str, 'ext4'),
        })

        fmt2 = get_format(
            "luks"
        )
        dev2 = LUKSDevice(
            "dev2",
            parents=[dev1],
            fmt=fmt2,
            size=Size("10 GiB")
        )
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

        dev1 = DiskDevice(
            "dev1",
            fmt=get_format("disklabel"),
            size=Size("1 GiB"),
            vendor="VENDOR",
            model="MODEL"
        )

        self._add_device(dev1)
        self.storage.initialize_disk(dev1)
        dev1.format._label_type = "msdos"

        action_1 = {
            'action-type': 'create',
            'action-description': 'create format',
            'object-type': 'format',
            'object-description': 'partition table (MSDOS)',
            'device-name': 'dev1',
            'device-description': 'VENDOR MODEL (dev1)',
            'attrs': {},
        }

        self.assertEqual(get_native(self.interface.GetActions()), [
            action_1
        ])

        dev2 = StorageDevice(
            "dev2",
            size=Size("500 MiB"),
            serial="SERIAL",
            exists=True
        )

        self._add_device(dev2)
        self.storage.destroy_device(dev2)

        action_2 = {
            'action-type': 'destroy',
            'action-description': 'destroy device',
            'object-type': 'device',
            'object-description': 'blivet',
            'device-name': 'dev2',
            'device-description': 'dev2',
            'attrs': {"serial": "SERIAL"},
        }

        self.assertEqual(get_native(self.interface.GetActions()), [
            action_2,
            action_1
          ])

        dev3 = PartitionDevice(
            "dev3",
            fmt=get_format("ext4", mountpoint="/home"),
            size=Size("500 MiB"),
            parents=[dev1]
        )

        self.storage.create_device(dev3)
        dev3.disk = dev1

        action_3 = {
            'action-type': 'create',
            'action-description': 'create device',
            'object-type': 'device',
            'object-description': 'partition',
            'device-name': 'dev3',
            'device-description': 'dev3 on VENDOR MODEL',
            'attrs': {},
        }

        action_4 = {
            'action-type': 'create',
            'action-description': 'create format',
            'object-type': 'format',
            'object-description': 'ext4',
            'device-name': 'dev3',
            'device-description': 'dev3 on VENDOR MODEL',
            'attrs': {'mount-point': '/home'},
        }

        self.assertEqual(get_native(self.interface.GetActions()), [
            action_2,
            action_1,
            action_3,
            action_4,
          ])

    def get_supported_file_systems_test(self):
        """Test GetSupportedFileSystems."""
        result = self.interface.GetSupportedFileSystems()
        self.assertIsInstance(result, list)
        self.assertNotEqual(len(result), 0)

        for fs in result:
            self.assertIsInstance(fs, str)
            self.assertEqual(fs, get_format(fs).type)

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

    @patch("blivet.formats.disklabel.DiskLabel.free", new_callable=PropertyMock)
    @patch("blivet.formats.disklabel.DiskLabel.get_platform_label_types")
    def get_disk_free_space_test(self, label_types, free):
        """Test GetDiskFreeSpace."""
        label_types.return_value = ["msdos", "gpt"]
        free.return_value = Size("4 GiB")

        self._add_device(DiskDevice(
            "dev1",
            fmt=get_format("disklabel", label_type="msdos"),
            size=Size("5 GiB"))
        )

        self._add_device(DiskDevice(
            "dev2",
            fmt=get_format("disklabel", label_type="gpt"),
            size=Size("5 GiB"))
        )

        self._add_device(DiskDevice(
            "dev3",
            fmt=get_format("disklabel", label_type="dasd"),
            size=Size("5 GiB")
        ))

        total_size = self.interface.GetDiskFreeSpace([])
        self.assertEqual(total_size, 0)

        total_size = self.interface.GetDiskFreeSpace(["dev1", "dev2", "dev3"])
        self.assertEqual(total_size, Size("8 GiB").get_bytes())

        with self.assertRaises(UnknownDeviceError):
            self.interface.GetDiskFreeSpace(["dev1", "dev2", "devX"])

    @patch("blivet.formats.disklabel.DiskLabel.get_platform_label_types")
    def get_disk_reclaimable_space_test(self, label_types):
        """Test GetDiskReclaimableSpace."""
        label_types.return_value = ["msdos", "gpt"]

        self._add_device(DiskDevice(
            "dev1",
            fmt=get_format("disklabel", label_type="msdos"),
            size=Size("5 GiB"))
        )

        self._add_device(DiskDevice(
            "dev2",
            fmt=get_format("disklabel", label_type="gpt"),
            size=Size("5 GiB"))
        )

        self._add_device(DiskDevice(
            "dev3",
            fmt=get_format("disklabel", label_type="dasd"),
            size=Size("5 GiB")
        ))

        total_size = self.interface.GetDiskReclaimableSpace([])
        self.assertEqual(total_size, 0)

        # FIXME: Test on devices with a reclaimable space.
        total_size = self.interface.GetDiskReclaimableSpace(["dev1", "dev2", "dev3"])
        self.assertEqual(total_size, 0)

        with self.assertRaises(UnknownDeviceError):
            self.interface.GetDiskReclaimableSpace(["dev1", "dev2", "devX"])

    def get_disk_total_space_test(self):
        """Test GetDiskTotalSpace."""
        self._add_device(DiskDevice(
            "dev1",
            size=Size("5 GiB"))
        )

        self._add_device(DiskDevice(
            "dev2",
            size=Size("5 GiB"))
        )

        self._add_device(DiskDevice(
            "dev3",
            size=Size("5 GiB")
        ))

        total_size = self.interface.GetDiskTotalSpace(["dev1", "dev2"])
        self.assertEqual(total_size, Size("10 GiB").get_bytes())

    def resolve_device_test(self):
        """Test ResolveDevice."""
        self._add_device(DiskDevice("dev1"))

        self.assertEqual(self.interface.ResolveDevice("dev0"), "")
        self.assertEqual(self.interface.ResolveDevice("dev1"), "dev1")
        self.assertEqual(self.interface.ResolveDevice("/dev/dev1"), "dev1")

    def get_ancestors_test(self):
        """Test GetAncestors."""
        dev1 = StorageDevice("dev1")
        self._add_device(dev1)

        dev2 = StorageDevice("dev2", parents=[dev1])
        self._add_device(dev2)

        dev3 = StorageDevice("dev3", parents=[dev2])
        self._add_device(dev3)

        dev4 = StorageDevice("dev4")
        self._add_device(dev4)

        dev5 = StorageDevice("dev5", parents=[dev4])
        self._add_device(dev5)

        self.assertEqual(self.interface.GetAncestors(["dev1"]), [])
        self.assertEqual(self.interface.GetAncestors(["dev2"]), ["dev1"])
        self.assertEqual(self.interface.GetAncestors(["dev3"]), ["dev1", "dev2"])
        self.assertEqual(self.interface.GetAncestors(["dev2", "dev3"]), ["dev1", "dev2"])
        self.assertEqual(self.interface.GetAncestors(["dev2", "dev5"]), ["dev1", "dev4"])

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
            self.interface.MountDevice("dev1", d, "")
            mount.assert_called_once_with(mountpoint=d, options=None)

        mount.side_effect = FSError("Fake error.")
        with self.assertRaises(MountFilesystemError) as cm:
            self.interface.MountDevice("dev1", "/path", "")

        self.assertEqual(
            str(cm.exception), "Failed to mount dev1 at /path: Fake error."
        )

    @patch.object(FS, "mount")
    def mount_device_with_options_test(self, mount):
        """Test MountDevice with options specified."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))

        with tempfile.TemporaryDirectory() as d:
            self.interface.MountDevice("dev1", d, "ro,auto")
            mount.assert_called_once_with(mountpoint=d, options="ro,auto")

        mount.side_effect = FSError("Fake error.")
        with self.assertRaises(MountFilesystemError) as cm:
            self.interface.MountDevice("dev1", "/path", "ro,auto")

        self.assertEqual(
            str(cm.exception), "Failed to mount dev1 at /path: Fake error."
        )

    @patch.object(FS, "unmount")
    def unmount_device_test(self, unmount):
        """Test UnmountDevice."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))

        with tempfile.TemporaryDirectory() as d:
            self.interface.UnmountDevice("dev1", d)
            unmount.assert_called_once_with(mountpoint=d)

        unmount.side_effect = FSError("Fake error.")
        with self.assertRaises(MountFilesystemError) as cm:
            self.interface.UnmountDevice("dev1", "/path")

        self.assertEqual(
            str(cm.exception), "Failed to unmount dev1 from /path: Fake error."
        )

    @patch.object(Iso9660FS, "check_module")
    def find_install_media_test(self, check_module):
        """Test FindInstallMedia."""
        dev1 = OpticalDevice("dev1")
        dev1.size = Size("2 GiB")
        dev1.format = get_format("iso9660")
        dev1.controllable = True
        self._add_device(dev1)

        dev2 = StorageDevice("dev2")
        dev2.size = Size("2 GiB")
        dev2.format = get_format("iso9660")
        dev2.controllable = True
        self._add_device(dev2)

        dev3 = StorageDevice("dev3")
        dev3.size = Size("2 GiB")
        dev3.format = get_format("ext4")
        dev3.controllable = True
        self._add_device(dev3)

        self.assertEqual(self.interface.FindOpticalMedia(), ["dev1", "dev2"])

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

    @patch.object(LUKS, "setup")
    @patch.object(LUKSDevice, "teardown")
    @patch.object(LUKSDevice, "setup")
    def unlock_device_test(self, device_setup, device_teardown, format_setup):
        """Test UnlockDevice."""
        self.storage.devicetree.populate = Mock()
        self.storage.devicetree.teardown_all = Mock()

        dev1 = StorageDevice("dev1", fmt=get_format("ext4"), size=Size("10 GiB"))
        self._add_device(dev1)

        dev2 = LUKSDevice("dev2", parents=[dev1], fmt=get_format("luks"), size=Size("10 GiB"))
        self._add_device(dev2)

        self.assertEqual(self.interface.UnlockDevice("dev2", "passphrase"), True)

        device_setup.assert_called_once()
        format_setup.assert_called_once()
        device_teardown.assert_not_called()
        self.storage.devicetree.populate.assert_called_once()
        self.storage.devicetree.teardown_all.assert_called_once()
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
            devices=[root_device, swap_device],
            mounts={"/": root_device},
        )]

        self.assertEqual(self.interface.GetExistingSystems(), [{
            'os-name': get_variant(Str, 'My Linux'),
            'devices': get_variant(List[Str], ['dev1', 'dev2']),
            'mount-points': get_variant(Dict[Str, Str], {'/': 'dev1'}),
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

    def get_device_mount_options_test(self):
        """Test GetDeviceMountOptions."""
        dev1 = StorageDevice(
            "dev1",
            size=Size("10 GiB")
        )
        self._add_device(dev1)
        self.assertEqual(self.interface.GetDeviceMountOptions("dev1"), "")

        dev1.format = get_format("ext4")
        dev1.format.options = "defaults,ro"
        self.assertEqual(self.interface.GetDeviceMountOptions("dev1"), "defaults,ro")

    def set_device_mount_options_test(self):
        """Test SetDeviceMountOptions."""
        dev1 = StorageDevice(
            "dev1",
            size=Size("10 GiB")
        )
        self._add_device(dev1)

        self.interface.SetDeviceMountOptions("dev1", "auto")
        self.assertEqual(dev1.format.options, "auto")

        self.interface.SetDeviceMountOptions("dev1", "")
        self.assertEqual(dev1.format.options, None)

        dev1.format = get_format("ext4")
        dev1.format.options = "defaults,ro"
        self.interface.SetDeviceMountOptions("dev1", "")
        self.assertEqual(dev1.format.options, "defaults")


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
