#
# congrats_gui.py: install/upgrade complete screen.
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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
from iw_gui import *
from constants import *
import os

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class CongratulationWindow (InstallWindow):		

    windowTitle = N_("Congratulations")

    def __init__ (self, ics):
	InstallWindow.__init__(self, ics)

        ics.setPrevEnabled(False)

        # force buttonbar on in case release notes viewer is running
        ics.cw.mainxml.get_widget("buttonBar").set_sensitive(True)

        # this mucks around a bit, but it's the weird case and it's
        # better than adding a lot of complication to the normal
	ics.cw.mainxml.get_widget("nextButton").hide()
        if os.path.exists("/dev/live-osimg"):
            ics.cw.mainxml.get_widget("closeButton").show()
            ics.cw.mainxml.get_widget("closeButton").grab_focus()
        else:
            ics.cw.mainxml.get_widget("rebootButton").show()
            ics.cw.mainxml.get_widget("rebootButton").grab_focus()

    def getNext(self):
	# XXX - copy any screenshots over
	gui.copyScreenshots()

    # CongratulationWindow tag=NA
    def getScreen (self, anaconda):
        hbox = gtk.HBox (False, 5)
        
        pix = gui.readImageFromFile ("done.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
	    a.set_size_request(200, -1)
            hbox.pack_start (a, False, False, 36)

        bootstr = ""
        if iutil.isS390() or os.path.exists("/dev/live-osimg"):
            floppystr = _("Please reboot the system to use the installed "
                          "system.\n\n")
        else:
            floppystr = _("Press the \"Reboot\" button to reboot your system."
                          "\n\n")


        txt = _("Congratulations, the installation is complete.\n\n"
                "%s%s") %(floppystr, bootstr)
	label = gui.WrappingLabel(txt)
        label.set_size_request(250, -1)

        hbox.pack_start (label, True, True)

        gtk.gdk.beep()
        return hbox

