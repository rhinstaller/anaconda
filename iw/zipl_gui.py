#
# Copyright 2001-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

# must replace with explcit form so update disks will work
import isys
import gtk
import gui
import iutil
import string
from iw_gui import *
from rhpl.translate import _, N_

class ZiplWindow (InstallWindow):
    checkMark = None
    checkMark_Off = None

    def __init__ (self, ics):
        InstallWindow.__init__ (self, ics)
        self.ics.setTitle ("z/IPL")
        self.ics.windowTitle = N_("z/IPL Boot Loader Configuration")

    def getPrev (self):
        # avoid coming back in here if the user backs past and then tries
        # to skip this screen
	pass

    def getNext (self):
        self.bl.args.set(self.kernelEntry.get_text())


    # ZiplWindow tag="zipl"
    def getScreen(self, anaconda):
	self.dispatch = anaconda.dispatch
	self.bl = anaconda.id.bootloader
        self.intf = anaconda.intf

	imageList = self.bl.images.getImages()
	defaultDevice = self.bl.images.getDefault()
        self.ignoreSignals = 0

        box  = gtk.VBox(False, 5)
        box.set_border_width(5)

        label = gtk.Label(_("The z/IPL boot loader will be installed on your "
                            "system."))
        label = gtk.Label(_("The z/IPL Boot Loader will now be installed "
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
        label.set_size_request(500, -1)
        label.set_line_wrap(True)
        label.set_alignment(0.0, 0.0)
        label.set_padding(50,50)
        box.pack_start(label, False)

        box.pack_start (gtk.HSeparator (), False)

        label = gtk.Label(_("Kernel Parameters") + ":")
        label.set_alignment(0.0, 0.5)
        self.kernelEntry = gtk.Entry()
        clabel1 = gtk.Label(_("Chandev Parameters") + ":")
        clabel1.set_alignment(0.0, 0.5)
        self.chandeventry1 = gtk.Entry()
        clabel2 = gtk.Label(_("Chandev Parameters") + ":")
        clabel2.set_alignment(0.0, 0.5)
        self.chandeventry2 = gtk.Entry()

        if self.bl.args and self.bl.args.get():
            kernelparms = self.bl.args.get()
        else:
            kernelparms = ""
        if isys.getDasdPorts() and (kernelparms.find("dasd=") == -1):
            if len(kernelparms) > 0:
                kernelparms = "%s dasd=%s" %(kernelparms, isys.getDasdPorts())
            else:
                kernelparms = "dasd=%s" %(isys.getDasdPorts(),)
        self.kernelEntry.set_text(kernelparms)
        
        if self.bl.args and self.bl.args.chandevget():
            cdevs = self.bl.args.chandevget()
            self.chandeventry1.set_text('')
            self.chandeventry2.set_text('')
            if len(cdevs) > 0:
                self.chandeventry1.set_text(cdevs[0])
            if len(cdevs) > 1:
                self.chandeventry2.set_text(string.join(cdevs[1:],';'))
        hbox = gtk.HBox(False, 5)
        hbox.pack_start(label, False)
        hbox.pack_start(self.kernelEntry)
        box.pack_start(hbox, False)
        hbox1 = gtk.HBox(False, 5)
        hbox1.pack_start(clabel1, False)
        hbox1.pack_start(self.chandeventry1)
        box.pack_start(hbox1, False)
        hbox2 = gtk.HBox(False, 5)
        hbox2.pack_start(clabel2, False)
        hbox2.pack_start(self.chandeventry2)
        box.pack_start(hbox2, False)

        return box
