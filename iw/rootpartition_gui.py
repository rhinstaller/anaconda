from gtk import *
from iw_gui import *
from thread import *
import isys
from translate import _
import gui
from fdisk_gui import *
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

	self.todo.fstab.savePartitions()
	self.todo.fstab.turnOnSwap(self.todo.intf.waitWindow)
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

        if self.todo.fstab.rootOnLoop():
            return LoopSizeWindow

        return None

    def enableCallback (self, value):
        self.ics.setNextEnabled (value)

    def getScreen (self):
	self.running = 0
	if not self.todo.fstab.getRunDruid(): return None
	self.running = 1
	return self.todo.fstab.runDruid(self.enableCallback)

class LoopSizeWindow(InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.readHTML ("loopback")

    def getNext (self):
        self.todo.fstab.setLoopbackSize (self.sizeAdj.value, self.swapAdj.value)

    def getScreen (self):
        # XXX error check mount that this check tries
        avail = apply(isys.spaceAvailable, self.todo.fstab.getRootDevice())
	(size, swapSize) = self.todo.fstab.getLoopbackSize()
	if not size:
	    size = avail / 2
	    swapSize = 32

        vbox = GtkVBox (FALSE, 5)
        
        label = GtkLabel (
		_("You've chosen to put your root filesystem in a file on "
		  "an already-existing DOS or Windows filesystem. How large, "
		  "in megabytes, should would you like the root filesystem "
		  "to be, and how much swap space would you like? They must "
		  "total less then %d megabytes in size." % (avail, )))
        label.set_usize (400, -1)
        label.set_line_wrap (TRUE)
        vbox.pack_start (label, FALSE, FALSE)

	upper = avail
	if avail > 2000:
	    upper = 2000

        # XXX lower is 150
        self.sizeAdj = GtkAdjustment (value = size, lower = 150, upper = upper, step_incr = 1)
        self.sizeSpin = GtkSpinButton (self.sizeAdj, digits = 0)
        self.sizeSpin.set_usize (100, -1)

        self.swapAdj = GtkAdjustment (value = swapSize, lower = 16, upper = upper, step_incr = 1)
        self.swapSpin = GtkSpinButton (self.swapAdj, digits = 0)
        self.swapSpin.set_usize (100, -1)

        table = GtkTable ()

        label = GtkLabel (_("Root filesystem size:"))
        label.set_alignment (1.0, 0.5)
        table.attach (label, 0, 1, 0, 1, xpadding=5, ypadding=5)
        table.attach (self.sizeSpin, 1, 2, 0, 1, xpadding=5, ypadding=5)

        label = GtkLabel (_("Swap space size:"))
        label.set_alignment (1.0, 0.5)
        table.attach (label, 0, 1, 1, 2, xpadding=5, ypadding=5)
        table.attach (self.swapSpin, 1, 2, 1, 2, xpadding=5, ypadding=5)

        align = GtkAlignment ()
        align.add (table)
        align.set (0, 0, 0.5, 0.5)
        vbox.pack_start (align, FALSE, FALSE)

	self.ics.setNextEnabled (TRUE)

        return vbox
        
class AutoPartitionWindow(InstallWindow):
    def getPrev(self):
	self.druid = None
	self.beingDisplayed = 0

    def getNext(self):
	if not self.beingDisplayed: return

	if not self.__dict__.has_key("manuallyPartition"):
            # if druid wasn't running, must have been in autopartition mode
            # clear fstab cache so we don't get junk from attempted
            # autopartitioning
            clearcache = not self.todo.fstab.getRunDruid()
	    self.todo.fstab.setRunDruid(1)
            #print "Rescanning partitions 1 - ", clearcache
            self.todo.fstab.rescanPartitions(clearcache)
	    self.todo.instClass.removeFromSkipList("format")
	elif self.manuallyPartition.get_active():
            del self.druid
            # see comment above about clearing cache
            clearcache = not self.todo.fstab.getRunDruid()
	    self.todo.fstab.setRunDruid(1)
            #print "Rescanning partitions 2 - ", clearcache
	    self.todo.fstab.rescanPartitions(clearcache)
	    self.todo.instClass.removeFromSkipList("format")
	else:
	    self.todo.fstab.setRunDruid(0)
	    self.todo.fstab.setDruid(self.druid, self.todo.instClass.raidList)
	    self.todo.fstab.formatAllFilesystems()
	    self.todo.instClass.addToSkipList("format")

	self.beingDisplayed = 0
	    
	return None

    def __init__(self, ics):
	InstallWindow.__init__(self, ics)
        ics.setTitle (_("Automatic Partitioning"))
	self.druid = None
	self.beingDisplayed = 0

    def getScreen (self):   
        from installpath_gui import InstallPathWindow

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
                                               todo.instClass.fstab,
					       todo.instClass.clearParts)
	self.ics.setNextEnabled (TRUE)

	if not self.druid:
	    # auto partitioning failed
	    self.todo.fstab.setRunDruid(1)
	    return

	if not todo.getPartitionWarningText():
	    self.todo.fstab.setRunDruid(0)
	    self.todo.fstab.setDruid(self.druid)
	    self.todo.fstab.formatAllFilesystems()
	    self.todo.instClass.addToSkipList("format")
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



