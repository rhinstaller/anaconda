#
# welcome_gui.py: gui welcome screen.
#
# Copyright (C) 2000, 2001, 2002  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import gtk
import gui
import sys
from iw_gui import *

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class WelcomeWindow (InstallWindow):

    windowTitle = "" #N_("Welcome")

    def __init__ (self, ics):
        InstallWindow.__init__ (self, ics)
        ics.setGrabNext (1)
        self.anaconda = None

    # WelcomeWindow tag="wel"
    def getScreen (self, anaconda):
        self.anaconda = anaconda
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

    def getNext (self):
        if self.anaconda.requiresNetworkInstall():
            self.anaconda.intf.messageWindow(_("Network Install Required"),
                                             _("Your installation source is set to "
                                               "a network location, but no netork "
                                               "devices were found on your "
                                               "system.  To avoid a network "
                                               "installation, boot with the full "
                                               "DVD, full CD set, or do not pass "
                                               "a repo= parameter that specifies "
                                               "a network source."),
                                             type="custom",
                                             custom_icon="error",
                                             custom_buttons=[_("E_xit Installer")])
            sys.exit(0)
