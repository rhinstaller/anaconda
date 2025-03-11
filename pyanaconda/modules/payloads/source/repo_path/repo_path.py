#
# Copyright (C) 2023 Red Hat, Inc.
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
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.repo_path.initialization import (
    SetUpRepoPathSourceTask,
)
from pyanaconda.modules.payloads.source.repo_path.repo_path_interface import (
    RepoPathSourceInterface,
)
from pyanaconda.modules.payloads.source.source_base import (
    PayloadSourceBase,
    RPMSourceMixin,
)

log = get_module_logger(__name__)


class RepoPathSourceModule(PayloadSourceBase, RPMSourceMixin):
    """An RPM source defined by a local path to a repository.

    This RPM source will work as default and should replace current default which
    is CDROM source. This mount point will just re-use dracut mount points if it
    has a valid repository.
    """

    def __init__(self):
        super().__init__()
        self._path = ""
        self.path_changed = Signal()

    def for_publication(self):
        """Get the interface used to publish this source."""
        return RepoPathSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.REPO_PATH

    @property
    def description(self):
        """Get description of this source."""
        return _("Auto-detected source")

    def get_state(self):
        """Get state of this source."""
        return SourceState.NOT_APPLICABLE

    @property
    def network_required(self):
        """Does the source require a network?

        :return: True or False
        """
        return False

    @property
    def required_space(self):
        """The space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        return 0

    @property
    def path(self):
        """The local path to a repository.

        :return str: a local path
        """
        return self._path

    def set_path(self, path):
        """Set a local path to a repository.

        :param str path: a local path
        """
        self._path = path
        self.path_changed.emit()
        log.debug("Repository path is set to: '%s'", path)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("This source is not supported by kickstart.")

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        log.debug("This source is not supported by kickstart.")

    def set_up_with_tasks(self):
        """Set up the installation source.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        return [SetUpRepoPathSourceTask(self._path)]

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: []
        """
        return []

    def generate_repo_configuration(self):
        """Generate RepoConfigurationData structure."""
        return RepoConfigurationData.from_directory(self.path)

    def __repr__(self):
        """Return a string representation of the source."""
        return "Source(type='{}', path='{}')".format(
            self.type.value,
            self.path
        )
