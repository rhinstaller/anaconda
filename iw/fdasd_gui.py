#
# fdasd_gui.py: interface that allows the user to run util-linux fdasd.
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
from iw_gui import *
from gnome.zvt import *
from translate import _
from dispatch import DISPATCH_NOOP
import partitioning
import isys
import os
import iutil

class FDasdWindow (InstallWindow):		
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        self.fdasd_name = _("fdasd")
        self.selectlabel = _("Select drive to run fdasd on")
        self.drive = None

        ics.setTitle (self.fdasd_name)
        ics.readHTML ("usefdasd-s390")

    def getNext(self):
        # reread partitions
        self.diskset.refreshDevices(self.intf)
        partitioning.checkNoDisks(self.diskset, self.intf)
        self.partrequests.setFromDisk(self.diskset)

        return None
        

    def child_died (self, widget, button):
        self.windowContainer.remove (self.windowContainer.children ()[0])
        self.windowContainer.pack_start (self.buttonBox)
        button.set_state (STATE_NORMAL)
        try:
            os.remove ('/tmp/' + self.drive)
        except:
            # XXX fixme
            pass

        self.ics.readHTML ("usefdasd-s390")
        self.ics.setPrevEnabled (1)
        self.ics.setNextEnabled (1)
#        self.ics.setHelpEnabled (1)


    def row_selected (self, clist, row, column, event):
        self.drive = clist.get_text(row, column)

    def fdasd_button_clicked (self, widget):
        if self.drive == None:
            return

        zvt = ZvtTerm (80, 24)
        zvt.set_del_key_swap(TRUE)
        zvt.connect ("child_died", self.child_died, widget)

        # free our fd's to the hard drive -- we have to 
        # fstab.rescanDrives() after this or bad things happen!
        if os.access("/sbin/fdasd", os.X_OK):
            path = "/sbin/fdasd"
        else:
            path = "/usr/sbin/fdasd"
            
	isys.makeDevInode(self.drive, '/tmp/' + self.drive)

        if zvt.forkpty() == 0:
            env = os.environ
            os.execve (path, (path, '/tmp/' + self.drive), env)
        zvt.show ()

        self.windowContainer.remove (self.buttonBox)
        self.windowContainer.pack_start (zvt)

        self.ics.readHTML ("usefdasd-s390")
	self.ics.setPrevEnabled (0)
        self.ics.setNextEnabled (0)

    def dasdfmt_button_clicked (self, widget):
        rc = self.intf.messageWindow(_("Warning"), _("Formating the selected DASD device will destroy all contents of the device. Do you really want to format the selected DASD device?"), "yesno")
        if rc == 1:
            self.diskset.dasdFmt(self.intf, self.drive)

    # FdasdWindow tag="fdasd"
    def getScreen (self, diskset, partrequests, intf):
        self.diskset = diskset
        self.partrequests = partrequests
        self.intf = intf
        
        self.windowContainer = GtkVBox (FALSE)
        self.buttonBox = GtkVBox (FALSE, 5)
        self.buttonBox.set_border_width (5)
        box = GtkVButtonBox ()
        label = GtkLabel (self.selectlabel)

        drives =  self.diskset.driveList()
        
        # close all references we had to the diskset
        self.diskset.closeDevices()

        clist = GtkCList(1, ["Available DASD devices:"])
        for drive in drives:
            clist.append([drive])

        clist.connect ("select_row", self.row_selected)
        box.add (clist)

        box2 = GtkHButtonBox ()
        box2.set_layout (BUTTONBOX_SPREAD)
        button = GtkButton ("Run fdasd")
        button.connect ("clicked", self.fdasd_button_clicked)
        box2.add(button)
        button = GtkButton ("Run dasdfmt")
        button.connect ("clicked", self.dasdfmt_button_clicked)
        box2.add(button)

        self.buttonBox.pack_start (label, FALSE)
        self.buttonBox.pack_start (box, FALSE)
        self.buttonBox.pack_start (box2, FALSE)
        self.windowContainer.pack_start (self.buttonBox)

        self.ics.setNextEnabled (1)

        return self.windowContainer
