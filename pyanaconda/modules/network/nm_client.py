#
# utility functions using libnm
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

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM

import socket
from queue import Queue
from pykickstart.constants import BIND_TO_MAC
from pyanaconda.modules.network.constants import NM_CONNECTION_UUID_LENGTH
from pyanaconda.modules.network.kickstart import default_ks_vlan_interface_name
from pyanaconda.modules.network.utils import is_s390, get_s390_settings, netmask2prefix

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def get_iface_from_connection(nm_client, uuid):
    """Get the name of device that would be used for the connection.

    In installer it should be just one device.
    We need to account also for the case of configurations bound to mac address
    (HWADDR), eg network --bindto=mac command.
    """
    connection = nm_client.get_connection_by_uuid(uuid)
    if not connection:
        return None
    iface = connection.get_setting_connection().get_interface_name()
    if not iface:
        wired_setting = connection.get_setting_wired()
        if wired_setting:
            mac = wired_setting.get_mac_address()
            if mac:
                iface = get_iface_from_hwaddr(nm_client, mac)
    return iface


def get_vlan_interface_name_from_connection(nm_client, connection):
    """Get vlan interface name from vlan connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection

    If no interface name is specified in the connection settings, infer the
    value as <PARENT_IFACE>.<VLAN_ID> - same as NetworkManager.
    """
    iface = connection.get_setting_connection().get_interface_name()
    if not iface:
        setting_vlan = connection.get_setting_vlan()
        if setting_vlan:
            vlanid = setting_vlan.get_id()
            parent = setting_vlan.get_parent()
            # if parent is specified by UUID
            if len(parent) == NM_CONNECTION_UUID_LENGTH:
                parent = get_iface_from_connection(nm_client, parent)
            if vlanid is not None and parent:
                iface = default_ks_vlan_interface_name(parent, vlanid)
    return iface


def get_iface_from_hwaddr(nm_client, hwaddr):
    """Find the name of device specified by mac address."""
    for device in nm_client.get_devices():
        if device.get_device_type() in (NM.DeviceType.ETHERNET,
                                        NM.DeviceType.WIFI):
            try:
                address = device.get_permanent_hw_address()
                if not address:
                    address = device.get_hw_address()
            except AttributeError as e:
                log.warning("Device %s: %s", device.get_iface(), e)
                address = device.get_hw_address()
        else:
            address = device.get_hw_address()
        # per #1703152, at least in *some* case, we wind up with
        # address as None here, so we need to guard against that
        if address and address.upper() == hwaddr.upper():
            return device.get_iface()
    return None


def get_team_port_config_from_connection(nm_client, uuid):
    connection = nm_client.get_connection_by_uuid(uuid)
    if not connection:
        return None
    team_port = connection.get_setting_team_port()
    if not team_port:
        return None
    config = team_port.get_config()
    return config


def get_team_config_from_connection(nm_client, uuid):
    connection = nm_client.get_connection_by_uuid(uuid)
    if not connection:
        return None
    team = connection.get_setting_team()
    if not team:
        return None
    config = team.get_config()
    return config


def get_device_name_from_network_data(nm_client, network_data, supported_devices, bootif):
    """Get the device name from kickstart device specification.

    Generally given by --device option. For vlans also --interfacename
    and --vlanid comes into play.

    Side effect: for vlan sets network_data.parent value from --device option

    :param network_data: a kickstart device configuartion
    :type network_data: kickstart NetworkData object
    :param supported_devices: list of names of supported devices
    :type supported_devices: list(str)
    :param bootif: MAC addres of device to be used for --device=bootif specification
    :type bootif: str
    :returns: device name the configuration should be used for
    :rtype: str
    """
    spec = network_data.device
    device_name = ""
    msg = ""

    if not spec:
        msg = "device specification missing"

    # Specification by device name
    if spec in supported_devices:
        device_name = spec
        msg = "existing device found"
    # Specification by mac address
    elif ':' in spec:
        device_name = get_iface_from_hwaddr(nm_client, spec) or ""
        msg = "existing device found"
    # Specification by BOOTIF boot option
    elif spec == 'bootif':
        if bootif:
            device_name = get_iface_from_hwaddr(nm_client, bootif) or ""
            msg = "existing device for {} found".format(bootif)
        else:
            msg = "BOOTIF value is not specified in boot options"
    # First device with carrier (sorted lexicographically)
    elif spec == 'link':
        device_name = get_first_iface_with_link(nm_client, supported_devices) or ""
        msg = "first device with link found"

    if device_name:
        if device_name not in supported_devices:
            msg = "{} device found is not supported".format(device_name)
            device_name = ""
    # Virtual devices don't have to exist
    elif spec and any((network_data.vlanid,
                       network_data.bondslaves,
                       network_data.teamslaves,
                       network_data.bridgeslaves)):
        device_name = spec
        msg = "virtual device does not exist, which is OK"

    if network_data.vlanid:
        network_data.parent = device_name
        if network_data.interfacename:
            device_name = network_data.interfacename
            msg = "vlan device name specified by --interfacename"
        else:
            device_name = default_ks_vlan_interface_name(device_name, network_data.vlanid)
            msg = "vlan device name inferred from parent and vlanid"

    log.debug("kickstart specification --device=%s -> %s (%s)", spec, device_name, msg)
    return device_name


def _update_bond_connection_from_ksdata(connection, network_data):
    """Update connection with values from bond kickstart configuration.

    :param connection: connection to be updated before adding to NM
    :type connection: NM.SimpleConnection
    :param network_data: kickstart configuration
    :type network_data: pykickstart NetworkData
    """
    s_con = connection.get_setting_connection()
    s_con.props.type = "bond"

    s_bond = NM.SettingBond.new()
    opts = network_data.bondopts
    for option in opts.split(';' if ';' in opts else ','):
        key, _sep, value = option.partition("=")
        if not s_bond.add_option(key, value):
            log.warning("adding bond option %s failed (invalid?)")
    connection.add_setting(s_bond)


def _update_team_connection_from_ksdata(connection, network_data):
    """Update connection with values from team kickstart configuration.

    :param connection: connection to be updated before adding to NM
    :type connection: NM.SimpleConnection
    :param network_data: kickstart configuration
    :type network_data: pykickstart NetworkData
    """
    s_con = connection.get_setting_connection()
    s_con.props.type = "team"

    s_team = NM.SettingTeam.new()
    s_team.props.config = network_data.teamconfig
    connection.add_setting(s_team)


def _update_vlan_connection_from_ksdata(connection, network_data):
    """Update connection with values from vlan kickstart configuration.

    :param connection: connection to be updated before adding to NM
    :type connection: NM.SimpleConnection
    :param network_data: kickstart configuration
    :type network_data: pykickstart NetworkData
    :returns: interface name of the device
    :rtype: str
    """
    s_con = connection.get_setting_connection()
    s_con.props.type = "vlan"
    if network_data.interfacename:
        s_con.props.id = network_data.interfacename
        s_con.props.interface_name = network_data.interfacename
    else:
        s_con.props.interface_name = None

    s_vlan = NM.SettingVlan.new()
    s_vlan.props.id = int(network_data.vlanid)
    s_vlan.props.parent = network_data.parent
    connection.add_setting(s_vlan)

    return s_con.props.interface_name


def _update_bridge_connection_from_ksdata(connection, network_data):
    """Update connection with values from bridge kickstart configuration.

    :param connection: connection to be updated before adding to NM
    :type connection: NM.SimpleConnection
    :param network_data: kickstart configuration
    :type network_data: pykickstart NetworkData
    """
    s_con = connection.get_setting_connection()
    s_con.props.type = "bridge"

    s_bridge = NM.SettingBridge.new()
    for opt in network_data.bridgeopts.split(","):
        key, _sep, value = opt.partition("=")
        if key in ("stp", "multicast-snooping"):
            if value == "yes":
                value = True
            elif value == "no":
                value = False
        else:
            try:
                value = int(value)
            except ValueError:
                log.error("Invalid bridge option %s", opt)
                continue
        s_bridge.set_property(key, value)
    connection.add_setting(s_bridge)


def _update_infiniband_connection_from_ksdata(connection, network_data):
    """Update connection with values from infiniband kickstart configuration.

    :param connection: connection to be updated before adding to NM
    :type connection: NM.SimpleConnection
    :param network_data: kickstart configuration
    :type network_data: pykickstart NetworkData
    """
    s_con = connection.get_setting_connection()
    s_con.props.type = "infiniband"

    s_ib = NM.SettingInfiniband.new()
    s_ib.props.transport_mode = "datagram"
    connection.add_setting(s_ib)


def _update_ethernet_connection_from_ksdata(connection, network_data, bound_mac):
    """Update connection with values from ethernet kickstart configuration.

    :param connection: connection to be updated before adding to NM
    :type connection: NM.SimpleConnection
    :param network_data: kickstart configuration
    :type network_data: pykickstart NetworkData
    :param bound_mac: MAC address the device name is bound to (ifname=)
    :type bound_mac: str
    """
    s_con = connection.get_setting_connection()
    s_con.props.type = "802-3-ethernet"

    s_wired = NM.SettingWired.new()
    if bound_mac:
        s_wired.props.mac_address = bound_mac
    connection.add_setting(s_wired)


def _update_wired_connection_with_s390_settings(connection, s390cfg):
    """Update connection with values specific for s390 architecture.

    :param connection: connection to be updated before adding to NM
    :type connection: NM.SimpleConnection
    :param s390cfg: dictionary storing s390 specific settings
    :type s390cfg: dict
    """
    s_wired = connection.get_setting_wired()
    if s390cfg['SUBCHANNELS']:
        subchannels = s390cfg['SUBCHANNELS'].split(",")
        s_wired.props.s390_subchannels = subchannels
    if s390cfg['NETTYPE']:
        s_wired.props.s390_nettype = s390cfg['NETTYPE']
    if s390cfg['OPTIONS']:
        opts = s390cfg['OPTIONS'].split(" ")
        opts_dict = {k: v for k, v in (o.split("=") for o in opts)}
        s_wired.props.s90_options = opts_dict


def create_connections_from_ksdata(nm_client, network_data, device_name, ifname_option_values=None):
    """Create NM connections from kickstart configuration.

    :param network_data: kickstart configuration
    :type network_data: pykickstart NetworkData
    :param device_name: name of the device to be configured by kickstart
    :type device_name: str
    :param ifname_option_values: list of ifname boot option values
    :type ifname_option_values: list(str)
    :return: list of tuples (CONNECTION, NAME_OF_DEVICE_TO_BE_ACTIVATED)
    :rtype: list((NM.RemoteConnection, str))
    """
    ifname_option_values = ifname_option_values or []
    connections = []
    device_to_activate = device_name

    con_uuid = NM.utils_uuid_generate()
    con = NM.SimpleConnection.new()

    update_connection_ip_settings_from_ksdata(con, network_data)

    s_con = NM.SettingConnection.new()
    s_con.props.uuid = con_uuid
    s_con.props.id = device_name
    s_con.props.interface_name = device_name
    s_con.props.autoconnect = network_data.onboot
    con.add_setting(s_con)

    # type "bond"
    if network_data.bondslaves:
        _update_bond_connection_from_ksdata(con, network_data)

        for i, slave in enumerate(network_data.bondslaves.split(","), 1):
            slave_con = create_slave_connection('bond', i, slave, device_name)
            bind_connection(nm_client, slave_con, network_data.bindto, slave)
            connections.append((slave_con, slave))

    # type "team"
    elif network_data.teamslaves:
        _update_team_connection_from_ksdata(con, network_data)

        for i, (slave, cfg) in enumerate(network_data.teamslaves, 1):
            s_team_port = NM.SettingTeamPort.new()
            s_team_port.props.config = cfg
            slave_con = create_slave_connection('team', i, slave, device_name,
                                                settings=[s_team_port])
            bind_connection(nm_client, slave_con, network_data.bindto, slave)
            connections.append((slave_con, slave))

    # type "vlan"
    elif network_data.vlanid:
        device_to_activate = _update_vlan_connection_from_ksdata(con, network_data)

    # type "bridge"
    elif network_data.bridgeslaves:
        # bridge connection is autoactivated
        _update_bridge_connection_from_ksdata(con, network_data)

        for i, slave in enumerate(network_data.bridgeslaves.split(","), 1):
            slave_con = create_slave_connection('bridge', i, slave, device_name)
            bind_connection(nm_client, slave_con, network_data.bindto, slave)
            connections.append((slave_con, slave))

    # type "infiniband"
    elif is_infiniband_device(nm_client, device_name):
        _update_infiniband_connection_from_ksdata(con, network_data)

    # type "802-3-ethernet"
    else:
        bound_mac = bound_hwaddr_of_device(nm_client, device_name, ifname_option_values)
        _update_ethernet_connection_from_ksdata(con, network_data, bound_mac)
        if bound_mac:
            log.debug("add connection: mac %s is bound to name %s",
                      bound_mac, device_name)
        else:
            bind_connection(nm_client, con, network_data.bindto, device_name)

        # Add s390 settings
        if is_s390():
            s390cfg = get_s390_settings(device_name)
            _update_wired_connection_with_s390_settings(con, s390cfg)

    connections.insert(0, (con, device_to_activate))

    return connections


def add_connection_from_ksdata(nm_client, network_data, device_name, activate=False,
                               ifname_option_values=None):
    """Add NM connection created from kickstart configuration.

    :param network_data: kickstart configuration
    :type network_data: pykickstart NetworkData
    :param device_name: name of the device to be configured by kickstart
    :type device_name: str
    :param activate: activate the added connection
    :type activate: bool
    :param ifname_option_values: list of ifname boot option values
    :type ifname_option_values: list(str)
    """
    connections = create_connections_from_ksdata(
        nm_client,
        network_data,
        device_name,
        ifname_option_values
    )

    for con, device_name in connections:
        log.debug("add connection: %s for %s\n%s", con.get_uuid(), device_name,
                  con.to_dbus(NM.ConnectionSerializationFlags.NO_SECRETS))
        device_to_activate = device_name if activate else None
        nm_client.add_connection2(
            con.to_dbus(NM.ConnectionSerializationFlags.ALL),
            (NM.SettingsAddConnection2Flags.TO_DISK |
             NM.SettingsAddConnection2Flags.BLOCK_AUTOCONNECT),
            None,
            False,
            None,
            _connection_added_cb,
            device_to_activate
        )

    return connections


def _connection_added_cb(client, result, device_to_activate=None):
    """Finish asynchronous adding of a connection and activate eventually.

    :param device_to_activate: name of the device to be activated with the
                                added connection.
    :type device_to_activate: str
    """
    con, result = client.add_connection2_finish(result)
    log.debug("connection %s added:\n%s", con.get_uuid(),
              con.to_dbus(NM.ConnectionSerializationFlags.NO_SECRETS))
    if device_to_activate:
        device = client.get_device_by_iface(device_to_activate)
        if device:
            log.debug("activating with device %s", device.get_iface())
        else:
            log.debug("activating without device specified (not found)")
        client.activate_connection_async(con, device, None, None)


def create_slave_connection(slave_type, slave_idx, slave, master, settings=None):
    """Create a slave NM connection for virtual connection (bond, team, bridge).

    :param slave_type: type of slave ("bond", "team", "bridge")
    :type slave_type: str
    :param slave_idx: index of the slave for naming
    :type slave_idx: int
    :param slave: slave's device name
    :type slave: str
    :param master: slave's master device name
    :type master: str
    :param settings: list of other settings to be added to the connection
    :type settings: list(NM.Setting)

    :return: created connection
    :rtype: NM.SimpleConnection
    """
    settings = settings or []
    slave_name = "%s slave %d" % (master, slave_idx)

    con = NM.SimpleConnection.new()
    s_con = NM.SettingConnection.new()
    s_con.props.uuid = NM.utils_uuid_generate()
    s_con.props.id = slave_name
    s_con.props.slave_type = slave_type
    s_con.props.master = master
    s_con.props.type = '802-3-ethernet'
    # HACK preventing NM to autoactivate the connection
    # The real network --onboot value (ifcfg ONBOOT) will be set later by
    # update_onboot
    s_con.props.autoconnect = False
    con.add_setting(s_con)

    s_wired = NM.SettingWired.new()
    con.add_setting(s_wired)

    for setting in settings:
        con.add_setting(setting)

    return con


def is_infiniband_device(nm_client, device_name):
    """Is the type of the device infiniband?"""
    device = nm_client.get_device_by_iface(device_name)
    if device and device.get_device_type() == NM.DeviceType.INFINIBAND:
        return True
    return False


def bound_hwaddr_of_device(nm_client, device_name, ifname_option_values):
    """Check and return mac address of device bound by device renaming.

    For example ifname=ens3:f4:ce:46:2c:44:7a should bind the device name ens3
    to the MAC address (and rename the device in initramfs eventually).  If
    hwaddress of the device devname is the same as the MAC address, its value
    is returned.

    :param devname: device name
    :type devname: str
    :param ifname_option_values: list of ifname boot option values
    :type ifname_option_values: list(str)
    :return: hwaddress of the device if bound, or None
    :rtype: str or None
    """
    for ifname_value in ifname_option_values:
        iface, mac = ifname_value.split(":", 1)
        if iface == device_name:
            if iface == get_iface_from_hwaddr(nm_client, mac):
                return mac.upper()
            else:
                log.warning("MAC address of ifname %s does not correspond to ifname=%s",
                            iface, ifname_value)
    return None


def update_connection_from_ksdata(nm_client, connection, network_data, device_name=None):
    """Update NM connection specified by uuid from kickstart configuration.

    :param connection: existing NetworkManager connection to be updated
    :type connection: NM.RemoteConnection
    :param network_data: kickstart network configuration
    :type network_data: pykickstart NetworkData
    :param device_name: device name the connection should be bound to eventually
    :type device_name: str
    """
    log.debug("updating connection %s:\n%s", connection.get_uuid(),
              connection.to_dbus(NM.ConnectionSerializationFlags.NO_SECRETS))

    # IP configuration
    update_connection_ip_settings_from_ksdata(connection, network_data)

    s_con = connection.get_setting_connection()
    s_con.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, network_data.onboot)

    bind_connection(nm_client, connection, network_data.bindto, device_name)

    commit_changes_with_autoconnection_blocked(connection)

    log.debug("updated connection %s:\n%s", connection.get_uuid(),
              connection.to_dbus(NM.ConnectionSerializationFlags.NO_SECRETS))


def update_connection_ip_settings_from_ksdata(connection, network_data):
    """Update NM connection from kickstart IP configuration in place.

    :param connection: existing NetworkManager connection to be updated
    :type connection: NM.RemoteConnection
    :param network_data: kickstart configuation containing the IP configuration
                            to be applied to the connection
    :type network_data: pykickstart NetworkData
    """
    # ipv4 settings
    if network_data.noipv4:
        method4 = "disabled"
    elif network_data.bootProto == "static":
        method4 = "manual"
    else:
        method4 = "auto"

    connection.remove_setting(NM.SettingIP4Config)
    s_ip4 = NM.SettingIP4Config.new()
    s_ip4.set_property(NM.SETTING_IP_CONFIG_METHOD, method4)
    if method4 == "manual":
        prefix4 = netmask2prefix(network_data.netmask)
        addr4 = NM.IPAddress.new(socket.AF_INET, network_data.ip, prefix4)
        s_ip4.add_address(addr4)
        if network_data.gateway:
            s_ip4.props.gateway = network_data.gateway
    connection.add_setting(s_ip4)

    # ipv6 settings
    if network_data.noipv6:
        method6 = "ignore"
    elif not network_data.ipv6 or network_data.ipv6 == "auto":
        method6 = "auto"
    elif network_data.ipv6 == "dhcp":
        method6 = "dhcp"
    else:
        method6 = "manual"

    connection.remove_setting(NM.SettingIP6Config)
    s_ip6 = NM.SettingIP6Config.new()
    s_ip6.set_property(NM.SETTING_IP_CONFIG_METHOD, method6)
    if method6 == "manual":
        addr6, _slash, prefix6 = network_data.ipv6.partition("/")
        if prefix6:
            prefix6 = int(prefix6)
        else:
            prefix6 = 64
        addr6 = NM.IPAddress.new(socket.AF_INET6, addr6, prefix6)
        s_ip6.add_address(addr6)
        if network_data.ipv6gateway:
            s_ip6.props.gateway = network_data.ipv6gateway
    connection.add_setting(s_ip6)

    # nameservers
    if network_data.nameserver:
        for ns in [str.strip(i) for i in network_data.nameserver.split(",")]:
            if NM.utils_ipaddr_valid(socket.AF_INET6, ns):
                s_ip6.add_dns(ns)
            elif NM.utils_ipaddr_valid(socket.AF_INET, ns):
                s_ip4.add_dns(ns)
            else:
                log.error("IP address %s is not valid", ns)


def bind_settings_to_mac(nm_client, s_connection, s_wired, device_name=None, bind_exclusively=True):
    """Bind the settings to the mac address of the device.

    :param s_connection: connection setting to be updated
    :type s_connection: NM.SettingConnection
    :param s_wired: wired setting to be updated
    :type s_wired: NM.SettingWired
    :param device_name: name of the device to be bound
    :type evice_name: str
    :param bind_exclusively: remove reference to the device name from the settings
    :type bind_exclusively: bool
    :returns: True if the settings were modified, False otherwise
    :rtype: bool
    """
    mac_address = s_wired.get_mac_address()
    interface_name = s_connection.get_interface_name()
    modified = False

    if mac_address:
        log.debug("Bind to mac: already bound to %s", mac_address)
    else:
        iface = device_name or interface_name
        if not iface:
            log.warning("Bind to mac: no device name provided to look for mac")
            return False
        device = nm_client.get_device_by_iface(iface)
        if device:
            hwaddr = device.get_permanent_hw_address() or device.get_hw_address()
            s_wired.props.mac_address = hwaddr
            log.debug("Bind to mac: bound to %s", hwaddr)
            modified = True

    if bind_exclusively and interface_name:
        s_connection.props.interface_name = None
        log.debug("Bind to mac: removed interface-name %s from connection", interface_name)
        modified = True

    return modified


def bind_settings_to_device(nm_client, s_connection, s_wired, device_name=None, bind_exclusively=True):
    """Bind the settings to the name of the device.

    :param s_connection: connection setting to be updated
    :type s_connection: NM.SettingConnection
    :param s_wired: wired setting to be updated
    :type s_wired: NM.SettingWired
    :param device_name: name of the device to be bound
    :type evice_name: str
    :param bind_exclusively: remove reference to the mac address from the settings
    :type bind_exclusively: bool
    :returns: True if the settings were modified, False otherwise
    :rtype: bool
    """
    mac_address = s_wired.get_mac_address()
    interface_name = s_connection.get_interface_name()
    modified = False

    if device_name:
        s_connection.props.interface_name = device_name
        log.debug("Bind to device: %s -> %s", interface_name, device_name)
        modified = interface_name != device_name
    else:
        if not interface_name:
            log.debug("Bind to device: no device to bind to")
            return False
        else:
            log.debug("Bind to device: already bound to %s", interface_name)

    if bind_exclusively and mac_address:
        s_wired.props.mac_address = None
        log.debug("Bind to device: removed mac-address from connection")
        modified = True

    return modified


def bind_connection(nm_client, connection, bindto, device_name=None, bind_exclusively=True):
    """Bind the connection to device name or mac address.

    :param connection: connection to be updated before adding to NM
    :type connection: NM.SimpleConnection
    :param bindto: type of binding of the connection (mac address of device name)
                    - BIND_TO_MAC for mac address
                    - None for device name (default)
    :type bindto: pykickstart --bindto constant
    :param device_name: device name for binding
    :type device_name: str
    :param bind_exclusively: when binding to an entity, remove reference to the other
    :type bind_exclusively: bool
    :returns: True if the connection was modified, False otherwise
    :rtype: bool
    """
    msg = "Bind connection {} to {}:".format(connection.get_uuid(), bindto or "iface")

    s_con = connection.get_setting_connection()
    if not s_con:
        log.warning("%s no connection settings, bailing", msg)
        return False
    s_wired = connection.get_setting_wired()

    if bindto == BIND_TO_MAC:
        if not s_wired:
            log.warning("%s no wired settings, bailing", msg)
            return False
        modified = bind_settings_to_mac(nm_client, s_con, s_wired, device_name, bind_exclusively)
    else:
        modified = bind_settings_to_device(nm_client, s_con, s_wired, device_name, bind_exclusively)

    return modified


def ensure_active_connection_for_device(nm_client, uuid, device_name, only_replace=False):
    """Make sure active connection of a device is the one specified by uuid.

    :param uuid: uuid of the connection to be applied
    :type uuid: str
    :param device_name: name of device to apply the connection to
    :type device_name: str
    :param only_replace: apply the connection only if the device has different
                         active connection
    :type only_replace: bool
    """
    activated = False
    active_uuid = None
    device = nm_client.get_device_by_iface(device_name)
    if device:
        ac = device.get_active_connection()
        if ac or not only_replace:
            active_uuid = ac.get_uuid() if ac else None
            if uuid != active_uuid:
                ifcfg_con = nm_client.get_connection_by_uuid(uuid)
                # TODO make the API calls synchronous ?
                nm_client.activate_connection_async(ifcfg_con, None, None, None)
                activated = True
    msg = "activated" if activated else "not activated"
    log.debug("ensure active ifcfg connection for %s (%s -> %s): %s",
              device_name, active_uuid, uuid, msg)
    return activated


def get_connections_available_for_iface(nm_client, iface):
    """Get all connections available for given interface.

    :param iface: interface name
    :type iface: str
    :return: list of all available connections
    :rtype: list(NM.RemoteConnection)
    """
    cons = []
    device = nm_client.get_device_by_iface(iface)
    if device:
        cons = device.get_available_connections()
    else:
        # Try also non-existing (not real) virtual devices
        for device in nm_client.get_all_devices():
            if not device.is_real() and device.get_iface() == iface:
                cons = device.get_available_connections()
                if cons:
                    break
        else:
            # Getting available connections does not seem to work quite well for
            # non-real team - try to look them up in all connections.
            for con in nm_client.get_connections():
                interface_name = con.get_interface_name()
                if not interface_name and con.get_connection_type() == "vlan":
                    interface_name = get_vlan_interface_name_from_connection(nm_client, con)
                if interface_name == iface:
                    cons.append(con)

    return cons


def update_connection_values(connection, new_values):
    """Update setting values of a connection.

    :param connection: existing NetworkManager connection to be updated
    :type connection: NM.RemoteConnection
    :param new_values: list of properties to be updated
    :type new_values: [(SETTING_NAME, SETTING_PROPERTY, VALUE)]
    """
    for setting_name, setting_property, value in new_values:
        setting = connection.get_setting_by_name(setting_name)
        if setting:
            setting.set_property(setting_property, value)
            log.debug("updating connection %s setting '%s' '%s' to '%s'",
                      connection.get_uuid(), setting_name, setting_property, value)
        else:
            log.debug("setting '%s' not found while updating connection %s",
                      setting_name, connection.get_uuid())
    commit_changes_with_autoconnection_blocked(connection)
    log.debug("updated connection %s:\n%s", connection.get_uuid(),
              connection.to_dbus(NM.ConnectionSerializationFlags.ALL))


def devices_ignore_ipv6(nm_client, device_types):
    """All connections of devices of given type ignore ipv6."""
    device_types = device_types or []
    for device in nm_client.get_devices():
        if device.get_device_type() in device_types:
            cons = device.get_available_connections()
            for con in cons:
                s_ipv6 = con.get_setting_ip6_config()
                if s_ipv6 and s_ipv6.get_method() != NM.SETTING_IP6_CONFIG_METHOD_IGNORE:
                    return False
    return True


def get_first_iface_with_link(nm_client, ifaces):
    """Find first iface having link (in lexicographical order)."""
    for iface in sorted(ifaces):
        device = nm_client.get_device_by_iface(iface)
        if device and device.get_carrier():
            return device.get_iface()
    return None


def get_connections_dump(nm_client):
    """Dumps all connections for logging."""
    con_dumps = []
    for con in nm_client.get_connections():
        con_dumps.append(str(con.to_dbus(NM.ConnectionSerializationFlags.NO_SECRETS)))
    return "\n".join(con_dumps)


def commit_changes_with_autoconnection_blocked(connection, save_to_disk=True):
    """Implementation of NM CommitChanges() method with blocked autoconnection.

    Update2() API is used to implement the functionality (called synchronously).

    Prevents autoactivation of the connection on its update which would happen
    with CommitChanges if "autoconnect" is set True.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param save_to_disk: should the changes be written also to disk?
    :type save_to_disk: bool
    :return: on success result of the Update2() call, None of failure
    :rtype: GVariant of type "a{sv}" or None
    """
    sync_queue = Queue()

    def finish_callback(connection, result, sync_queue):
        ret = connection.update2_finish(result)
        sync_queue.put(ret)

    flags = NM.SettingsUpdate2Flags.BLOCK_AUTOCONNECT
    if save_to_disk:
        flags |= NM.SettingsUpdate2Flags.TO_DISK

    con2 = NM.SimpleConnection.new_clone(connection)
    connection.update2(
        con2.to_dbus(NM.ConnectionSerializationFlags.ALL),
        flags,
        None,
        None,
        finish_callback,
        sync_queue
    )

    return sync_queue.get()
