from gtk import *
from iw_gui import *
from thread import *
import isys
from translate import _

class FormatWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Choose partitions to Format"))
        ics.setNextEnabled (1)
##         ics.setHTML ("<HTML><BODY>Choose partitions to Format</BODY></HTML>")
        ics.readHTML ("format")

    def getScreen (self):
        def toggled (widget, (todo, dev)):
            if widget.get_active ():
		todo.fstab.setFormatFilesystem(dev, 1)
            else:
		todo.fstab.setFormatFilesystem(dev, 0)

        def check (widget, todo):
            todo.fstab.setBadBlockCheck(widget.get_active ())

        box = GtkVBox (FALSE, 10)

        mounts = self.todo.fstab.mountList()

	gotOne = 0
	for (mount, dev, fstype, format, size) in mounts:
            if fstype == "ext2":
		gotOne = 1
                checkButton = GtkCheckButton ("/dev/%s   %s" % (dev, mount))
                checkButton.set_active (format)
                checkButton.connect ("toggled", toggled, (self.todo, dev))
                box.pack_start (checkButton)

	if not gotOne: return None

        vbox = GtkVBox (FALSE, 10)
        vbox.pack_start (box, FALSE, TRUE)

        vbox.pack_start (GtkHSeparator (), FALSE, padding=3)
        
        self.check = GtkCheckButton (_("Check for bad blocks while formatting"))
        self.check.set_active (self.todo.fstab.getBadBlockCheck())
        self.check.connect ("toggled", check, self.todo)
        vbox.pack_start (self.check, FALSE)
        
        self.check = GtkCheckButton 
	vbox.set_border_width (5)
        return vbox
