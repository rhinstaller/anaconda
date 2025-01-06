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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.structures.packages import PackagesSelectionData
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.common.task import ValidationTask
from pyanaconda.modules.payloads.payload.dnf.utils import (
    get_installation_specs,
    get_kernel_package,
)

log = get_module_logger(__name__)


class VerifyRepomdHashesTask(ValidationTask):
    """Verification task for checking repomd hashes of enabled repositories."""

    def __init__(self, dnf_manager):
        """Create a task.

        :param dnf_manager: a DNF manager
        """
        super().__init__()
        self._dnf_manager = dnf_manager

    @property
    def name(self):
        """The name of the task."""
        return "Verify repomd hashes"

    def run(self):
        """Run the task.

        :return: a validation report
        """
        report = ValidationReport()

        if not self._dnf_manager.verify_repomd_hashes():
            report.error_messages.append(_(
                "Some of the repomd.xml files have changed or are unreachable."
            ))

        return report


class CheckPackagesSelectionTask(ValidationTask):
    """Validation task to check the software selection."""

    def __init__(self, dnf_manager, selection: PackagesSelectionData):
        """Create a task.

        :param dnf_manager: a DNF manager
        :param selection: a packages selection data
        """
        super().__init__()
        self._dnf_manager = dnf_manager
        self._selection = selection
        self._include_list = []
        self._exclude_list = []

    @property
    def name(self):
        """The name of the task."""
        return "Check the software selection"

    def run(self):
        """Run the task.

        :return: a validation report
        """
        # Clear the previous selection.
        self._clear_selection()

        # Prepare the new selection.
        self._collect_selected_specs()
        self._collect_required_specs()

        # Resolve the new selection.
        return self._resolve_selection()

    def _clear_selection(self):
        """Clear the previous selection."""
        self._dnf_manager.clear_selection()

    def _collect_selected_specs(self):
        """Collect specs for the selected software."""
        log.debug("Collecting selected specs.")

        # Get the default environment.
        default_environment = self._dnf_manager.default_environment

        # Get the installation specs.
        include_list, exclude_list = get_installation_specs(
            self._selection, default_environment
        )

        self._include_list.extend(include_list)
        self._exclude_list.extend(exclude_list)

    def _collect_required_specs(self):
        """Collect specs for the required software."""
        log.debug("Collecting required specs.")

        # Add the kernel package.
        kernel_package = get_kernel_package(self._dnf_manager, self._exclude_list)

        if kernel_package:
            self._include_list.append(kernel_package)

    def _resolve_selection(self):
        """Resolve the new selection."""
        log.debug("Resolving the software selection.")

        # Set up the selection.
        self._dnf_manager.apply_specs(self._include_list, self._exclude_list)

        # Resolve the selection.
        report = self._dnf_manager.resolve_selection()
        log.debug("Resolving has been completed: %s", report)
        return report
