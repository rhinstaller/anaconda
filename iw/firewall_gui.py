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


    def activate (self, widget, args):
#        print "Inside activate"
#        print self.radio4.get_active()

        self.trusted.set_sensitive(self.radio5.get_active())
        self.incoming.set_sensitive(self.radio5.get_active())
        self.ports.set_sensitive(self.radio5.get_active())
        self.label1.set_sensitive(self.radio5.get_active())
        self.label2.set_sensitive(self.radio5.get_active())
        self.label3.set_sensitive(self.radio5.get_active())

            
    def getScreen (self):
        box = GtkVBox (FALSE, 5)
        box.set_border_width (5)

        label = GtkLabel (_("Please choose your level of security.  "))
        label.set_alignment (0.2, 0.5)

        label.set_line_wrap (TRUE)
        
        box.pack_start(label, FALSE)

        hbox = GtkHBox ()

        label = GtkLabel (_("Security level:"))

        hbox.pack_start(label)

        radio1 = GtkRadioButton (None, (_("High")))
        radio2 = GtkRadioButton (radio1, (_("Medium")))
        radio3 = GtkRadioButton (radio1, (_("None")))

        hbox.pack_start (radio1)
        hbox.pack_start (radio2)
        hbox.pack_start (radio3)

        box.pack_start (hbox, FALSE)

        hsep = GtkHSeparator ()
        box.pack_start (hsep, FALSE)

        self.radio4 = GtkRadioButton (None, (_("Use default firewall rules")))
        self.radio5 = GtkRadioButton (self.radio4, (_("Customize")))
        self.radio4.set_active (TRUE)

        self.radio4.connect ("draw", self.activate)
        self.radio4.connect ("clicked", self.activate, None)
        self.radio5.connect ("clicked", self.activate, None)
        
        box.pack_start (self.radio4, FALSE)
        box.pack_start (self.radio5, FALSE)


        table = GtkTable (2, 3)
        box.pack_start (table)

        hbox = GtkHBox(FALSE, 10)
        self.label1 = GtkLabel (_("Trusted devices:"))
        self.label1.set_alignment (0.2, 0.0)
        self.trusted = checklist.CheckList(1)
        table.attach (self.label1, 0, 1, 0, 1, FILL, FILL, 5, 5)
        table.attach (self.trusted, 1, 2, 0, 1, EXPAND|FILL, FILL, 5, 5)

        self.trusted.append_row (("cipcb0", ""), FALSE)
        self.trusted.append_row (("wvlan0", ""), FALSE)


        hbox = GtkHBox(FALSE, 10)        
        self.label2 = GtkLabel (_("Allow incoming:"))
        self.label2.set_alignment (0.2, 0.0)
        self.incoming = checklist.CheckList(1)
        table.attach (self.label2, 0, 1, 1, 2, FILL, FILL, 5, 5)
        table.attach (self.incoming, 1, 2, 1, 2, EXPAND|FILL, FILL, 5, 5)

        list = ["DHCP", "SSH", "Telnet", "WWW (HTTP)", "Mail (SMTP)", "FTP"]

        for item in list:
            self.incoming.append_row ((item, ""), FALSE)

        self.label3 = GtkLabel (_("Other ports:"))
        self.ports = GtkEntry ()

        table.attach (self.label3, 0, 1, 2, 3, FILL, FILL, 5, 5)
        table.attach (self.ports, 1, 2, 2, 3, EXPAND|FILL, FILL, 5, 5)

        return box

