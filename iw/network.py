from gtk import *
from iw import *
from isys import *
from gui import _

class NetworkWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Network Configuration")
        ics.setNextEnabled (1)
        self.todo = ics.getToDo ()
        self.calcNMHandler = None


#    def getNext (self):
#        self.setupTODO ()
#        return None

    def focusInIP (self, *args):
        if self.nm.get_text() == "":
            self.calcNetmask ()
            self.calcNMHandler = self.ip.connect ("changed", self.calcNetmask)

    def focusOutIP (self, *args):
        if self.calcNMHandler != None:
            self.ip.disconnect (self.calcNMHandler)
            self.calcNMHandler = None
        

    def setupTODO (self):
        if self.devs:
            if self.DHCPcb.get_active ():
                self.dev.set (("bootproto", "dhcp"))
                self.dev.unset ("ipaddr", "netmask", "network", "broadcast")
            else:
                try:
                    network, broadcast = inet_calcNetBroad (self.ip.get_text (), self.nm.get_text ())
                    self.dev.set (("bootproto", "static"))
                    self.dev.set (("ipaddr", self.ip.get_text ()), ("netmask", self.nm.get_text ()),
                                  ("network", network), ("broadcast", broadcast), ("onboot", "yes"))
                    self.todo.network.gateway = self.gw.get_text ()
                    self.todo.network.primaryNS = self.dns1.get_text ()
                    self.todo.network.guessHostnames ()
                except:
                    pass
            
                self.dev.set (("onboot", "yes"))


    def calcNWBC (self, widget, (dev, ip, nm, nw, bc)):
        for addr in (ip, nm):
            dots = 0
            for ch in addr.get_text ():
                if ch == '.':
                    dots = dots + 1
            if dots != 3: return

        dev.set (("ipaddr", ip.get_text ()))
        dev.set (("netmask", nm.get_text ()))

        try:
            network, broadcast = inet_calcNetBroad (ip.get_text (), nm.get_text ())
        except:
            if nw.get_text () != "":
                nw.set_text ("")
            if bc.get_text () != "":
                bc.set_text ("")
            return
        if network != nw.get_text ():
            nw.set_text (network)
            dev.set (("network", network))
        if broadcast != bc.get_text ():
            bc.set_text (broadcast)
            dev.set (("broadcast", broadcast))
        
    def calcNetmask (self, *args):
        ip = self.ip.get_text ()
        dots = 0
        for x in ip:
            if x == '.':
                dots = dots + 1
        if dots != 3: return

        new_nm = inet_calcNetmask (self.ip.get_text ())
        if (new_nm != self.nm.get_text ()):
            self.nm.set_text (new_nm)

    def calcHostname (self, box):
        box.focus (DIR_TAB_FORWARD)
        
        self.dev.set (("ipaddr", self.ip.get_text (),))
        self.todo.network.guessHostnames ()
        if (self.todo.network.hostname != "localhost.localdomain"
            and self.todo.network.hostname != self.hostname.get_text ()):
            self.hostname.set_text (self.todo.network.hostname)

    def devSelected (self, widget, key):
        self.setupTODO ()
        self.dev = self.devs[key]
        if self.dev.get ("bootproto") == "dhcp":
            self.DHCPcb.set_active (TRUE)
            self.ip.set_text ("")
            self.nm.set_text ("")
        else:
            self.DHCPcb.set_active (FALSE)
            self.ip.set_text (self.dev.get ("ipaddr"))
            self.nm.set_text (self.dev.get ("netmask"))

    def getScreen (self):
	hostnameBox = GtkHBox (FALSE)
	label = GtkLabel ("System Hostname: ")
	label.set_alignment (0.0, 0.0)
	hostnameBox.pack_start (label, FALSE)
	self.hostname = GtkEntry ()
	hostnameBox.pack_start (self.hostname, TRUE)

        box = GtkVBox ()
	box.pack_start (hostnameBox, FALSE)
        box.pack_start (GtkHSeparator (), FALSE, padding=3)

        notebook = GtkNotebook ()
        self.devs = self.todo.network.available ()
	print self.devs
        if self.devs:
            self.devs.keys ().sort ()
            for i in self.devs.keys ():
                devbox = GtkVBox ()
                align = GtkAlignment ()
                DHCPcb = GtkCheckButton (_("Configure using DHCP"))
#                DHCPcb.connect ("toggled", devs[i])
                DHCPcb.set_active (TRUE)
                align.add (DHCPcb)
                devbox.pack_start (align, FALSE)
                
                align = GtkAlignment ()
                bootcb = GtkCheckButton (_("Activate on boot"))
                bootcb.set_active (TRUE)
                align.add (bootcb)

                devbox.pack_start (align, FALSE)

                devbox.pack_start (GtkHSeparator (), FALSE, padding=3)

                options = [_("IP Address"), _("Netmask"), _("Network"), _("Broadcast")]
                ipTable = GtkTable (2, len (options))

		forward = lambda widget, box=box: box.focus (DIR_TAB_FORWARD)

                for t in range (len (options)):
                    label = GtkLabel ("%s:" % (options[t],))
                    label.set_alignment (0.0, 0.0)
                    ipTable.attach (label, 0, 1, t, t+1, FILL, 0, 10)
                    entry = GtkEntry (15)
#                    entry.set_usize (gdk_char_width (entry.get_style ().font, '0')*15, -1)
                    entry.set_usize (7 * 15, -1)
                    entry.connect ("activate", forward)
                    options[t] = entry
                    ipTable.attach (entry, 1, 2, t, t+1, 0, 0)

                for t in range (len (options)):
                    if t == 0 or t == 1:
                        options[t].connect ("changed", self.calcNWBC, (self.devs[i],) + tuple (options))
                    else:
                        options[t].set_sensitive (FALSE)

#                self.ip.connect ("focus_in_event", self.focusInIP)
#                self.ip.connect ("focus_out_event", self.focusOutIP)
#                self.ip.connect ("activate", 
#                self.nm.connect ("activate", lambda widget, box=box: box.focus (DIR_TAB_FORWARD))
                devbox.pack_start (ipTable, FALSE, FALSE, 5)
                notebook.append_page (devbox, GtkLabel (i))

            box.pack_start (notebook, FALSE)

            box.pack_start (GtkHSeparator (), FALSE, padding=3)
        
            ipTable = GtkTable (5, 2)
            ipTable.attach (GtkLabel (_("Gateway: ")), 0, 1, 0, 1)
            ipTable.attach (GtkLabel (_("Primary DNS: ")), 0, 1, 2, 3)
            ipTable.attach (GtkLabel (_("Secondary DNS: ")), 0, 1, 3, 4)
            ipTable.attach (GtkLabel (_("Ternary DNS: ")), 0, 1, 4, 5)
            self.gw = GtkEntry (15)
            self.gw.connect ("activate", lambda widget, box=box, self=self: self.calcHostname (box))
            self.dns1 = GtkEntry (15)
            self.dns1.connect ("activate", forward)
            self.dns2 = GtkEntry (15)
            self.dns2.connect ("activate", forward)
            self.dns3 = GtkEntry (15)
            ipTable.attach (self.gw, 1, 2, 0, 1)
            ipTable.attach (self.dns1, 1, 2, 2, 3)
            ipTable.attach (self.dns2, 1, 2, 3, 4)
            ipTable.attach (self.dns3, 1, 2, 4, 5)
            box.pack_start (ipTable, FALSE)

        
        return box

    
