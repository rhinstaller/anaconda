#
# desktop_choice_gui.py: choose desktop
#
# Copyright 2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gobject
import string
import gui
from iw_gui import *
from rhpl.translate import _, N_
from constants import productName
from flags import flags

class DesktopChoiceWindow (InstallWindow):		

    windowTitle = N_("Package Defaults")
    htmlTag = "pkg-default"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setGrabNext (1)
	self.ics = ics

    def getNext(self):
	if self.customizeRadio.get_active():
	    self.dispatch.skipStep("package-selection", skip = 0)
	else:
	    self.dispatch.skipStep("package-selection", skip = 1)

	return None
    
    # WelcomeWindow tag="wel"
    def getScreen (self, intf, instclass, dispatch):

	self.intf = intf
	self.dispatch = dispatch

	vbox = gtk.VBox (gtk.FALSE, 0)
	vbox.set_border_width (5)
	hbox = gtk.HBox (gtk.FALSE, 0)

        header = _("The default installation environment includes our "
                   "recommended package selection, including:\n\n")
        footer = _("\n\nAfter installation, additional software can be "
                   "added or removed using the 'redhat-config-packages' "
                   "tool.\n\n"
                   "If you are familiar with %s, you may have specific "
                   "packages you would like to install or avoid "
                   "installing. Check the box below to "
                   "customize your installation.") %(productName,)

        if len(instclass.pkgstext) > 0:
            labeltxt = header + _(instclass.pkgstext) + footer
        else:
	    labeltxt = _(
		"If you would like to change the default package set to be "
		"installed you can choose to customize this below.")
	    
	label = gui.WrappingLabel(labeltxt)

	hbox.pack_start (label, gtk.FALSE, gtk.FALSE, 0)
	vbox.pack_start (hbox, gtk.FALSE, gtk.FALSE, 0)
	
	self.acceptRadio = gtk.RadioButton (None, _("_Install default software packages"))
	self.customizeRadio = gtk.RadioButton (self.acceptRadio, _("_Customize software packages to be installed"))
	vbox2 = gtk.VBox (gtk.FALSE)
	vbox2.pack_start (self.acceptRadio, gtk.FALSE, gtk.FALSE, 0)
	vbox2.pack_start (self.customizeRadio, gtk.FALSE, gtk.FALSE, 0)
	al = gtk.Alignment(0.5, 0)
	al.add (vbox2)
	
	vbox.pack_start (al, gtk.FALSE, gtk.FALSE, 25)
	custom = not self.dispatch.stepInSkipList("package-selection")
	if custom:
	    self.customizeRadio.set_active(1)
	else:
	    self.acceptRadio.set_active(0)
	    
	big_al = gtk.Alignment (0.5, 0.2)
	big_al.add (vbox)
	return big_al
