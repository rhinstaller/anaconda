from gtk import *
from iw import *
from thread import *
import isys

def _(x):
    return x

class FormatWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Choose partitions to Format"))
        ics.setNextEnabled (1)
        ics.setHTML ("<HTML><BODY>Choose partitions to Format</BODY></HTML>")

    def getScreen (self):
        def toggled (widget, (todo, mount)):
            if widget.get_active ():
                (dev, fstype, format) = todo.mounts[mount]
                todo.mounts[mount] = (dev, fstype, 1)
            else:
                (dev, fstype, format) = todo.mounts[mount]
                todo.mounts[mount] = (dev, fstype, 0)

        def check (widget, todo):
            todo.badBlockCheck = widget.get_active ()

        box = GtkVBox (FALSE, 10)

        mounts = self.todo.mounts.keys ()
        mounts.sort ()

        for mount in mounts:
            (dev, fstype, format) = self.todo.mounts[mount]
            if fstype == "ext2":
                checkButton = GtkCheckButton ("/dev/%s   %s" % (dev, mount))
                checkButton.set_active (format)
                checkButton.connect ("toggled", toggled, (self.todo, mount))
                box.pack_start (checkButton)

        vbox = GtkVBox (FALSE, 10)
        vbox.pack_start (box, FALSE, TRUE)
        
        self.check = GtkCheckButton (_("Check for bad blocks while formatting"))
        self.check.set_active (self.todo.badBlockCheck)
        self.check.connect ("toggled", check, self.todo)
        vbox.pack_start (self.check, FALSE)
        
        self.check = GtkCheckButton 

        return vbox
