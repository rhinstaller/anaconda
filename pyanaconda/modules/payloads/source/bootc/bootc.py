#
# The Bootc source module.
#
# Copyright (C) 2025 Red Hat, Inc.
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
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.bootc import BootcConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.bootc.bootc_interface import (
    BootcSourceInterface,
)
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase

log = get_module_logger(__name__)

__all__ = ["BootcSourceModule"]


class BootcSourceModule(PayloadSourceBase):
    """The Bootc source module."""

    def __init__(self):
        super().__init__()
        self._configuration = BootcConfigurationData()
        self.configuration_changed = Signal()

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.BOOTC

    @property
    def description(self):
        """Get description of this source."""
        return _("Bootc")

    def for_publication(self):
        """Return a DBus representation."""
        return BootcSourceInterface(self)

    @property
    def configuration(self):
        """The source configuration.

        :return: an instance of BootcConfigurationData
        """
        return self._configuration

    def set_configuration(self, configuration):
        """Set the source configuration.

        :param configuration: an instance of BootcConfigurationData
        """
        self._configuration = configuration
        self.configuration_changed.emit()
        log.debug("Configuration is set to '%s'.", configuration)

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
        return Size("500 MB").get_bytes()

    def get_state(self):
        """Get state of this source."""
        return SourceState.NOT_APPLICABLE

    def process_kickstart(self, data):
        """Process the kickstart data."""
        configuration = BootcConfigurationData()
        configuration.stateroot = data.bootc.stateroot
        configuration.sourceImgRef = data.bootc.sourceImgRef
        configuration.targetImgRef = data.bootc.targetImgRef
        self.set_configuration(configuration)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.bootc.stateroot = self.configuration.stateroot
        data.bootc.sourceImgRef = self.configuration.sourceImgRef
        data.bootc.targetImgRef = self.configuration.targetImgRef
        data.bootc.seen = True

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        return []

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        return []

    def __repr__(self):
        """Return a string representation of the source."""
        return "Source(type='{}', stateroot='{}', sourceImgRef='{}', targetImgRef='{}')".format(
            self.type.value,
            self.configuration.stateroot,
            self.configuration.sourceImgRef,
            self.configuration.targetImgRef
        )
