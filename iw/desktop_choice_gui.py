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
from installclass import DEFAULT_DESKTOP_LABEL_1, DEFAULT_DESKTOP_LABEL_2
from constants import productName
from flags import flags

class DesktopChoiceWindow (InstallWindow):		

    windowTitle = N_("Workstation Defaults")
    htmlTag = "wsdefaults"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setGrabNext (1)

    def getNext(self):
	if self.customize.get_active():
	    self.dispatch.skipStep("package-selection", skip = 0)
	else:
	    self.dispatch.skipStep("package-selection")

	return None
    
    # WelcomeWindow tag="wel"
    def getScreen (self, intf, dispatch):

	self.intf = intf
	self.dispatch = dispatch

	table = gtk.Table()
	table.set_row_spacings(5)
	table.set_border_width(5)

	label1 = DEFAULT_DESKTOP_LABEL_1
	label2 = "\tGNOME Desktop\t\t\tNautilus file manager\n"+"\tMozilla web browser\t\tEvolution mail client\n"+"\tCD authoring software\t\tMultimedia applications\n"+"\tOpen Office(tm) office suite"
	label3 = DEFAULT_DESKTOP_LABEL_2 % (productName, productName)

	label = gui.WrappingLabel(label1+"\n\n"+label2+"\n\n"+label3)
	table.attach(label, 0, 1, 0, 1)

	self.customize = gtk.CheckButton(_("I would like to choose additional software"))
	table.attach(self.customize, 0, 1, 1, 2, ypadding=15)

	custom = not self.dispatch.stepInSkipList("package-selection")
	self.customize.set_active(custom)

	al = gtk.Alignment(0.5, 0.5)
	al.add(table)
	return al
    
