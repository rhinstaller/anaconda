from gtk import *
from iw_gui import *
from isys import *
from translate import _

class NetworkWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Network Configuration"))
        ics.setNextEnabled (1)
        ics.readHTML ("netconf")
        self.todo = ics.getToDo ()
        self.calcNMHandler = None

        for dev in self.todo.network.available ().values ():
	    if not dev.get('onboot'):
		dev.set (("onboot", "yes"))

    def getNext (self):
	if not self.__dict__.has_key("gw"):
	    return None
        self.todo.network.gateway = self.gw.get_text ()
        self.todo.network.primaryNS = self.ns.get_text ()
        self.todo.network.secondaryNS = self.ns2.get_text ()
        self.todo.network.ternaryNS = self.ns3.get_text ()


        if (self.hostname.get_text () != ""):
            self.todo.network.hostname = self.hostname.get_text ()
            
        return None

    def focusInIP (self, widget, event, (ip, nm)):
        if nm.get_text() == "":
            self.calcNetmask (None, (ip, nm))
            
        ip.calcNMHandler = ip.connect ("changed", self.calcNetmask, (ip, nm))
        
    def focusOutIP (self, widget, event, ip):
        if (self.hostname.get_text () == ""
            and self.todo.network.hostname != "localhost.localdomain"):

            hs = self.todo.network.hostname
            tmp = string.split(hs, ".")

            self.hostname.set_text (tmp[0])
            count = 0
            domain = ""
            for token in tmp:
                if count == 0:
                    pass
                elif count == 1:
                    domain = domain + token
                else:
                    domain = domain + "." + token
                count = count + 1

            self.domainname.set_text (domain)

#            self.hostname.set_text (self.todo.network.hostname)

        if ip.calcNMHandler != None:
            ip.disconnect (ip.calcNMHandler)
            ip.calcNMHandler = None

    def focusOutNM (self, widget, event, (dev, ip, nm, nw, bc)):
        try:
            network, broadcast = inet_calcNetBroad (ip.get_text (), nm.get_text ())
            if nw.get_text () == "":
                nw.set_text (network)
                dev.set (("network", network))
            if bc.get_text () == "":
                bc.set_text (broadcast)
                dev.set (("broadcast", broadcast))
        except:
            pass

    def focusOutBC (self, widget, event, dev):
        if self.gw.get_text () == "":
            try:
                gw = inet_calcGateway (widget.get_text ())
                self.gw.set_text (gw)
            except:
                pass

    def focusOutNW (self, widget, event, dev):
        if self.ns.get_text () == "":
            try:
                ns = inet_calcNS (widget.get_text ())
                self.ns.set_text (ns)
            except:
                pass
            
    # not currently used
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

        
    def calcNetmask (self, widget, (ip, nm)):
        ip = ip.get_text ()
        dots = 0
        valid_list = [ "1", "2", "3", "4", "5", "6", "7", "8" , "9", "0", "." ]
        valid_ip = TRUE

        for x in ip:
            if x == '.':
                dots = dots + 1
            if x not in valid_list:        #-if there's an invalid char in the widget, don't calculate netmask
                print "found invalid char"
                valid_ip = FALSE
        if dots != 3: return

        if valid_ip == TRUE:
            new_nm = inet_calcNetmask (ip)
            if (new_nm != nm.get_text ()):
                nm.set_text (new_nm)

    def DHCPtoggled (self, widget, (dev, table)):
	active = widget.get_active ()
        table.set_sensitive (not active)
        self.ipTable.set_sensitive (not active)
	
	bootproto = "dhcp"
	if not active:
            bootproto = "static"
	dev.set (("bootproto", bootproto))

    def onBootToggled (self, widget, dev):
	if widget.get_active ():
	    onboot = "yes"
	else:
	    onboot = "no"
	dev.set (("onboot", onboot))


    # NetworkWindow tag="netconf"
    def getScreen (self):
        box = GtkVBox ()
        box.set_border_width (5)
        
        notebook = GtkNotebook ()
        devs = self.todo.network.available ()
        if not devs: return None

        devs.keys ().sort ()
        for i in devs.keys ():
            devbox = GtkVBox ()
            align = GtkAlignment ()
            DHCPcb = GtkCheckButton (_("Configure using DHCP"))

            align.add (DHCPcb)
            devbox.pack_start (align, FALSE)

            align = GtkAlignment ()
            bootcb = GtkCheckButton (_("Activate on boot"))
            bootcb.set_active (devs[i].get ("onboot") == "yes")
	    bootcb.connect ("toggled", self.onBootToggled, devs[i])
            align.add (bootcb)

            devbox.pack_start (align, FALSE)

            devbox.pack_start (GtkHSeparator (), FALSE, padding=3)

            options = [(_("IP Address"), "ipaddr"),
                       (_("Netmask"),    "netmask"),
                       (_("Network"),    "network"),
                       (_("Broadcast"),  "broadcast") ]
            ipTable = GtkTable (len (options), 2)
            self.ipTable = GtkTable (len (options), 2) # this is the iptable used for DNS, et. al

            DHCPcb.connect ("toggled", self.DHCPtoggled, (devs[i], ipTable))
#            DHCPcb.set_active (devs[i].get ("bootproto") == "dhcp")
            DHCPcb.set_active (TRUE)

            forward = lambda widget, box=box: box.focus (DIR_TAB_FORWARD)

            for t in range (len (options)):
                label = GtkLabel ("%s:" % (options[t][0],))
                label.set_alignment (0.0, 0.5)
                ipTable.attach (label, 0, 1, t, t+1, FILL, 0, 10)
                entry = GtkEntry (15)
                # entry.set_usize (gdk_char_width (entry.get_style ().font, '0')*15, -1)
                entry.set_usize (7 * 15, -1)
                entry.connect ("activate", forward)

                entry.set_text (devs[i].get (options[t][1]))
                options[t] = entry
                ipTable.attach (entry, 1, 2, t, t+1, 0, FILL|EXPAND)

            for t in range (len (options)):
                if t == 0 or t == 1:
                    options[t].connect ("changed", self.calcNWBC, (devs[i],) + tuple (options))

            options[0].ipCalcNMHandler = None
            
            self.focusOutNM (None, None, (devs[i],) + tuple (options))

            # add event handlers for the main IP widget to calcuate the netmask
            options[0].connect ("focus_in_event", self.focusInIP, (options[0], options[1]))
            options[0].connect ("focus_out_event", self.focusOutIP, options[0])
            options[1].connect ("focus_out_event", self.focusOutNM, (devs[i],) + tuple (options))
            options[2].connect ("focus_out_event", self.focusOutNW, devs[i])
            options[3].connect ("focus_out_event", self.focusOutBC, devs[i])

            devbox.pack_start (ipTable, FALSE, FALSE, 5)

            devbox.show_all ()
            notebook.append_page (devbox, GtkLabel (i))

        box.pack_start (notebook, FALSE)
        box.pack_start (GtkHSeparator (), FALSE, padding=10)

        options = [_("Hostname"),
                   _("Gateway"), _("Primary DNS"), _("Secondary DNS"), _("Ternary DNS")]

        for i in range (len (options)):
            label = GtkLabel ("%s:" % (options[i],))
            label.set_alignment (0.0, 0.0)
            self.ipTable.attach (label, 0, 1, i, i+1, FILL, 0, 10)
            if i == 0:
                options[i] = GtkEntry ()
                options[i].set_usize (7 * 30, -1)
            else:
                options[i] = GtkEntry (15)
                options[i].set_usize (7 * 15, -1)
            options[i].connect ("activate", forward)
            align = GtkAlignment (0, 0.5)
            align.add (options[i])
            self.ipTable.attach (align, 1, 2, i, i+1, FILL, 0)
        self.ipTable.set_row_spacing (0, 5)

        self.hostname = options[0]

        # bring over the value from the loader
        if (self.todo.network.hostname != "localhost.localdomain"):
            self.hostname.set_text (self.todo.network.hostname)

        self.gw = options[1]
        self.gw.set_text (self.todo.network.gateway)

        self.ns = options[2]
        self.ns.set_text (self.todo.network.primaryNS)

        self.ns2 = options[3]
        self.ns2.set_text (self.todo.network.secondaryNS)

        self.ns3 = options[4]
        self.ns3.set_text (self.todo.network.ternaryNS)
        box.pack_start (self.ipTable, FALSE, FALSE, 5)
        return box

