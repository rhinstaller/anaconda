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
import gui
from iw_gui import *
from rhpl.translate import _, N_
from constants import *
import iutil
import _isys

class CongratulationWindow (InstallWindow):		

    windowTitle = N_("Congratulations")

    def __init__ (self, ics):
	InstallWindow.__init__(self, ics)

        ics.setPrevEnabled(gtk.FALSE)
        ics.setNextButton(gtk.STOCK_QUIT, _("_Exit"))
        ics.setHelpButtonEnabled(gtk.FALSE)
        ics.setHelpEnabled(gtk.FALSE)
	ics.setGrabNext(1)

    def getNext(self):
	# XXX - copy any screenshots over
	gui.copyScreenshots()

    # CongratulationWindow tag=NA
    def getScreen (self):
        self.ics.setHelpEnabled (gtk.FALSE)

        hbox = gtk.HBox (gtk.FALSE, 5)
        
        pix = self.ics.readPixmap ("done.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
	    a.set_size_request(200, -1)
            hbox.pack_start (a, gtk.FALSE, gtk.FALSE, 36)

        if not iutil.getArch() in ('ia64', 's390'):
            bootstr = _("If you created a boot diskette during this "
			"installation as your primary means of "
			"booting %s, insert it before "
			"rebooting your newly installed system.\n\n") % (productName,)
        else:
            bootstr = ""
            

	label = gui.WrappingLabel(
             _("Congratulations, the installation is complete.\n\n"
               "Remove any installation media (diskettes or CD-ROMs) used during the "
               "installation."
               "\n\n"
               "%s"
	       "For information on Errata (updates and bug fixes), visit:\n"
	       "\thttp://www.redhat.com/errata/\n\n"
	       "For information on automatic updates through Red Hat "
	       "Network, visit:\n"
	       "\thttp://rhn.redhat.com/\n\n"
	       "For information on using and configuring the system, visit:\n"
	       "\thttp://www.redhat.com/docs/\n"
	       "\thttp://www.redhat.com/apps/support/\n\n"
	       "To register the product for support, visit:\n"
	       "\thttp://www.redhat.com/apps/activate/\n\n"
	       "Click 'Exit' to reboot the system.") % (bootstr,))

        hbox.pack_start (label, gtk.TRUE, gtk.TRUE)
	# FIXME: Need to investigate why the normal umount didn't work and
	# remove this hack
	if iutil.getArch() == "s390":
	    try:
	        f = open("/proc/mounts", "r")
	    except:
	        pass
	    else:
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

