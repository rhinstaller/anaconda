#
# welcome_gui.py: gui welcome screen.
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

import gtk
from iw_gui import *
from translate import _, N_

class WelcomeWindow (InstallWindow):		

    windowTitle = N_("Welcome")
    htmlTag = "wel"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setGrabNext (1)

    # WelcomeWindow tag="wel"
    def getScreen (self, configFileData):
        frame = gtk.Frame ()
        frame.set_shadow_type (gtk.SHADOW_IN)

        image = configFileData["WelcomeScreen"]
        pix = self.ics.readPixmap(image)
        
        if pix:
            box = gtk.EventBox ()
            box.modify_bg(gtk.STATE_NORMAL, box.get_style ().white)
            box.add (pix)
            frame.add (box)

        return frame

class ReconfigWelcomeWindow (InstallWindow):		

    windowTitle = N_("Welcome")
    htmlTag = "welreconfig"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setNextEnabled (1)
	self.beingDisplayed = 0

    def getNext (self):
        if not self.beingDisplayed: return

        if self.cancelChoice.get_active():
            import sys

            print (_("Exiting anaconda now"))
            sys.exit(0)
        else:
            self.beingDisplay = 0
            return None

    # ReconfigWelcomeWindow tag="welreconfig"
    def getScreen (self):


	frame = gtk.Frame ()
        frame.set_shadow_type (gtk.SHADOW_IN)

        box = gtk.VBox (gtk.FALSE)
        box.set_border_width (5)
        frame.add (box)

        pix = self.ics.readPixmap ("first-375.png")
        
        if pix:
            ebox = gtk.EventBox ()
            ebox.modify_bg(gtk.STATE_NORMAL, ebox.get_style ().white)
            ebox.add (pix)
            box.pack_start (ebox, gtk.FALSE)

        label = gtk.Label(_("Would you like to configure your system?"))
	label.set_line_wrap(gtk.TRUE)
	label.set_alignment(0.0, 0.0)
	label.set_usize(400, -1)

        box.pack_start(label)
        
        radioBox = gtk.VBox (gtk.FALSE)
	self.continueChoice = gtk.RadioButton (None, _("Yes"))
	radioBox.pack_start(self.continueChoice, gtk.FALSE)
	self.cancelChoice = gtk.RadioButton(
		self.continueChoice, _("No"))
	radioBox.pack_start(self.cancelChoice, gtk.FALSE)

	align = gtk.Alignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, gtk.TRUE, gtk.TRUE)
	box.set_border_width (5)
	self.beingDisplayed = 1

	return frame
    
