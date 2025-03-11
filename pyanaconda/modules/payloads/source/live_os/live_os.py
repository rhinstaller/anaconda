#
# Kickstart module for Live OS payload source.
#
# Copyright (C) 2019 Red Hat, Inc.
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
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.live_os.initialization import (
    DetectLiveOSImageTask,
    SetupLiveOSResult,
    SetUpLiveOSSourceTask,
)
from pyanaconda.modules.payloads.source.live_os.live_os_interface import (
    LiveOSSourceInterface,
)
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.payloads.source.source_base import (
    MountingSourceMixin,
    PayloadSourceBase,
)

log = get_module_logger(__name__)


class LiveOSSourceModule(PayloadSourceBase, MountingSourceMixin):
    """The Live OS source payload module."""

    def __init__(self):
        super().__init__()
        self._image_path = ""
        self.image_path_changed = Signal()
        self._required_space = 0

    def for_publication(self):
        """Return a DBus representation."""
        return LiveOSSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.LIVE_OS_IMAGE

    @property
    def description(self):
        """Get description of this source."""
        return _("Live OS")

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
        return self._required_space

    @property
    def image_path(self):
        """Path to the Live OS image.

        This image will be used as the installation source.

        :rtype: str
        """
        return self._image_path

    def set_image_path(self, image_path):
        """Set path to the Live OS image.

        :param image_path: path to the image
        :type image_path: str
        """
        self._image_path = image_path
        self.image_path_changed.emit()
        log.debug("LiveOS image path is set to '%s'", self._image_path)

    def detect_image_with_task(self):
        """Detect a Live OS image with a task.

        Detect an image and set the image path of the source.

        :return: a task
        """
        task = DetectLiveOSImageTask()
        task.succeeded_signal.connect(
            lambda: self.set_image_path(task.get_result())
        )
        return task

    def get_state(self):
        """Get state of this source."""
        return SourceState.from_bool(self.get_mount_state())

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpLiveOSSourceTask(
            image_path=self.image_path,
            target_mount=self.mount_point
        )

        handler = self._handle_live_os_task_result
        task.succeeded_signal.connect(lambda: handler(task.get_result()))
        return [task]

    def _handle_live_os_task_result(self, result: SetupLiveOSResult):
        self._required_space = result.required_space

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [TearDownMountTask]
        """
        return [
            TearDownMountTask(
                target_mount=self.mount_point
            )
        ]

    def __repr__(self):
        """Return a string representation of the source."""
        return "Source(type='{}', image='{}')".format(
            self.type.value,
            self.image_path,
        )
