from gtk import *
from iw_gui import *
import string
import rpm
import time
import os
from threading import *
from translate import _
import sys

class DoInstall (Thread):
    def __init__ (self, icw, todo):
        self.todo = todo
        self.icw = icw
        Thread.__init__ (self)

    def run (self):
        from exception import handleException
        try:
            rc = self.todo.doInstall ()
        except SystemExit, code:
            import os, signal

            print "shutting down"
            self.todo.intf.shutdown()
            print "shut down"
            os.kill(os.getpid(), signal.SIGTERM)
            
        except:
            threads_enter ()
            handleException(self.todo, sys.exc_info())
        threads_enter ()
        if rc:
            self.icw.prevClicked ()
        else:
            self.icw.nextClicked ()
        threads_leave ()
                
class InstallProgressWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Installing Packages"))
        ics.readHTML ("installing")
        ics.setPrevEnabled (FALSE)
        ics.setHelpButtonEnabled (FALSE)

        self.todo = ics.getToDo ()
	self.numComplete = 0
	self.sizeComplete = 0
        
    def setPackageScale (self, amount, total):
        threads_enter ()
	self.progress.update (float (amount) / total)
#        self.totalProgress.update (float (self.sizeComplete + amount) / self.totalSize)
        threads_leave ()

    def completePackage(self, header):
        def formatTime(amt):
            hours = amt / 60 / 60
            amt = amt % (60 * 60)
            min = amt / 60
            amt = amt % 60
            secs = amt

            return "%01d:%02d.%02d" % (int(hours) ,int(min), int(secs))

        threads_enter ()
        self.numComplete = self.numComplete + 1

        apply (self.clist.set_text, self.status["completed"]["packages"] + ("%d" % self.numComplete,))

	self.sizeComplete = self.sizeComplete + (header[rpm.RPMTAG_SIZE]/1024)

        apply (self.clist.set_text, self.status["completed"]["size"] +
               ("%d M" % (self.sizeComplete/1024),))

        apply (self.clist.set_text, self.status["remaining"]["packages"] +
               ("%d" % (self.numTotal - self.numComplete),))

        apply (self.clist.set_text, self.status["remaining"]["size"] +
               ("%d M" % (self.totalSize/1024 - self.sizeComplete/1024),))

        # check to see if we've started yet
        if (self.timeStarted == -1):
            self.timeStarted = time.time ()
            elapsedTime = 1
        else:
            elapsedTime = time.time() - self.timeStarted

        apply (self.clist.set_text, self.status["completed"]["time"] + ("%s" % formatTime(elapsedTime),))

        if self.sizeComplete != 0:
            finishTime = (float (self.totalSize) / self.sizeComplete) * elapsedTime
        else:
            finishTime = (float (self.totalSize) / self.sizeComplete+1) * elapsedTime


        apply (self.clist.set_text, self.status["total"]["time"] + ("%s" % formatTime(finishTime),))

	remainingTime = finishTime - elapsedTime
        apply (self.clist.set_text, self.status["remaining"]["time"] + ("%s" % formatTime(remainingTime),))

        self.totalProgress.update (float (self.sizeComplete) / self.totalSize)
        threads_leave ()
        
        return
	self.timeCompleteW.setText("%12s" % formatTime(elapsedTime))
	self.timeTotalW.setText("%12s" % formatTime(finishTime))

    def setPackage(self, header):
        threads_enter ()
        if len(self.pixmaps):
            if not (self.numComplete) % (self.numTotal / len(self.pixmaps)):
                if self.numComplete:
                    num = self.numComplete * len(self.pixmaps) / self.numTotal
                else:
                    num = 0
                im = self.ics.readPixmap (self.pixmaps[num])
                im.render ()
                pix = im.make_pixmap ()
                self.adbox.remove (self.adpix)
                self.adbox.add (pix)
                self.adpix = pix
                self.adbox.show_all()

        self.curPackage["package"].set_text ("%s-%s-%s" % (header[rpm.RPMTAG_NAME],
                                                           header[rpm.RPMTAG_VERSION],
                                                           header[rpm.RPMTAG_RELEASE]))
        size = str (header[rpm.RPMTAG_SIZE] / 1024)
        if len (size) > 3:
            size = size [0:len(size) - 3] + ',' + size[len(size) - 3:]
        self.curPackage["size"].set_text (_("%s KBytes") % size)
        summary = header[rpm.RPMTAG_SUMMARY]
	if (summary == None):
            summary = "(none)"
        self.curPackage["summary"].set_text (summary)
        threads_leave ()

    def setSizes (self, total, totalSize):
        threads_enter ()
        self.numTotal = total
        self.totalSize = totalSize
        self.timeStarted = -1

        apply (self.clist.set_text, self.status["total"]["packages"] + (("%d" % total),))
        apply (self.clist.set_text, self.status["total"]["size"] +
                                    (("%d M" % (totalSize/1024)),))
        threads_leave ()

    def allocate (self, widget, *args):
        if self.frobnicatingClist: return
        
        self.frobnicatingClist = 1
        width = widget.get_allocation ()[2] - 50
        for x in range (4):
            widget.set_column_width (x, width / 4)

            
    def getScreen (self):
        import glob

	files = []
	if (not os.environ.has_key('LANG') or 
	    not os.environ['LANG'] or
	    os.environ['LANG'] == 'en_US'):

	    pixmaps1 = glob.glob("/usr/share/anaconda/pixmaps/progress_*")
	    pixmaps2 = glob.glob("pixmaps/progress_*")
	    if len(pixmaps1) < len(pixmaps2):
		files = pixmaps2
	    else:
		files = pixmaps1

        pixmaps = []
        for pixmap in files:
            if string.find (pixmap, "progress_first.png") < 0:
                pixmaps.append(pixmap[string.find(pixmap, "progress_"):])
        self.pixmaps = pixmaps
        
	table = GtkTable (3, 2)
        self.curPackage = { "package" : _("Package"),
                            "size"    : _("Size"),
                            "summary" : _("Summary") }
        i = 0
        for key in ("package", "size", "summary"):
            label = GtkLabel ("%s: " % (self.curPackage[key],))
            label.set_alignment (0, 0)
            if key == "summary":
                fillopts = EXPAND|FILL
            else:
                fillopts = FILL
            table.attach (label, 0, 1, i, i+1, FILL, fillopts)
            label = GtkLabel ()
            label.set_alignment (0, 0)
            label.set_line_wrap (TRUE)
            if key == "summary":
                label.set_text ("\n\n")
#                label.set_usize(-1, 35)
                label.set_usize(-1, 1)
            self.curPackage[key] = label
            table.attach (label, 1, 2, i, i+1, FILL, fillopts)
            i = i + 1

        vbox = GtkVBox (FALSE, 10)
        vbox.pack_start (table)

	self.progress = GtkProgressBar ()
        self.totalProgress = GtkProgressBar ()
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

        clist = GtkCList (4, (_("Status"), _("Packages"), _("Size"), _("Time")))
        clist.set_column_justification (0, JUSTIFY_LEFT)
        clist.set_column_justification (1, JUSTIFY_RIGHT)
        clist.set_column_justification (2, JUSTIFY_RIGHT)
        clist.set_column_justification (3, JUSTIFY_RIGHT)
        clist.append ((_("Total"),     "0", "0 M", "0:00.00"))
        clist.append ((_("Completed"), "0", "0 M", "0:00.00"))
        clist.append ((_("Remaining"), "0", "0 M", "0:00.00"))
        self.frobnicatingClist = 0
        
	clist.connect_after ("size_allocate", self.allocate)
        for x in range (4):
            clist.column_title_passive (x)
        for x in range (3):
            clist.set_selectable (x, FALSE)
        clist['can_focus'] = FALSE
        self.clist = clist
#        align = GtkAlignment (0.5, 0.5)
#        align.add (clist)
#        vbox.pack_start (align, FALSE)
        hbox = GtkHBox (FALSE, 5)
        hbox.pack_start (clist, TRUE)
        vbox.pack_start (hbox, FALSE)
        vbox.pack_start (self.totalProgress, FALSE)

        im = self.ics.readPixmap ("progress_first.png")
        
        if im:
            frame = GtkFrame()
            frame.set_shadow_type (SHADOW_IN)
            im.render ()
            box = GtkEventBox ()
            self.adpix = im.make_pixmap ()
            style = box.get_style ().copy ()
            style.bg[STATE_NORMAL] = style.white
            box.set_style (style)
            box.add (self.adpix)
            self.adbox = box
            frame.add (box)
            vbox.pack_start (frame, FALSE);

	self.ics.getInstallInterface ().setPackageProgressWindow (self)
        ii = self.ics.getInstallInterface ()
        icw = ii.icw
        worker = DoInstall (icw, self.todo)
        worker.start ()

	vbox.set_border_width (5)
	return vbox

