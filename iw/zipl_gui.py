#
# bootloader_gui.py: gui bootloader configuration dialog
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

# must replace with explcit form so update disks will work
from iw_gui import *

from gtk import *
from gnome.ui import *
from translate import _, N_
import iutil
from package_gui import queryUpgradeContinue
import gui

class ZiplWindow (InstallWindow):
    checkMark = None
    checkMark_Off = None

    def __init__ (self, ics):
        InstallWindow.__init__ (self, ics)
        self.ics.setTitle ("z/IPL")
        self.ics.readHTML ("zipl-s390")
        self.ics.windowTitle = N_("z/IPL Boot Loader Configuration")

    def getPrev (self):
        # avoid coming back in here if the user backs past and then tries
        # to skip this screen
	pass

	# XXX
	#
        # if doing an upgrade, offer choice of aborting upgrade.
        # we can't allow them to go back in install, since we've
        # started swap and mounted the systems filesystems
        # if we've already started an upgrade, cannot back out
        #
        # if we are skipping indivual package selection, must stop it here
        # very messy.
        #
        #if self.todo.upgrade and self.todo.instClass.skipStep("indivpackage"):
            #rc = queryUpgradeContinue(self.todo.intf)
            #if not rc:
                #raise gui.StayOnScreen
            #else:
                #import sys
                #print _("Aborting upgrade")
                #sys.exit(0)

    def getNext (self):
        self.bl.args.set(self.appendEntry.get_text())


    # ZiplWindow tag="zipl"
    def getScreen(self, dispatch, bl, fsset, diskSet):
	self.dispatch = dispatch
	self.bl = bl
        self.intf = dispatch.intf

	imageList = bl.images.getImages()
	defaultDevice = bl.images.getDefault()
        self.ignoreSignals = 0

        box  = GtkVBox(FALSE, 5)
        box.set_border_width(5)
        label = GtkLabel(_("The z/IPL Boot Loader will now be installed "
                           "on your system."
                           "\n"
                           "\n"
                           "The root partition will be the one you "
                           "selected previously in the partition setup."
                           "\n"
                           "\n"
                           "The kernel used to start the machine will be "
                           "the one to be installed by default."
                           "\n"
                           "\n"
                           "If you wish to make changes later after "
                           "the installation feel free to change the "
                           "/etc/zipl.conf configuration file."
                           "\n"
                           "\n"
                           "You can now enter any additional kernel parameters "
                           "which your machine or your setup may require."))
        label.set_usize(500, -1)
        label.set_line_wrap(TRUE)
        label.set_alignment(0.0, 0.0)
        label.set_padding(50,50)
        box.pack_start(label, FALSE)

        box.pack_start (GtkHSeparator (), FALSE)

        label = GtkLabel(_("Kernel Parameters") + ":")
        label.set_alignment(0.0, 0.5)
        self.appendEntry = GtkEntry()
        if bl.args and bl.args.get():
            self.appendEntry.set_text(bl.args.get())
        hbox = GtkHBox(FALSE, 5)
        hbox.pack_start(label, FALSE)
        hbox.pack_start(self.appendEntry)
        box.pack_start(hbox, FALSE)

        return box
