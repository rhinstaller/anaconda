#
# congrats_gui.py: install/upgrade complete screen.
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

from gtk import *
from gnome.ui import *
from iw_gui import *
from translate import _, N_
import iutil
import _isys
import sys
import string

class CongratulationWindow (InstallWindow):		

    windowTitle = N_("Congratulations")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setPrevEnabled (FALSE)
        ics.setNextButton (STOCK_PIXMAP_QUIT, _("Exit"))
        ics.setHelpButtonEnabled (FALSE)
        ics.setHelpEnabled(FALSE)
	ics.setGrabNext (1)

    # CongratulationWindow tag=NA
    def getScreen (self):
        self.ics.setHelpEnabled (FALSE)

        hbox = GtkHBox (TRUE, 5)
        
        pix = self.ics.readPixmap ("done.png")
        if pix:
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox.pack_start (a, FALSE)

        if iutil.getArch() != "ia64":
            bootstr = _("If you created a boot disk to use to boot your "
                        "Red Hat Linux system, insert it before you "
                        "press <Enter> to reboot.\n\n")
        else:
            bootstr = ""
            

	if iutil.getArch() != "s390" and iutil.getArch() != "s390x":
            label = GtkLabel(
                 _("Congratulations, your Red Hat Linux installation is "
                   "complete.\n\n"
                   "Remove any floppy diskettes you used during the "
                   "installation process and press <Enter> to reboot your system. "
                   "\n\n"
                   "%s"
                   "For information on errata (updates and bug fixes), visit "
                   "http://www.redhat.com/errata.\n\n"
                   "Information on using and configuring your "
                   "system is available in the Red Hat Linux manuals "
                   "at http://www.redhat.com/support/manuals.") % bootstr,
                 )
	else:
            label = GtkLabel(
                 _("Congratulations, your Red Hat Linux installation is "
                   "complete.\n\n"
                   "Press <Enter> to reboot your system. "
                   "\n\n"
                   "For information on errata (updates and bug fixes), visit "
                   "http://www.redhat.com/errata.\n\n"
                   "Information on using and configuring your "
                   "system is available in the Red Hat Linux manuals "
                   "at http://www.redhat.com/support/manuals."),
                 )
                
        label.set_line_wrap (TRUE)
        label.set_alignment (0.0, 0.5)

        box = GtkVBox (FALSE, 10)
        box.pack_start (label, TRUE, TRUE, 0)

        hbox.pack_start (box)
        f = open("/proc/mounts", "r")
        lines = f.readlines()
        f.close()
        umounts = []
        for line in lines:
           if string.find(line, "/mnt/sysimage") > -1:
                tokens = string.split(line)
                umounts.append(tokens[1])
        umounts.sort()
        umounts.reverse()
        for part in umounts:
            try:
                _isys.umount(part)
            except:
                print part + "is busy, couldn't umount."
	sys.exit(0)
        return hbox


class ReconfigCongratulationWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Congratulations"))
        ics.setPrevEnabled (0)
        ics.setNextButton (STOCK_PIXMAP_QUIT, _("Exit"))
        ics.setNextEnabled (1)
	ics.setGrabNext (1)

    # ReconfigCongratulationWindow tag=NA
    def getScreen (self):
        self.ics.setHelpEnabled (0)

        hbox = GtkHBox (TRUE, 5)
        
        pix = self.ics.readPixmap ("done.png")
        if pix:
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox.pack_start (a, FALSE)

        label = GtkLabel(_("Congratulations, configuration is complete.\n\n"
                  "For information on errata (updates and bug fixes), visit "
                  "http://www.redhat.com/errata.\n\n"
                  "Information on using and configuring your "
                  "system is available in the Red Hat Linux manuals "
                  "at http://www.redhat.com/support/manuals."))
        
        label.set_line_wrap (TRUE)
        label.set_alignment (0.0, 0.5)
        
        box = GtkVBox (FALSE, 10)
        box.pack_start (label, TRUE, TRUE, 0)

        hbox.pack_start (box)
        f = open("/proc/mounts", "r")
        lines = f.readlines()
        f.close()
        umounts = []
        for line in lines:
           if string.find(line, "/mnt/sysimage") > -1:
                tokens = string.split(line)
                umounts.append(tokens[1])
        umounts.sort()
        umounts.reverse()
        for part in umounts:
            try:
                _isys.umount(part)
            except:
                print part + "is busy, couldn't umount."
        return hbox

