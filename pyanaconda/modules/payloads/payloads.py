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
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.modules.common.containers import TaskContainer, PayloadContainer
from pyanaconda.modules.common.errors.payload import PayloadNotSetError
from pyanaconda.modules.payloads.factory import PayloadFactory, SourceFactory
from pyanaconda.modules.payloads.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payloads.packages.packages import PackagesModule
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class PayloadsService(KickstartService):
    """The Payload service."""

    def __init__(self):
        super().__init__()
        self._payload = None
        self._payload_path = None

        self._packages = PackagesModule()

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(PAYLOADS.namespace)

        self._packages.publish()

        DBus.publish_object(PAYLOADS.object_path, PayloadsInterface(self))
        DBus.register_service(PAYLOADS.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return PayloadKickstartSpecification

    @property
    def payload(self):
        """Get payload.

        Payloads are handling the installation process.

        FIXME: Replace this solution by something extensible for multiple payload support.
               Could it be SetPayloads() and using this list to set order of payload installation?

        There are a few types of payloads e.g.: DNF, LiveImage...
        """
        if self._payload is None:
            raise PayloadNotSetError()
        else:
            return self._payload

    def set_payload(self, payload):
        """Set payload."""
        self._payload = payload
        log.debug("Payload %s used.", payload.__class__.__name__)

    def is_payload_set(self):
        """Test if any payload is created and used.

        :rtype: bool
        """
        return self._payload is not None

    def get_active_payload_path(self):
        """Get path of the active payload.

        :rtype: str
        """
        if self._payload_path:
            return self._payload_path

        return ""

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

        # create payload if no payload is set already
        if not self.is_payload_set():
            payload = PayloadFactory.create_from_ks_data(data)
            if not payload:
                log.warning("No payload was created. Kickstart data passed in are lost.")
                return

        payload.process_kickstart(data)

        self.set_payload(payload)
        PayloadContainer.to_object_path(payload)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        return ""

    def generate_temporary_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()

        try:
            self.payload.setup_kickstart(data)
        except PayloadNotSetError:
            log.warning("Generating kickstart data without payload set - data will be empty!")

        return str(data)

    def create_payload(self, payload_type):
        """Create payload based on the passed type.

        :param payload_type: type of the desirable payload
        :type payload_type: value of the payload.base.constants.PayloadType enum
        """
        payload = PayloadFactory.create(payload_type)
        self.set_payload(payload)
        return payload

    def create_source(self, source_type):
        """Create source based on the passed type.

        :param source_type: type of the desirable source
        :type source_type: value of the payload.base.constants.SourceType enum
        """
        return SourceFactory.create(source_type)
