#
# Kickstart module for CD-ROM payload source.
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
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.cdrom.cdrom_interface import (
    CdromSourceInterface,
)
from pyanaconda.modules.payloads.source.cdrom.initialization import SetUpCdromSourceTask
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.payloads.source.source_base import (
    MountingSourceMixin,
    PayloadSourceBase,
    RPMSourceMixin,
)

log = get_module_logger(__name__)


class CdromSourceModule(PayloadSourceBase, MountingSourceMixin, RPMSourceMixin):
    """The CD-ROM source payload module.

    This source will try to automatically detect installation source. First it tries to look only
    stage2 device used to boot the environment then it will use first valid iso9660 media with a
    valid structure.
    """

    def __init__(self):
        super().__init__()
        self._device_id = ""
        self.device_id_changed = Signal()

    def __repr__(self):
        return "Source(type='CDROM')"

    def for_publication(self):
        """Get the interface used to publish this source."""
        return CdromSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.CDROM

    @property
    def description(self):
        """Get description of this source."""
        return _("Local media")

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
    def device_id(self):
        """Get device ID of the cdrom found.

        :return: device ID of the cdrom device
        :rtype: str
        """
        return self._device_id

    def get_state(self):
        """Get state of this source."""
        return SourceState.from_bool(self.get_mount_state())

    def generate_repo_configuration(self):
        """Generate RepoConfigurationData structure."""
        return RepoConfigurationData.from_directory(self.mount_point)

    def set_up_with_tasks(self):
        """Set up the installation source.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpCdromSourceTask(self.mount_point)
        task.succeeded_signal.connect(lambda: self._handle_setup_task_result(task))
        return [task]

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [TearDownMountTask]
        """
        task = TearDownMountTask(self._mount_point)
        return [task]

    def process_kickstart(self, data):
        """Process the kickstart data.

        This will be empty because cdrom KS command does not have any arguments.
        """
        pass

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.cdrom.seen = True

    def _handle_setup_task_result(self, task):
        self._device_id = task.get_result()
        self.device_id_changed.emit()
        self.module_properties_changed.emit()
