#
# congrats_gui.py: install/upgrade complete screen.
#
# Copyright 2000-2006 Red Hat, Inc.
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
import rhpl
from iw_gui import *
from rhpl.translate import _, N_
from constants import *
import iutil

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

	self.rebootButton = ics.cw.mainxml.get_widget("rebootButton")
	self.rebootButton.show()
	self.rebootButton.grab_focus()

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
        if rhpl.getArch() in ['s390', 's390x']:
            floppystr = ""
            if not anaconda.canReIPL:
                self.rebootButton.set_label(_("Shutdown"))
            if not anaconda.reIPLMessage is None:
                floppystr = anaconda.reIPLMessage

        else:
            floppystr = _("Remove any media used during the installation "
                          "process and press the \"Reboot\" button to "
                          "reboot your system."
                          "\n\n")

        txt = _("Congratulations, the installation is complete.\n\n"
                "%s%s") %(floppystr, bootstr)
	label = gui.WrappingLabel(txt)

        hbox.pack_start (label, True, True)

        gtk.gdk.beep()
        return hbox

