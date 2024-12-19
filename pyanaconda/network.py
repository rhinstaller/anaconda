#
# network.py - network configuration install data
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
#               2008, 2009, 2017
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import ipaddress
import itertools
import os
import re
import shutil
import socket
import threading
import time

import gi
from dasbus.typing import get_native

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants, util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import TIME_SOURCE_SERVER
from pyanaconda.core.i18n import _
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.path import make_directories
from pyanaconda.core.regexes import (
    HOSTNAME_PATTERN_WITHOUT_ANCHORS,
    IPV6_ADDRESS_IN_DRACUT_IP_OPTION,
    MAC_OCTET,
)
from pyanaconda.modules.common.constants.objects import FCOE
from pyanaconda.modules.common.constants.services import NETWORK, STORAGE, TIMEZONE
from pyanaconda.modules.common.structures.network import NetworkDeviceInfo
from pyanaconda.modules.common.structures.timezone import TimeSourceData
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.modules.common.util import is_module_available

gi.require_version("NM", "1.0")
from gi.repository import NM

log = get_module_logger(__name__)

network_connected = None
network_connected_condition = threading.Condition()

_nm_client = None

__all__ = [
    "check_ip_address",
    "copy_resolv_conf_to_root",
    "get_first_ip_address",
    "get_nm_client",
    "get_supported_devices",
    "initialize_network",
    "is_valid_hostname",
    "netmask_to_prefix",
    "prefix_to_netmask",
    "status_message",
    "wait_for_connected_NM",
    "wait_for_connecting_NM_thread",
    "wait_for_connectivity",
    "wait_for_network_devices",
    "write_configuration",
]


def get_nm_client():
    """Get NetworkManager Client."""
    if conf.system.provides_system_bus:
        global _nm_client
        if not _nm_client:
            _nm_client = NM.Client.new(None)
        return _nm_client
    else:
        log.debug("NetworkManager client not available (system does not provide it).")
        return None


def check_ip_address(address, version=None):
    """Check if the given IP address is valid in given version if set.

    :param str address: IP address for testing
    :param int version: ``4`` for IPv4, ``6`` for IPv6 or
                        ``None`` to allow either format
    :returns: ``True`` if IP address is valid or ``False`` if not
    :rtype: bool
    """
    try:
        if version == 4:
            ipaddress.IPv4Address(address)
        elif version == 6:
            ipaddress.IPv6Address(address)
        elif not version:  # any of those
            ipaddress.ip_address(address)
        else:
            log.error("IP version %s is not supported", version)
            return False
        return True
    except ValueError:
        return False


def is_valid_hostname(hostname, local=False):
    """Check if the given string is (syntactically) a valid hostname.

    :param str hostname: a string to check
    :param bool local: is the hostname static (for this system) or not (on the network)
    :returns: a pair containing boolean value (valid or invalid) and
              an error message (if applicable)
    :rtype: (bool, str)
    """
    if not hostname:
        return (False, _("Host name cannot be None or an empty string."))

    if len(hostname) > 64:
        return (False, _("Host name must be 64 or fewer characters in length."))

    if local and hostname[-1] == ".":
        return (False, _("Local host name must not end with period '.'."))

    if not re.match('^' + HOSTNAME_PATTERN_WITHOUT_ANCHORS + '$', hostname):
        return (False, _("Host names can only contain the characters 'a-z', "
                         "'A-Z', '0-9', '-', or '.', parts between periods "
                         "must contain something and cannot start or end with "
                         "'-'."))

    return (True, "")


def get_ip_addresses():
    """Return a list of IP addresses for all active devices."""
    ipv4_addresses = []
    ipv6_addresses = []
    for device in get_activated_devices(get_nm_client()):
        ipv4_addresses += get_device_ip_addresses(device, version=4)
        ipv6_addresses += get_device_ip_addresses(device, version=6)
    # prefer IPv4 addresses to IPv6 addresses
    return ipv4_addresses + ipv6_addresses


def get_first_ip_address():
    """Return the first non-local IP of active devices.

    :return: IP address assigned to an active device
    :rtype: str or None
    """
    for ip in get_ip_addresses():
        if ip not in ("127.0.0.1", "::1"):
            return ip
    return None


def netmask_to_prefix(netmask):
    """ Convert netmask to prefix (CIDR bits) """
    prefix = 0

    while prefix < 33:
        if prefix_to_netmask(prefix) == netmask:
            return prefix

        prefix += 1

    return prefix


def prefix_to_netmask(prefix):
    """ Convert prefix (CIDR bits) to netmask """
    _bytes = []
    for _i in range(4):
        if prefix >= 8:
            _bytes.append(255)
            prefix -= 8
        else:
            _bytes.append(256 - 2 ** (8 - prefix))
            prefix = 0
    netmask = ".".join(str(byte) for byte in _bytes)
    return netmask


def hostname_from_cmdline(kernel_args):
    """Get hostname defined by boot options.

    :param kernel_args: structure holding installer boot options
    :type kernel_args: KernelArguments
    """
    # legacy hostname= option
    hostname = kernel_args.get('hostname', "")
    # ip= option (man dracut.cmdline)
    ipopts = kernel_args.get('ip')
    # Example (2 options):
    # ens3:dhcp 10.34.102.244::10.34.102.54:255.255.255.0:myhostname:ens9:none
    if ipopts:
        for ipopt in ipopts.split(" "):
            if ipopt.startswith("["):
                # Replace ipv6 addresses with empty string, example of ipv6 config:
                # [fd00:10:100::84:5]::[fd00:10:100::86:49]:80:myhostname:ens9:none
                ipopt = IPV6_ADDRESS_IN_DRACUT_IP_OPTION.sub('', ipopt)
            elements = ipopt.split(':')
            # Hostname can be defined only in option having more than 5 elements.
            # But filter out auto ip= with mac address set by MAC_OCTET matching, eg:
            # ip=<interface>:dhcp::52:54:00:12:34:56
            # where the 4th element is not hostname.
            if len(elements) > 5 and not re.match(MAC_OCTET, elements[5]):
                hostname = ipopt.split(':')[4]
    return hostname


def iface_for_host_ip(host_ip):
    """Get interface used to access given host IP."""
    route = util.execWithCapture("ip", ["route", "get", "to", host_ip])
    if not route:
        log.error("Could not get interface for route to %s", host_ip)
        return ""

    route_info = route.split()
    if route_info[0] != host_ip or len(route_info) < 5 or \
       "dev" not in route_info or route_info.index("dev") > 3:
        log.error('Unexpected "ip route get to %s" reply: %s', host_ip, route_info)
        return ""

    return route_info[route_info.index("dev") + 1]


def copy_resolv_conf_to_root(root="/"):
    """Copy resolv.conf to a system root."""
    src = "/etc/resolv.conf"
    dst = os.path.join(root, src.lstrip('/'))
    if not os.path.isfile(src):
        log.debug("%s does not exist", src)
        return
    if os.path.isfile(dst):
        log.debug("%s already exists", dst)
        return
    dst_dir = os.path.dirname(dst)
    if not os.path.isdir(dst_dir):
        make_directories(dst_dir)
    shutil.copyfile(src, dst)


def run_network_initialization_task(task_path):
    """Run network initialization task and log the result."""
    task_proxy = NETWORK.get_proxy(task_path)
    log.debug("Running task %s", task_proxy.Name)
    sync_run_task(task_proxy)
    result = get_native(task_proxy.GetResult())
    msg = "%s result: %s" % (task_proxy.Name, result)
    log.debug(msg)


def initialize_network():
    """Initialize networking."""
    if not conf.system.can_configure_network:
        return

    network_proxy = NETWORK.get_proxy()

    msg = "Initialization started."
    log.debug(msg)
    network_proxy.LogConfigurationState(msg)

    log.debug("Devices found: %s",
              [dev.device_name for dev in get_supported_devices()])

    if util.is_stage2_on_nfs() and network_proxy.Kickstarted:
        msg = "Using kickstart network configuration with installer image (stage2) provided " \
            "via nfs server can freeze the installation."
        log.warning(msg)
        print("WARNING:", msg)

    run_network_initialization_task(network_proxy.ApplyKickstartWithTask())
    run_network_initialization_task(network_proxy.DumpMissingConfigFilesWithTask())

    if not network_proxy.Hostname:
        bootopts_hostname = hostname_from_cmdline(kernel_arguments)
        if bootopts_hostname:
            log.debug("Updating host name from boot options: %s", bootopts_hostname)
            network_proxy.Hostname = bootopts_hostname

    # Create device configuration tracking in the module.
    # It will be used to generate kickstart from persistent network configuration
    # managed by NM (having config files) and updated by NM signals on device
    # configuration changes.
    log.debug("Creating network configurations.")
    network_proxy.CreateDeviceConfigurations()

    log.debug("Initialization finished.")


def write_configuration(overwrite=False):
    """Install network configuration to target system."""
    fcoe_proxy = STORAGE.get_proxy(FCOE)
    fcoe_nics = fcoe_proxy.GetNics()
    fcoe_ifaces = [dev.device_name for dev in get_supported_devices()
                   if dev.device_name in fcoe_nics]
    network_proxy = NETWORK.get_proxy()

    task_path = network_proxy.ConfigureActivationOnBootWithTask(fcoe_ifaces)
    task_proxy = NETWORK.get_proxy(task_path)
    sync_run_task(task_proxy)

    task_path = network_proxy.InstallNetworkWithTask(overwrite)
    task_proxy = NETWORK.get_proxy(task_path)
    sync_run_task(task_proxy)

    task_path = network_proxy.ConfigureHostnameWithTask(overwrite)
    task_proxy = NETWORK.get_proxy(task_path)
    sync_run_task(task_proxy)

    if conf.system.can_change_hostname:
        hostname = network_proxy.Hostname
        if hostname:
            network_proxy.SetCurrentHostname(hostname)


def _set_ntp_servers_from_dhcp():
    """Set NTP servers of timezone module from dhcp if not set by kickstart."""
    # FIXME - do it only if they will be applied (the guard at the end of the function)
    if not is_module_available(TIMEZONE):
        return

    timezone_proxy = TIMEZONE.get_proxy()
    ntp_servers = get_ntp_servers_from_dhcp(get_nm_client())
    log.info("got %d NTP servers from DHCP", len(ntp_servers))
    hostnames = []
    for server_address in ntp_servers:
        try:
            hostname = socket.gethostbyaddr(server_address)[0]
        except socket.error:
            # getting hostname failed, just use the address returned from DHCP
            log.debug("getting NTP server host name failed for address: %s",
                      server_address)
            hostname = server_address
        hostnames.append(hostname)

    # check if some NTP servers were specified from kickstart
    if not timezone_proxy.TimeSources and conf.target.is_hardware:
        # no NTP servers were specified, add those from DHCP
        servers = []

        for hostname in hostnames:
            server = TimeSourceData()
            server.type = TIME_SOURCE_SERVER
            server.hostname = hostname
            server.options = ["iburst"]
            servers.append(server)

        timezone_proxy.TimeSources = \
            TimeSourceData.to_structure_list(servers)


def wait_for_connected_NM(timeout=constants.NETWORK_CONNECTION_TIMEOUT, only_connecting=False):
    """Wait for NM being connected.

    If only_connecting is set, wait only if NM is in connecting state and
    return immediately after leaving this state (regardless of the new state).
    Used to wait for dhcp configuration in progress.

    :param timeout: timeout in seconds
    :type timeout: int
    :parm only_connecting: wait only for the result of NM being connecting
    :type only_connecting: bool
    :return: NM is connected
    :rtype: bool
    """

    network_proxy = NETWORK.get_proxy()
    if network_proxy.Connected:
        return True

    if only_connecting:
        if network_proxy.IsConnecting():
            log.debug("waiting for connecting NM (dhcp in progress?), timeout=%d", timeout)
        else:
            return False
    else:
        log.debug("waiting for connected NM, timeout=%d", timeout)

    i = 0
    while i < timeout:
        i += constants.NETWORK_CONNECTED_CHECK_INTERVAL
        time.sleep(constants.NETWORK_CONNECTED_CHECK_INTERVAL)
        if network_proxy.Connected:
            log.debug("NM connected, waited %d seconds", i)
            return True
        elif only_connecting:
            if not network_proxy.IsConnecting():
                break

    log.debug("NM not connected, waited %d seconds", i)
    return False


def wait_for_network_devices(devices, timeout=constants.NETWORK_CONNECTION_TIMEOUT):
    """Wait for network devices to be activated with a connection."""
    devices = set(devices)
    i = 0
    log.debug("waiting for connection of devices %s for iscsi", devices)
    while i < timeout:
        network_proxy = NETWORK.get_proxy()
        activated_devices = network_proxy.GetActivatedInterfaces()
        if not devices - set(activated_devices):
            return True
        i += 1
        time.sleep(1)
    return False


def wait_for_connecting_NM_thread():
    """Wait for connecting NM in thread, do some work and signal connectivity.

    This function is called from a thread which is run at startup to wait for
    NetworkManager being in connecting state (eg getting IP from DHCP). When NM
    leaves connecting state do some actions and signal new state if NM becomes
    connected.
    """
    connected = wait_for_connected_NM(only_connecting=True)
    if connected:
        _set_ntp_servers_from_dhcp()
    with network_connected_condition:
        global network_connected
        network_connected = connected
        network_connected_condition.notify_all()


def wait_for_connectivity(timeout=constants.NETWORK_CONNECTION_TIMEOUT):
    """Wait for network connectivty to become available

    :param timeout: how long to wait in seconds
    :type timeout: integer of float"""
    connected = False
    network_connected_condition.acquire()
    # if network_connected is None, network connectivity check
    # has not yet been run or is in progress, so wait for it to finish
    if network_connected is None:
        # wait releases the lock and reacquires it once the thread is unblocked
        network_connected_condition.wait(timeout=timeout)
    connected = network_connected
    # after wait() unblocks, we get the lock back,
    # so we need to release it
    network_connected_condition.release()
    return connected


def get_activated_devices(nm_client):
    """Get activated NetworkManager devices."""
    activated_devices = []

    if not nm_client:
        return activated_devices

    for ac in nm_client.get_active_connections():
        if ac.get_state() != NM.ActiveConnectionState.ACTIVATED:
            continue
        for device in ac.get_devices():
            activated_devices.append(device)
    return activated_devices


def status_message(nm_client):
    """A short string describing which devices are connected."""

    msg = _("Unknown")

    if not nm_client:
        msg = _("Status not available")
        return msg

    state = nm_client.get_state()
    if state == NM.State.CONNECTING:
        msg = _("Connecting...")
    elif state == NM.State.DISCONNECTING:
        msg = _("Disconnecting...")
    else:
        active_devs = [d for d in get_activated_devices(nm_client)
                       if not is_libvirt_device(d.get_ip_iface() or d.get_iface())]
        if active_devs:

            ports = {}
            ssids = {}
            nonports = []

            # first find ports and wireless aps
            for device in active_devs:
                device_ports = []
                if hasattr(device, 'get_slaves'):
                    device_ports = [port_dev.get_iface() for port_dev in device.get_slaves()]
                iface = device.get_iface()
                ports[iface] = device_ports
                if device.get_device_type() == NM.DeviceType.WIFI:
                    ssid = ""
                    ap = device.get_active_access_point()
                    if ap:
                        ssid = ap.get_ssid().get_data().decode()
                    ssids[iface] = ssid
            all_ports = set(itertools.chain.from_iterable(ports.values()))
            nonports = [dev for dev in active_devs if dev.get_iface() not in all_ports]

            if len(nonports) == 1:
                device = nonports[0]
                iface = device.get_ip_iface() or device.get_iface()
                device_type = device.get_device_type()
                if device_type_is_supported_wired(device_type):
                    msg = _("Wired (%(interface_name)s) connected") \
                          % {"interface_name": iface}
                elif device_type == NM.DeviceType.WIFI:
                    msg = _("Wireless connected to %(access_point)s") \
                          % {"access_point": ssids[iface]}
                elif device_type == NM.DeviceType.BOND:
                    msg = _("Bond %(interface_name)s (%(list_of_ports)s) connected") \
                          % {"interface_name": iface,
                             "list_of_ports": ",".join(ports[iface])}
                elif device_type == NM.DeviceType.TEAM:
                    msg = _("Team %(interface_name)s (%(list_of_ports)s) connected") \
                          % {"interface_name": iface,
                             "list_of_ports": ",".join(ports[iface])}
                elif device_type == NM.DeviceType.BRIDGE:
                    msg = _("Bridge %(interface_name)s (%(list_of_ports)s) connected") \
                          % {"interface_name": iface,
                             "list_of_ports": ",".join(ports[iface])}
                elif device_type == NM.DeviceType.VLAN:
                    parent = device.get_parent()
                    vlanid = device.get_vlan_id()
                    msg = _("VLAN %(interface_name)s (%(parent_device)s, ID %(vlanid)s) connected") \
                        % {"interface_name": iface, "parent_device": parent, "vlanid": vlanid}
            elif len(nonports) > 1:
                devlist = []
                for device in nonports:
                    iface = device.get_ip_iface() or device.get_iface()
                    device_type = device.get_device_type()
                    if device_type_is_supported_wired(device_type):
                        devlist.append("%s" % iface)
                    elif device_type == NM.DeviceType.WIFI:
                        devlist.append("%s" % ssids[iface])
                    elif device_type == NM.DeviceType.BOND:
                        devlist.append("%s (%s)" % (iface, ",".join(ports[iface])))
                    elif device_type == NM.DeviceType.TEAM:
                        devlist.append("%s (%s)" % (iface, ",".join(ports[iface])))
                    elif device_type == NM.DeviceType.BRIDGE:
                        devlist.append("%s (%s)" % (iface, ",".join(ports[iface])))
                    elif device_type == NM.DeviceType.VLAN:
                        devlist.append("%s" % iface)
                msg = _("Connected: %(list_of_interface_names)s") % {"list_of_interface_names": ", ".join(devlist)}
        else:
            msg = _("Not connected")

    if not get_supported_devices():
        msg = _("No network devices available")

    return msg


def get_supported_devices():
    """Get existing network devices supported by the installer.

    :return: basic information about the devices
    :rtype: list(NetworkDeviceInfo)
    """
    network_proxy = NETWORK.get_proxy()
    return NetworkDeviceInfo.from_structure_list(network_proxy.GetSupportedDevices())


def get_ntp_servers_from_dhcp(nm_client):
    """Return IPs of NTP servers obtained by DHCP.

    :param nm_client: instance of NetworkManager client
    :type nm_client: NM.Client
    :return: IPs of NTP servers obtained by DHCP
    :rtype: list of str
    """
    ntp_servers = []

    if not nm_client:
        return ntp_servers

    for device in get_activated_devices(nm_client):
        dhcp4_config = device.get_dhcp4_config()
        if dhcp4_config:
            options = dhcp4_config.get_options()
            ntp_servers_string = options.get("ntp_servers")
            if ntp_servers_string:
                ntp_servers.extend(ntp_servers_string.split(" "))
        # NetworkManager does not request NTP/SNTP options for DHCP6

    return ntp_servers


def get_device_ip_addresses(device, version=4):
    """Get IP addresses of the device.

    Ignores ipv6 link-local addresses.

    :param device: NetworkManager device object
    :type device: NMDevice
    :param version: IP version (4 or 6)
    :type version: int
    """
    addresses = []

    if version == 4:
        ipv4_config = device.get_ip4_config()
        if ipv4_config:
            addresses = [addr.get_address() for addr in ipv4_config.get_addresses()]
    elif version == 6:
        ipv6_config = device.get_ip6_config()
        if ipv6_config:
            all_addresses = [addr.get_address() for addr in ipv6_config.get_addresses()]
            addresses = [addr for addr in all_addresses
                         if not addr.startswith("fe80:")]
    return addresses


def is_libvirt_device(iface):
    return iface and iface.startswith("virbr")


def device_type_is_supported_wired(device_type):
    return device_type in [NM.DeviceType.ETHERNET, NM.DeviceType.INFINIBAND]
