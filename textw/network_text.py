import iutil
import os
import isys
from snack import *
from constants_text import *
from translate import _

class NetworkWindow:
    def setsensitive (self):
        if self.cb.selected ():
            sense = FLAGS_SET
        else:
            sense = FLAGS_RESET

        for n in self.ip, self.nm, self.gw, self.ns:
            n.setFlags (FLAG_DISABLED, sense)

    def calcNM (self):
        ip = self.ip.value ()
        if ip and not self.nm.value ():
            try:
                mask = isys.inet_calcNetmask (ip)
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

    def __call__(self, screen, todo):


        devices = todo.network.available ()
        if not devices:
            return INSTALL_NOOP

        if todo.network.readData:
            # XXX expert mode, allow changing network settings here
            return INSTALL_NOOP
        
	list = devices.keys ()
	list.sort()
        dev = devices[list[0]]

        firstg = Grid (1, 1)
        boot = dev.get ("bootproto")
        
        if not boot:
            boot = "dhcp"
        self.cb = Checkbox (_("Use bootp/dhcp"),
                            isOn = (boot == "dhcp"))
        firstg.setField (self.cb, 0, 0, anchorLeft = 1)

        secondg = Grid (2, 4)
        secondg.setField (Label (_("IP address:")), 0, 0, anchorLeft = 1)
	secondg.setField (Label (_("Netmask:")), 0, 1, anchorLeft = 1)
	secondg.setField (Label (_("Default gateway (IP):")), 0, 2, anchorLeft = 1)
        secondg.setField (Label (_("Primary nameserver:")), 0, 3, anchorLeft = 1)

        self.ip = Entry (16)
        self.ip.set (dev.get ("ipaddr"))
        self.nm = Entry (16)
        self.nm.set (dev.get ("netmask"))
        self.gw = Entry (16)
        self.gw.set (todo.network.gateway)
        self.ns = Entry (16)
        self.ns.set (todo.network.primaryNS)

        self.cb.setCallback (self.setsensitive)
        self.ip.setCallback (self.calcNM)
        self.nm.setCallback (self.calcGW)

        secondg.setField (self.ip, 1, 0, (1, 0, 0, 0))
	secondg.setField (self.nm, 1, 1, (1, 0, 0, 0))
	secondg.setField (self.gw, 1, 2, (1, 0, 0, 0))
        secondg.setField (self.ns, 1, 3, (1, 0, 0, 0))

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        toplevel = GridFormHelp (screen, _("Network Configuration"), 
				 "network", 1, 3)
        toplevel.add (firstg, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        toplevel.add (secondg, 0, 1, (0, 0, 0, 1))
        toplevel.add (bb, 0, 2, growx = 1)

        self.setsensitive ()

        while 1:
            result = toplevel.run ()
            if self.cb.selected ():
                dev.set (("bootproto", "dhcp"))
                dev.unset ("ipaddr", "netmask", "network", "broadcast")
            else:
                try:
                    (network, broadcast) = isys.inet_calcNetBroad (self.ip.value (), self.nm.value ())
                except:
                    ButtonChoiceWindow(screen, _("Invalid information"),
                                       _("You must enter valid IP information to continue"),
                                       buttons = [ _("OK") ])
                    continue

                dev.set (("bootproto", "static"))
                dev.set (("ipaddr", self.ip.value ()), ("netmask", self.nm.value ()),
                         ("network", network), ("broadcast", broadcast))
                todo.network.gateway = self.gw.value ()
                todo.network.primaryNS = self.ns.value ()
            screen.popWindow()
            break
                     
        dev.set (("onboot", "yes"))

        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

class HostnameWindow:
    def __call__(self, screen, todo):
        entry = Entry (24)
        if todo.network.hostname != "localhost.localdomain":
            entry.set (todo.network.hostname)
        rc, values = EntryWindow(screen, _("Hostname Configuration"),
             _("The hostname is the name of your computer.  If your "
               "computer is attached to a network, this may be "
               "assigned by your network administrator."),
             [(_("Hostname"), entry)], buttons = [ _("OK"), _("Back")],
	     help = "hostname")

        if rc == string.lower (_("Back")):
            return INSTALL_BACK

        todo.network.hostname = entry.value ()
        
        return INSTALL_OK
