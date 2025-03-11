#
# Firewall configuration module.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import FIREWALL
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.network.constants import FirewallMode
from pyanaconda.modules.network.firewall.firewall_interface import FirewallInterface
from pyanaconda.modules.network.firewall.installation import ConfigureFirewallTask

log = get_module_logger(__name__)


class FirewallModule(KickstartBaseModule):
    """The firewall module."""

    def __init__(self):
        super().__init__()

        self._firewall_seen = False

        self.firewall_mode_changed = Signal()
        self._firewall_mode = FirewallMode.DEFAULT

        self.enabled_ports_changed = Signal()
        self._enabled_ports = []

        self.trusts_changed = Signal()
        self._trusts = []

        # services to allow
        self.enabled_services_changed = Signal()
        self._enabled_services = []

        # services to explicitly disallow
        self.disabled_services_changed = Signal()
        self._disabled_services = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(FIREWALL.object_path, FirewallInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_firewall_seen(data.firewall.seen)
        # mode
        if data.firewall.use_system_defaults:
            self.set_firewall_mode(FirewallMode.USE_SYSTEM_DEFAULTS)
        elif data.firewall.enabled is True:
            self.set_firewall_mode(FirewallMode.ENABLED)
        elif data.firewall.enabled is False:
            self.set_firewall_mode(FirewallMode.DISABLED)
        # ports, trusts, services
        self.set_enabled_ports(data.firewall.ports)
        self.set_trusts(data.firewall.trusts)
        self.set_enabled_services(data.firewall.services)
        self.set_disabled_services(data.firewall.remove_services)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        if self.firewall_mode is FirewallMode.USE_SYSTEM_DEFAULTS:
            data.firewall.use_system_defaults = True
        elif self.firewall_mode is FirewallMode.ENABLED:
            data.firewall.enabled = True
        elif self.firewall_mode is FirewallMode.DISABLED:
            data.firewall.enabled = False
        data.firewall.ports = self.enabled_ports
        data.firewall.trusts = self.trusts
        data.firewall.services = self.enabled_services
        data.firewall.remove_services = self.disabled_services

    @property
    def firewall_seen(self):
        """Reports if the firewall command was present in the input kickstart.

        :return: if the firewall command was seen in input kickstart
        :rtype: bool
        """
        return self._firewall_seen

    def set_firewall_seen(self, firewall_seen):
        """Set if the firewall command was present in the input kickstart.

        :param bool firewall_seen: if the firewall command has been present in input kickstart
        """
        self._firewall_seen = firewall_seen
        log.debug("Firewall command considered seen in kickstart: %s.", self._firewall_seen)

    @property
    def firewall_mode(self):
        """Firewall mode for the target system.

        :return: the firewall mode for the target system
        :rtype: FirewallMode enum
        """
        return self._firewall_mode

    def set_firewall_mode(self, firewall_mode):
        """Set the firewall mode for the target system.

        :param firewall_mode: firewall mode for the target system
        :type firewall_mode: FirewallMode enum
        """
        self._firewall_mode = firewall_mode
        self.firewall_mode_changed.emit()
        log.debug("Firewall mode will be: %s", firewall_mode)

    @property
    def enabled_ports(self):
        """Ports that should be enabled on the target system firewall.

        :return: ports that should be enabled
        :rtype: list of strings
        """
        return self._enabled_ports

    def set_enabled_ports(self, enabled_ports):
        """Set what ports should be enabled on the target system firewall.

        :param enabled_ports: ports to be enabled
        :rtype enabled_ports: list of str
        """
        self._enabled_ports = list(enabled_ports)
        self.enabled_ports_changed.emit()
        log.debug("Ports that will be allowed through the firewall: %s", self._enabled_ports)

    @property
    def trusts(self):
        """List of network devices to be allowed through the target system firewall.

        :return: network devices to be allowed
        :rtype: list of str
        """
        return self._trusts

    def set_trusts(self, trusts):
        """Set which network devices should be allowed through the target system firewall.

        :param trusts: network devices to be allowed
        :type trusts: list of str
        """
        self._trusts = list(trusts)
        self.trusts_changed.emit()
        log.debug("Trusted devices that will be allowed through the firewall: %s", self._trusts)

    @property
    def enabled_services(self):
        """List of network services to be allowed on the target system firewall.

        :return: network services to be allowed
        :rtype: list of str
        """
        return self._enabled_services

    def set_enabled_services(self, enabled_services):
        """Set which network services should be allowed on the target system firewall.

        :param enabled_services: network services to be allowed
        :type: list of str
        """
        self._enabled_services = list(enabled_services)
        self.enabled_services_changed.emit()
        log.debug("Services that will be allowed through the firewall: %s",
                  self._enabled_services)

    @property
    def disabled_services(self):
        """List of network services to be explicitly disabled on the target system firewall.

        :return: network services to be disabled
        :rtype: list of str
        """
        return self._disabled_services

    def set_disabled_services(self, disabled_services):
        """Set which network services should be explicitly disabled on the target system firewall.

        :param disabled_services: network services to be disabled
        :type: list of str
        """
        self._disabled_services = list(disabled_services)
        self.disabled_services_changed.emit()
        log.debug("Services that will be explicitly disabled on the firewall: %s",
                  self._disabled_services)

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        requirements = []

        if self.firewall_seen:
            requirements.append(Requirement.for_package(
                "firewalld",
                reason="Requested by the firewall kickstart command."
            ))

        return requirements

    def install_with_task(self):
        """Return the installation task of this module.

        :returns: an installation task
        """
        return ConfigureFirewallTask(
            sysroot=conf.target.system_root,
            firewall_mode=self.firewall_mode,
            enabled_services=self.enabled_services,
            disabled_services=self.disabled_services,
            enabled_ports=self.enabled_ports,
            trusts=self.trusts
        )
