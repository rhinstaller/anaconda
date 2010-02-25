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
from installinterfacebase import InstallInterfaceBase
import imputil

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

import logging
log = logging.getLogger("anaconda")

stepToClasses = {
    "language" : ("language_text", "LanguageWindow"),
    "keyboard" : ("keyboard_text", "KeyboardWindow"),
    "welcome" : ("welcome_text", "WelcomeWindow"),
    "parttype" : ("partition_text", "PartitionTypeWindow"),
    "addswap" : ("upgrade_text", "UpgradeSwapWindow"),
    "upgrademigratefs" : ("upgrade_text", "UpgradeMigrateFSWindow"),
    "zfcpconfig": ("zfcp_text", ("ZFCPWindow")),
    "findinstall" : ("upgrade_text", ("UpgradeExamineWindow")),
    "upgbootloader": ("upgrade_bootloader_text", "UpgradeBootloaderWindow"),
    "network" : ("network_text", ("HostnameWindow")),
    "timezone" : ("timezone_text", "TimezoneWindow"),
    "accounts" : ("userauth_text", "RootPasswordWindow"),
    "tasksel": ("task_text", "TaskWindow"),
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

class LuksPassphraseWindow:
    def __init__(self, screen, passphrase = "", preexist = False):
        self.screen = screen
        self.passphrase = passphrase
        self.minLength = 8
        self.preexist = preexist
        self.txt = _("Choose a passphrase for the encrypted devices. You "
                     "will be prompted for this passphrase during system boot.")
        self.rc = None

    def run(self):
        toplevel = GridForm(self.screen, _("Passphrase for encrypted device"),
                            1, 5)

        txt = TextboxReflowed(65, self.txt)
        toplevel.add(txt, 0, 0)

        passphraseentry = Entry(60, password = 1)
        toplevel.add(passphraseentry, 0, 1, (0,0,0,1))

        confirmentry = Entry(60, password = 1)
        toplevel.add(confirmentry, 0, 2, (0,0,0,1))

        if self.preexist:
            globalcheckbox = Checkbox(_("Also add this passphrase to all existing encrypted devices"), isOn = True)
            toplevel.add(globalcheckbox, 0, 3)

        buttons = ButtonBar(self.screen, [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        toplevel.add(buttons, 0, 4, growx=1)

        passphraseentry.set(self.passphrase)
        confirmentry.set(self.passphrase)

        while True:
            rc = toplevel.run()
            res = buttons.buttonPressed(rc)

            passphrase = None
            if res == TEXT_OK_CHECK or rc == "F12":
                passphrase = passphraseentry.value()
                confirm = confirmentry.value()

                if passphrase != confirm:
                    ButtonChoiceWindow(self.screen,
                                       _("Error with passphrase"),
                                       _("The passphrases you entered were "
                                         "different.  Please try again."),
                                       buttons=[TEXT_OK_BUTTON])
                    passphraseentry.set("")
                    confirmentry.set("")
                    continue

                if len(passphrase) < self.minLength:
                    ButtonChoiceWindow(self.screen,
                                       _("Error with passphrase"),
                                       P_("The passphrase must be at least "
                                          "%d character long.",
                                          "The passphrase must be at least "
                                          "%d characters long.",
                                          self.minLength)
                                         % (self.minLength,),
                                       buttons=[TEXT_OK_BUTTON])
                    passphraseentry.set("")
                    confirmentry.set("")
                    continue
            else:
                passphrase = self.passphrase
                passphraseentry.set(self.passphrase)
                confirmentry.set(self.passphrase)

            retrofit = False
            if self.preexist:
                retrofit = globalcheckbox.selected()
            self.rc = passphrase
            return (self.rc, retrofit)

    def pop(self):
        self.screen.popWindow()

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

class InstallInterface(InstallInterfaceBase):
    def progressWindow(self, title, text, total, updpct = 0.05, pulse = False):
        return ProgressWindow(self.screen, title, text, total, updpct, pulse)

    def setInstallProgressClass(self, c):
        self.instProgress = c

    def exitWindow(self, title, text):
        return self.messageWindow(title, text, type="custom",
                                  custom_buttons=[_("Exit installer")])

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
        t = TextboxReflowed(60, text, maxHeight=8)
        lt = Textbox(60, 6, longText, scroll=1, wrap=1)
        g = GridFormHelp(self.screen, title, help, 1, 3)
        g.add(t, 0, 0)
        g.add(lt, 0, 1, padding = (0, 1, 0, 1))

        if type == "ok":
            bb = ButtonBar(self.screen, [TEXT_OK_BUTTON])
            g.add(bb, 0, 2, growx = 1)
            return bb.buttonPressed(g.runOnce(None, None))
        elif type == "yesno":
            if default and default == "no":
                buttons = [TEXT_NO_BUTTON, TEXT_YES_BUTTON]
            else:
                buttons = [TEXT_YES_BUTTON, TEXT_NO_BUTTON]

            bb = ButtonBar(self.screen, buttons)
            g.add(bb, 0, 2, growx = 1)
            rc = bb.buttonPressed(g.runOnce(None, None))

            if rc == "yes":
                return 1
            else:
                return 0
        elif type == "custom":
            buttons = []
            idx = 0

            for button in custom_buttons:
                buttons.append(string.replace(button, "_", ""))

            bb = ButtonBar(self.screen, buttons)
            g.add(bb, 0, 2, growx = 1)
            rc = bb.buttonPressed(g.runOnce(None, None))

            for b in buttons:
                if string.lower(b) == rc:
                    return idx
                idx += 1

            return 0
        else:
            return self.messageWindow(title, text, type, default, custom_icon,
                                      custom_buttons)

    def createRepoWindow(self):
        self.messageWindow(_("Error"),
                           _("Repository editing is not available in text mode."))

    def editRepoWindow(self, repoObj):
        self.messageWindow(_("Error"),
                           _("Repository editing is not available in text mode."))

    def entryWindow(self, title, text, prompt, entrylength = None):
        (res, value) = EntryWindow(self.screen, title, text, [prompt])
        if res == "cancel":
            return None
        r = value[0]
        r.strip()
        return r

    def getLuksPassphrase(self, passphrase = "", preexist = False):
        w = LuksPassphraseWindow(self.screen, passphrase = passphrase,
                                 preexist = preexist)
        rc = w.run()
        w.pop()
        return rc

    def passphraseEntryWindow(self, device):
        w = PassphraseEntryWindow(self.screen, device)
        (passphrase, isglobal) = w.run()
        w.pop()
        return (passphrase, isglobal)

    def enableNetwork(self):
        if len(self.anaconda.network.netdevices) == 0:
            return False
        from netconfig_text import NetworkConfiguratorText
        w = NetworkConfiguratorText(self.screen, self.anaconda)
        ret = w.run()
        return ret != INSTALL_BACK

    def kickstartErrorWindow(self, text):
        s = _("The following error was found while parsing the "
              "kickstart configuration file:\n\n%s") %(text,)
        self.messageWindow(_("Error Parsing Kickstart Config"),
                           s,
                           type = "custom",
                           custom_buttons = [("_Reboot")],
                           custom_icon="error")
                           
    def mainExceptionWindow(self, shortText, longTextFile):
        from meh.ui.text import MainExceptionWindow
        log.critical(shortText)
        exnWin = MainExceptionWindow(shortText, longTextFile, screen=self.screen)
        return exnWin

    def saveExceptionWindow(self, longTextFile, desc="", *args, **kwargs):
        from meh.ui.text import SaveExceptionWindow
        win = SaveExceptionWindow (longTextFile, desc=desc, screen=self.screen,
                                   *args, **kwargs)
        return win

    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def beep(self):
        # no-op.  could call newtBell() if it was bound
        pass

    def drawFrame(self):
        self.screen.drawRootText (0, 0, self.screen.width * " ")
        if productArch:
          self.screen.drawRootText (0, 0, _("Welcome to %(productName)s for %(productArch)s") % {'productName': productName, 'productArch': productArch})
        else:
          self.screen.drawRootText (0, 0, _("Welcome to %s") % productName)

        self.screen.pushHelpLine(_("  <Tab>/<Alt-Tab> between elements   |  <Space> selects   |  <F12> next screen"))

    def setScreen(self, screen):
        self.screen = screen

    def shutdown(self):
	self.screen.finish()
	self.screen = None

    def suspend(self):
        self.screen.suspend()

    def resume(self):
        self.screen.resume()

    def __init__(self):
	InstallInterfaceBase.__init__(self)
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	signal.signal(signal.SIGTSTP, signal.SIG_IGN)
	self.screen = SnackScreen()
        self.instProgress = None
        self._initLabelAnswers = {}
        self._inconsistentLVMAnswers = {}

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
        return True

    def resetInitializeDiskQuestion(self):
        self._initLabelAnswers = {}

    def questionInitializeDisk(self, path, description, size, details=""):

        retVal = False # The less destructive default

        if not path:
            return retVal

        # we are caching answers so that we don't
        # ask in each storage.reset() again
        if path in self._initLabelAnswers:
            log.info("UI not asking about disk initialization, "
                     "using cached answer: %s" % self._initLabelAnswers[path])
            return self._initLabelAnswers[path]
        elif "all" in self._initLabelAnswers:
            log.info("UI not asking about disk initialization, "
                     "using cached answer: %s" % self._initLabelAnswers["all"])
            return self._initLabelAnswers["all"]

        rc = self.messageWindow(_("Warning"),
                _("Error processing drive:\n\n"
                  "%(path)s\n%(size)-0.fMB\n%(description)s\n\n"
                  "This device may need to be reinitialized.\n\n"
                  "REINITIALIZING WILL CAUSE ALL DATA TO BE LOST!\n\n"
                  "This action may also be applied to all other disks "
                  "needing reinitialization.%(details)s")
                % {'path': path, 'size': size,
                   'description': description, 'details': details},
                type="custom",
                custom_buttons = [ _("_Ignore"),
                                   _("Ignore _all"),
                                   _("_Re-initialize"),
                                   _("Re-ini_tialize all") ],
                custom_icon="question")
        if rc == 0:
            retVal = False
        elif rc == 1:
            path = "all"
            retVal = False
        elif rc == 2:
            retVal = True
        elif rc == 3:
            path = "all"
            retVal = True

        self._initLabelAnswers[path] = retVal
        return retVal

    def resetReinitInconsistentLVMQuestion(self):
        self._inconsistentLVMAnswers = {}

    def questionReinitInconsistentLVM(self, pv_names=None, lv_name=None, vg_name=None):

        retVal = False # The less destructive default
        allSet = frozenset(["all"])

        if not pv_names or (lv_name is None and vg_name is None):
            return retVal

        # We are caching answers so that we don't ask for ignoring
        # in each storage.reset() again (note that reinitialization is
        # done right after confirmation in dialog, not as a planned
        # action).
        key = frozenset(pv_names)
        if key in self._inconsistentLVMAnswers:
            log.info("UI not asking about disk initialization, "
                     "using cached answer: %s" % self._inconsistentLVMAnswers[key])
            return self._inconsistentLVMAnswers[key]
        elif allSet in self._inconsistentLVMAnswers:
            log.info("UI not asking about disk initialization, "
                     "using cached answer: %s" % self._inconsistentLVMAnswers[allSet])
            return self._inconsistentLVMAnswers[allSet]

        if vg_name is not None:
            message = "Volume Group %s" % vg_name
        elif lv_name is not None:
            message = "Logical Volume %s" % lv_name

        na = {'msg': message, 'pvs': ", ".join(pv_names)}
        rc = self.messageWindow(_("Warning"),
                  _("Error processing LVM.\n"
                    "There is inconsistent LVM data on %(msg)s.  You can "
                    "reinitialize all related PVs (%(pvs)s) which will erase "
                    "the LVM metadata, or ignore which will preserve the "
                    "contents.  This action may also be applied to all other "
                    "PVs with inconsistent metadata.") % na,
                type="custom",
                custom_buttons = [ _("_Ignore"),
                                   _("Ignore _all"),
                                   _("_Re-initialize"),
                                   _("Re-ini_tialize all") ],
                custom_icon="question")
        if rc == 0:
            retVal = False
        elif rc == 1:
            key = allSet
            retVal = False
        elif rc == 2:
            retVal = True
        elif rc == 3:
            key = allSet
            retval = True

        self._inconsistentLVMAnswers[key] = retVal
        return retVal

    def run(self, anaconda):
        self.anaconda = anaconda
        instLang = anaconda.instLanguage

        if instLang.getFontFile(instLang.instLang) == "none":
            if not anaconda.ksdata:
                ButtonChoiceWindow(self.screen, "Language Unavailable",
                                   "%s display is unavailable in text mode.  "
                                   "The installation will continue in "
                                   "English." % (instLang.instLang,),
                                   buttons=[TEXT_OK_BUTTON])

	if not self.isRealConsole():
	    self.screen.suspendCallback(spawnShell, self.screen)

        # drop into the python debugger on ctrl-z if we're running in test mode
        if flags.debug:
            self.screen.suspendCallback(debugSelf, self.screen)

        # draw the frame after setting up the fallback
        self.drawFrame()

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

    def setSteps(self, anaconda):
        anaconda.dispatch.skipStep("filtertype", permanent=1)
        anaconda.dispatch.skipStep("filter", permanent=1)
        anaconda.dispatch.skipStep("cleardiskssel", permanent=1)
        anaconda.dispatch.skipStep("group-selection", permanent=1)

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
    print("\n\nType <exit> to return to the install program.\n")
    if os.path.exists("/bin/sh"):
        iutil.execConsole()
    else:
        print("Unable to find /bin/sh to execute!  Not starting shell")
    time.sleep(5)
    screen.resume()
