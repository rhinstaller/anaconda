from gtk import *
from iw_gui import *
from isys import *
from translate import _
import checklist

class FirewallWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Firewall Configuration"))
        ics.setNextEnabled (1)
        ics.readHTML ("securitylevel")
        self.todo = ics.getToDo ()
#        self.calcNMHandler = None

#        for dev in self.todo.network.available ().values ():
#	    if not dev.get('onboot'):
#		dev.set (("onboot", "yes"))

    def getNext (self):
#        print self.ports.get_text ()
        
        if self.radio3.get_active ():
#            print "Welcome to crackers"
            self.todo.firewall.enabled = 0
            self.todo.firewall.policy = 1
        else:

            if self.radio1.get_active ():
#                print "We're paranoid"
                self.todo.firewall.policy = 0
                self.todo.firewall.enabled = 1
            elif self.radio2.get_active ():
#                print "We're reasonable"
                self.todo.firewall.policy = 1
                self.todo.firewall.enabled = 1

            if self.radio4.get_active ():
                self.todo.firewallState = 0

            if self.radio5.get_active ():
#                print "Customizing"
                self.todo.firewallState = 1

                count = 0
                for device in self.devices:
#                    print count
                    (val, row_data, header) = self.trusted.get_row_data (count)
#                    print device, val, row_data, header
                    
                    if val == 1:
#                        print "adding ", device
                        self.todo.firewall.trustdevs.append(device)
                    elif val == 0:
#                        print "need to remove ", device
                        pass
                    
                    count = count + 1


                for i in range(6):
                    (val, row_data, header) = self.incoming.get_row_data (i)
#                    print val, row_data, header

                    if row_data == "DHCP":
                        self.todo.firewall.dhcp = val
                    elif row_data == "SSH":
                        self.todo.firewall.ssh = val
                    elif row_data == "Telnet":
                        self.todo.firewall.telnet = val
                    elif row_data == "WWW (HTTP)":
                        self.todo.firewall.http = val
                    elif row_data == "Mail (SMTP)":
                        self.todo.firewall.smtp = val
                    elif row_data == "FTP":
                        self.todo.firewall.ftp = val
                    
                self.todo.firewall.portlist = self.ports.get_text()    

#                print "self.todo.firewall.dhcp", self.todo.firewall.dhcp 
#                print "self.todo.firewall.ssh", self.todo.firewall.ssh 
#                print "self.todo.firewall.telnet", self.todo.firewall.telnet
#                print "self.todo.firewall.http", self.todo.firewall.http
#                print "self.todo.firewall.smtp", self.todo.firewall.smtp
#                print "self.todo.firewall.ftp", self.todo.firewall.ftp

#                    self.packageList.set_row_data (i, (TRUE, row_data, header)) 
#                    self.packageList._update_row (i)
                    

#                print "self.todo.firewall.portlist", self.todo.firewall.portlist

#        print "self.todo.firewall.policy", self.todo.firewall.policy
#        print "self.todo.firewall.enabled", self.todo.firewall.enabled 
        
#        self.radio2 = GtkRadioButton (self.radio1, (_("Medium")))
#        self.radio3
        self.todo.firewall.portlist = self.ports.get_text () 



    def activate_firewall (self, widget):
        if self.radio3.get_active ():            
            active = not (self.radio3.get_active())

            self.radio4.set_sensitive (active)
            self.radio5.set_sensitive (active)        
            self.trusted.set_sensitive(active)
            self.incoming.set_sensitive(active)
            self.ports.set_sensitive(active)
            self.label1.set_sensitive(active)
            self.label2.set_sensitive(active)
            self.label3.set_sensitive(active)
        else:
            self.radio4.set_sensitive (TRUE)
            self.radio5.set_sensitive (TRUE) 

            if self.radio5.get_active ():
                self.trusted.set_sensitive(self.radio5.get_active())
                self.incoming.set_sensitive(self.radio5.get_active())
                self.ports.set_sensitive(self.radio5.get_active())
                self.label1.set_sensitive(self.radio5.get_active())
                self.label2.set_sensitive(self.radio5.get_active())
                self.label3.set_sensitive(self.radio5.get_active())

            else:
                self.trusted.set_sensitive(self.radio5.get_active())
                self.incoming.set_sensitive(self.radio5.get_active())
                self.ports.set_sensitive(self.radio5.get_active())
                self.label1.set_sensitive(self.radio5.get_active())
                self.label2.set_sensitive(self.radio5.get_active())
                self.label3.set_sensitive(self.radio5.get_active())

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
            
    def getScreen (self):
        self.devices = self.todo.network.available().keys()
        self.devices.sort()
        
	self.netCBs = {}

        box = GtkVBox (FALSE, 5)
        box.set_border_width (5)

        label = GtkLabel (_("Please choose your security level:  "))
        label.set_alignment (0.0, 0.5)

        label.set_line_wrap (TRUE)
        
        box.pack_start(label, FALSE)

        hbox = GtkHBox (FALSE)

        self.radio1 = GtkRadioButton (None, (_("High")))
        self.radio2 = GtkRadioButton (self.radio1, (_("Medium")))
        self.radio3 = GtkRadioButton (self.radio1, (_("No firewall")))

        self.radio3.connect ("clicked", self.activate_firewall)

        hbox.pack_start (self.radio1)
        hbox.pack_start (self.radio2)
        hbox.pack_start (self.radio3)

        a = GtkAlignment ()
        a.add (hbox)
        a.set (1.0, 0.5, 0.7, 1.0)

        box.pack_start (a, FALSE)

        hsep = GtkHSeparator ()
        box.pack_start (hsep, FALSE)

        self.radio4 = GtkRadioButton (None, (_("Use default firewall rules")))
        self.radio5 = GtkRadioButton (self.radio4, (_("Customize")))
        self.radio4.set_active (TRUE)

        self.radio4.connect ("clicked", self.activate_firewall)
        self.radio5.connect ("clicked", self.activate_firewall)
        
        box.pack_start (self.radio4, FALSE)
        box.pack_start (self.radio5, FALSE)

        table = GtkTable (2, 3)
        box.pack_start (table)

        hbox = GtkHBox(FALSE, 10)
        self.label1 = GtkLabel (_("Trusted devices:"))
        self.label1.set_alignment (0.2, 0.0)
        self.trusted = checklist.CheckList(1)
        self.trusted.connect ('button_press_event', self.trusted_select_row)
        self.trusted.connect ("key_press_event", self.trusted_key_press)

        table.attach (self.label1, 0, 1, 0, 1, FILL, FILL, 5, 5)
        table.attach (self.trusted, 1, 2, 0, 1, EXPAND|FILL, FILL, 5, 5)


        
        count = 0
        for device in self.devices:
            if self.todo.firewall.trustdevs == []:
                self.trusted.append_row ((device, device), FALSE)
            else:
                if self.todo.firewall.trustdevs.index(device) >= 0:
                    self.trusted.append_row ((device, device), TRUE)

            count = count + 1

        #--Need
#        for device in self.netCBs.keys():
#            if self.netCBs[device].selected():
#                print "here"
#                self.trusted.append_row ((device, device), FALSE)


#        self.trusted.append_row (("cipcb0", ""), FALSE)
#        self.trusted.append_row (("wvlan0", ""), FALSE)

        hbox = GtkHBox(FALSE, 10)        
        self.label2 = GtkLabel (_("Allow incoming:"))
        self.label2.set_alignment (0.2, 0.0)
        self.incoming = checklist.CheckList(1)
        self.incoming.connect ('button_press_event', self.incoming_select_row)
        self.incoming.connect ("key_press_event", self.incoming_key_press)
        table.attach (self.label2, 0, 1, 1, 2, FILL, FILL, 5, 5)
        table.attach (self.incoming, 1, 2, 1, 2, EXPAND|FILL, FILL, 5, 5)

        self.list = ["DHCP", "SSH", "Telnet", "WWW (HTTP)", "Mail (SMTP)", "FTP"]

        count = 0
        for item in self.list:
            self.incoming.append_row ((item, ""), FALSE)

            if item == "DHCP":
                self.incoming.set_row_data (count, (self.todo.firewall.dhcp, item, item)) 
            elif item == "SSH":
                self.incoming.set_row_data (count, (self.todo.firewall.ssh, item, item)) 
            elif item == "Telnet":
                self.incoming.set_row_data (count, (self.todo.firewall.telnet, item, item)) 
            elif item == "WWW (HTTP)":
                self.incoming.set_row_data (count, (self.todo.firewall.http, item, item)) 
            elif item == "Mail (SMTP)":
                self.incoming.set_row_data (count, (self.todo.firewall.smtp, item, item)) 
            elif item == "FTP":
                self.incoming.set_row_data (count, (self.todo.firewall.ftp, item, item)) 

            count = count + 1

        self.label3 = GtkLabel (_("Other ports:"))
        self.ports = GtkEntry ()

        table.attach (self.label3, 0, 1, 2, 3, FILL, FILL, 5, 5)
        table.attach (self.ports, 1, 2, 2, 3, EXPAND|FILL, FILL, 5, 5)

#        print self.todo.firewall.policy


        if self.todo.firewall.enabled == 0:
            self.radio3.set_active (TRUE)
        elif self.todo.firewall.policy == 0:
            self.radio1.set_active (TRUE)
        elif self.todo.firewall.policy == 1:
            self.radio2.set_active (TRUE)

        if self.todo.firewallState == 1:
            self.radio5.set_active(TRUE)

        else:
            self.trusted.set_sensitive(FALSE)
            self.incoming.set_sensitive(FALSE)
            self.ports.set_sensitive(FALSE)
            self.label1.set_sensitive(FALSE)
            self.label2.set_sensitive(FALSE)
            self.label3.set_sensitive(FALSE)


        return box

