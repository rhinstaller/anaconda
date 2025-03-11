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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.errors.installation import FirewallConfigurationError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.network.constants import FirewallMode

log = get_module_logger(__name__)


class ConfigureFirewallTask(Task):
    """Installation task for firewall configuration."""

    FIREWALL_OFFLINE_CMD = "/usr/bin/firewall-offline-cmd"

    def __init__(self, sysroot, firewall_mode, enabled_services, disabled_services,
                 enabled_ports, trusts):
        """Create a new task,

        :param sysroot: a path to the root of the installed system
        :param int firewall_mode: firewall operation mode
        :param enabled_services: a list of services that should be allowed through the firewall
        :type enabled_services: a list of strings
        :param disabled_services: a list of services to be explicitly disabled on the firewall
        :type disabled_services: a list of strings
        :param enabled_ports: a list of ports that should be enabled through the firewall
        :type enabled_ports: a list of strings
        :param trusts:  list of trusted devices to be allowed through the firewall
        :type trusts: a list of strings
        """
        super().__init__()
        self._sysroot = sysroot
        self._firewall_mode = firewall_mode
        self._enabled_services = enabled_services
        self._disabled_services = disabled_services
        self._enabled_ports = enabled_ports
        self._trusts = trusts

    @property
    def name(self):
        return "Configure firewall"

    def run(self):
        args = []

        # If --use-system-defaults was passed then the user wants
        # whatever was provided by the rpms or ostree to be the
        # default, do nothing.
        if self._firewall_mode == FirewallMode.USE_SYSTEM_DEFAULTS:
            log.info("ks file instructs to use system defaults for firewall, "
                     "skipping configuration.")
            return

        # enabled is None if neither --enable or --disable is passed
        # default to enabled if nothing has been set.
        if self._firewall_mode == FirewallMode.DISABLED:
            args += ["--disabled"]
        else:
            args += ["--enabled"]

        ssh_service_not_enabled = "ssh" not in self._enabled_services
        ssh_service_not_disabled = "ssh" not in self._disabled_services
        ssh_port_not_enabled = "22:tcp" not in self._enabled_ports

        # always enable SSH unless the service is explicitely disabled
        if ssh_service_not_enabled and ssh_service_not_disabled and ssh_port_not_enabled:
            args += ["--service=ssh"]

        for dev in self._trusts:
            args += ["--trust=%s" % (dev,)]

        for port in self._enabled_ports:
            args += ["--port=%s" % (port,)]

        for remove_service in self._disabled_services:
            args += ["--remove-service=%s" % (remove_service,)]

        for service in self._enabled_services:
            args += ["--service=%s" % (service,)]

        if not os.path.exists(self._sysroot + self.FIREWALL_OFFLINE_CMD):
            if self._firewall_mode == FirewallMode.ENABLED:
                msg = _("%s is missing. Cannot setup firewall.") % (self.FIREWALL_OFFLINE_CMD,)
                raise FirewallConfigurationError(msg)
        else:
            execWithRedirect(self.FIREWALL_OFFLINE_CMD, args, root=self._sysroot)
