from gtk import *
from iw import *
from thread import *
import isys
from gui import _

class ConfirmPartitionWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Confirm Partitioning Selection"))
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
        ics.setTitle (_("Root Partition Selection"))
        ics.setHTML ("<HTML><BODY>Select a root partition"
                     "</BODY></HTML>")
	ics.setNextEnabled (TRUE)
	self.skippedScreen = 0

    def getNext (self):
	self.todo.ddruid.next ()
        
	if not self.skippedScreen:

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

	if self.skippedScreen:
	    # if we skipped it once, skip it again
	    return None

        if not self.todo.ddruid:
            drives = self.todo.drives.available ().keys ()
            drives.sort ()
            self.todo.ddruid = \
                fsedit(1, drives, [])
	    self.todo.ddruid.next()
            self.todo.ddruid.setCallback (self.enableCallback, self)

	self.todo.instClass.finishPartitioning(self.todo.ddruid)
	if (self.todo.instClass.skipPartitioning): 
	    self.skippedScreen = 1
	    return None

        self.bin = GtkFrame (None, _obj = self.todo.ddruid.getWindow ())
        self.bin.set_shadow_type (SHADOW_NONE)
        self.todo.ddruid.edit ()
        
        return self.bin
