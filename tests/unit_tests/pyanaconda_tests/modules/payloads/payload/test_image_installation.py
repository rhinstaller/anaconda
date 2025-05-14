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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import tempfile
import time
import unittest
from unittest.mock import Mock, call, patch

from pyanaconda.core.path import join_paths
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.payloads.payload.live_image.installation_progress import (
    InstallationProgress,
)
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy_with_cache


class InstallationProgressTestCase(unittest.TestCase):
    """Test the installation progress of the image installation."""

    @patch("os.statvfs")
    @patch_dbus_get_proxy_with_cache
    def test_canceled_progress(self, proxy_getter, statvfs_mock):
        """Test the canceled installation progress."""
        callback = Mock()

        with tempfile.TemporaryDirectory() as sysroot:
            os.mkdir(join_paths(sysroot, "/boot"))
            os.mkdir(join_paths(sysroot, "/home"))

            device_tree = STORAGE.get_proxy(DEVICE_TREE)
            device_tree.GetMountPoints.return_value = {
                "/": "dev1",
                "/boot": "dev2",
                "/home": "dev3",
            }
            device_tree.GetDeviceData.return_value = DeviceData.to_structure(DeviceData())

            statvfs_mock.return_value = \
                Mock(f_frsize=1024, f_blocks=150, f_bfree=100)

            progress = InstallationProgress(
                sysroot=sysroot,
                callback=callback,
                installation_size=1024 * 100
            )

            with progress:
                time.sleep(2)

        expected = [
            call("Synchronizing writes to disk"),
            call("Installing software 0%")
        ]
        assert callback.call_args_list == expected

    @patch("time.sleep")
    @patch("os.statvfs")
    @patch_dbus_get_proxy_with_cache
    def test_finished_progress(self, proxy_getter, statvfs_mock, sleep_mock):
        """Test the finished installation progress."""
        callback = Mock()

        with tempfile.TemporaryDirectory() as sysroot:
            device_tree = STORAGE.get_proxy(DEVICE_TREE)
            device_tree.GetMountPoints.return_value = {
                "/": "dev1",
                "/boot": "dev2",
                "/home": "dev3",
            }
            device_tree.GetDeviceData.return_value = DeviceData.to_structure(DeviceData())

            statvfs_mock.side_effect = [
                Mock(f_frsize=1024, f_blocks=150, f_bfree=125),
                Mock(f_frsize=1024, f_blocks=150, f_bfree=100),
                Mock(f_frsize=1024, f_blocks=150, f_bfree=75),
                Mock(f_frsize=1024, f_blocks=150, f_bfree=45),
                Mock(f_frsize=1024, f_blocks=150, f_bfree=25),
                Mock(f_frsize=1024, f_blocks=150, f_bfree=0),
            ]

            progress = InstallationProgress(
                sysroot=sysroot,
                callback=callback,
                installation_size=1024 * 100
            )

            progress._monitor_progress()

        expected = [
            call("Synchronizing writes to disk"),
            call("Installing software 25%"),
            call("Installing software 50%"),
            call("Installing software 80%"),
            call("Installing software 100%"),
        ]
        assert callback.call_args_list == expected

    @patch_dbus_get_proxy_with_cache
    def test_btrfs_mountpoint_selection(self, proxy_getter):
        """Test installation progress calculation with btrfs."""

        def get_device_data(device):
            data = DeviceData()
            if device in ("root-btrfs-one", "home-btrfs-one"):
                data.type = "btrfs subvolume"
            elif device == "btrfs-one":
                data.type = "btrfs volume"
            return DeviceData.to_structure(data)

        def get_device_ancestors(devices):
            ancestors = {
                "root-btrfs-one": ["btrfs-one", "dev1-disk", "dev2-disk"],
                "dev2": ["dev2-disk"],
                "home-btrfs-one": ["dev1-disk", "dev2-disk", "btrfs-one"],
            }
            return ancestors[devices[0]]

        callback = Mock()

        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        device_tree.GetMountPoints.return_value = {
            "/": "root-btrfs-one",
            "/boot": "dev2",
            "/home": "home-btrfs-one",
        }
        device_tree.GetDeviceData = Mock(wraps=get_device_data)
        device_tree.GetAncestors = Mock(wraps=get_device_ancestors)

        progress = InstallationProgress(
            sysroot="/somewhere",
            callback=callback,
            installation_size=1024 * 100
        )

        mount_points = progress._get_mount_points_to_count()

        assert mount_points == [
            "/somewhere/",
            "/somewhere/boot",
        ]
