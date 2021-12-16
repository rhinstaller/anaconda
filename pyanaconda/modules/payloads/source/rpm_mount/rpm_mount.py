#
# Kickstart module for RPM mount payload source.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.core.i18n import _
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase, \
    RPMSourceMixin
from pyanaconda.modules.payloads.source.rpm_mount.rpm_mount_interface import \
    RPMMountSourceInterface
from pyanaconda.modules.payloads.source.rpm_mount.initialization import \
    SetUpRPMMountSourceTask

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class RPMMountSourceModule(PayloadSourceBase, RPMSourceMixin):
    """The RPM mount point source payload module.

    This source will use existing mount point as the payload source. There will be no unmount and
    mounting involved.
    """

    def __init__(self):
        super().__init__()
        self._path = ""
        self.path_changed = Signal()
        self._is_ready = False

    def __repr__(self):
        return "Source(type='{}', path='{}')".format(
            self.type.value,
            self._path)

    def for_publication(self):
        """Get the interface used to publish this source."""
        return RPMMountSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.RPM_MOUNT

    @property
    def description(self):
        """Get description of this source."""
        return _("RPM Mount {}".format(self._path))

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

    def get_state(self):
        """Get state of this source."""
        return SourceState.from_bool(self._is_ready)

    def generate_repo_configuration(self):
        """Generate RepoConfigurationData structure."""
        return RepoConfigurationData.from_directory(self.path)

    @property
    def path(self):
        """Path to the directory where repository should be.

        :rtype: str
        """
        return self._path

    def set_path(self, path):
        """Set path to the directory where repository should be.

        :param path: path to the directory
        :type path: str
        """
        self._path = path
        self.path_changed.emit()
        log.debug("RPM Mount directory is set to %s", self._path)

    def set_up_with_tasks(self):
        """Set up the installation source.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpRPMMountSourceTask(self._path)
        task.succeeded_signal.connect(lambda: self._handle_setup_task_result(task))
        return [task]

    def _handle_setup_task_result(self, task):
        result = task.get_result()
        self._is_ready = result
        log.debug("Repository found at '%s'", self._path)

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: []
        """
        return []

    def process_kickstart(self, data):
        """Process the kickstart data.

        This command is not supported by kickstart.
        """
        pass

    def setup_kickstart(self, data):
        """Setup the kickstart data.

        This command is not supported by kickstart.
        """
        pass
