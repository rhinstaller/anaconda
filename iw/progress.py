from gtk import *
from iw import *
import string
import rpm
import time

class InstallProgressWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Installing Packages")
        ics.setPrevEnabled (0)

	self.numComplete = 0
	self.sizeComplete = 0
        
    def setPackageScale (self, amount, total):
        threads_enter ()
	self.progress.update (float (amount) / total)
        threads_leave ()

    def completePackage(self, header):
        def formatTime(amt):
            hours = amt / 60 / 60
            amt = amt % (60 * 60)
            min = amt / 60
            amt = amt % 60
            secs = amt

            return "%01d:%02d.%02d" % (int(hours) ,int(min), int(secs))

        self.numComplete = self.numComplete + 1
        apply (self.clist.set_text, self.status["completed"]["packages"] + ("%d" % self.numComplete,))

	self.sizeComplete = self.sizeComplete + header[rpm.RPMTAG_SIZE]
        apply (self.clist.set_text, self.status["completed"]["size"] +
                                    ("%d M" % (self.sizeComplete / (1024 * 1024)),))

        apply (self.clist.set_text, self.status["remaining"]["packages"] +
                                    ("%d" % (self.numTotal - self.numComplete),))

        apply (self.clist.set_text, self.status["remaining"]["size"] +
                                    ("%d M" % ((self.totalSize - self.sizeComplete) / (1024 * 1024)),))

	elapsedTime = time.time() - self.timeStarted 
        apply (self.clist.set_text, self.status["completed"]["time"] + ("%s" % formatTime(elapsedTime),))

	finishTime = (float (self.totalSize) / self.sizeComplete) * elapsedTime
        apply (self.clist.set_text, self.status["total"]["time"] + ("%s" % formatTime(finishTime),))

	remainingTime = finishTime - elapsedTime
        apply (self.clist.set_text, self.status["remaining"]["time"] + ("%s" % formatTime(remainingTime),))

        return

#        self.clist.set_text ("%d" % self.numComplete,
#                             status["completed"]["packages"]["row"],
#                             status["completed"]["packages"]["


	self.timeCompleteW.setText("%12s" % formatTime(elapsedTime))

	self.timeTotalW.setText("%12s" % formatTime(finishTime))

    def setPackage(self, header):
        threads_enter ()
        self.name.set_text (header[rpm.RPMTAG_NAME])
        self.size.set_text ("%.1f KBytes" % (header[rpm.RPMTAG_SIZE] / 1024.0))
        self.summary.set_text (header[rpm.RPMTAG_SUMMARY])
        threads_leave ()

    def setSizes (self, total, totalSize):
        self.numTotal = total
        self.totalSize = totalSize
        self.timeStarted = time.time ()

        apply (self.clist.set_text, self.status["total"]["packages"] + ("%d" % total,))
        
        apply (self.clist.set_text, self.status["total"]["size"] +
                                    ("%d M" % (totalSize / (1024 * 1024)),))

    def getScreen (self):
	table = GtkTable (3, 3)
	label = GtkLabel ("Package")
        label.set_alignment (0.0, 0.0)
	table.attach (label, 0, 1, 0, 1, FILL, 0)
	label = GtkLabel (":")
	table.attach (label, 1, 2, 0, 1, 0, 0, 5)
	label = GtkLabel (":")
	table.attach (label, 1, 2, 1, 2, 0, 0, 5)
	label = GtkLabel (":")
	label.set_alignment (0.0, 0.0)
	table.attach (label, 1, 2, 2, 3, 0, FILL | EXPAND, 5)
	label = GtkLabel ("Size")
        label.set_alignment (0.0, 0.0)
	table.attach (label, 0, 1, 1, 2, FILL, 0)
	label = GtkLabel ("Summary")
        label.set_alignment (0.0, 0.0)
	table.attach (label, 0, 1, 2, 3, FILL, FILL | EXPAND)

	self.name = GtkLabel();
        self.name.set_alignment (0.0, 0.0)
	self.size = GtkLabel();
        self.size.set_alignment (0.0, 0.0)
	self.summary = GtkLabel();
        self.summary.set_alignment (0.0, 0.0)
        self.summary.set_line_wrap (TRUE)
	self.summary.set_text ("\n\n")
	table.attach(self.name, 2, 3, 0, 1, FILL | EXPAND, 0)
	table.attach(self.size, 2, 3, 1, 2, FILL | EXPAND, 0)
	table.attach(self.summary, 2, 3, 2, 3, FILL | EXPAND, FILL | EXPAND)

        vbox = GtkVBox (FALSE, 10)
        vbox.pack_start (table, FALSE)

	self.progress = GtkProgressBar()
        vbox.pack_start (self.progress, FALSE)

        self.status =  {
            "total" :     { "packages" : (0, 1),
                            "size"     : (0, 2),
                            "time"     : (0, 3) },
            "completed" : { "packages" : (1, 1),
                            "size"     : (1, 2),
                            "time"     : (1, 3) },
            "remaining" : { "packages" : (2, 1),
                            "size"     : (2, 2),
                            "time"     : (2, 3) }
            }

        clist = GtkCList (4, ("Status", "Packages", "Size", "Time"))
        clist.set_column_justification (0, JUSTIFY_LEFT)
        clist.set_column_justification (1, JUSTIFY_RIGHT)
        clist.set_column_justification (2, JUSTIFY_RIGHT)
        clist.set_column_justification (3, JUSTIFY_RIGHT)
        clist.append (("Total", "0", "0", "0:00.00"))
        clist.append (("Completed", "0", "0", "0:00.00"))
        clist.append (("Remaining", "0", "0", "0:00.00"))
#        clist.set_column_auto_resize (0, TRUE)
	clist.columns_autosize ()
        self.clist = clist
        vbox.pack_start (clist, TRUE)

	self.ics.getInstallInterface ().setPackageProgressWindow (self)
	return vbox

