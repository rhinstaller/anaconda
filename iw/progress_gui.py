#
# progress_gui.py: install/upgrade progress window setup.
#
# Copyright 2000-2003 Red Hat, Inc.
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
import time
import timer
import gobject
import pango
import gtk
import locale
import math

from flags import flags
from iw_gui import *
from rhpl.translate import _, N_
from constants import *
from gui import processEvents, takeScreenShot

import logging
log = logging.getLogger("anaconda")

# FIXME: from redhat-config-packages.  perhaps move to common location
def size_string (size):
    def number_format(s):
        return locale.format("%s", s, 1)

    if size > 1024 * 1024:
        size = size / (1024*1024)
        return _("%s MB") %(number_format(size),)
    elif size > 1024:
        size = size / 1024
        return _("%s KB") %(number_format(size),)        
    else:
        if size == 1:
            return _("%s Byte") %(number_format(size),)                    
        else:
            return _("%s Bytes") %(number_format(size),)

class InstallProgressWindow (InstallWindow):

    windowTitle = N_("Installing Packages")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setPrevEnabled (False)
        ics.setNextEnabled (False)
        
	self.numComplete = 0
	self.sizeComplete = 0
	self.filesComplete = 0

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
        
	self.filesComplete = self.filesComplete + (len(header[rpm.RPMTAG_BASENAMES]))

        #crude fix for the completed packages overflow
        if self.numComplete>self.numTotal:
            self.numTotal = self.numComplete
        if self.sizeComplete>self.totalSize:
            self.totalSize = self.sizeComplete
        if self.filesComplete>self.totalFiles:
            self.totalFiles = self.filesComplete

        # check to see if we've started yet
	elapsedTime = timer.elapsed()
	if not elapsedTime:
	    elapsedTime = 1
	
        if self.sizeComplete != 0:
            finishTime1 = (float (self.totalSize) / self.sizeComplete) * elapsedTime
	else:
            finishTime1 = (float (self.totalSize)) * elapsedTime
		
	if  self.numComplete != 0:
            finishTime2 = (float (self.numTotal) / self.numComplete) * elapsedTime
	else:
	    finishTime2 = (float (self.numTotal)) * elapsedTime


	if self.filesComplete != 0:	    
	    finishTime3 = (float (self.totalFiles) / self.filesComplete) * elapsedTime
	else:
	    finishTime3 = (float (self.totalFiles)) * elapsedTime

	finishTime = finishTime1
# another alternate suggestion
#	finishTime = math.sqrt(finishTime1 * finishTime2)

	remainingTime = finishTime - elapsedTime

	fractionComplete = float(self.sizeComplete)/float(self.totalSize)

	timeest = 1.4*remainingTime/60.0

	# average last 10 estimates
	self.estimateHistory.append(timeest)
	if len(self.estimateHistory) > 10:
	    del self.estimateHistory[0]
	tavg = 0.0
	for testimate in self.estimateHistory:
	    tavg += testimate

	timeest = tavg/float(len(self.estimateHistory))

        # here is strategy for time estimate
	#
	# 1) First 100 or so packages give us misleading estimates as things
        #    are not settled down. So no estimate until past 100 packages
	#
	# 2) Time estimate based on % of bytes installed is on about 30% too
	#    low overall. So we just bump our estimate to compensate
	#
	# 3) Lets only report time on 5 minute boundaries, and round up.
	#

#	self.timeLog.write("%s %s %s %s %s %s %s %s %s %s %s %s\n" % (elapsedTime/60.0, (finishTime1-elapsedTime)/60.0, (finishTime2-elapsedTime)/60.0, (finishTime3-elapsedTime)/60.0, (finishTime-elapsedTime)/60.0, timeest, self.sizeComplete, self.totalSize, self.numComplete, self.numTotal, self.filesComplete, self.totalFiles, ))
#	self.timeLog.flush()

#	if (fractionComplete > 0.10):
        if self.numComplete > 100:
	    if self.initialTimeEstimate is None:
		self.initialTimeEstimate = timeest
		log.info("Initial install time estimate = %s", timeest)

#	    log.info("elapsed time, time est, remaining time =  %s %s", int(elapsedTime/60), timeest)		

            if timeest < 10:
	        timefactor = 2
	    else:
		timefactor = 5
	    str = _("Remaining time: %s minutes") % ((int(timeest/timefactor)+1)*timefactor,)
	    self.remainingTimeLabel.set_text(str)

	if (fractionComplete >= 1):
	    log.info("Actual install time = %s", elapsedTime/60.0)
	    self.remainingTimeLabel.set_text("")
	    
        self.totalProgress.set_fraction(fractionComplete)
	
        return

    def setPackageStatus(self, state, amount):
	if self.pkgstatus is None:
	    return
	
	if state == "downloading":
	    msgstr = _("Downloading %s") % (amount,)
	else:
	    msgstr = state
	self.pkgstatus.set_text(msgstr)
	self.processEvents()

    def setPackage(self, header):
        if len(self.pixmaps):
            # set to switch every N seconds
            if self.pixtimer is None or self.pixtimer.elapsed() > 30:
                if self.pixtimer is None:
                    self.pixtimer = timer.Timer()

                num = self.pixcurnum
                if num >= len(self.pixmaps):
                    num = 0
		    self.wrappedpixlist = 1
		    
                pix = gui.readImageFromFile (self.pixmaps[num], 500, 325)
                if pix:
		    if self.adpix:
			self.adbox.remove (self.adpix)
                    pix.set_alignment (0.5, 0.5)
                    self.adbox.add (pix)
                    self.adpix = pix
                else:
                    log.warning("couldn't get a pix")
                self.adbox.show_all()
                self.pixcurnum = num + 1

		# take screenshot if desired
		if flags.autoscreenshot and not self.wrappedpixlist:
		    # let things settle down graphically??
		    processEvents()
		    time.sleep(5)
		    takeScreenShot()
		    
                self.pixtimer.reset()
                
        size = size_string(header[rpm.RPMTAG_SIZE])
        pkgstr = _("Installing %s-%s-%s.%s (%s)") %(header[rpm.RPMTAG_NAME],
                                                    header[rpm.RPMTAG_VERSION],
                                                    header[rpm.RPMTAG_RELEASE],
                                                    header[rpm.RPMTAG_ARCH],
                                                    size)
        self.curPackage["package"].set_text (pkgstr)
        self.curPackage["package"].set_ellipsize (pango.ELLIPSIZE_END)

        summary = header[rpm.RPMTAG_SUMMARY]
	if (summary == None):
            summary = "(none)"
        self.curPackage["summary"].set_text (summary)
        self.curPackage["summary"].set_ellipsize (pango.ELLIPSIZE_END)

    def setSizes (self, total, totalSize, totalFiles):
        self.numTotal = total
	self.totalFiles = totalFiles
        self.totalSize = totalSize
        self.timeStarted = -1

    def renderCallback(self):
	self.intf.icw.nextClicked()

    def allocate (self, widget, *args):
        if self.sizingprogview: return
        
        self.sizingprogview = 1
        width = widget.get_allocation ()[2] - 50

    # InstallProgressWindow tag="installing"
    def getScreen (self, anaconda):
        import glob

	self.intf = anaconda.intf

	if anaconda.dir == DISPATCH_BACK:
	    self.intf.icw.prevClicked()

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

        paths = ("/tmp/product/pixmaps/rnotes/%s/*.png" %(shortlang,),
                 "/tmp/product/pixmaps/rnotes/%s/*.png" %(longlang,),
                 "/tmp/product/pixmaps/rnotes/*.png",
                 "/usr/share/anaconda/pixmaps/rnotes/%s/*.png" %(shortlang,),
                 "/usr/share/anaconda/pixmaps/rnotes/%s/*.png" %(longlang,),
                 "/usr/share/anaconda/pixmaps/rnotes/*.png")
        for path in paths:
            pixmaps = glob.glob(path)
            if len(pixmaps) > 0:
                break

        if len(pixmaps) > 0:
            files = pixmaps
        else:
            files = ["progress_first.png"]

        #--Need to merge with if statement above...don't show ads in lowres
        if self.intf.runres != '800x600':
            files = ["progress_first-lowres.png"]

        # sort the list of filenames
        files.sort()

        pixmaps = []
        for pixmap in files:
            if string.find (pixmap, "progress_first.png") < 0:
                pixmaps.append(pixmap[string.find(pixmap, "rnotes/"):])

        self.pixmaps = pixmaps
        self.pixtimer = None
        self.pixcurnum = 0
	self.wrappedpixlist = 0
	self.lastTimeEstimate = None
	self.initialTimeEstimate = None
	self.estimateHistory = []

#	self.timeLog = open("/tmp/timelog", "w")

	# Create vbox to contain components of UI
        vbox = gtk.VBox (False, 10)

        # Create rnote area
        pix = gui.readImageFromFile ("progress_first.png")
        if pix:
            frame = gtk.Frame()
            frame.set_shadow_type(gtk.SHADOW_NONE)
            box = gtk.EventBox()
            self.adpix = pix
            box.add(self.adpix)
            self.adbox = box
            frame.add (box)
            vbox.pack_start(frame);

	# Create progress bars for package and total progress
	self.progress = gtk.ProgressBar ()
        self.totalProgress = gtk.ProgressBar ()

	progressTable = gtk.Table (2, 2, False)
	progressTable.attach (self.totalProgress, 1, 2, 0, 1, xpadding=0, ypadding=2)
        vbox.pack_start (progressTable, False)

	# create a table to display time remaining and package info
	infoTable = gtk.Table (3, 2, False)

	# remaining time
	self.remainingTimeLabel = gtk.Label ("")
	self.remainingTimeLabel.set_alignment (1.0, 0.5)
	infoTable.attach (self.remainingTimeLabel, 1, 2, 0, 1)

	# current package info
        self.curPackage = { "package" : _("Package"),
                            "summary" : _("Summary") }
        i = 0
        for key in ("package", "summary"):
            label = gtk.Label ("")
            label.set_alignment (0, 0)
            label.set_line_wrap (True)
            if key == "summary":
                label.set_text ("\n\n")
                label.set_size_request(525, 35)
                fillopts = gtk.EXPAND|gtk.FILL
            else:
                fillopts = gtk.FILL
                
            self.curPackage[key] = label
            infoTable.attach (label, 0, 1, i, i+1, gtk.FILL, fillopts)
            i = i + 1

	vbox.pack_start (infoTable, False)

	# some sort of table for status
	statusflag = 0
        if anaconda.methodstr.startswith("http://") or anaconda.methodstr.startswith("ftp://"):
	    statusflag = 1

	if statusflag:
	    statusTable = gtk.Table (2, 2, False)
	    self.pkgstatus = gtk.Label("")
	    statusTable.attach (gtk.Label(_("Status: ")), 0, 1, 0, 1, gtk.SHRINK)
	    statusTable.attach (self.pkgstatus, 1, 2, 0, 1, gtk.FILL, gtk.FILL, ypadding=2)
	    vbox.pack_start (statusTable, False, False)
	else:
	    self.pkgstatus = None
	
	# All done with creating components of UI
	self.intf.setPackageProgressWindow (self)
	anaconda.id.setInstallProgressClass(self)

	vbox.set_border_width (5)

	return vbox
