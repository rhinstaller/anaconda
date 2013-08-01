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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Samantha N. Bueno <sbueno@redhat.com>,
#                    Radek Vykydal <rvykydal@redhat.com>
#

from pyanaconda.flags import can_touch_runtime_system
from pyanaconda.ui.tui.spokes import EditTUISpoke, OneShotEditTUIDialog
from pyanaconda.ui.tui.spokes import EditTUISpokeEntry as Entry
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget
from pyanaconda.i18n import _
from pyanaconda import network
from pyanaconda.nm import nm_activated_devices, nm_is_connecting

# pylint: disable-msg=E0611
from gi.repository import GLib, NetworkManager, NMClient
import dbus
import socket
import struct

import ctypes
ctypes.cdll.LoadLibrary("libnm-util.so.2")
nm_utils = ctypes.CDLL("libnm-util.so.2")

import re
import logging
LOG = logging.getLogger("anaconda")


# These are required for dbus API use we need because of
# NM_GI_BUGS: 767998, 773678
NM_SERVICE = "org.freedesktop.NetworkManager"
NM_802_11_AP_FLAGS_PRIVACY = 0x1
NM_802_11_AP_SEC_NONE = 0x0
NM_802_11_AP_SEC_KEY_MGMT_802_1X = 0x200
DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"


__all__ = ["NetworkSpoke"]


class NetworkSpoke(EditTUISpoke):
    """ Spoke used to configure network settings. """
    title = _("Network settings")
    category = "network"

    def __init__(self, app, data, storage, payload, instclass):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.hostname = OneShotEditTUIDialog(app, data, storage, payload, instclass)
        self.devices = []
        self.errors = []
        # NM Client stuff
        self.client = NMClient.Client.new()
        self.selected = None
        self.cfg = {}

    def initialize(self):
        EditTUISpoke.initialize(self)
        if not self.data.network.seen:
            self._update_network_data()
            # if we have a network device available, go ahead and default to
            # selecting the first device in the list
            if len(self.activated_connections()) > 0:
                self.selected = self.activated_connections()[0]

    @property
    def completed(self):
        return (not can_touch_runtime_system("require network connection")
                or self.activated_connections())

    @property
    def status(self):
        """ Short msg telling what devices are active. """
        msg = _("Unknown")

        state = nm_is_connecting()
        if state == NetworkManager.State.CONNECTING:
            msg = _("Connecting...")
        elif state == NetworkManager.State.DISCONNECTING:
            msg = _("Disconnecting...")
        else:
            cons = self.activated_connections()
            if cons:
                if len(cons) == 1:
                    name, tipe, dev = cons[0]
                    if tipe == NetworkManager.DeviceType.ETHERNET:
                        msg = _("Wired %s connected" % name)
            else:
                msg = _("Not connected")

        if len(self.activated_connections()) == 0:
            msg = _("No network devices available")

        return msg

    def getNMObjProperty(self, obj, nm_iface_suffix, prop):
        """ Get property of NM object. """
        props_iface = dbus.Interface(obj, DBUS_PROPS_IFACE)
        return props_iface.Get("org.freedesktop.NetworkManager"+nm_iface_suffix, prop)

    def activated_connections(self):
        """ Returns list of tuples with info about active devices. """
        active_devs = []

        for con in self.client.get_active_connections():
            if con.get_state() != NetworkManager.ActiveConnectionState.ACTIVATED:
                continue
            dev = con.get_devices()[0]
            dev_type, dev_name = dev.get_device_type(), None
            if dev_type == NetworkManager.DeviceType.ETHERNET:
                dev_name = dev.get_iface()
            if dev_name and (dev_type == NetworkManager.DeviceType.ETHERNET):
                # only allowing wired connections in TUI
                # too much of a pain to add all the config options to make
                # wifi, etc. available
                active_devs.append((dev_name, dev_type, dev))
        return active_devs

    def _update_summary(self):
        """ Update summary screen with current dev info and hostname. """
        msg = ""
        dev = self.selected

        if not self.activated_connections():
            msg = _("No network devices available.")

        if dev:
            name, tipe, device = dev
            # grab our dev configuration settings
            if self.data.network.network:
                _data = self.data.network.network[0]
                if _data.bootProto == "dhcp":
                    # only call this function if we're using dhcp.
                    # since we do not interface with network manager when
                    # devices are manually configured, _refresh_device_cfg
                    # will obliterate our settings
                    self._refresh_device_cfg(device, 3, device.get_state())
                else:
                    self._set_device_info_value("subnet", "Netmask", _data.netmask)
                    self._set_device_info_value("route", "Gateway", _data.gateway)
                    self._set_device_info_value("dns", "DNS", _data.nameserver)
                    if _data.ip and _data.ipv6:
                        self._set_device_info_value("ipv4", "IPv4 Address", _data.ip)
                        self._set_device_info_value("ipv6", "IPv6 Address", _data.ipv6)
                    elif _data.ip:
                        self._set_device_info_value("ipv4", "IP Address", _data.ip)
                    elif _data.ipv6:
                        self._set_device_info_value("ipv6", "IP Address", _data.ipv6)

            if tipe == NetworkManager.DeviceType.ETHERNET:
                msg = _("Wired (%(interface_name)s) connected\n") \
                    % {"interface_name": name}
            # update the display message with config settings
            for i in self.cfg:
                msg += _("%s: %s\n" % (self.cfg[i][0], self.cfg[i][1]))

            # make sure to display the hostname as well
            if self.hostname.value:
                msg += _("\nHostname: %s") % self.hostname.value

        return msg

    def _refresh_device_cfg(self, dev, num_of_tries, state):
        """ Refresh the device configuration. """
        ipv4cfg = None
        ipv6cfg = None

        if num_of_tries > 0:
            ipv4cfg = dev.get_ip4_config()
            ipv6cfg = dev.get_ip6_config()
            if not ipv4cfg and not ipv6cfg:
                GLib.timeout_add(300, self._refresh_device_cfg, dev, num_of_tries-1, state)
                return False

        if state is None:
            state = dev.get_state()
        if (ipv4cfg and state == NetworkManager.DeviceState.ACTIVATED):
            addr = socket.inet_ntoa(struct.pack('=L',
                                                ipv4cfg.get_addresses()[0].get_address()))
            dnss = " ".join(socket.inet_ntoa(struct.pack('=L', addr))
                            for addr in ipv4cfg.get_nameservers())
            self._set_device_info_value("dns", "DNS", dnss)
            gateway = socket.inet_ntoa(struct.pack('=L',
                                       ipv4cfg.get_addresses()[0].get_gateway()))
            self._set_device_info_value("route", "Gateway", gateway)
            prefix = ipv4cfg.get_addresses()[0].get_prefix()
            nm_utils.nm_utils_ip4_prefix_to_netmask.argtypes = [ctypes.c_uint32]
            nm_utils.nm_utils_ip4_prefix_to_netmask.restype = ctypes.c_uint32
            netmask = nm_utils.nm_utils_ip4_prefix_to_netmask(prefix)
            netmask = socket.inet_ntoa(struct.pack('=L', netmask))
            self._set_device_info_value("subnet", "Netmask", netmask)
        else:
            self._set_device_info_value("ipv4", "IPv4 Address", None)
            self._set_device_info_value("subnet", "Netmask", None)
            self._set_device_info_value("route", "Gateway", None)
            self._set_device_info_value("dns", "DNS", None)

        # TODO NM_GI_BUGS - segfaults on get_addres(), get_prefix()
        ipv6_addr = None
        if (ipv6cfg and state == NetworkManager.DeviceState.ACTIVATED):
            config = dbus.SystemBus().get_object(NM_SERVICE, ipv6cfg.get_path())
            addr, prefix, gateway = self.getNMObjProperty(config, ".IP6Config",
                                                        "Addresses")[0]
            ipv6_addr = socket.inet_ntop(socket.AF_INET6, "".join(chr(byte) for byte in addr))

        if ipv4cfg and ipv6_addr:
            self._set_device_info_value("ipv4", "IPv4 Address", addr)
            self._set_device_info_value("ipv6", "IPv6 Address", ipv6_addr)
        elif ipv4cfg:
            self._set_device_info_value("ipv4", "IP Address", addr)
        elif ipv6_addr:
            self._set_device_info_value("ipv6", "IP Address", ipv6_addr)

        return False

    def _set_device_info_value(self, key, desc_str, value_str):
        """ Set info about a network device; this is stored in a dict. """
        self.cfg[key] = [desc_str, value_str]

    def refresh(self, args=None):
        """ Refresh screen. """
        EditTUISpoke.refresh(self, args)

        summary = self._update_summary()
        self._window += [TextWidget(summary), ""]

        # if we have any errors, display them
        while len(self.errors) > 0:
            self._window += [TextWidget(self.errors.pop()), ""]

        def _prep(i, w):
            """ Mangle our text to make it look pretty on screen. """
            number = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        _opts = [_("Set hostname"), _("Configure network")]
        _protocols = [_("IPv4"), _("IPv6")]
        if args == 2:
            # user's chosen 'configure network' from _opts
            text = [TextWidget(p) for p in _protocols]
        else:
            text = [TextWidget(o) for o in _opts]

        # make everything presentable on screen
        choices = [_prep(i, w) for i, w in enumerate(text)]
        displayed = ColumnWidget([(78, choices)], 1)
        self._window.append(displayed)

        return True

    def input(self, args, key):
        """ Handle the input. """
        try:
            num = int(key)
            if args == 2:
                # configure network
                if num:
                    # 'num' is the IP protocol they wish to configure, ipv4 or
                    # ipv6 pass this option to the configuration spoke so it
                    # knows which options to display to the user
                    newspoke = ConfigureNetworkSpoke(self.app, self.data, self.storage,
                                            self.payload, self.instclass, num)
                    self.app.switch_screen_modal(newspoke)
                    self.apply()
                    return True
            else:
                if num == 1:
                    # set hostname
                    self.app.switch_screen_modal(self.hostname, Entry(_("Hostname"),
                                        "hostname", re.compile(".*$"), True))
                    self.apply()
                    return True
                else:
                    self.app.switch_screen(self, num)
            return None
        except (ValueError, IndexError):
            return key

    def apply(self):
        " Apply all of our settings. """
        # first update the network data in case any changes have been made
        self._update_network_data()
        # then make sure to update the summary so users can see any changes
        self._update_summary()

    def _update_hostname(self):
        """ Update hostname value. """
        if not self.hostname.value:
            # set it to the default value
            self.hostname.value = network.DEFAULT_HOSTNAME

        # if we are set to the default value, try and make a guess as to what
        # the hostname should be
        if self.hostname.value == network.DEFAULT_HOSTNAME:
            hostname = network.getHostname()
            network.update_hostname_data(self.data, hostname)

        # run sanity check on hostname
        (valid, error) = network.sanityCheckHostname(self.hostname.value)
        if not valid:
            self.errors.append(_("Hostname is not valid: %s") % error)
            # set hostname value back to default if sanity check fails
            self.hostname.value = network.DEFAULT_HOSTNAME
        else:
            # if our hostname is valid, go ahead and update network settings
            network.update_hostname_data(self.data, self.hostname.value)

    def _update_network_data(self):
        """ Update all of the network data. """
        # the reason for not setting self.network.network.data = []
        # here as in the GUI is because there may be values stored
        # from manual network configuration, and we don't want to
        # blow them all away until setting the values in the ifcfg file(s)
        _data = []

        for con in self.activated_connections():
            (name, tipe, dev) = con
            network_data = self.getKSNetworkData(dev)
            if network_data is not None:
                _data.append(network_data)
        self.data.network.network = _data

        self._update_hostname()

    def getKSNetworkData(self, device):
        """ Get network data. """
        retval = None

        ifcfg_suffix = None
        if device.get_device_type() == NetworkManager.DeviceType.ETHERNET:
            ifcfg_suffix = device.get_iface()

        if ifcfg_suffix:
            ifcfg_suffix = ifcfg_suffix.replace(' ', '_')
            device_cfg = network.NetworkDevice(network.netscriptsDir, ifcfg_suffix)
            try:
                device_cfg.loadIfcfgFile()
                # if we have a device cfg file and have set custom config opts
                # apply them here ....unfortunately the network manager cli
                # tool with the ability to configure networking is not yet
                # available. when it is, this needs to get stripped since it's
                # really, really ugly
                if self.data.network.network:
                    _data = self.data.network.network[0]
                    if _data.ip:
                        device_cfg.set(('IPADDR', _data.ip))
                    if _data.netmask:
                        device_cfg.set(('BOOTPROTO', "static"))
                        device_cfg.set(('NETMASK', _data.netmask))
                    if _data.gateway:
                        device_cfg.set(('GATEWAY', _data.gateway))
                    if _data.nameserver:
                        device_cfg.set(('DNS', _data.nameserver))
                    if _data.ipv6:
                        device_cfg.set(('IPV6ADDR', _data.ipv6))
                        device_cfg.set(('NETWORKING_IPV6', "yes"))
                    if _data.ipv6gateway:
                        device_cfg.set(('IPV6_DEFAULTGW', _data.ipv6gateway))
                    # if we set any values above, we need to rewrite the cfg.
                    device_cfg.writeIfcfgFile()

            except IOError as err:
                LOG.debug("getKSNetworkData %s: %s" % (ifcfg_suffix, err))
                return None
            retval = network.kickstartNetworkData(ifcfg=device_cfg)
            if retval and device.get_iface() in nm_activated_devices():
                retval.activate = True

        return retval


class ConfigureNetworkSpoke(EditTUISpoke):
    """ Spoke to set various configuration options for net devices. """
    title = _("Network settings")
    category = "network"

    edit_fields = [
        Entry(_("IPv4 Address"), "ip", re.compile(".*$"), lambda self, args: self.proto == 1),
        Entry(_("Netmask"), "netmask", re.compile(".*$"), True),
        Entry(_("Gateway"), "gateway", re.compile(".*$"), lambda self, args: self.proto == 1),
        Entry(_("DNS"), "nameserver", re.compile(".*$"), True),
        Entry(_("IPv6 Address"), "ipv6", re.compile(".*$"), lambda self, args: self.proto == 2),
        Entry(_("Gateway"), "ipv6gateway", re.compile(".*$"), lambda self, args: self.proto == 2)
    ]

    def __init__(self, app, data, storage, payload, instclass, proto):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.proto = proto
        if self.data.network:
            self.args = self.data.network.network[0]
        else:
            self.args = self.data.NetworkData()

    def refresh(self, args=None):
        """ Refresh window. """
        return EditTUISpoke.refresh(self, args)

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply our changes. """
        # set this one manually, apply in parent spoke takes care of the rest
        if self.args.ip or self.args.ipv6:
            self.args.bootProto = "static"
