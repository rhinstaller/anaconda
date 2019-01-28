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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet.iscsi import iscsi, TargetInfo
from blivet.safe_dbus import SafeDBusError

from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError
from pyanaconda.modules.common.structures.iscsi import Target, Credentials, Node
from pyanaconda.modules.common.task import Task


class ISCSIDiscoverTask(Task):
    """A task for discovering iSCSI nodes"""

    def __init__(self, target: Target, credentials: Credentials):
        """Create a new task.

        :param target: the target information
        :param credentials: the iSCSI credentials
        """
        super().__init__()
        self._target = target
        self._credentials = credentials
        self._nodes = []

    @property
    def name(self):
        return "Discover iSCSI nodes"

    def run(self):
        """Run the discovery."""
        self._set_initiator(self._target.initiator)
        self._update_interfaces(self._target.bind)
        self._nodes = self._discover_nodes(self._target, self._credentials)

    def _set_initiator(self, initiator):
        """Set up the initiator.

        :param initiator: a name of the initiator
        """
        if not iscsi.initiator_set:
            iscsi.initiator = initiator

    def _update_interfaces(self, bind):
        """Update the interfaces.

        :param bind: bind targets to network interfaces?
        """
        if iscsi.mode == "none" and not bind:
            iscsi.delete_interfaces()
        elif iscsi.mode == "bind" or iscsi.mode == "none" and bind:
            network_proxy = NETWORK.get_proxy()
            activated = set(network_proxy.GetActivatedInterfaces())
            created = set(iscsi.ifaces.values())
            iscsi.create_interfaces(activated - created)

    def _discover_nodes(self, target, credentials):
        """Discover iSCSI nodes.

        :param target: the target information
        :param credentials: the iSCSI credentials
        :return: a list of discovered nodes
        """
        try:
            nodes = iscsi.discover(
                ipaddr=target.ip_address,
                username=credentials.username,
                password=credentials.password,
                r_username=credentials.reverse_username,
                r_password=credentials.reverse_password
            )
        except SafeDBusError as e:
            raise StorageDiscoveryError(str(e).split(':')[-1])

        if not nodes:
            raise StorageDiscoveryError("No nodes discovered.")

        return nodes


class ISCSILoginTask(Task):
    """A task for logging into an iSCSI node."""

    def __init__(self, target: Target, credentials: Credentials, node: Node):
        """Create a new task.

        :param target: the target information
        :param credentials: the iSCSI credentials
        :param node: the node information
        """
        super().__init__()
        self._target = target
        self._credentials = credentials
        self._node = node

    @property
    def name(self):
        return "Log into an iSCSI node"

    def run(self):
        """Run the discovery."""
        if self._skip_interface(self._node.interface):
            return

        node_info = self._get_node_info(self._target, self._node)
        self._log_into_node(node_info, self._credentials)

    def _skip_interface(self, interface):
        """Should we skip logging for the given interface?

        FIXME: Should we raise an error?

        :param interface: a name of an interface
        :return: True or False
        """
        return iscsi.ifaces and interface != iscsi.ifaces[interface]

    def _get_node_info(self, target, node):
        """Get the node info.

        :param target: an instance of Target
        :param node: an instance of Node
        :return: an instance of NodeInfo or None
        """
        target_info = TargetInfo(target.ip_address, target.port)

        target_nodes = [
            info.node
            for info in iscsi.discovered_targets.get(target_info, [])
            if not info.logged_in
        ]

        for info in target_nodes:
            if info.name == node.name and info.address == node.address and \
               info.port == int(node.port) and info.iface == node.interface:
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
