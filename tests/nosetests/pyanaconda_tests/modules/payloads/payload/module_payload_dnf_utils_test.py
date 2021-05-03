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
import unittest
from textwrap import dedent
from unittest.mock import patch, Mock

from blivet.size import Size

from pyanaconda.core.constants import GROUP_PACKAGE_TYPES_REQUIRED, GROUP_PACKAGE_TYPES_ALL
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.utils import get_kernel_package, \
    get_product_release_version, get_installation_specs, get_kernel_version_list, \
    pick_download_location, calculate_required_space, get_free_space_map, _pick_mount_points

from tests.nosetests.pyanaconda_tests import patch_dbus_get_proxy_with_cache


class DNFUtilsPackagesTestCase(unittest.TestCase):

    def get_kernel_package_excluded_test(self):
        """Test the get_kernel_package function with kernel excluded."""
        kernel = get_kernel_package(Mock(), exclude_list=["kernel"])
        self.assertEqual(kernel, None)

    def get_kernel_package_unavailable_test(self):
        """Test the get_kernel_package function with unavailable packages."""
        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.is_package_available.return_value = False

        with self.assertLogs(level="ERROR") as cm:
            kernel = get_kernel_package(dnf_manager, exclude_list=[])

        msg = "Failed to select a kernel"
        self.assertIn(msg, "\n".join(cm.output))
        self.assertEqual(kernel, None)

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.is_lpae_available")
    def get_kernel_package_lpae_test(self, is_lpae):
        """Test the get_kernel_package function with LPAE."""
        is_lpae.return_value = True

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.is_package_available.return_value = True

        kernel = get_kernel_package(dnf_manager, exclude_list=[])
        self.assertEqual(kernel, "kernel-lpae")

        kernel = get_kernel_package(dnf_manager, exclude_list=["kernel-lpae"])
        self.assertEqual(kernel, "kernel")

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.is_lpae_available")
    def get_kernel_package_test(self, is_lpae):
        """Test the get_kernel_package function."""
        is_lpae.return_value = False

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.is_package_available.return_value = True

        kernel = get_kernel_package(dnf_manager, exclude_list=[])
        self.assertEqual(kernel, "kernel")

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.productVersion", "invalid")
    def get_product_release_version_invalid_test(self):
        """Test the get_product_release_version function with an invalid value."""
        self.assertEqual(get_product_release_version(), "rawhide")

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.productVersion", "28")
    def get_product_release_version_number_test(self):
        """Test the get_product_release_version function with a valid number."""
        self.assertEqual(get_product_release_version(), "28")

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.productVersion", "7.4")
    def get_product_release_version_dot_test(self):
        """Test the get_product_release_version function with a dot."""
        self.assertEqual(get_product_release_version(), "7.4")

    def get_installation_specs_default_test(self):
        """Test the get_installation_specs function with defaults."""
        data = PackagesSelectionData()
        self.assertEqual(get_installation_specs(data), (["@core"], []))

    def get_installation_specs_nocore_test(self):
        """Test the get_installation_specs function without core."""
        data = PackagesSelectionData()
        data.core_group_enabled = False
        self.assertEqual(get_installation_specs(data), ([], ["@core"]))

    def get_installation_specs_environment_test(self):
        """Test the get_installation_specs function with environment."""
        data = PackagesSelectionData()
        data.environment = "environment-1"

        self.assertEqual(get_installation_specs(data), (
            ["@environment-1", "@core"], []
        ))

        env = "environment-2"
        self.assertEqual(get_installation_specs(data, default_environment=env), (
            ["@environment-1", "@core"], []
        ))

        data.default_environment_enabled = True
        self.assertEqual(get_installation_specs(data, default_environment=env), (
            ["@environment-2", "@core"], []
        ))

    def get_installation_specs_packages_test(self):
        """Test the get_installation_specs function with packages."""
        data = PackagesSelectionData()
        data.packages = ["p1", "p2", "p3"]
        data.excluded_packages = ["p4", "p5", "p6"]

        self.assertEqual(get_installation_specs(data), (
            ["@core", "p1", "p2", "p3"], ["p4", "p5", "p6"]
        ))

    def get_installation_specs_groups_test(self):
        """Test the get_installation_specs function with groups."""
        data = PackagesSelectionData()

        data.groups = ["g1", "g2", "g3"]
        data.excluded_groups = ["g4", "g5", "g6"]
        data.groups_package_types = {
            "g1": GROUP_PACKAGE_TYPES_REQUIRED,
            "g3": GROUP_PACKAGE_TYPES_ALL,
            "g4": GROUP_PACKAGE_TYPES_REQUIRED,
            "g6": GROUP_PACKAGE_TYPES_ALL,
        }

        self.assertEqual(get_installation_specs(data), (
            [
                "@core",
                "@g1/mandatory,conditional",
                "@g2",
                "@g3/mandatory,default,conditional,optional"],
            [
                "@g4",
                "@g5",
                "@g6"
            ]
        ))

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.rpm")
    def get_kernel_version_list_test(self, mock_rpm):
        """Test the get_kernel_version_list function."""
        hdr_1 = Mock(filenames=[
            "/boot/vmlinuz-0-rescue-dbe69c1b88f94a67b689e3f44b0550c8"
            "/boot/vmlinuz-5.8.15-201.fc32.x86_64",
            "/boot/efi/EFI/default/vmlinuz-6.8.15-201.fc32.x86_64",
        ])

        hdr_2 = Mock(filenames=[
            "/boot/vmlinuz-5.8.16-200.fc32.x86_64",
            "/boot/efi/EFI/default/vmlinuz-7.8.16-200.fc32.x86_64",
            "/boot/vmlinuz-5.8.18-200.fc32.x86_64"
            "/boot/efi/EFI/default/vmlinuz-8.8.18-200.fc32.x86_64"
        ])

        ts = Mock()
        ts.dbMatch.return_value = [hdr_1, hdr_2]

        mock_rpm.TransactionSet.return_value = ts
        self.assertEqual(get_kernel_version_list(), [
            '5.8.15-201.fc32.x86_64',
            '5.8.16-200.fc32.x86_64',
            '6.8.15-201.fc32.x86_64',
            '7.8.16-200.fc32.x86_64',
            '8.8.18-200.fc32.x86_64'
        ])

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.execWithCapture")
    def get_free_space_test(self, exec_mock):
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

        self.assertEqual(get_free_space_map(), {
            '/dev': Size("100 KiB"),
            '/dev/shm': Size("200 KiB"),
            '/run': Size("300 KiB"),
            '/': Size("400 KiB"),
            '/tmp': Size("500 KiB"),
            '/boot': Size("600 KiB"),
            '/home': Size("700 KiB"),
            '/boot/efi': Size("800 KiB"),
        })

    @patch("os.statvfs")
    @patch("pyanaconda.modules.payloads.payload.dnf.utils.conf")
    @patch("pyanaconda.modules.payloads.payload.dnf.utils.execWithCapture")
    def get_free_space_image_test(self, exec_mock, conf_mock, statvfs_mock):
        """Test the get_free_space function."""
        output = """
        Mounted on        Avail
        /                   100
        /boot               200
        """
        exec_mock.return_value = dedent(output).strip()
        conf_mock.target.is_hardware = False
        statvfs_mock.return_value = Mock(f_frsize=1024, f_bfree=300)

        self.assertEqual(get_free_space_map(), {
            '/': Size("100 KiB"),
            '/boot': Size("200 KiB"),
            '/var/tmp': Size("300 KiB"),
        })

    def pick_mount_points_test(self):
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
        self.assertEqual(sufficient, {
            "/var/tmp",
            "/mnt/sysroot",
            "/mnt/sysroot/home",
            "/mnt/sysroot/tmp",
            "/mnt/sysroot/var"
        })

        # No mount point is big enough for installation.
        # Choose non-sysroot mount points for download.
        sufficient = _pick_mount_points(
            mount_points,
            download_size=Size("0.5 G"),
            install_size=Size("1.5 G")
        )
        self.assertEqual(sufficient, {
            "/var/tmp",
        })

        # No mount point is big enough for installation or download.
        sufficient = _pick_mount_points(
            mount_points,
            download_size=Size("1.5 G"),
            install_size=Size("1.5 G")
        )
        self.assertEqual(sufficient, set())

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.get_free_space_map")
    def pick_download_location_test(self, free_space_getter):
        """Test the pick_download_location function."""
        download_size = Size(100)
        installation_size = Size(200)
        total_size = Size(300)

        dnf_manager = Mock()
        dnf_manager.get_download_size.return_value = download_size
        dnf_manager.get_installation_size.return_value = installation_size

        # Found mount points for download and install.
        # Don't use /mnt/sysroot if possible.
        free_space_getter.return_value = {
            "/var/tmp": download_size,
            "/mnt/sysroot": total_size,
        }

        path = pick_download_location(dnf_manager)
        self.assertEqual(path, "/var/tmp/dnf.package.cache")

        # Found mount points only for download.
        # Use the biggest mount point.
        free_space_getter.return_value = {
            "/mnt/sysroot/tmp": download_size + 1,
            "/mnt/sysroot/home": download_size,
        }

        path = pick_download_location(dnf_manager)
        self.assertEqual(path, "/mnt/sysroot/tmp/dnf.package.cache")

        # No mount point to use.
        # Fail with an exception.
        free_space_getter.return_value = {}

        with self.assertRaises(RuntimeError) as cm:
            pick_download_location(dnf_manager)

        msg = "Not enough disk space to download the packages; size 100 B."
        self.assertEqual(str(cm.exception), msg)

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.execWithCapture")
    @patch_dbus_get_proxy_with_cache
    def get_combined_free_space_test(self, proxy_getter, exec_mock):
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

        self.assertEqual(get_free_space_map(current=True, scheduled=False), {
            '/': Size("100 KiB"),
            '/tmp': Size("200 KiB"),
        })

        self.assertEqual(get_free_space_map(current=False, scheduled=True), {
            '/mnt/sysroot': Size("300 KiB"),
            '/mnt/sysroot/boot': Size("400 KiB"),
        })

        self.assertEqual(get_free_space_map(current=True, scheduled=True), {
            '/': Size("100 KiB"),
            '/tmp': Size("200 KiB"),
            '/mnt/sysroot': Size("300 KiB"),
            '/mnt/sysroot/boot': Size("400 KiB"),
        })

        self.assertEqual(get_free_space_map(current=False, scheduled=False), {})

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.get_free_space_map")
    def calculate_required_space_test(self, free_space_getter):
        """Test the calculate_required_space function."""
        download_size = Size(100)
        installation_size = Size(200)
        total_size = Size(300)

        dnf_manager = Mock()
        dnf_manager.get_download_size.return_value = download_size
        dnf_manager.get_installation_size.return_value = installation_size

        # No mount point to use.
        # The total size is required.
        free_space_getter.return_value = {}
        self.assertEqual(calculate_required_space(dnf_manager), total_size)

        # Found a mount point for download and install.
        # The total size is required.
        free_space_getter.return_value = {
            "/mnt/sysroot/home": total_size
        }
        self.assertEqual(calculate_required_space(dnf_manager), total_size)

        # Found a mount point for download.
        # The installation size is required.
        free_space_getter.return_value = {
            "/var/tmp": download_size
        }
        self.assertEqual(calculate_required_space(dnf_manager), installation_size)

        # The biggest mount point can be used for download and install.
        # The total size is required.
        free_space_getter.return_value = {
            "/var/tmp": download_size,
            "/mnt/sysroot": total_size
        }
        self.assertEqual(calculate_required_space(dnf_manager), total_size)
