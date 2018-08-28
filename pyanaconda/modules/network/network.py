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

from pyanaconda.dbus import DBus, SystemBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import NETWORK, HOSTNAME
from pyanaconda.modules.network.network_interface import NetworkInterface
from pyanaconda.modules.network.kickstart import NetworkKickstartSpecification
from pyanaconda.modules.network.firewall import FirewallModule

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class NetworkModule(KickstartModule):
    """The Network module."""

    def __init__(self):
        super().__init__()

        self._firewall_module = FirewallModule()

        self.hostname_changed = Signal()
        self._hostname = "localhost.localdomain"

        self.current_hostname_changed = Signal()
        # Will be initialized on the first property access either to the proxy or
        # False if the proxy is not available or should not be used
        self._hostname_service_proxy_ = None

        self._can_touch_runtime_system = True

        self.connected_changed = Signal()
        self.nm_client = None
        # TODO fallback solution - use Gio/GNetworkMonitor ?
        if SystemBus.check_connection():
            nm_client = NM.Client.new(None)
            if nm_client.get_nm_running():
                self.nm_client = nm_client
                self.nm_client.connect("notify::%s" % NM.CLIENT_STATE, self._nm_state_changed)
                initial_state = self.nm_client.get_state()
                self.set_connected(self._nm_state_connected(initial_state))
            else:
                log.debug("NetworkManager is not running.")

    def publish(self):
        """Publish the module."""
        self._firewall_module.publish()

        DBus.publish_object(NETWORK.object_path, NetworkInterface(self))
        DBus.register_service(NETWORK.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return NetworkKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        if data.network.hostname:
            self.set_hostname(data.network.hostname)
        self._firewall_module.process_kickstart(data)

    def generate_kickstart(self):
        """Return the kickstart string."""
        data = self.get_kickstart_handler()
        data.network.network = []
        # hostname
        hostname_data = data.NetworkData(hostname=self.hostname, bootProto="")
        data.network.network.append(hostname_data)
        # firewall
        self._firewall_module.setup_kickstart(data)
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

    @property
    def can_touch_runtime_system(self):
        """Can anaconda touch runtime system?."""
        return self._can_touch_runtime_system

    @can_touch_runtime_system.setter
    def can_touch_runtime_system(self, allow):
        """Set if anaconda can touch runtime system."""
        self._can_touch_runtime_system = allow
        log.debug("Can touch runtime system is set to %s",
                  self._can_touch_runtime_system)

    @property
    def _hostname_service_proxy(self):
        if self._hostname_service_proxy_ is None:
            if not self.can_touch_runtime_system:
                # Don't even try to get the HOSTNAME proxy in this
                # case as it can hang on selinux denial (#1616214).
                self._hostname_service_proxy_ = False
            else:
                if SystemBus.check_connection():
                    self._hostname_service_proxy_ = HOSTNAME.get_proxy()
                    self._hostname_service_proxy_.PropertiesChanged.connect(
                        self._hostname_service_properties_changed)
                else:
                    self._hostname_service_proxy_ = False
        return self._hostname_service_proxy_

    def _hostname_service_properties_changed(self, interface, changed, invalid):
        if interface == HOSTNAME.interface_name and "Hostname" in changed:
            hostname = changed["Hostname"]
            self.current_hostname_changed.emit(hostname)
            log.debug("Current hostname changed to %s", hostname)

    def get_current_hostname(self):
        """Return current hostname of the system."""
        if self._hostname_service_proxy:
            return self._hostname_service_proxy.Hostname

        log.debug("Current hostname cannot be get.")
        return ""

    def set_current_hostname(self, hostname):
        """Set current system hostname."""
        if not self._hostname_service_proxy:
            log.debug("Current hostname cannot be set.")
            return

        self._hostname_service_proxy.SetHostname(hostname, False)
        log.debug("Current hostname is set to %s", hostname)

    @property
    def nm_available(self):
        return self.nm_client is not None

    @property
    def connected(self):
        """Is the system connected to the network?"""
        if self.nm_available:
            return self._connected
        else:
            log.debug("Connectivity state can't be determined, assuming connected.")
            return True

    def set_connected(self, connected):
        """Set network connectivity status."""
        self._connected = connected
        self.connected_changed.emit()
        self.module_properties_changed.emit()
        log.debug("Connected to network: %s", connected)

    def is_connecting(self):
        """Is NM in connecting state?"""
        if self.nm_available:
            return self.nm_client.get_state() == NM.State.CONNECTING
        else:
            log.debug("Connectivity state can't be determined, assuming not connecting.")
            return False

    @staticmethod
    def _nm_state_connected(state):
        return state in (NM.State.CONNECTED_LOCAL, NM.State.CONNECTED_SITE, NM.State.CONNECTED_GLOBAL)

    def _nm_state_changed(self, *args):
        state = self.nm_client.get_state()
        log.debug("NeworkManager state changed to %s", state)
        self.set_connected(self._nm_state_connected(state))
