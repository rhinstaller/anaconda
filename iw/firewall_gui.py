#
# firewall_gui.py: firewall setup screen
#
# Copyright 2001 Red Hat, Inc.
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
from iw_gui import *
from isys import *
from translate import _, N_

class FirewallWindow (InstallWindow):		

    windowTitle = N_("Firewall Configuration")
    htmlTag = "securitylevel"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

    def getNext (self):
        if not self.__dict__.has_key("sec_none_radio"):
            return None

        if self.sec_none_radio.get_active ():
            self.firewall.enabled = 0
            self.firewall.policy = 1
        else:

            if self.sec_high_radio.get_active ():
                self.firewall.policy = 0
                self.firewall.enabled = 1
            elif self.sec_med_radio.get_active ():
                self.firewall.policy = 1
                self.firewall.enabled = 1

            if self.default_radio.get_active ():
                self.firewallState = 0

            if self.custom_radio.get_active ():
                self.firewallState = 1
                count = 0
                self.firewall.trustdevs = []

                for device in self.devices:
                    (val, row_data, header) = self.trusted.get_row_data (count)

                    if val == 1:
                        self.firewall.trustdevs.append(device)

                    count = count + 1

                for i in range(6):
                    (val, row_data, header) = self.incoming.get_row_data (i)

                    if row_data == "DHCP":
                        self.firewall.dhcp = val
                    elif row_data == "SSH":
                        self.firewall.ssh = val
                    elif row_data == "Telnet":
                        self.firewall.telnet = val
                    elif row_data == "WWW (HTTP)":
                        self.firewall.http = val
                    elif row_data == "Mail (SMTP)":
                        self.firewall.smtp = val
                    elif row_data == "FTP":
                        self.firewall.ftp = val
                    
                portstring = string.strip(self.ports.get_text())
                portlist = ""
                bad_token_found = 0
                bad_token = ""
                if portstring != "":
                    tokens = string.split(portstring, ',')
                    for token in tokens:
                        try:
                            if string.index(token,':'):         #- if there's a colon in the token, it's valid
                                parts = string.split(token, ':')
                                if len(parts) > 2:              #- We've found more than one colon.  Break loop and raise an error.
                                    bad_token_found = 1
                                    bad_token = token
                                else:
                                    if parts[1] == 'tcp' or parts[1] == 'udp':  #-upd and tcp are the only valid protocols
                                        if portlist == "":
                                            portlist = token
                                        else:
                                            portlist = portlist + ',' + token
                                    else:                        #- Found a protocol other than tcp or udp.  Break loop
                                        bad_token_found = 1
                                        bad_token = token
                                        pass
                        except:
                            if token != "":
                                if portlist == "":
                                    portlist = token + ":tcp"
                                else:
                                    portlist = portlist + ',' + token + ':tcp'

                else:
                    pass

                if bad_token_found == 1:         #- We've found a bad token...raise a warning
                    from gnome.ui import *
                    import gui
                    self.textWin = GnomeDialog ()
                    self.textWin.set_modal (gtk.TRUE)

                    vbox = gtk.VBox()
                    hbox = gtk.HBox()

                    hbox.pack_start (GnomePixmap ('/usr/share/pixmaps/gnome-warning.png'), gtk.FALSE)
                    self.textWin.vbox.pack_start(hbox)
                    hbox.pack_start(vbox)
                    

                    
                    self.textWin.set_default_size (500, 200)
                    self.textWin.set_usize (500, 200)
                    self.textWin.set_position (WIN_POS_CENTER)

                    label = gtk.Label((_("Warning: ")) + bad_token + (_(" is an invalid port.")))
                    vbox.pack_start(label)

                    label = gtk.Label(_("The format is 'port:protocol'.  For example, '1234:udp'"))
                    vbox.pack_start(label)
                    
                    self.textWin.append_button(_("Close"))
                    self.textWin.button_connect (0, self.textWin.destroy)

                    self.textWin.set_border_width(0)
                    self.textWin.show_all()

                    raise gui.StayOnScreen
                else:                           # all the port data looks good
                    self.firewall.portlist = portlist
        

    def activate_firewall (self, widget):
        if self.sec_none_radio.get_active ():            
            active = not (self.sec_none_radio.get_active())

            self.default_radio.set_sensitive (active)
            self.custom_radio.set_sensitive (active)        
            self.trusted.set_sensitive(active)
            self.incoming.set_sensitive(active)
            self.ports.set_sensitive(active)
            self.label1.set_sensitive(active)
            self.label2.set_sensitive(active)
            self.label3.set_sensitive(active)
        else:
            self.default_radio.set_sensitive (gtk.TRUE)
            self.custom_radio.set_sensitive (gtk.TRUE) 

            if self.custom_radio.get_active ():
                self.trusted.set_sensitive(self.custom_radio.get_active())
                self.incoming.set_sensitive(self.custom_radio.get_active())
                self.ports.set_sensitive(self.custom_radio.get_active())
                self.label1.set_sensitive(self.custom_radio.get_active())
                self.label2.set_sensitive(self.custom_radio.get_active())
                self.label3.set_sensitive(self.custom_radio.get_active())

            else:
                self.trusted.set_sensitive(self.custom_radio.get_active())
                self.incoming.set_sensitive(self.custom_radio.get_active())
                self.ports.set_sensitive(self.custom_radio.get_active())
                self.label1.set_sensitive(self.custom_radio.get_active())
                self.label2.set_sensitive(self.custom_radio.get_active())
                self.label3.set_sensitive(self.custom_radio.get_active())

    def trusted_select_row(self, clist, event):
        try:
            row, col  = self.trusted.get_selection_info (event.x, event.y)
            self.toggle_row(self.trusted, row)
        except:
            pass

    def incoming_select_row(self, clist, event):
        try:
            row, col  = self.incoming.get_selection_info (event.x, event.y)
            self.toggle_row(self.incoming, row)
        except:
            pass    
        
        
    def trusted_key_press (self, list, event):
        if event.keyval == ord(" ") and self.trusted.focus_row != -1:
            self.toggle_row (self.trusted, self.trusted.focus_row)

    def incoming_key_press (self, list, event):
        if event.keyval == ord(" ") and self.incoming.focus_row != -1:
            self.toggle_row (self.incoming, self.incoming.focus_row)        

    def toggle_row (self, list, row):
        (val, row_data, header) = list.get_row_data(row)
        val = not val
        list.set_row_data(row, (val, row_data, header))
        list._update_row (row)
            
    def getScreen (self, network, firewall):
	self.firewall = firewall
	self.network = network

        self.devices = self.network.available().keys()
        self.devices.sort()
        
	self.netCBs = {}

        box = gtk.VBox (gtk.FALSE, 5)
        box.set_border_width (5)

        label = gtk.Label (_("Please choose your security level:  "))
        label.set_alignment (0.0, 0.5)

        label.set_line_wrap (gtk.TRUE)
        
        box.pack_start(label, gtk.FALSE)

        hbox = gtk.HBox (gtk.FALSE)

        self.sec_high_radio = gtk.RadioButton (None, (_("High")))
        self.sec_med_radio = gtk.RadioButton (self.sec_high_radio, (_("Medium")))
        self.sec_none_radio = gtk.RadioButton (self.sec_high_radio, (_("No firewall")))
        self.sec_none_radio.connect ("clicked", self.activate_firewall)

        hbox.pack_start (self.sec_high_radio)
        hbox.pack_start (self.sec_med_radio)
        hbox.pack_start (self.sec_none_radio)

        a = gtk.Alignment ()
        a.add (hbox)
        a.set (1.0, 0.5, 0.7, 1.0)

        box.pack_start (a, gtk.FALSE)

        hsep = gtk.HSeparator ()
        box.pack_start (hsep, gtk.FALSE)

        self.default_radio = gtk.RadioButton (None, (_("Use default firewall rules")))
        self.custom_radio = gtk.RadioButton (self.default_radio, (_("Customize")))
        self.default_radio.set_active (gtk.TRUE)

        self.default_radio.connect ("clicked", self.activate_firewall)
        self.custom_radio.connect ("clicked", self.activate_firewall)
        
        box.pack_start (self.default_radio, gtk.FALSE)
        box.pack_start (self.custom_radio, gtk.FALSE)

        table = gtk.Table (2, 3)
        box.pack_start (table)

        hbox = gtk.HBox(gtk.FALSE, 10)
        self.label1 = gtk.Label (_("Trusted devices:"))
        self.label1.set_alignment (0.2, 0.0)
        self.trusted = checklist.CheckList(1)
        self.trusted.connect ('button_press_event', self.trusted_select_row)
        self.trusted.connect ("key_press_event", self.trusted_key_press)

        if self.devices != []:
            table.attach (self.label1, 0, 1, 0, 1, gtk.FILL, gtk.FILL, 5, 5)
            table.attach (self.trusted, 1, 2, 0, 1, gtk.EXPAND|gtk.FILL, gtk.FILL, 5, 5)

            count = 0
            for device in self.devices:
                if self.firewall.trustdevs == []:
                    self.trusted.append_row ((device, device), gtk.FALSE)
                else:
                    if device in self.firewall.trustdevs:
                        self.trusted.append_row ((device, device), gtk.TRUE)
                    else:
                        self.trusted.append_row ((device, device), gtk.FALSE)
                if self.network.netdevices[device].get('bootproto') == 'dhcp':
                    self.firewall.dhcp = 1

            count = count + 1

        hbox = gtk.HBox(gtk.FALSE, 10)        
        self.label2 = gtk.Label (_("Allow incoming:"))
        self.label2.set_alignment (0.2, 0.0)
        self.incoming = checklist.CheckList(1)
        self.incoming.connect ('button_press_event', self.incoming_select_row)
        self.incoming.connect ("key_press_event", self.incoming_key_press)
        table.attach (self.label2, 0, 1, 1, 2, gtk.FILL, gtk.FILL, 5, 5)
        table.attach (self.incoming, 1, 2, 1, 2, gtk.EXPAND|gtk.FILL, gtk.FILL, 5, 5)

        self.list = ["DHCP", "SSH", "Telnet", "WWW (HTTP)", "Mail (SMTP)", "FTP"]

        count = 0
        for item in self.list:
            self.incoming.append_row ((item, ""), gtk.FALSE)

            if item == "DHCP":
                self.incoming.set_row_data (count, (self.firewall.dhcp, item, item)) 
            elif item == "SSH":
                self.incoming.set_row_data (count, (self.firewall.ssh, item, item)) 
            elif item == "Telnet":
                self.incoming.set_row_data (count, (self.firewall.telnet, item, item)) 
            elif item == "WWW (HTTP)":
                self.incoming.set_row_data (count, (self.firewall.http, item, item)) 
            elif item == "Mail (SMTP)":
                self.incoming.set_row_data (count, (self.firewall.smtp, item, item)) 
            elif item == "FTP":
                self.incoming.set_row_data (count, (self.firewall.ftp, item, item)) 

            count = count + 1

        self.label3 = gtk.Label (_("Other ports:"))
        self.ports = gtk.Entry ()

        table.attach (self.label3, 0, 1, 2, 3, gtk.FILL, gtk.FILL, 5, 5)
        table.attach (self.ports, 1, 2, 2, 3, gtk.EXPAND|gtk.FILL, gtk.FILL, 5, 5)

        if self.firewall.enabled == 0:
            self.sec_none_radio.set_active (gtk.TRUE)
        elif self.firewall.policy == 0:
            self.sec_high_radio.set_active (gtk.TRUE)
        elif self.firewall.policy == 1:
            self.sec_med_radio.set_active (gtk.TRUE)

        if self.firewall.portlist != "":
            self.ports.set_text (self.firewall.portlist)

        if self.firewall.custom == 1:
            self.custom_radio.set_active(gtk.TRUE)
        else:
            self.trusted.set_sensitive(gtk.FALSE)
            self.incoming.set_sensitive(gtk.FALSE)
            self.ports.set_sensitive(gtk.FALSE)
            self.label1.set_sensitive(gtk.FALSE)
            self.label2.set_sensitive(gtk.FALSE)
            self.label3.set_sensitive(gtk.FALSE)

        return box


