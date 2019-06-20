#
# Kickstart module for Live OS payload.
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
from pyanaconda.dbus import DBus

from pyanaconda.core.signal import Signal

from pyanaconda.modules.common.constants.objects import LIVE_OS_HANDLER
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.payload.live.live_os_interface import LiveOSHandlerInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class LiveOSHandlerModule(KickstartBaseModule):
    """The Live OS payload module."""

    def __init__(self):
        super().__init__()

        self._image_path = ""
        self.image_path_changed = Signal()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(LIVE_OS_HANDLER.object_path, LiveOSHandlerInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""

    def setup_kickstart(self, data):
        """Setup the kickstart data."""

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
