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
	if 0 and self.todo.getSkipPartitioning():
	    self.skippedScreen = 1
	    fstab = self.todo.ddruid.getFstab ()
	    self.todo.resetMounts()
	    for (partition, mount, fsystem, size) in fstab:
		self.todo.addMount(partition, mount, fsystem)
		if mount == "/":
		    rootPartition = partition
		elif mount == "/boot":
		    bootPartition = partition
            if not self.checkSwap ():
                return AutoPartitionWindow
	    return None

	return self.todo.fstab.runDruid(self.enableCallback)

        return self.bin

class AutoPartitionWindow(InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Automatic Partitioning"))
	ics.setNextEnabled (TRUE)
        self.ics = ics

    def getNext(self):
        from gnomepyfsedit import fsedit

	if (self.__dict__.has_key("manuallyPartition") and   
		self.manuallyPartition.get_active()):
	    self.todo.manuallyPartition()
	    
	return None

    def getScreen (self):   
        from gnomepyfsedit import fsedit
        from installpath import InstallPathWindow

	return None

        if (InstallPathWindow.fdisk and
            InstallPathWindow.fdisk.get_active ()):
		self.todo.manuallyPartition()
		return None
        
        # XXX hack
        if self.todo.instClass.clearType:
            self.ics.readHTML (self.todo.instClass.clearType)

	todo = self.todo

        self.fstab = []
        for mntpoint, (dev, fstype, reformat) in todo.mounts.items ():
            self.fstab.append ((dev, mntpoint))

        if not todo.ddruid:
            drives = todo.drives.available ().keys ()
            drives.sort (isys.compareDrives)
            todo.ddruid = fsedit(0, drives, self.fstab, self.todo.zeroMbr,
				  self.todo.ddruidReadOnly)
            if not todo.instClass.finishPartitioning(todo.ddruid):
                self.todo.log ("Autopartitioning FAILED\n")

	if not todo.getPartitionWarningText(): 
	    return None

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
	return box



