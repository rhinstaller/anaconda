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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from unittest.mock import Mock, patch, PropertyMock

import libdnf5

from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.validation import (
    CheckPackagesSelectionTask,
    VerifyRepomdHashesTask,
)


class CheckPackagesSelectionTaskTestCase(unittest.TestCase):
    """Test the validation task for checking the packages selection."""

    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_no_selection_report(self, kernel_getter):
        dnf_manager = DNFManager()
        dnf_manager.setup_base()

        kernel_getter.return_value = None

        selection = PackagesSelectionData()
        selection.default_environment_enabled = False
        selection.core_group_enabled = False

        report = CheckPackagesSelectionTask(dnf_manager, selection).run()

        assert report.is_valid() is True
        assert report.error_messages == []
        assert report.warning_messages == []

    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_no_selection_calls(self, kernel_getter):
        dnf_manager = Mock(spec=DNFManager)

        kernel_getter.return_value = None

        selection = PackagesSelectionData()
        selection.default_environment_enabled = False
        selection.core_group_enabled = False

        CheckPackagesSelectionTask(dnf_manager, selection).run()

        dnf_manager.clear_selection.assert_called_once_with()
        dnf_manager.apply_specs.assert_called_once_with([], ["@core"])
        dnf_manager.resolve_selection.assert_called_once_with()

    @patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.DNFManager.default_environment", new_callable=PropertyMock)
    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_default_selection_report(self, kernel_getter, default_environment):
        dnf_manager = DNFManager()
        dnf_manager.setup_base()

        kernel_getter.return_value = "kernel"
        default_environment.return_value = 'environment'

        selection = PackagesSelectionData()
        selection.default_environment_enabled = True
        selection.core_group_enabled = True

        report = CheckPackagesSelectionTask(dnf_manager, selection).run()

        assert report.is_valid() is True
        assert report.error_messages == []
        assert report.warning_messages == [
            "No match for argument: kernel",
            "No match for argument: environment",
            "No match for argument: core",
        ]

    @patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.DNFManager.resolve_selection")
    @patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.DNFManager.apply_specs")
    @patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.DNFManager.clear_selection")
    @patch("pyanaconda.modules.payloads.payload.dnf.dnf_manager.DNFManager.default_environment", new_callable=PropertyMock)
    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_default_selection_calls(self, kernel_getter, default_environment, clear_selection, apply_specs, resolve_selection):
        dnf_manager = DNFManager()
        dnf_manager.setup_base()

        kernel_getter.return_value = "kernel"
        default_environment.return_value = 'environment'
    
        selection = PackagesSelectionData()
        selection.default_environment_enabled = True
        selection.core_group_enabled = True

        CheckPackagesSelectionTask(dnf_manager, selection).run()

        clear_selection.assert_called_once_with()
        apply_specs.assert_called_once_with(
            ["@environment", "@core", "kernel"], []
        )
        resolve_selection.assert_called_once_with()

    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_selection_report(self, kernel_getter):
        dnf_manager = DNFManager()
        dnf_manager.setup_base()

        kernel_getter.return_value = None

        selection = PackagesSelectionData()
        selection.core_group_enabled = False
        selection.environment = "e1"

        selection.packages = ["p1", "p2"]
        selection.excluded_packages = ["p3", "p4"]

        selection.groups = ["g1", "g2"]
        selection.excluded_groups = ["g3", "g4"]

        report = CheckPackagesSelectionTask(dnf_manager, selection).run()

        assert report.is_valid() is True
        assert report.error_messages == []
        assert report.warning_messages == [
            "No match for argument: p1",
            "No match for argument: p2",
            "No match for argument: e1",
            "No match for argument: g1",
            "No match for argument: g2",
        ]

    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_selection_calls(self, kernel_getter):
        dnf_manager = Mock(spec=DNFManager)

        kernel_getter.return_value = None

        selection = PackagesSelectionData()
        selection.core_group_enabled = False
        selection.environment = "e1"

        selection.packages = ["p1", "p2"]
        selection.excluded_packages = ["p3", "p4"]

        selection.groups = ["g1", "g2"]
        selection.excluded_groups = ["g3", "g4"]

        selection.modules = ["m1", "m2"]
        selection.disabled_modules = ["m3", "m4"]

        CheckPackagesSelectionTask(dnf_manager, selection).run()

        dnf_manager.clear_selection.assert_called_once_with()
        dnf_manager.apply_specs.assert_called_once_with(
            ["@e1", "@g1", "@g2", "p1", "p2"],
            ["@core", "@g3", "@g4", "p3", "p4"]
        )
        dnf_manager.resolve_selection.assert_called_once_with()

    @patch("libdnf5.base.Transaction.get_resolve_logs_as_strings")
    @patch("libdnf5.base.Transaction.get_problems")
    @patch("pyanaconda.modules.payloads.payload.dnf.validation.get_kernel_package")
    def test_check_invalid_selection_report(self, kernel_getter, get_problems, get_resolve_logs):
        dnf_manager = DNFManager()
        dnf_manager.setup_base()

        kernel_getter.return_value = None
        selection = PackagesSelectionData()

        get_problems.return_value = libdnf5.base.GoalProblem_MODULE_SOLVER_ERROR
        get_resolve_logs.return_value = ["Error message!"]

        report = CheckPackagesSelectionTask(dnf_manager, selection).run()

        assert report.is_valid() is False
        assert report.error_messages == [
            "The following software marked for installation has errors.\n"
            "This is likely caused by an error with your installation source.\n\n",
            'Error message!'
        ]
        assert report.warning_messages == []


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
