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
from unittest.mock import patch

from blivet.devices import StorageDevice, DiskDevice, DASDDevice, ZFCPDiskDevice, PartitionDevice, \
    LUKSDevice
from blivet.errors import StorageError
from blivet.formats import get_format
from blivet.formats.fs import FS
from blivet.formats.luks import LUKS
from blivet.size import Size

from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.errors.storage import UnknownDeviceError
from pyanaconda.modules.storage.devicetree import DeviceTreeModule
from pyanaconda.modules.storage.devicetree.devicetree_interface import DeviceTreeInterface
from pyanaconda.storage.initialization import create_storage


class DeviceTreeInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the device tree handler."""

    def setUp(self):
        self.module = DeviceTreeModule()
        self.interface = DeviceTreeInterface(self.module)

        # Set the storage.
        self.module.on_storage_reset(create_storage())

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

        self._add_device(DiskDevice("dev1", fmt=get_format("ext4")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4")))

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
