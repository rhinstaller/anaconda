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
from pyanaconda.modules.common.errors.payload import HandlerNotSetError
from pyanaconda.modules.payload.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payload.payload_interface import PayloadInterface
from pyanaconda.modules.payload.dnf.dnf import DNFHandlerModule
from pyanaconda.modules.payload.live.live_image import LiveImageHandlerModule
from pyanaconda.modules.payload.live.live_os import LiveOSHandlerModule

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

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return PayloadKickstartSpecification

    @property
    def payload_handler(self):
        """Get payload handler.

        Handlers are handling the installation process.

        There are a few types of handler e.g.: DNF, LiveImage...
        """
        if self._payload_handler is None:
            raise HandlerNotSetError()
        else:
            return self._payload_handler

    def set_payload_handler(self, payload_handler):
        """Set payload handler."""
        self._payload_handler = payload_handler
        log.debug("Payload handler %s used.", payload_handler.__class__.__name__)

    def get_active_handler_path(self):
        """Get path of the active payload handler.

        :rtype: str
        """
        try:
            return self.payload_handler.get_handler_path()
        except HandlerNotSetError:
            return ""

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

        handler_class = self._get_correct_handler_class(data)
        self._initialize_handler(handler_class)

        self.payload_handler.process_kickstart(data)

    def _get_correct_handler_class(self, data):
        if data.liveimg.seen:
            return LiveImageHandlerModule
        else:
            return DNFHandlerModule

    def _initialize_handler(self, handler_class):
        handler = handler_class()

        self._publish_handler(handler)
        self.set_payload_handler(handler)

    @staticmethod
    def _publish_handler(handler):
        """Publish handler passed in.

        This method is really helpful for testing purpose.
        """
        handler.publish()

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()

        try:
            self.payload_handler.setup_kickstart(data)
        except HandlerNotSetError:
            log.warning("Generating kickstart data without set handler - data will be empty!")

        return str(data)

    def create_dnf_handler(self):
        """Create the DNF payload handler and publish it.

        :returns: DBus path to the handler
        :rtype: str
        """
        self._initialize_handler(DNFHandlerModule)
        return self.payload_handler.get_handler_path()

    def create_live_os_handler(self):
        """Create the live os payload handler and publish it.

        :returns: DBus path to the handler
        :rtype: str
        """
        self._initialize_handler(LiveOSHandlerModule)
        return self.payload_handler.get_handler_path()
