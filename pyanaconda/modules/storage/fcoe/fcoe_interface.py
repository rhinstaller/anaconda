#
# DBus interface for the FCoE module.
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
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import FCOE
from pyanaconda.modules.common.containers import TaskContainer


@dbus_interface(FCOE.interface_name)
class FCOEInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the FCoE module."""

    def IsSupported(self) -> Bool:
        """Is this module supported?"""
        return self.implementation.is_supported()

    def DiscoverWithTask(self, nic: Str, dcb: Bool, auto_vlan: Bool) -> ObjPath:
        """Discover a FCoE device.

        :param nic: a name of the network device
        :param dcb: Data Center Bridging awareness enabled
        :param auto_vlan: automatic VLAN discovery and setup enabled
        :return: a DBus path to a task
        """
        return TaskContainer.to_object_path(
            self.implementation.discover_with_task(nic, dcb, auto_vlan)
        )

    def WriteConfiguration(self):
        """Write the configuration to sysroot.

        FIXME: This is just a temporary method.
        """
        self.implementation.write_configuration()

    def GetNics(self) -> List[Str]:
        """Get all NICs.

        :return: a list of names of network devices connected to FCoE switches
        """
        return self.implementation.get_nics()

    def GetDracutArguments(self, nic: Str) -> List[Str]:
        """Get dracut arguments for the given FCoE device.

        :param nic: a name of the network device connected to the FCoE switch
        :return: a list of dracut arguments

        FIXME: This is just a temporary method.
        """
        return self.implementation.get_dracut_arguments(nic)
