from gtk import *
from iw import *
from thread import *
import isys

class ConfirmPartitionWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle ("Confirm Partitioning Selection")
        ics.setHTML ("<HTML><BODY>Select a root partition"
                     "</BODY></HTML>")
	ics.setNextEnabled (TRUE)
        
    def getScreen (self):
        return self.window

    def getPrev (self):
        return PartitionWindow

class PartitionWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle ("Root Partition Selection")
        ics.setHTML ("<HTML><BODY>Select a root partition"
                     "</BODY></HTML>")
	ics.setNextEnabled (TRUE)

    def getNext (self):
        print "calling self.ddruid.next ()"
        self.todo.ddruid.next ()
        print "done calling self.ddruid.next ()"
        
        win = self.todo.ddruid.getConfirm ()
        if win:
            print "confirm"
            bin = GtkFrame (None, _obj = win)
            bin.set_shadow_type (SHADOW_NONE)
            window = ConfirmPartitionWindow
            window.window = bin
            return window

        fstab = self.todo.ddruid.getFstab ()
        for (partition, mount, fsystem, size) in fstab:
            self.todo.addMount(partition, mount, fsystem)

        return None

    def enableCallback (self, value):
        self.ics.setNextEnabled (value)

    def getScreen (self):
        from gnomepyfsedit import fsedit

        if not self.todo.ddruid:
            self.todo.ddruid = \
                fsedit(1, self.todo.drives.available ().keys (), [])
            self.todo.ddruid.setCallback (self.enableCallback, self)
   
        self.bin = GtkFrame (None, _obj = self.todo.ddruid.getWindow ())
        self.bin.set_shadow_type (SHADOW_NONE)
        self.todo.ddruid.edit ()
        
        return self.bin
