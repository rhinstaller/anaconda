#
# welcome_gui.py: gui welcome screen.
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gui
from iw_gui import *
from rhpl.translate import _, N_

class WelcomeWindow (InstallWindow):		

    windowTitle = "" #N_("Welcome")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setGrabNext (1)

    # WelcomeWindow tag="wel"
    def getScreen (self, anaconda):
        # this is a bit ugly... but scale the image if we're not at 800x600
        (w, h) = self.ics.cw.window.get_size_request()
        if w >= 800:
            height = None
            width = None
        else:
            width = 500
            height = 258
        pix = gui.readImageFromFile("splash.png", width, height, dither=False)
        box = gtk.EventBox ()
        box.add (pix)
        return box

