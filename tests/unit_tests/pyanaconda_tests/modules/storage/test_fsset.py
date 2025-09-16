#
# Copyright (C) 2021  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import tempfile
import unittest
from unittest.mock import patch

from blivet.devices import StorageDevice
from blivet.devicetree import DeviceTree
from blivet.formats import get_format

from pyanaconda.modules.storage.devicetree.fsset import FSSet
from pyanaconda.modules.storage.devicetree.root import _parse_fstab
from pyanaconda.modules.storage.platform import EFI, X86


class FSSetTestCase(unittest.TestCase):
    """Test the class that represents a set of filesystems."""

    def setUp(self):
        """Set up the test."""
        self.maxDiff = None
        self.devicetree = DeviceTree()
        self.fsset = FSSet(self.devicetree)

    def _add_device(self, device):
        """Add a device to the device tree."""
        self.devicetree._add_device(device)

    def _get_mount_points(self, devices):
        """Get mount points of the given devices."""
        return [getattr(d.format, "mountpoint", None) for d in devices]

    def _get_format_types(self, devices):
        """Get format types of the given devices."""
        return [d.format.type for d in devices]

    def test_system_filesystems(self):
        """Test the system_filesystems property."""
        devices = self.fsset.system_filesystems

        # There are some devices in the list.
        assert devices

        # The devices are always the same.
        assert devices == self.fsset.system_filesystems

    @patch("pyanaconda.modules.storage.devicetree.fsset.platform", X86())
    def test_collect_filesystems(self):
        """Test the collect_filesystems method."""
        devices = self.fsset.collect_filesystems()
        mount_points = self._get_mount_points(devices)
        format_types = self._get_format_types(devices)

        assert mount_points == [
            '/dev',
            '/dev/pts',
            '/dev/shm',
            '/proc',
            '/proc/bus/usb',
            '/run',
            '/sys',
            '/sys/fs/selinux',
            '/tmp',
        ]

        assert format_types == [
            'bind',
            'devpts',
            'tmpfs',
            'proc',
            'usbfs',
            'bind',
            'sysfs',
            'selinuxfs',
            'tmpfs',
        ]

    @patch("pyanaconda.modules.storage.devicetree.fsset.platform", EFI())
    def test_collect_filesystems_efi(self):
        """Test the collect_filesystems method with EFI."""
        devices = self.fsset.collect_filesystems()
        mount_points = self._get_mount_points(devices)
        format_types = self._get_format_types(devices)

        assert mount_points == [
            '/dev',
            '/dev/pts',
            '/dev/shm',
            '/proc',
            '/proc/bus/usb',
            '/run',
            '/sys',
            '/sys/firmware/efi/efivars',
            '/sys/fs/selinux',
            '/tmp',
        ]

        assert format_types == [
            'bind',
            'devpts',
            'tmpfs',
            'proc',
            'usbfs',
            'bind',
            'sysfs',
            'efivarfs',
            'selinuxfs',
            'tmpfs',
        ]

    @patch("pyanaconda.modules.storage.devicetree.fsset.platform", X86())
    def test_collect_filesystems_tmp(self):
        """Test the collect_filesystems method with /tmp."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/tmp")))

        devices = self.fsset.collect_filesystems()
        mount_points = self._get_mount_points(devices)
        format_types = self._get_format_types(devices)

        assert mount_points == [
            '/dev',
            '/dev/pts',
            '/dev/shm',
            '/proc',
            '/proc/bus/usb',
            '/run',
            '/sys',
            '/sys/fs/selinux',
            '/tmp',
        ]

        assert format_types == [
            'bind',
            'devpts',
            'tmpfs',
            'proc',
            'usbfs',
            'bind',
            'sysfs',
            'selinuxfs',
            'ext4',
        ]

    def test_swap_devices(self):
        """Test the swap_devices property"""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/boot")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev3", fmt=get_format("ext4", mountpoint="/home")))
        swap1 = StorageDevice("dev4", fmt=get_format("swap"))
        self._add_device(swap1)
        swap2 = StorageDevice("dev5", fmt=get_format("swap"))
        self._add_device(swap2)

        assert self.fsset.swap_devices == []

        self.fsset.add_fstab_swap(swap2)
        assert self.fsset.swap_devices == [swap2]

        self.fsset.set_fstab_swaps([swap1])
        assert self.fsset.swap_devices == [swap1]

    @patch("pyanaconda.modules.storage.devicetree.fsset.platform", X86())
    def test_collect_filesystems_extra(self):
        """Test the collect_filesystems method with additional devices."""
        self._add_device(StorageDevice("dev1", fmt=get_format("ext4", mountpoint="/boot")))
        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/")))
        self._add_device(StorageDevice("dev3", fmt=get_format("ext4", mountpoint="/home")))
        existing_swap = StorageDevice("dev4", fmt=get_format("swap"))
        self._add_device(existing_swap)
        reused_swap = StorageDevice("dev5", fmt=get_format("swap"))
        self._add_device(reused_swap)

        self.fsset.add_fstab_swap(reused_swap)
        devices = self.fsset.collect_filesystems()
        mount_points = self._get_mount_points(devices)
        format_types = self._get_format_types(devices)


        assert mount_points == [
            None,
            '/',
            '/boot',
            '/dev',
            '/dev/pts',
            '/dev/shm',
            '/home',
            '/proc',
            '/proc/bus/usb',
            '/run',
            '/sys',
            '/sys/fs/selinux',
            '/tmp',
        ]

        # Only one of the swap devices (the reused one) is collected
        assert format_types == [
            'swap',
            'ext4',
            'ext4',
            'bind',
            'devpts',
            'tmpfs',
            'ext4',
            'proc',
            'usbfs',
            'bind',
            'sysfs',
            'selinuxfs',
            'tmpfs',
        ]

    def test_parse_fstab(self):
        """ test the fsset.py parse_fstab method: unrecognized devices
            from fstab are supposed to be stored in preserve entries
            the rest of devices should stay in devicetree
        """

        UNRECOGNIZED_ENTRY = "UUID=111111 /mnt/fakemount ext3 defaults 0 0\n"
        DEVICE_ENTRY = "/dev/dev2 /mnt ext4 defaults 0 0\n"

        self._add_device(StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/")))

        with tempfile.TemporaryDirectory() as tmpdirname:
            fstab_path = os.path.join(tmpdirname, 'etc/fstab')
            os.makedirs(os.path.dirname(fstab_path), exist_ok=True)
            with open(fstab_path, "w") as f:
                f.write(UNRECOGNIZED_ENTRY)
                f.write(DEVICE_ENTRY)

            self.fsset.parse_fstab(chroot=tmpdirname)

        self.assertEqual(self.fsset.preserve_entries[0].file, "/mnt/fakemount")
        self.assertIsNotNone(self.devicetree.get_device_by_path('/dev/dev2'))

    def test_root_parse_fstab(self):
        """ test the root.py _parse_fstab function: return mounts and devices obtained from fstab
        """

        test_dev = StorageDevice("dev2", fmt=get_format("ext4", mountpoint="/mnt/testmount"))

        devicetree = DeviceTree()
        devicetree._add_device(test_dev)
        DEVICE_ENTRY = "/dev/dev2 /mnt/testmount ext4 defaults 0 0\n"

        with tempfile.TemporaryDirectory() as tmpdirname:
            fstab_path = os.path.join(tmpdirname, 'etc/fstab')
            os.makedirs(os.path.dirname(fstab_path), exist_ok=True)
            with open(fstab_path, "w") as f:
                f.write(DEVICE_ENTRY)

            mounts, devices, options = _parse_fstab(devicetree, chroot=tmpdirname)

        self.assertEqual(mounts["/mnt/testmount"], test_dev)
        self.assertTrue(test_dev in devices)
        self.assertEqual(options["/mnt/testmount"], "defaults")
