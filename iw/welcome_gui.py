from gtk import *
from gnome.ui import *
from iw_gui import *
from translate import _

class WelcomeWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Welcome"))
        ics.setNextEnabled (1)
        ics.readHTML ("wel")
        self.ics = ics

    def getScreen (self):
        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_IN)
        im = self.ics.readPixmap ("splash.png")
        
        if im:
            im.render ()
            box = GtkEventBox ()
            pix = im.make_pixmap ()
            style = box.get_style ().copy ()
            style.bg[STATE_NORMAL] = style.white
            box.set_style (style)
            box.add (pix)
            frame.add (box)

        return frame

class ReconfigWelcomeWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Welcome"))
        ics.setNextEnabled (1)
        ics.readHTML ("welreconfig")
        ics.setGrabNext (1)
	self.beingDisplayed = 0
        self.ics = ics

    def getNext (self):
        if not self.beingDisplayed: return

        if self.cancelChoice.get_active():
            import sys

            print "Exitting"
            self.ics.ii.finishedTODO.set()
            sys.exit(0)
        else:
            self.beingDisplay = 0
            return None

    def getScreen (self):


	frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_IN)

        box = GtkVBox (FALSE)
        box.set_border_width (5)
        frame.add (box)

        im = self.ics.readPixmap ("first-375.png")
        
        if im:
            im.render ()
            ebox = GtkEventBox ()
            pix = im.make_pixmap ()
            style = ebox.get_style ().copy ()
            style.bg[STATE_NORMAL] = style.white
            ebox.set_style (style)
            ebox.add (pix)
            box.pack_start (ebox, FALSE)

        label = GtkLabel(_("Would you like to configure your system?"))
	label.set_line_wrap(TRUE)
	label.set_alignment(0.0, 0.0)
	label.set_usize(400, -1)

        box.pack_start(label)
        
        radioBox = GtkVBox (FALSE)
	self.continueChoice = GtkRadioButton (None, _("Yes"))
	radioBox.pack_start(self.continueChoice, FALSE)
	self.cancelChoice = GtkRadioButton(
		self.continueChoice, _("No"))
	radioBox.pack_start(self.cancelChoice, FALSE)

	align = GtkAlignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, TRUE, TRUE)
	box.set_border_width (5)
	self.beingDisplayed = 1

	return frame
    
