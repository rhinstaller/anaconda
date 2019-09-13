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

from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.core.signal import Signal
from pyanaconda.modules.payload.base.constants import SourceType
from pyanaconda.modules.payload.base.source_base import PayloadSourceBase
from pyanaconda.modules.payload.sources.live_os_interface import LiveOSSourceInterface
from pyanaconda.modules.payload.sources.initialization import SetUpInstallationSourceTask, \
    TearDownInstallationSourceTask

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class LiveOSSourceModule(PayloadSourceBase):
    """The Live OS source payload module."""

    def __init__(self):
        super().__init__()
        self._image_path = ""
        self.image_path_changed = Signal()

    @property
    def kind(self):
        """Get type of this source."""
        return SourceType.LIVE_OS_IMAGE

    @property
    def image_path(self):
        """Path to the source live OS image.

        This image will be used for the installation.

        :rtype: str
        """
        return self._image_path

    def set_image_path(self, image_path):
        """Set path to the live os OS image.

        :param image_path: path to the image
        :type image_path: str
        """
        self._image_path = image_path
        self.image_path_changed.emit()
        log.debug("LiveOS image path is set to '%s'", self._image_path)

    def for_publication(self):
        """Get the interface used to publish this source."""
        return LiveOSSourceInterface(self)

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpInstallationSourceTask(self._image_path, INSTALL_TREE)

        task.succeeded_signal.connect(lambda: self._set_is_ready(True))

        return [task]

    def tear_down_with_tasks(self):
        """Tear down the installation source for installation.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        task = TearDownInstallationSourceTask(INSTALL_TREE)

        task.succeeded_signal.connect(lambda: self._set_is_ready(False))

        return [task]

    def validate(self):
        """Test if the image exists on the given path.

        :return: True if file on the path exists.
        """
        try:
            res = stat.S_ISBLK(os.stat(self._image_path)[stat.ST_MODE])
            if res:
                log.debug("Live OS source is valid %s", self._image_path)
                return True
            else:
                log.warning("Live OS source is not valid %s", self._image_path)
        except FileNotFoundError:
            log.warning("Live OS source is not available %s", self._image_path)

        return False
