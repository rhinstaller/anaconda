from gtk import *
from iw import *
from thread import *
import isys
from gui import _
import gui
from fdisk import *
import isys
import iutil

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
    swapon = 0
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Disk Druid"))
        ics.readHTML ("partition")
	ics.setNextEnabled (FALSE)
	self.skippedScreen = 0
        self.swapon = 0

    def checkSwap (self):
        if PartitionWindow.swapon or (iutil.memInstalled() > 34000):
	    return 1

        threads_leave ()
	message = gui.MessageWindow(_("Low Memory"),
		   _("As you don't have much memory in this machine, we "
		     "need to turn on swap space immediately. To do this "
		     "we'll have to write your new partition table to the "
		     "disk immediately. Is that okay?"), "okcancel")

	if (message.getrc () == 1):
	    threads_enter ()
	    return 0

	self.todo.ddruid.save ()
	self.fstab.turnOnSwap(self.intf.waitWindow)
	self.todo.ddruidAlreadySaved = 1
	PartitionWindow.swapon = 1

        threads_enter ()

        return 1

    def getNext (self):
	if not self.running: return 0
	self.todo.fstab.runDruidFinished()

        # FIXME
	#if not self.skippedScreen:
	    #win = self.todo.ddruid.getConfirm ()
	    #if win:
		#bin = GtkFrame (None, _obj = win)
		#bin.set_shadow_type (SHADOW_NONE)
		#window = ConfirmPartitionWindow
		#window.window = bin
		#return window

	bootPartition = None
	rootPartition = None

        if not self.checkSwap ():
            return PartitionWindow

        return None

    def enableCallback (self, value):
        self.ics.setNextEnabled (value)

    def getScreen (self):
	self.running = 0
	if not self.todo.fstab.getRunDruid(): return None
	self.running = 1
	return self.todo.fstab.runDruid(self.enableCallback)

class AutoPartitionWindow(InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Automatic Partitioning"))
	ics.setNextEnabled (TRUE)
        self.ics = ics

    def getPrev(self):
	self.druid = None
	self.beingDisplayed = 0

    def getNext(self):
	if not self.beingDisplayed: return

	if not self.__dict__.has_key("manuallyPartition"):
	    self.todo.fstab.setRunDruid(1)
	elif self.manuallyPartition.get_active():
	    self.todo.fstab.setRunDruid(1)
	    self.todo.fstab.rescanPartitions()
	else:
	    self.todo.fstab.setRunDruid(0)
	    self.todo.fstab.setDruid(self.druid)

	self.beingDisplayed = 0
	    
	return None

    def __init__(self, todo):
	InstallWindow.__init__(self, todo)
	self.druid = None
	self.beingDisplayed = 0

    def getScreen (self):   
        from installpath import InstallPathWindow

        if (InstallPathWindow.fdisk and
            InstallPathWindow.fdisk.get_active ()):
		return None
        
        # XXX hack
        if self.todo.instClass.clearType:
            self.ics.readHTML (self.todo.instClass.clearType)

	todo = self.todo
	self.druid = None

	if self.todo.instClass.partitions:
	    self.druid = \
		todo.fstab.attemptPartitioning(todo.instClass.partitions,
					       todo.instClass.clearParts)
	self.ics.setNextEnabled (TRUE)

	if not self.druid:
	    # auto partitioning failed
	    self.todo.fstab.setRunDruid(1)
	    return

	if not todo.getPartitionWarningText():
	    self.fstab.setRunDruid(0)
	    return

	label = \
           GtkLabel(_("%s\n\nIf you don't want to do this, you can continue with "
	      "this install by partitioning manually, or you can go back "
	      "and perform a fully customized installation.") % 
		    (_(todo.getPartitionWarningText()), ))

	label.set_line_wrap(TRUE)
	label.set_alignment(0.0, 0.0)
	label.set_usize(400, -1)

        box = GtkVBox (FALSE)
	box.pack_start(label, FALSE)
        box.set_border_width (5)

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
	box.set_border_width (5)
	self.beingDisplayed = 1
	return box



