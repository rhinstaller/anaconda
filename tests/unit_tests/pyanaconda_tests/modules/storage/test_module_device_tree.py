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
import pytest

from unittest.mock import patch, Mock, PropertyMock

from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation

from blivet.devices import StorageDevice, DiskDevice, DASDDevice, ZFCPDiskDevice, PartitionDevice, \
    LUKSDevice, iScsiDiskDevice, FcoeDiskDevice, OpticalDevice
from blivet.errors import StorageError, FSError
from blivet.formats import get_format, device_formats, DeviceFormat
from blivet.formats.fs import FS, Iso9660FS
from blivet.formats.luks import LUKS
from blivet.size import Size

from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.core.kernel import KernelArguments
from pyanaconda.modules.common.errors.storage import UnknownDeviceError, MountFilesystemError
from pyanaconda.modules.common.structures.storage import DeviceFormatData, \
    MountPointConstraintsData
from pyanaconda.modules.storage.devicetree import DeviceTreeModule, create_storage, utils
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

    def test_publication(self):
        """Check the DBus representation."""
        assert isinstance(self.module.for_publication(), DeviceTreeInterface)

    @property
    def storage(self):
        """Get the storage object."""
        return self.module.storage

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.storage.devicetree._add_device(device)

    def test_get_root_device(self):
        """Test GetRootDevice."""
        assert self.interface.GetRootDevice() == ""

        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/home")))

        assert self.interface.GetRootDevice() == "dev1"

    def test_get_devices(self):
        """Test GetDevices."""
        assert self.interface.GetDevices() == []

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

        assert self.interface.GetDevices() == ["dev1", "dev2"]

    def test_get_disks(self):
        """Test GetDisks."""
        assert self.interface.GetDisks() == []

        self._add_device(DiskDevice(
            "dev1",
            fmt=get_format("ext4"),
            exists=True,
            size=Size("10 GiB"))
        )

        assert self.interface.GetDisks() == ["dev1"]

    def test_get_mount_points(self):
        """Test GetMountPoints."""
        assert self.interface.GetMountPoints() == {}

        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/home")))

        assert self.interface.GetMountPoints() == {
            "/": "dev1",
            "/home": "dev2"
        }

    def test_get_device_data(self):
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

        assert self.interface.GetDeviceData("dev1") == {
            'type': get_variant(Str, 'disk'),
            'name': get_variant(Str, 'dev1'),
            'path': get_variant(Str, '/dev/dev1'),
            'size': get_variant(UInt64, Size("10 MiB").get_bytes()),
            'is-disk': get_variant(Bool, True),
            'protected': get_variant(Bool, False),
            'removable': get_variant(Bool, False),
            'parents': get_variant(List[Str], []),
            'children': get_variant(List[Str], []),
            'links': get_variant(List[Str], []),
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
        }

    def test_get_unknown_device_data(self):
        """Test GetDeviceData for unknown."""
        with pytest.raises(UnknownDeviceError):
            self.interface.GetDeviceData("dev1")

    def test_get_dasd_device_data(self):
        """Test GetDeviceData for DASD."""
        self._add_device(DASDDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB"),
            busid="0.0.0201",
            opts={}
        ))

        data = self.interface.GetDeviceData("dev1")
        assert data['type'] == get_variant(Str, 'dasd')
        assert data['attrs'] == get_variant(Dict[Str, Str], {
            "bus-id": "0.0.0201"
        })

    def test_get_fcoe_device_data(self):
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
        assert data['type'] == get_variant(Str, 'fcoe')
        assert data['attrs'] == get_variant(Dict[Str, Str], {
            "path-id": "pci-0000:00:00.0-bla-1"
        })

    def test_get_iscsi_device_data(self):
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
        assert data['type'] == get_variant(Str, 'iscsi')
        assert data['attrs'] == get_variant(Dict[Str, Str], {
            "port": "3260",
            "initiator": "iqn.1994-05.com.redhat:blabla",
            "lun": "0",
            "target": "iqn.2014-08.com.example:t1",
            "path-id": "pci-0000:00:00.0-bla-1"
        })

    def test_get_zfcp_device_data(self):
        """Test GetDeviceData for zFCP."""
        self._add_device(ZFCPDiskDevice(
            "dev1",
            fmt=get_format("ext4"),
            size=Size("10 GiB"),
            fcp_lun="0x5719000000000000",
            wwpn="0x5005076300c18154",
            hba_id="0.0.010a",
            id_path="ccw-0.0.010a-fc-0x5005076300c18154-lun-0x5719000000000000"
        ))

        data = self.interface.GetDeviceData("dev1")
        assert data['type'] == get_variant(Str, 'zfcp')
        assert data['attrs'] == get_variant(Dict[Str, Str], {
            "fcp-lun": "0x5719000000000000",
            "wwpn": "0x5005076300c18154",
            "hba-id": "0.0.010a",
            "path-id": "ccw-0.0.010a-fc-0x5005076300c18154-lun-0x5719000000000000"
        })

    def test_get_format_data(self):
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

        assert self.interface.GetFormatData("dev1") == {
            'type': get_variant(Str, 'ext4'),
            'mountable': get_variant(Bool, True),
            'formattable': get_variant(Bool, True),
            'attrs': get_variant(Dict[Str, Str], {
                "uuid": "1234-56-7890",
                "label": "LABEL",
                "mount-point": "/home"
            }),
            'description': get_variant(Str, 'ext4'),
        }

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

        assert self.interface.GetFormatData("dev2") == {
            'type': get_variant(Str, 'luks'),
            'mountable': get_variant(Bool, False),
            'formattable': get_variant(Bool, True),
            'attrs': get_variant(Dict[Str, Str], {'has_key': 'False'}),
            'description': get_variant(Str, 'LUKS'),
        }

        fmt3 = get_format(
            ""
        )
        dev3 = StorageDevice(
            "dev3",
            parents=[dev1],
            fmt=fmt3,
            size=Size("10 GiB")
        )
        self._add_device(dev3)

        assert self.interface.GetFormatData("dev3") == {
            'type': get_variant(Str, ''),
            'mountable': get_variant(Bool, False),
            'formattable': get_variant(Bool, False),
            'description': get_variant(Str, 'Unknown'),
            'attrs': get_variant(Dict[Str, Str], {}),
        }

    def test_get_format_type_data(self):
        """Test GetFormatTypeData."""
        assert self.interface.GetFormatTypeData("swap") == {
            'type': get_variant(Str, 'swap'),
            'mountable': get_variant(Bool, False),
            'formattable': get_variant(Bool, False),
            'attrs': get_variant(Dict[Str, Str], {}),
            'description': get_variant(Str, 'swap'),
        }

    def test_get_all_format_type_data(self):
        """Test GetFormatTypeData for all format types."""
        for format_type in device_formats:
            data = DeviceFormatData.from_structure(
                self.interface.GetFormatTypeData(format_type)
            )
            assert (format_type or "") == data.type

    def test_get_actions(self):
        """Test GetActions."""
        assert self.interface.GetActions() == []

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

        assert get_native(self.interface.GetActions()) == [
            action_1
        ]

        dev2 = StorageDevice(
            "dev2",
            fmt=get_format("ext4", mountpoint="/boot"),
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
            'attrs': {
                'serial': 'SERIAL',
                'mount-point': '/boot'
            },
        }

        assert get_native(self.interface.GetActions()) == [
            action_2,
            action_1
          ]

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
            'attrs': {'mount-point': '/home'},
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

        assert get_native(self.interface.GetActions()) == [
            action_2,
            action_1,
            action_3,
            action_4,
          ]

    def test_get_supported_file_systems(self):
        """Test GetSupportedFileSystems."""
        result = self.interface.GetSupportedFileSystems()
        assert isinstance(result, list)
        assert len(result) != 0

        for fs in result:
            assert isinstance(fs, str)
            assert fs == get_format(fs).type

    def test_get_required_device_size(self):
        """Test GetRequiredDeviceSize."""
        assert self.interface.GetRequiredDeviceSize(0) == 0

        required_size = self.interface.GetRequiredDeviceSize(Size("10 B").get_bytes())
        assert Size("1 MiB").get_bytes() == required_size, Size(required_size)

        required_size = self.interface.GetRequiredDeviceSize(Size("10 KiB").get_bytes())
        assert Size("1 MiB").get_bytes() == required_size, Size(required_size)

        required_size = self.interface.GetRequiredDeviceSize(Size("1 GiB").get_bytes())
        assert Size("1280 MiB").get_bytes() == required_size, Size(required_size)

    def test_get_file_system_free_space(self):
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
        assert total_size == 0

        total_size = self.interface.GetFileSystemFreeSpace(["/", "/usr"])
        assert total_size < Size("10 GiB").get_bytes()
        assert total_size > Size("8 GiB").get_bytes()

    @patch("blivet.formats.disklabel.DiskLabel.free", new_callable=PropertyMock)
    @patch("blivet.formats.disklabel.DiskLabel.get_platform_label_types")
    def test_get_disk_free_space(self, label_types, free):
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
        assert total_size == 0

        total_size = self.interface.GetDiskFreeSpace(["dev1", "dev2", "dev3"])
        assert total_size == Size("8 GiB").get_bytes()

        with pytest.raises(UnknownDeviceError):
            self.interface.GetDiskFreeSpace(["dev1", "dev2", "devX"])

    @patch("blivet.formats.disklabel.DiskLabel.get_platform_label_types")
    def test_get_disk_reclaimable_space(self, label_types):
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
        assert total_size == 0

        # FIXME: Test on devices with a reclaimable space.
        total_size = self.interface.GetDiskReclaimableSpace(["dev1", "dev2", "dev3"])
        assert total_size == 0

        with pytest.raises(UnknownDeviceError):
            self.interface.GetDiskReclaimableSpace(["dev1", "dev2", "devX"])

    def test_get_disk_total_space(self):
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
        assert total_size == Size("10 GiB").get_bytes()

    def test_resolve_device(self):
        """Test ResolveDevice."""
        self._add_device(DiskDevice("dev1"))

        assert self.interface.ResolveDevice("dev0") == ""
        assert self.interface.ResolveDevice("dev1") == "dev1"
        assert self.interface.ResolveDevice("/dev/dev1") == "dev1"

    def test_get_ancestors(self):
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

        assert self.interface.GetAncestors(["dev1"]) == []
        assert self.interface.GetAncestors(["dev2"]) == ["dev1"]
        assert self.interface.GetAncestors(["dev3"]) == ["dev1", "dev2"]
        assert self.interface.GetAncestors(["dev2", "dev3"]) == ["dev1", "dev2"]
        assert self.interface.GetAncestors(["dev2", "dev5"]) == ["dev1", "dev4"]

    @patch.object(FS, "mount")
    def test_mount_device(self, mount):
        """Test MountDevice."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))

        with tempfile.TemporaryDirectory() as d:
            self.interface.MountDevice("dev1", d, "")
            mount.assert_called_once_with(mountpoint=d, options=None)

        mount.side_effect = FSError("Fake error.")
        with pytest.raises(MountFilesystemError) as cm:
            self.interface.MountDevice("dev1", "/path", "")

        assert str(cm.value) == "Failed to mount dev1 at /path: Fake error."

    @patch.object(FS, "mount")
    def test_mount_device_with_options(self, mount):
        """Test MountDevice with options specified."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))

        with tempfile.TemporaryDirectory() as d:
            self.interface.MountDevice("dev1", d, "ro,auto")
            mount.assert_called_once_with(mountpoint=d, options="ro,auto")

        mount.side_effect = FSError("Fake error.")
        with pytest.raises(MountFilesystemError) as cm:
            self.interface.MountDevice("dev1", "/path", "ro,auto")

        assert str(cm.value) == "Failed to mount dev1 at /path: Fake error."

    @patch.object(FS, "unmount")
    def test_unmount_device(self, unmount):
        """Test UnmountDevice."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))

        with tempfile.TemporaryDirectory() as d:
            self.interface.UnmountDevice("dev1", d)
            unmount.assert_called_once_with(mountpoint=d)

        unmount.side_effect = FSError("Fake error.")
        with pytest.raises(MountFilesystemError) as cm:
            self.interface.UnmountDevice("dev1", "/path")

        assert str(cm.value) == "Failed to unmount dev1 from /path: Fake error."

    @patch.object(Iso9660FS, "check_module")
    def test_find_install_media(self, check_module):
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

        assert self.interface.FindOpticalMedia() == ["dev1", "dev2"]

    @patch.object(FS, "update_size_info")
    def test_find_mountable_partitions(self, update_size_info):
        """Test FindMountablePartitions."""
        self._add_device(StorageDevice(
            "dev1",
            fmt=get_format("ext4"))
        )
        self._add_device(PartitionDevice(
            "dev2",
            fmt=get_format("ext4", exists=True)
        ))

        assert self.interface.FindMountablePartitions() == ["dev2"]

    @patch.object(LUKS, "setup")
    @patch.object(LUKSDevice, "teardown")
    @patch.object(LUKSDevice, "setup")
    def test_unlock_device(self, device_setup, device_teardown, format_setup):
        """Test UnlockDevice."""
        self.storage.devicetree.populate = Mock()
        self.storage.devicetree.teardown_all = Mock()

        dev1 = StorageDevice("dev1", fmt=get_format("ext4"), size=Size("10 GiB"))
        self._add_device(dev1)

        dev2 = LUKSDevice("dev2", parents=[dev1], fmt=get_format("luks"), size=Size("10 GiB"))
        self._add_device(dev2)
        assert self.interface.GetFormatData("dev2") == {
            'type': get_variant(Str, 'luks'),
            'mountable': get_variant(Bool, False),
            'formattable': get_variant(Bool, True),
            'attrs': get_variant(Dict[Str, Str], {'has_key': 'False'}),
            'description': get_variant(Str, 'LUKS'),
        }

        assert self.interface.UnlockDevice("dev2", "passphrase") is True

        device_setup.assert_called_once()
        format_setup.assert_called_once()
        device_teardown.assert_not_called()
        self.storage.devicetree.populate.assert_called_once()
        self.storage.devicetree.teardown_all.assert_called_once()
        assert dev2.format.has_key
        assert self.interface.GetFormatData("dev2") == {
            'type': get_variant(Str, 'luks'),
            'mountable': get_variant(Bool, False),
            'formattable': get_variant(Bool, True),
            'attrs': get_variant(Dict[Str, Str], { "has_key": "True" }),
            'description': get_variant(Str, 'LUKS'),
        }

        device_setup.side_effect = StorageError("Fake error")
        assert self.interface.UnlockDevice("dev2", "passphrase") is False

        device_teardown.assert_called_once()
        assert not dev2.format.has_key

    def test_find_unconfigured_luks(self):
        """Test FindUnconfiguredLUKS."""
        assert self.interface.FindUnconfiguredLUKS() == []

        dev1 = StorageDevice("dev1", fmt=get_format("ext4"), size=Size("10 GiB"))
        self._add_device(dev1)

        assert self.interface.FindUnconfiguredLUKS() == []

        dev2 = LUKSDevice("dev2", parents=[dev1], fmt=get_format("luks"), size=Size("10 GiB"))
        self._add_device(dev2)

        assert self.interface.FindUnconfiguredLUKS() == ["dev2"]

    def test_set_device_passphrase(self):
        """Test SetDevicePassphrase."""
        dev1 = StorageDevice("dev1", fmt=get_format("ext4"), size=Size("10 GiB"))
        self._add_device(dev1)

        dev2 = LUKSDevice("dev2", parents=[dev1], fmt=get_format("luks"), size=Size("10 GiB"))
        self._add_device(dev2)

        assert self.interface.FindUnconfiguredLUKS() == ["dev2"]
        self.interface.SetDevicePassphrase("dev2", "123456")
        assert self.interface.FindUnconfiguredLUKS() == []

    def test_get_fstab_spec(self):
        """Test GetFstabSpec."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", uuid="123")))
        assert self.interface.GetFstabSpec("dev1") == "UUID=123"

    def test_get_existing_systems(self):
        """Test GetExistingSystems."""
        assert self.interface.GetExistingSystems() == []

        root_device = StorageDevice("dev1", fmt=get_format("ext4"))
        swap_device = StorageDevice("dev2", fmt=get_format("swap"))

        self.storage.roots = [Root(
            name="My Linux",
            devices=[root_device, swap_device],
            mounts={"/": root_device},
        )]

        assert self.interface.GetExistingSystems() == [{
            'os-name': get_variant(Str, 'My Linux'),
            'devices': get_variant(List[Str], ['dev1', 'dev2']),
            'mount-points': get_variant(Dict[Str, Str], {'/': 'dev1'}),
        }]

    @patch_dbus_publish_object
    def test_find_existing_systems_with_task(self, publisher):
        """Test FindExistingSystemsWithTask."""
        task_path = self.interface.FindExistingSystemsWithTask()

        obj = check_task_creation(task_path, publisher, FindExistingSystemsTask)

        assert obj.implementation._devicetree == self.module.storage.devicetree

        roots = [Root(name="My Linux")]
        obj.implementation._set_result(roots)
        obj.implementation.succeeded_signal.emit()
        assert self.storage.roots == roots

    @patch_dbus_publish_object
    def test_mount_existing_system_with_task(self, publisher):
        """Test MountExistingSystemWithTask."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4")))

        task_path = self.interface.MountExistingSystemWithTask("dev1", True)

        obj = check_task_creation(task_path, publisher, MountExistingSystemTask)

        assert obj.implementation._storage == self.module.storage
        assert obj.implementation._device.name == "dev1"
        assert obj.implementation._read_only is True

    @patch_dbus_publish_object
    def test_find_devices_with_task(self, publisher):
        """Test FindDevicesWithTask."""
        task_path = self.interface.FindDevicesWithTask()

        obj = check_task_creation(task_path, publisher, FindDevicesTask)

        assert obj.implementation._devicetree == self.module.storage.devicetree

    def test_get_device_mount_options(self):
        """Test GetDeviceMountOptions."""
        dev1 = StorageDevice(
            "dev1",
            size=Size("10 GiB")
        )
        self._add_device(dev1)
        assert self.interface.GetDeviceMountOptions("dev1") == ""

        dev1.format = get_format("ext4")
        dev1.format.options = "defaults,ro"
        assert self.interface.GetDeviceMountOptions("dev1") == "defaults,ro"

    def test_set_device_mount_options(self):
        """Test SetDeviceMountOptions."""
        dev1 = StorageDevice(
            "dev1",
            size=Size("10 GiB")
        )
        self._add_device(dev1)

        self.interface.SetDeviceMountOptions("dev1", "auto")
        assert dev1.format.options == "auto"

        self.interface.SetDeviceMountOptions("dev1", "")
        assert dev1.format.options is None

        dev1.format = get_format("ext4")
        dev1.format.options = "defaults,ro"
        self.interface.SetDeviceMountOptions("dev1", "")
        assert dev1.format.options == "defaults"

    def test_get_mount_point_constraints(self):
        """Test GetMountPointConstraints."""
        result = self.interface.GetMountPointConstraints()
        assert isinstance(result, list)
        assert len(result) == 2

        result = MountPointConstraintsData.from_structure_list(
            self.interface.GetMountPointConstraints()
        )
        for mp in result:
            assert mp.mount_point is not None
            assert mp.required_filesystem_type is not None

        # we are always adding / so it's a good candidate for testing
        root = next(r for r in result if r.mount_point == "/")
        assert root is not None
        assert root.encryption_allowed is True
        assert root.logical_volume_allowed is True
        assert root.mount_point == "/"
        assert root.required_filesystem_type == ""
        assert root.required is True
        assert root.recommended is False

    def test_get_required_mount_points(self):
        """Test GetRequiredMountPoints."""
        result = self.interface.GetRequiredMountPoints()
        assert isinstance(result, list)
        assert len(result) != 0

        result = MountPointConstraintsData.from_structure_list(
            self.interface.GetRequiredMountPoints()
        )
        for mp in result:
            assert mp.mount_point is not None
            assert mp.required_filesystem_type is not None

        # we are always adding / so it's a good candidate for testing
        root = next(r for r in result if r.mount_point == "/")
        assert root is not None
        assert root.encryption_allowed is True
        assert root.logical_volume_allowed is True
        assert root.mount_point == "/"
        assert root.required_filesystem_type == ""


class DeviceTreeTasksTestCase(unittest.TestCase):
    """Test the storage tasks."""

    def test_find_existing_systems(self):
        storage = create_storage()
        task = FindExistingSystemsTask(storage.devicetree)
        assert task.run() == []

    @patch('pyanaconda.modules.storage.devicetree.rescue.mount_existing_system')
    def test_mount_existing_system(self, mount):
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

    def test_find_devices(self):
        storage = Mock()

        task = FindDevicesTask(storage.devicetree)
        task.run()

        storage.devicetree.populate.assert_called_once_with()


class DeviceTreeUtilsTestCase(unittest.TestCase):
    """Test utilities for the device tree."""

    @patch.object(DeviceFormat, "formattable", new_callable=PropertyMock)
    @patch.object(DeviceFormat, "supported", new_callable=PropertyMock)
    def test_is_supported_filesystem(self, supported, formattable):
        """Test the is_supported_filesystem function."""
        supported.return_value = True
        formattable.return_value = False

        assert utils.is_supported_filesystem("xfs") is False

        supported.return_value = False
        formattable.return_value = True

        assert utils.is_supported_filesystem("xfs") is False

        supported.return_value = True
        formattable.return_value = True

        assert utils.is_supported_filesystem("xfs") is True
        assert utils.is_supported_filesystem("swap") is True
        assert utils.is_supported_filesystem("biosboot") is True

        assert utils.is_supported_filesystem("unknown") is False
        assert utils.is_supported_filesystem("disklabel") is False
        assert utils.is_supported_filesystem("ntfs") is False
        assert utils.is_supported_filesystem("tmpfs") is False

    def test_find_stage2_device(self):
        """Test the find_stage2_device function."""
        storage = create_storage()

        self._test_find_stage2_device(storage, "", None)
        self._test_find_stage2_device(storage, "stage2=http://test", None)
        self._test_find_stage2_device(storage, "stage2=hd:/dev/dev1", None)

        device = StorageDevice("dev1", fmt=get_format("ext4"))
        storage.devicetree._add_device(device)

        self._test_find_stage2_device(storage, "stage2=hd:dev1", device)
        self._test_find_stage2_device(storage, "stage2=hd:/dev/dev1", device)
        self._test_find_stage2_device(storage, "stage2=hd:/dev/dev1:/path", device)

    def _test_find_stage2_device(self, storage, cmdline, expected_device):
        """Call the find_stage2_device function and check its return value."""
        args = KernelArguments.from_string(cmdline)

        with patch("pyanaconda.modules.storage.devicetree.utils.kernel_arguments", args):
            return utils.find_stage2_device(storage.devicetree) == expected_device
