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


from pyanaconda.flags import can_touch_runtime_system, flags
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.tui.spokes import EditTUISpoke, OneShotEditTUIDialog
from pyanaconda.ui.tui.spokes import EditTUISpokeEntry as Entry
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.i18n import N_, _
from pyanaconda import network
from pyanaconda import nm

from pyanaconda.regexes import IPV4_PATTERN_WITHOUT_ANCHORS, IPV4_NETMASK_WITHOUT_ANCHORS
from pyanaconda.constants_text import INPUT_PROCESSED
from pyanaconda.constants import ANACONDA_ENVIRON

import logging
log = logging.getLogger("anaconda")

import re

__all__ = ["NetworkSpoke"]


class NetworkSpoke(FirstbootSpokeMixIn, EditTUISpoke):
    """ Spoke used to configure network settings.

       .. inheritance-diagram:: NetworkSpoke
          :parts: 3
    """
    title = N_("Network configuration")
    category = SystemCategory

    def __init__(self, app, data, storage, payload, instclass):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.hostname_dialog = OneShotEditTUIDialog(app, data, storage, payload, instclass)
        self.hostname_dialog.value = self.data.network.hostname
        self.supported_devices = []
        self.errors = []
        self._apply = False

    def initialize(self):
        self._load_new_devices()

        EditTUISpoke.initialize(self)
        if not self.data.network.seen:
            self._update_network_data()

    def _load_new_devices(self):
        devices = nm.nm_devices()
        intf_dumped = network.dumpMissingDefaultIfcfgs()
        if intf_dumped:
            log.debug("Dumped interfaces: %s", intf_dumped)

        for name in devices:
            if name in self.supported_devices:
                continue
            if network.is_ibft_configured_device(name):
                continue
            if nm.nm_device_type_is_ethernet(name):
                # ignore slaves
                if nm.nm_device_setting_value(name, "connection", "slave-type"):
                    continue
                self.supported_devices.append(name)

    @property
    def completed(self):
        """ Check whether this spoke is complete or not. Do an additional
            check if we're installing from CD/DVD, since a network connection
            should not be required in this case.
        """
        return (not can_touch_runtime_system("require network connection")
                or nm.nm_activated_devices())

    @property
    def mandatory(self):
        # the network spoke should be mandatory only if it is running
        # during the installation and if the installation source requires network
        return ANACONDA_ENVIRON in flags.environs and self.payload.needsNetwork

    @property
    def status(self):
        """ Short msg telling what devices are active. """
        return network.status_message()

    def _summary_text(self):
        """Devices cofiguration shown to user."""
        msg = ""
        activated_devs = nm.nm_activated_devices()
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

        ipv4config = nm.nm_device_ip_config(devname, version=4)
        ipv6config = nm.nm_device_ip_config(devname, version=6)

        if ipv4config and ipv4config[0]:
            addr_str, prefix, gateway_str = ipv4config[0][0]
            netmask_str = network.prefix2netmask(prefix)
            dnss_str = ",".join(ipv4config[1])
        else:
            addr_str = dnss_str = gateway_str = netmask_str = ""
        msg += _(" IPv4 Address: %(addr)s Netmask: %(netmask)s Gateway: %(gateway)s\n") % \
                {"addr": addr_str, "netmask": netmask_str, "gateway": gateway_str}
        msg += _(" DNS: %s\n") % dnss_str

        if ipv6config and ipv6config[0]:
            for ipv6addr in ipv6config[0]:
                addr_str, prefix, gateway_str = ipv6addr
                # Do not display link-local addresses
                if not addr_str.startswith("fe80:"):
                    msg += _(" IPv6 Address: %(addr)s/%(prefix)d\n") % \
                            {"addr": addr_str, "prefix": prefix}

            dnss_str = ",".join(ipv6config[1])

        return msg

    def refresh(self, args=None):
        """ Refresh screen. """
        self._load_new_devices()
        EditTUISpoke.refresh(self, args)

        summary = self._summary_text()
        self._window += [TextWidget(summary), ""]
        hostname = _("Host Name: %s\n") % self.data.network.hostname
        self._window += [TextWidget(hostname), ""]
        current_hostname = _("Current host name: %s\n") % network.current_hostname()
        self._window += [TextWidget(current_hostname), ""]

        # if we have any errors, display them
        while len(self.errors) > 0:
            self._window += [TextWidget(self.errors.pop()), ""]

        def _prep(i, w):
            """ Mangle our text to make it look pretty on screen. """
            number = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        _opts = [_("Set host name")]
        for devname in self.supported_devices:
            _opts.append(_("Configure device %s") % devname)
        text = [TextWidget(o) for o in _opts]

        # make everything presentable on screen
        choices = [_prep(i, w) for i, w in enumerate(text)]
        displayed = ColumnWidget([(78, choices)], 1)
        self._window += [displayed, ""]

        return True

    def input(self, args, key):
        """ Handle the input. """
        try:
            num = int(key)
        except ValueError:
            return key

        if num == 1:
            # set hostname
            self.app.switch_screen_modal(self.hostname_dialog, Entry(_("Host Name"),
                                "hostname", re.compile(".*$"), True))
            self.apply()
            return INPUT_PROCESSED
        elif 2 <= num <= len(self.supported_devices) + 1:
            # configure device
            devname = self.supported_devices[num-2]
            ndata = network.ksdata_from_ifcfg(devname)
            if not ndata:
                try:
                    nm.nm_device_setting_value(devname, "connection", "uuid")
                except nm.SettingsNotFoundError:
                    pass
                else:
                    log.debug("network: dumping ifcfg file for in-memory connection %s", devname)
                    nm.nm_update_settings_of_device(devname, [['connection', 'id', devname, None]])
                    ndata = network.ksdata_from_ifcfg(devname)

            if not ndata:
                log.debug("network: can't find any connection for %s", devname)
                self.errors.append(_("Configuration of device not found"))
                return INPUT_PROCESSED

            newspoke = ConfigureNetworkSpoke(self.app, self.data, self.storage,
                                    self.payload, self.instclass, ndata)
            self.app.switch_screen_modal(newspoke)

            if ndata.ip == "dhcp":
                ndata.bootProto = "dhcp"
                ndata.ip = ""
            else:
                ndata.bootProto = "static"
                if not ndata.netmask:
                    self.errors.append(_("Configuration not saved: netmask missing in static configuration"))
                    return INPUT_PROCESSED

            if ndata.ipv6 == "ignore":
                ndata.noipv6 = True
                ndata.ipv6 = ""
            else:
                ndata.noipv6 = False

            network.update_settings_with_ksdata(devname, ndata)
            network.update_onboot_value(devname, ndata.onboot, ksdata=None, root_path="")

            if ndata._apply:
                self._apply = True
                uuid = nm.nm_device_setting_value(devname, "connection", "uuid")
                try:
                    nm.nm_activate_device_connection(devname, uuid)
                except (nm.UnmanagedDeviceError, nm.UnknownConnectionError):
                    self.errors.append(_("Can't apply configuration, device activation failed."))

            self.apply()
            return INPUT_PROCESSED
        else:
            return key

    def apply(self):
        """Apply all of our settings."""
        self._update_network_data()
        log.debug("network: apply ksdata %s", self.data.network)

        if self._apply:
            self._apply = False
            if ANACONDA_ENVIRON in flags.environs:
                from pyanaconda.packaging import payloadMgr
                payloadMgr.restartThread(self.storage, self.data, self.payload,
                                         self.instclass, checkmount=False)

    def _update_network_data(self):
        hostname = self.data.network.hostname

        self.data.network.network = []
        for i, name in enumerate(nm.nm_devices()):
            if network.is_ibft_configured_device(name):
                continue
            nd = network.ksdata_from_ifcfg(name)
            if not nd:
                continue
            if name in nm.nm_activated_devices():
                nd.activate = True
            else:
                # First network command defaults to --activate so we must
                # use --no-activate explicitly to prevent the default
                if i == 0:
                    nd.activate = False
            self.data.network.network.append(nd)

        (valid, error) = network.sanityCheckHostname(self.hostname_dialog.value)
        if valid:
            hostname = self.hostname_dialog.value
        else:
            self.errors.append(_("Host name is not valid: %s") % error)
            self.hostname_dialog.value = hostname
        network.update_hostname_data(self.data, hostname)

def check_ipv6_config(value):
    if value in ["auto", "dhcp", "ignore"]:
        return (True, None)
    addr, _slash, prefix = value.partition("/")
    if prefix:
        try:
            if not 1 <= int(prefix) <= 128:
                return (False, None)
        except ValueError:
            return (False, None)
    return check_ipv6_address(addr)

def check_ipv6_address(value):
    return (network.check_ip_address(value, version=6), None)

def check_nameservers(value):
    addresses = [str.strip(i) for i in value.split(",")]
    if not addresses:
        return (False, None)

    for ip in addresses:
        if not network.check_ip_address(ip):
            return (False, None)
    return (True, None)

class ConfigureNetworkSpoke(EditTUISpoke):
    """ Spoke to set various configuration options for net devices. """
    title = N_("Device configuration")
    category = "network"

    edit_fields = [
        Entry(N_('IPv4 address or %s for DHCP') % '"dhcp"', "ip",
              re.compile("^(?:" + IPV4_PATTERN_WITHOUT_ANCHORS + "|dhcp)$"), True),
        Entry(N_("IPv4 netmask"), "netmask", re.compile("^" + IPV4_NETMASK_WITHOUT_ANCHORS + "$"), True),
        Entry(N_("IPv4 gateway"), "gateway", re.compile("^" + IPV4_PATTERN_WITHOUT_ANCHORS + "$"), True),
        Entry(N_('IPv6 address[/prefix] or %(auto)s for automatic, %(dhcp)s for DHCP, %(ignore)s to turn off')
              % {"auto": '"auto"', "dhcp": '"dhcp"', "ignore": '"ignore"'}, "ipv6",
              check_ipv6_config, True),
        Entry(N_("IPv6 default gateway"), "ipv6gateway", check_ipv6_address, True),
        Entry(N_("Nameservers (comma separated)"), "nameserver", check_nameservers, True),
        Entry(N_("Connect automatically after reboot"), "onboot", EditTUISpoke.CHECK, True),
        Entry(N_("Apply configuration in installer"), "_apply", EditTUISpoke.CHECK, True),
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
        message = _("Configuring device %s.") % self.args.device
        self._window += [TextWidget(message), ""]
        return True

    def input(self, args, key):
        self.dialog.wrong_input_message = _("Bad format of the IP address")
        try:
            field = self.visible_fields[int(key)-1]
        except (ValueError, IndexError):
            pass
        else:
            if field.attribute == "netmask":
                self.dialog.wrong_input_message = _("Bad format of the netmask")
        return EditTUISpoke.input(self, args, key)

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply our changes. """
        # this is done at upper level by updating ifcfg file
