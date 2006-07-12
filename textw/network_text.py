#
# network_text.py: text mode network configuration dialogs
#
# Jeremy Katz <katzj@redhat.com>
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2000-2003 Red Hat, Inc.
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
import string
import network
from snack import *
from constants_text import *
from constants import *
from rhpl.translate import _

def badIPDisplay(screen, the_ip):
    ButtonChoiceWindow(screen, _("Invalid IP string"),
                       _("The entered IP '%s' is not a valid IP.") %(the_ip,),
                       buttons = [ _("OK") ])
    return

def sanityCheckIPString(val):
    try:
        network.sanityCheckIPString(val)
    except IPError, err:
        return err

class NetworkDeviceWindow:
    def setsensitive(self):
        if self.dhcpCb.selected ():
            sense = FLAGS_SET
        else:
            sense = FLAGS_RESET

        for n in self.dhcpentries.values():
            n.setFlags (FLAG_DISABLED, sense)

    def calcNM(self):
        ip = self.entries["ipaddr"].value()
        if ip and not self.entries["netmask"].value ():
            try:
                mask = "255.255.255.0"
            except ValueError:
                return

            self.entries["netmask"].set (mask)
        
    def runScreen(self, screen, net, dev, showonboot=1):
        boot = dev.get("bootproto")
        onboot = dev.get("onboot")

        devnames = self.devices.keys()
        devnames.sort(cmp=isys.compareNetDevices)
        if devnames.index(dev.get("DEVICE")) == 0 and not onboot:
            onbootIsOn = 1
        else:
            onbootIsOn = (onboot == "yes")
        if not boot:
            boot = "dhcp"

	options = [(_("IP Address"), "ipaddr", 1),
		   (_("Netmask"),    "netmask", 1)]
        if (network.isPtpDev(dev.info["DEVICE"])):
	    newopt = (_("Point to Point (IP)"), "remip", 1)
	    options.append(newopt)

        if isys.isWireless(dev.info["DEVICE"]):
            wireopt = [(_("ESSID"), "essid", 0),
                       (_("Encryption Key"), "key", 0)]
            options.extend(wireopt)

	descr = dev.get("desc")
        hwaddr = dev.get("hwaddr")
	if descr is None or len(descr) == 0:
	    descr = None
        if hwaddr is None or len(hwaddr) == 0:
            hwaddr = None

	topgrid = Grid(1, 3)

        topgrid.setField(Label (_("Network Device: %s")
                                %(dev.info['DEVICE'],)),
                         0, 0, padding = (0, 0, 0, 0), anchorLeft = 1,
                         growx = 1)

	if descr is not None:
	    topgrid.setField(Label (_("Description: %s") % (descr[:70],)),
			     0, 1, padding = (0, 0, 0, 0), anchorLeft = 1,
			     growx = 1)
        if hwaddr is not None:
            topgrid.setField(Label (_("Hardware Address: %s") %(hwaddr,)),
                             0, 2, padding = (0, 0, 0, 0), anchorLeft = 1,
                             growx = 1)

	botgrid = Grid(2, 2+len(options))
        self.dhcpCb = Checkbox(_("Configure using DHCP"),
                               isOn = (boot == "dhcp"))

	if not showonboot:
	    ypad = 1
	else:
	    ypad = 0

	currow = 0
        botgrid.setField(self.dhcpCb, 0, currow, anchorLeft = 1, growx = 1,
			 padding = (0, 0, 0, ypad))
	currow += 1
        
        self.onbootCb = Checkbox(_("Activate on boot"), isOn = onbootIsOn)
	if showonboot:
	    botgrid.setField(self.onbootCb, 0, currow, anchorLeft = 1, growx = 1,
			     padding = (0, 0, 0, 1))
	    currow += 1

	row = currow
        self.entries = {}
        self.dhcpentries = {}
        for (name, opt, dhcpdep) in options:
            botgrid.setField(Label(name), 0, row, anchorLeft = 1)

            entry = Entry (16)
            entry.set(dev.get(opt))
            botgrid.setField(entry, 1, row, padding = (1, 0, 0, 0))

            self.entries[opt] = entry
            if dhcpdep:
                self.dhcpentries[opt] = entry
            row = row + 1

        self.dhcpCb.setCallback(self.setsensitive)
        self.entries["ipaddr"].setCallback(self.calcNM)

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        toplevel = GridFormHelp(screen, _("Network Configuration for %s") %
                                (dev.info['DEVICE']), 
                                "networkdev", 1, 4)

        toplevel.add(topgrid,  0, 0, (0, 0, 0, 1), anchorLeft = 1)
        toplevel.add(botgrid,  0, 1, (0, 0, 0, 1), anchorLeft = 1)
        toplevel.add(bb, 0, 3, growx = 1)

        self.setsensitive()
        
        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed (result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            if self.onbootCb.selected() != 0:
                dev.set(("onboot", "yes"))
            else:
                dev.unset("onboot")

            if self.dhcpCb.selected() != 0:
                dev.set(("bootproto", "dhcp"))
                dev.unset("ipaddr", "netmask", "network", "broadcast", "remip")
            else:
                ip = self.entries["ipaddr"].value()
                nm = self.entries["netmask"].value()
                try:
                    (net, bc) = isys.inet_calcNetBroad(ip, nm)
                except:
                    if self.onbootCb.selected() != 0:
                        ButtonChoiceWindow(screen, _("Invalid information"),
                                           _("You must enter valid IP "
                                             "information to continue"),
                                           buttons = [ _("OK") ])
                        continue
                    else:
                        net = ""
                        bc = ""

                dev.set(("bootproto", "static"))
                if bc and net:
                    dev.set(("broadcast", bc), ("network", net))

            for val in self.entries.keys():
                if ((self.dhcpCb.selected() != 0) and
                    self.dhcpentries.has_key(val)):
                    continue
                if self.entries[val].value():
                    dev.set((val, self.entries[val].value()))
                        

            break

        screen.popWindow()
        return INSTALL_OK


    def __call__(self, screen, anaconda, showonboot=1):

        self.devices = anaconda.id.network.available()
        if not self.devices:
            return INSTALL_NOOP

        list = self.devices.keys()
        list.sort(cmp=isys.compareNetDevices)
        devLen = len(list)
        if anaconda.dir == DISPATCH_FORWARD:
            currentDev = 0
        else:
            currentDev = devLen - 1

        while currentDev < devLen and currentDev >= 0:
            rc = self.runScreen(screen, anaconda.id.network,
                                self.devices[list[currentDev]],
                                showonboot)
            if rc == INSTALL_BACK:
                currentDev = currentDev - 1
            else:
                currentDev = currentDev + 1

        if currentDev < 0:
            return INSTALL_BACK
        else:
            return INSTALL_OK

class NetworkGlobalWindow:
    def __call__(self, screen, anaconda):
        devices = anaconda.id.network.available()
        if not devices:
            return INSTALL_NOOP

        # we don't let you set gateway/dns if you've got any interfaces
        # using dhcp (for better or worse)
        if network.anyUsingDHCP(devices):
            return INSTALL_NOOP

        thegrid = Grid(2, 4)

        thegrid.setField(Label(_("Gateway:")), 0, 0, anchorLeft = 1)
        gwEntry = Entry(16)
        # if it's set already, use that... otherwise, make them enter it
        if anaconda.id.network.gateway:
            gwEntry.set(anaconda.id.network.gateway)
        else:
            gwEntry.set("")
        thegrid.setField(gwEntry, 1, 0, padding = (1, 0, 0, 0))
        
        thegrid.setField(Label(_("Primary DNS:")), 0, 1, anchorLeft = 1)
        ns1Entry = Entry(16)
        ns1Entry.set(anaconda.id.network.primaryNS)
        thegrid.setField(ns1Entry, 1, 1, padding = (1, 0, 0, 0))
        
        thegrid.setField(Label(_("Secondary DNS:")), 0, 2, anchorLeft = 1)
        ns2Entry = Entry(16)
        ns2Entry.set(anaconda.id.network.secondaryNS)
        thegrid.setField(ns2Entry, 1, 2, padding = (1, 0, 0, 0))
        
        thegrid.setField(Label(_("Tertiary DNS:")), 0, 3, anchorLeft = 1)
        ns3Entry = Entry(16)
        ns3Entry.set(anaconda.id.network.ternaryNS)
        thegrid.setField(ns3Entry, 1, 3, padding = (1, 0, 0, 0))

        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        toplevel = GridFormHelp (screen, _("Miscellaneous Network Settings"),
				 "miscnetwork", 1, 3)
        toplevel.add (thegrid, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        toplevel.add (bb, 0, 2, growx = 1)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed (result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            val = gwEntry.value()
            if val and sanityCheckIPString(val) is not None:
                screen.suspend()
                print "gw", val, sanityCheckIPString(val)
                import pdb; pdb.set_trace()
                screen.resume()
                badIPDisplay(screen, val)
                continue
            anaconda.id.network.gateway = val

            val = ns1Entry.value()
            if val and sanityCheckIPString(val) is not None:
                badIPDisplay(screen, val)
                continue
            anaconda.id.network.primaryNS = val

            val = ns2Entry.value()
            if val and sanityCheckIPString(val) is not None:
                badIPDisplay(screen, val)
                continue
            anaconda.id.network.secondaryNS = val

            val = ns3Entry.value()
            if val and sanityCheckIPString(val) is not None:
                badIPDisplay(screen, val)
                continue
            anaconda.id.network.ternaryNS = val
            break

        screen.popWindow()        
        return INSTALL_OK
        

class HostnameWindow:
    def hostTypeCb(self, (radio, hostEntry)):
        if radio.getSelection() != "manual":
            sense = FLAGS_SET
        else:
            sense = FLAGS_RESET

        hostEntry.setFlags(FLAG_DISABLED, sense)
            
    def __call__(self, screen, anaconda):
        devices = anaconda.id.network.available ()
        if not devices:
            return INSTALL_NOOP

        # figure out if the hostname is currently manually set
        if network.anyUsingDHCP(devices):
            if (anaconda.id.network.hostname != "localhost.localdomain" and
                anaconda.id.network.overrideDHCPhostname):
                manual = 1
            else:
                manual = 0
        else:
            manual = 1

        thegrid = Grid(2, 2)
        radio = RadioGroup()
        autoCb = radio.add(_("automatically via DHCP"), "dhcp",
                                not manual)
        thegrid.setField(autoCb, 0, 0, growx = 1, anchorLeft = 1)

        manualCb = radio.add(_("manually"), "manual", manual)
        thegrid.setField(manualCb, 0, 1, anchorLeft = 1)
        hostEntry = Entry(24)
        if anaconda.id.network.hostname != "localhost.localdomain":
            hostEntry.set(anaconda.id.network.hostname)
        thegrid.setField(hostEntry, 1, 1, padding = (1, 0, 0, 0),
                         anchorLeft = 1)            

        # disable the dhcp if we don't have any dhcp
        if network.anyUsingDHCP(devices):
            autoCb.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_RESET)            
        else:
            autoCb.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)

        self.hostTypeCb((radio, hostEntry))

        autoCb.setCallback(self.hostTypeCb, (radio, hostEntry))
        manualCb.setCallback(self.hostTypeCb, (radio, hostEntry))

        toplevel = GridFormHelp(screen, _("Hostname Configuration"),
                                "hostname", 1, 4)
        text = TextboxReflowed(55,
                               _("If your system is part of a larger network "
                                 "where hostnames are assigned by DHCP, "
                                 "select automatically via DHCP. Otherwise, "
                                 "select manually and enter in a hostname for "
                                 "your system. If you do not, your system "
                                 "will be known as 'localhost.'"))
        toplevel.add(text, 0, 0, (0, 0, 0, 1))

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        toplevel.add(thegrid, 0, 1, padding = (0, 0, 0, 1))
        toplevel.add(bb, 0, 2, growx = 1)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed(result)
            
            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            if radio.getSelection() != "manual":
                anaconda.id.network.overrideDHCPhostname = 0
                anaconda.id.network.hostname = "localhost.localdomain"
            else:
                hname = string.strip(hostEntry.value())
                if len(hname) == 0:
                    ButtonChoiceWindow(screen, _("Invalid Hostname"),
                                       _("You have not specified a hostname."),
                                       buttons = [ _("OK") ])
                    continue
                neterrors = network.sanityCheckHostname(hname)
                if neterrors is not None:
                    ButtonChoiceWindow(screen, _("Invalid Hostname"),
                                       _("The hostname \"%s\" is not valid "
                                         "for the following reason:\n\n%s")
                                       %(hname, neterrors),
                                       buttons = [ _("OK") ])
                    continue

                anaconda.id.network.overrideDHCPhostname = 1
                anaconda.id.network.hostname = hname
            break

        screen.popWindow()
        return INSTALL_OK
