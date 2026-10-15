#
# Copyright (C) 2026  Red Hat, Inc.
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
from unittest.mock import Mock, patch

from blivet.errors import FSError

from pyanaconda.modules.storage.devicetree.root import (
    _mount_system_filesystems_into_chroot,
    mount_existing_system,
)


def _make_system_fs_device(mountpoint):
    """Build a mock system filesystem device."""
    device = Mock()
    device.format.mountable = True
    device.format.mountpoint = mountpoint
    device.format.setup = Mock()
    return device


class MountSystemFilesystemsIntoChrootTestCase(unittest.TestCase):
    """Test mounting blivet system filesystems into a nested chroot."""

    def test_mount_system_filesystems_into_chroot(self):
        """Call format.setup(chroot=...) for each mountable system filesystem."""
        proc = _make_system_fs_device("/proc")
        sysfs = _make_system_fs_device("/sys")
        skipped = Mock()
        skipped.format.mountable = False
        skipped.format.mountpoint = "/nowhere"

        storage = Mock()
        storage.fsset.system_filesystems = [proc, sysfs, skipped]

        _mount_system_filesystems_into_chroot(storage, "/mnt/sysroot/deploy")

        proc.format.setup.assert_called_once_with(chroot="/mnt/sysroot/deploy")
        sysfs.format.setup.assert_called_once_with(chroot="/mnt/sysroot/deploy")
        skipped.format.setup.assert_not_called()

    def test_mount_system_filesystems_logs_failures(self):
        """Continue mounting remaining devices if one setup fails."""
        proc = _make_system_fs_device("/proc")
        proc.format.setup.side_effect = FSError("boom")
        sysfs = _make_system_fs_device("/sys")

        storage = Mock()
        storage.fsset.system_filesystems = [proc, sysfs]

        _mount_system_filesystems_into_chroot(storage, "/mnt/sysroot/deploy")

        sysfs.format.setup.assert_called_once_with(chroot="/mnt/sysroot/deploy")


class MountExistingSystemOSTreeTestCase(unittest.TestCase):
    """Test rescue mounting of OSTree deployments (RHEL-253218)."""

    @patch("pyanaconda.modules.storage.devicetree.root._mount_system_filesystems_into_chroot")
    @patch("pyanaconda.modules.storage.devicetree.root.set_system_root")
    @patch("pyanaconda.modules.storage.devicetree.root.conf")
    def test_mount_existing_system_mounts_system_fs_into_deployment(
            self, conf_mock, set_root_mock, mount_sysfs_mock):
        """Rescue must mount system filesystems into the deployment path."""
        with tempfile.TemporaryDirectory() as physical:
            deployment = os.path.join(
                physical,
                "ostree",
                "deploy",
                "default",
                "deploy",
                "deadbeef.0",
            )
            os.makedirs(os.path.join(deployment, "etc"))
            with open(os.path.join(deployment, "etc", "fstab"), "w", encoding="utf-8") as f:
                f.write("# empty fstab for test\n")

            conf_mock.target.physical_root = physical
            conf_mock.target.system_root = "/mnt/sysroot"
            conf_mock.target.is_image = False

            root_device = Mock()
            root_device.protected = False
            root_device.format.options = "defaults"
            root_device.format.mount = Mock()

            storage = Mock()
            storage.fsset.parse_fstab = Mock()
            storage.fsset.mount_filesystems = Mock()
            storage.fsset.turn_on_swap = Mock()

            mount_existing_system(storage, root_device, read_only=False)

            set_root_mock.assert_any_call(deployment)
            storage.fsset.mount_filesystems.assert_called_once_with(
                root_path=physical,
                read_only="",
                skip_root=True,
            )
            mount_sysfs_mock.assert_called_once_with(storage, deployment)

    @patch("pyanaconda.modules.storage.devicetree.root._mount_system_filesystems_into_chroot")
    @patch("pyanaconda.modules.storage.devicetree.root.set_system_root")
    @patch("pyanaconda.modules.storage.devicetree.root.conf")
    def test_mount_existing_system_skips_system_fs_for_rpm(
            self, conf_mock, set_root_mock, mount_sysfs_mock):
        """Traditional RPM roots do not remount system filesystems into a nest."""
        with tempfile.TemporaryDirectory() as physical:
            os.makedirs(os.path.join(physical, "etc"))
            with open(os.path.join(physical, "etc", "fstab"), "w", encoding="utf-8") as f:
                f.write("# empty fstab for test\n")

            conf_mock.target.physical_root = physical
            conf_mock.target.system_root = "/mnt/sysroot"
            conf_mock.target.is_image = False

            root_device = Mock()
            root_device.protected = False
            root_device.format.options = "defaults"
            root_device.format.mount = Mock()

            storage = Mock()
            storage.fsset.parse_fstab = Mock()
            storage.fsset.mount_filesystems = Mock()
            storage.fsset.turn_on_swap = Mock()

            mount_existing_system(storage, root_device, read_only=False)

            mount_sysfs_mock.assert_not_called()
