# Network configuration spoke classes
#
# Copyright (C) 2013  Red Hat, Inc.
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

from gi.repository import NM
from simpleline.render.containers import ListColumnContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import CheckboxWidget, EntryWidget, TextWidget

from pyanaconda import network
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import ANACONDA_ENVIRON
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.regexes import (
    IPV4_NETMASK_WITH_ANCHORS,
    IPV4_OR_DHCP_PATTERN_WITH_ANCHORS,
    IPV4_PATTERN_WITH_ANCHORS,
)
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.structures.network import NetworkDeviceConfiguration
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import Dialog, report_if_failed

log = get_module_logger(__name__)

# This will be used in decorators in ConfigureDeviceSpoke.
# The decorators are processed before the class is created so you can have this as a variable there.
IP_ERROR_MSG = N_("Bad format of the IP address")
NETMASK_ERROR_MSG = N_("Bad format of the netmask")

__all__ = ["NetworkSpoke"]


# TODO: use our own datastore?
class WiredTUIConfigurationData():
    """Holds tui input configuration data of wired device."""
    def __init__(self):
        self.ip = "dhcp"
        self.netmask = ""
        self.gateway = ""
        self.ipv6 = "auto"
        self.ipv6gateway = ""
        self.nameserver = ""
        self.ipv6addrgenmode = NM.SettingIP6ConfigAddrGenMode.EUI64
        self.onboot = False

    def set_from_connection(self, connection):
        """Set the object from NM RemoteConnection.

        :param connection: connection to be used to set the object
        :type connection: NM.RemoteConnection
        """
        connection_uuid = connection.get_uuid()

        ip4_config = connection.get_setting_ip4_config()
        ip4_method = ip4_config.get_method()
        if ip4_method == NM.SETTING_IP4_CONFIG_METHOD_AUTO:
            self.ip = "dhcp"
        elif ip4_method == NM.SETTING_IP4_CONFIG_METHOD_MANUAL:
            if ip4_config.get_num_addresses() > 0:
                addr = ip4_config.get_address(0)
                self.ip = addr.get_address()
                self.netmask = network.prefix_to_netmask(addr.get_prefix())
            else:
                log.error("No ip4 address found for manual method in %s", connection_uuid)
        elif ip4_method == NM.SETTING_IP4_CONFIG_METHOD_DISABLED:
            self.ip = ""
        else:
            log.error("Unexpected ipv4 method %s found in connection %s", ip4_method, connection_uuid)
            self.ip = "dhcp"
        self.gateway = ip4_config.get_gateway() or ""

        ip6_config = connection.get_setting_ip6_config()
        self.ipv6addrgenmode = ip6_config.get_addr_gen_mode()
        ip6_method = ip6_config.get_method()
        if ip6_method == NM.SETTING_IP6_CONFIG_METHOD_AUTO:
            self.ipv6 = "auto"
        elif ip6_method == NM.SETTING_IP6_CONFIG_METHOD_IGNORE:
            self.ipv6 = "ignore"
        elif ip6_method == NM.SETTING_IP6_CONFIG_METHOD_DHCP:
            self.ipv6 = "dhcp"
        elif ip6_method == NM.SETTING_IP6_CONFIG_METHOD_MANUAL:
            if ip6_config.get_num_addresses() > 0:
                addr = ip6_config.get_address(0)
                self.ipv6 = "{}/{}".format(addr.get_address(), addr.get_prefix())
            else:
                log.error("No ip6 address found for manual method in %s", connection_uuid)
        else:
            log.error("Unexpected ipv6 method %s found in connection %s", ip6_method, connection_uuid)
            self.ipv6 = "auto"
        self.ipv6gateway = ip6_config.get_gateway() or ""

        nameservers = []
        for i in range(0, ip4_config.get_num_dns()):
            nameservers.append(ip4_config.get_dns(i))
        for i in range(0, ip6_config.get_num_dns()):
            nameservers.append(ip6_config.get_dns(i))
        self.nameserver = ",".join(nameservers)

        self.onboot = connection.get_setting_connection().get_autoconnect()

    def update_connection(self, connection):
        """Update NM RemoteConnection from the object.

        :param connection: connection to be updated from the object
        :type connection: NM.RemoteConnection
        """
        # ipv4 settings
        if self.ip == "dhcp":
            method4 = NM.SETTING_IP4_CONFIG_METHOD_AUTO
        elif self.ip:
            method4 = NM.SETTING_IP4_CONFIG_METHOD_MANUAL
        else:
            method4 = NM.SETTING_IP4_CONFIG_METHOD_DISABLED

        connection.remove_setting(NM.SettingIP4Config)
        s_ip4 = NM.SettingIP4Config.new()
        s_ip4.set_property(NM.SETTING_IP_CONFIG_METHOD, method4)
        if method4 == NM.SETTING_IP4_CONFIG_METHOD_MANUAL:
            prefix4 = network.netmask_to_prefix(self.netmask)
            addr4 = NM.IPAddress.new(socket.AF_INET, self.ip, prefix4)
            s_ip4.add_address(addr4)
            if self.gateway:
                s_ip4.props.gateway = self.gateway
        connection.add_setting(s_ip4)

        # ipv6 settings
        if self.ipv6 == "ignore":
            method6 = NM.SETTING_IP6_CONFIG_METHOD_IGNORE
        elif not self.ipv6 or self.ipv6 == "auto":
            method6 = NM.SETTING_IP6_CONFIG_METHOD_AUTO
        elif self.ipv6 == "dhcp":
            method6 = NM.SETTING_IP6_CONFIG_METHOD_DHCP
        else:
            method6 = NM.SETTING_IP6_CONFIG_METHOD_MANUAL

        connection.remove_setting(NM.SettingIP6Config)
        s_ip6 = NM.SettingIP6Config.new()
        s_ip6.set_property(NM.SETTING_IP6_CONFIG_ADDR_GEN_MODE, self.ipv6addrgenmode)
        s_ip6.set_property(NM.SETTING_IP_CONFIG_METHOD, method6)
        if method6 == NM.SETTING_IP6_CONFIG_METHOD_MANUAL:
            addr6, _slash, prefix6 = self.ipv6.partition("/")
            if prefix6:
                prefix6 = int(prefix6)
            else:
                prefix6 = 64
            addr6 = NM.IPAddress.new(socket.AF_INET6, addr6, prefix6)
            s_ip6.add_address(addr6)
            if self.ipv6gateway:
                s_ip6.props.gateway = self.ipv6gateway
        connection.add_setting(s_ip6)

        # nameservers
        if self.nameserver:
            for ns in [str.strip(i) for i in self.nameserver.split(",")]:
                if NM.utils_ipaddr_valid(socket.AF_INET6, ns):
                    s_ip6.add_dns(ns)
                elif NM.utils_ipaddr_valid(socket.AF_INET, ns):
                    s_ip4.add_dns(ns)
                else:
                    log.error("IP address %s is not valid", ns)

        s_con = connection.get_setting_connection()
        s_con.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, self.onboot)

    def __str__(self):
        return "WiredTUIConfigurationData ip:{} netmask:{} gateway:{} ipv6:{} ipv6gateway:{} " \
            "nameserver:{} onboot:{} addr-gen-mode:{}".format(self.ip, self.netmask, self.gateway,
                                                              self.ipv6, self.ipv6gateway,
                                                              self.nameserver, self.onboot,
                                                              self.ipv6addrgenmode)


class NetworkSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    """ Spoke used to configure network settings.

       .. inheritance-diagram:: NetworkSpoke
          :parts: 3
    """
    category = SystemCategory
    configurable_device_types = [
        NM.DeviceType.ETHERNET,
        NM.DeviceType.INFINIBAND,
    ]

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "network-configuration"

    def __init__(self, data, storage, payload):
        NormalTUISpoke.__init__(self, data, storage, payload)
        self.title = N_("Network configuration")
        self._network_module = NETWORK.get_proxy()

        self.nm_client = network.get_nm_client()
        if not self.nm_client and conf.system.provides_system_bus:
            self.nm_client = NM.Client.new(None)

        self._container = None
        self.hostname = self._network_module.Hostname
        self.editable_configurations = []
        self.errors = []
        self._apply = False

    @classmethod
    def should_run(cls, environment, data):
        """Should the spoke run?"""
        if not FirstbootSpokeMixIn.should_run(environment, data):
            return False

        return conf.system.can_configure_network

    def initialize(self):
        self.initialize_start()
        NormalTUISpoke.initialize(self)
        self._update_editable_configurations()
        self._network_module.DeviceConfigurationChanged.connect(self._device_configurations_changed)
        self.initialize_done()

    def _device_configurations_changed(self, device_configurations):
        log.debug("device configurations changed: %s", device_configurations)
        self._update_editable_configurations()

    def _update_editable_configurations(self):
        device_configurations = NetworkDeviceConfiguration.from_structure_list(
            self._network_module.GetDeviceConfigurations()
        )
        self.editable_configurations = [dc for dc in device_configurations
                                        if dc.device_type in self.configurable_device_types]

    @property
    def completed(self):
        """ Check whether this spoke is complete or not."""
        # If we can't configure network, don't require it
        return (not conf.system.can_configure_network
                or self._network_module.IsConnecting()
                or self._network_module.Connected)

    @property
    def mandatory(self):
        # the network spoke should be mandatory only if it is running
        # during the installation and if the installation source requires network
        return ANACONDA_ENVIRON in flags.environs and self.payload.needs_network

    @property
    def status(self):
        """ Short msg telling what devices are active. """
        return network.status_message(self.nm_client)

    def _summary_text(self):
        """Devices cofiguration shown to user."""
        msg = ""
        activated_devs = self._network_module.GetActivatedInterfaces()
        for device_configuration in self.editable_configurations:
            name = device_configuration.device_name
            if name in activated_devs:
                msg += self._activated_device_msg(name)
            else:
                msg += _("Wired (%(interface_name)s) disconnected\n") \
                       % {"interface_name": name}
        return msg

    def _activated_device_msg(self, devname):
        msg = _("Wired (%(interface_name)s) connected\n") \
              % {"interface_name": devname}

        device = self.nm_client.get_device_by_iface(devname)
        if device:
            addr_str = dnss_str = gateway_str = netmask_str = ""
            ipv4config = device.get_ip4_config()
            if ipv4config:
                addresses = ipv4config.get_addresses()
                if addresses:
                    a0 = addresses[0]
                    addr_str = a0.get_address()
                    prefix = a0.get_prefix()
                    netmask_str = network.prefix_to_netmask(prefix)
                gateway_str = ipv4config.get_gateway() or ''
                dnss_str = ",".join(ipv4config.get_nameservers())
            msg += _(" IPv4 Address: %(addr)s Netmask: %(netmask)s Gateway: %(gateway)s\n") % \
                {"addr": addr_str, "netmask": netmask_str, "gateway": gateway_str}
            msg += _(" DNS: %s\n") % dnss_str

            ipv6config = device.get_ip6_config()
            if ipv6config:
                for address in ipv6config.get_addresses():
                    addr_str = address.get_address()
                    prefix = address.get_prefix()
                    # Do not display link-local addresses
                    if not addr_str.startswith("fe80:"):
                        msg += _(" IPv6 Address: %(addr)s/%(prefix)d\n") % \
                            {"addr": addr_str, "prefix": prefix}
        return msg

    def refresh(self, args=None):
        """ Refresh screen. """
        NormalTUISpoke.refresh(self, args)

        self._container = ListColumnContainer(1, columns_width=78, spacing=1)

        if not self.nm_client:
            self.window.add_with_separator(TextWidget(_("Network configuration is not available.")))
            return

        summary = self._summary_text()
        self.window.add_with_separator(TextWidget(summary))

        hostname = _("Host Name: %s\n") % self._network_module.Hostname
        self.window.add_with_separator(TextWidget(hostname))
        current_hostname = _("Current host name: %s\n") % self._network_module.GetCurrentHostname()
        self.window.add_with_separator(TextWidget(current_hostname))

        # if we have any errors, display them
        while len(self.errors) > 0:
            self.window.add_with_separator(TextWidget(self.errors.pop()))

        dialog = Dialog(_("Host Name"))
        self._container.add(TextWidget(_("Set host name")), callback=self._set_hostname_callback, data=dialog)

        self._container.add(TextWidget(_("Apply host name")), callback=self._apply_hostname_callback)

        for device_configuration in self.editable_configurations:
            iface = device_configuration.device_name
            text = (_("Configure device %s") % iface)
            self._container.add(TextWidget(text), callback=self._ensure_connection_and_configure,
                                data=iface)

        self.window.add_with_separator(self._container)

    def _set_hostname_callback(self, dialog):
        self.hostname = dialog.run()
        self.redraw()
        self.apply()

    def _apply_hostname_callback(self):
        self._network_module.SetCurrentHostname(self.hostname)
        self.redraw()
        self.apply()

    def _ensure_connection_and_configure(self, iface):
        for device_configuration in self.editable_configurations:
            if device_configuration.device_name == iface:
                connection_uuid = device_configuration.connection_uuid
                if connection_uuid:
                    self._configure_connection(iface, connection_uuid)
                else:
                    device_type = self.nm_client.get_device_by_iface(iface).get_device_type()
                    connection = get_default_connection(iface, device_type)
                    connection_uuid = connection.get_uuid()
                    log.debug("adding default connection %s for %s", connection_uuid, iface)
                    data = (iface, connection_uuid)
                    self.nm_client.add_connection2(
                        connection.to_dbus(NM.ConnectionSerializationFlags.ALL),
                        (NM.SettingsAddConnection2Flags.TO_DISK |
                         NM.SettingsAddConnection2Flags.BLOCK_AUTOCONNECT),
                        None,
                        False,
                        None,
                        self._default_connection_added_cb,
                        data
                    )
                return
        log.error("device configuration for %s not found", iface)

    def _default_connection_added_cb(self, client, result, data):
        iface, connection_uuid = data
        try:
            _connection, result = client.add_connection2_finish(result)
        except Exception as e:  # pylint: disable=broad-except
            msg = "adding default connection {} from {} failed: {}".format(
                connection_uuid, iface, str(e))
            log.error(msg)
            self.errors.append(msg)
            self.redraw()
        else:
            log.debug("added default connection %s for %s: %s", connection_uuid, iface, result)
            self._configure_connection(iface, connection_uuid)

    def _configure_connection(self, iface, connection_uuid):
        connection = self.nm_client.get_connection_by_uuid(connection_uuid)

        new_spoke = ConfigureDeviceSpoke(self.data, self.storage, self.payload,
                                         self._network_module, iface, connection)
        ScreenHandler.push_screen_modal(new_spoke)

        if new_spoke.errors:
            self.errors.extend(new_spoke.errors)
            self.redraw()
            return

        if new_spoke.apply_configuration:
            self._apply = True

        self._network_module.LogConfigurationState(
            "Settings of {} updated in TUI.".format(iface)
        )

        self.redraw()
        self.apply()

    def input(self, args, key):
        """ Handle the input. """
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            return super().input(args, key)

    def apply(self):
        """Apply all of our settings."""
        # Inform network module that device configurations might have been changed
        # and we want to generate kickstart from device configurations
        # (persistent NM / config files configuration), instead of using original kickstart.
        self._network_module.NetworkDeviceConfigurationChanged()

        (valid, error) = network.is_valid_hostname(self.hostname, local=True)
        if not self.hostname or valid:
            self._network_module.Hostname = self.hostname
        else:
            self.errors.append(_("Host name is not valid: %s") % error)
            self.hostname = self._network_module.Hostname

        if self._apply:
            self._apply = False
            if ANACONDA_ENVIRON in flags.environs:
                from pyanaconda.payload.manager import payloadMgr
                payloadMgr.start(self.payload)


class ConfigureDeviceSpoke(NormalTUISpoke):
    """ Spoke to set various configuration options for net devices. """
    category = "network"

    def __init__(self, data, storage, payload, network_module, iface, connection):
        super().__init__(data, storage, payload)
        self.title = N_("Device configuration")

        self._network_module = network_module
        self._container = None
        self._connection = connection
        self._iface = iface
        self._connection_uuid = connection.get_uuid()
        self.errors = []
        self.apply_configuration = False

        self._data = WiredTUIConfigurationData()
        self._data.set_from_connection(self._connection)

        log.debug("Configure iface %s: connection %s -> %s", self._iface, self._connection_uuid,
                  self._data)

    def refresh(self, args=None):
        """ Refresh window. """
        super().refresh(args)

        self._container = ListColumnContainer(1)

        dialog = Dialog(title=(_('IPv4 address or %s for DHCP') % '"dhcp"'),
                        conditions=[self._check_ipv4_or_dhcp])
        self._container.add(EntryWidget(dialog.title, self._data.ip), self._set_ipv4_or_dhcp, dialog)

        dialog = Dialog(title=_("IPv4 netmask"), conditions=[self._check_netmask])
        self._container.add(EntryWidget(dialog.title, self._data.netmask), self._set_netmask, dialog)

        dialog = Dialog(title=_("IPv4 gateway"), conditions=[self._check_ipv4])
        self._container.add(EntryWidget(dialog.title, self._data.gateway), self._set_ipv4_gateway, dialog)

        msg = (_('IPv6 address[/prefix] or %(auto)s for automatic, %(dhcp)s for DHCP, '
                 '%(ignore)s to turn off')
               % {"auto": '"auto"', "dhcp": '"dhcp"', "ignore": '"ignore"'})
        dialog = Dialog(title=msg, conditions=[self._check_ipv6_config])
        self._container.add(EntryWidget(dialog.title, self._data.ipv6), self._set_ipv6, dialog)

        dialog = Dialog(title=_("IPv6 default gateway"), conditions=[self._check_ipv6])
        self._container.add(EntryWidget(dialog.title, self._data.ipv6gateway), self._set_ipv6_gateway, dialog)

        dialog = Dialog(title=_("Nameservers (comma separated)"), conditions=[self._check_nameservers])
        self._container.add(EntryWidget(dialog.title, self._data.nameserver), self._set_nameservers, dialog)

        msg = _("Connect automatically after reboot")
        w = CheckboxWidget(title=msg, completed=self._data.onboot)
        self._container.add(w, self._set_onboot_handler)

        msg = _("Apply configuration in installer")
        w = CheckboxWidget(title=msg, completed=self.apply_configuration)
        self._container.add(w, self._set_apply_handler)

        self.window.add_with_separator(self._container)

        message = _("Configuring device %s.") % self._iface
        self.window.add_with_separator(TextWidget(message))

    @report_if_failed(message=IP_ERROR_MSG)
    def _check_ipv4_or_dhcp(self, user_input, report_func):
        return IPV4_OR_DHCP_PATTERN_WITH_ANCHORS.match(user_input) is not None

    @report_if_failed(message=IP_ERROR_MSG)
    def _check_ipv4(self, user_input, report_func):
        return IPV4_PATTERN_WITH_ANCHORS.match(user_input) is not None

    @report_if_failed(message=NETMASK_ERROR_MSG)
    def _check_netmask(self, user_input, report_func):
        return IPV4_NETMASK_WITH_ANCHORS.match(user_input) is not None

    @report_if_failed(message=IP_ERROR_MSG)
    def _check_ipv6(self, user_input, report_func):
        return network.check_ip_address(user_input, version=6)

    @report_if_failed(message=IP_ERROR_MSG)
    def _check_ipv6_config(self, user_input, report_func):
        if user_input in ["auto", "dhcp", "ignore"]:
            return True
        addr, _slash, prefix = user_input.partition("/")
        if prefix:
            try:
                if not 1 <= int(prefix) <= 128:
                    return False
            except ValueError:
                return False
        return network.check_ip_address(addr, version=6)

    @report_if_failed(message=IP_ERROR_MSG)
    def _check_nameservers(self, user_input, report_func):
        if user_input.strip():
            addresses = [str.strip(i) for i in user_input.split(",")]
            for ip in addresses:
                if not network.check_ip_address(ip):
                    return False
        return True

    def _set_ipv4_or_dhcp(self, dialog):
        self._data.ip = dialog.run()

    def _set_netmask(self, dialog):
        self._data.netmask = dialog.run()

    def _set_ipv4_gateway(self, dialog):
        self._data.gateway = dialog.run()

    def _set_ipv6(self, dialog):
        self._data.ipv6 = dialog.run()

    def _set_ipv6_gateway(self, dialog):
        self._data.ipv6gateway = dialog.run()

    def _set_nameservers(self, dialog):
        self._data.nameserver = dialog.run()

    def _set_apply_handler(self, args):
        self.apply_configuration = not self.apply_configuration

    def _set_onboot_handler(self, args):
        self._data.onboot = not self._data.onboot

    def input(self, args, key):
        if self._container.process_user_input(key):
            return InputState.PROCESSED_AND_REDRAW
        else:
            if key.lower() == Prompt.CONTINUE:
                if self._data.ip != "dhcp" and not self._data.netmask:
                    self.errors.append(_("Configuration not saved: netmask missing in static configuration"))
                else:
                    self.apply()
                return InputState.PROCESSED_AND_CLOSE
            else:
                return super().input(args, key)

    @property
    def indirect(self):
        return True

    def apply(self):
        """Apply changes to NM connection."""
        log.debug("updating connection %s:\n%s", self._connection_uuid,
                  self._connection.to_dbus(NM.ConnectionSerializationFlags.ALL))

        updated_connection = NM.SimpleConnection.new_clone(self._connection)
        self._data.update_connection(updated_connection)

        # Commit the changes
        self._connection.update2(
            updated_connection.to_dbus(NM.ConnectionSerializationFlags.ALL),
            NM.SettingsUpdate2Flags.TO_DISK | NM.SettingsUpdate2Flags.BLOCK_AUTOCONNECT,
            None,
            None,
            self._connection_updated_cb,
            self._connection_uuid
        )

    def _connection_updated_cb(self, connection, result, connection_uuid):
        connection.update2_finish(result)
        log.debug("updated connection %s:\n%s", connection_uuid,
                  connection.to_dbus(NM.ConnectionSerializationFlags.ALL))
        if self.apply_configuration:
            nm_client = network.get_nm_client()
            device = nm_client.get_device_by_iface(self._iface)
            log.debug("activating connection %s with device %s",
                      connection_uuid, self._iface)
            nm_client.activate_connection_async(connection, device, None, None)


def get_default_connection(iface, device_type):
    """Get default connection to be edited by the UI."""
    connection = NM.SimpleConnection.new()
    s_con = NM.SettingConnection.new()
    s_con.props.uuid = NM.utils_uuid_generate()
    s_con.props.autoconnect = True
    s_con.props.id = iface
    s_con.props.interface_name = iface
    if device_type == NM.DeviceType.ETHERNET:
        s_con.props.type = "802-3-ethernet"
        s_wired = NM.SettingWired.new()
        connection.add_setting(s_wired)
    elif device_type == NM.DeviceType.INFINIBAND:
        s_con.props.type = "infiniband"
        s_ib = NM.SettingInfiniband.new()
        s_ib.props.transport_mode = "datagram"
        connection.add_setting(s_ib)
    connection.add_setting(s_con)
    return connection
