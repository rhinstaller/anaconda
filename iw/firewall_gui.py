#
# firewall_gui.py: firewall setup screen
#
# Copyright 2001-2004 Red Hat, Inc.
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
from flags import flags
from constants import *

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
            for service in self.firewall.services:
                val = self.incoming.get_active(count)
                service.set_enabled(val)
                count = count + 1

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

        label = gui.WrappingLabel (_("A firewall can help prevent "
                                     "unauthorized access to your computer "
                                     "from the outside world.  Would you like "
                                     "to enable a firewall?"))
        label.set_alignment (0.0, 0)
	label.set_size_request(450, -1)        

        box.pack_start(label, gtk.FALSE)

        vbox = gtk.VBox (gtk.FALSE)

        self.disabled_radio = gtk.RadioButton (None, (_("N_o firewall")))
        self.enabled_radio = gtk.RadioButton (self.disabled_radio,
                                               (_("_Enable firewall")))
        self.disabled_radio.connect("clicked", self.activate_firewall)
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
        label = gui.WrappingLabel (_("With a firewall, you may wish to "
                                     "allow access to specific services on "
                                     "your computer from others.  "
                                     "Allow access to which services?"))
	label.set_size_request(400, -1)
        label.set_alignment(0.0, 0.0)
        self.table.attach(label, 0, 2, y, y + 1, gtk.EXPAND | gtk.FILL, gtk.FILL, 5, 5)

        y = y + 1
        hbox = gtk.HBox(gtk.FALSE, 10)        
        self.incoming = checklist.CheckList(1)
	self.incoming.set_size_request(-1, 125)

        incomingSW = gtk.ScrolledWindow()
        incomingSW.set_border_width(5)
        incomingSW.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        incomingSW.set_shadow_type(gtk.SHADOW_IN)
        incomingSW.add(self.incoming)
        
        for serv in self.firewall.services:
            self.incoming.append_row ( (_(serv.get_name()), serv),
                                       serv.get_enabled() )

        self.table.attach (incomingSW, 0, 2, y, y + 1, gtk.EXPAND|gtk.FILL, gtk.FILL, 5, 5)

        if self.firewall.enabled == 0:
            self.disabled_radio.set_active (gtk.TRUE)
        else:
            self.enabled_radio.set_active(gtk.TRUE)
            
        self.activate_firewall(None)

        # SELinux widgets
        selbox = gtk.VBox()
        selbox.set_spacing(8)

        l = gui.WrappingLabel(_("Security Enhanced Linux (SELinux) "
                                "provides finer-grained "
                                "security controls than are available "
                                "in a traditional Linux system.  It can "
                                "be set up in a disabled state, a state "
                                "which only warns about things which would "
                                "be denied, or a fully active state."))
        l.set_size_request(400, -1)
        l.set_alignment(0.0, 0.0)

        selbox.pack_start(l, gtk.FALSE)

        label = gtk.Label(_("Enable _SELinux?:"))
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
        hbox.pack_start(self.se_option_menu, gtk.FALSE)
        selbox.pack_start(hbox)

        if flags.selinux == 0:
            selbox.set_sensitive(gtk.FALSE)

        if (SELINUX_DEFAULT == 1) or flags.selinux:
            box.pack_start (gtk.HSeparator(), gtk.FALSE)
            box.pack_start(selbox, gtk.FALSE)

        return box


