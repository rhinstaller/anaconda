#
# utility functions using libnm
#
# Copyright (C) 2018-2023 Red Hat, Inc.
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

import gi

gi.require_version("NM", "1.0")
import socket
from contextlib import contextmanager

from blivet.arch import is_s390
from gi.repository import NM
from pykickstart.constants import BIND_TO_MAC

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.dbus import SystemBus
from pyanaconda.core.glib import GError, create_new_context, sync_call_glib
from pyanaconda.modules.network.config_file import is_config_file_for_system
from pyanaconda.modules.network.constants import (
    CONNECTION_ADDING_TIMEOUT,
    NM_CONNECTION_TYPE_BOND,
    NM_CONNECTION_TYPE_BRIDGE,
    NM_CONNECTION_TYPE_ETHERNET,
    NM_CONNECTION_TYPE_INFINIBAND,
    NM_CONNECTION_TYPE_TEAM,
    NM_CONNECTION_TYPE_VLAN,
    NM_CONNECTION_TYPE_WIFI,
    NM_CONNECTION_UUID_LENGTH,
)
from pyanaconda.modules.network.kickstart import default_ks_vlan_interface_name
from pyanaconda.modules.network.utils import (
    get_s390_settings,
    netmask2prefix,
    prefix2netmask,
)

log = get_module_logger(__name__)


NM_BRIDGE_DUMPED_SETTINGS_DEFAULTS = {
    NM.SETTING_BRIDGE_MAC_ADDRESS: None,
    NM.SETTING_BRIDGE_STP: True,
    NM.SETTING_BRIDGE_PRIORITY: 32768,
    NM.SETTING_BRIDGE_FORWARD_DELAY: 15,
    NM.SETTING_BRIDGE_HELLO_TIME: 2,
    NM.SETTING_BRIDGE_MAX_AGE: 20,
    NM.SETTING_BRIDGE_AGEING_TIME: 300,
    NM.SETTING_BRIDGE_GROUP_FORWARD_MASK: 0,
    NM.SETTING_BRIDGE_MULTICAST_SNOOPING: True
}


@contextmanager
def nm_client_in_thread():
    """Create NM Client with new GMainContext to be run in thread.

    Expected to be used only in installer environment for a few
    one-shot isolated network configuration tasks.
    Destroying of the created NM Client instance and release of
    related resources is not implemented.

    For more information see NetworkManager example examples/python/gi/gmaincontext.py
    """
    mainctx = create_new_context()
    mainctx.push_thread_default()

    try:
        yield get_new_nm_client()
    finally:
        mainctx.pop_thread_default()


def get_new_nm_client():
    """Get new instance of NMClient.

    :returns: an instance of NetworkManager NMClient or None if system bus
              is not available or NM is not running
    :rtype: NM.NMClient
    """
    if not SystemBus.check_connection():
        log.debug("get new NM Client failed: SystemBus connection check failed.")
        return None

    try:
        nm_client = NM.Client.new(None)
    except GError as e:
        log.debug("get new NM Client constructor failed: %s", e)
        return None

    if not nm_client.get_nm_running():
        log.debug("get new NM Client failed: NetworkManager is not running.")
        return None

    log.debug("get new NM Client succeeded.")
    return nm_client


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


def _create_vlan_bond_connection_from_ksdata(network_data):
    con = _create_new_connection(network_data, network_data.device)
    _update_bond_connection_from_ksdata(con, network_data)
    # No ip configuration on vlan parent (bond)
    s_ip4 = NM.SettingIP4Config.new()
    s_ip4.set_property(NM.SETTING_IP_CONFIG_METHOD,
                       NM.SETTING_IP4_CONFIG_METHOD_DISABLED)
    con.add_setting(s_ip4)
    s_ip6 = NM.SettingIP6Config.new()
    s_ip6.set_property(NM.SETTING_IP_CONFIG_METHOD,
                       NM.SETTING_IP6_CONFIG_METHOD_DISABLED)
    con.add_setting(s_ip6)
    return con


def _update_bond_connection_from_ksdata(connection, network_data):
    """Update connection with values from bond kickstart configuration.

    :param connection: connection to be updated before adding to NM
    :type connection: NM.SimpleConnection
    :param network_data: kickstart configuration
    :type network_data: pykickstart NetworkData
    """
    s_con = connection.get_setting_connection()
    s_con.props.type = NM_CONNECTION_TYPE_BOND

    s_bond = NM.SettingBond.new()
    opts = network_data.bondopts
    if opts:
        for option in opts.split(';' if ';' in opts else ','):
            key, _sep, value = option.partition("=")
            if s_bond.validate_option(key, value):
                s_bond.add_option(key, value)
            else:
                log.warning("ignoring invalid bond option '%s=%s'", key, value)
    connection.add_setting(s_bond)


def _add_existing_virtual_device_to_bridge(nm_client, device_name, bridge_spec):
    """Add existing virtual device to a bridge.

    :param device_name: name of the virtual device to be added
    :type device_name: str
    :param bridge_spec: specification of the bridge (interface name or connection uuid)
    :type bridge_spec: str
    :returns: uuid of the updated connection or None
    :rtype: str
    """
    supported_virtual_types = (
        NM_CONNECTION_TYPE_BOND,
    )
    port_connection = None
    cons = nm_client.get_connections()
    for con in cons:
        if con.get_interface_name() == device_name \
                and con.get_connection_type() in supported_virtual_types:
            port_connection = con
            break

    if not port_connection:
        return None

    update_connection_values(
        port_connection,
        [
            (NM.SETTING_CONNECTION_SETTING_NAME,
             NM.SETTING_CONNECTION_SLAVE_TYPE,
             'bridge'),
            (NM.SETTING_CONNECTION_SETTING_NAME,
             NM.SETTING_CONNECTION_MASTER,
             bridge_spec),
        ]
    )
    commit_changes_with_autoconnection_blocked(port_connection, nm_client)
    return port_connection.get_uuid()


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
    s_con.props.type = NM_CONNECTION_TYPE_VLAN
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
    s_con.props.type = NM_CONNECTION_TYPE_BRIDGE

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
    s_con.props.type = NM_CONNECTION_TYPE_INFINIBAND

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
    s_con.props.type = NM_CONNECTION_TYPE_ETHERNET

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


def _create_new_connection(network_data, device_name):
    con_uuid = NM.utils_uuid_generate()
    con = NM.SimpleConnection.new()
    s_con = NM.SettingConnection.new()
    s_con.props.uuid = con_uuid
    s_con.props.id = device_name
    s_con.props.interface_name = device_name
    s_con.props.autoconnect = network_data.onboot
    con.add_setting(s_con)
    return con


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
    port_connections = []
    connections = []
    device_to_activate = device_name

    con = _create_new_connection(network_data, device_name)
    bond_con = None

    update_connection_ip_settings_from_ksdata(con, network_data)

    # type "bond"
    if network_data.bondslaves:
        # vlan over bond
        if network_data.vlanid:
            # create bond connection, vlan connection will be created later
            bond_controller = network_data.device
            bond_con = _create_vlan_bond_connection_from_ksdata(network_data)
            connections.append((bond_con, bond_controller))
        else:
            bond_controller = device_name
            _update_bond_connection_from_ksdata(con, network_data)

        for i, port in enumerate(network_data.bondslaves.split(","), 1):
            port_con = create_port_connection('bond', i, port, bond_controller,
                                              network_data.onboot)
            bind_connection(nm_client, port_con, network_data.bindto, port)
            port_connections.append((port_con, port))

    # type "team"
    if network_data.teamslaves:
        _update_team_connection_from_ksdata(con, network_data)

        for i, (port, cfg) in enumerate(network_data.teamslaves, 1):
            s_team_port = NM.SettingTeamPort.new()
            s_team_port.props.config = cfg
            port_con = create_port_connection('team', i, port, device_name,
                                              network_data.onboot, settings=[s_team_port])
            bind_connection(nm_client, port_con, network_data.bindto, port)
            port_connections.append((port_con, port))

    # type "vlan"
    if network_data.vlanid:
        device_to_activate = _update_vlan_connection_from_ksdata(con, network_data) \
            or device_to_activate

    # type "bridge"
    if network_data.bridgeslaves:
        # bridge connection is autoactivated
        _update_bridge_connection_from_ksdata(con, network_data)

        for i, port in enumerate(network_data.bridgeslaves.split(","), 1):
            if not _add_existing_virtual_device_to_bridge(nm_client, port, device_name):
                port_con = create_port_connection('bridge', i, port, device_name,
                                                  network_data.onboot)
                bind_connection(nm_client, port_con, network_data.bindto, port)
                port_connections.append((port_con, port))

    # type "infiniband"
    if is_infiniband_device(nm_client, device_name):
        _update_infiniband_connection_from_ksdata(con, network_data)

    # type "802-3-ethernet"
    if is_ethernet_device(nm_client, device_name):
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

    update_connection_wired_settings_from_ksdata(con, network_data)

    connections.append((con, device_to_activate))
    connections.extend(port_connections)

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

    for connection, dev_name in connections:
        log.debug("add connection (activate=%s): %s for %s\n%s",
                  activate, connection.get_uuid(), dev_name,
                  connection.to_dbus(NM.ConnectionSerializationFlags.NO_SECRETS))
        added_connection = add_connection_sync(
            nm_client,
            connection
        )

        if not added_connection:
            continue

        if activate:
            if dev_name:
                device = nm_client.get_device_by_iface(dev_name)
                if device:
                    log.debug("activating with device %s", device.get_iface())
                else:
                    log.debug("activating without device specified - device %s not found",
                              dev_name)
            else:
                device = None
                log.debug("activating without device specified")
            nm_client.activate_connection_async(added_connection, device, None, None)

    return connections


def add_connection_sync(nm_client, connection):
    """Add a connection synchronously.

    Synchronous run is implemented by running a blocking GMainLoop with
    GMainContext belonging to the nm_client created for the calling Task.

    :param nm_client: NetoworkManager client
    :type nm_client: NM.NMClient
    :param connection: connection to be added
    :type connection: NM.SimpleConnection
    :return: added connection or None on timeout
    :rtype: NM.RemoteConnection
    """
    result = sync_call_glib(
        nm_client.get_main_context(),
        nm_client.add_connection2,
        nm_client.add_connection2_finish,
        CONNECTION_ADDING_TIMEOUT,
        connection.to_dbus(NM.ConnectionSerializationFlags.ALL),
        (NM.SettingsAddConnection2Flags.TO_DISK |
         NM.SettingsAddConnection2Flags.BLOCK_AUTOCONNECT),
        None,
        False
    )

    if result.failed:
        log.error("adding of a connection %s failed: %s",
                  connection.get_uuid(),
                  result.error_message)
        return None

    con, _res = result.received_data
    log.debug("connection %s added:\n%s", connection.get_uuid(),
              connection.to_dbus(NM.ConnectionSerializationFlags.NO_SECRETS))

    return con


def create_port_connection(port_type, port_idx, port, controller, autoconnect, settings=None):
    """Create a port NM connection for virtual connection (bond, team, bridge).

    :param port_type: type of port ("bond", "team", "bridge")
    :type port_type: str
    :param port_idx: index of the port for naming
    :type port_idx: int
    :param port: port's device name
    :type port: str
    :param controller: port's controller device name
    :type controller: str
    :param autoconnect: connection autoconnect value
    :type autoconnect: bool
    :param settings: list of other settings to be added to the connection
    :type settings: list(NM.Setting)

    :return: created connection
    :rtype: NM.SimpleConnection
    """
    settings = settings or []
    port_name = "%s_slave_%d" % (controller, port_idx)

    con = NM.SimpleConnection.new()
    s_con = NM.SettingConnection.new()
    s_con.props.uuid = NM.utils_uuid_generate()
    s_con.props.id = port_name
    s_con.props.slave_type = port_type
    s_con.props.master = controller
    s_con.props.type = NM_CONNECTION_TYPE_ETHERNET
    s_con.props.autoconnect = autoconnect
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


def is_ethernet_device(nm_client, device_name):
    """Is the type of the device ethernet?"""
    device = nm_client.get_device_by_iface(device_name)
    if device and device.get_device_type() == NM.DeviceType.ETHERNET:
        return True
    return False


def bound_hwaddr_of_device(nm_client, device_name, ifname_option_values):
    """Check and return mac address of device bound by device renaming.

    For example ifname=ens3:f4:ce:46:2c:44:7a should bind the device name ens3
    to the MAC address (and rename the device in initramfs eventually).  If
    hwaddress of the device devname is the same as the MAC address, its value
    is returned.

    :param device_name: device name
    :type device_name: str
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


def update_connection_from_ksdata(nm_client, connection, network_data, device_name,
                                  ifname_option_values=None):
    """Update NM connection specified by uuid from kickstart configuration.

    :param connection: existing NetworkManager connection to be updated
    :type connection: NM.RemoteConnection
    :param network_data: kickstart network configuration
    :type network_data: pykickstart NetworkData
    :param device_name: device name the connection should be bound to eventually
    :type device_name: str
    :param ifname_option_values: list of ifname boot option values
    :type ifname_option_values: list(str)
    """
    log.debug("updating connection %s:\n%s", connection.get_uuid(),
              connection.to_dbus(NM.ConnectionSerializationFlags.NO_SECRETS))

    ifname_option_values = ifname_option_values or []

    # IP configuration
    update_connection_ip_settings_from_ksdata(connection, network_data)

    update_connection_wired_settings_from_ksdata(connection, network_data)

    s_con = connection.get_setting_connection()
    s_con.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, network_data.onboot)

    if connection.get_connection_type() not in (NM_CONNECTION_TYPE_BOND,
                                                NM_CONNECTION_TYPE_TEAM,
                                                NM_CONNECTION_TYPE_VLAN,
                                                NM_CONNECTION_TYPE_BRIDGE):
        bound_mac = bound_hwaddr_of_device(nm_client, device_name, ifname_option_values)
        if bound_mac:
            log.debug("update connection: mac %s is bound to name %s", bound_mac, device_name)
            # The connection is already bound to iface name by NM in initramfs,
            # still bind also to MAC until this method of renaming is abandoned (rhbz#1875485)
            bind_connection(nm_client, connection, BIND_TO_MAC, device_name,
                            bind_exclusively=False)
        else:
            bind_connection(nm_client, connection, network_data.bindto, device_name)

    commit_changes_with_autoconnection_blocked(connection, nm_client)

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
    if network_data.nodefroute:
        s_ip4.props.never_default = True
    if network_data.dhcpclass:
        s_ip4.set_property(NM.SETTING_IP4_CONFIG_DHCP_VENDOR_CLASS_IDENTIFIER,
                           network_data.dhcpclass)
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
    s_ip6.set_property(NM.SETTING_IP6_CONFIG_ADDR_GEN_MODE,
                       NM.SettingIP6ConfigAddrGenMode.EUI64)
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

    # DNS search domains
    if network_data.ipv4_dns_search:
        for domain in [str.strip(i) for i in network_data.ipv4_dns_search.split(",")]:
            s_ip4.add_dns_search(domain)
    if network_data.ipv6_dns_search:
        for domain in [str.strip(i) for i in network_data.ipv6_dns_search.split(",")]:
            s_ip6.add_dns_search(domain)

    # ignore auto DNS
    if network_data.ipv4_ignore_auto_dns:
        s_ip4.props.ignore_auto_dns = network_data.ipv4_ignore_auto_dns
    if network_data.ipv6_ignore_auto_dns:
        s_ip6.props.ignore_auto_dns = network_data.ipv6_ignore_auto_dns


def update_connection_wired_settings_from_ksdata(connection, network_data):
    """Update NM connection wired settings from kickstart in place.

    :param connection: existing NetworkManager connection to be updated
    :type connection: NM.RemoteConnection
    :param network_data: kickstart configuation to be applied to the connection
    :type network_data: pykickstart NetworkData
    """
    if network_data.mtu:
        try:
            mtu = int(network_data.mtu)
        except ValueError:
            log.error("Value of network --mtu option is not valid: %s", network_data.mtu)
        else:
            s_wired = connection.get_setting_wired()
            if not s_wired:
                s_wired = NM.SettingWired.new()
                connection.add_setting(s_wired)
            s_wired.props.mtu = mtu


def bind_settings_to_mac(nm_client, s_connection, s_wired, device_name=None, bind_exclusively=True):
    """Bind the settings to the mac address of the device.

    :param s_connection: connection setting to be updated
    :type s_connection: NM.SettingConnection
    :param s_wired: wired setting to be updated
    :type s_wired: NM.SettingWired
    :param device_name: name of the device to be bound
    :type device_name: str
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
            try:
                perm_hwaddr = device.get_permanent_hw_address()
            except AttributeError:
                perm_hwaddr = None
            hwaddr = perm_hwaddr or device.get_hw_address()
            s_wired.props.mac_address = hwaddr
            log.debug("Bind to mac: bound to %s", hwaddr)
            modified = True

    if bind_exclusively and interface_name:
        s_connection.props.interface_name = None
        log.debug("Bind to mac: removed interface-name %s from connection", interface_name)
        modified = True

    return modified


def bind_settings_to_device(nm_client, s_connection, s_wired, device_name=None,
                            bind_exclusively=True):
    """Bind the settings to the name of the device.

    :param s_connection: connection setting to be updated
    :type s_connection: NM.SettingConnection
    :param s_wired: wired setting to be updated
    :type s_wired: NM.SettingWired
    :param device_name: name of the device to be bound
    :type device_name: str
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
                if not interface_name and con.get_connection_type() == NM_CONNECTION_TYPE_VLAN:
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
        if device:
            try:
                carrier = device.get_carrier()
            except AttributeError:
                carrier = None
            if carrier:
                return device.get_iface()
    return None


def get_connections_dump(nm_client):
    """Dumps all connections for logging."""
    con_dumps = []
    for con in nm_client.get_connections():
        con_dumps.append(str(con.to_dbus(NM.ConnectionSerializationFlags.NO_SECRETS)))
    return "\n".join(con_dumps)


def commit_changes_with_autoconnection_blocked(connection, nm_client, save_to_disk=True):
    """Implementation of NM CommitChanges() method with blocked autoconnection.

    Update2() API is used to implement the functionality.
    Prevents autoactivation of the connection on its update which would happen
    with CommitChanges if "autoconnect" is set True.

    Synchronous run is implemented by running a blocking GMainLoop with
    GMainContext belonging to the nm_client created for the calling Task.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param nm_client: NetoworkManager client
    :type nm_client: NM.NMClient
    :param save_to_disk: should the changes be written also to disk?
    :type save_to_disk: bool
    :return: on success result of the Update2() call, None of failure
    :rtype: GVariant of type "a{sv}" or None
    """
    flags = NM.SettingsUpdate2Flags.BLOCK_AUTOCONNECT
    if save_to_disk:
        flags |= NM.SettingsUpdate2Flags.TO_DISK
    con2 = NM.SimpleConnection.new_clone(connection)

    result = sync_call_glib(
        nm_client.get_main_context(),
        connection.update2,
        connection.update2_finish,
        CONNECTION_ADDING_TIMEOUT,
        con2.to_dbus(NM.ConnectionSerializationFlags.ALL),
        flags,
        None
    )

    if result.failed:
        log.error("comitting changes of connection %s failed: %s",
                  connection.get_uuid(),
                  result.error_message)
        return None

    return result.received_data


def clone_connection_sync(nm_client, connection, con_id=None, uuid=None):
    """Clone a connection synchronously.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param con_id: id of the cloned connection
    :type con_id: str
    :param uuid: uuid of the cloned connection (None to be generated)
    :type uuid: str
    :return: NetworkManager connection or None on timeout
    :rtype: NM.RemoteConnection
    """
    cloned_connection = NM.SimpleConnection.new_clone(connection)
    s_con = cloned_connection.get_setting_connection()
    s_con.props.uuid = uuid or NM.utils_uuid_generate()
    s_con.props.id = con_id or "{}-clone".format(connection.get_id())

    log.debug("cloning connection %s", connection.get_uuid())
    added_connection = add_connection_sync(nm_client, cloned_connection)

    if added_connection:
        log.debug("connection was cloned into %s", added_connection.get_uuid())
    else:
        log.debug("connection cloning failed")
    return added_connection


def get_dracut_arguments_from_connection(nm_client, connection, iface, target_ip,
                                         hostname):
    """Get dracut arguments for the iface and SAN target from NM connection.

    Examples of SAN: iSCSI, FCoE

    The dracut arguments would activate the iface in initramfs so that the
    SAN target can be attached (usually to mount root filesystem).

    :param nm_client: instance of NetworkManager client
    :type nm_client: NM.Client
    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param iface: network interface used to connect to the target
    :type iface: str
    :param target_ip: IP of the SAN target
    :type target_ip: str
    :param hostname: static hostname to be configured
    :type hostname: str
    :returns: dracut arguments
    :rtype: set(str)
    """
    netargs = set()

    if target_ip:
        if hostname is None:
            hostname = ""
        if ':' in target_ip:
            # Using IPv6 target IP
            ipv6_arg = _get_dracut_ipv6_argument(connection, iface, hostname)
            if ipv6_arg:
                netargs.add(ipv6_arg)
            else:
                log.error("No IPv6 configuration found in connection %s", connection.get_uuid())
        else:
            # Using IPv4 target IP
            ipv4_arg = _get_dracut_ipv4_argument(connection, iface, hostname)
            if ipv4_arg:
                netargs.add(ipv4_arg)
            else:
                log.error("No IPv4 configuration found in connection %s", connection.get_uuid())

        ifname_arg = _get_dracut_ifname_argument_from_connection(connection, iface)
        if ifname_arg:
            netargs.add(ifname_arg)

        team_arg = _get_dracut_team_argument_from_connection(nm_client, connection, iface)
        if team_arg:
            netargs.add(team_arg)

        vlan_arg, vlan_parent_connection = _get_dracut_vlan_argument_from_connection(nm_client,
                                                                                     connection,
                                                                                     iface)
        if vlan_arg:
            netargs.add(vlan_arg)
        # For vlan the parent connection defines the s390 znet argument values
        if vlan_parent_connection:
            connection = vlan_parent_connection

    znet_arg = _get_dracut_znet_argument_from_connection(connection)
    if znet_arg:
        netargs.add(znet_arg)

    return netargs


def _get_dracut_ipv6_argument(connection, iface, hostname):
    """Get dracut ip IPv6 configuration for given interface and NM connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param iface: network interface to be used
    :type iface: str
    :param hostname: static hostname to be configured
    :type hostname: str
    :returns: dracut ip argument or "" if the configuration can't be find
    :rtype: set(str)
    """
    argument = ""
    ip6_config = connection.get_setting_ip6_config()
    ip6_method = ip6_config.get_method()
    if ip6_method == NM.SETTING_IP6_CONFIG_METHOD_AUTO:
        argument = "ip={}:auto6".format(iface)
    elif ip6_method == NM.SETTING_IP6_CONFIG_METHOD_DHCP:
        # Most probably not working
        argument = "ip={}:dhcp6".format(iface)
    elif ip6_method == NM.SETTING_IP6_CONFIG_METHOD_MANUAL:
        ipaddr = ""
        if ip6_config.get_num_addresses() > 0:
            addr = ip6_config.get_address(0)
            ipaddr = "[{}/{}]".format(addr.get_address(), addr.get_prefix())
        gateway = ip6_config.get_gateway() or ""
        if gateway:
            gateway = "[{}]".format(gateway)
        if ipaddr or gateway:
            argument = ("ip={}::{}::{}:{}:none".format(ipaddr, gateway, hostname, iface))
    return argument


def _get_dracut_ipv4_argument(connection, iface, hostname):
    """Get dracut ip IPv4 configuration for given interface and NM connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param iface: network interface to be used
    :type iface: str
    :param hostname: static hostname to be configured
    :type hostname: str
    :returns: dracut ip argument or "" if the configuration can't be find
    :rtype: str
    """
    argument = ""
    ip4_config = connection.get_setting_ip4_config()
    ip4_method = ip4_config.get_method()
    if ip4_method == NM.SETTING_IP4_CONFIG_METHOD_AUTO:
        argument = "ip={}:dhcp".format(iface)
    elif ip4_method == NM.SETTING_IP4_CONFIG_METHOD_MANUAL:
        if ip4_config.get_num_addresses() > 0:
            addr = ip4_config.get_address(0)
            ip = addr.get_address()
            netmask = prefix2netmask(addr.get_prefix())
            gateway = ip4_config.get_gateway() or ""
            argument = "ip={}::{}:{}:{}:{}:none".format(ip, gateway, netmask, hostname, iface)
    return argument


def _get_dracut_ifname_argument_from_connection(connection, iface):
    """Get dracut ifname configuration for given interface and NM connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param iface: network interface to be used
    :type iface: str
    :returns: dracut ifname argument or "" if the configuration does not apply
    :rtype: str
    """
    argument = ""
    wired_setting = connection.get_setting_wired()
    if wired_setting:
        hwaddr = wired_setting.get_mac_address()
        if hwaddr:
            argument = "ifname={}:{}".format(iface, hwaddr.lower())
    return argument


def _get_dracut_team_argument_from_connection(nm_client, connection, iface):
    """Get dracut team configuration for given interface and NM connection.

    :param nm_client: instance of NetworkManager client
    :type nm_client: NM.Client
    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param iface: network interface to be used
    :type iface: str
    :returns: dracut team argument or "" if the configuration does not apply
    :rtype: str
    """
    argument = ""
    if connection.get_connection_type() == NM_CONNECTION_TYPE_TEAM:
        ports = get_ports_from_connections(
            nm_client,
            ["team"],
            [iface, connection.get_uuid()]
        )
        port_ifaces = sorted(s_iface for _name, s_iface, _uuid in ports if s_iface)
        argument = "team={}:{}".format(iface, ",".join(port_ifaces))
    return argument


def _get_dracut_vlan_argument_from_connection(nm_client, connection, iface):
    """Get dracut vlan configuration for given interface and NM connection.

    Returns also parent vlan connection.

    :param nm_client: instance of NetworkManager client
    :type nm_client: NM.Client
    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param iface: network interface to be used
    :type iface: str
    :returns: tuple (ARGUMENT, PARENT_CONNECTION) where
              ARGUMENT is dracut vlan argument or "" if the configuration does not apply
              PARENT_CONNECTION is vlan parent connection of the connection
    :rtype: tuple(str, NM.RemoteConnection)
    """
    argument = ""
    parent_con = None
    if connection.get_connection_type() == NM_CONNECTION_TYPE_VLAN:
        setting_vlan = connection.get_setting_vlan()
        parent_spec = setting_vlan.get_parent()
        parent = None
        # parent can be specified by connection uuid (eg from nm-c-e)
        if len(parent_spec) == NM_CONNECTION_UUID_LENGTH:
            parent_con = nm_client.get_connection_by_uuid(parent_spec)
            if parent_con:
                # On s390 with net.ifnames=0 there is no DEVICE so use NAME
                parent = parent_con.get_interface_name() or parent_con.get_id()
        # parent can be specified by interface
        else:
            parent = parent_spec
            parent_cons = get_connections_available_for_iface(nm_client, parent)
            if len(parent_cons) != 1:
                log.error("unexpected number of connections found for vlan parent %s",
                          parent_spec)
            if parent_cons:
                parent_con = parent_cons[0]

        if parent:
            argument = "vlan={}:{}".format(iface, parent)
        else:
            log.error("can't find parent interface of vlan device %s specified by %s",
                      iface, parent_spec)
        if not parent_con:
            log.error("can't find parent connection of vlan device %s specified by %s",
                      iface, parent_spec)

    return argument, parent_con


def _get_dracut_znet_argument_from_connection(connection):
    """Get dracut znet (s390) configuration for given NM connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :returns: dracut znet argument or "" if the configuration does not apply
    :rtype: str
    """
    argument = ""
    wired_setting = connection.get_setting_wired()
    if wired_setting and is_s390():
        devspec = util.execWithCapture("/lib/s390-tools/zdev-to-rd.znet",
                                       ["persistent",
                                        connection.get_interface_name()]).strip()
        argument = "rd.znet={}".format(devspec)
    return argument


def get_ports_from_connections(nm_client, port_types, controller_specs):
    """Get ports of controller of given type specified by uuid or interface.

    :param nm_client: instance of NetworkManager client
    :type nm_client: NM.Client
    :param port_types: type of the port - NM setting "slave-type" value (eg. "team")
    :type port_types: list(str)
    :param controller_specs: a list containing sepcification of a controller:
                             interface name or connection uuid or both
    :type controller_specs: list(str)
    :returns: ports specified by name, interface and connection uuid
    :rtype: set((str,str,str))
    """
    ports = set()
    for con in nm_client.get_connections():
        if con.get_setting_connection().get_port_type() not in port_types:
            continue
        if con.get_setting_connection().get_controller() in controller_specs:
            iface = get_iface_from_connection(nm_client, con.get_uuid())
            name = con.get_id()
            ports.add((name, iface, con.get_uuid()))
    return ports


def get_config_file_connection_of_device(nm_client, device_name, device_hwaddr=None):
    """Find connection of the device's configuration file.

    :param nm_client: instance of NetworkManager client
    :type nm_client: NM.Client
    :param device_name: name of the device
    :type device_name: str
    :param device_hwaddr: hardware address of the device
    :type device_hwaddr: str
    :returns: uuid of NetworkManager connection
    :rtype: str
    """

    cons = []
    for con in nm_client.get_connections():

        filename = con.get_filename() or ""
        # Ignore connections from initramfs in
        # /run/NetworkManager/system-connections
        if not is_config_file_for_system(filename):
            continue
        con_type = con.get_connection_type()

        if con_type == NM_CONNECTION_TYPE_ETHERNET:

            # Ignore ports
            if con.get_setting_connection().get_controller():
                continue

            interface_name = con.get_interface_name()
            mac_address = None
            wired_setting = con.get_setting_wired()
            if wired_setting:
                mac_address = wired_setting.get_mac_address()

            if interface_name:
                if interface_name == device_name:
                    cons.append(con)
            elif mac_address:
                if device_hwaddr:
                    if device_hwaddr.upper() == mac_address.upper():
                        cons.append(con)
                else:
                    iface = get_iface_from_hwaddr(nm_client, mac_address)
                    if iface == device_name:
                        cons.append(con)
            elif is_s390():
                # s390 setting generated in dracut with net.ifnames=0
                # has neither DEVICE/interface-name nor HWADDR/mac-address set (#1249750)
                if con.get_id() == device_name:
                    cons.append(con)

        elif con_type in (NM_CONNECTION_TYPE_BOND, NM_CONNECTION_TYPE_TEAM,
                          NM_CONNECTION_TYPE_BRIDGE, NM_CONNECTION_TYPE_INFINIBAND):
            if con.get_interface_name() == device_name:
                cons.append(con)

        elif con_type == NM_CONNECTION_TYPE_VLAN:
            interface_name = get_vlan_interface_name_from_connection(nm_client, con)
            if interface_name and interface_name == device_name:
                cons.append(con)

    if len(cons) > 1:
        log.debug("Unexpected number of config files found for %s: %s", device_name,
                  [con.get_filename() for con in cons])

    if cons:
        return cons[0].get_uuid()
    else:
        log.debug("Config file for %s not found", device_name)
        return ""


def get_kickstart_network_data(connection, nm_client, network_data_class):
    """Get kickstart data from NM connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param nm_client: instance of NetworkManager client
    :type nm_client: NM.Client
    :param network_data_class: pykickstart network command data class
    :type: pykickstart BaseData
    :returns: network_data object corresponding to the connection
    :rtype: network_data_class object instance
    """
    # no network command for non-virtual device ports
    if connection.get_connection_type() not in (NM_CONNECTION_TYPE_BOND, NM_CONNECTION_TYPE_TEAM):
        if connection.get_setting_connection().get_controller():
            return None

    # no support for wireless
    if connection.get_connection_type() == NM_CONNECTION_TYPE_WIFI:
        return None

    network_data = network_data_class()

    # connection
    network_data.onboot = connection.get_setting_connection().get_autoconnect()
    iface = get_iface_from_connection(nm_client, connection.get_uuid())
    if iface:
        network_data.device = iface

    _update_ip4_config_kickstart_network_data(connection, network_data)
    _update_ip6_config_kickstart_network_data(connection, network_data)
    _update_nameserver_kickstart_network_data(connection, network_data)

    # --mtu
    s_wired = connection.get_setting_wired()
    if s_wired:
        if s_wired.get_mtu():
            network_data.mtu = s_wired.get_mtu()

    # vlan
    if connection.get_connection_type() == NM_CONNECTION_TYPE_VLAN:
        _update_vlan_kickstart_network_data(nm_client, connection, network_data)

    # bonding
    if connection.get_connection_type() == NM_CONNECTION_TYPE_BOND:
        _update_bond_kickstart_network_data(nm_client, iface, connection, network_data)

    # bridging
    if connection.get_connection_type() == NM_CONNECTION_TYPE_BRIDGE:
        _update_bridge_kickstart_network_data(nm_client, iface, connection, network_data)

    # teaming
    if connection.get_connection_type() == NM_CONNECTION_TYPE_TEAM:
        _update_team_kickstart_network_data(nm_client, iface, connection, network_data)

    return network_data


def _update_nameserver_kickstart_network_data(connection, network_data):
    """Update nameserver configuration of network data from connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param network_data: kickstart configuration to be modified
    :type network_data: pykickstart NetworkData
    """
    # --nameserver is used both for ipv4 and ipv6
    dns_list = []
    s_ip4_config = connection.get_setting_ip4_config()
    if s_ip4_config:
        for i in range(s_ip4_config.get_num_dns()):
            dns_list.append(s_ip4_config.get_dns(i))
    s_ip6_config = connection.get_setting_ip6_config()
    if s_ip6_config:
        for i in range(s_ip6_config.get_num_dns()):
            dns_list.append(s_ip6_config.get_dns(i))
    dns_str = ','.join(dns_list)
    if dns_str:
        network_data.nameserver = dns_str


def _update_ip4_config_kickstart_network_data(connection, network_data):
    """Update IPv4 configuration of network data from connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param network_data: kickstart configuration to be modified
    :type network_data: pykickstart NetworkData
    """
    s_ip4_config = connection.get_setting_ip4_config()
    if not s_ip4_config:
        return
    ip4_method = s_ip4_config.get_method()
    if ip4_method == NM.SETTING_IP4_CONFIG_METHOD_DISABLED:
        network_data.noipv4 = True
    elif ip4_method == NM.SETTING_IP4_CONFIG_METHOD_AUTO:
        network_data.bootProto = "dhcp"
    elif ip4_method == NM.SETTING_IP4_CONFIG_METHOD_MANUAL:
        network_data.bootProto = "static"
        if s_ip4_config.get_num_addresses() > 0:
            addr = s_ip4_config.get_address(0)
            network_data.ip = addr.get_address()
            netmask = prefix2netmask(addr.get_prefix())
            if netmask:
                network_data.netmask = netmask
            gateway = s_ip4_config.get_gateway()
            if gateway:
                network_data.gateway = gateway

    # --hostname
    ip4_dhcp_hostname = s_ip4_config.get_dhcp_hostname()
    if ip4_dhcp_hostname:
        network_data.hostname = ip4_dhcp_hostname

    # dns
    network_data.ipv4_ignore_auto_dns = s_ip4_config.get_ignore_auto_dns()
    ip4_num_domains = s_ip4_config.get_num_dns_searches()
    ip4_domains = [s_ip4_config.get_dns_search(i) for i in range(ip4_num_domains)]
    ip4_dns_search = ",".join(ip4_domains)
    if ip4_dns_search:
        network_data.ipv4_dns_search = ip4_dns_search

    ip4_dhcpclass = s_ip4_config.get_dhcp_vendor_class_identifier()
    if ip4_dhcpclass:
        network_data.dhcpclass = ip4_dhcpclass


def _update_ip6_config_kickstart_network_data(connection, network_data):
    """Update IPv6 configuration of network data from connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param network_data: kickstart configuration to be modified
    :type network_data: pykickstart NetworkData
    """
    s_ip6_config = connection.get_setting_ip6_config()
    if not s_ip6_config:
        return
    ip6_method = s_ip6_config.get_method()
    if ip6_method == NM.SETTING_IP6_CONFIG_METHOD_DISABLED:
        network_data.noipv6 = True
    elif ip6_method == NM.SETTING_IP6_CONFIG_METHOD_AUTO:
        network_data.ipv6 = "auto"
    elif ip6_method == NM.SETTING_IP6_CONFIG_METHOD_DHCP:
        network_data.ipv6 = "dhcp"
    elif ip6_method == NM.SETTING_IP6_CONFIG_METHOD_MANUAL:
        if s_ip6_config.get_num_addresses() > 0:
            addr = s_ip6_config.get_address(0)
            network_data.ipv6 = "{}/{}".format(addr.get_address(), addr.get_prefix())
        gateway = s_ip6_config.get_gateway()
        if gateway:
            network_data.ipv6gateway = gateway

    # dns
    network_data.ipv6_ignore_auto_dns = s_ip6_config.get_ignore_auto_dns()
    ip6_num_domains = s_ip6_config.get_num_dns_searches()
    ip6_domains = [s_ip6_config.get_dns_search(i) for i in range(ip6_num_domains)]
    ip6_dns_search = ",".join(ip6_domains)
    if ip6_dns_search:
        network_data.ipv6_dns_search = ip6_dns_search


def _update_vlan_kickstart_network_data(nm_client, connection, network_data):
    """Update vlan configuration of network data from connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param network_data: kickstart configuration to be modified
    :type network_data: pykickstart NetworkData
    """
    setting_vlan = connection.get_setting_vlan()
    if setting_vlan:
        interface_name = connection.get_setting_connection().get_interface_name()
        vlanid = setting_vlan.get_id()
        parent = setting_vlan.get_parent()
        # if parent is specified by UUID
        if len(parent) == NM_CONNECTION_UUID_LENGTH:
            parent = get_iface_from_connection(nm_client, parent)
        default_name = default_ks_vlan_interface_name(parent, vlanid)
        if interface_name and interface_name != default_name:
            network_data.interfacename = interface_name
        network_data.vlanid = vlanid
        network_data.device = parent


def _update_bond_kickstart_network_data(nm_client, iface, connection, network_data):
    """Update bond configuration of network data from connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param network_data: kickstart configuration to be modified
    :type network_data: pykickstart NetworkData
    """
    ports = get_ports_from_connections(
        nm_client,
        ['bond'],
        [iface, connection.get_uuid()]
    )
    if ports:
        port_ifaces = sorted(s_iface for _name, s_iface, _uuid in ports if s_iface)
        network_data.bondslaves = ",".join(port_ifaces)
    s_bond = connection.get_setting_bond()
    if s_bond:
        option_list = []
        for i in range(s_bond.get_num_options()):
            _result, _name, _value = s_bond.get_option(i)
            if _result:
                option_list.append("{}={}".format(_name, _value))
        if option_list:
            network_data.bondopts = ",".join(option_list)


def _update_bridge_kickstart_network_data(nm_client, iface, connection, network_data):
    """Update bridge configuration of network data from connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param network_data: kickstart configuration to be modified
    :type network_data: pykickstart NetworkData
    """
    ports = get_ports_from_connections(
        nm_client,
        ['bridge'],
        [iface, connection.get_uuid()]
    )
    if ports:
        port_ifaces = sorted(s_iface for _name, s_iface, _uuid in ports if s_iface)
        network_data.bridgeslaves = ",".join(port_ifaces)
    s_bridge = connection.get_setting_bridge()
    if s_bridge:
        bridge_options = []
        for setting, default_value in NM_BRIDGE_DUMPED_SETTINGS_DEFAULTS.items():
            value = s_bridge.get_property(setting)
            if value != default_value:
                bridge_options.append("{}={}".format(setting, value))
        if bridge_options:
            network_data.bridgeopts = ",".join(bridge_options)


def _update_team_kickstart_network_data(nm_client, iface, connection, network_data):
    """Update team configuration of network data from connection.

    :param connection: NetworkManager connection
    :type connection: NM.RemoteConnection
    :param network_data: kickstart configuration to be modified
    :type network_data: pykickstart NetworkData
    """
    ports = get_ports_from_connections(
        nm_client,
        ['team'],
        [iface, connection.get_uuid()]
    )
    if ports:
        port_list = sorted((s_iface, s_uuid) for _name, s_iface, s_uuid in ports if s_iface)

        for s_iface, s_uuid in port_list:
            team_port_cfg = get_team_port_config_from_connection(nm_client, s_uuid) or ""
            network_data.teamslaves.append((s_iface, team_port_cfg))

    s_team = connection.get_setting_team()
    if s_team:
        teamconfig = s_team.get_config()
        if teamconfig:
            network_data.teamconfig = teamconfig.replace("\n", "").replace(" ", "")


def is_bootif_connection(con):
    return con.get_id().startswith("BOOTIF Connection")
