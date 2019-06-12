#
# Kickstart module for packaging.
#
# Copyright (C) 2018 Red Hat, Inc.
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
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import PAYLOAD
from pyanaconda.modules.payload.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payload.payload_interface import PayloadInterface
from pyanaconda.modules.payload.dnf.dnf import DNFHandlerModule
from pyanaconda.modules.payload.live.live import LiveHandlerModule

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class PayloadModule(KickstartModule):
    """The Payload module."""

    def __init__(self):
        super().__init__()
        self._payload_handler = None

    def publish(self):
        """Publish the module."""
        DBus.publish_object(PAYLOAD.object_path, PayloadInterface(self))
        DBus.register_service(PAYLOAD.service_name)

    def _publish_handler(self):
        """Publish handler as soon as we know which one to chose"""
        self._payload_handler.publish()

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return PayloadKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

        self._create_correct_handler(data)
        self._publish_handler()

        self._payload_handler.process_kickstart(data)

    def _create_correct_handler(self, data):
        if data.liveimg.seen:
            self._payload_handler = LiveHandlerModule()
        else:
            self._payload_handler = DNFHandlerModule()

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()

        self._payload_handler.setup_kickstart(data)

        return str(data)
