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
from unittest.mock import Mock, patch

from pyanaconda.core.constants import (
    GROUP_PACKAGE_TYPES_ALL,
    GROUP_PACKAGE_TYPES_REQUIRED,
)
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.utils import (
    collect_installation_devices,
    get_installation_specs,
    get_kernel_package,
    get_kernel_version_list,
    get_product_release_version,
)
from pyanaconda.modules.payloads.source.cdrom.cdrom import CdromSourceModule
from pyanaconda.modules.payloads.source.harddrive.harddrive import HardDriveSourceModule
from pyanaconda.modules.payloads.source.url.url import URLSourceModule


class DNFUtilsPackagesTestCase(unittest.TestCase):

    def test_get_kernel_package_excluded(self):
        """Test the get_kernel_package function with kernel excluded."""
        kernel = get_kernel_package(Mock(), exclude_list=["kernel"])
        assert kernel is None

    def test_get_kernel_package_unavailable(self):
        """Test the get_kernel_package function with unavailable packages."""
        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.is_package_available.return_value = False

        with self.assertLogs(level="ERROR") as cm:
            kernel = get_kernel_package(dnf_manager, exclude_list=[])

        msg = "Failed to select a kernel"
        assert msg in "\n".join(cm.output)
        assert kernel is None

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.is_lpae_available")
    def test_get_kernel_package_lpae(self, is_lpae):
        """Test the get_kernel_package function with LPAE."""
        is_lpae.return_value = True

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.is_package_available.return_value = True

        kernel = get_kernel_package(dnf_manager, exclude_list=[])
        assert kernel == "kernel-lpae"

        kernel = get_kernel_package(dnf_manager, exclude_list=["kernel-lpae"])
        assert kernel == "kernel"

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.is_lpae_available")
    def test_get_kernel_package(self, is_lpae):
        """Test the get_kernel_package function."""
        is_lpae.return_value = False

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.is_package_available.return_value = True

        kernel = get_kernel_package(dnf_manager, exclude_list=[])
        assert kernel == "kernel"

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.get_product_version",
           return_value="invalid")
    def test_get_product_release_version_invalid(self, version_mock):
        """Test the get_product_release_version function with an invalid value."""
        assert get_product_release_version() == "rawhide"

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.get_product_version", return_value="28")
    def test_get_product_release_version_number(self, version_mock):
        """Test the get_product_release_version function with a valid number."""
        assert get_product_release_version() == "28"

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.get_product_version",
           return_value="7.4")
    def test_get_product_release_version_dot(self, version_mock):
        """Test the get_product_release_version function with a dot."""
        assert get_product_release_version() == "7.4"

    def test_get_installation_specs_default(self):
        """Test the get_installation_specs function with defaults."""
        data = PackagesSelectionData()
        assert get_installation_specs(data) == (["@core"], [])

    def test_get_installation_specs_nocore(self):
        """Test the get_installation_specs function without core."""
        data = PackagesSelectionData()
        data.core_group_enabled = False
        assert get_installation_specs(data) == ([], ["@core"])

    def test_get_installation_specs_environment(self):
        """Test the get_installation_specs function with environment."""
        data = PackagesSelectionData()
        data.environment = "environment-1"

        assert get_installation_specs(data) == (
            ["@environment-1", "@core"], []
        )

        env = "environment-2"
        assert get_installation_specs(data, default_environment=env) == (
            ["@environment-1", "@core"], []
        )

        data.default_environment_enabled = True
        assert get_installation_specs(data, default_environment=env) == (
            ["@environment-2", "@core"], []
        )

    def test_get_installation_specs_packages(self):
        """Test the get_installation_specs function with packages."""
        data = PackagesSelectionData()
        data.packages = ["p1", "p2", "p3"]
        data.excluded_packages = ["p4", "p5", "p6"]

        assert get_installation_specs(data) == (
            ["@core", "p1", "p2", "p3"], ["p4", "p5", "p6"]
        )

    def test_get_installation_specs_groups(self):
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

        assert get_installation_specs(data) == (
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
        )

    @patch("pyanaconda.modules.payloads.payload.dnf.utils.rpm")
    def test_get_kernel_version_list(self, mock_rpm):
        """Test the get_kernel_version_list function."""
        hdr_1 = Mock(filenames=[
            "/boot/vmlinuz-0-rescue-dbe69c1b88f94a67b689e3f44b0550c8",
            "/boot/vmlinuz-5.8.15-201.fc32.x86_64",
            "/boot/efi/EFI/default/vmlinuz-6.8.15-201.fc32.x86_64",
        ])

        hdr_2 = Mock(filenames=[
            "/boot/vmlinuz-5.8.16-200.fc32.x86_64",
            "/boot/efi/EFI/default/vmlinuz-7.8.16-200.fc32.x86_64",
            "/boot/vmlinuz-5.8.18-200.fc32.x86_64",
            "/boot/efi/EFI/default/vmlinuz-8.8.18-200.fc32.x86_64",
        ])

        ts = Mock()
        ts.dbMatch.return_value = [hdr_1, hdr_2]

        mock_rpm.TransactionSet.return_value = ts
        assert get_kernel_version_list() == [
            '0-rescue-dbe69c1b88f94a67b689e3f44b0550c8',
            '5.8.15-201.fc32.x86_64',
            '5.8.16-200.fc32.x86_64',
            '5.8.18-200.fc32.x86_64',
            '6.8.15-201.fc32.x86_64',
            '7.8.16-200.fc32.x86_64',
            '8.8.18-200.fc32.x86_64',
        ]

    def test_collect_installation_devices(self):
        """Test the collect_installation_devices function."""
        devices = collect_installation_devices([], [])
        assert devices == set()

        r1 = RepoConfigurationData()
        r1.url = "cdrom"

        r2 = RepoConfigurationData()
        r2.url = "hd:dev1"

        r3 = RepoConfigurationData()
        r3.url = "http://test"

        r4 = RepoConfigurationData()
        r4.url = "hd:/dev/dev2:/local/path"

        devices = collect_installation_devices([], [r1, r2, r3, r4])
        assert devices == {"dev1", "/dev/dev2"}

        s1 = CdromSourceModule()

        s2 = HardDriveSourceModule()
        s2.configuration.url = "hd:dev3"

        s3 = URLSourceModule()
        s3.configuration.url = "ftp://test"

        s4 = HardDriveSourceModule()
        s4.configuration.url = "hd:/dev/dev4:/some/path"

        devices = collect_installation_devices([s1, s2, s3, s4], [])
        assert devices == {"dev3", "/dev/dev4"}

        devices = collect_installation_devices([s1, s2, s3, s4], [r1, r2, r3, r4])
        assert devices == {"dev1", "/dev/dev2", "dev3", "/dev/dev4"}
