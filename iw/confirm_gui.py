#
# confirm_gui.py: install/upgrade point of no return screen.
#
# Copyright 2000-2003 Red Hat, Inc.
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
from rhpl.translate import _, N_
from constants import *
from upgrade import queryUpgradeContinue
from image import presentRequiredMediaMessage
import gui
import sys

class ConfirmWindow (InstallWindow):

    def getNext(self):
        if self.anaconda.methodstr.startswith("cdrom://") and not self.anaconda.isKickstart:
	    rc = presentRequiredMediaMessage(self.anaconda)
	    if rc == 0:
		rc2 = self.anaconda.intf.messageWindow(_("Reboot?"),
					_("The system will be rebooted now."),
					type="custom", custom_icon="warning",
					custom_buttons=[_("_Back"), _("_Reboot")])
		if rc2 == 1:
		    sys.exit(0)
		else:
		    raise gui.StayOnScreen
            elif rc == 1: # they asked to go back
                self.anaconda.intf.icw.prevClicked()
                raise gui.StayOnScreen
                return DISPATCH_BACK

    # ConfirmWindow tag="aboutupgrade" or "aboutinstall"
    def getScreen (self, labelText, longText):
        hbox = gtk.HBox (True, 5)
        box = gtk.VBox (False, 5)

        pix = gui.readImageFromFile ("about-to-install.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox.pack_start (a, False)

	label = gtk.Label (labelText)
        label.set_line_wrap (True)
        label.set_size_request(190, -1)

	label2 = gtk.Label (longText)
        label2.set_line_wrap (True)
        label2.set_size_request(190, -1)
        
        box.pack_start (label, False)
        box.pack_start (label2, False)
        box.set_border_width (5)

        a = gtk.Alignment ()
        a.add (box)
        a.set (0.5, 0.5, 0.0, 0.0)

        hbox.pack_start (a)
        return hbox
        
class InstallConfirmWindow (ConfirmWindow):
    windowTitle = N_("About to Install")

    def getScreen(self, anaconda):
        self.anaconda = anaconda

	return ConfirmWindow.getScreen(self,
	    _("Click next to begin installation of %s.") % (productName,),
	    _("A complete log of the installation can be found in "
	      "the file '%s' after rebooting your system.\n\n"
              "A kickstart file containing the installation options "
	      "selected can be found in the file '%s' after rebooting the "
	      "system.") % (u'/root/install.log', '/root/anaconda-ks.cfg'))

class UpgradeConfirmWindow (ConfirmWindow):
    windowTitle = N_("About to Upgrade")

    def getScreen(self, anaconda):
        self.anaconda = anaconda

	return ConfirmWindow.getScreen(self,
            _("Click next to begin upgrade of %s.") % (productName,),
            _("A complete log of the upgrade can be found in "
	      "the file '%s' after rebooting your system.") % (u'/root/upgrade.log',))

