#
# DBus interface for the iSCSI module.
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
from dasbus.server.interface import dbus_class, dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import ISCSI
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.iscsi import Credentials, Node, Portal
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.storage.constants import IscsiInterfacesMode


@dbus_class
class ISCSIDiscoverTaskInterface(TaskInterface):
    """The interface for iSCSI discovery task.

    Returns a list of Node structures representing discovered nodes.
    """

    @staticmethod
    def convert_result(value):
        return get_variant(List[Structure], Node.to_structure_list(value))


@dbus_interface(ISCSI.interface_name)
class ISCSIInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the iSCSI module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Initiator", self.implementation.initiator_changed)

    def IsSupported(self) -> Bool:
        """Is this module supported?"""
        return self.implementation.is_supported()

    @property
    def Initiator(self) -> Str:
        """ISCSI initiator name."""
        return self.implementation.initiator

    @Initiator.setter
    @emits_properties_changed
    def Initiator(self, initiator: Str):
        """Set the initiator name.

        Sets the ISCSI initiator name.

        :param initiator: a string with initiator name
        """
        self.implementation.set_initiator(initiator)

    def CanSetInitiator(self) -> Bool:
        """Can the iSCSI initator be set?

        Initiator name can be changed when no sessions are active.
        """
        return self.implementation.can_set_initiator()

    def GetInterfaceMode(self) -> Str:
        """Get the mode of interface used for iSCSI operations.

        The mode is chosen during discovery of nodes.  Once there there are
        active nodes logged in using particular mode, the mode can't be
        changed.

        Return values: IscsiInterfacesMode
        """
        return self.implementation.get_interface_mode().value

    def DiscoverWithTask(
        self,
        portal: Structure,
        credentials: Structure,
        interfaces_mode: Str
    ) -> ObjPath:
        """Discover an iSCSI device.

        :param portal: the portal information
        :param credentials: the iSCSI credentials
        :param interfaces_mode: required mode specified by IscsiInterfacesMode string value
        :return: a DBus path to a task
        """
        portal = Portal.from_structure(portal)
        credentials = Credentials.from_structure(credentials)
        interfaces_mode = IscsiInterfacesMode(interfaces_mode)
        return TaskContainer.to_object_path(
            self.implementation.discover_with_task(portal, credentials, interfaces_mode)
        )

    def LoginWithTask(
        self,
        portal: Structure,
        credentials: Structure,
        node: Structure
    ) -> ObjPath:
        """Login into an iSCSI node discovered on a portal.

        :param portal: the portal information
        :param credentials: the iSCSI credentials
        :param node: the node information
        :return: a DBus path to a task
        """
        portal = Portal.from_structure(portal)
        credentials = Credentials.from_structure(credentials)
        node = Node.from_structure(node)
        return TaskContainer.to_object_path(
            self.implementation.login_with_task(portal, credentials, node)
        )

    def IsNodeFromIbft(self, node: Structure) -> Bool:
        """Is the node configured from iBFT table?.

        :param node: the node information
        """
        node = Node.from_structure(node)
        return self.implementation.is_node_from_ibft(node)

    def GetInterface(self, iscsi_iface: Str) -> Str:
        """Get network interface backing iscsi iface.

        :param iscsi_iface: name of an iscsi interface (eg iface0)
        :returns: specification of interface backing the iscsi iface (eg ens3)
                  or "" if there is none
        """
        return self.implementation.get_interface(iscsi_iface)

    def GetDracutArguments(self, node: Structure) -> List[Str]:
        """Get dracut arguments for iSCSI device backed by the node.

        :param node: the node information
        :return: a list of dracut arguments

        FIXME: This is just a temporary method.
        """
        node = Node.from_structure(node)
        return self.implementation.get_dracut_arguments(node)

    def WriteConfiguration(self):
        """Write the configuration to sysroot.

        FIXME: This is just a temporary method.
        """
        self.implementation.write_configuration()
