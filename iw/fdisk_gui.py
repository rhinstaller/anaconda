from gtk import *
from iw_gui import *
from gnome.zvt import *
from translate import _
import isys
import os

class FDiskWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setTitle (_("fdisk"))
        ics.readHTML ("fdisk")

    def child_died (self, widget, button):
        self.windowContainer.remove (self.windowContainer.children ()[0])
        self.windowContainer.pack_start (self.buttonBox)
        button.set_state (STATE_NORMAL)
        try:
            os.remove ('/tmp/' + self.drive)
        except:
            # XXX fixme
            pass
        self.ics.readHTML ("fdisk")
        self.ics.setPrevEnabled (1)
        self.ics.setNextEnabled (1)
#        self.ics.setHelpEnabled (1)

    def getPrev(self):
	self.todo.fstab.rescanPartitions()

    def getNext(self):
#        from installpath_gui import InstallPathWindow
###
###  msf - 05-11-2000 - change how we determine if we should be run
###        
#        if ((not InstallPathWindow.fdisk) or
#            (not InstallPathWindow.fdisk.get_active ())):
#               return None
#
### here is fix
#
        from rootpartition_gui import AutoPartitionWindow

        if not AutoPartitionWindow.manuallyPartitionfdisk.get_active():
           return None

	self.todo.fstab.rescanPartitions()

	return None

    def button_clicked (self, widget, drive):
        zvt = ZvtTerm (80, 24)
        zvt.set_del_key_swap(TRUE)
        zvt.connect ("child_died", self.child_died, widget)
        self.drive = drive

	# free our fd's to the hard drive -- we have to 
	# fstab.rescanDrives() after this or bad things happen!
        if os.access("/sbin/fdisk", os.X_OK):
            path = "/sbin/fdisk"
        else:
            path = "/usr/sbin/fdisk"
        
	isys.makeDevInode(drive, '/tmp/' + drive)

        if zvt.forkpty() == 0:
            lang = self.ics.getICW().locale
            env = os.environ
            os.execve (path, (path, '/tmp/' + drive), env)
        zvt.show ()

        self.windowContainer.remove (self.buttonBox)
        self.windowContainer.pack_start (zvt)

#        self.ics.setHelpEnabled (0)
        self.ics.readHTML ("fdiskpart")
	self.ics.setPrevEnabled (0)
        self.ics.setNextEnabled (0)

    # FDiskWindow tag="fdisk"
    def getScreen (self):
#        from installpath_gui import InstallPathWindow
#
###
###  msf - 05-11-2000 - change how we determine if we should be run
###        
#        if ((not InstallPathWindow.fdisk) or
#            (not InstallPathWindow.fdisk.get_active ())):
#               return None
#
# 
###  here is fix
#
        from rootpartition_gui import AutoPartitionWindow

        if not AutoPartitionWindow.manuallyPartitionfdisk.get_active():
           return None

	self.todo.fstab.closeDrives()

        self.windowContainer = GtkVBox (FALSE)
        self.buttonBox = GtkVBox (FALSE, 5)
        self.buttonBox.set_border_width (5)
        box = GtkVButtonBox ()
        label = GtkLabel (_("Select drive to run fdisk on"))

        for drive in self.todo.fstab.driveList():
            button = GtkButton (drive)
            button.connect ("clicked", self.button_clicked, drive)
            box.add (button)

        self.buttonBox.pack_start (label, FALSE)
        self.buttonBox.pack_start (box, FALSE)
        self.windowContainer.pack_start (self.buttonBox)

        self.ics.setNextEnabled (1)

        return self.windowContainer
