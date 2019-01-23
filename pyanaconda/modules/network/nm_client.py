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
from pykickstart.constants import BIND_TO_MAC
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

def get_iface_from_hwaddr(nm_client, hwaddr):
    """Find the name of device specified by mac address."""
    for device in nm_client.get_devices():
        if device.get_device_type() in (NM.DeviceType.ETHERNET,
                                        NM.DeviceType.WIFI):
            try:
                address = device.get_permanent_hw_address()
            except AttributeError as e:
                log.warning("Device %s: %s", device.get_iface(), e)
                address = device.get_hw_address()
        else:
            address = device.get_hw_address()
        if address.upper() == hwaddr.upper():
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

def get_team_config_form_connection(nm_client, uuid):
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
    :param bootif: MAC addres of device to be used for
                    --device=bootif specification
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
        device_name = get_iface_from_hwaddr(nm_client, bootif) or ""
        msg = "existing device for {} found".format(bootif)
    # First device with carrier (sorted lexicographically)
    elif spec == 'link':
        for candidate_name in sorted(supported_devices):
            device = nm_client.get_device_by_iface(candidate_name)
            if device and device.get_carrier():
                device_name = device.get_iface()
                break

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


def add_connection_from_ksdata(nm_client, network_data, device_name, activate=False, ifname_option_values=None):
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
    ifname_option_values = ifname_option_values or []
    added_connections = []
    device_to_activate = device_name

    con_uuid = NM.utils_uuid_generate()
    con = NM.SimpleConnection.new()

    update_connection_ip_settings_from_ksdata(con, network_data)

    s_con = NM.SettingConnection.new()
    s_con.props.uuid = con_uuid
    # HACK preventing NM to autoactivate the connection
    # The real network --onboot value (ifcfg ONBOOT) will be set later by
    # update_onboot
    s_con.props.autoconnect = False

    # type "bond"
    if network_data.bondslaves:
        s_con.props.type = "bond"
        s_con.props.id = device_name
        s_con.props.interface_name = device_name
        con.add_setting(s_con)

        s_bond = NM.SettingBond.new()
        opts = network_data.bondopts
        for option in opts.split(';' if ';' in opts else ','):
            key, _sep, value = option.partition("=")
            if not s_bond.add_option(key, value):
                log.warning("adding bond option %s failed (invalid?)")
        con.add_setting(s_bond)

        for i, slave in enumerate(network_data.bondslaves.split(","), 1):
            slave_con = create_slave_connection('bond', i, slave, device_name)
            bind_connection(nm_client, slave_con, network_data.bindto, slave)
            added_connections.append((slave_con, slave))

    # type "team"
    elif network_data.teamslaves:
        s_con.props.type = "team"
        s_con.props.id = device_name
        s_con.props.interface_name = device_name
        con.add_setting(s_con)

        s_team = NM.SettingTeam.new()
        s_team.props.config = network_data.teamconfig
        con.add_setting(s_team)

        for i, (slave, cfg) in enumerate(network_data.teamslaves, 1):
            s_team_port = NM.SettingTeamPort.new()
            s_team_port.props.config = cfg
            slave_con = create_slave_connection('team', i, slave, device_name,
                                                settings=[s_team_port])
            bind_connection(nm_client, slave_con, network_data.bindto, slave)
            added_connections.append((slave_con, slave))

    # type "vlan"
    elif network_data.vlanid:
        s_con.props.type = "vlan"
        s_con.props.id = network_data.interfacename or device_name
        # FIXME: fix also the test
        # s_con.props.interface_name = network_data.interfacename or None
        s_con.props.interface_name = network_data.interfacename or device_name
        con.add_setting(s_con)

        s_vlan = NM.SettingVlan.new()
        s_vlan.props.id = int(network_data.vlanid)
        s_vlan.props.parent = network_data.parent
        con.add_setting(s_vlan)

    # type "bridge"
    elif network_data.bridgeslaves:
        # bridge connection is autoactivated
        s_con.props.type = "bridge"
        s_con.props.id = device_name
        s_con.props.interface_name = device_name
        con.add_setting(s_con)

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
        con.add_setting(s_bridge)

        for i, slave in enumerate(network_data.bridgeslaves.split(","), 1):
            slave_con = create_slave_connection('bridge', i, slave, device_name)
            bind_connection(nm_client, slave_con, network_data.bindto, slave)
            added_connections.append((slave_con, slave))

    # type "infiniband"
    elif is_infiniband_device(nm_client, device_name):
        s_con.props.type = "infiniband"
        s_con.props.id = device_name
        s_con.props.interface_name = device_name
        con.add_setting(s_con)

        s_ib = NM.SettingInfiniband.new()
        s_ib.props.transport_mode = "datagram"
        con.add_settings(s_ib)

    # type "802-3-ethernet"
    else:
        s_con.props.type = "802-3-ethernet"
        s_con.props.id = device_name

        s_wired = NM.SettingWired.new()
        con.add_setting(s_wired)

        bound_mac = bound_hwaddr_of_device(nm_client, device_name, ifname_option_values)
        if bound_mac:
            s_con.props.interface_name = device_name
            s_wired.props.mac_address = bound_mac
            log.debug("add connection: mac %s is bound to name %s",
                      bound_mac, device_name)
            con.add_setting(s_con)
        else:
            con.add_setting(s_con)
            bind_connection(nm_client, con, network_data.bindto, device_name)

        # Add s390 settings
        if is_s390():
            s390cfg = get_s390_settings(device_name)
            if s390cfg['SUBCHANNELS']:
                subchannels = s390cfg['SUBCHANNELS'].split(",")
                s_wired.props.s390_subchannels = subchannels
            if s390cfg['NETTYPE']:
                s_wired.props.s390_nettype = s390cfg['NETTYPE']
            if s390cfg['OPTIONS']:
                opts = s390cfg['OPTIONS'].split(" ")
                opts_dict = {k: v for k, v in (o.split("=") for o in opts)}
                s_wired.props.s90_options = opts_dict

    added_connections.insert(0, (con, device_to_activate))

    for con, device_name in added_connections:
        log.debug("add connection: %s for %s\n%s", con_uuid, device_name,
                  con.to_dbus(NM.ConnectionSerializationFlags.ALL))
        device_to_activate = device_name if activate else None
        nm_client.add_connection_async(con, True, None,
                                       _connection_added_cb,
                                       device_to_activate)

    return added_connections


def _connection_added_cb(client, result, device_to_activate=None):
    """Finish asynchronous adding of a connection and activate eventually.

    :param device_to_activate: name of the device to be activated with the
                                added connection.
    :type device_to_activate: str
    """
    con = client.add_connection_finish(result)
    log.debug("connection %s added:\n%s", con.get_uuid(),
              con.to_dbus(NM.ConnectionSerializationFlags.ALL))
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
            if iface ==  get_iface_from_hwaddr(nm_client, mac):
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
              connection.to_dbus(NM.ConnectionSerializationFlags.ALL))

    # IP configuration
    update_connection_ip_settings_from_ksdata(connection, network_data)

    # ONBOOT workaround so that the connection is not activated
    s_con = connection.get_setting_connection()
    s_con.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, False)

    bind_connection(nm_client, connection, network_data.bindto, device_name)

    connection.commit_changes(True, None)

    log.debug("updated connection %s:\n%s", connection.get_uuid(),
              connection.to_dbus(NM.ConnectionSerializationFlags.ALL))


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


def bind_connection(nm_client, connection, bindto, device_name=None, bind_exclusively=True):
    """Bind the connection to device name or mac address.

    :param connection: uuid of the connection
    :type connection: str
    :param bindto: type of binding of the connection (mac address of device name)
                    - BIND_TO_MAC for mac address
                    - None for device name (default)
    :type bindto: pykickstart --bindto constant
    :param device_name: device name for binding
    :type device_name: str
    :param bind_exclusively: when binding to an entity, remove reference to the other
    :type bind_exclusively: bool
    """
    msg = "bind connection {} to {}:".format(connection.get_uuid(), bindto or "iface")

    s_con = connection.get_setting_connection()
    if not s_con:
        log.warning("%s no connection settings", msg)
        return False
    interface_name = s_con.get_interface_name()
    s_wired = connection.get_setting_wired()
    if s_wired:
        mac_address = s_wired.get_mac_address()
    else:
        mac_address = None

    # bind to mac address
    if bindto == BIND_TO_MAC:
        if not s_wired:
            log.warning("%s no wired settings", msg)
            return False
        if mac_address:
            log.debug("%s already bound to %s", msg, mac_address)
            if interface_name and bind_exclusively:
                connection.get_setting_connection().props.interface_name = None
                log.debug("%s removed interface-name from connection", msg)
                return True
            return False
        else:
            device_name = device_name or interface_name
            if not device_name:
                log.warning("%s no device to look for mac", msg)
                return False
            device = nm_client.get_device_by_iface(device_name)
            if device:
                hwaddr = device.get_permanent_hw_address() or device.get_hw_address()
                if interface_name and bind_exclusively:
                    connection.get_setting_connection().props.interface_name = None
                    log.debug("%s removed interface-name from connection", msg)
                s_wired.props.mac_address = hwaddr
                log.debug("%s bound to %s", msg, hwaddr)
                return True
    # bind to device name
    else:
        if device_name:
            if mac_address and bind_exclusively:
                s_wired.props.mac_address = None
                log.debug("%s removed mac-address from connection", msg)
            s_con.props.interface_name = device_name
            log.debug("%s %s -> %s", msg, interface_name, device_name)
            return True
        else:
            if not interface_name:
                log.debug("%s no device to bind to", msg)
                return False
            else:
                log.debug("%s already bound to %s", msg, interface_name)
                if mac_address and bind_exclusively:
                    s_wired.props.mac_address = None
                    log.debug("%s removed mac-address from connection", msg)
                    return True
                return False


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
            active_uuid = ac.get_uuid()
            if uuid != active_uuid:
                ifcfg_con = nm_client.get_connection_by_uuid(uuid)
                # TODO make the API calls synchronous ?
                nm_client.activate_connection_async(ifcfg_con, None, None, None)
                activated = True
    msg = "activated" if activated else "not activated"
    log.debug("ensure active ifcfg connection for %s (%s -> %s): %s",
                device_name, active_uuid, uuid, msg)
    return activated

def update_iface_setting_values(nm_client, iface, new_values):
    """Update settings of the connection for the interface.

    The values will be applied only if a single applicable connection is found
    for the iface (return value is 1).

    :param iface: name of the device
    :type iface: str
    :param new_values: list of properties to be updated
    :type new_values: [(SETTING_NAME, SETTING_PROPERTY, VALUE)]
    :returns: number of applicable connections found
    :rtype: int
    """
    n_cons = 0
    device = nm_client.get_device_by_iface(iface)
    if not device:
        return n_cons

    cons = device.get_available_connections()
    n_cons = len(cons)
    if n_cons != 1:
        return n_cons

    con = cons[0]
    for setting_name, setting_property, value in new_values:
        setting = con.get_setting_by_name(setting_name)
        setting.set_property(setting_property, value)
        log.debug("updating %s device setting '%s' '%s' to '%s'",
                  iface, setting_name, setting_property, value)
    con.commit_changes(True, None)
    return n_cons

def devices_ignore_ipv6(nm_client, device_types):
    """All connections of devices of given type ignore ipv6."""
    device_types = device_types or []
    for device in nm_client.get_devices():
        if device.get_device_type() in device_types:
            cons = device.get_available_connections()
            for con in cons:
                s_ipv6 = con.get_setting_ipv6_config()
                if s_ipv6 and s_ipv6.method() != NM.SETTING_IP6_CONFIG_METHOD_IGNORE:
                    return False
    return True

def get_first_iface_with_link(nm_client, device_types):
    for device in nm_client.get_devices():
        if device.get_device_type() in device_types and device.get_carrier():
            return device.get_iface()
    return None
