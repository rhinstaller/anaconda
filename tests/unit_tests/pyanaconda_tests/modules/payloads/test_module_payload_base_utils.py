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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from textwrap import dedent
from unittest.case import TestCase
from unittest.mock import Mock, patch

import pytest
from blivet.size import Size

from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.payloads.base.utils import (
    _pick_mount_points,
    calculate_required_space,
    get_free_space_map,
    pick_download_location,
    sort_kernel_version_list,
)
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy_with_cache


class PayloadBaseUtilsTest(TestCase):
    def test_sort_kernel_version_list(self):
        """Test the sort_kernel_version_list function."""
        # Test fake versions.
        kernel_version_list = [
            '9.1.1-100.f1',
            '10.1.1-100.f1',
            '1.9.1-100.f1',
            '1.10.1-100.f1',
            '1.1.9-100.f1',
            '1.1.10-100.f1',
            '1.1.1-999.f1',
            '1.1.1-1000.f1',
            '1.1.1-100.f1',
            '1.1.1-100.f2',
        ]

        sort_kernel_version_list(kernel_version_list)
        assert kernel_version_list == [
            '1.1.1-100.f1',
            '1.1.1-100.f2',
            '1.1.1-999.f1',
            '1.1.1-1000.f1',
            '1.1.9-100.f1',
            '1.1.10-100.f1',
            '1.9.1-100.f1',
            '1.10.1-100.f1',
            '9.1.1-100.f1',
            '10.1.1-100.f1'
        ]

        # Test real versions.
        kernel_version_list = [
            '5.8.16-200.fc32.x86_64',
            '5.8.18-200.fc32.x86_64',
            '5.10.0-0.rc4.78.fc34.x86_64',
            '5.9.8-100.fc33.x86_64',
            '5.8.18-300.fc33.x86_64',
            '5.8.15-201.fc32.x86_64',
            '5.9.8-200.fc33.x86_64',
        ]

        sort_kernel_version_list(kernel_version_list)
        assert kernel_version_list == [
            '5.8.15-201.fc32.x86_64',
            '5.8.16-200.fc32.x86_64',
            '5.8.18-200.fc32.x86_64',
            '5.8.18-300.fc33.x86_64',
            '5.9.8-100.fc33.x86_64',
            '5.9.8-200.fc33.x86_64',
            '5.10.0-0.rc4.78.fc34.x86_64'
        ]

    @patch("pyanaconda.modules.payloads.base.utils.get_free_space_map")
    def test_pick_download_location(self, free_space_getter):
        """Test the pick_download_location function."""
        download_size = Size(100)
        installation_size = Size(200)
        total_size = Size(300)

        # Found mount points for download and install.
        # Don't use /mnt/sysroot if possible.
        free_space_getter.return_value = {
            "/var/tmp": download_size,
            "/mnt/sysroot": total_size,
        }

        path = pick_download_location(download_size, installation_size, "TEST_SUFFIX")
        assert path == "/var/tmp/TEST_SUFFIX"

        # Found mount points only for download.
        # Use the biggest mount point.
        free_space_getter.return_value = {
            "/mnt/sysroot/tmp": download_size + 1,
            "/mnt/sysroot/home": download_size,
        }

        path = pick_download_location(download_size, installation_size, "TEST_SUFFIX")
        assert path == "/mnt/sysroot/tmp/TEST_SUFFIX"

        # No mount point to use.
        # Fail with an exception.
        free_space_getter.return_value = {}

        with pytest.raises(RuntimeError) as cm:
            pick_download_location(download_size, installation_size, "TEST_SUFFIX")

        msg = "Not enough disk space to download the packages; size 100 B."
        assert str(cm.value) == msg

    @patch("pyanaconda.modules.payloads.base.utils.execWithCapture")
    def test_get_free_space(self, exec_mock):
        """Test the get_free_space function."""
        output = """
        Mounted on        Avail
        /dev                100
        /dev/shm            200
        /run                300
        /                   400
        /tmp                500
        /boot               600
        /home               700
        /boot/efi           800
        """
        exec_mock.return_value = dedent(output).strip()

        assert get_free_space_map() == {
            '/dev': Size("100 KiB"),
            '/dev/shm': Size("200 KiB"),
            '/run': Size("300 KiB"),
            '/': Size("400 KiB"),
            '/tmp': Size("500 KiB"),
            '/boot': Size("600 KiB"),
            '/home': Size("700 KiB"),
            '/boot/efi': Size("800 KiB"),
        }

    @patch("os.statvfs")
    @patch("pyanaconda.modules.payloads.base.utils.conf")
    @patch("pyanaconda.modules.payloads.base.utils.execWithCapture")
    def test_get_free_space_image(self, exec_mock, conf_mock, statvfs_mock):
        """Test the get_free_space function."""
        output = """
        Mounted on        Avail
        /                   100
        /boot               200
        """
        exec_mock.return_value = dedent(output).strip()
        conf_mock.target.is_hardware = False
        statvfs_mock.return_value = Mock(f_frsize=1024, f_bfree=300)

        assert get_free_space_map() == {
            '/': Size("100 KiB"),
            '/boot': Size("200 KiB"),
            '/var/tmp': Size("300 KiB"),
        }

    def test_pick_mount_points(self):
        """Test the _pick_mount_points function."""
        mount_points = {
            "/": Size("1 G"),
            "/home": Size("1 G"),
            "/var/tmp": Size("1 G"),
            "/mnt/sysroot": Size("1 G"),
            "/mnt/sysroot/home": Size("1 G"),
            "/mnt/sysroot/tmp": Size("1 G"),
            "/mnt/sysroot/var": Size("1 G"),
            "/mnt/sysroot/usr": Size("1 G"),

        }

        # All mount points are big enough.
        # Choose all suitable mount points.
        sufficient = _pick_mount_points(
            mount_points,
            download_size=Size("0.5 G"),
            install_size=Size("0.5 G")
        )
        assert sufficient == {
            "/var/tmp",
            "/mnt/sysroot",
            "/mnt/sysroot/home",
            "/mnt/sysroot/tmp",
            "/mnt/sysroot/var"
        }

        # No mount point is big enough for installation.
        # Choose non-sysroot mount points for download.
        sufficient = _pick_mount_points(
            mount_points,
            download_size=Size("0.5 G"),
            install_size=Size("1.5 G")
        )
        assert sufficient == {
            "/var/tmp",
        }

        # No mount point is big enough for installation or download.
        sufficient = _pick_mount_points(
            mount_points,
            download_size=Size("1.5 G"),
            install_size=Size("1.5 G")
        )
        assert sufficient == set()

    @patch("pyanaconda.modules.payloads.base.utils.execWithCapture")
    @patch_dbus_get_proxy_with_cache
    def test_get_combined_free_space(self, proxy_getter, exec_mock):
        """Test the get_free_space function with the combined options."""
        output = """
        Mounted on        Avail
        /                   100
        /tmp                200
        """
        exec_mock.return_value = dedent(output).strip()

        mount_points = {
            '/': Size("300 KiB"),
            '/boot': Size("400 KiB"),
        }

        def get_mount_points():
            return list(mount_points.keys())

        def get_free_space(paths):
            return sum(map(mount_points.get, paths))

        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        device_tree.GetMountPoints.side_effect = get_mount_points
        device_tree.GetFileSystemFreeSpace.side_effect = get_free_space

        assert get_free_space_map(current=True, scheduled=False) == {
            '/': Size("100 KiB"),
            '/tmp': Size("200 KiB"),
        }

        assert get_free_space_map(current=False, scheduled=True) == {
            '/mnt/sysroot': Size("300 KiB"),
            '/mnt/sysroot/boot': Size("400 KiB"),
        }

        assert get_free_space_map(current=True, scheduled=True) == {
            '/': Size("100 KiB"),
            '/tmp': Size("200 KiB"),
            '/mnt/sysroot': Size("300 KiB"),
            '/mnt/sysroot/boot': Size("400 KiB"),
        }

        assert get_free_space_map(current=False, scheduled=False) == {}

    @patch("pyanaconda.modules.payloads.base.utils.get_free_space_map")
    def test_calculate_required_space(self, free_space_getter):
        """Test the calculate_required_space function."""
        download_size = Size(100)
        installation_size = Size(200)
        total_size = Size(300)

        # No mount point to use.
        # The total size is required.
        free_space_getter.return_value = {}
        assert calculate_required_space(download_size, installation_size) == total_size

        # Found a mount point for download and install.
        # The total size is required.
        free_space_getter.return_value = {
            "/mnt/sysroot/home": total_size
        }
        assert calculate_required_space(download_size, installation_size) == total_size

        # Found a mount point for download.
        # The installation size is required.
        free_space_getter.return_value = {
            "/var/tmp": download_size
        }
        assert calculate_required_space(download_size, installation_size) == installation_size

        # The biggest mount point can be used for download and install.
        # The total size is required.
        free_space_getter.return_value = {
            "/var/tmp": download_size,
            "/mnt/sysroot": total_size
        }
        assert calculate_required_space(download_size, installation_size) == total_size
