#
# confirm_gui.py: install/upgrade point of no return screen.
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
from package_gui import queryUpgradeContinue
import gui

class ConfirmWindow (InstallWindow):

    # ConfirmWindow tag="aboutupgrade" or "aboutinstall"
    def getScreen (self, labelText, longText):
        hbox = gtk.HBox (gtk.TRUE, 5)
        box = gtk.VBox (gtk.FALSE, 5)

        pix = self.ics.readPixmap ("about-to-install.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox.pack_start (a, gtk.FALSE)

	label = gtk.Label (labelText)
        label.set_line_wrap (gtk.TRUE)
        label.set_usize(190, -1)

	label2 = gtk.Label (longText)
        label2.set_line_wrap (gtk.TRUE)
        label2.set_usize(190, -1)
        
        box.pack_start (label, gtk.FALSE)
        box.pack_start (label2, gtk.FALSE)
        box.set_border_width (5)

        a = gtk.Alignment ()
        a.add (box)
        a.set (0.5, 0.5, 0.0, 0.0)

        hbox.pack_start (a)
        return hbox
        
class InstallConfirmWindow (ConfirmWindow):
    windowTitle = N_("About to Install")
    htmlTag = "aboutinstall"

    def getScreen(self):
	return ConfirmWindow.getScreen(self,
	    _("Click next to begin installation of Red Hat Linux."),
	    _("A complete log of your installation will be in "
	      "/tmp/install.log after rebooting your system. You "
	      "may want to keep this file for later reference. "
              "A kickstart file representing the choices you have made "
              "will be in /root/anaconda-ks.cfg."))

class UpgradeConfirmWindow (ConfirmWindow):
    windowTitle = N_("About to Upgrade")
    htmlTag = "aboutupgrade"

    def getScreen(self):
	return ConfirmWindow.getScreen(self,
            _("Click next to begin upgrade of Red Hat Linux."),
            _("A complete log of your upgrade will be in "
	      "/tmp/upgrade.log after rebooting your system. You "
	      "may want to keep this file for later reference."))

