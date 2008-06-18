#
# progress_text.py: text mode install/upgrade progress dialog
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
import rpm
from constants import *
from snack import *
from constants_text import *
from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

class InstallProgressWindow:
    def completePackage(self, header, timer):
        def formatTime(amt):
            hours = amt / 60 / 60
            amt = amt % (60 * 60)
            min = amt / 60
            amt = amt % 60
            secs = amt

            return "%01d:%02d:%02d" % (int(hours) ,int(min), int(secs))

       	self.numComplete = self.numComplete + 1
	self.sizeComplete = self.sizeComplete + (header[rpm.RPMTAG_SIZE] / 1024)

        #crude fix for the completed packages overflow
        if self.numComplete>self.numTotal:
            self.numTotal = self.numComplete
        if self.sizeComplete>self.sizeTotal:
            self.sizeTotal=self.sizeComplete

	self.numCompleteW.setText("%12d" % self.numComplete)
	self.sizeCompleteW.setText("%10dM" % (self.sizeComplete/1024))
	self.numRemainingW.setText("%12d" % (self.numTotal - self.numComplete))
	self.sizeRemainingW.setText("%10dM" % (self.sizeTotal/1024 - self.sizeComplete/1024))
	self.total.set(self.sizeComplete)

	elapsedTime = timer.elapsed()
        if not elapsedTime:
            elapsedTime = 1
	self.timeCompleteW.setText("%12s" % formatTime(elapsedTime))
        if self.sizeComplete != 0:
            finishTime = (float (self.sizeTotal) / (self.sizeComplete)) * elapsedTime;
        else:
            finishTime = (float (self.sizeTotal) / (self.sizeComplete+1)) * elapsedTime;
	self.timeTotalW.setText("%12s" % formatTime(finishTime))
	remainingTime = finishTime - elapsedTime;
	self.timeRemainingW.setText("%12s" % formatTime(remainingTime))

	self.g.draw()
	self.screen.refresh()

    def setPackageScale(self, amount, total):
	self.s.set(int(((amount * 1.0)/ total) * 100))
	self.g.draw()
	self.screen.refresh()

    def setPackageStatus(self, state, amount):
	if self.pkgstatus is None:
	    return
	
	if state == "downloading":
	    msgstr = _("Downloading - %s") % (amount,)
	else:
	    msgstr = state
	self.pkgstatus.setText(msgstr)
	self.g.draw()
	self.screen.refresh()

    def setPackage(self, header):
	pkgname = "%s-%s-%s-%s" % (header[rpm.RPMTAG_NAME],
	                           header[rpm.RPMTAG_VERSION],
	                           header[rpm.RPMTAG_RELEASE],
	                           header[rpm.RPMTAG_ARCH])
	if len(pkgname) > 48:
	    pkgname = "%s..." %(pkgname[:45])

	self.name.setText(pkgname)
	self.size.setText("%dk" % (header[rpm.RPMTAG_SIZE] / 1024))
	summary = header[rpm.RPMTAG_SUMMARY]
	if (summary != None):
	    self.summ.setText(summary)
	else:
            self.summ.setText("(none)")

	self.g.draw()
	self.screen.refresh()

    def processEvents(self):
	pass

    def setSizes(self, total, totalSize, totalFiles):
	screen = self.screen

	if self.showdownload:
	    totlen = 7
	else:
	    totlen = 6
	    
        toplevel = GridForm(self.screen, _("Package Installation"), 1, totlen)
        
        name = _(" Name   : ")
        size = _(" Size   : ")
        sum =  _(" Summary: ")

	currow = 0
        
        width = 47 + max (len (name), len (size), len (sum))
	self.name = Label(" " * 48)
	self.size = Label(" ")
	detail = Grid(2, 2)
	detail.setField(Label(name), 0, 0, anchorLeft = 1)
	detail.setField(Label(size), 0, 1, anchorLeft = 1)
	detail.setField(self.name, 1, 0, anchorLeft = 1)
	detail.setField(self.size, 1, 1, anchorLeft = 1)
	toplevel.add(detail, 0, currow)
	currow += 1

	summary = Grid(2, 1)
	summlabel = Label(sum)
	self.summ = Textbox(48, 2, "", wrap = 1)
	summary.setField(summlabel, 0, 0)
	summary.setField(self.summ, 1, 0)
	toplevel.add(summary, 0, currow)
	currow += 1

	if self.showdownload:
	    toplevel.add(Label(""), 0, currow)
	    currow += 1
	    
	    pkgstatgrid = Grid(2, 1)
	    pkgstatlabel = Label(_("Status: "))
	    self.pkgstatus = Label(" " * 48)
	    pkgstatgrid.setField(pkgstatlabel, 0, 0)
	    pkgstatgrid.setField(self.pkgstatus, 1, 0)
	    toplevel.add(pkgstatgrid, 0, currow)
	    currow += 1
	else:
	    self.pkgstatus = None

	self.s = Scale (width, 100)
	toplevel.add (self.s, 0, currow, (0, 1, 0, 1))
	currow += 1

	overall = Grid(4, 4)
	# don't ask me why, but if this spacer isn"t here then the 
        # grid code gets unhappy
	overall.setField (Label (" " * 19), 0, 0, anchorLeft = 1)
	overall.setField (Label (_("    Packages")), 1, 0, anchorLeft = 1)
	overall.setField (Label (_("      Bytes")), 2, 0, anchorLeft = 1)
	overall.setField (Label (_("        Time")), 3, 0, anchorLeft = 1)

	overall.setField (Label (_("Total    :")), 0, 1, anchorLeft = 1)
	overall.setField (Label ("%12d" % total), 1, 1, anchorLeft = 1)
	overall.setField (Label ("%10dM" % (totalSize/1024)),
                          2, 1, anchorLeft = 1)
	self.timeTotalW = Label("")
	overall.setField(self.timeTotalW, 3, 1, anchorLeft = 1)

	overall.setField (Label (_("Completed:   ")), 0, 2, anchorLeft = 1)
	self.numComplete = 0
	self.numCompleteW = Label("%12d" % self.numComplete)
	overall.setField(self.numCompleteW, 1, 2, anchorLeft = 1)
	self.sizeComplete = 0
        self.sizeCompleteW = Label("%10dM" % (self.sizeComplete))
	overall.setField(self.sizeCompleteW, 2, 2, anchorLeft = 1)
	self.timeCompleteW = Label("")
	overall.setField(self.timeCompleteW, 3, 2, anchorLeft = 1)

	overall.setField (Label (_("Remaining:  ")), 0, 3, anchorLeft = 1)
	self.numRemainingW = Label("%12d" % total)
        self.sizeRemainingW = Label("%10dM" % (totalSize/1024))
	overall.setField(self.numRemainingW, 1, 3, anchorLeft = 1)
	overall.setField(self.sizeRemainingW, 2, 3, anchorLeft = 1)
	self.timeRemainingW = Label("")
	overall.setField(self.timeRemainingW, 3, 3, anchorLeft = 1)

	toplevel.add(overall, 0, currow)
	currow += 1

	self.numTotal = total
	self.sizeTotal = totalSize
	self.total = Scale (width, totalSize)
	toplevel.add(self.total, 0, currow, (0, 1, 0, 0))
	currow += 1

	self.timeStarted = -1
	
	toplevel.draw()
	self.g = toplevel
	screen.refresh()
	self.drawn = 1

    def __init__(self, screen, showdownload=0):
	self.screen = screen
	self.showdownload = showdownload
	self.drawn = 0

    def __del__ (self):
	if self.drawn: self.screen.popWindow ()

class setupForInstall:

    def __call__(self, screen, anaconda):
	if anaconda.dir == DISPATCH_BACK:
	    anaconda.id.setInstallProgressClass(None)
	    return INSTALL_BACK
	else:
	    flag = 0
            if anaconda.methodstr.startswith("http://") or anaconda.methodstr.startswith("ftp://"):
                flag = 1

	    log.info("anaconda.methodstr = %s %s", anaconda.methodstr, flag)
	    anaconda.id.setInstallProgressClass(InstallProgressWindow(screen, showdownload=flag))

	return INSTALL_OK
