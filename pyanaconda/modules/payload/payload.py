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
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.errors.payload import HandlerNotSetError
from pyanaconda.modules.payload.handler_factory import HandlerFactory
from pyanaconda.modules.payload.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payload.payload_interface import PayloadInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class PayloadModule(KickstartModule):
    """The Payload module."""

    def __init__(self):
        super().__init__()
        self._payload_handler = None
        self._payload_handler_path = None

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(PAYLOAD.namespace)
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

    def is_handler_set(self):
        """Test if any handler is created and used.

        :rtype: bool
        """
        return self._payload_handler is not None

    def get_active_handler_path(self):
        """Get path of the active payload handler.

        :rtype: str
        """
        if self._payload_handler_path:
            return self._payload_handler_path

        return ""

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

        # create handler if no handler is set already
        if not self.is_handler_set():
            handler = HandlerFactory.create_handler_from_ks_data(data)
            if not handler:
                log.warning("No handler was created. Kickstart data passed in are lost.")
                return

        handler.process_kickstart(data)

        self._initialize_handler(handler)

    def _initialize_handler(self, handler):
        self._payload_handler_path = handler.publish_handler()
        self.set_payload_handler(handler)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()

        try:
            self.payload_handler.setup_kickstart(data)
        except HandlerNotSetError:
            log.warning("Generating kickstart data without set handler - data will be empty!")

        return str(data)

    def create_handler(self, handler_type):
        """Create handler based on the passed type.

        :param handler_type: type of the desirable handler
        :type handler_type: value of the payload.handler_factory.HandlerType enum
        """
        handler = HandlerFactory.create_handler(handler_type)
        self._initialize_handler(handler)
        return self._payload_handler_path
