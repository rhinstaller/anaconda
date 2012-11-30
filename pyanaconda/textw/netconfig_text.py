#
# netconfig_text.py: Configure a network interface now.
#
# Copyright (C) 2008  Red Hat, Inc.
# All rights reserved.
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
#
# Author(s): Chris Lumens <clumens@redhat.com>
#            David Cantrell <dcantrell@redhat.com>
#


from pyanaconda import isys
from pyanaconda import network
from snack import *
from constants_text import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class NetworkConfiguratorText:
    def _handleIPError(self, field, errmsg):
        self.intf.messageWindow(_("Error With Data"),
                                         _("An error occurred converting the "
                                           "value entered for "
                                           "\"%(field)s\":\n%(errmsg)s") \
                                         % {'field': field, 'errmsg': errmsg})

    def _handleIPMissing(self, field):
        self.intf.messageWindow(_("Error With Data"),
                                         _("A value is required for the field %s") % field)

    def __init__(self, screen, intf):
        self.screen = screen
        self.netdevs = network.getDevices()

        self._initValues()

    def _initValues(self):
        self.ipv4Selected = 1
        self.ipv6Selected = 1
        self.ipv4Method = "v4dhcp"
        self.ipv6Method = "v6auto"
        self.ipv4Address = ""
        self.ipv4Prefix = ""
        self.ipv4Gateway = ""
        self.ipv4Nameserver = ""
        self.ipv6Address = ""
        self.ipv6Prefix = ""
        self.ipv6Gateway = ""
        self.ipv6Nameserver = ""

    def run(self):

        dev_list = []
        selected_devname = None

        devnames = self.netdevs.sort()

        # Preselect device set in kickstart
        ksdevice = network.get_ksdevice_name()

        for devname in devnames:
            hwaddr = isys.getMacAddress(devname)

            if hwaddr:
                desc = "%s - %.50s" % (devname, hwaddr)
            else:
                desc = devname

            if selected_devname is None:
                selected_devname = devname

            if ksdevice and ksdevice == devname:
                selected_devname = devname
            dev_list.append((desc, devname))

        while True:
            w = self.deviceSelectionForm(dev_list, selected_devname)
            result = w.run()
            button = w.buttons.buttonPressed(result)

            if button == TEXT_BACK_CHECK:
                self.screen.popWindow()
                return INSTALL_BACK

            selected_devname = self.interfaceList.current()

            while True:
                w = self.configForm(selected_devname)
                result = w.run()
                button = w.buttons.buttonPressed(result)

                if button == TEXT_BACK_CHECK:
                    self.screen.popWindow()
                    self.screen.popWindow()
                    break

                self._readValues()
                if (self._checkValues() and
                    self._applyValues(selected_devname)):
                    self.screen.popWindow()
                    self.screen.popWindow()
                    return INSTALL_OK
                else:
                    self.screen.popWindow()

    def deviceSelectionForm(self, dev_list, preselected_dev=None):

        grid = GridFormHelp(self.screen, _("Enable network interface"), "netselection",
                            1, 9)

        tb = TextboxReflowed(60, _("This requires that you have an active "
                                   "network connection during the installation "
                                   "process.  Please select network "
                                   "interface to configure."))
        grid.add(tb, 0, 0, anchorLeft = 1, padding = (0, 0, 0, 1))

        self.interfaceList = Listbox(3, scroll = 1, returnExit = 0)

        for (desc, dev) in dev_list:
            self.interfaceList.append(desc, dev)
        if preselected_dev:
            self.interfaceList.setCurrent(preselected_dev)

        grid.add(self.interfaceList, 0, 1, padding = (0, 0, 0, 1))

        grid.buttons = ButtonBar(self.screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON] )
        grid.add(grid.buttons, 0, 2, anchorLeft = 1, growx = 1)

        return grid

    def configForm(self, devname):

        # Create device configuration screen
        grid = GridFormHelp(self.screen, _("Enable network interface"), "netconfig",
                            1, 13)

        tb = TextboxReflowed(60, _("Configure interface %s "
                                   "to be used during installation process.")
                                    % devname)
        grid.add(tb, 0, 0, anchorLeft = 1, padding = (0, 0, 0, 1))

        self.ipv4Checkbox = Checkbox(_("Enable IPv4 Support"),
                                     isOn=self.ipv4Selected)
        grid.add(self.ipv4Checkbox, 0, 1, anchorLeft = 1, padding = (0, 0, 0, 0), growx = 1)
        self.v4radio = RadioGroup()
        self.v4radio_auto = self.v4radio.add(_("Dynamic IP configuration (DHCP)"),
                                             "v4dhcp",
                                             self.ipv4Method=="v4dhcp")
        self.v4radio_manual = self.v4radio.add(_("Manual Configuration"),
                                               "v4manual",
                                               self.ipv4Method=="v4manual")
        grid.add(self.v4radio_auto, 0, 2, anchorLeft = 1, padding = (2, 0, 0, 0), growx = 1)
        grid.add(self.v4radio_manual, 0, 3, anchorLeft = 1, padding = (2, 0, 0, 0), growx = 1)


        ipv4Grid = Grid(4, 3)
        ipv4Grid.setField(Label(_("IPv4 Address:")), 0, 0, padding = (0, 0, 1, 0),
                         anchorLeft = 1)
        self.ipv4AddressEntry = Entry(20, scroll=1)
        self.ipv4AddressEntry.set(self.ipv4Address)
        ipv4Grid.setField(self.ipv4AddressEntry, 1, 0)
        ipv4Grid.setField(Label("/"), 2, 0)
        self.ipv4PrefixEntry = Entry(3, scroll=0)
        self.ipv4PrefixEntry.set(self.ipv4Prefix)
        ipv4Grid.setField(self.ipv4PrefixEntry, 3, 0)
        ipv4Grid.setField(Label(_("Gateway:")), 0, 1, padding = (0, 0, 0, 0),
                              anchorLeft = 1)
        self.ipv4GatewayEntry = Entry(20, scroll=1)
        self.ipv4GatewayEntry.set(self.ipv4Gateway)
        ipv4Grid.setField(self.ipv4GatewayEntry, 1, 1)
        ipv4Grid.setField(Label(_("Nameserver:")), 0, 2, padding = (0, 0, 0, 0),
                             anchorLeft = 1)
        self.ipv4NameserverEntry = Entry(20, scroll=1)
        self.ipv4NameserverEntry.set(self.ipv4Nameserver)
        ipv4Grid.setField(self.ipv4NameserverEntry, 1, 2)

        grid.add(ipv4Grid, 0, 4, anchorLeft = 1, padding = (6, 0, 0, 0))

        self.ipv6Checkbox = Checkbox(_("Enable IPv6 Support"),
                                     isOn=self.ipv6Selected)
        grid.add(self.ipv6Checkbox, 0, 5, anchorLeft = 1, padding = (0, 0, 0, 0), growx = 1)
        self.v6radio = RadioGroup()
        self.v6radio_auto = self.v6radio.add(_("Automatic neighbor discovery"),
                                             "v6auto",
                                             self.ipv6Method=="v6auto")
        self.v6radio_dhcp = self.v6radio.add(_("Dynamic IP Configuration (DHCPv6)"),
                                               "v6dhcp",
                                               self.ipv6Method=="v6dhcp")
        self.v6radio_manual = self.v6radio.add(_("Manual Configuration"),
                                               "v6manual",
                                               self.ipv6Method=="v6manual")
        grid.add(self.v6radio_auto, 0, 6, anchorLeft = 1, padding = (2, 0, 0, 0), growx = 1)
        grid.add(self.v6radio_dhcp, 0, 7, anchorLeft = 1, padding = (2, 0, 0, 0), growx = 1)
        grid.add(self.v6radio_manual, 0, 8, anchorLeft = 1, padding = (2, 0, 0, 0), growx = 1)

        ipv6Grid = Grid(4, 3)
        ipv6Grid.setField(Label(_("IPv6 Address:")), 0, 0, padding = (0, 0, 1, 0),
                          anchorLeft = 1)
        self.ipv6AddressEntry = Entry(41, scroll=1)
        self.ipv6AddressEntry.set(self.ipv6Address)
        ipv6Grid.setField(self.ipv6AddressEntry, 1, 0)
        ipv6Grid.setField(Label("/"), 2, 0)
        self.ipv6PrefixEntry = Entry(4, scroll=0)
        self.ipv6PrefixEntry.set(self.ipv6Prefix)
        ipv6Grid.setField(self.ipv6PrefixEntry, 3, 0)
        ipv6Grid.setField(Label(_("Gateway:")), 0, 1, padding = (0, 0, 0, 0),
                          anchorLeft = 1)
        self.ipv6GatewayEntry = Entry(41, scroll=1)
        self.ipv6GatewayEntry.set(self.ipv6Gateway)
        ipv6Grid.setField(self.ipv6GatewayEntry, 1, 1)
        ipv6Grid.setField(Label(_("Nameserver:")), 0, 2, padding = (0, 0, 0, 0),
                         anchorLeft = 1)
        self.ipv6NameserverEntry = Entry(41, scroll=1)
        self.ipv6NameserverEntry.set(self.ipv6Nameserver)
        ipv6Grid.setField(self.ipv6NameserverEntry, 1, 2)

        grid.add(ipv6Grid, 0, 9, anchorLeft = 1, padding = (6, 0, 0, 0))

        grid.buttons = ButtonBar(self.screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON])
        grid.add(grid.buttons, 0, 10, anchorLeft = 1, growx = 1)

        self.v4radio_manual.setCallback(self._ipv4MethodToggled)
        self.v4radio_auto.setCallback(self._ipv4MethodToggled)
        self.v6radio_manual.setCallback(self._ipv6MethodToggled)
        self.v6radio_auto.setCallback(self._ipv6MethodToggled)
        self.v6radio_dhcp.setCallback(self._ipv6MethodToggled)
        self.ipv4Checkbox.setCallback(self._ipv4MethodToggled)
        self.ipv6Checkbox.setCallback(self._ipv6MethodToggled)

        self._ipv4MethodToggled()
        self._ipv6MethodToggled()

        return grid


    def _readValues(self):
        self.ipv4Selected = self.ipv4Checkbox.selected()
        self.ipv6Selected = self.ipv6Checkbox.selected()
        self.ipv4Method = self.v4radio.getSelection()
        self.ipv6Method = self.v6radio.getSelection()
        self.ipv4Address = self.ipv4AddressEntry.value()
        self.ipv4Prefix = self.ipv4PrefixEntry.value()
        self.ipv4Gateway = self.ipv4GatewayEntry.value()
        self.ipv4Nameserver = self.ipv4NameserverEntry.value()
        self.ipv6Address = self.ipv6AddressEntry.value()
        self.ipv6Prefix = self.ipv6PrefixEntry.value()
        self.ipv6Gateway = self.ipv6GatewayEntry.value()
        self.ipv6Nameserver = self.ipv6NameserverEntry.value()

    def _checkValues(self):
        if not self.ipv4Selected and not self.ipv6Selected:
            self.intf.messageWindow(_("Missing protocol"),
                               _("You must select at least one protocol version"))
            return False

        if self.ipv4Selected:
            if self.ipv4Method == "v4manual":
                try:
                    network.sanityCheckIPString(self.ipv4Address)
                except network.IPMissing as msg:
                    self._handleIPMissing(_("IPv4 Address"))
                    return False
                except network.IPError as msg:
                    self._handleIPError(_("IPv4 Address"), msg)
                    return False

                if not self.ipv4Prefix:
                    self._handleIPMissing(_("IPv4 Prefix"))
                    return False
                elif (int(self.ipv4Prefix) < 0 or
                      int(self.ipv4Prefix) > 32):
                    msg = _("IPv4 CIDR prefix must be between 0 and 32.")
                    self._handleIPError(_("IPv4 Prefix"), msg)
                    return False

                if self.ipv4Gateway:
                    try:
                        network.sanityCheckIPString(self.ipv4Gateway)
                    except network.IPError as msg:
                        self._handleIPError(_("IPv4 Gateway"), msg)
                        return False

                if self.ipv4Nameserver:
                    for addr in self.ipv4Nameserver.split(','):
                        addr.split()
                        try:
                            network.sanityCheckIPString(addr)
                        except network.IPError as msg:
                            self._handleIPError(_("IPv4 Nameserver"), msg)
                            return False

        if self.ipv6Selected:
            if self.ipv6Method == "v6manual":
                try:
                    network.sanityCheckIPString(self.ipv6Address)
                except network.IPMissing as msg:
                    self._handleIPMissing(_("IPv6 Address"))
                    return False
                except network.IPError as msg:
                    self._handleIPError(_("IPv6 Address"), msg)
                    return False

                if not self.ipv6Prefix:
                    self._handleIPMissing(_("IPv6 Prefix"))
                    return False
                elif (int(self.ipv6Prefix) < 0 or
                      int(self.ipv6Prefix) > 128):
                    msg = _("IPv6 CIDR prefix must be between 0 and 128.")
                    self._handleIPError(_("IPv6 Prefix"), msg)
                    return False

                if self.ipv6Gateway:
                    try:
                        network.sanityCheckIPString(self.ipv6Gateway)
                    except network.IPError as msg:
                        self._handleIPError(_("IPv6 Gateway"), msg)
                        return False
                if self.ipv6Nameserver:
                    for addr in self.ipv6Nameserver.split(','):
                        addr.split()
                        try:
                            network.sanityCheckIPString(addr)
                        except network.IPError as msg:
                            self._handleIPError(_("IPv6 Nameserver"), msg)
                            return False

        return True

    def _applyValues(self, devname):
        """Activates device devname.

           Returns True in case of success, False if failed.
        """

        dev = network.NetworkDevice(ROOT_PATH, devname)
        dev.loadIfcfgFile()

        nameservers = ''

        if self.ipv4Selected:
            if self.ipv4Method == "v4dhcp":
                dev.set(("BOOTPROTO", "dhcp"))
            elif self.ipv4Method == "v4manual":
                dev.set(("BOOTPROTO", "static"))
                dev.set(("IPADDR", self.ipv4Address))
                dev.set(("PREFIX", self.ipv4Prefix))
                if self.ipv4Gateway:
                    dev.set(("GATEWAY", self.ipv4Gateway))
                if self.ipv4Nameserver:
                    nameservers += self.ipv4Nameserver
        else:
            dev.unset("BOOTPROTO")
            dev.unset("IPADDR")
            dev.unset("PREFIX")
            dev.unset("GATEWAY")

        if self.ipv6Selected:
            dev.set(("IPV6INIT", "yes"))
            if self.ipv6Method == "v6auto":
                dev.set(("IPV6_AUTOCONF", "yes"))
            elif self.ipv6Method == "v6dhcp":
                dev.set(("IPV6_AUTOCONF", "no"))
                dev.set(("DHCPV6C", "yes"))
            elif self.ipv6Method == "v6manual":
                dev.set(("IPV6_AUTOCONF", "no"))
                dev.set(("IPV6ADDR", "%s/%s" % (self.ipv6Address,
                                                self.ipv6Prefix)))
                if self.ipv6Gateway:
                    dev.set(("IPV6_DEFAULTGW", self.ipv6Gateway))
                if self.ipv6Nameserver:
                    if nameservers:
                        nameservers += ','
                    nameservers += self.ipv6Nameserver
        else:
            dev.set(("IPV6INIT", "no"))

        self.netdevs[devname].unsetDNS()
        if nameservers:
            self.netdevs[devname].setDNS(nameservers)

        dev.set(('ONBOOT', 'yes'))

        w = self.intf.waitWindow(_("Configuring Network Interfaces"), _("Waiting for NetworkManager"))
        dev.writeIfcfgFile()
        result = network.waitForConnection()
        w.pop()
        if not result:
            self.intf.messageWindow(_("Network Error"),
                                             _("There was an error configuring "
                                               "network device %s") % dev.iface)
            dev.set(("ONBOOT", "no"))
            dev.writeIfcfgFile()
            return False

        return True

    def _ipv4MethodToggled(self, *args):
        if (self.v4radio.getSelection() == "v4manual" and
            self.ipv4Checkbox.selected()):
            flag = FLAGS_RESET
        else:
            flag = FLAGS_SET

        self.ipv4AddressEntry.setFlags(FLAG_DISABLED, flag)
        self.ipv4PrefixEntry.setFlags(FLAG_DISABLED, flag)
        self.ipv4GatewayEntry.setFlags(FLAG_DISABLED, flag)
        self.ipv4NameserverEntry.setFlags(FLAG_DISABLED, flag)

        # Update flags for radio buttons based on whether ipv4 is selected
        if self.ipv4Checkbox.selected():
            self.v4radio_auto.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_RESET)
            self.v4radio_manual.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_RESET)
        else:
            self.v4radio_auto.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)
            self.v4radio_manual.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)

    def _ipv6MethodToggled(self, *args):
        if (self.v6radio.getSelection() == "v6manual" and
            self.ipv6Checkbox.selected()):
            flag = FLAGS_RESET
        else:
            flag = FLAGS_SET

        self.ipv6AddressEntry.setFlags(FLAG_DISABLED, flag)
        self.ipv6PrefixEntry.setFlags(FLAG_DISABLED, flag)
        self.ipv6GatewayEntry.setFlags(FLAG_DISABLED, flag)
        self.ipv6NameserverEntry.setFlags(FLAG_DISABLED, flag)

        # Update flags for radio buttons based on whether ipv6 is selected
        if self.ipv6Checkbox.selected():
            self.v6radio_auto.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_RESET)
            self.v6radio_dhcp.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_RESET)
            self.v6radio_manual.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_RESET)
        else:
            self.v6radio_auto.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)
            self.v6radio_dhcp.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)
            self.v6radio_manual.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)
