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
        ics.readHTML ("partition")
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
	if self.skippedScreen:
	    # if we skipped it once, skip it again
	    return None

	if self.todo.getSkipPartitioning():
	    self.skippedScreen = 1
	    return None

        self.bin = GtkFrame (None, _obj = self.todo.ddruid.getWindow ())
        self.bin.set_shadow_type (SHADOW_NONE)
        self.todo.ddruid.edit ()
        
        return self.bin

class AutoPartitionWindow(InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Automatic Partitioning"))
        ics.setHTML ("<HTML><BODY>Confirm automatic partitioning"
                     "</BODY></HTML>")
	ics.setNextEnabled (TRUE)

    def getNext(self):
        from gnomepyfsedit import fsedit

	if (self.__dict__.has_key("manuallyPartition") and   
		self.manuallyPartition.get_active()):
            drives = self.todo.drives.available ().keys ()
            drives.sort ()
            self.todo.ddruid = fsedit(0, drives, self.fstab)
	    self.todo.manuallyPartition()
	    
	return None

    def getScreen (self):   
        from gnomepyfsedit import fsedit

	todo = self.todo

        self.fstab = []
        for mntpoint, (dev, fstype, reformat) in todo.mounts.items ():
            self.fstab.append ((dev, mntpoint))

        if not todo.ddruid:
            drives = todo.drives.available ().keys ()
            drives.sort ()
            todo.ddruid = fsedit(0, drives, self.fstab)
	    todo.instClass.finishPartitioning(todo.ddruid)

	if not todo.getPartitionWarningText(): 
	    return None

	label = GtkLabel(
	    _("%s\n\nIf you don't want to do this, you can continue with "
	      "this install by partitioning manually, or you can go back "
	      "and perform a fully customized installation.") % 
		    (todo.getPartitionWarningText(), ))
	label.set_line_wrap(TRUE)
	label.set_alignment(0.0, 0.0)
	label.set_usize(400, -1)

        box = GtkVBox (FALSE)
	box.pack_start(label, FALSE)

        radioBox = GtkVBox (FALSE)
	self.continueChoice = GtkRadioButton (None, _("Remove data"))
	radioBox.pack_start(self.continueChoice, FALSE)
	self.manuallyPartition = GtkRadioButton(
		self.continueChoice, _("Manually partition"))
	radioBox.pack_start(self.manuallyPartition, FALSE)

	align = GtkAlignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, TRUE, TRUE)

	return box



