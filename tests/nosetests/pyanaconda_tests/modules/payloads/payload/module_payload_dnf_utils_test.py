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
from unittest.mock import patch, Mock, PropertyMock

from blivet.size import Size

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import GROUP_PACKAGE_TYPES_REQUIRED, GROUP_PACKAGE_TYPES_ALL
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.utils import get_kernel_package, \
    get_product_release_version, get_default_environment, get_installation_specs, \
    get_kernel_version_list, pick_mount_point, get_df_map, pick_download_location, \
    calculate_required_space, get_sysroot_df_map

from tests.nosetests.pyanaconda_tests import patch_dbus_get_proxy_with_cache


class DNFUtilsPackagesTestCase(unittest.TestCase):

    def get_kernel_package_excluded_test(self):
        """Test the get_kernel_package function with kernel excluded."""
        kernel = get_kernel_package(dnf_base=Mock(), exclude_list=["kernel"])
        self.assertEqual(kernel, None)

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.dnf")
    def get_kernel_package_installable_test(self, mock_dnf):
        """Test the get_kernel_package function without installable packages."""
        subject = mock_dnf.subject.Subject.return_value
        subject.get_best_query.return_value = False

        with self.assertLogs(level="ERROR") as cm:
            kernel = get_kernel_package(dnf_base=Mock(), exclude_list=[])

        msg = "kernel: failed to select a kernel"
        self.assertTrue(any(map(lambda x: msg in x, cm.output)))
        self.assertEqual(kernel, None)

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.dnf")
    @patch("pyanaconda.modules.payloads.payload.dnf.utils.is_lpae_available")
    def get_kernel_package_lpae_test(self, is_lpae, mock_dnf):
        """Test the get_kernel_package function with LPAE."""
        subject = mock_dnf.subject.Subject.return_value
        subject.get_best_query.return_value = True
        is_lpae.return_value = True

        kernel = get_kernel_package(dnf_base=Mock(), exclude_list=[])
        self.assertEqual(kernel, "kernel-lpae")

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.dnf")
    @patch("pyanaconda.modules.payloads.payload.dnf.utils.is_lpae_available")
    def get_kernel_package_test(self, is_lpae, mock_dnf):
        """Test the get_kernel_package function."""
        subject = mock_dnf.subject.Subject.return_value
        subject.get_best_query.return_value = True
        is_lpae.return_value = False

        kernel = get_kernel_package(dnf_base=Mock(), exclude_list=[])
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

    @patch.object(DNFManager, 'environments', new_callable=PropertyMock)
    def get_default_environment_test(self, mock_environments):
        """Test the get_default_environment function"""
        mock_environments.return_value = []
        self.assertEqual(get_default_environment(DNFManager()), None)

        mock_environments.return_value = [
            "environment-1",
            "environment-2",
            "environment-3",
        ]
        self.assertEqual(get_default_environment(DNFManager()), "environment-1")

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
    def get_df_map_test(self, exec_mock):
        """Test the get_df_map function."""
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

        self.assertEqual(get_df_map(), {
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
    def get_df_map_image_test(self, exec_mock, conf_mock, statvfs_mock):
        """Test the get_df_map function."""
        output = """
        Mounted on        Avail
        /                   100
        /boot               200
        """
        exec_mock.return_value = dedent(output).strip()
        conf_mock.target.is_hardware = False
        statvfs_mock.return_value = Mock(f_frsize=1024, f_bfree=300)

        self.assertEqual(get_df_map(), {
            '/': Size("100 KiB"),
            '/boot': Size("200 KiB"),
            '/var/tmp': Size("300 KiB"),
        })

    def pick_mount_point_download_only_test(self):
        """Test the pick_mount_point function for download only."""
        df_map = {
            "/mnt/sysroot/not_used": Size("20 G"),
            "/mnt/sysroot/home": Size("2 G"),
            "/mnt/sysroot": Size("5 G")
        }

        # Choose the biggest mount point that can be used for download.
        path = pick_mount_point(
            df_map,
            download_size=Size("1.5 G"),
            install_size=Size("1.8 G"),
            download_only=True
        )
        self.assertEqual(path, "/mnt/sysroot/home")

        # Choose the root, because there are no other available
        # mount points. Even when the root isn't big enough.
        path = pick_mount_point(
            df_map,
            download_size=Size("2.5 G"),
            install_size=Size("3.0 G"),
            download_only=True
        )
        self.assertEqual(path, "/mnt/sysroot")

    def pick_mount_point_test(self):
        """Test the pick_mount_point function."""
        df_map = {
            "/mnt/sysroot/not_used": Size("20 G"),
            "/mnt/sysroot/home": Size("2 G"),
            "/mnt/sysroot": Size("6 G")
        }

        # Choose the root.
        path = pick_mount_point(
            df_map,
            download_size=Size("1.5 G"),
            install_size=Size("3 G"),
            download_only=False
        )
        self.assertEqual(path, "/mnt/sysroot")

        # No suitable location is found.
        path = pick_mount_point(
            df_map,
            download_size=Size("2.5 G"),
            install_size=Size("5 G"),
            download_only=False
        )
        self.assertEqual(path, None)

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.pick_mount_point")
    def pick_download_location_test(self, mount_point_picker):
        """Test the pick_download_location function."""
        mount_point_picker.return_value = "/my/download/path"
        path = pick_download_location(Mock())
        self.assertEqual(path, "/my/download/path/dnf.package.cache")

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.pick_mount_point")
    def pick_download_location_failed_test(self, mount_point_picker):
        """Test the failed pick_download_location function."""
        mount_point_picker.return_value = None

        dnf_manager = Mock()
        dnf_manager.get_download_size.return_value = Size(100)

        with self.assertRaises(RuntimeError) as cm:
            pick_download_location(dnf_manager)

        msg = "Not enough disk space to download the packages; size 100 B."
        self.assertEqual(str(cm.exception), msg)

    @patch_dbus_get_proxy_with_cache
    def get_sysroot_df_map_test(self, proxy_getter):
        """Test the get_sysroot_df_map function."""
        mount_points = {
            '/': Size("100 KiB"),
            '/boot': Size("200 KiB"),
            '/home': Size("300 KiB"),
        }

        def get_mount_points():
            return list(mount_points.keys())

        def get_free_space(paths):
            return sum(map(mount_points.get, paths))

        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        device_tree.GetMountPoints.side_effect = get_mount_points
        device_tree.GetFileSystemFreeSpace.side_effect = get_free_space

        self.assertEqual(get_sysroot_df_map(), {
            '/mnt/sysroot': Size("100 KiB"),
            '/mnt/sysroot/boot': Size("200 KiB"),
            '/mnt/sysroot/home': Size("300 KiB"),
        })

    @patch_dbus_get_proxy_with_cache
    @patch("pyanaconda.modules.payloads.payload.dnf.utils.pick_mount_point")
    def calculate_required_space_test(self, mount_point_picker, proxy_getter):
        """Test the calculate_required_space function."""
        download_size = Size(100)
        installation_size = Size(200)
        total_size = Size(300)

        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        device_tree.GetMountPoints.return_value = {}

        dnf_manager = Mock()
        dnf_manager.get_download_size.return_value = download_size
        dnf_manager.get_installation_size.return_value = installation_size

        mount_point_picker.return_value = None
        self.assertEqual(calculate_required_space(dnf_manager), total_size)

        mount_point_picker.return_value = conf.target.system_root
        self.assertEqual(calculate_required_space(dnf_manager), total_size)

        mount_point_picker.return_value = "/my/path"
        self.assertEqual(calculate_required_space(dnf_manager), installation_size)
