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


    def button_clicked (self, widget, drive):
        zvt = ZvtTerm (80, 24)
        zvt.set_del_key_swap(TRUE)
        zvt.connect ("child_died", self.child_died, widget)
        self.drive = drive


        # free our fd's to the hard drive -- we have to 
        # fstab.rescanDrives() after this or bad things happen!
        if os.access("/sbin/fdasd", os.X_OK):
            path = "/sbin/fdasd"
        else:
            path = "/usr/sbin/fdasd"
            
        
	isys.makeDevInode(drive, '/tmp/' + drive)

        if zvt.forkpty() == 0:
            env = os.environ
            os.execve (path, (path, '/tmp/' + drive), env)
        zvt.show ()

        self.windowContainer.remove (self.buttonBox)
        self.windowContainer.pack_start (zvt)

        self.ics.readHTML ("usefdasd-s390")
	self.ics.setPrevEnabled (0)
        self.ics.setNextEnabled (0)

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

        for drive in drives:
            button = GtkButton (drive)
            button.connect ("clicked", self.button_clicked, drive)
            box.add (button)

        self.buttonBox.pack_start (label, FALSE)
        self.buttonBox.pack_start (box, FALSE)
        self.windowContainer.pack_start (self.buttonBox)

        self.ics.setNextEnabled (1)

        return self.windowContainer
