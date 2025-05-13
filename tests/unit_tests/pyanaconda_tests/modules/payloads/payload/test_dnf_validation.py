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
from unittest.mock import Mock, patch

from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import (
    BrokenSpecsError,
    DNFManager,
    InvalidSelectionError,
    MissingSpecsError,
)
from pyanaconda.modules.payloads.payload.dnf.validation import (
    CheckPackagesSelectionTask,
    VerifyRepomdHashesTask,
)


class CheckPackagesSelectionTaskTestCase(unittest.TestCase):
    """Test the validation task for checking the packages selection."""

    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_no_selection(self, kernel_getter):
        kernel_getter.return_value = None

        dnf_manager = Mock()
        dnf_manager.default_environment = None

        selection = PackagesSelectionData()
        selection.default_environment_enabled = False
        selection.core_group_enabled = False

        task = CheckPackagesSelectionTask(dnf_manager, selection)
        report = task.run()

        dnf_manager.clear_selection.assert_called_once_with()
        dnf_manager.disable_modules.assert_called_once_with([])
        dnf_manager.enable_modules.assert_called_once_with([])
        dnf_manager.apply_specs.assert_called_once_with([], ["@core"])
        dnf_manager.resolve_selection.assert_called_once_with()
        assert report.get_messages() == []

    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_default_selection(self, kernel_getter):
        kernel_getter.return_value = "kernel"

        dnf_manager = Mock()
        dnf_manager.default_environment = "environment"

        selection = PackagesSelectionData()
        selection.default_environment_enabled = True
        selection.core_group_enabled = True

        task = CheckPackagesSelectionTask(dnf_manager, selection)
        report = task.run()

        dnf_manager.clear_selection.assert_called_once_with()
        dnf_manager.disable_modules.assert_called_once_with([])
        dnf_manager.enable_modules.assert_called_once_with([])
        dnf_manager.apply_specs.assert_called_once_with(
            ["@environment", "@core", "kernel"], []
        )
        dnf_manager.resolve_selection.assert_called_once_with()
        assert report.get_messages() == []

    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_selection(self, kernel_getter):
        kernel_getter.return_value = None
        dnf_manager = Mock()

        selection = PackagesSelectionData()
        selection.core_group_enabled = False
        selection.environment = "e1"

        selection.packages = ["p1", "p2"]
        selection.excluded_packages = ["p3", "p4"]

        selection.groups = ["g1", "g2"]
        selection.excluded_groups = ["g3", "g4"]

        selection.modules = ["m1", "m2"]
        selection.disabled_modules = ["m3", "m4"]

        task = CheckPackagesSelectionTask(dnf_manager, selection)
        report = task.run()

        dnf_manager.clear_selection.assert_called_once_with()
        dnf_manager.disable_modules.assert_called_once_with(
            ["m3", "m4"]
        )
        dnf_manager.enable_modules.assert_called_once_with(
            ["m1", "m2"]
        )
        dnf_manager.apply_specs.assert_called_once_with(
            ["@e1", "@g1", "@g2", "p1", "p2"],
            ["@core", "@g3", "@g4", "p3", "p4"]
        )
        dnf_manager.resolve_selection.assert_called_once_with()
        assert report.get_messages() == []

    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_invalid_selection(self, kernel_getter):
        kernel_getter.return_value = None
        selection = PackagesSelectionData()

        dnf_manager = Mock()
        dnf_manager.disable_modules.side_effect = MissingSpecsError("e1")
        dnf_manager.enable_modules.side_effect = BrokenSpecsError("e2")
        dnf_manager.apply_specs.side_effect = MissingSpecsError("e3")
        dnf_manager.resolve_selection.side_effect = InvalidSelectionError("e4")

        task = CheckPackagesSelectionTask(dnf_manager, selection)
        report = task.run()

        assert report.error_messages == ["e2", "e4"]
        assert report.warning_messages == ["e1", "e3"]


class VerifyRepomdHashesTaskTestCase(unittest.TestCase):
    """Test the VerifyRepomdHashesTask task."""

    def test_success(self):
        """Run a task with the same repomd.xml files."""
        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.verify_repomd_hashes.return_value = True

        task = VerifyRepomdHashesTask(dnf_manager)
        report = task.run()

        assert report.is_valid() is True
        assert report.error_messages == []
        assert report.warning_messages == []

    def test_failure(self):
        """Run a task with the changed repomd.xml files."""
        dnf_manager = Mock(spec=DNFManager)
        dnf_manager.verify_repomd_hashes.return_value = False

        task = VerifyRepomdHashesTask(dnf_manager)
        report = task.run()

        assert report.is_valid() is False
        assert report.error_messages == [
            "Some of the repomd.xml files have changed or are unreachable."
        ]
        assert report.warning_messages == []
