#
# The live image source module.
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
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.live_image import LiveImageConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.live_image.initialization import (
    SetupImageResult,
    SetUpLocalImageSourceTask,
    SetUpRemoteImageSourceTask,
)
from pyanaconda.modules.payloads.source.live_image.installation import (
    InstallLiveImageTask,
)
from pyanaconda.modules.payloads.source.live_image.live_image_interface import (
    LiveImageSourceInterface,
)
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase
from pyanaconda.modules.payloads.source.utils import has_network_protocol

log = get_module_logger(__name__)

__all__ = ["LiveImageSourceModule"]


class LiveImageSourceModule(PayloadSourceBase):
    """The live image source module."""

    def __init__(self):
        super().__init__()
        self._configuration = LiveImageConfigurationData()
        self.configuration_changed = Signal()

        self._required_space = None

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.LIVE_IMAGE

    @property
    def description(self):
        """Get description of this source."""
        return _("Live image")

    def for_publication(self):
        """Return a DBus representation."""
        return LiveImageSourceInterface(self)

    @property
    def configuration(self):
        """The source configuration.

        :return: an instance of LiveImageConfigurationData
        """
        return self._configuration

    def set_configuration(self, configuration):
        """Set the source configuration.

        :param configuration: an instance of LiveImageConfigurationData
        """
        self._configuration = configuration
        self.configuration_changed.emit()
        log.debug("Configuration is set to '%s'.", configuration)

    @property
    def network_required(self):
        """Does the source require a network?

        :return: True or False
        """
        return has_network_protocol(self.configuration.url)

    @property
    def is_local(self):
        """Is the image local or remote?"""
        return self.configuration.url.startswith("file://")

    @property
    def required_space(self):
        """The space required for the installation of the source.

        :return: required size in bytes
        :rtype: int
        """
        if not self._required_space:
            return 1024 * 1024 * 1024

        return self._required_space

    def get_state(self):
        """Get state of this source."""
        return SourceState.NOT_APPLICABLE

    def process_kickstart(self, data):
        """Process the kickstart data."""
        configuration = LiveImageConfigurationData()
        configuration.url = data.liveimg.url or ""
        configuration.proxy = data.liveimg.proxy or ""
        configuration.checksum = data.liveimg.checksum or ""
        configuration.ssl_verification_enabled = not data.liveimg.noverifyssl
        self.set_configuration(configuration)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.liveimg.seen = True
        data.liveimg.url = self.configuration.url
        data.liveimg.proxy = self.configuration.proxy
        data.liveimg.checksum = self.configuration.checksum
        data.liveimg.noverifyssl = not self.configuration.ssl_verification_enabled

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        if self.is_local:
            task = SetUpLocalImageSourceTask(self.configuration)
        else:
            task = SetUpRemoteImageSourceTask(self.configuration)

        handler = self._handle_setup_task_result
        task.succeeded_signal.connect(lambda: handler(task.get_result()))
        return [task]

    def _handle_setup_task_result(self, result: SetupImageResult):
        """Apply the result of the set-up task."""
        self._required_space = result.required_space

    def install_with_tasks(self):
        """Install the installation source.

        :return: a list of installation tasks
        """
        return [
            InstallLiveImageTask(
                sysroot=conf.target.system_root,
                configuration=self.configuration
            )
        ]

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        return []

    def __repr__(self):
        """Return a string representation of the source."""
        return "Source(type='{}', url='{}')".format(
            self.type.value,
            self.configuration.url
        )
