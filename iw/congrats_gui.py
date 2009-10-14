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
import platform

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class CongratulationWindow (InstallWindow):		

    windowTitle = N_("Congratulations")

    def __init__ (self, ics):
	InstallWindow.__init__(self, ics)

        ics.setPrevEnabled(False)

        # force buttonbar on in case release notes viewer is running
        ics.cw.mainxml.get_widget("buttonBar").set_sensitive(True)

        self.rebootButton = ics.cw.mainxml.get_widget("rebootButton")

        # this mucks around a bit, but it's the weird case and it's
        # better than adding a lot of complication to the normal
	ics.cw.mainxml.get_widget("nextButton").hide()
        if os.path.exists(os.environ.get("LIVE_BLOCK", "/dev/mapper/live-osimg-min")):
            ics.cw.mainxml.get_widget("closeButton").show()
            ics.cw.mainxml.get_widget("closeButton").grab_focus()
        else:
            self.rebootButton.show()
            self.rebootButton.grab_focus()
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

        if isinstance(anaconda.platform, platform.S390):
            txt = _("Congratulations, your %s installation is complete.\n\n") % (productName,)

            if not anaconda.canReIPL:
                self.rebootButton.set_label(_("Shutdown"))

                txt = txt + _("Please shutdown to use the installed system.\n")
            else:
                txt = txt + _("Please reboot to use the installed system.\n")

            if not anaconda.reIPLMessage is None:
                txt = txt + "\n" + anaconda.reIPLMessage + "\n\n"

            txt = txt + _("Note that updates may be available to ensure the proper "
                          "functioning of your system and installation of these "
                          "updates is recommended after the reboot.")
        else:
            txt = _("Congratulations, your %s installation is complete.\n\n"
                    "Please reboot to use the installed system.  "
                    "Note that updates may be available to ensure the proper "
                    "functioning of your system and installation of these "
                    "updates is recommended after the reboot.") %(productName,)

	label = gui.WrappingLabel(txt)
        label.set_size_request(250, -1)

        hbox.pack_start (label, True, True)

        gtk.gdk.beep()
        return hbox

