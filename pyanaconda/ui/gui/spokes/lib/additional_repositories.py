#
# Copyright (C) 2022  Red Hat, Inc.
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
import copy

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import REPO_ORIGIN_TREEINFO
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.ui.gui.spokes.lib.installation_source_helpers import \
    validate_additional_repositories, collect_conflicting_repo_names, \
    generate_repository_description

log = get_module_logger(__name__)

__all__ = ["AdditionalRepositoriesSection"]


class AdditionalRepositoriesSection(object):
    """Representation of the additional repositories section.

    NOTE: This class is just a data holder now. The widget was removed.
    """

    def __init__(self, payload, window):
        """Create the section."""
        self.payload = payload
        self._window = window
        self._repositories = []
        self._original_repositories = []

    def clear(self):
        """Clear the repo store."""
        self._repositories = []

    def refresh(self):
        """Refresh the section."""
        # Get the list of additional repositories.
        repositories = self.payload.get_repo_configurations()
        self._original_repositories = copy.deepcopy(repositories)

        if not repositories:
            return

        self._repositories = repositories

        # Trigger the validation.
        self.validate()

    def remove_treeinfo_repositories(self):
        """Remove repositories loaded from the .treeinfo file."""
        if not self._repositories:
            return

        log.debug("Removing treeinfo repositories...")

        self._repositories = [
            r for r in self._repositories
            if r.origin != REPO_ORIGIN_TREEINFO
        ]

        self.validate()

    def validate(self):
        """Validate the additional repositories.

        :return: True if the repositories are valid, otherwise False
        """
        self._window.clear_info()

        # Validate the repo configuration data.
        conflicting_names = collect_conflicting_repo_names(self.payload)
        report = validate_additional_repositories(self._repositories, conflicting_names)

        if report.error_messages:
            self._window.set_warning(report.error_messages[0])

        return report.is_valid()

    def apply(self):
        """Apply the additional repositories.

        :return: True if the repositories has changed, otherwise False
        """
        old_repositories = self._original_repositories
        new_repositories = self._repositories

        if RepoConfigurationData.to_structure_list(old_repositories) == \
                RepoConfigurationData.to_structure_list(new_repositories):
            log.debug("The additional repositories haven't changed.")
            return False

        log.debug(
            "The additional repositories has changed:\n%s",
            "\n".join(map(generate_repository_description, new_repositories))
        )

        self.payload.set_repo_configurations(new_repositories)
        return True
