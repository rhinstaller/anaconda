from gtk import *
from iw_gui import *
from thread import *
import isys
from translate import _
import gui
from fdisk_gui import *
import isys
import iutil

CHOICE_FDISK = 1
CHOICE_DDRUID = 2
CHOICE_AUTOPART = 3


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
###
###    msf - 05/11/2000 - removed this block shouldnt be needed with changes
###
#
#	if not self.__dict__.has_key("manuallyPartitionddruid"):
#            # if druid wasn't running, must have been in autopartition mode
#            # clear fstab cache so we don't get junk from attempted
#            # autopartitioning
#            print "number 1"
#            clearcache = not self.todo.fstab.getRunDruid()
#	    self.todo.fstab.setRunDruid(1)
#            self.todo.fstab.setReadonly(0)
#            #print "Rescanning partitions 1 - ", clearcache
#            self.todo.fstab.rescanPartitions(clearcache)
#	    self.todo.instClass.removeFromSkipList("format")
	if AutoPartitionWindow.manuallyPartitionddruid.get_active():
            if self.druid:
                del self.druid
            # see comment above about clearing cache

            if self.lastChoice != CHOICE_DDRUID:
                clearcache = 1
            else:
                clearcache = 0
#            clearcache = not self.todo.fstab.getRunDruid()
	    self.todo.fstab.setRunDruid(1)
            self.todo.fstab.setReadonly(0)
            #print "Rescanning partitions 2 - ", clearcache
	    self.todo.fstab.rescanPartitions(clearcache)
	    self.todo.instClass.removeFromSkipList("format")
            self.lastChoice = CHOICE_DDRUID
        elif AutoPartitionWindow.manuallyPartitionfdisk.get_active():
            self.todo.fstab.setRunDruid(1)
            self.todo.fstab.setReadonly(1)
            self.lastChoice = CHOICE_FDISK
	else:
	    self.todo.fstab.setRunDruid(0)
	    self.todo.fstab.setDruid(self.druid, self.todo.instClass.raidList)
	    self.todo.fstab.formatAllFilesystems()
	    self.todo.instClass.addToSkipList("format")
            self.lastChoice = CHOICE_AUTOPART

	self.beingDisplayed = 0
	return None

    def __init__(self, ics):
	InstallWindow.__init__(self, ics)
        ics.setTitle (_("Automatic Partitioning"))
	self.druid = None
	self.beingDisplayed = 0
        self.lastChoice = None

    def getScreen (self):   

        # XXX hack
        if self.todo.instClass.clearType:
            self.ics.readHTML (self.todo.instClass.clearType)

	todo = self.todo
	self.druid = None

# user selected an install type which had predefined partitioning
# attempt to automatically allocate these partitions.
#
# if this fails we drop them into disk druid
#
        attemptedPartitioningandFailed = 0
	if self.todo.instClass.partitions:
	    self.druid = \
		todo.fstab.attemptPartitioning(todo.instClass.partitions,
                                               todo.instClass.fstab,
					       todo.instClass.clearParts)

            if not self.druid:
                attemptedPartitioningandFailed = 1

#
# if no warning text means we have carte blanc to blow everything away
# without telling user
#
	if not todo.getPartitionWarningText() and self.druid:

            self.ics.setNextEnabled (TRUE)

	    self.todo.fstab.setRunDruid(0)
	    self.todo.fstab.setDruid(self.druid)
	    self.todo.fstab.formatAllFilesystems()
	    self.todo.instClass.addToSkipList("format")
	    return

#
# see what means the user wants to use to partition
#
        self.todo.fstab.setRunDruid(1)
        self.todo.fstab.setReadonly(0)

        if self.druid:
            self.ics.setTitle (_("Automatic Partitioning"))
            label = \
                  GtkLabel(_("%s\n\nIf you don't want to do this, you can continue with "
                             "this install by partitioning manually, or you can go back "
                             "and perform a fully customized installation.") % 
                           (_(todo.getPartitionWarningText()), ))
        else:
            if attemptedPartitioningandFailed:
                self.ics.setTitle (_("Automatic Partitioning Failed"))
                label = GtkLabel(_("\nThere is not sufficient disk space in "
                                   "order to automatically partition your disk. "
                                   "You will need to manually partition your "
                                   "disks for Red Hat Linux to install."
                                   "\n\nPlease choose the tool you would like to "
                                   "use to partition your system for Red Hat Linux."))
            else:
                self.ics.setTitle (_("Manual Partitioning"))
                label = GtkLabel(_("\nPlease choose the tool you would like to "
                                   "use to partition your system for Red Hat Linux."))
            
        label.set_line_wrap(TRUE)
        label.set_alignment(0.0, 0.0)
        label.set_usize(380, -1)
            
        box = GtkVBox (FALSE)
	box.pack_start(label, FALSE)
        box.set_border_width (5)

        radioBox = GtkVBox (FALSE)

        if self.druid:
            self.continueChoice = GtkRadioButton (None, _("Automatically partition and REMOVE DATA"))
            radioBox.pack_start(self.continueChoice, FALSE)
            firstbutton = self.continueChoice
        else:
            firstbutton = None
        
	AutoPartitionWindow.manuallyPartitionddruid = GtkRadioButton(
		firstbutton, _("Manually partition with Disk Druid"))

        if self.lastChoice == CHOICE_DDRUID:
            AutoPartitionWindow.manuallyPartitionddruid.set_active(1)

        if firstbutton == None:
            secondbutton = AutoPartitionWindow.manuallyPartitionddruid
        else:
            secondbutton = firstbutton
            
	radioBox.pack_start(AutoPartitionWindow.manuallyPartitionddruid, FALSE)
	AutoPartitionWindow.manuallyPartitionfdisk = GtkRadioButton(
		secondbutton, _("Manually partition with fdisk [experts only]"))
	radioBox.pack_start(AutoPartitionWindow.manuallyPartitionfdisk, FALSE)

        if self.lastChoice == CHOICE_FDISK:
            AutoPartitionWindow.manuallyPartitionfdisk.set_active(1)
            
	align = GtkAlignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, TRUE, TRUE)
	box.set_border_width (5)

        self.ics.setNextEnabled (TRUE)

	self.beingDisplayed = 1
	return box



