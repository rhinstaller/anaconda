#
# netconfig_dialog.py: Configure a network interface now.
#
# Copyright (C) 2006  Red Hat, Inc.  All rights reserved.
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import gtk
import gobject
import gui

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import network
import isys

class NetworkConfigurator:
    def __init__(self, network):
        (xml, w) = gui.getGladeWidget("netconfig.glade", "NetworkConfigWindow")

        self.window = w
        self.network = network
        self.xml = xml
        self.rc = gtk.RESPONSE_CANCEL

        self._setSizeGroup()
        self._connectSignals()
        self._populateNetdevs()

        self.xml.get_widget("ipv4Checkbutton").set_active(True)
        self.xml.get_widget("ipv6Checkbutton").set_active(False)

    def _connectSignals(self):
        sigs = { "on_ipv4Checkbutton_toggled": self._ipv4Toggled,
                 "on_ipv6Checkbutton_toggled": self._ipv6Toggled,
                 "on_dhcpCheckbutton_toggled": self._dhcpToggled,
                 "on_interfaceCombo_changed": self._netdevChanged,
                 "on_cancelButton_clicked": self._cancel,
                 "on_okButton_clicked": self._ok }
        self.xml.signal_autoconnect(sigs)

    def _setSizeGroup(self): # too bad we can't do this in the glade file
        sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        for w in ("nameserverLabel", "gatewayLabel", "ipv6Label",
                  "ipv4Label", "interfaceLabel"):
            sg.add_widget(self.xml.get_widget(w))

    def _netdevChanged(self, combo):
        active = combo.get_active_iter()
        val = combo.get_model().get_value(active, 1)
        netdev = self.network.available()[val]

        bootproto = netdev.get("BOOTPROTO")
        if not bootproto or bootproto == "dhcp" or bootproto == "ibft":
            self.xml.get_widget("dhcpCheckbutton").set_active(True)
        else:
            self.xml.get_widget("dhcpCheckbutton").set_active(False)

            # FIXME: need to set ipv6 here too once we have that
            try:
                if netdev.get('IPADDR'):
                    self.xml.get_widget("ipv4Address").set_text(netdev.get('IPADDR'))
            except:
                pass

            try:
                if netdev.get('NETMASK'):
                    self.xml.get_widget("ipv4Netmask").set_text(netdev.get('NETMASK'))
            except:
                pass

            try:
                if self.network.gateway:
                    self.xml.get_widget("gatewayEntry").set_text(self.network.gateway)
            except:
                pass

            try:
                if self.network.primaryNS:
                    self.xml.get_widget("nameserverEntry").set_text(self.network.primaryNS)
            except:
                pass

    def _ipv4Toggled(self, cb):
        if self.xml.get_widget("dhcpCheckbutton").get_active():
            return
        if cb.get_active():
            self.xml.get_widget("ipv4Box").set_sensitive(True)
        else:
            self.xml.get_widget("ipv4Box").set_sensitive(False)

    def _ipv6Toggled(self, cb):
        if self.xml.get_widget("dhcpCheckbutton").get_active():
            return
        if cb.get_active():
            self.xml.get_widget("ipv6Box").set_sensitive(True)
        else:
            self.xml.get_widget("ipv6Box").set_sensitive(False)

    def _dhcpToggled(self, cb):
        boxes = ("ipv4Box", "ipv6Box", "nameserverBox", "gatewayBox")
        if not cb.get_active():
            map(lambda x: self.xml.get_widget(x).set_sensitive(True), boxes)
            self.xml.get_widget("ipv4Box").set_sensitive(self.xml.get_widget("ipv4Checkbutton").get_active())
            self.xml.get_widget("ipv6Box").set_sensitive(self.xml.get_widget("ipv6Checkbutton").get_active())
        else:
            map(lambda x: self.xml.get_widget(x).set_sensitive(False), boxes)

    def _populateNetdevs(self):
        combo = self.xml.get_widget("interfaceCombo")

        cell = gtk.CellRendererText()
        combo.pack_start(cell, True)
        combo.set_attributes(cell, text = 0)
        cell.set_property("wrap-width", 525)
        combo.set_size_request(480, -1)

        store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        combo.set_model(store)

        netdevs = self.network.available()
        devs = netdevs.keys()
        devs.sort()
        ksdevice = self.network.getKSDevice()
        if ksdevice:
            ksdevice = ksdevice.get('DEVICE')
        selected_interface = None

        for dev in devs:
            i = store.append(None)
            hwaddr = netdevs[dev].get("HWADDR")

            if hwaddr:
                desc = "%s - %s" %(dev, hwaddr,)
            else:
                desc = "%s" %(dev,)

            if selected_interface is None:
                selected_interface = i

            if ksdevice and ksdevice == dev:
                selected_interface = i

            store[i] = (desc, dev)

        if selected_interface:
            combo.set_active_iter(selected_interface)
        else:
            combo.set_active(0)

    def run(self):
        gui.addFrame(self.window)
        busycursor = gui.getBusyCursorStatus()
        gui.setCursorToNormal()

        self.window.show()
        while True:
            rc = self.window.run()
            if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
                self._cancel()
                break
            if self._ok():
                break

        # restore busy cursor
        if busycursor:
            gui.setCursorToBusy()
        return self.rc

    def destroy(self):
        self.window.destroy()

    def _handleIPError(self, field, errmsg):
        d = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR,
                              gtk.BUTTONS_OK,
                                _("An error occurred converting the value "
                                  "entered for \"%(field)s\":\n%(errmsg)s")
                                % {'field': field, 'errmsg': errmsg})
        d.set_title(_("Error With Data"))
        d.set_position(gtk.WIN_POS_CENTER)
        gui.addFrame(d)
        d.run()
        d.destroy()

    def _handleIPMissing(self, field):
        d = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
                         _("A value is required for the field %s.") % (field,))
        d.set_title(_("Error With Data"))
        d.set_position(gtk.WIN_POS_CENTER)
        gui.addFrame(d)
        d.run()
        d.destroy()

    def _handleNetworkError(self, field):
        d = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR,
                              gtk.BUTTONS_OK,
                              _("An error occurred trying to bring up the "
                                "%s network interface.") % (field,))
        d.set_title(_("Error Configuring Network"))
        d.set_position(gtk.WIN_POS_CENTER)
        gui.addFrame(d)
        d.run()
        d.destroy()

    def _cancel(self, *args):
        self.rc = gtk.RESPONSE_CANCEL

    def _ok(self, *args):
        self.rc = gtk.RESPONSE_OK
        haveNet = False
        combo = self.xml.get_widget("interfaceCombo")
        active = combo.get_active_iter()
        val = combo.get_model().get_value(active, 1)
        for v, dev in self.network.available().items():
            if v == val:
                dev.set(('ONBOOT', 'yes'))
                netdev = dev
            else:
                dev.set(('ONBOOT', 'no'))

        # FIXME: need to do input validation
        if self.xml.get_widget("dhcpCheckbutton").get_active():
            netdev.set(('BOOTPROTO', 'dhcp'))
            self.window.hide()
            w = gui.WaitWindow(_("Dynamic IP Address"),
                               _("Sending request for IP address information "
                                 "for %s") % (netdev.get('DEVICE'),))
            haveNet = self.network.bringUp(devices=[netdev])
            w.pop()
        else:
            netdev.set(('BOOTPROTO', 'static'))
            ipv4addr = self.xml.get_widget("ipv4Address").get_text()
            ipv4nm = self.xml.get_widget("ipv4Netmask").get_text()
            gateway = self.xml.get_widget("gatewayEntry").get_text()
            ns = self.xml.get_widget("nameserverEntry").get_text()

            try:
                network.sanityCheckIPString(ipv4addr)
                netdev.set(('IPADDR', ipv4addr))
            except network.IPMissing, msg:
                self._handleIPMissing(_("IP Address"))
                return False
            except network.IPError, msg:
                self._handleIPError(_("IP Address"), msg)
                return False

            if ipv4nm.find('.') == -1:
                # user provided a CIDR prefix
                try:
                    if int(ipv4nm) > 32 or int(ipv4nm) < 0:
                        msg = _("IPv4 CIDR prefix must be between 0 and 32.")
                        self._handleIPError(_("IPv4 Network Mask"), msg)
                        return False
                    else:
                        ipv4nm = isys.prefix2netmask(int(ipv4nm))
                        netdev.set(('NETMASK', ipv4nm))
                except:
                    self._handleIPMissing(_("IPv4 Network Mask"))
                    return False
            else:
                # user provided a dotted-quad netmask
                try:
                    network.sanityCheckIPString(ipv4nm)
                    netdev.set(('NETMASK', ipv4nm))
                except network.IPMissing, msg:
                    self._handleIPMissing(_("IPv4 Network Mask"))
                    return False
                except network.IPError, msg:
                    self._handleIPError(_("IPv4 Network Mask"), msg)
                    return False

            try:
                if gateway:
                    network.sanityCheckIPString(gateway)
                    netdev.set(('GATEWAY', gateway))
            except network.IPMissing, msg:
                pass
            except network.IPError, msg:
                self._handleIPError(_("Gateway"), msg)
                return False

            try:
                if ns:
                    network.sanityCheckIPString(ns)
                    netdev.set(('DNS1', ns))
            except network.IPMissing, msg:
                pass
            except network.IPError, msg:
                self._handleIPError(_("Nameserver"), msg)
                return False

            try:
                haveNet = self.network.bringUp(devices=[netdev])
            except Exception, e:
                import logging
                log = logging.getLogger("anaconda")
                log.error("Error configuring network device: %s" %(e,))
                self._handleIPError(_("Error configuring network device:"), e)
                return False

        if not haveNet:
            self._handleNetworkError(netdev.get('DEVICE'))
            return False

        return True

def main():
    net = network.Network()
    d = NetworkConfigurator(net)
    ret = d.run()

if __name__ == "__main__":
    main()
