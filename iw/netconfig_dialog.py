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

from rhpl.translate import _, N_

import gui
import network

class NetworkConfigurator:
    def __init__(self, network):
        (xml, w) = gui.getGladeWidget("netconfig.glade", "NetworkConfigWindow")

        self.window = w
        self.network = network
        self.xml = xml

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
        if not bootproto or bootproto == "dhcp":
            self.xml.get_widget("dhcpCheckbutton").set_active(True)
        else:
            self.xml.get_widget("dhcpCheckbutton").set_active(False)

            # FIXME: need to set ipv6 here too once we have that
            if netdev.get("ipaddr"): self.xml.get_widget("ipv4AddressEntry").set_text(netdev.get("ipaddr"))
            if netdev.get("netmask"): self.xml.get_widget("ipv4NetmaskEntry").set_text(netdev.get("netmask"))
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
        self.window.show()
        gtk.main()

    def _cancel(self, *args):
        gtk.main_quit()
        return False

    def _ok(self, *args):
        combo = self.xml.get_widget("interfaceCombo")
        active = combo.get_active_iter()
        val = combo.get_model().get_value(active, 1)
        netdev = self.network.available()[val]

        # FIXME: need to do input validation
        if self.xml.get_widget("dhcpCheckbutton").get_active():
            print "going to do dhcp on %s" %(netdev,)
        else:
            ipv4addr = self.xml.get_widget("ipv4AddressEntry").get_text()
            ipv4nm = self.xml.get_widget("ipv4NetmaskEntry").get_text()
            gateway = self.xml.get_widget("gatewayEntry").get_text()
            ns = self.xml.get_widget("nameserverEntry").get_text()
            
            print "going to bring up %s as %s/%s, gateway %s, ns %s" %(netdev, ipv4addr, ipv4nm, gateway, ns)
            # FIXME: ... and actually bring up the interface :)
        
        gtk.main_quit()
        


def main():
    net = network.Network()
    d = NetworkConfigurator(net)
    d.run()


if __name__ == "__main__":
    main()
