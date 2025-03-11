#
# FCoE module
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
from blivet.fcoe import fcoe, has_fcoe

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import FCOE
from pyanaconda.modules.storage.fcoe.discover import FCOEDiscoverTask
from pyanaconda.modules.storage.fcoe.fcoe_interface import FCOEInterface

log = get_module_logger(__name__)


class FCOEModule(KickstartBaseModule):
    """The FCoE module."""

    def __init__(self):
        super().__init__()
        self.reload_module()
        self._fcoe_data = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(FCOE.object_path, FCOEInterface(self))

    def is_supported(self):
        """Is this module supported?"""
        return has_fcoe()

    def reload_module(self):
        """Reload the fcoe module."""
        log.debug("Start up the FCoE module.")
        fcoe.startup()

    def discover_with_task(self, nic, dcb, auto_vlan):
        """Discover a FCoE device.

        :param nic: a name of the network device
        :param dcb: Data Center Bridging awareness enabled
        :param auto_vlan: automatic VLAN discovery and setup enabled
        :return: a task
        """
        return FCOEDiscoverTask(nic, dcb, auto_vlan)

    def write_configuration(self):
        """Write the configuration to sysroot."""
        log.debug("Write FCoE configuration.")
        fcoe.write(conf.target.system_root)

    def get_nics(self):
        """Get all NICs.

        :return: a list of names of network devices connected to FCoE switches
        """
        return [nic for nic, dcb, auto_vlan in fcoe().nics]

    def get_dracut_arguments(self, nic):
        """Get dracut arguments for the given FCoE device.

        :param nic: a name of the network device
        :return: a list of dracut arguments

        FIXME: This is just a temporary method taken from blivet.
        """
        log.debug("Getting dracut arguments for FCoE nic %s", nic)

        dcb = True

        for _nic, _dcb, _auto_vlan in fcoe().nics:
            if nic == _nic:
                dcb = _dcb
                break
        else:
            return []

        dcb_opt = "dcb" if dcb else "nodcb"

        if nic in fcoe().added_nics:
            return ["fcoe=%s:%s" % (nic, dcb_opt)]
        else:
            return ["fcoe=edd:%s" % dcb_opt]

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._fcoe_data = data.fcoe.fcoe

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.fcoe.fcoe = self._fcoe_data
