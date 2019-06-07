#
# Kickstart module for Live payload.
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

from pyanaconda.modules.common.constants.objects import LIVE_HANDLER
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.payload.live.live_interface import LiveHandlerInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class LiveHandlerModule(KickstartBaseModule):
    """The Live payload module."""

    def __init__(self):
        super().__init__()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(LIVE_HANDLER.object_path, LiveHandlerInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
