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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import stat

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.signal import Signal
from pyanaconda.core.util import execWithCapture
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.live_os.initialization import (
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

    def __repr__(self):
        return "Source(type='LIVE_OS_IMAGE', image='{}')".format(self._image_path)

    def for_publication(self):
        """Get the interface used to publish this source."""
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
        # FIXME: Implement this method.
        return 0

    @property
    def image_path(self):
        """Path to the live OS source image.

        This image will be used as the installation source.

        :rtype: str
        """
        return self._image_path

    def get_state(self):
        """Get state of this source."""
        return SourceState.from_bool(self.get_mount_state())

    def set_image_path(self, image_path):
        """Set path to the live OS source image.

        :param image_path: path to the image
        :type image_path: str
        """
        self._image_path = image_path
        self.image_path_changed.emit()
        log.debug("LiveOS image path is set to '%s'", self._image_path)

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [TearDownMountTask]
        """
        task = TearDownMountTask(self._mount_point)
        return [task]

    def detect_live_os_image(self):
        """Detect live os image in the system."""
        log.debug("Trying to detect live os base image automatically")
        for block_device in ["/dev/mapper/live-base", "/dev/mapper/live-osimg-min"]:
            try:
                if stat.S_ISBLK(os.stat(block_device)[stat.ST_MODE]):
                    log.debug("Detected live base image %s", block_device)
                    return block_device
            except FileNotFoundError:
                pass

        # Is it a squashfs+overlayfs base image?
        if os.path.exists("/run/rootfsbase"):
            try:
                block_device = execWithCapture("findmnt",
                                               ["-n", "-o", "SOURCE", "/run/rootfsbase"]).strip()
                if block_device:
                    log.debug("Detected live base image %s", block_device)
                    return block_device
            except (OSError, FileNotFoundError):
                pass

        log.debug("No live base image detected")
        return ""

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpLiveOSSourceTask(self._image_path, self.mount_point)
        return [task]
