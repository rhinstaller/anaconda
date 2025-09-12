#
# Discovery tasks
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
from blivet.iscsi import TargetInfo, iscsi

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError
from pyanaconda.modules.common.structures.iscsi import Credentials, Node, Portal
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.storage.constants import IscsiInterfacesMode
from pyanaconda.modules.storage.iscsi.iscsi_interface import ISCSIDiscoverTaskInterface

log = get_module_logger(__name__)


class ISCSIDiscoverTask(Task):
    """A task for discovering iSCSI nodes"""

    def __init__(self, portal: Portal, credentials: Credentials,
                 interfaces_mode: IscsiInterfacesMode):
        """Create a new task.

        :param portal: the portal information
        :param credentials: the iSCSI credentials
        :param interfaces_mode: the mode of interfaces used for operation
        """
        super().__init__()
        self._portal = portal
        self._credentials = credentials
        self._interfaces_mode = interfaces_mode
        self._nodes = []

    @property
    def name(self):
        return "Discover iSCSI nodes"

    def for_publication(self):
        """Return a DBus representation."""
        return ISCSIDiscoverTaskInterface(self)

    def run(self):
        """Run the discovery."""
        self._update_interfaces(self._interfaces_mode)
        node_infos = self._discover_nodes(self._portal, self._credentials)
        self._nodes = [self._get_node_from_node_info(node_info)
                       for node_info in node_infos]
        return self._nodes

    def _get_node_from_node_info(self, node_info):
        node = Node()
        node.name = node_info.name
        node.address = node_info.address
        node.port = str(node_info.port)
        node.iface = node_info.iface
        if self._interfaces_mode == IscsiInterfacesMode.IFACENAME:
            node.net_ifacename = iscsi.ifaces[node_info.iface]
        return node

    def _update_interfaces(self, interfaces_mode):
        """Update the interfaces according to requested mode.

        :param interfaces_mode: required mode specified by IscsiInterfacesMode
        """
        if interfaces_mode == IscsiInterfacesMode.DEFAULT and iscsi.mode in ("default", "none"):
            if iscsi.ifaces:
                iscsi.delete_interfaces()
        elif interfaces_mode == IscsiInterfacesMode.IFACENAME and iscsi.mode in ("bind", "none"):
            network_proxy = NETWORK.get_proxy()
            activated = set(network_proxy.GetActivatedInterfaces())
            created = set(iscsi.ifaces.values())
            iscsi.create_interfaces(activated - created)
        else:
            raise StorageDiscoveryError('Requiring "{}" mode while "{}" is already set.'.format(
                                        interfaces_mode, iscsi.mode))

    def _discover_nodes(self, portal, credentials):
        """Discover iSCSI nodes.

        :param portal: the portal information
        :param credentials: the iSCSI credentials
        :return: a list of discovered nodes
        """
        try:
            nodes = iscsi.discover(
                ipaddr=portal.ip_address,
                username=credentials.username,
                password=credentials.password,
                r_username=credentials.reverse_username,
                r_password=credentials.reverse_password
            )
        except Exception as e:  # pylint: disable=broad-except
            raise StorageDiscoveryError(str(e).split(':')[-1]) from e

        if not nodes:
            raise StorageDiscoveryError("No nodes discovered.")

        return nodes


class ISCSILoginTask(Task):
    """A task for logging into an iSCSI node."""

    def __init__(self, portal: Portal, credentials: Credentials, node: Node):
        """Create a new task.

        :param portal: the portal information
        :param credentials: the iSCSI credentials
        :param node: the node information
        """
        super().__init__()
        self._portal = portal
        self._credentials = credentials
        self._node = node

    @property
    def name(self):
        return "Log into an iSCSI node"

    def run(self):
        """Run the login."""
        node_info = self._get_node_info(self._portal, self._node)
        self._log_into_node(node_info, self._credentials)

    def _get_node_info(self, portal, node):
        """Get the node info.

        :param portal: an instance of Portal
        :param node: an instance of Node
        :return: an instance of NodeInfo or None
        """
        target_info = TargetInfo(portal.ip_address, portal.port)

        portal_nodes = [
            info.node
            for info in iscsi.discovered_targets.get(target_info, [])
            if not info.logged_in
        ]

        for info in portal_nodes:
            if info.name == node.name and info.address == node.address and \
               info.port == int(node.port) and info.iface == node.iface:
                return info

        raise StorageDiscoveryError("Unknown node.")

    def _log_into_node(self, node_info, credentials):
        """Log into the node.

        :param node_info: an instance of NodeInfo
        :param credentials: an instance of Credentials
        """
        rc, msg = iscsi.log_into_node(
            node=node_info,
            username=credentials.username,
            password=credentials.password,
            r_username=credentials.reverse_username,
            r_password=credentials.reverse_password
        )

        if not rc:
            raise StorageDiscoveryError(msg)
