#
# text.py - text mode frontend to anaconda
#
# Erik Troan <ewt@redhat.com>
# Matt Wilson <msw@redhat.com>
#
# Copyright 1999-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
import sys
import os
import isys
import iutil
import time
import signal
import parted
import string
import kudzu
from language import expandLangs
from flags import flags
from constants_text import *
from constants import *
from network import hasActiveNetDev
import floppy

import rhpl
from rhpl.translate import _, cat, N_

import logging
log = logging.getLogger("anaconda")

stepToClasses = {
    "language" : ("language_text", "LanguageWindow"),
    "keyboard" : ("keyboard_text", "KeyboardWindow"),
    "mouse" : ("mouse_text", ("MouseWindow", "MouseDeviceWindow")),
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
                                        "BootloaderPasswordWindow")),
    "bootloaderadvanced" : ("bootloader_text", ("BootloaderImagesWindow",
                                                "BootloaderLocationWindow")),
    "network" : ("network_text", ("NetworkDeviceWindow", "NetworkGlobalWindow",
                                  "HostnameWindow")),
    "timezone" : ("timezone_text", "TimezoneWindow"),
    "accounts" : ("userauth_text", "RootPasswordWindow"),
    "tasksel": ("task_text", "TaskWindow"),
    "group-selection": ("grpselect_text", "GroupSelectionWindow"),    
    "confirminstall" : ("confirm_text", "BeginInstallWindow"),
    "confirmupgrade" : ("confirm_text", "BeginUpgradeWindow"),
    "install" : ("progress_text", "setupForInstall"),
    "complete" : ("complete_text", "FinishedWindow"),
}

if rhpl.getArch() == 's390':
    stepToClasses["bootloader"] = ("zipl_text", ( "ZiplWindow"))

class InstallWindow:
    def __call__ (self, screen):
        raise RuntimeError, "Unimplemented screen"

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

    def set(self, amount):
        self.scale.set(float(amount) * self.multiplier)
        self.screen.refresh()

    def refresh(self):
        pass

    def __init__(self, screen, title, text, total, updpct = 0.05):
        self.multiplier = 1
        if total == 1.0:
            self.multiplier = 100
	self.screen = screen
	width = 55
	if (len(text) > width): width = len(text)

	t = TextboxReflowed(width, text)

	g = GridForm(self.screen, title, 1, 2)
	g.add(t, 0, 0, (0, 0, 0, 1), anchorLeft=1)

        self.scale = Scale(int(width), float(total) * self.multiplier)
        g.add(self.scale, 0, 1)
                
	g.draw()
	self.screen.refresh()

class ExceptionWindow:
    def __init__ (self, shortTraceback, longTracebackFile=None, screen=None):
        self.text = "%s\n\n" % shortTraceback
        self.screen = screen

        self.buttons=[TEXT_OK_BUTTON]

        if floppy.hasFloppyDevice() == True or flags.debug:
            self.buttons.append(_("Save"))

        if hasActiveNetDev() or flags.debug:
            self.buttons.append(_("Remote"))

        self.buttons.append(_("Debug"))

    def run(self):
        log.info ("in run, screen = %s" % self.screen)
	self.rc = ButtonChoiceWindow(self.screen, _("Exception Occurred"),
                                     self.text, self.buttons)

    def getrc(self):
        if self.rc == string.lower(_("Debug")):
            return 1
	elif self.rc == string.lower(_("Save")):
            return 2
        elif self.rc == string.lower(_("Remote")):
            return 3
        else:
            return 0

    def pop(self):
        self.screen.popWindow()
	self.screen.refresh()

class ScpWindow:
    def __init__(self, screen=None):
        self.screen = screen
        pass

    def run(self):
        buttons = ButtonBar(self.screen, [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        self.hostEntry = Entry(24)
        self.pathEntry = Entry(24)
        self.usernameEntry = Entry(24)
        self.passwordEntry = Entry(24, password=1)

        win = GridForm(self.screen, _("Save to Remote Host"), 1, 2)

        subgrid = Grid(2, 4)
        subgrid.setField(Label(_("Host")), 0, 0, anchorLeft=1)
        subgrid.setField(self.hostEntry, 1, 0)
        subgrid.setField(Label(_("Remote path")), 0, 1, anchorLeft=1)
        subgrid.setField(self.pathEntry, 1, 1)
        subgrid.setField(Label(_("User name")), 0, 2, anchorLeft=1)
        subgrid.setField(self.usernameEntry, 1, 2)
        subgrid.setField(Label(_("Password")), 0, 3, anchorLeft=1)
        subgrid.setField(self.passwordEntry, 1, 3)

        win.add(subgrid, 0, 0, (0, 0, 0, 1))
        win.add(buttons, 0, 1)

        result = win.run()
        self.rc = buttons.buttonPressed(result)

    def getrc(self):
        if self.rc == TEXT_CANCEL_CHECK:
            return None
        elif self.rc == TEXT_OK_CHECK:
            retval = (self.hostEntry.value(), self.pathEntry.value(),
                      self.usernameEntry.value(), self.passwordEntry.value())
            return retval

    def pop(self):
        self.screen.popWindow()
	self.screen.refresh()
        pass

class LuksPassphraseWindow:
    def __init__(self, screen, passphrase = "", preexist = False):
        self.screen = screen
        self.passphrase = passphrase
        self.minLength = 8
        self.preexist = preexist
        self.txt = _("Choose a passphrase for your encrypted devices. "
                     "You will be prompted for the passphrase during system "
                     "boot.")
        self.rc = None

    def run(self):
        toplevel = GridForm(self.screen, _("Passphrase for encrypted devices"),
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
        toplevel.add(buttons, 0, 3, growx=1)

        passphraseentry.set(self.passphrase)
        confirmentry.set(self.passphrase)

        while True:
            rc = toplevel.run()
            res = buttons.buttonPressed(rc)

            passphrase = None
            if res == TEXT_OK_CHECK:
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
                                       _("The passphrase must be at least "
                                         "%d characters long.") % (self.minLength,),
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
            return (passphrase, retrofit)

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

class InstallInterface:
    def helpWindow(self, screen, key):
        if key == "helponhelp":
            if self.showingHelpOnHelp:
                return None
            else:
                self.showingHelpOnHelp = 1
	try:
            f = None

            arch = "-%s" % (rhpl.getArch(),)
            tags = ["%s" % (arch,), "" ]

	    # XXX
	    #
	    # HelpWindow can't get to the langauge

            found = 0
            for path in ("./text-", "/mnt/source/RHupdates/", "/tmp/updates/",
                         "/usr/share/anaconda/"):
                if found:
                    break
                for lang in self.instLanguage.getCurrentLangSearchList():
                    for tag in tags:
                        fn = "%shelp/%s/s1-help-screens-%s%s.txt" \
                             % (path, lang, key, tag)

                        try:
                            f = open(fn)
                        except IOError, msg:
                            continue
                        found = 1
                        break

            if not f:
                ButtonChoiceWindow(screen, _("Help not available"), 
                                   _("No help is available for this "
                                     "step of the install."),
                                   buttons=[TEXT_OK_BUTTON])
                return None

	    lines = f.readlines()
            for l in lines:
                l = l.replace("@RHL@", productName)
                l = l.replace("@RHLVER@", productVersion)
	    while not string.strip(l[0]):
		l = l[1:]
	    title = string.strip(l[0])
	    l = l[1:]
	    while not string.strip(l[0]):
		l = l[1:]
	    f.close()

	    height = 10
	    scroll = 1
	    if len(l) < height: 
		height = len(l)
		scroll = 0

	    width = len(title) + 6
	    stream = ""
	    for line in l:
		line = string.strip(line)
		stream = stream + line + "\n"
		if len(line) > width:
		    width = len(line)

	    bb = ButtonBar(screen, [TEXT_OK_BUTTON])
	    t = Textbox(width, height, stream, scroll=scroll)

	    g = GridFormHelp(screen, title, "helponhelp", 1, 2)
	    g.add(t, 0, 0, padding=(0, 0, 0, 1))
	    g.add(bb, 0, 1, growx=1)

	    g.runOnce()
            self.showingHelpOnHelp = 0
	except:
	    import traceback
	    (type, value, tb) = sys.exc_info()
	    from string import joinfields
	    list = traceback.format_exception(type, value, tb)
	    text = joinfields(list, "")
	    win = self.exceptionWindow(text, None)
            win.run()
            rc = win.getrc()
	    if rc == 1:
		import pdb
		pdb.post_mortem(tb)
	    os._exit(1)

    def progressWindow(self, title, text, total, updpct = 0.05):
        return ProgressWindow(self.screen, title, text, total, updpct)

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

    def entryWindow(self, title, text, prompt, entrylength = None):
        (res, value) = EntryWindow(self.screen, title, text, [prompt])
        if res == "cancel":
            return None
        r = value[0]
        r.strip()
        return r

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
        keyradio = radio.add(keyname, "key", int(not ic.skipkey))
        keyentry = Entry(24)
        keyentry.set(key)

        sg = Grid(3, 1)
        sg.setField(keyradio, 0, 0)
        sg.setField(Label("      "), 1, 0)
        sg.setField(keyentry, 2, 0, (1,0,0,0))
        g.add(sg, 0, 1)

        if ic.allowinstkeyskip:
            skipradio = radio.add(_("Skip entering %(instkey)s") %
                                  {"instkey": keyname}, "skip", int(ic.skipkey))
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
        
    def passphraseEntryWindow(self, device):
        w = PassphraseEntryWindow(self.screen, device)
        (passphrase, isglobal) = w.run()
        w.pop()
        return (passphrase, isglobal)

    def getLuksPassphrase(self, passphrase = "", preexist = False):
        w = LuksPassphraseWindow(self.screen, passphrase = passphrase,
                                 preexist = preexist)
        rc = w.run()
        w.pop()
        return rc

    def kickstartErrorWindow(self, text):
        s = _("The following error was found while parsing your "
              "kickstart configuration:\n\n%s") %(text,)
        self.messageWindow(_("Error Parsing Kickstart Config"),
                           s,
                           type = "custom",
                           custom_buttons = [("_Reboot")],
                           custom_icon="error")
                           
    

    def dumpWindow(self):
	rc = ButtonChoiceWindow(self.screen, _("Save Crash Dump"),
	    _("Please insert a floppy now. All contents of the disk "
	      "will be erased, so please choose your diskette carefully."),
	    [TEXT_OK_BUTTON, _("Cancel")])

        if rc == string.lower(_("Cancel")):
	    return 1

	return 0

    def scpWindow(self):
        return ScpWindow(self.screen)

    def exceptionWindow(self, shortText, longTextFile):
        log.critical(shortText)
        exnWin = ExceptionWindow(shortText, longTextFile, self.screen)
        return exnWin

    def partedExceptionWindow(self, exc, anaconda):
        # if our only option is to cancel, let us handle the exception
        # in our code and avoid popping up the exception window here.
        if exc.options == parted.EXCEPTION_CANCEL:
            return parted.EXCEPTION_UNHANDLED
        log.critical("parted exception: %s: %s" %(exc.type_string,exc.message))

        if anaconda.isKickstart and exc.type == parted.EXCEPTION_WARNING and \
           exc.options in [parted.EXCEPTION_IGNORE, parted.EXCEPTION_OK]:
            return 0

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
        self.welcomeText = _("Welcome to %s") % (productName,)
        self.screen.drawRootText (0, 0, self.welcomeText)
	self.screen.drawRootText (len(_(self.welcomeText)), 0,
                                  (self.screen.width -
                                   len(_(self.welcomeText))) * " ")
        
	if (os.access("/usr/share/anaconda/help/C/s1-help-screens-lang.txt", os.R_OK)):
	    self.screen.pushHelpLine(_(" <F1> for help | <Tab> between elements | <Space> selects | <F12> next screen"))
	else:
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
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	signal.signal(signal.SIGTSTP, signal.SIG_IGN)
	self.screen = SnackScreen()
        self.showingHelpOnHelp = 0

    def __del__(self):
	if self.screen:
	    self.screen.finish()

    def isRealConsole(self):
        """Returns True if this is a _real_ console that can do things, False
        for non-real consoles such as serial, i/p virtual consoles or xen."""
        if flags.serial or flags.virtpconsole:
            return False
        if isys.isPsudoTTY(0):
            return False
        if isys.isVioConsole():
            return False
        if iutil.inXen():
            return False
        return True

    def run(self, anaconda):
        instLang = anaconda.id.instLanguage

        if instLang.getFontFile(instLang.getCurrent()) == "none":
            if anaconda.isKickstart and not anaconda.id.instClass.ksdata.interactive:
                log.warning("%s display is unavailable in text mode.  The "
                            "installation will continue in English.")
            else:
                ButtonChoiceWindow(self.screen, "Language Unavailable",
                                   "%s display is unavailable in text mode.  "
                                   "The installation will continue in "
                                   "English." % (instLang.getCurrent(),),
                                   buttons=[TEXT_OK_BUTTON])
        
	self.screen.helpCallback(self.helpWindow)

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

        parted.exception_set_handler(lambda exn: self.partedExceptionWindow(exn, anaconda))
        
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

                namespace = {'nextWindow' : None} 

		s = "from %s import %s; nextWindow = %s" % \
			(file, classNames[step], classNames[step])
		exec s in namespace

		win = namespace['nextWindow']()

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
                if anaconda.dispatch.canGoBack():
                    anaconda.dispatch.gotoPrev()
                else:
                    ButtonChoiceWindow(self.screen, _("Cancelled"),
                                       _("I can't go to the previous step "
                                         "from here. You will have to try "
                                         "again."),
                                       buttons=[_("OK")])
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
