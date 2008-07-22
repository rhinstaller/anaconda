#
# text.py - text mode frontend to anaconda
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Erik Troan <ewt@redhat.com>
#            Matt Wilson <msw@redhat.com>
#

from snack import *
import sys
import os
import isys
import iutil
import time
import signal
import parted
import product
import string
from language import expandLangs
from flags import flags
from constants_text import *
from constants import *
from network import hasActiveNetDev
import imputil

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

stepToClasses = {
    "language" : ("language_text", "LanguageWindow"),
    "keyboard" : ("keyboard_text", "KeyboardWindow"),
    "welcome" : ("welcome_text", "WelcomeWindow"),
    "parttype" : ("partition_text", "PartitionTypeWindow"),    
    "custom-upgrade" : ("upgrade_text", "UpgradeExamineWindow"),
    "addswap" : ("upgrade_text", "UpgradeSwapWindow"),
    "upgrademigratefs" : ("upgrade_text", "UpgradeMigrateFSWindow"),
    "partitionmethod" : ("partmethod_text", ("PartitionMethod")),
    "partition": ("partition_text", ("PartitionWindow")),
    "zfcpconfig": ("zfcp_text", ("ZFCPWindow")),
    "findinstall" : ("upgrade_text", ("UpgradeExamineWindow")),
    "addswap" : ("upgrade_text", "UpgradeSwapWindow"),
    "upgbootloader": ("upgrade_bootloader_text", "UpgradeBootloaderWindow"),
    "bootloader" : ("bootloader_text", ("BootloaderChoiceWindow",
                                        "BootloaderAppendWindow",
                                        "BootloaderPasswordWindow",
                                        "BootloaderImagesWindow",
                                        "BootloaderLocationWindow")),
    "network" : ("network_text", ("NetworkDeviceWindow", "NetworkGlobalWindow",
                                  "HostnameWindow")),
    "timezone" : ("timezone_text", "TimezoneWindow"),
    "accounts" : ("userauth_text", "RootPasswordWindow"),
    "tasksel": ("task_text", "TaskWindow"),
    "group-selection": ("grpselect_text", "GroupSelectionWindow"),    
    "install" : ("progress_text", "setupForInstall"),
    "complete" : ("complete_text", "FinishedWindow"),
}

if iutil.isS390():
    stepToClasses["bootloader"] = ("zipl_text", ( "ZiplWindow"))

class InstallWindow:
    def __call__ (self, screen):
        raise RuntimeError, "Unimplemented screen"

class WaitWindow:
    def pop(self):
	self.screen.popWindow()
	self.screen.refresh()

    def refresh(self):
        pass

    def __init__(self, screen, title, text):
	self.screen = screen
	width = 40
	if (len(text) < width): width = len(text)

	t = TextboxReflowed(width, text)

	g = GridForm(self.screen, title, 1, 1)
	g.add(t, 0, 0)
	g.draw()
	self.screen.refresh()

class OkCancelWindow:
    def getrc(self):
	return self.rc

    def __init__(self, screen, title, text):
	rc = ButtonChoiceWindow(screen, title, text,
			        buttons=[TEXT_OK_BUTTON, _("Cancel")])
	if rc == string.lower(_("Cancel")):
	    self.rc = 1
	else:
	    self.rc = 0

class ProgressWindow:
    def pop(self):
	self.screen.popWindow()
	self.screen.refresh()
        del self.scale
        self.scale = None

    def pulse(self):
        pass

    def set(self, amount):
        self.scale.set(int(float(amount) * self.multiplier))
        self.screen.refresh()

    def refresh(self):
        pass

    def __init__(self, screen, title, text, total, updpct = 0.05, pulse = False):
        self.multiplier = 1
        if total == 1.0:
            self.multiplier = 100
	self.screen = screen
	width = 55
	if (len(text) > width): width = len(text)

	t = TextboxReflowed(width, text)

	g = GridForm(self.screen, title, 1, 2)
	g.add(t, 0, 0, (0, 0, 0, 1), anchorLeft=1)

        self.scale = Scale(int(width), int(float(total) * self.multiplier))
        if not pulse:
            g.add(self.scale, 0, 1)
                
	g.draw()
	self.screen.refresh()

class SaveExceptionWindow:
    def __init__(self, anaconda, longTracebackFile=None, screen=None):
        self.anaconda = anaconda
        self.screen = screen

    def _destCb(self, *args):
        if self.rg.getSelection() == "disk":
            self.bugzillaNameEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.bugzillaPasswordEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.bugDesc.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.scpNameEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.scpPasswordEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.scpHostEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.scpDestEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
        elif self.rg.getSelection() == "remote":
            self.bugzillaNameEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.bugzillaPasswordEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.bugDesc.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.scpNameEntry.setFlags(FLAG_DISABLED, FLAGS_RESET)
            self.scpPasswordEntry.setFlags(FLAG_DISABLED, FLAGS_RESET)
            self.scpHostEntry.setFlags(FLAG_DISABLED, FLAGS_RESET)
            self.scpDestEntry.setFlags(FLAG_DISABLED, FLAGS_RESET)
        else:
            self.bugzillaNameEntry.setFlags(FLAG_DISABLED, FLAGS_RESET)
            self.bugzillaPasswordEntry.setFlags(FLAG_DISABLED, FLAGS_RESET)
            self.bugDesc.setFlags(FLAG_DISABLED, FLAGS_RESET)
            self.scpNameEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.scpPasswordEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.scpHostEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.scpDestEntry.setFlags(FLAG_DISABLED, FLAGS_SET)

    def getrc(self):
        if self.rc == TEXT_OK_CHECK:
            return EXN_OK
        elif self.rc == TEXT_CANCEL_CHECK:
            return EXN_CANCEL

    def getDest(self):
        if self.saveToDisk():
            return self.diskList.current()
        elif self.saveToRemote():
            return map(lambda e: e.value(), [self.scpNameEntry,
                                             self.scpPasswordEntry,
                                             self.scpHostEntry,
                                             self.scpDestEntry])
        else:
            return map(lambda e: e.value(), [self.bugzillaNameEntry,
                                             self.bugzillaPasswordEntry,
                                             self.bugDesc])

    def pop(self):
        self.screen.popWindow()
        self.screen.refresh()

    def run(self):
        toplevel = GridForm(self.screen, _("Save"), 1, 7)

        self.rg = RadioGroup()
        self.diskButton = self.rg.add(_("Save to local disk"), "disk", True)
        self.bugzillaButton = self.rg.add(_("Send to bugzilla (%s)") % product.bugUrl, "bugzilla", False)
        self.remoteButton = self.rg.add(_("Send to remote server (scp)"), "remote", False)

        self.diskButton.setCallback(self._destCb, None)
        self.bugzillaButton.setCallback(self._destCb, None)
        self.remoteButton.setCallback(self._destCb, None)

        buttons = ButtonBar(self.screen, [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        self.bugzillaNameEntry = Entry(24)
        self.bugzillaPasswordEntry = Entry(24, password=1)
        self.bugDesc = Entry(24)

        self.diskList = Listbox(height=3, scroll=1)

        bugzillaGrid = Grid(2, 3)
        bugzillaGrid.setField(Label(_("User name")), 0, 0, anchorLeft=1)
        bugzillaGrid.setField(self.bugzillaNameEntry, 1, 0)
        bugzillaGrid.setField(Label(_("Password")), 0, 1, anchorLeft=1)
        bugzillaGrid.setField(self.bugzillaPasswordEntry, 1, 1)
        bugzillaGrid.setField(Label(_("Bug Description")), 0, 2, anchorLeft=1)
        bugzillaGrid.setField(self.bugDesc, 1, 2)

        self.remoteNameEntry = Entry(24)
        self.remotePasswordEntry = Entry(24, password=1)
        self.remoteHostEntry = Entry(24)
        self.remoteDestEntry = Entry(24)

        remoteGrid = Grid(2, 4)
        remoteGrid.setField(Label(_("User name")), 0, 0, anchorLeft=1)
        remoteGrid.setField(self.remoteNameEntry, 1, 0)
        remoteGrid.setField(Label(_("Password")), 0, 1, anchorLeft=1)
        remoteGrid.setField(self.remotePasswordEntry, 1, 1)
        remoteGrid.setField(Label(_("Host (host:port)")), 0, 2, anchorLeft=1)
        remoteGrid.setField(self.remoteHostEntry, 1, 2)
        remoteGrid.setField(Label(_("Destination file")), 0, 3, anchorLeft=1)
        remoteGrid.setField(self.remoteDestEntry, 1, 3)

        toplevel.add(self.diskButton, 0, 0, (0, 0, 0, 1))
        toplevel.add(self.diskList, 0, 1, (0, 0, 0, 1))
        toplevel.add(self.bugzillaButton, 0, 2, (0, 0, 0, 1))
        toplevel.add(bugzillaGrid, 0, 3, (0, 0, 0, 1))
        toplevel.add(self.remoteButton, 0, 4, (0, 0, 0, 1))
        toplevel.adD(remoteGrid, 0, 5, (0, 0, 0, 1))
        toplevel.add(buttons, 0, 6, growx=1)

        dests = self.anaconda.id.diskset.exceptionDisks(self.anaconda)

        if len(dests) > 0:
            for (dev, desc) in dests:
                self.diskList.append("/dev/%s - %s" % (dev, desc), dev)

#            self.diskList.setCurrent("sda")

            self.bugzillaNameEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
            self.bugzillaPasswordEntry.setFlags(FLAG_DISABLED, FLAGS_SET)
        else:
            self.diskButton.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)
            self.diskButton.w.checkboxSetValue(" ")
            self.bugzillaButton.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_RESET)
            self.bugzillaButton.w.checkboxSetValue("*")

        result = toplevel.run()
        self.rc = buttons.buttonPressed(result)

    def saveToDisk(self):
        return self.rg.getSelection() == "disk"

    def saveToLocal(self):
        return False

    def saveToRemote(self):
        return self.rg.getSelection() == "remote"

class MainExceptionWindow:
    def __init__ (self, shortTraceback, longTracebackFile=None, screen=None):
        self.text = "%s\n\n" % shortTraceback
        self.screen = screen

        self.buttons=[TEXT_OK_BUTTON]

        self.buttons.append(_("Save"))

        if not flags.livecdInstall:
            self.buttons.append(_("Debug"))

    def run(self):
        log.info ("in run, screen = %s" % self.screen)
	self.rc = ButtonChoiceWindow(self.screen, _("Exception Occurred"),
                                     self.text, self.buttons)

    def getrc(self):
        if self.rc == string.lower(_("Debug")):
            return EXN_DEBUG
        elif self.rc == string.lower(_("Save")):
            return EXN_SAVE
        else:
            return EXN_OK

    def pop(self):
        self.screen.popWindow()
	self.screen.refresh()

class PassphraseEntryWindow:
    def __init__(self, screen, device):
        self.screen = screen
        self.txt = _("Device %s is encrypted. In order to "
                     "access the device's contents during "
                     "installation you must enter the device's "
                     "passphrase below.") % (device,)
        self.rc = None

    def run(self):
        toplevel = GridForm(self.screen, _("Passphrase"), 1, 4)

        txt = TextboxReflowed(65, self.txt)
        toplevel.add(txt, 0, 0)

        passphraseentry = Entry(60, password = 1)
        toplevel.add(passphraseentry, 0, 1, (0,0,0,1))

        globalcheckbox = Checkbox(_("This is a global passphrase"))
        toplevel.add(globalcheckbox, 0, 2)

        buttons = ButtonBar(self.screen, [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        toplevel.add(buttons, 0, 3, growx=1)

        rc = toplevel.run()
        res = buttons.buttonPressed(rc)

        passphrase = None
        isglobal = False
        if res == TEXT_OK_CHECK:
            passphrase = passphraseentry.value().strip()
            isglobal = globalcheckbox.selected()

        self.rc = (passphrase, isglobal)
        return self.rc

    def pop(self):
        self.screen.popWindow()

class InstallInterface:
    def progressWindow(self, title, text, total, updpct = 0.05, pulse = False):
        return ProgressWindow(self.screen, title, text, total, updpct, pulse)

    def messageWindow(self, title, text, type="ok", default = None,
		      custom_icon=None, custom_buttons=[]):
	if type == "ok":
	    ButtonChoiceWindow(self.screen, title, text,
			       buttons=[TEXT_OK_BUTTON])
        elif type == "yesno":
            if default and default == "no":
                btnlist = [TEXT_NO_BUTTON, TEXT_YES_BUTTON]
            else:
                btnlist = [TEXT_YES_BUTTON, TEXT_NO_BUTTON]
	    rc = ButtonChoiceWindow(self.screen, title, text,
			       buttons=btnlist)
            if rc == "yes":
                return 1
            else:
                return 0
	elif type == "custom":
	    tmpbut = []
	    for but in custom_buttons:
		tmpbut.append(string.replace(but,"_",""))

	    rc = ButtonChoiceWindow(self.screen, title, text, width=60,
				    buttons=tmpbut)

	    idx = 0
	    for b in tmpbut:
		if string.lower(b) == rc:
		    return idx
		idx = idx + 1
	    return 0
	else:
	    return OkCancelWindow(self.screen, title, text)

    def detailedMessageWindow(self, title, text, longText=None, type="ok",
                              default=None, custom_icon=None,
                              custom_buttons=[]):
        return self.messageWindow(title, text, type, default, custom_icon,
                                  custom_buttons)

    def createRepoWindow(self, anaconda):
        self.messageWindow(_("Error"),
                           _("Repository editing is not available in text mode."))

    def editRepoWindow(self, anaconda, repoObj):
        self.messageWindow(_("Error"),
                           _("Repository editing is not available in text mode."))

    def entryWindow(self, title, text, prompt, entrylength = None):
        (res, value) = EntryWindow(self.screen, title, text, [prompt])
        if res == "cancel":
            return None
        r = value[0]
        r.strip()
        return r

    def passphraseEntryWindow(self, device):
        w = PassphraseEntryWindow(self.screen, device)
        (passphrase, isglobal) = w.run()
        w.pop()
        return (passphrase, isglobal)

    def enableNetwork(self, anaconda):
        from netconfig_text import NetworkConfiguratorText
        w = NetworkConfiguratorText(self.screen, anaconda)
        ret = w.run()
        return ret != INSTALL_BACK

    def getInstallKey(self, anaconda, key = ""):
        ic = anaconda.id.instClass
        keyname = _(ic.instkeyname)
        if keyname is None:
            keyname = _("Installation Key")

        g = GridFormHelp(self.screen, keyname, "instkey", 1, 6)

        txt = TextboxReflowed(65, ic.instkeydesc or
                              _("Please enter your %(instkey)s") %
                              {"instkey": keyname,})
        g.add(txt, 0, 0, (0,0,0,1))


        radio = RadioGroup()
        keyradio = radio.add(keyname, "key", int(not anaconda.id.instClass.skipkey))
        keyentry = Entry(24)
        keyentry.set(key)

        sg = Grid(3, 1)
        sg.setField(keyradio, 0, 0)
        sg.setField(Label("      "), 1, 0)
        sg.setField(keyentry, 2, 0, (1,0,0,0))
        g.add(sg, 0, 1)

        if ic.allowinstkeyskip:
            skipradio = radio.add(_("Skip entering %(instkey)s") %
                                  {"instkey": keyname}, "skip", 
                                  int(anaconda.id.instClass.skipkey))
            g.add(skipradio, 0, 2)

        bb = ButtonBar(self.screen, [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON ])
        g.add(bb, 0, 5, (0,1,0,0))
        rc = g.run()
        res = bb.buttonPressed(rc)
        if res == TEXT_BACK_CHECK:
            self.screen.popWindow()
            return None
        if radio.getSelection() == "skip":
            self.screen.popWindow()            
            return SKIP_KEY
        key = keyentry.value()
        self.screen.popWindow()
        return key
        

    def kickstartErrorWindow(self, text):
        s = _("The following error was found while parsing your "
              "kickstart configuration:\n\n%s") %(text,)
        self.messageWindow(_("Error Parsing Kickstart Config"),
                           s,
                           type = "custom",
                           custom_buttons = [("_Reboot")],
                           custom_icon="error")
                           
    def mainExceptionWindow(self, shortText, longTextFile):
        log.critical(shortText)
        exnWin = MainExceptionWindow(shortText, longTextFile, self.screen)
        return exnWin

    def saveExceptionWindow(self, anaconda, longTextFile):
        win = SaveExceptionWindow (anaconda, longTextFile, self.screen)
        return win

    def partedExceptionWindow(self, exc):
        # if our only option is to cancel, let us handle the exception
        # in our code and avoid popping up the exception window here.
        if exc.options == parted.EXCEPTION_CANCEL:
            return parted.EXCEPTION_UNHANDLED
        log.critical("parted exception: %s: %s" %(exc.type_string,exc.message))
        buttons = []
        buttonToAction = {}
        flags = ((parted.EXCEPTION_FIX, N_("Fix")),
                 (parted.EXCEPTION_YES, N_("Yes")),
                 (parted.EXCEPTION_NO, N_("No")),
                 (parted.EXCEPTION_OK, N_("OK")),
                 (parted.EXCEPTION_RETRY, N_("Retry")),
                 (parted.EXCEPTION_IGNORE, N_("Ignore")),
                 (parted.EXCEPTION_CANCEL, N_("Cancel")))
        for flag, errorstring in flags:
            if exc.options & flag:
                buttons.append(_(errorstring))
                buttonToAction[string.lower(_(errorstring))] = flag

        rc = None
        while not buttonToAction.has_key(rc):
            rc = ButtonChoiceWindow(self.screen, exc.type_string, exc.message,
                                    buttons=buttons)

        return buttonToAction[rc]
    

    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def beep(self):
        # no-op.  could call newtBell() if it was bound
        pass

    def drawFrame(self):
        self.screen.drawRootText (0, 0, self.screen.width * " ")
        if productArch:
          self.screen.drawRootText (0, 0, _("Welcome to %s for %s") % (productName, productArch,))
        else:
          self.screen.drawRootText (0, 0, _("Welcome to %s") % productName)

        self.screen.pushHelpLine(_("  <Tab>/<Alt-Tab> between elements   |  <Space> selects   |  <F12> next screen"))

    def setScreen(self, screen):
        self.screen = screen

    def shutdown(self):
	self.screen.finish()
	self.screen = None

    def __init__(self):
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	signal.signal(signal.SIGTSTP, signal.SIG_IGN)
	self.screen = SnackScreen()

    def __del__(self):
	if self.screen:
	    self.screen.finish()

    def isRealConsole(self):
        """Returns True if this is a _real_ console that can do things, False
        for non-real consoles such as serial, i/p virtual consoles or xen."""
        if flags.serial or flags.virtpconsole:
            return False
        if isys.isPseudoTTY(0):
            return False
        if isys.isVioConsole():
            return False
        if os.path.exists("/proc/xen"): # this keys us that we're a xen guest
            return False
        return True

    def run(self, anaconda):
        instLang = anaconda.id.instLanguage

        if instLang.getFontFile(instLang.getCurrent()) == "none":
            if not anaconda.isKickstart:
                ButtonChoiceWindow(self.screen, "Language Unavailable",
                                   "%s display is unavailable in text mode.  "
                                   "The installation will continue in "
                                   "English." % (instLang.getCurrent(),),
                                   buttons=[TEXT_OK_BUTTON])

	if not self.isRealConsole():
	    self.screen.suspendCallback(spawnShell, self.screen)

        # drop into the python debugger on ctrl-z if we're running in test mode
        if flags.debug or flags.test:
            self.screen.suspendCallback(debugSelf, self.screen)

        self.instLanguage = anaconda.id.instLanguage

        # draw the frame after setting up the fallback
        self.drawFrame()

        anaconda.id.fsset.registerMessageWindow(self.messageWindow)
        anaconda.id.fsset.registerProgressWindow(self.progressWindow)
        anaconda.id.fsset.registerWaitWindow(self.waitWindow)

	parted.exception_set_handler(self.partedExceptionWindow)

	lastrc = INSTALL_OK
	(step, instance) = anaconda.dispatch.currentStep()
	while step:
	    (file, classNames) = stepToClasses[step]

	    if type(classNames) != type(()):
		classNames = (classNames,)

	    if lastrc == INSTALL_OK:
		step = 0
	    else:
		step = len(classNames) - 1

	    while step >= 0 and step < len(classNames):
                # reget the args.  they could change (especially direction)
                (foo, args) = anaconda.dispatch.currentStep()
                nextWindow = None

                while 1:
                    try:
                        found = imputil.imp.find_module(file)
                        loaded = imputil.imp.load_module(classNames[step],
                                                         found[0], found[1],
                                                         found[2])
                        nextWindow = loaded.__dict__[classNames[step]]
                        break
                    except ImportError, e:
                        rc = ButtonChoiceWindow(self.screen, _("Error!"),
                                          _("An error occurred when attempting "
                                            "to load an installer interface "
                                            "component.\n\nclassName = %s")
                                          % (classNames[step],),
                                          buttons=[_("Exit"), _("Retry")])

                        if rc == string.lower(_("Exit")):
                            sys.exit(0)

		win = nextWindow()

		#log.info("TUI running step %s (class %s, file %s)" % 
			 #(step, file, classNames))

                rc = win(self.screen, instance)

		if rc == INSTALL_NOOP:
		    rc = lastrc

		if rc == INSTALL_BACK:
		    step = step - 1
                    anaconda.dispatch.dir = DISPATCH_BACK
		elif rc == INSTALL_OK:
		    step = step + 1
                    anaconda.dispatch.dir = DISPATCH_FORWARD

		lastrc = rc

	    if step == -1:
                if not anaconda.dispatch.canGoBack():
                    ButtonChoiceWindow(self.screen, _("Cancelled"),
                                       _("I can't go to the previous step "
                                         "from here. You will have to try "
                                         "again."),
                                       buttons=[_("OK")])
		anaconda.dispatch.gotoPrev()
	    else:
		anaconda.dispatch.gotoNext()

	    (step, args) = anaconda.dispatch.currentStep()

        self.screen.finish()

def killSelf(screen):
    screen.finish()
    os._exit(0)

def debugSelf(screen):
    screen.suspend()
    import pdb
    try:
        pdb.set_trace()
    except:
        sys.exit(-1)
    screen.resume()

def spawnShell(screen):
    screen.suspend()
    print "\n\nType <exit> to return to the install program.\n"
    if os.path.exists("/bin/sh"):
        iutil.execConsole()
    else:
        print "Unable to find /bin/sh to execute!  Not starting shell"
    time.sleep(5)
    screen.resume()
