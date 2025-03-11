#
# Kickstart handler for network and hostname settings
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
from pykickstart.errors import KickstartParseError

from pyanaconda.core.kickstart import KickstartSpecification
from pyanaconda.core.kickstart import commands as COMMANDS
from pyanaconda.network import is_valid_hostname

DEFAULT_DEVICE_SPECIFICATION = "link"


class Network(COMMANDS.Network):
    def parse(self, args):
        hostname_only_command = is_hostname_only_network_args(args)
        # call the overridden command to do it's job first
        retval = super().parse(args)

        if hostname_only_command:
            retval.bootProto = ""

        if retval.hostname:
            (result, reason) = is_valid_hostname(retval.hostname)
            if not result:
                message = "Hostname '{}' given in network kickstart command is invalid: {}"\
                    .format(retval.hostname, reason)
                raise KickstartParseError(message, lineno=self.lineno)

        return retval


class NetworkKickstartSpecification(KickstartSpecification):

    commands = {
        "network": Network,
        "firewall": COMMANDS.Firewall,
    }

    commands_data = {
        "NetworkData": COMMANDS.NetworkData,
    }


# TODO force moving hostname data into separate line?
def update_network_hostname_data(network_data_list, hostname_data):
    """Apply hostname value to kickstart network data."""
    hostname_found = False
    for nd in network_data_list:
        if nd.hostname:
            nd.hostname = hostname_data.hostname
            hostname_found = True
    if not hostname_found:
        network_data_list.append(hostname_data)


def update_network_data_with_default_device(network_data_list, device_specification):
    """Apply default --device value to kickstart network data."""
    updated = False
    for nd in network_data_list:
        if not nd.device and not is_hostname_only_network_data(nd):
            nd.device = device_specification
            updated = True
    return updated


def update_first_network_command_activate_value(network_data_list):
    """Applies the historical default to the first network command.

    For the first network command the device is activated by default.  To
    override it --no-activate option has to be used. For following network
    commands the devices are not activated by default.

    """
    if network_data_list:
        nd = network_data_list[0]
        if not is_hostname_only_network_data(nd):
            if nd.activate is None:
                nd.activate = True
                return True
    return False


def is_hostname_only_network_args(args):
    return ((len(args) == 1 and args[0].startswith("--hostname")) or
            (len(args) == 2 and "--hostname" in args))


def is_hostname_only_network_data(network_data):
    return network_data.bootProto == ""


def default_ks_vlan_interface_name(parent, vlanid):
    return "%s.%s" % (parent, vlanid)
