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

from pyanaconda import network
from pyanaconda import nm
from pyanaconda.flags import can_touch_runtime_system, flags
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import Dialog, report_if_failed
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.i18n import N_, _

from pyanaconda.regexes import IPV4_PATTERN_WITH_ANCHORS, IPV4_NETMASK_WITH_ANCHORS, IPV4_OR_DHCP_PATTERN_WITH_ANCHORS
from pyanaconda.constants import ANACONDA_ENVIRON

from pyanaconda.anaconda_loggers import get_module_logger

from simpleline.render.containers import ListColumnContainer
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget, CheckboxWidget, EntryWidget

log = get_module_logger(__name__)

# This will be used in decorators in ConfigureNetworkSpoke.
# The decorators are processed before the class is created so you can have this as a variable there.
IP_ERROR_MSG = N_("Bad format of the IP address")
NETMASK_ERROR_MSG = N_("Bad format of the netmask")

__all__ = ["NetworkSpoke"]


class NetworkSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    """ Spoke used to configure network settings.

       .. inheritance-diagram:: NetworkSpoke
          :parts: 3
    """
    helpFile = "NetworkSpoke.txt"
    category = SystemCategory

    def __init__(self, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, data, storage, payload, instclass)
        self.title = N_("Network configuration")
        self._container = None
        self._value = self.data.network.hostname
        self.supported_devices = []
        self.errors = []
        self._apply = False

    def initialize(self):
        self.initialize_start()
        self._load_new_devices()

        NormalTUISpoke.initialize(self)
        if not self.data.network.seen:
            self._update_network_data()
        self.initialize_done()

    def _load_new_devices(self):
        devices = nm.nm_devices()
        intf_dumped = network.dumpMissingDefaultIfcfgs()
        if intf_dumped:
            log.debug("dumped interfaces: %s", intf_dumped)

        for name in devices:
            if name in self.supported_devices:
                continue
            if network.is_ibft_configured_device(name):
                continue
            if network.device_type_is_supported_wired(name):
                # ignore slaves
                try:
                    if nm.nm_device_setting_value(name, "connection", "slave-type"):
                        continue
                except nm.MultipleSettingsFoundError as e:
                    log.debug("%s during initialization", e)
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

        return msg

    def refresh(self, args=None):
        """ Refresh screen. """
        self._load_new_devices()
        NormalTUISpoke.refresh(self, args)

        self._container = ListColumnContainer(1, columns_width=78, spacing=1)

        summary = self._summary_text()
        self.window.add_with_separator(TextWidget(summary))
        hostname = _("Host Name: %s\n") % self.data.network.hostname
        self.window.add_with_separator(TextWidget(hostname))
        current_hostname = _("Current host name: %s\n") % network.current_hostname()
        self.window.add_with_separator(TextWidget(current_hostname))

        # if we have any errors, display them
        while len(self.errors) > 0:
            self.window.add_with_separator(TextWidget(self.errors.pop()))

        dialog = Dialog(_("Host Name"))
        self._container.add(TextWidget(_("Set host name")), callback=self._set_hostname_callback, data=dialog)

        for dev_name in self.supported_devices:
            text = (_("Configure device %s") % dev_name)
            self._container.add(TextWidget(text), callback=self._configure_network_interface, data=dev_name)

        self.window.add_with_separator(self._container)

    def _set_hostname_callback(self, dialog):
        # set hostname
        self._value = dialog.run()
        self.redraw()
        self.apply()

    def _configure_network_interface(self, data):
        devname = data
        ndata = network.ksdata_from_ifcfg(devname)
        if not ndata:
            # There is no ifcfg file for the device.
            # Make sure there is just one connection for the device.
            try:
                nm.nm_device_setting_value(devname, "connection", "uuid")
            except nm.SettingsNotFoundError:
                log.debug("can't find any connection for %s", devname)
                return
            except nm.MultipleSettingsFoundError:
                log.debug("multiple non-ifcfg connections found for %s", devname)
                return

            log.debug("dumping ifcfg file for in-memory connection %s", devname)
            nm.nm_update_settings_of_device(devname, [['connection', 'id', devname, None]])
            ndata = network.ksdata_from_ifcfg(devname)

        new_spoke = ConfigureNetworkSpoke(self.data, self.storage,
                                          self.payload, self.instclass, ndata)
        ScreenHandler.push_screen_modal(new_spoke)
        self.redraw()

        if ndata.ip == "dhcp":
            ndata.bootProto = "dhcp"
            ndata.ip = ""
        else:
            ndata.bootProto = "static"
            if not ndata.netmask:
                self.errors.append(_("Configuration not saved: netmask missing in static configuration"))
                return

        if ndata.ipv6 == "ignore":
            ndata.noipv6 = True
            ndata.ipv6 = ""
        else:
            ndata.noipv6 = False

        uuid = network.update_settings_with_ksdata(devname, ndata)
        network.update_onboot_value(devname, ndata.onboot, ksdata=None, root_path="")
        network.logIfcfgFiles("settings of %s updated in tui" % devname)

        if new_spoke.apply_configuration:
            self._apply = True
            try:
                nm.nm_activate_device_connection(devname, uuid)
            except (nm.UnmanagedDeviceError, nm.UnknownConnectionError):
                self.errors.append(_("Can't apply configuration, device activation failed."))

        self.apply()

    def input(self, args, key):
        """ Handle the input. """
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            return super(NetworkSpoke, self).input(args, key)

    def apply(self):
        """Apply all of our settings."""
        self._update_network_data()
        log.debug("apply ksdata %s", self.data.network)

        if self._apply:
            self._apply = False
            if ANACONDA_ENVIRON in flags.environs:
                from pyanaconda.payload import payloadMgr
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

        (valid, error) = network.sanityCheckHostname(self._value)
        if valid:
            hostname = self._value
        else:
            self.errors.append(_("Host name is not valid: %s") % error)
            self._value = hostname
        network.update_hostname_data(self.data, hostname)


class ConfigureNetworkSpoke(NormalTUISpoke):
    """ Spoke to set various configuration options for net devices. """
    category = "network"

    def __init__(self, data, storage, payload, instclass, network_data):
        super().__init__(data, storage, payload, instclass)
        self.title = N_("Device configuration")

        self.network_data = network_data
        if self.network_data.bootProto == "dhcp":
            self.network_data.ip = "dhcp"
        if self.network_data.noipv6:
            self.network_data.ipv6 = "ignore"

        self.apply_configuration = False
        self._container = None

    def refresh(self, args=None):
        """ Refresh window. """
        super().refresh(args)

        self._container = ListColumnContainer(1)

        dialog = Dialog(title=(_('IPv4 address or %s for DHCP') % '"dhcp"'),
                        conditions=[self._check_ipv4_or_dhcp])
        self._container.add(EntryWidget(dialog.title, self.network_data.ip), self._set_ipv4_or_dhcp, dialog)

        dialog = Dialog(title=_("IPv4 netmask"), conditions=[self._check_netmask])
        self._container.add(EntryWidget(dialog.title, self.network_data.netmask), self._set_netmask, dialog)

        dialog = Dialog(title=_("IPv4 gateway"), conditions=[self._check_ipv4])
        self._container.add(EntryWidget(dialog.title, self.network_data.gateway), self._set_ipv4_gateway, dialog)

        msg = (_('IPv6 address[/prefix] or %(auto)s for automatic, %(dhcp)s for DHCP, '
                 '%(ignore)s to turn off')
               % {"auto": '"auto"', "dhcp": '"dhcp"', "ignore": '"ignore"'})
        dialog = Dialog(title=msg, conditions=[self._check_ipv6_config])
        self._container.add(EntryWidget(dialog.title, self.network_data.ipv6), self._set_ipv6, dialog)

        dialog = Dialog(title=_("IPv6 default gateway"), conditions=[self._check_ipv6])
        self._container.add(EntryWidget(dialog.title, self.network_data.ipv6gateway), self._set_ipv6_gateway, dialog)

        dialog = Dialog(title=_("Nameservers (comma separated)"), conditions=[self._check_nameservers])
        self._container.add(EntryWidget(dialog.title, self.network_data.nameserver), self._set_nameservers, dialog)

        msg = _("Connect automatically after reboot")
        w = CheckboxWidget(title=msg, completed=self.network_data.onboot)
        self._container.add(w, self._set_onboot_handler)

        msg = _("Apply configuration in installer")
        w = CheckboxWidget(title=msg, completed=self.apply_configuration)
        self._container.add(w, self._set_apply_handler)

        self.window.add_with_separator(self._container)

        message = _("Configuring device %s.") % self.network_data.device
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
        self.network_data.ip = dialog.run()

    def _set_netmask(self, dialog):
        self.network_data.netmask = dialog.run()

    def _set_ipv4_gateway(self, dialog):
        self.network_data.gateway = dialog.run()

    def _set_ipv6(self, dialog):
        self.network_data.ipv6 = dialog.run()

    def _set_ipv6_gateway(self, dialog):
        self.network_data.ipv6gateway = dialog.run()

    def _set_nameservers(self, dialog):
        self.network_data.nameserver = dialog.run()

    def _set_apply_handler(self, args):
        self.apply_configuration = not self.apply_configuration

    def _set_onboot_handler(self, args):
        self.network_data.onboot = not self.network_data.onboot

    def input(self, args, key):
        if self._container.process_user_input(key):
            self.redraw()
            self.apply()
            return InputState.PROCESSED
        else:
            return super().input(args, key)

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply our changes. """
        # save this back to network data, this will be applied in upper layer
        pass
