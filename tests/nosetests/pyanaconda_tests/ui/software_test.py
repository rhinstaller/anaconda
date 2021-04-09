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

from pyanaconda.modules.common.structures.comps import CompsEnvironmentData
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.ui.lib.software import is_software_selection_complete, \
    get_software_selection_status


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
