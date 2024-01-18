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
import unittest
from unittest.mock import patch
from unittest.mock import Mock

from dasbus.structure import compare_data

from pyanaconda.modules.common.structures.comps import CompsEnvironmentData, CompsGroupData
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.ui.lib.software import is_software_selection_complete, \
    get_software_selection_status, SoftwareSelectionCache, get_kernel_from_properties, \
    get_available_kernel_features, KernelFeatures


def get_dnf_proxy(dnf_manager):
    """Create a DNF payload proxy using the specified DNF manager."""
    dnf_module = DNFModule()
    dnf_module._dnf_manager = dnf_manager
    return dnf_module.for_publication()


class SoftwareSelectionUITestCase(unittest.TestCase):
    """Test the helper functions of the Software Selection spoke."""

    def setUp(self):
        self.dnf_manager = Mock(spec=DNFManager)
        self.dnf_proxy = get_dnf_proxy(self.dnf_manager)

    def test_is_software_selection_complete(self):
        """Test the is_software_selection_complete function."""
        selection = PackagesSelectionData()
        selection.environment = "e1"

        self.dnf_manager.resolve_environment.return_value = "e1"

        assert is_software_selection_complete(self.dnf_proxy, selection)
        assert is_software_selection_complete(self.dnf_proxy, selection, kickstarted=True)

        self.dnf_manager.resolve_environment.return_value = None

        assert not is_software_selection_complete(self.dnf_proxy, selection)
        assert not is_software_selection_complete(self.dnf_proxy, selection, kickstarted=True)

        selection.environment = ""

        assert not is_software_selection_complete(self.dnf_proxy, selection)
        assert is_software_selection_complete(self.dnf_proxy, selection, kickstarted=True)

    def test_get_software_selection_status(self):
        """Test the get_software_selection_status function."""
        selection = PackagesSelectionData()
        selection.environment = "e1"

        environment_data = CompsEnvironmentData()
        environment_data.name = "The e1 environment"

        self.dnf_manager.resolve_environment.return_value = "e1"
        self.dnf_manager.get_environment_data.return_value = environment_data

        status = get_software_selection_status(self.dnf_proxy, selection)
        assert status == "The e1 environment"

        status = get_software_selection_status(self.dnf_proxy, selection, kickstarted=True)
        assert status == "The e1 environment"

        self.dnf_manager.resolve_environment.return_value = None

        status = get_software_selection_status(self.dnf_proxy, selection)
        assert status == "Selected environment is not valid"

        status = get_software_selection_status(self.dnf_proxy, selection, kickstarted=True)
        assert status == "Invalid environment specified in kickstart"

        selection.environment = ""

        status = get_software_selection_status(self.dnf_proxy, selection)
        assert status == "Please confirm software selection"

        status = get_software_selection_status(self.dnf_proxy, selection, kickstarted=True)
        assert status == "Custom software selected"

    def test_get_kernel_from_properties(self):
        """Test if kernel features are translated to corrent package names."""
        assert get_kernel_from_properties(
            KernelFeatures(page_size_64k=False)) is None
        assert get_kernel_from_properties(
            KernelFeatures(page_size_64k=True)) == "kernel-64k"

    @patch("pyanaconda.ui.lib.software.is_aarch64")
    def test_get_available_kernel_features(self, is_aarch64):
        """test availability of kernel packages"""
        self.dnf_manager.match_available_packages.return_value = \
            ["kernel-64k-5.14.0-408.el9.aarch64.rpm"]

        is_aarch64.return_value = False
        res = get_available_kernel_features(self.dnf_proxy)
        assert isinstance(res, dict)
        assert len(res) > 0
        assert not res["64k"]
        is_aarch64.assert_called_once()

        is_aarch64.return_value = True
        assert is_aarch64()
        res = get_available_kernel_features(self.dnf_proxy)
        assert res["64k"]

        self.dnf_manager.match_available_packages.return_value = []
        res = get_available_kernel_features(self.dnf_proxy)
        assert not res["64k"]


class SoftwareSelectionCacheTestCase(unittest.TestCase):
    """Test the cache for the Software Selection spoke."""

    def setUp(self):
        """Set up the test."""
        self.environment_data = CompsEnvironmentData()
        self.environment_data.id = "e1"
        self.environment_data.optional_groups = ["g1", "g2", "g3", "g4", "g5"]

        self.dnf_manager = Mock(spec=DNFManager)
        self.dnf_manager.resolve_environment.return_value = True
        self.dnf_manager.get_environment_data.return_value = self.environment_data
        self.dnf_manager.get_group_data.side_effect = self._get_group_data
        self.dnf_manager.resolve_group.return_value = True

        self.cache = SoftwareSelectionCache(get_dnf_proxy(self.dnf_manager))

    def _get_group_data(self, group):
        """Mock the get_group_data method of the DNF manager."""
        data = CompsGroupData()
        data.id = group
        return data

    def test_available_environments(self):
        """Test the available_environments property."""
        self.dnf_manager.environments = []
        assert self.cache.available_environments == []

        self.dnf_manager.environments = ["e1", "e2"]
        assert self.cache.available_environments == ["e1", "e2"]

    def test_is_environment_selected(self):
        """Test the is_environment_selected method."""
        assert self.cache.is_environment_selected("e1") is False

        self.cache.select_environment("e1")
        assert self.cache.is_environment_selected("e1") is True

        self.cache.select_environment("")
        assert self.cache.is_environment_selected("e1") is False

    def test_environment(self):
        """Test the environment property."""
        assert self.cache.environment == ""

        self.cache.select_environment("e1")
        assert self.cache.environment == "e1"

    def test_available_groups(self):
        """Test the available_groups property."""
        self.cache.select_environment("e1")
        assert self.cache.available_groups == ["g1", "g2", "g3", "g4", "g5"]

        self.cache.select_environment("")
        assert self.cache.available_groups == []

    def test_groups(self):
        """Test the groups property."""
        self.environment_data.default_groups = ["g2", "g4"]

        self.cache.select_environment("e1")
        assert self.cache.groups == ["g2", "g4"]

        self.cache.select_group("g1")
        assert self.cache.groups == ["g1", "g2", "g4"]

        self.cache.deselect_group("g4")
        assert self.cache.groups == ["g1", "g2"]

    def test_is_group_selected(self):
        """Test the is_group_selected method."""
        self.environment_data.default_groups = ["g2", "g4"]

        self.cache.select_environment("e1")
        assert self.cache.is_group_selected("g1") is False
        assert self.cache.is_group_selected("g4") is True
        assert self.cache.is_group_selected("g7") is False

        self.cache.select_group("g1")
        assert self.cache.is_group_selected("g1") is True
        assert self.cache.is_group_selected("g4") is True
        assert self.cache.is_group_selected("g7") is False

        self.cache.deselect_group("g4")
        assert self.cache.is_group_selected("g1") is True
        assert self.cache.is_group_selected("g4") is False
        assert self.cache.is_group_selected("g7") is False

    def test_apply_selection_data(self):
        """Test the apply_selection_data method."""
        selection = PackagesSelectionData()
        selection.environment = "e1"
        selection.groups = ["g1", "g2", "g3"]

        self.cache.apply_selection_data(selection)
        assert self.cache.environment == "e1"
        assert self.cache.groups == ["g1", "g2", "g3"]

    def test_apply_selection_data_default_environment(self):
        """Test the apply_selection_data method with a default environment."""
        self.dnf_manager.default_environment = "e1"
        self.dnf_manager.resolve_environment.return_value = False

        selection = PackagesSelectionData()
        selection.environment = "e2"

        self.cache.apply_selection_data(selection)
        assert self.cache.environment == "e1"
        assert self.cache.groups == []

    def test_apply_selection_data_invalid_environment(self):
        """Test the apply_selection_data method with an invalid environment."""
        self.dnf_manager.default_environment = ""
        self.dnf_manager.resolve_environment.return_value = False

        selection = PackagesSelectionData()
        selection.environment = "e2"

        self.cache.apply_selection_data(selection)
        assert self.cache.environment == ""
        assert self.cache.groups == []

    def test_apply_selection_data_invalid_groups(self):
        """Test the apply_selection_data method with invalid groups."""
        self.dnf_manager.resolve_group.return_value = False

        selection = PackagesSelectionData()
        selection.environment = "e1"
        selection.groups = ["g1", "g2", "g3"]

        self.cache.apply_selection_data(selection)
        assert self.cache.environment == "e1"
        assert self.cache.groups == []

    def test_get_selection_data(self):
        """Test the get_selection_data method."""
        self.cache.select_environment("e1")
        self.cache.select_group("g1")
        self.cache.select_group("g2")
        self.cache.select_group("g3")

        expected = PackagesSelectionData()
        expected.environment = "e1"
        expected.groups = ["g1", "g2", "g3"]

        data = self.cache.get_selection_data()
        assert compare_data(data, expected)

    def test_default_selection(self):
        """Test the default environment and group selection."""
        self.environment_data.id = "e1"
        self.environment_data.default_groups = ["g2", "g4"]

        self.cache.select_environment("e1")
        assert self.cache.groups == ["g2", "g4"]

        self.cache.select_group("g2")
        assert self.cache.groups == ["g2", "g4"]

        self.cache.select_group("g4")
        assert self.cache.groups == ["g2", "g4"]

        self.environment_data.id = "e2"
        self.environment_data.default_groups = ["g1", "g3", "g5"]

        self.cache.select_environment("e2")
        assert self.cache.groups == ["g1", "g3", "g5"]

    def test_selection(self):
        """Test the environment and group selection."""
        self.environment_data.id = "e1"

        self.cache.select_environment("e1")
        assert self.cache.groups == []

        self.cache.select_group("g2")
        assert self.cache.groups == ["g2"]

        self.cache.select_group("g4")
        assert self.cache.groups == ["g2", "g4"]

        self.environment_data.id = "e2"
        self.environment_data.default_groups = ["g1", "g3", "g5"]

        self.cache.select_environment("e2")
        assert self.cache.groups == ["g1", "g2", "g3", "g4", "g5"]

    def test_deselection(self):
        """Test the environment and group deselection."""
        self.environment_data.id = "e1"
        self.environment_data.default_groups = ["g2", "g4"]

        self.cache.select_environment("e1")
        assert self.cache.groups == ["g2", "g4"]

        self.cache.select_group("g1")
        assert self.cache.groups == ["g1", "g2", "g4"]

        self.cache.deselect_group("g4")
        assert self.cache.groups == ["g1", "g2"]

        self.cache.select_group("g5")
        assert self.cache.groups == ["g1", "g2", "g5"]

        self.cache.deselect_group("g5")
        assert self.cache.groups == ["g1", "g2"]

        self.environment_data.id = "e2"
        self.environment_data.default_groups = ["g2", "g3", "g4", "g5"]

        self.cache.select_environment("e2")
        assert self.cache.groups == ["g1", "g2", "g3"]
