#
# progress_gui.py: install/upgrade progress window setup.
#
# Copyright 2000-2002 Red Hat, Inc.
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
import gobject
import gtk
from iw_gui import *
from rhpl.translate import _, N_
from packages import doInstall
from constants import *
from rhpl.log import log

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
	# only update widget if we've changed by 5%, otherwise
	# we update widget hundreds of times a seconds because RPM
	# calls us back ALOT
	curval = self.progress.get_fraction()
	newval = float (amount) / total
	if newval < 0.998:
	    if (newval - curval) < 0.05 and newval > curval:
		return
                 
	self.progress.set_fraction (newval)
	self.processEvents()

    def setStatusRow(self, iter, vals):
	i = 0;
	for val in vals:
	    self.progstore.set_value(iter, i, val)
	    i = i + 1

    def completePackage(self, header, timer):
        def formatTime(amt):
            hours = amt / 60 / 60
            amt = amt % (60 * 60)
            min = amt / 60
            amt = amt % 60
            secs = amt

            return "%01d:%02d:%02d" % (int(hours) ,int(min), int(secs))

        self.numComplete = self.numComplete + 1

	self.sizeComplete = self.sizeComplete + (header[rpm.RPMTAG_SIZE]/1024)

        # check to see if we've started yet
	elapsedTime = timer.elapsed()
	if not elapsedTime:
	    elapsedTime = 1
	
        if self.sizeComplete != 0:
            finishTime = (float (self.totalSize) / self.sizeComplete) * elapsedTime
        else:
            finishTime = (float (self.totalSize) / (self.sizeComplete+1)) * elapsedTime

	remainingTime = finishTime - elapsedTime

	self.setStatusRow(self.completed_iter,
			  [_("Completed"),
			   "%d" % (self.numComplete,),
			   "%d M" % (self.sizeComplete/1024,),
			   "%s" % (formatTime(elapsedTime),)])
	
	self.setStatusRow(self.total_iter,
			  [_("Total"),
			   "%d" % (self.numTotal,),
			   "%d M" % (self.totalSize/1024,),
			   "%s" % (formatTime(finishTime),)])
	
	self.setStatusRow(self.remaining_iter,
			  [_("Remaining"),
			   "%d" % ((self.numTotal - self.numComplete),),
			   "%d M" % ((self.totalSize/1024 - self.sizeComplete/1024),),
			   "%s" % (formatTime(remainingTime),)])
	
        self.totalProgress.set_fraction(float (self.sizeComplete) / self.totalSize)
        
        return

    def setPackage(self, header):
        if len(self.pixmaps):
            # set to switch every N seconds
            if self.pixtimer is None or self.pixtimer.elapsed() > 30:
                if self.pixtimer is None:
                    self.pixtimer = timer.Timer()
                
                num = self.pixcurnum
                if num >= len(self.pixmaps):
                    num = 0
                pix = self.ics.readPixmapDithered (self.pixmaps[num], 425, 225)
                if pix:
		    if self.adpix:
			self.adbox.remove (self.adpix)
                    pix.set_alignment (0.5, 0.5)
                    self.adbox.add (pix)
                    self.adpix = pix
                else:
                    log("couldn't get a pix")
                self.adbox.show_all()
                self.pixcurnum = num + 1
                self.pixtimer.reset()
                
        self.curPackage["package"].set_text ("%s-%s-%s.%s" % (header[rpm.RPMTAG_NAME],
                                                              header[rpm.RPMTAG_VERSION],
                                                              header[rpm.RPMTAG_RELEASE],
                                                              header[rpm.RPMTAG_ARCH]))
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

    def renderCallback(self):
	self.intf.icw.nextClicked()

    def allocate (self, widget, *args):
        if self.sizingprogview: return
        
        self.sizingprogview = 1
        width = widget.get_allocation ()[2] - 50
#        for x in range (4):
#            widget.set_column_width (x, width / 4)

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
                longlang = string.split(os.environ['LANG'], '.')[0]
            except:
                shortlang = ''
                longlang = os.environ['LANG']
        else:
            shortlang = ''
            longlang = ''

        pixmaps1 = glob.glob("/usr/share/anaconda/pixmaps/rnotes/%s/*.png" % (shortlang,))

	if len(pixmaps1) <= 0:
	    pixmaps1 = glob.glob("/usr/share/anaconda/pixmaps/rnotes/%s/*.png" % (longlang,))

	if len(pixmaps1) <= 0:
	    # for beta try top level w/o lang
	    pixmaps1 = glob.glob("/usr/share/anaconda/pixmaps/rnotes/*.png")

        if len(pixmaps1) > 0:
            files = pixmaps1
        else:
            files = ["progress_first.png"]

        #--Need to merge with if statement above...don't show ads in lowres
        if intf.runres != '800x600':
            files = ["progress_first.png"]

        # sort the list of filenames
        files.sort()

        pixmaps = []
        for pixmap in files:
            if string.find (pixmap, "progress_first.png") < 0:
                pixmaps.append(pixmap[string.find(pixmap, "rnotes/"):])

        self.pixmaps = pixmaps
        self.pixtimer = None
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
                label.set_size_request(450, 35)
#                label.set_size_request(-1, 1)
            self.curPackage[key] = label
            table.attach (label, 1, 2, i, i+1, gtk.FILL, fillopts)
            i = i + 1


        vbox = gtk.VBox (gtk.FALSE, 10)
        vbox.pack_start (table, gtk.FALSE, gtk.FALSE)

	self.progress = gtk.ProgressBar ()
        self.totalProgress = gtk.ProgressBar ()

        progressTable = gtk.Table (2, 2, gtk.FALSE)
        label = gtk.Label (_("Package Progress: "))
        label.set_alignment (1.0, 0.5)
        progressTable.attach (label, 0, 1, 0, 1, gtk.SHRINK)
        progressTable.attach (self.progress, 1, 2, 0, 1, ypadding=2)

        label = gtk.Label (_("Total Progress:   "))
        label.set_alignment (1.0, 0.5)
        progressTable.attach (label, 0, 1, 1, 2, gtk.SHRINK)
        progressTable.attach (self.totalProgress, 1, 2, 1, 2, ypadding=2)

	self.progstore = gtk.ListStore(gobject.TYPE_STRING,
				       gobject.TYPE_STRING,
				       gobject.TYPE_STRING,
				       gobject.TYPE_STRING)

	self.total_iter = self.progstore.append()
	self.completed_iter = self.progstore.append()
	self.remaining_iter = self.progstore.append()

	self.setStatusRow(self.total_iter, [_("Total"),"0", "0 M", "0:00:00"])
	self.setStatusRow(self.completed_iter, [_("Completed"),"0", "0 M", "0:00:00"])
	self.setStatusRow(self.remaining_iter, [_("Remaining"),"0", "0 M", "0:00:00"])
	 
	self.progview = gtk.TreeView(self.progstore)


	if gtk.gdk.screen_width() > 640:
	    cwidth = 128
	else:
	    cwidth = 96
	
	i = 0
	for title in [_("Status"), _("Packages"), _("Size"), _("Time")]:
	    renderer = gtk.CellRendererText()
	    col = gtk.TreeViewColumn(title, renderer, text=i)
	    col.set_min_width(cwidth)
	    self.progview.append_column(col)
	    if i > 0:
		val = 1.0
	    else:
		val = 0.0
	    renderer.set_property("xalign", val)
	    col.set_alignment(val)
	    i = i + 1

        hbox = gtk.HBox (gtk.FALSE, 5)
        
        vbox.pack_start (progressTable, gtk.FALSE)
	sw = gtk.ScrolledWindow()
	sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
	sw.set_shadow_type(gtk.SHADOW_IN)
	sw.add(self.progview)
	self.sizingprogview = 0
	sw.connect_after("size-allocate", self.allocate)
        hbox.pack_start (sw, gtk.TRUE)
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
