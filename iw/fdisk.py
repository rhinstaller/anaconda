from gtk import *
from iw import *
from gnome.zvt import *
from os import execvp
from gui import _
import isys

class FDiskWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setTitle (_("fdisk"))

    def child_died (self, widget, button):
        self.windowContainer.remove (self.windowContainer.children ()[0])
        self.windowContainer.pack_start (self.buttonBox)
        button.set_state (STATE_NORMAL)
        
        self.ics.setPrevEnabled (1)
        self.ics.setNextEnabled (1)
        self.ics.setHelpEnabled (1)

    def button_clicked (self, widget, drive):
        zvt = ZvtTerm (80, 24)
        zvt.connect ("child_died", self.child_died, widget)
        if zvt.forkpty() == 0:
            if os.access ("/usr/sbin/fdisk", os.X_OK):
                path = "/usr/sbin/fdisk"
            else:
                path = "/sbin/fdisk"
            execvp (path, ("fdisk", "/dev/%s" % (drive,)))
        zvt.show ()

        self.windowContainer.remove (self.buttonBox)
        self.windowContainer.pack_start (zvt)

        self.ics.setHelpEnabled (0)
	self.ics.setPrevEnabled (0)
        self.ics.setNextEnabled (0)


    def getScreen (self):
        self.windowContainer = GtkVBox (FALSE)
        self.buttonBox = GtkVBox (FALSE, 5)
        self.buttonBox.set_border_width (5)
        box = GtkVButtonBox ()
        label = GtkLabel (_("Select drive to run fdisk on"))

        drives = self.todo.drives.available ().keys ()
	drives.sort(isys.compareDrives)
        for drive in drives:
            button = GtkButton (drive)
            button.connect ("clicked", self.button_clicked, drive)
            box.add (button)

        self.buttonBox.pack_start (label, FALSE)
        self.buttonBox.pack_start (box, FALSE)
        self.windowContainer.pack_start (self.buttonBox)

        return self.windowContainer
