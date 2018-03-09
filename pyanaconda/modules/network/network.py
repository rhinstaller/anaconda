#
# Kickstart module for network and hostname settings
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
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import NETWORK, HOSTNAME
from pyanaconda.modules.network.network_interface import NetworkInterface
from pyanaconda.modules.network.kickstart import NetworkKickstartSpecification

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class NetworkModule(KickstartModule):
    """The Network module."""

    def __init__(self):
        super().__init__()
        self.hostname_changed = Signal()
        self._hostname = "localhost.localdomain"

        self.current_hostname_changed = Signal()
        self._hostname_service = self._get_hostname_service_observer()

    def _get_hostname_service_observer(self):
        """Get an observer of the hostname service."""
        service = HOSTNAME.get_cached_observer()

        service.cached_properties_changed.connect(
            self._hostname_service_properties_changed)

        service.connect_once_available()
        return service

    def publish(self):
        """Publish the module."""
        DBus.publish_object(NETWORK.object_path, NetworkInterface(self))
        DBus.register_service(NETWORK.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specififcation."""
        return NetworkKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        if data.network.hostname:
            self.set_hostname(data.network.hostname)

    def generate_kickstart(self):
        """Retrurn the kickstart string."""
        data = self.get_kickstart_handler()
        data.network.network = []
        # hostname
        hostname_data = data.NetworkData(hostname=self.hostname, bootProto="")
        data.network.network.append(hostname_data)
        return str(data)

    @property
    def hostname(self):
        """Return the hostname."""
        return self._hostname

    def set_hostname(self, hostname):
        """Set the hostname."""
        self._hostname = hostname
        self.hostname_changed.emit()
        log.debug("Hostname is set to %s", hostname)

    def _hostname_service_properties_changed(self, observer, changed, invalid):
        if "Hostname" in changed:
            hostname = self._hostname_service.cache.Hostname
            self.current_hostname_changed.emit(hostname)
            log.debug("Current hostname changed to %s", hostname)

    def get_current_hostname(self):
        """Return current hostname of the system."""
        if self._hostname_service.is_service_available:
            return self._hostname_service.proxy.Hostname

        log.debug("Current hostname cannot be get.")
        return ""

    def set_current_hostname(self, hostname):
        """Set current system hostname."""
        if not self._hostname_service.is_service_available:
            log.debug("Current hostname cannot be set.")
            return

        self._hostname_service.proxy.SetHostname(hostname, False)
        log.debug("Current hostname is set to %s", hostname)
