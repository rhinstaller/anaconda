#
# Kickstart module for Repo files payload source.
#
# Copyright (C) 2020 Red Hat, Inc.
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
from pyanaconda.modules.payloads.constants import DNF_REPO_DIRS, SourceState, SourceType
from pyanaconda.modules.payloads.source.repo_files.initialization import (
    SetUpRepoFilesSourceTask,
)
from pyanaconda.modules.payloads.source.repo_files.repo_files_interface import (
    RepoFilesSourceInterface,
)
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase

log = get_module_logger(__name__)


class RepoFilesSourceModule(PayloadSourceBase):
    """The source payload module for local repo files.

    This is a general class for working with local repo files.
    Special cases like the CDN or the closest mirror should be
    handled in sources of different types. This source can be
    used for example for additional repositories.
    """

    def for_publication(self):
        """Get the interface used to publish this source."""
        return RepoFilesSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.REPO_FILES

    @property
    def description(self):
        """Get description of this source."""
        return _("Local repositories")

    @property
    def network_required(self):
        """Does the source require a network?

        :return: True or False
        """
        return True

    @property
    def required_space(self):
        """The space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        return 0

    def get_state(self):
        """Get state of this source."""
        return SourceState.NOT_APPLICABLE

    def set_up_with_tasks(self):
        """Set up the installation source.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpRepoFilesSourceTask(DNF_REPO_DIRS)
        return [task]

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        return []
