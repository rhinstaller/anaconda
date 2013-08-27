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
from pyanaconda.nm import nm_activated_devices, nm_state, nm_devices, nm_device_type_is_ethernet, nm_device_ip_config, nm_activate_device_connection, nm_device_setting_value

# pylint: disable-msg=E0611
from gi.repository import NetworkManager

import re
IPV4_PATTERN_WITHOUT_ANCHORS=r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'

__all__ = ["NetworkSpoke"]


class NetworkSpoke(EditTUISpoke):
    """ Spoke used to configure network settings. """
    title = _("Network settings")
    category = "network"

    def __init__(self, app, data, storage, payload, instclass):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.hostname_dialog = OneShotEditTUIDialog(app, data, storage, payload, instclass)
        self.hostname_dialog.value = self.data.network.hostname
        self.supported_devices = []
        self.errors = []

    def initialize(self):
        for name in nm_devices():
            if nm_device_type_is_ethernet(name):
                self.supported_devices.append(name)

        EditTUISpoke.initialize(self)
        if not self.data.network.seen:
            self._update_network_data()

    @property
    def completed(self):
        return (not can_touch_runtime_system("require network connection")
                or nm_activated_devices())

    @property
    def status(self):
        """ Short msg telling what devices are active. """
        msg = _("Unknown")

        state = nm_state()
        if state == NetworkManager.State.CONNECTING:
            msg = _("Connecting...")
        elif state == NetworkManager.State.DISCONNECTING:
            msg = _("Disconnecting...")
        else:
            activated_devs = nm_activated_devices()
            if not activated_devs:
                msg = _("Not connected")
            elif len(activated_devs) == 1:
                if nm_device_type_is_ethernet(activated_devs[0]):
                    msg = _("Wired %s connected" % activated_devs[0])
            else:
                devlist = []
                for dev in activated_devs:
                    if nm_device_type_is_ethernet(dev):
                        devlist.append("%s" % dev)
                msg = _("Connected: %(list_of_interface_names)s") \
                      % {"list_of_interface_names": ", ".join(devlist)}

        if not nm_devices():
            msg = _("No network devices available")

        return msg

    def _summary_text(self):
        """Devices cofiguration shown to user."""
        msg = ""
        activated_devs = nm_activated_devices()
        for name in self.supported_devices:
            if name in activated_devs:
                msg += self._activated_device_msg(name)
            else:
                msg += _("Wired (%(interface_name)s) disconnected\n") \
                    % {"interface_name": name}
        return msg

    def _activated_device_msg(self, devname):
        msg = _("Wired (%(interface_name)s) connected\n") \
                % {"interface_name": devname}

        ipv4config = nm_device_ip_config(devname, version=4)
        ipv6config = nm_device_ip_config(devname, version=6)

        if ipv4config and ipv4config[0]:
            addr_str, prefix, gateway_str = ipv4config[0][0]
            netmask_str = network.prefix2netmask(prefix)
            dnss_str = ",".join(ipv4config[1])
        else:
            addr_str = dnss_str = gateway_str = netmask_str = ""
        msg += _(" IPv4 Address: %s Netmask: %s Gateway: %s\n") % (addr_str, netmask_str, gateway_str)
        msg += _(" DNS: %s\n") % dnss_str

        if ipv6config and ipv6config[0]:
            for ipv6addr in ipv6config[0]:
                addr_str, prefix, gateway_str = ipv6addr
                # Do not display link-local addresses
                if not addr_str.startswith("fe80:"):
                    msg += _(" IPv6 Address: %s/%d\n") % (addr_str, prefix)

            dnss_str = ",".join(ipv6config[1])

        return msg

    def refresh(self, args=None):
        """ Refresh screen. """
        EditTUISpoke.refresh(self, args)

        # on refresh check if we haven't got hostname from NM on activated
        # connection (dhcp or DNS)
        if self.hostname_dialog.value == network.DEFAULT_HOSTNAME:
            hostname = network.getHostname()
            network.update_hostname_data(self.data, hostname)
            self.hostname_dialog.value = self.data.network.hostname

        summary = self._summary_text()
        self._window += [TextWidget(summary), ""]
        hostname = _("Hostname: %s\n") % self.data.network.hostname
        self._window += [TextWidget(hostname), ""]

        # if we have any errors, display them
        while len(self.errors) > 0:
            self._window += [TextWidget(self.errors.pop()), ""]

        def _prep(i, w):
            """ Mangle our text to make it look pretty on screen. """
            number = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        _opts = [_("Set hostname")]
        for devname in self.supported_devices:
            _opts.append(_("Configure device %s") % devname)
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
        except ValueError:
            return key

        if num == 1:
            # set hostname
            self.app.switch_screen_modal(self.hostname_dialog, Entry(_("Hostname"),
                                "hostname", re.compile(".*$"), True))
            self.apply()
            return True
        elif 2 <= num <= len(self.supported_devices) + 1:
            # configure device
            devname = self.supported_devices[num-2]
            ndata = network.get_ks_network_data(devname)
            newspoke = ConfigureNetworkSpoke(self.app, self.data, self.storage,
                                    self.payload, self.instclass, ndata)
            self.app.switch_screen_modal(newspoke)

            if ndata.ip == "dhcp":
                ndata.bootProto = "dhcp"
                ndata.ip = ""
            else:
                ndata.bootProto = "static"
                if not ndata.gateway or not ndata.netmask:
                    self.errors.append(_("Configuration not saved: gateway or netmask missing in static configuration"))
                    return True

            if ndata.ipv6 == "ignore":
                ndata.noipv6 = True
                ndata.ipv6 = ""
            else:
                ndata.noipv6 = False

            network.update_settings_with_ksdata(devname, ndata)

            if ndata._apply:
                uuid = nm_device_setting_value(devname, "connection", "uuid")
                nm_activate_device_connection(devname, uuid)

            self.apply()
            return True
        else:
            return key

    def apply(self):
        " Apply all of our settings."""
        self._update_network_data()

    def _update_network_data(self):
        hostname = self.data.network.hostname

        self.data.network.network = []
        for name in self.supported_devices:
            network_data = network.get_ks_network_data(name)
            if network_data is not None:
                self.data.network.network.append(network_data)

        (valid, error) = network.sanityCheckHostname(self.hostname_dialog.value)
        if valid:
            hostname = self.hostname_dialog.value
        else:
            self.errors.append(_("Hostname is not valid: %s") % error)
            self.hostname_dialog.value = hostname
        network.update_hostname_data(self.data, hostname)

class ConfigureNetworkSpoke(EditTUISpoke):
    """ Spoke to set various configuration options for net devices. """
    title = _("Device configuration")
    category = "network"

    edit_fields = [
        Entry(_('IPv4 address or %s for DHCP' % '"dhcp"'), "ip",
              re.compile("^" + IPV4_PATTERN_WITHOUT_ANCHORS + "|dhcp$"), True),
        Entry(_("IPv4 netmask"), "netmask", re.compile("^" + IPV4_PATTERN_WITHOUT_ANCHORS + "$"), True),
        Entry(_("IPv4 gateway"), "gateway", re.compile("^" + IPV4_PATTERN_WITHOUT_ANCHORS + "$"), True),
        Entry(_('IPv6 address or %s for automatic, %s for DHCP, %s to turn off') % ('"auto"', '"dhcp"', '"ignore"'), "ipv6", re.compile(".*:|^auto$|^ignore$|^dhcp$"), True),
        Entry(_("IPv6 default gateway"), "ipv6gateway", re.compile(".*$"), True),
        Entry(_("Nameservers (comma separated)"), "nameserver", re.compile(".*$"), True),
        Entry(_("Connect automatically after reboot"), "onboot", EditTUISpoke.CHECK, True),
        Entry(_("Apply configuration in installer"), "_apply", EditTUISpoke.CHECK, True),
    ]

    def __init__(self, app, data, storage, payload, instclass, ndata):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.args = ndata
        if self.args.bootProto == "dhcp":
            self.args.ip = "dhcp"
        if self.args.noipv6:
            self.args.ipv6 = "ignore"
        self.args._apply = False

    def refresh(self, args=None):
        """ Refresh window. """
        EditTUISpoke.refresh(self, args)
        message = _("Configuring device %s." % self.args.device)
        self._window += [TextWidget(message), ""]
        return True

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply our changes. """
        # this is done at upper level by updating ifcfg file
