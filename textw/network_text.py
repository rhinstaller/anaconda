#
# network_text.py: text mode network configuration dialogs
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
import os
import isys
from snack import *
from constants_text import *
from rhpl.translate import _

class NetworkWindow:
    def setsensitive (self):
        if self.cb.selected ():
            sense = FLAGS_SET
        else:
            sense = FLAGS_RESET

        for n in self.ip, self.nm, self.gw, self.ns, self.ns2, self.ns3:
            n.setFlags (FLAG_DISABLED, sense)

    def calcNM (self):
        ip = self.ip.value ()
        if ip and not self.nm.value ():
            try:
                mask = "255.255.255.0"
            except ValueError:
                return

            self.nm.set (mask)

    def calcGW (self):
        ip = self.ip.value ()
        nm = self.nm.value ()
        if ip and nm:
            try:
                (net, bcast) = isys.inet_calcNetBroad (ip, nm)
            except ValueError:
                return

            if not self.gw.value ():
                gw = isys.inet_calcGateway (bcast)
                self.gw.set (gw)
            if not self.ns.value ():
                ns = isys.inet_calcNS (net)
                self.ns.set (ns)

    def runScreen(self, screen, network, dev):

        firstg = Grid (1, 3)
        boot = dev.get ("bootproto")
        onboot = dev.get('onboot')
        onbootIsOn = ((dev == network.available().values()[0] and not onboot)
                      or onboot == 'yes')
        
        if not boot:
            boot = "dhcp"
        firstg.setField (Label (_("Network Device: %s") %
                                (dev.info['DEVICE'],)),
                         0, 0, padding = (0, 0, 0, 1), anchorLeft = 1)
        self.cb = Checkbox (_("Use bootp/dhcp"),
                            isOn = (boot == "dhcp"))
        firstg.setField (self.cb, 0, 1, anchorLeft = 1)
        self.onboot = Checkbox(_("Activate on boot"), isOn = onbootIsOn)
        firstg.setField (self.onboot, 0, 2, anchorLeft = 1)

        if len(dev.info["DEVICE"]) >= 3 and dev.info["DEVICE"][:3] == "ctc":
            ask_ptp = 1
            secondg = Grid (2, 7)
        else:
            ask_ptp = None
            secondg = Grid (2, 6)
            
        secondg.setField (Label (_("IP address:")), 0, 0, anchorLeft = 1)
	secondg.setField (Label (_("Netmask:")), 0, 1, anchorLeft = 1)
	secondg.setField (Label (_("Default gateway (IP):")), 0, 2,
                          anchorLeft = 1)
        secondg.setField (Label (_("Primary nameserver:")), 0, 3,
                          anchorLeft = 1)
        secondg.setField (Label (_("Secondary nameserver:")), 0, 4,
                          anchorLeft = 1)
        secondg.setField (Label (_("Tertiary nameserver:")), 0, 5,
                          anchorLeft = 1)
        if ask_ptp:            
            secondg.setField (Label (_("Point to Point (IP):")), 0, 6,
                              anchorLeft = 1)
        
        self.ip = Entry (16)
        self.ip.set (dev.get ("ipaddr"))
        self.nm = Entry (16)
        self.nm.set (dev.get ("netmask"))
        self.gw = Entry (16)
        self.gw.set (network.gateway)
        self.ns = Entry (16)
        self.ns.set (network.primaryNS)
        self.ns2 = Entry (16)
        self.ns2.set (network.secondaryNS)
        self.ns3 = Entry (16)
        self.ns3.set (network.ternaryNS)
        if ask_ptp:            
            self.ptp = Entry(16)
            self.ptp.set (dev.get ("remip"))

            
        self.cb.setCallback (self.setsensitive)
        self.ip.setCallback (self.calcNM)
        self.nm.setCallback (self.calcGW)

        secondg.setField (self.ip, 1, 0, (1, 0, 0, 0))
	secondg.setField (self.nm, 1, 1, (1, 0, 0, 0))        
	secondg.setField (self.gw, 1, 2, (1, 0, 0, 0))
        secondg.setField (self.ns, 1, 3, (1, 0, 0, 0))
        secondg.setField (self.ns2, 1, 4, (1, 0, 0, 0))
        secondg.setField (self.ns3, 1, 5, (1, 0, 0, 0))
	if ask_ptp:
            secondg.setField (self.ptp, 1, 6, (1, 0, 0, 0))

        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        toplevel = GridFormHelp (screen, _("Network Configuration for %s") %
                                 (dev.info['DEVICE']), 
				 "network", 1, 3)
        toplevel.add (firstg, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        toplevel.add (secondg, 0, 1, (0, 0, 0, 1))
        toplevel.add (bb, 0, 2, growx = 1)

        self.setsensitive ()

        while 1:
            result = toplevel.run ()
            if self.onboot.selected() != 0:
                dev.set (('onboot', 'yes'))
            else:
                dev.unset ('onboot')
            if self.cb.selected ():
                dev.set (("bootproto", "dhcp"))
                dev.unset ("ipaddr", "netmask", "network", "broadcast", "remip")
            else:
                try:
                    (net, bc) = isys.inet_calcNetBroad (self.ip.value (),
                                                        self.nm.value ())
                except:
                    ButtonChoiceWindow(screen, _("Invalid information"),
                                       _("You must enter valid IP information to continue"),
                                       buttons = [ _("OK") ])
                    continue

                dev.set (("bootproto", "static"))
                dev.set (("ipaddr", self.ip.value ()), ("netmask",
                                                        self.nm.value ()),
                         ("network", net), ("broadcast", bc))
                if ask_ptp:
                    dev.set (("remip", self.ptp.value()))
                network.gateway = self.gw.value ()
                network.primaryNS = self.ns.value ()
                network.secondaryNS = self.ns2.value()
                network.ternaryNS = self.ns3.value()

            screen.popWindow()
            break
                     
        rc = bb.buttonPressed (result)

        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK
        return INSTALL_OK

    def __call__(self, screen, network, dir, intf):

        devices = network.available ()
        if not devices:
            return INSTALL_NOOP

	list = devices.keys ()
	list.sort()
        devLen = len(list)
        if dir == 1:
            currentDev = 0
        else:
            currentDev = devLen - 1

        while currentDev < devLen and currentDev >= 0:
            rc = self.runScreen(screen, network, devices[list[currentDev]])
            if rc == INSTALL_BACK:
                currentDev = currentDev - 1
            else:
                currentDev = currentDev + 1

        if currentDev < 0:
            return INSTALL_BACK
        else:
            return INSTALL_OK

class HostnameWindow:
    def __call__(self, screen, network, dir, intf):
        devices = network.available ()
        if not devices:
            return INSTALL_NOOP

	list = devices.keys ()
	list.sort()
        dev = devices[list[0]]
        if dev.get ("bootproto") == "dhcp":
            return INSTALL_NOOP
        
        entry = Entry (24)

        if network.hostname != "localhost.localdomain":
            entry.set (network.hostname)

        rc, values = EntryWindow(screen, _("Hostname Configuration"),
             _("The hostname is the name of your computer.  If your "
               "computer is attached to a network, this may be "
               "assigned by your network administrator."),
             [(_("Hostname"), entry)], buttons = [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON],
	     help = "hostname")

        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK

        network.hostname = entry.value ()

        return INSTALL_OK
