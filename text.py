from snack import *
import _balkan
import sys
import isys
import os
import rpm
import time
import lang
_ = lang.gettext

class WelcomeWindow:
    def run(self, screen):
        ButtonChoiceWindow(screen, _("Red Hat Linux"), 
            _("Welcome to Red Hat Linux!\n\n"
              "This installation process is outlined in detail in the "
              "Official Red Hat Linux Installation Guide available from "
              "Red Hat Software. If you have access to this manual, you "
              "should read the installation section before continuing.\n\n"
              "If you have purchased Official Red Hat Linux, be sure to "
              "register your purchase through our web site, "
              "http://www.redhat.com/."), buttons = ["Ok"])
        return 0


class InstallProgressWindow:

    def completePackage(self, header):
        def formatTime(amt):
            hours = amt / 60 / 60
            amt = amt % (60 * 60)
            min = amt / 60
            amt = amt % 60
            secs = amt

            return "%01d:%02d.%02d" % (int(hours) ,int(min), int(secs))

       	self.numComplete = self.numComplete + 1
	self.sizeComplete = self.sizeComplete + header[rpm.RPMTAG_SIZE]
	self.numCompleteW.setText("%12d" % self.numComplete)
	self.sizeCompleteW.setText("%10d M" % (self.sizeComplete / (1024 * 1024)))
	self.numRemainingW.setText("%12d" % (self.numTotal - self.numComplete))
	self.sizeRemainingW.setText("%10d M" % ((self.sizeTotal - self.sizeComplete) / (1024 * 1024)))
	self.total.set(self.numComplete)

	elapsedTime = time.time() - self.timeStarted 
	self.timeCompleteW.setText("%12s" % formatTime(elapsedTime))
	finishTime = (float (self.sizeTotal) / self.sizeComplete) * elapsedTime;
	self.timeTotalW.setText("%12s" % formatTime(finishTime))
	remainingTime = finishTime - elapsedTime;
	self.timeRemainingW.setText("%12s" % formatTime(remainingTime))

	self.g.draw()
	self.screen.refresh()

    def setPackageScale(self, amount, total):
	self.s.set(int(((amount * 1.0)/ total) * 100))
	self.g.draw()
	self.screen.refresh()

    def setPackage(self, header):
	self.name.setText("%s-%s-%s" % (header[rpm.RPMTAG_NAME],
                                        header[rpm.RPMTAG_VERSION],
                                        header[rpm.RPMTAG_RELEASE]))
	self.size.setText("%d k" % (header[rpm.RPMTAG_SIZE] / 1024))
	summary = header[rpm.RPMTAG_SUMMARY]
	if (summary != None):
	    self.summ.setText(summary)
	else:
            self.summ.setText("(none)")

	self.g.draw()
	self.screen.refresh()

    def __del__(self):
	self.screen.popWindow()
	self.screen.refresh()

    def __init__(self, screen, total, totalSize):
	self.screen = screen
        toplevel = GridForm(self.screen, _("Package Installation"), 1, 5)

	self.name = Label("                                        ")
	self.size = Label(" ")
	detail = Grid(2, 2)
	detail.setField(Label(_("Name   : ")), 0, 0, anchorLeft = 1)
	detail.setField(Label(_("Size   : ")), 0, 1, anchorLeft = 1)
	detail.setField(self.name, 1, 0, anchorLeft = 1)
	detail.setField(self.size, 1, 1, anchorLeft = 1)
	toplevel.add(detail, 0, 0)

	summary = Grid(2, 1)
	summlabel = Label(_("Summary: "))
	self.summ = Textbox(40, 2, "", wrap = 1)
	summary.setField(summlabel, 0, 0)
	summary.setField(self.summ, 1, 0)
	toplevel.add(summary, 0, 1)

	self.s = Scale(50, 100)
	toplevel.add(self.s, 0, 2, (0, 1, 0, 1))

	overall = Grid(4, 4)
	# don"t ask me why, but if this spacer isn"t here then the 
        # grid code gets unhappy
	overall.setField (Label (" "), 0, 0, anchorLeft = 1)
	overall.setField (Label (_("    Packages")), 1, 0, anchorLeft = 1)
	overall.setField (Label (_("       Bytes")), 2, 0, anchorLeft = 1)
	overall.setField (Label (_("        Time")), 3, 0, anchorLeft = 1)

	overall.setField (Label (_("Total    :")), 0, 1, anchorLeft = 1)
	overall.setField (Label ("%12d" % total), 1, 1, anchorLeft = 1)
	overall.setField (Label ("%10d M" % (totalSize / (1024 * 1024))),
                               2, 1, anchorLeft = 1)
	self.timeTotalW = Label("")
	overall.setField(self.timeTotalW, 3, 1, anchorLeft = 1)

	overall.setField (Label (_("Completed:   ")), 0, 2, anchorLeft = 1)
	self.numComplete = 0
	self.numCompleteW = Label("%12d" % self.numComplete)
	overall.setField(self.numCompleteW, 1, 2, anchorLeft = 1)
	self.sizeComplete = 0
        self.sizeCompleteW = Label("%10d M" % (self.sizeComplete / (1024 * 1024)))
	overall.setField(self.sizeCompleteW, 2, 2, anchorLeft = 1)
	self.timeCompleteW = Label("")
	overall.setField(self.timeCompleteW, 3, 2, anchorLeft = 1)

	overall.setField (Label (_("Remaining:  ")), 0, 3, anchorLeft = 1)
	self.numRemainingW = Label("%12d" % total)
        self.sizeRemainingW = Label("%10d M" % (totalSize / (1024 * 1024)))
	overall.setField(self.numRemainingW, 1, 3, anchorLeft = 1)
	overall.setField(self.sizeRemainingW, 2, 3, anchorLeft = 1)
	self.timeRemainingW = Label("")
	overall.setField(self.timeRemainingW, 3, 3, anchorLeft = 1)

	toplevel.add(overall, 0, 3)

	self.numTotal = total
	self.sizeTotal = totalSize
	self.total = Scale(50, total)
	toplevel.add(self.total, 0, 4, (0, 1, 0, 0))

	self.timeStarted = time.time()	
	
	toplevel.draw()
	self.g = toplevel
	screen.refresh()

class WaitWindow:

    def pop(self):
	self.screen.popWindow()
	self.screen.refresh()

    def __init__(self, screen, title, text):
	self.screen = screen
	width = 40
	if (len(text) < width): width = len(text)

	t = TextboxReflowed(width, text)

	g = GridForm(self.screen, title, 1, 1)
	g.add(t, 0, 0)
	g.draw()
	self.screen.refresh()

class PartitionWindow:
    def run(self, screen, todo):
	if (not todo.setupFilesystems): return -2

        device = "hda";

	isys.makeDevInode(device, "/tmp/" + device)
	table = _balkan.readTable("/tmp/" + device)
	os.remove("/tmp/" + device)

	partList = []
	for i in range(0, len(table) - 1):
	    (type, start, size) = table[i]
	    if (type == 0x83 and size):
		fullName = "%s%d" % (device, i + 1)
		partList.append((fullName, fullName))

	rc = ListboxChoiceWindow(screen, _("Root Partition"),
				 _("What partition would you "
				 "like to use for your root partition?"),
				 partList, buttons = [_("OK"), _("Back")])

	if rc[0] == string.lower(_("Back")):
	    return -1

	todo.addMount(rc[1], "/")

        return 0

class PackageWindow:
    def run(self, screen, todo):
        # be sure that the headers and comps files have been read.
	todo.headerList()
        todo.compsList()

        ct = CheckboxTree(height = 10, scroll = 1)
        for comp in todo.comps:
            if not comp.hidden:
                ct.append(comp.names, comp, comp.selected)

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        g = GridForm (screen, _("Package Group Selection"), 1, 2)
        g.add (ct, 0, 0, (0, 0, 0, 1))
        g.add (bb, 0, 1, growx = 1)

        result = g.runOnce()
 
        # turn off all the comps
        for comp in todo.comps:
            if not comp.hidden: comp.unselect(0)
        # turn on all the comps we selected
        for comp in ct.getSelection():
            comp.select (0)
            
        rc = bb.buttonPressed (result)

        if rc == "ok":
            return 0
        return -1

class InstallInterface:

    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def packageProgressWindow(self, total, totalSize):
	return InstallProgressWindow(self.screen, total, totalSize)

    def __init__(self):
        self.screen = SnackScreen()
        self.welcomeText = _("Red Hat Linux (C) 1999 Red Hat, Inc.")
        self.screen.drawRootText (0, 0, self.welcomeText)
        self.screen.pushHelpLine (_("  <Tab>/<Alt-Tab> between elements   |  <Space> selects   |  <F12> next screen"))
	self.screen.suspendCallback(killSelf, self)

    def __del__(self):
        self.screen.finish()

    def run(self, todo):
        steps = [
            [_("Welcome"), WelcomeWindow, (self.screen,)],
            [_("Partition"), PartitionWindow, (self.screen, todo)],
            [_("Packages"), PackageWindow, (self.screen, todo)]            
        ]

        step = 0
	dir = 1
        while step >= 0 and step < len(steps) and steps[step]:
            # clear out the old root text by writing spaces in the blank
            # area on the right side of the screen
            self.screen.drawRootText(len(self.welcomeText), 0,
                                     (self.screen.width - len(self.welcomeText)) * " ")
            self.screen.drawRootText(0 - len(steps[step][0]), 0, steps[step][0])
            rc =  apply(steps[step][1]().run, steps[step][2])
	    if rc == -1:
		dir = -1
            elif rc == 0:
		dir = 1
	    step = step + dir

	todo.liloLocation("hda")

def killSelf(screen):
    print "HERE"
    del screen
    sys.exit(0) 
