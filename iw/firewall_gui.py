#
# firewall_gui.py: firewall setup screen
#
# Copyright 2001-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import checklist
import gtk
import gui
from iw_gui import *
from isys import *
from rhpl.translate import _, N_

class FirewallWindow (InstallWindow):		

    windowTitle = N_("Firewall")
    htmlTag = "securitylevel"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

    def getNext (self):
        self.security.setSELinux(self.se_option_menu.get_history())
        
        if self.disabled_radio.get_active ():
	    rc2 = self.intf.messageWindow(_("Warning - No Firewall"),
		   _("If this system is attached directly to the Internet or "
		     "is on a large public network, it is recommended that a "
		     "firewall be configured to help prevent unauthorized "
		     "access.  However, you have selected not to "
		     "configure a firewall.  Choose \"Proceed\" to continue "
		     "without a firewall."),
		    type="custom", custom_icon="warning",
		    custom_buttons=[_("_Configure Firewall"), _("_Proceed")])
	    
	    if rc2 == 0:
		raise gui.StayOnScreen
            self.firewall.enabled = 0
        else:
            self.firewall.enabled = 1
            
            count = 0
            self.firewall.trustdevs = []

            for device in self.devices:
                val = self.trusted.get_active(count)
                if val == 1:
                    self.firewall.trustdevs.append(device)
                count = count + 1

            count = 0
            for service in self.knownPorts.keys():
                val = self.incoming.get_active(count)
                if service == "SSH":
                    self.firewall.ssh = val
                elif service == "Telnet":
                    self.firewall.telnet = val
                elif service == "WWW (HTTP)":
                    self.firewall.http = val
                elif service == "Mail (SMTP)":
                    self.firewall.smtp = val
                elif service == "FTP":
                    self.firewall.ftp = val                    
                count = count + 1

            portstring = string.strip(self.ports.get_text())
            portlist = ""
            bad_token_found = 0
            bad_token = ""
            if portstring != "":
                tokens = string.split(portstring, ',')
                for token in tokens:
                    try:
                        #- if there's a colon in the token, it's valid
                        if string.index(token,':'):         
                            parts = string.split(token, ':')
                            try:
                                portnum = string.atoi(parts[0])
                            except:
                                portnum = None

                            if len(parts) > 2: # more than one colon
                                bad_token_found = 1
                                bad_token = token
                            elif portnum is not None and (portnum < 1 or portnum > 65535):
                                bad_token_found = 1
                                bad_token = token
                            else:
                                # udp and tcp are the only valid protos
                                if parts[1] == 'tcp' or parts[1] == 'udp':
                                    if portlist == "":
                                        portlist = token
                                    else:
                                        portlist = portlist + ',' + token
                                else: # found protocol !tcp && !udp
                                    bad_token_found = 1
                                    bad_token = token
                                    pass
                    except:
                        if token != "":
                            try:
                                try:
                                    portnum = string.atoi(token)
                                except:
                                    portnum = None

                                if portnum is not None and (portnum < 1 or portnum > 65535):
                                    bad_token_found = 1
                                    bad_token = token
                                else:
                                    if portlist == "":
                                        portlist = token + ":tcp"
                                    else:
                                        portlist = portlist + ',' + token + ':tcp'
                            except:
                                bad_token_found = 1
                                bad_token = token
            else:
                pass

            if bad_token_found == 1: # raise a warning
                text = _("Invalid port given: %s.  The proper format is "
                         "'port:protocol', where port is between 1 and 65535, and protocol is either 'tcp' or 'udp'.\n\nFor example, "
                         "'1234:udp'") % (bad_token,)
                
                self.intf.messageWindow(_("Warning: Bad Token"),
                                        text, type="warning")
                raise gui.StayOnScreen
            else:                           # all the port data looks good
                self.firewall.portlist = portlist

    def activate_firewall (self, widget):
        if self.disabled_radio.get_active ():
            self.table.set_sensitive(gtk.FALSE)            
        else:
            self.table.set_sensitive(gtk.TRUE)

    def getScreen (self, intf, network, firewall, security):
	self.firewall = firewall
        self.security = security
	self.network = network
        self.intf = intf

        self.devices = self.network.available().keys()
        self.devices.sort()
        
	self.netCBs = {}

        box = gtk.VBox (gtk.FALSE, 5)
        box.set_border_width (5)

        label = gui.WrappingLabel (_("A firewall can help prevent unauthorized access to your computer from the outside world.  Would you like to enable a firewall?"))
        label.set_alignment (0.0, 0)
	label.set_size_request(450, -1)        

        box.pack_start(label, gtk.FALSE)

        vbox = gtk.VBox (gtk.FALSE)

        self.disabled_radio = gtk.RadioButton (None, (_("N_o firewall")))
        self.enabled_radio = gtk.RadioButton (self.disabled_radio,
                                               (_("_Enable firewall")))
        self.custom_radio = gtk.RadioButton (self.disabled_radio,
                                             (_("_Custom firewall")))
        self.disabled_radio.connect("clicked", self.activate_firewall)
        self.custom_radio.connect("clicked", self.activate_firewall)
        self.enabled_radio.connect("clicked", self.activate_firewall)

        vbox.pack_start (self.disabled_radio)
        vbox.pack_start (self.enabled_radio)

        a = gtk.Alignment ()
        a.add (vbox)
        a.set (0.3, 0, 0.7, 1.0)

        box.pack_start (a, gtk.FALSE, 5)

        self.table = gtk.Table (2, 8)
        box.pack_start (self.table, gtk.FALSE, 5)

        y = 0
        label = gtk.Label (_("What services should be allowed to pass through "
                             "the firewall?"))
	label.set_size_request(450, -1)
        label.set_alignment(0.0, 0.0)
        self.table.attach(label, 0, 2, y, y + 1, gtk.EXPAND | gtk.FILL, gtk.FILL, 5, 5)

        y = y + 1
        hbox = gtk.HBox(gtk.FALSE, 10)        
        self.label2 = gui.MnemonicLabel (_("_Allow incoming:"))
        self.label2.set_alignment (0.2, 0.0)
        self.incoming = checklist.CheckList(1)
	self.incoming.set_size_request(-1, 125)
        self.label2.set_mnemonic_widget(self.incoming)

        incomingSW = gtk.ScrolledWindow()
        incomingSW.set_border_width(5)
        incomingSW.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        incomingSW.set_shadow_type(gtk.SHADOW_IN)
        incomingSW.add(self.incoming)
        
#        self.table.attach (self.label2, 0, 1, y, y + 1, gtk.FILL, gtk.FILL, 5, 5)
        self.table.attach (incomingSW, 0, 2, y, y + 1, gtk.EXPAND|gtk.FILL, gtk.FILL, 5, 5)

        self.knownPorts = {"SSH": self.firewall.ssh,
                           "Telnet": self.firewall.telnet,
                           "WWW (HTTP)": self.firewall.http,
                           "Mail (SMTP)": self.firewall.smtp,
                           "FTP": self.firewall.ftp}

        for item in self.knownPorts.keys():
            self.incoming.append_row ((item, ""), self.knownPorts[item])

        y = y + 1
        self.label3 = gui.MnemonicLabel (_("Other _ports:"))
        self.ports = gtk.Entry ()
        self.label3.set_mnemonic_widget(self.ports)

        self.table.attach (self.label3, 0, 1, y, y + 1, gtk.FILL, gtk.FILL, 5, 5)
        self.table.attach (self.ports, 1, 2, y, y + 1, gtk.EXPAND|gtk.FILL, gtk.FILL, 10, 5)
        y = y + 1

        label = gui.WrappingLabel (_("If you would like to allow all traffic "
                                     "from a device, select it below."))
	label.set_size_request(450, -1)        
        label.set_alignment(0, 1)
        self.table.attach(label, 0, 2, y, y + 1,
                     gtk.FILL, gtk.FILL, 5, 5)

        y = y + 1
        hbox = gtk.HBox(gtk.FALSE, 10)
        self.label1 = gui.MnemonicLabel (_("_Trusted devices:"))
        self.label1.set_alignment (0.2, 0.0)

        self.trusted = checklist.CheckList(1)
	self.trusted.set_size_request(-1, 40)
        self.label1.set_mnemonic_widget(self.trusted)

        trustedSW = gtk.ScrolledWindow()
        trustedSW.set_border_width(5)
        trustedSW.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        trustedSW.set_shadow_type(gtk.SHADOW_IN)
        trustedSW.add(self.trusted)

        if self.devices != []:
#           self.table.attach (self.label1, 0, 1, y, y + 1, gtk.FILL, gtk.FILL, 5, 5)
            self.table.attach (trustedSW, 0, 2, y, y + 1, gtk.EXPAND|gtk.FILL, gtk.FILL, 5, 0)

            for device in self.devices:
                if device in self.firewall.trustdevs:
                    self.trusted.append_row ((device, device), gtk.TRUE)
                else:
                    self.trusted.append_row ((device, device), gtk.FALSE)


        y = y + 1

        if self.firewall.enabled == 0:
            self.disabled_radio.set_active (gtk.TRUE)
        else:
            self.enabled_radio.set_active(gtk.TRUE)
            
        if self.firewall.portlist != "":
            self.ports.set_text (self.firewall.portlist)

        self.activate_firewall(None)

        box.pack_start (gtk.HSeparator(), gtk.FALSE)

        label = gtk.Label(_("_Security Enhanced Linux (SELinux) Extensions:"))
        label.set_use_underline(gtk.TRUE)
        self.se_option_menu = gtk.OptionMenu()
        label.set_mnemonic_widget(self.se_option_menu)
        se_menu = gtk.Menu()

        for i in (_("Disabled"), _("Warn"), _("Active")):
            se_menu.add(gtk.MenuItem(i))

        self.se_option_menu.set_menu(se_menu)

        self.se_option_menu.set_history(self.security.getSELinux())
        
        hbox = gtk.HBox()
        hbox.set_spacing(8)
        hbox.pack_start(label, gtk.FALSE)
        hbox.pack_start(self.se_option_menu, gtk.TRUE)

        box.pack_start(hbox, gtk.FALSE)

        return box


