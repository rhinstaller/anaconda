#
# progress_gui.py: install/upgrade progress window setup.
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string
import rpm
import os
import gui
import sys
import timer
import gtk
from iw_gui import *
from translate import _, N_
from packages import doInstall
from constants import *

class InstallProgressWindow (InstallWindow):

    windowTitle = N_("Installing Packages")
    htmlTag = "installing"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setPrevEnabled (gtk.FALSE)
        ics.setNextEnabled (gtk.FALSE)
        
        ics.setHelpButtonEnabled (gtk.FALSE)

	self.numComplete = 0
	self.sizeComplete = 0

    def processEvents(self):
	gui.processEvents()
        
    def setPackageScale (self, amount, total):
	self.progress.update (float (amount) / total)
#        self.totalProgress.update (float (self.sizeComplete + amount) / self.totalSize)

    def completePackage(self, header, timer):
        def formatTime(amt):
            hours = amt / 60 / 60
            amt = amt % (60 * 60)
            min = amt / 60
            amt = amt % 60
            secs = amt

            return "%01d:%02d:%02d" % (int(hours) ,int(min), int(secs))

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
	elapsedTime = timer.elapsed()
	if not elapsedTime:
	    elapsedTime = 1

        apply (self.clist.set_text, self.status["completed"]["time"] + ("%s" % formatTime(elapsedTime),))

        if self.sizeComplete != 0:
            finishTime = (float (self.totalSize) / self.sizeComplete) * elapsedTime
        else:
            finishTime = (float (self.totalSize) / (self.sizeComplete+1)) * elapsedTime


        apply (self.clist.set_text, self.status["total"]["time"] + ("%s" % formatTime(finishTime),))

	remainingTime = finishTime - elapsedTime
        apply (self.clist.set_text, self.status["remaining"]["time"] + ("%s" % formatTime(remainingTime),))

        self.totalProgress.update (float (self.sizeComplete) / self.totalSize)
        
        return

    def setPackage(self, header):
        if len(self.pixmaps):
            # set to switch every N seconds
            if self.pixtimer.elapsed() > 30:
                num = self.pixcurnum + 1
                if num >= len(self.pixmaps):
                    num = min(1, len(self.pixmaps))
                pix = self.ics.readPixmap (self.pixmaps[num])
                if pix:
                    self.adbox.remove (self.adpix)
                    pix.set_alignment (0.5, 0.5)
                    self.adbox.add (pix)
                    self.adpix = pix
                self.adbox.show_all()
                self.pixcurnum = num
                self.pixtimer.reset()
                
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

    def setSizes (self, total, totalSize):
        self.numTotal = total
        self.totalSize = totalSize
        self.timeStarted = -1

        apply (self.clist.set_text, self.status["total"]["packages"] + (("%d" % total),))
        apply (self.clist.set_text, self.status["total"]["size"] +
                                    (("%d M" % (totalSize/1024)),))

    def renderCallback(self):
	self.intf.icw.nextClicked()

    def allocate (self, widget, *args):
        if self.frobnicatingClist: return
        
        self.frobnicatingClist = 1
        width = widget.get_allocation ()[2] - 50
        for x in range (4):
            widget.set_column_width (x, width / 4)

    # InstallProgressWindow tag="installing"
    def getScreen (self, dir, intf, id):
        import glob

	self.intf = intf

	if dir == DISPATCH_BACK:
	    intf.icw.prevClicked()

	    return

	files = []

	# XXX this ought to search the lang path like everything else
        if (os.environ.has_key('LANG')):
            try:
                shortlang = string.split(os.environ['LANG'], '_')[0]
            except:
                shortlang = ''
        else:
            shortlang = ''
                
        pixmaps1 = glob.glob("/usr/share/anaconda/pixmaps/rnotes/%s/*.png" % shortlang)
        pixmaps2 = glob.glob("pixmaps/rnotes/%s/*.png" % shortlang)

        if len(pixmaps1) > 0 or len(pixmaps2) > 0:
            if len(pixmaps1) < len(pixmaps2):
                files = pixmaps2
            else:
                files = pixmaps1
        else:
            files = ["progress_first.png"]

        #--Need to merge with if statement above...don't show ads in lowres
        if intf.runres != '800x600':
            files = ["progress_first.png"]

        pixmaps = []
        for pixmap in files:
            if string.find (pixmap, "progress_first.png") < 0:
                pixmaps.append(pixmap[string.find(pixmap, "rnotes/"):])

        self.pixmaps = pixmaps
        self.pixtimer = timer.Timer()
        self.pixcurnum = 0
        
	table = gtk.Table (3, 2)
        self.curPackage = { "package" : _("Package"),
                            "size"    : _("Size"),
                            "summary" : _("Summary") }
        i = 0
        for key in ("package", "size", "summary"):
            label = gtk.Label ("%s: " % (self.curPackage[key],))
            label.set_alignment (0, 0)
            if key == "summary":
                fillopts = gtk.EXPAND|gtk.FILL
            else:
                fillopts = gtk.FILL

            table.attach (label, 0, 1, i, i+1, gtk.FILL, fillopts)
            label = gtk.Label ("")
            label.set_alignment (0, 0)
            label.set_line_wrap (gtk.TRUE)
            if key == "summary":
                label.set_text ("\n\n")
                label.set_usize(450, 35)
#                label.set_usize(-1, 1)
            self.curPackage[key] = label
            table.attach (label, 1, 2, i, i+1, gtk.FILL, fillopts)
            i = i + 1


        vbox = gtk.VBox (gtk.FALSE, 10)
        vbox.pack_start (table, gtk.FALSE, gtk.FALSE)

	self.progress = gtk.ProgressBar ()
        self.totalProgress = gtk.ProgressBar ()

        progressTable = gtk.Table (2, 2, gtk.FALSE)
        label = gtk.Label (_("Package Progress: "))
        label.set_alignment (0, 0)
        progressTable.attach (label, 0, 1, 0, 1, gtk.SHRINK)
        progressTable.attach (self.progress, 1, 2, 0, 1)

        label = gtk.Label (_("Total Progress:   "))
        label.set_alignment (0, 0)
        progressTable.attach (label, 0, 1, 1, 2, gtk.SHRINK)
        progressTable.attach (self.totalProgress, 1, 2, 1, 2)

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

        clist = gtk.CList (4, (_("Status"), _("Packages"), _("Size"), _("Time")))
        clist.column_titles_passive ()
        clist.set_column_resizeable (0, gtk.FALSE)
        clist.set_column_resizeable (1, gtk.FALSE)
        clist.set_column_resizeable (2, gtk.FALSE)
        clist.set_column_resizeable (3, gtk.FALSE)
        clist.set_column_justification (0, gtk.JUSTIFY_LEFT)
        clist.set_column_justification (1, gtk.JUSTIFY_RIGHT)
        clist.set_column_justification (2, gtk.JUSTIFY_RIGHT)
        clist.set_column_justification (3, gtk.JUSTIFY_RIGHT)
        clist.append ((_("Total"),     "0", "0 M", "0:00:00"))
        clist.append ((_("Completed"), "0", "0 M", "0:00:00"))
        clist.append ((_("Remaining"), "0", "0 M", "0:00:00"))
        self.frobnicatingClist = 0
        
	clist.connect_after ("size_allocate", self.allocate)
        for x in range (4):
            clist.column_title_passive (x)
        for x in range (3):
            clist.set_selectable (x, gtk.FALSE)
        clist.set_property('can_focus', gtk.FALSE)
        self.clist = clist
#        align = gtk.Alignment (0.5, 0.5)
#        align.add (clist)
#        vbox.pack_start (align, gtk.FALSE)
        hbox = gtk.HBox (gtk.FALSE, 5)
        
        vbox.pack_start (progressTable, gtk.FALSE)
        hbox.pack_start (clist, gtk.TRUE)
        vbox.pack_start (hbox, gtk.FALSE)
        
        pix = self.ics.readPixmap ("progress_first.png")
        if pix:
            frame = gtk.Frame()
            frame.set_shadow_type(gtk.SHADOW_IN)
            box = gtk.EventBox()
            self.adpix = pix
            box.modify_bg(gtk.STATE_NORMAL, box.get_style().white)
#            self.adpix.set_alignment (0, 0)
            box.add(self.adpix)
            self.adbox = box
            frame.add (box)
            vbox.pack_start(frame);

	intf.setPackageProgressWindow (self)
	id.setInstallProgressClass(self)

	vbox.set_border_width (5)

	return vbox
