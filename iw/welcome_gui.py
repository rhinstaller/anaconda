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
    htmlTag = "wel"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setGrabNext (1)

    # WelcomeWindow tag="wel"
    def getScreen (self, configFileData):
        frame = gtk.Frame ()
        frame.set_shadow_type (gtk.SHADOW_NONE)

        image = configFileData["WelcomeScreen"]
        pix = gui.readImageFromFile(image)
        
        if pix:
            box = gtk.EventBox ()
#            box.modify_bg(gtk.STATE_NORMAL, box.get_style ().white)
            box.add (pix)
            frame.add (box)

        return frame

