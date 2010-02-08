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


import isys
import network
from snack import *
from constants_text import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class NetworkConfiguratorText:
    def _handleIPError(self, field, errmsg):
        self.anaconda.intf.messageWindow(_("Error With Data"),
                                         _("An error occurred converting the "
                                           "value entered for "
                                           "\"%(field)s\":\n%(errmsg)s") \
                                         % {'field': field, 'errmsg': errmsg})

    def _handleIPMissing(self, field):
        self.anaconda.intf.messageWindow(_("Error With Data"),
                                         _("A value is required for the field %s") % field)

    def _dhcpToggled(self, *args):
        if self.dhcpCheckbox.selected():
            self.ipv4Address.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.ipv4Netmask.setFlags(FLAG_DISABLED, FLAGS_SET)
            #self.ipv6Address.setFlags(FLAG_DISABLED, FLAGS_SET)
            #self.ipv6Netmask.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.gatewayEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.nameserverEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
        else:
            self.ipv4Address.setFlags(FLAG_DISABLED, int(self.ipv4Checkbox.selected()))
            self.ipv4Netmask.setFlags(FLAG_DISABLED, int(self.ipv4Checkbox.selected()))
            #self.ipv6Address.setFlags(FLAG_DISABLED, int(self.ipv6Checkbox.selected()))
            #self.ipv6Netmask.setFlags(FLAG_DISABLED, int(self.ipv6Checkbox.selected()))
            self.gatewayEntry.setFlags(FLAG_DISABLED, FLAGS_RESET)
            self.nameserverEntry.setFlags(FLAG_DISABLED, FLAGS_RESET)

    def _ipv4Toggled(self, *args):
        if self.dhcpCheckbox.selected():
            return

        flag = FLAGS_RESET
        if not self.ipv4Checkbox.selected():
            flag = FLAGS_SET

        self.ipv4Address.setFlags(FLAG_DISABLED, flag)
        self.ipv4Netmask.setFlags(FLAG_DISABLED, flag)

    #def _ipv6Toggled(self, *args):
    #    if self.dhcpCheckbox.selected():
    #        return
    #
    #    flag = FLAGS_RESET
    #    if not self.ipv6Checkbox.selected():
    #        flag = FLAGS_SET
    #
    #    self.ipv6Address.setFlags(FLAG_DISABLED, flag)
    #    self.ipv6Netmask.setFlags(FLAG_DISABLED, flag)

    def __init__(self, screen, anaconda):
        self.screen = screen
        self.anaconda = anaconda

    def run(self):
        grid = GridFormHelp(self.screen, _("Enable network interface"), "netconfig",
                            1, 9)

        tb = TextboxReflowed(60, _("This requires that you have an active "
                                   "network connection during the installation "
                                   "process.  Please configure a network "
                                   "interface."))
        grid.add(tb, 0, 0, anchorLeft = 1, padding = (0, 0, 0, 1))

        self.interfaceList = CheckboxTree(height=3, scroll=1)

        netdevs = self.anaconda.network.available()
        devs = netdevs.keys()
        devs.sort()
        ksdevice = self.anaconda.network.getKSDevice()
        if ksdevice:
            ksdevice = ksdevice.get('DEVICE')
        selected_interface = None

        for dev in devs:
            hwaddr = netdevs[dev].get("HWADDR")

            if hwaddr:
                desc = "%s - %.50s" % (dev, hwaddr)
            else:
                desc = dev

            if selected_interface is None:
                selected_interface = desc

            if ksdevice and ksdevice == dev:
                selected_interface = desc

            self.interfaceList.append(desc)

        if selected_interface:
            self.interfaceList.setCurrent(selected_interface)
        else:
            self.interfaceList.setCurrent(0)

        grid.add(self.interfaceList, 0, 1, padding = (0, 0, 0, 1))

        self.dhcpCheckbox = Checkbox(_("Use dynamic IP configuration (DHCP)"), 1)
        grid.add(self.dhcpCheckbox, 0, 2, anchorLeft = 1)

        self.ipv4Checkbox = Checkbox(_("Enable IPv4 support"), 1)
        grid.add(self.ipv4Checkbox, 0, 3, anchorLeft = 1)

        #self.ipv6Checkbox = Checkbox(_("Enable IPv6 support"), 0)
        #grid.add(self.ipv6Checkbox, 0, 4, anchorLeft = 1, padding = (0, 0, 0, 1))

        ipv4Grid = Grid(4, 1)
        ipv4Grid.setField(Label(_("IPv4 Address:")), 0, 0, padding = (0, 0, 1, 0))
        self.ipv4Address = Entry(20, scroll=1)
        ipv4Grid.setField(self.ipv4Address, 1, 0)
        ipv4Grid.setField(Label("/"), 2, 0)
        self.ipv4Netmask = Entry(20, scroll=0)
        ipv4Grid.setField(self.ipv4Netmask, 3, 0)

        grid.add(ipv4Grid, 0, 5, anchorLeft = 1)

        #ipv6Grid = Grid(4, 1)
        #ipv6Grid.setField(Label(_("IPv6 Address:")), 0, 0, padding = (0, 0, 1, 0))
        #self.ipv6Address = Entry(20, scroll=1)
        #ipv6Grid.setField(self.ipv6Address, 1, 0)
        #ipv6Grid.setField(Label("/"), 2, 0)
        #self.ipv6Netmask = Entry(20, scroll=0)
        #ipv6Grid.setField(self.ipv6Netmask, 3, 0)

        #grid.add(ipv6Grid, 0, 6, anchorLeft = 1)

        extraGrid = Grid(4, 1)
        extraGrid.setField(Label(_("Gateway:")), 0, 0, padding = (0, 0, 1, 0))
        self.gatewayEntry = Entry(20, scroll=1)
        extraGrid.setField(self.gatewayEntry, 1, 0, padding = (0, 0, 2, 0))
        extraGrid.setField(Label(_("Nameserver:")), 2, 0, padding = (0, 0, 1, 0))
        self.nameserverEntry = Entry(20, scroll=1)
        extraGrid.setField(self.nameserverEntry, 3, 0)

        grid.add(extraGrid, 0, 7, anchorLeft = 1)

        buttons = ButtonBar(self.screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON] )
        grid.add(buttons, 0, 8, anchorLeft = 1, growx = 1)

        self.dhcpCheckbox.setCallback(self._dhcpToggled)
        self.ipv4Checkbox.setCallback(self._ipv4Toggled)
        #self.ipv6Checkbox.setCallback(self._ipv6Toggled)

        # Call these functions to set initial UI state.
        self._ipv4Toggled()
        #self._ipv6Toggled()
        self._dhcpToggled()

        netdevs = self.anaconda.network.available()

        while True:
            result = grid.run()
            button = buttons.buttonPressed(result)

            if button == TEXT_BACK_CHECK:
                self.screen.popWindow()
                return INSTALL_BACK

            selected = map(lambda x: x.split()[0], self.interfaceList.getSelection())
            if selected is None or selected == []:
                self.anaconda.intf.messageWindow(_("Missing Device"),
                                                 _("You must select a network device"))
                continue

            for name, dev in netdevs.items():
                if name in selected:
                    dev.set(('ONBOOT', 'yes'))
                else:
                    dev.set(('ONBOOT', 'no'))

            selected_netdevs = []
            for devname in selected:
                if not netdevs.has_key(devname):
                    continue

                netdev = netdevs[devname]
                selected_netdevs.append(netdev)
                netdev.set(("ONBOOT", "yes"))

                if self.dhcpCheckbox.selected():
                    netdev.set(("BOOTPROTO", "dhcp"))
                else:
                    netdev.set(("BOOTPROTO", "static"))
                    ipv4addr = self.ipv4Address.value()
                    ipv4nm = self.ipv4Netmask.value()
                    gateway = self.gatewayEntry.value()
                    ns = self.nameserverEntry.value()

                    try:
                        network.sanityCheckIPString(ipv4addr)
                        netdev.set(("IPADDR", ipv4addr))
                    except network.IPMissing, msg:
                        self._handleIPMissing(_("IP Address"))
                        continue
                    except network.IPError, msg:
                        self._handleIPError(_("IP Address"), msg)
                        continue

                    if ipv4nm.find('.') == -1:
                        # user provided a CIDR prefix
                        try:
                            if int(ipv4nm) > 32 or int(ipv4nm) < 0:
                                msg = _("IPv4 CIDR prefix must be between 0 and 32.")
                                self._handleIPError(_("IPv4 Network Mask"), msg)
                                continue
                            else:
                                ipv4nm = isys.prefix2netmask(int(ipv4nm))
                                netdev.set(("NETMASK", ipv4nm))
                        except:
                            self._handleIPMissing(_("IPv4 Network Mask"))
                            continue
                    else:
                        # user provided a dotted-quad netmask
                        try:
                            network.sanityCheckIPString(ipv4nm)
                            netdev.set(("NETMASK", ipv4nm))
                        except network.IPMissing, msg:
                            self._handleIPMissing(_("IPv4 Network Mask"))
                            continue
                        except network.IPError, msg:
                            self._handleIPError(_("IPv4 Network Mask "), msg)
                            continue

                    try:
                        if gateway:
                            network.sanityCheckIPString(gateway)
                            netdev.set(("GATEWAY", gateway))
                    except network.IPMissing, msg:
                        pass
                    except network.IPError, msg:
                        self._handleIPError(_("Gateway"), msg)
                        continue

                    try:
                        if ns:
                            network.sanityCheckIPString(ns)
                            netdev.set(("DNS1", ns))
                    except network.IPMissing, msg:
                        pass
                    except network.IPError, msg:
                        self._handleIPError(_("Nameserver"), msg)
                        continue

            w = self.anaconda.intf.waitWindow(_("Configuring Network Interfaces"), _("Waiting for NetworkManager"))
            result = self.anaconda.network.bringUp(devices=selected_netdevs)
            w.pop()
            if result:
                break
            else:
                 self.anaconda.intf.messageWindow(_("Error"), _("Error configuring network device"), _("Error configuring network device %s") % netdev.get('DEVICE'))

        self.screen.popWindow()
        return INSTALL_OK
