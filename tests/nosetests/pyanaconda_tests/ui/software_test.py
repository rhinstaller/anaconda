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
from unittest.mock import Mock

from dasbus.structure import compare_data

from pyanaconda.modules.common.structures.comps import CompsEnvironmentData, CompsGroupData
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.ui.lib.software import is_software_selection_complete, \
    get_software_selection_status, SoftwareSelectionCache


class SoftwareSelectionUITestCase(unittest.TestCase):
    """Test the helper functions of the Software Selection spoke."""

    def is_software_selection_complete_test(self):
        """Test the is_software_selection_complete function."""
        selection = PackagesSelectionData()
        selection.environment = "e1"

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.is_environment_valid.return_value = True

        self.assertTrue(is_software_selection_complete(dnf_manager, selection))
        self.assertTrue(is_software_selection_complete(dnf_manager, selection, kickstarted=True))

        dnf_manager.is_environment_valid.return_value = False

        self.assertFalse(is_software_selection_complete(dnf_manager, selection))
        self.assertFalse(is_software_selection_complete(dnf_manager, selection, kickstarted=True))

        selection.environment = ""

        self.assertFalse(is_software_selection_complete(dnf_manager, selection))
        self.assertTrue(is_software_selection_complete(dnf_manager, selection, kickstarted=True))

    def get_software_selection_status_test(self):
        """Test the get_software_selection_status function."""
        selection = PackagesSelectionData()
        selection.environment = "e1"

        environment_data = CompsEnvironmentData()
        environment_data.name = "The e1 environment"

        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.is_environment_valid.return_value = True
        dnf_manager.get_environment_data.return_value = environment_data

        status = get_software_selection_status(dnf_manager, selection)
        self.assertEqual(status, "The e1 environment")

        status = get_software_selection_status(dnf_manager, selection, kickstarted=True)
        self.assertEqual(status, "The e1 environment")

        dnf_manager.is_environment_valid.return_value = False

        status = get_software_selection_status(dnf_manager, selection)
        self.assertEqual(status, "Selected environment is not valid")

        status = get_software_selection_status(dnf_manager, selection, kickstarted=True)
        self.assertEqual(status, "Invalid environment specified in kickstart")

        selection.environment = ""

        status = get_software_selection_status(dnf_manager, selection)
        self.assertEqual(status, "Please confirm software selection")

        status = get_software_selection_status(dnf_manager, selection, kickstarted=True)
        self.assertEqual(status, "Custom software selected")


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

        self.cache = SoftwareSelectionCache(self.dnf_manager)

    def _get_group_data(self, group):
        """Mock the get_group_data method of the DNF manager."""
        data = CompsGroupData()
        data.id = group
        return data

    def available_environments_test(self):
        """Test the available_environments property."""
        self.dnf_manager.environments = []
        self.assertEqual(self.cache.available_environments, [])

        self.dnf_manager.environments = ["e1", "e2"]
        self.assertEqual(self.cache.available_environments, ["e1", "e2"])

    def is_environment_selected_test(self):
        """Test the is_environment_selected method."""
        self.assertEqual(self.cache.is_environment_selected("e1"), False)

        self.cache.select_environment("e1")
        self.assertEqual(self.cache.is_environment_selected("e1"), True)

        self.cache.select_environment("")
        self.assertEqual(self.cache.is_environment_selected("e1"), False)

    def environment_test(self):
        """Test the environment property."""
        self.assertEqual(self.cache.environment, "")

        self.cache.select_environment("e1")
        self.assertEqual(self.cache.environment, "e1")

    def available_groups_test(self):
        """Test the available_groups property."""
        self.cache.select_environment("e1")
        self.assertEqual(self.cache.available_groups, ["g1", "g2", "g3", "g4", "g5"])

        self.cache.select_environment("")
        self.assertEqual(self.cache.available_groups, [])

    def groups_test(self):
        """Test the groups property."""
        self.environment_data.default_groups = ["g2", "g4"]

        self.cache.select_environment("e1")
        self.assertEqual(self.cache.groups, ["g2", "g4"])

        self.cache.select_group("g1")
        self.assertEqual(self.cache.groups, ["g1", "g2", "g4"])

        self.cache.deselect_group("g4")
        self.assertEqual(self.cache.groups, ["g1", "g2"])

    def is_group_selected_test(self):
        """Test the is_group_selected method."""
        self.environment_data.default_groups = ["g2", "g4"]

        self.cache.select_environment("e1")
        self.assertEqual(self.cache.is_group_selected("g1"), False)
        self.assertEqual(self.cache.is_group_selected("g4"), True)
        self.assertEqual(self.cache.is_group_selected("g7"), False)

        self.cache.select_group("g1")
        self.assertEqual(self.cache.is_group_selected("g1"), True)
        self.assertEqual(self.cache.is_group_selected("g4"), True)
        self.assertEqual(self.cache.is_group_selected("g7"), False)

        self.cache.deselect_group("g4")
        self.assertEqual(self.cache.is_group_selected("g1"), True)
        self.assertEqual(self.cache.is_group_selected("g4"), False)
        self.assertEqual(self.cache.is_group_selected("g7"), False)

    def apply_selection_data_test(self):
        """Test the apply_selection_data method."""
        selection = PackagesSelectionData()
        selection.environment = "e1"
        selection.groups = ["g1", "g2", "g3"]

        self.cache.apply_selection_data(selection)
        self.assertEqual(self.cache.environment, "e1")
        self.assertEqual(self.cache.groups, ["g1", "g2", "g3"])

    def apply_selection_data_default_environment_test(self):
        """Test the apply_selection_data method with a default environment."""
        self.dnf_manager.default_environment = "e1"
        self.dnf_manager.resolve_environment.return_value = False

        selection = PackagesSelectionData()
        selection.environment = "e2"

        self.cache.apply_selection_data(selection)
        self.assertEqual(self.cache.environment, "e1")
        self.assertEqual(self.cache.groups, [])

    def apply_selection_data_invalid_environment_test(self):
        """Test the apply_selection_data method with an invalid environment."""
        self.dnf_manager.default_environment = ""
        self.dnf_manager.resolve_environment.return_value = False

        selection = PackagesSelectionData()
        selection.environment = "e2"

        self.cache.apply_selection_data(selection)
        self.assertEqual(self.cache.environment, "")
        self.assertEqual(self.cache.groups, [])

    def apply_selection_data_invalid_groups_test(self):
        """Test the apply_selection_data method with invalid groups."""
        self.dnf_manager.resolve_group.return_value = False

        selection = PackagesSelectionData()
        selection.environment = "e1"
        selection.groups = ["g1", "g2", "g3"]

        self.cache.apply_selection_data(selection)
        self.assertEqual(self.cache.environment, "e1")
        self.assertEqual(self.cache.groups, [])

    def get_selection_data_test(self):
        """Test the get_selection_data method."""
        self.cache.select_environment("e1")
        self.cache.select_group("g1")
        self.cache.select_group("g2")
        self.cache.select_group("g3")

        expected = PackagesSelectionData()
        expected.environment = "e1"
        expected.groups = ["g1", "g2", "g3"]

        data = self.cache.get_selection_data()
        self.assertTrue(compare_data(data, expected))

    def default_selection_test(self):
        """Test the default environment and group selection."""
        self.environment_data.id = "e1"
        self.environment_data.default_groups = ["g2", "g4"]

        self.cache.select_environment("e1")
        self.assertEqual(self.cache.groups, ["g2", "g4"])

        self.cache.select_group("g2")
        self.assertEqual(self.cache.groups, ["g2", "g4"])

        self.cache.select_group("g4")
        self.assertEqual(self.cache.groups, ["g2", "g4"])

        self.environment_data.id = "e2"
        self.environment_data.default_groups = ["g1", "g3", "g5"]

        self.cache.select_environment("e2")
        self.assertEqual(self.cache.groups, ["g1", "g3", "g5"])

    def selection_test(self):
        """Test the environment and group selection."""
        self.environment_data.id = "e1"

        self.cache.select_environment("e1")
        self.assertEqual(self.cache.groups, [])

        self.cache.select_group("g2")
        self.assertEqual(self.cache.groups, ["g2"])

        self.cache.select_group("g4")
        self.assertEqual(self.cache.groups, ["g2", "g4"])

        self.environment_data.id = "e2"
        self.environment_data.default_groups = ["g1", "g3", "g5"]

        self.cache.select_environment("e2")
        self.assertEqual(self.cache.groups, ["g1", "g2", "g3", "g4", "g5"])

    def deselection_test(self):
        """Test the environment and group deselection."""
        self.environment_data.id = "e1"
        self.environment_data.default_groups = ["g2", "g4"]

        self.cache.select_environment("e1")
        self.assertEqual(self.cache.groups, ["g2", "g4"])

        self.cache.select_group("g1")
        self.assertEqual(self.cache.groups, ["g1", "g2", "g4"])

        self.cache.deselect_group("g4")
        self.assertEqual(self.cache.groups, ["g1", "g2"])

        self.cache.select_group("g5")
        self.assertEqual(self.cache.groups, ["g1", "g2", "g5"])

        self.cache.deselect_group("g5")
        self.assertEqual(self.cache.groups, ["g1", "g2"])

        self.environment_data.id = "e2"
        self.environment_data.default_groups = ["g2", "g3", "g4", "g5"]

        self.cache.select_environment("e2")
        self.assertEqual(self.cache.groups, ["g1", "g2", "g3"])
