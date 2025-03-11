#
# The iSCSI module
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
from blivet.iscsi import iscsi

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import ISCSI
from pyanaconda.modules.storage.constants import IscsiInterfacesMode
from pyanaconda.modules.storage.iscsi.discover import ISCSIDiscoverTask, ISCSILoginTask
from pyanaconda.modules.storage.iscsi.iscsi_interface import ISCSIInterface

log = get_module_logger(__name__)


class ISCSIModule(KickstartBaseModule):
    """The iSCSI module."""

    def __init__(self):
        super().__init__()
        self.reload_module()

        self.initiator_changed = Signal()

        self._iscsi_data = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(ISCSI.object_path, ISCSIInterface(self))

    def is_supported(self):
        """Is this module supported?"""
        return bool(iscsi.available)

    def reload_module(self):
        """Reload the iscsi module."""
        log.debug("Start up the iSCSI module.")
        iscsi.startup()

    @property
    def initiator(self):
        """The iSCSI initiator.

        :return: a name of the initiator
        """
        return iscsi.initiator

    def set_initiator(self, initiator):
        """Set the iSCSI initiator.

        :param initiator: a name of the initiator
        """
        if not iscsi.initiator_set or (initiator != iscsi.initiator and self.can_set_initiator()):
            iscsi.initiator = initiator
            self.initiator_changed.emit()
            log.debug("The iSCSI initiator is set to '%s'.", initiator)
        else:
            log.debug("The iSCSI initiator has already been set to '%s'.", iscsi.initiator)

    def can_set_initiator(self):
        """Can the initiator be set?

        Initiator name can be changed when no sessions are active.
        """
        active = iscsi._get_active_sessions()
        return not active

    def get_interface_mode(self):
        """Get the mode of interfaces used for iSCSI operations.

        returns: an instance of IscsiInterfacesMode
        """
        mode = iscsi.mode
        if mode == "none":
            return IscsiInterfacesMode.UNSET
        elif mode == "default":
            return IscsiInterfacesMode.DEFAULT
        elif mode == "bind":
            return IscsiInterfacesMode.IFACENAME
        else:
            log.error("Unknown iSCSI interface mode %s set by blivet, using UNSET", mode)
            return IscsiInterfacesMode.UNSET

    def discover_with_task(self, portal, credentials, interfaces_mode):
        """Discover an iSCSI device.

        :param portal: the portal information
        :param credentials: the iSCSI credentials
        :param interfaces_mode: required mode specified by IscsiInterfacesMode
        :return: a task
        """
        return ISCSIDiscoverTask(portal, credentials, interfaces_mode)

    def login_with_task(self, portal, credentials, node):
        """Login into an iSCSI node discovered on a portal.

        :param portal: the portal information
        :param credentials: the iSCSI credentials
        :param node: the node information
        :return: a task
        """
        return ISCSILoginTask(portal, credentials, node)

    def write_configuration(self):
        """Write the configuration to sysroot."""
        log.debug("Write iSCSI configuration.")
        iscsi.write(conf.target.system_root, None)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        if data.iscsiname.iscsiname:
            self.set_initiator(data.iscsiname.iscsiname)
        self._iscsi_data = data.iscsi.iscsi

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.iscsi.iscsi = self.generate_iscsi_data(data.IscsiData)
        if data.iscsi.iscsi:
            data.iscsiname.iscsiname = self.initiator

    def generate_iscsi_data(self, iscsi_data_class):
        """Generate kickstart data based on original kickstart and attached nodes.

        If all nodes for a target were added by a kickstart command, preserve
        this in generated kickstart (ie do not add particular commands for each
        discovered node).
        """
        iscsi_data_list = list(self._iscsi_data)

        for node in iscsi.active_nodes():
            if node in iscsi.ibft_nodes:
                continue
            iscsi_data = iscsi_data_class()
            self._setup_iscsi_data_from_node(iscsi_data, node)

            for ks_command_data in iscsi_data_list:
                # If there is already a (perhaps more general) command
                # attaching the node, do not add another one
                if (iscsi_data.ipaddr == ks_command_data.ipaddr and
                    (not ks_command_data.target or iscsi_data.target == ks_command_data.target) and
                    iscsi_data.port == ks_command_data.port and
                    iscsi_data.iface == ks_command_data.iface):
                    break
            else:
                iscsi_data_list.append(iscsi_data)

        return iscsi_data_list

    def _setup_iscsi_data_from_node(self, iscsi_data, dev_node):
        """Set up iSCSI data from a device node.

        :param iscsi_data: an instance of iSCSI data
        :param dev_node: a device node NodeInfo object
        """
        iscsi_data.ipaddr = dev_node.address
        iscsi_data.target = dev_node.name
        iscsi_data.port = dev_node.port

        if iscsi.ifaces:
            iscsi_data.iface = iscsi.ifaces[dev_node.iface]

        if dev_node.username and dev_node.password:
            iscsi_data.user = dev_node.username
            iscsi_data.password = dev_node.password

        if dev_node.r_username and dev_node.r_password:
            iscsi_data.user_in = dev_node.r_username
            iscsi_data.password_in = dev_node.r_password

        return iscsi_data

    def get_interface(self, iscsi_iface):
        """Get network interface backing iscsi iface.

        :param iscsi_iface: name of an iscsi interface (eg iface0)
        :returns: specification of interface backing the iscsi iface (eg ens3)
                  or "" if there is none
        """
        return iscsi.ifaces.get(iscsi_iface, "")

    def is_node_from_ibft(self, node):
        """Is the node configured from iBFT table?.

        :param node: the node information
        """
        for ibft_node in iscsi.ibft_nodes:
            if ibft_node.name == node.name and ibft_node.address == node.address \
                    and ibft_node.port == int(node.port) and ibft_node.iface == node.iface:
                return True
        return False

    def get_dracut_arguments(self, node):
        """Get dracut arguments for iSCSI device backed by the node.

        :param node: the node information
        :return: a list of dracut arguments

        FIXME: This is just a temporary method.
        """
        log.debug("Getting dracut arguments for iSCSI node %s", node)

        if self.is_node_from_ibft(node):
            return ["rd.iscsi.firmware"]

        blivet_node = iscsi.get_node(node.name, node.address, node.port, node.iface)

        if not blivet_node:
            log.error("No iSCSI node %s found for device", node)
            return []

        address = blivet_node.address
        # surround ipv6 addresses with []
        if ":" in address:
            address = "[{}]".format(address)

        netroot = "netroot=iscsi:"
        if blivet_node.username and blivet_node.password:
            netroot += "{}:{}".format(blivet_node.username, blivet_node.password)
            if blivet_node.r_username and blivet_node.r_password:
                netroot += ":{}:{}".format(blivet_node.r_username, blivet_node.r_password)

        iface_spec = ""
        interface = self.get_interface(blivet_node.iface) or blivet_node.iface
        if interface != "default":
            iface_spec = ":{}:{}".format(blivet_node.iface, interface)
        netroot += "@{}::{}{}::{}".format(address, blivet_node.port, iface_spec, blivet_node.name)

        initiator = "rd.iscsi.initiator={}".format(self.initiator)

        return [netroot, initiator]
