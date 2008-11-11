#
# netconfig_dialog.py: Configure a network interface now.
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gobject
import gui

from rhpl.translate import _, N_

import gui
import network
import isys
import logging

log = logging.getLogger("anaconda")

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

        bootproto = netdev.get("bootproto")
        if not bootproto or bootproto == "dhcp" or bootproto == "ibft":
            self.xml.get_widget("dhcpCheckbutton").set_active(True)
        else:
            self.xml.get_widget("dhcpCheckbutton").set_active(False)

            # FIXME: need to set ipv6 here too once we have that
            if netdev.get("ipaddr"): self.xml.get_widget("ipv4Address").set_text(netdev.get("ipaddr"))
            if netdev.get("netmask"): self.xml.get_widget("ipv4Netmask").set_text(netdev.get("netmask"))
            if self.network.gateway: self.xml.get_widget("gatewayEntry").set_text(self.network.gateway)
            if self.network.primaryNS: self.xml.get_widget("nameserverEntry").set_text(self.network.primaryNS)

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
        for dev in devs:
            i = store.append(None)
            desc = netdevs[dev].get("desc")
            if desc:
                desc = "%s - %s" %(dev, desc)
            else:
                desc = "%s" %(dev,)
            store[i] = (desc, dev)
            if dev == self.network.firstnetdevice:
                combo.set_active_iter(i)

    def run(self):
        gui.addFrame(self.window)
        self.window.show()
        gtk.main()
        return self.rc

    def destroy(self):
        self.window.destroy()

    def _handleIPMissing(self, field):
        d = gtk.MessageDialog(_("Error With Data"), 0, gtk.MESSAGE_ERROR,
                              gtk.BUTTONS_OK,
                              _("A value is required for the field %s.")
                              % (field,))
        d.run()
        d.destroy()

    def _handleIPError(self, field, errmsg):
        d = gtk.MessageDialog(_("Error With Data"), 0, gtk.MESSAGE_ERROR,
                              gtk.BUTTONS_OK,
                                _("An error occurred converting the value "
                                  "entered for \"%s\":\n%s") %(field, errmsg))
        d.run()
        d.destroy()

    def _cancel(self, *args):
        gtk.main_quit()
        self.rc = gtk.RESPONSE_CANCEL

    def _ok(self, *args):
        combo = self.xml.get_widget("interfaceCombo")
        active = combo.get_active_iter()
        val = combo.get_model().get_value(active, 1)
        netdev = self.network.available()[val]

        # FIXME: need to do input validation
        if self.xml.get_widget("dhcpCheckbutton").get_active():
            self.window.hide()
            w = gui.WaitWindow(_("Dynamic IP"),
                               _("Sending request for IP information "
                                 "for %s...") %(netdev.get("device")))
            ns = isys.dhcpNetDevice(netdev.get("device"))
            w.pop()
            if ns is not None:
                self.rc = gtk.RESPONSE_OK
            if ns:
                f = open("/etc/resolv.conf", "w")
                f.write("nameserver %s\n" % ns)
                f.close()
                isys.resetResolv()
        else:
            ipv4addr = self.xml.get_widget("ipv4Address").get_text()
            ipv4nm = self.xml.get_widget("ipv4Netmask").get_text()
            gateway = self.xml.get_widget("gatewayEntry").get_text()
            ns = self.xml.get_widget("nameserverEntry").get_text()

            try:
                network.sanityCheckIPString(ipv4addr)
            except network.IPMissing, msg:
                self._handleIPMissing(_("IP Address"))
                return
            except network.IPError, msg:
                self._handleIPError(_("IP Address"), msg)
                return

            if ipv4nm.find('.') == -1:
                # user provided a CIDR prefix
                try:
                    if int(ipv4nm) > 32 or int(ipv4nm) < 0:
                        msg = _("IPv4 CIDR prefix must be between 0 and 32.")
                        self._handleIPError(_("IPv4 Network Mask"), msg)
                        return
                    else:
                        ipv4nm = isys.prefix2netmask(int(ipv4nm))
                        netdev.set(('netmask', ipv4nm))
                except:
                    self._handleIPMissing(_("IPv4 Network Mask"))
                    return
            else:
                # user provided a dotted-quad netmask
                try:
                    network.sanityCheckIPString(ipv4nm)
                    netdev.set(('netmask', ipv4nm))
                except network.IPMissing, msg:
                    self._handleIPMissing(_("IPv4 Network Mask"))
                    return
                except network.IPError, msg:
                    self._handleIPError(_("IPv4 Network Mask"), msg)
                    return

            try:
                if gateway:
                    network.sanityCheckIPString(gateway)
            except network.IPError, msg:
                self._handleIPError(_("Gateway"), msg)
                return

            try:
                if ns:
                    network.sanityCheckIPString(ns)
            except network.IPError, msg:
                self._handleIPError(_("Nameserver"), msg)
                return

            try:
                isys.configNetDevice(netdev.get("device"),
                                     ipv4addr, ipv4nm, gateway)
            except Exception, e:
                log.error("Error configuring network device: %s" %(e,))

            self.rc = gtk.RESPONSE_OK
            if ns:
                f = open("/etc/resolv.conf", "w")
                f.write("nameserver %s\n" %(ns,))
                f.close()
                isys.resetResolv()
                isys.setResolvRetry(1)

        if self.rc != gtk.RESPONSE_OK:
            gui.MessageWindow(_("Error"),
                              _("Error configuring network device"),
                              type = "ok", custom_icon="error")
            return

        gtk.main_quit()

def main():
    net = network.Network()
    d = NetworkConfigurator(net)
    ret = d.run()

if __name__ == "__main__":
    main()
