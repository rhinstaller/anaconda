#
# congrats_gui.py: install/upgrade complete screen.
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
from iw_gui import *
from rhpl.translate import _, N_
from constants import *
import iutil

class CongratulationWindow (InstallWindow):		

    windowTitle = N_("Congratulations")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setPrevEnabled (gtk.TRUE)
        ics.setNextButton (gtk.STOCK_QUIT, _("Exit"))
        ics.setHelpButtonEnabled (gtk.FALSE)
        ics.setHelpEnabled(gtk.FALSE)
	ics.setGrabNext (1)

    # CongratulationWindow tag=NA
    def getScreen (self):
        self.ics.setHelpEnabled (gtk.FALSE)

        hbox = gtk.HBox (gtk.TRUE, 5)
        
        pix = self.ics.readPixmap ("done.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox.pack_start (a, gtk.FALSE)

        if iutil.getArch() != "ia64":
            bootstr = _("If you created a boot disk to use to boot your "
                        "%s system, insert it before you "
                        "press <Enter> to reboot.\n\n") % (productName,)
        else:
            bootstr = ""
            

	label = gtk.Label(
             _("Congratulations, your %s installation is "
               "complete.\n\n"
               "Remove any floppy diskettes you used during the "
               "installation process and press <Enter> to reboot your system. "
               "\n\n"
               "%s"
               "For information on errata (updates and bug fixes), visit "
               "http://www.redhat.com/errata.\n\n"
               "Information on using and configuring your "
               "system is available in the %s manuals "
               "at http://www.redhat.com/docs.") % (productName,
                                                    bootstr, productName),
             )
                
        label.set_line_wrap (gtk.TRUE)
        label.set_alignment (0.0, 0.5)

        box = gtk.VBox (gtk.FALSE, 10)
        box.pack_start (label, gtk.TRUE, gtk.TRUE, 0)

        hbox.pack_start (box)
        return hbox


class ReconfigCongratulationWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Congratulations"))
        ics.setPrevEnabled (0)
        ics.setNextButton (gtk.STOCK_QUIT, _("Exit"))
        ics.setNextEnabled (1)
	ics.setGrabNext (1)

    # ReconfigCongratulationWindow tag=NA
    def getScreen (self):
        self.ics.setHelpEnabled (0)

        hbox = gtk.HBox (gtk.TRUE, 5)
        
        pix = self.ics.readPixmap ("done.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox.pack_start (a, gtk.FALSE)

        label = gtk.Label(_("Congratulations, configuration is complete.\n\n"
                  "For information on errata (updates and bug fixes), visit "
                  "http://www.redhat.com/errata.\n\n"
                  "Information on using and configuring your "
                  "system is available in the %s manuals "
                  "at http://www.redhat.com/docs.") % (productName,))
        
        label.set_line_wrap (gtk.TRUE)
        label.set_alignment (0.0, 0.5)
        
        box = gtk.VBox (gtk.FALSE, 10)
        box.pack_start (label, gtk.TRUE, gtk.TRUE, 0)

        hbox.pack_start (box)
        return hbox

