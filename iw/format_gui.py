from gtk import *
from iw_gui import *
from thread import *
import isys
from translate import _
from rootpartition_gui import AutoPartitionWindow
import gui

class FormatWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Choose partitions to Format"))
        ics.setNextEnabled (1)
##         ics.setHTML ("<HTML><BODY>Choose partitions to Format</BODY></HTML>")
        ics.readHTML ("format")

    def getNext(self):
	threads_leave()
	rc = self.todo.fstab.checkFormatting(self.todo.intf.messageWindow)
	threads_enter()

	if rc:
	    raise gui.StayOnScreen

    # FormatWindow tag="format"
    def getScreen (self):
        def toggled (widget, (todo, dev)):
            if widget.get_active ():
		todo.fstab.setFormatFilesystem(dev, 1)
            else:
		todo.fstab.setFormatFilesystem(dev, 0)

        def check (widget, todo):
            todo.fstab.setBadBlockCheck(widget.get_active ())

        box = GtkVBox (FALSE, 10)

        mounts = self.todo.fstab.formattablePartitions()

	gotOne = 0
        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
	for (mount, dev, fstype, format, size) in mounts:
	    gotOne = 1
	    checkButton = GtkCheckButton ("/dev/%s   %s" % (dev, mount))
	    checkButton.set_active (format)
	    checkButton.connect ("toggled", toggled, (self.todo, dev))
	    box.pack_start (checkButton, FALSE, FALSE)

	if not gotOne: return None

        sw.add_with_viewport (box)
        viewport = sw.children()[0]
        viewport.set_shadow_type (SHADOW_ETCHED_IN)
        
        vbox = GtkVBox (FALSE, 10)
        vbox.pack_start (sw, TRUE, TRUE)

        self.check = GtkCheckButton (_("Check for bad blocks while formatting"))
        self.check.set_active (self.todo.fstab.getBadBlockCheck())
        self.check.connect ("toggled", check, self.todo)
        vbox.pack_start (self.check, FALSE)
        
        self.check = GtkCheckButton 
	vbox.set_border_width (5)
        return vbox
