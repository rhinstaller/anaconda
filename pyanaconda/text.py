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
import traceback
import signal
import parted
import product
import string
from flags import flags
from textw.constants_text import *
from constants import *
from network import hasActiveNetDev, getDevices
from installinterfacebase import InstallInterfaceBase
import imp
import textw

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

import logging
log = logging.getLogger("anaconda")

stepToClasses = {
    "language" : ("language_text", "LanguageWindow"),
    "keyboard" : ("keyboard_text", "KeyboardWindow"),
    "parttype" : ("partition_text", "PartitionTypeWindow"),
    "upgrademigratefs" : ("upgrade_text", "UpgradeMigrateFSWindow"),
    "findinstall" : ("upgrade_text", "UpgradeExamineWindow"),
    "upgbootloader": ("upgrade_bootloader_text", "UpgradeBootloaderWindow"),
    "network" : ("network_text", "HostnameWindow"),
    "timezone" : ("timezone_text", "TimezoneWindow"),
    "accounts" : ("userauth_text", "RootPasswordWindow"),
    "tasksel": ("task_text", "TaskWindow"),
    "install" : ("progress_text", "setupForInstall"),
    "complete" : ("complete_text", "FinishedWindow"),
    "bootloader" : ("zipl_text", ( "ZiplWindow"))
}

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
        toplevel = GridForm(self.screen, _("Passphrase"), 1, 3)

        txt = TextboxReflowed(65, self.txt)
        toplevel.add(txt, 0, 0)

        passphraseentry = Entry(60, password = 1)
        toplevel.add(passphraseentry, 0, 1, (0,0,0,1))

        buttons = ButtonBar(self.screen, [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        toplevel.add(buttons, 0, 2, growx=1)

        rc = toplevel.run()
        res = buttons.buttonPressed(rc)

        passphrase = None
        if res == TEXT_OK_CHECK or rc == "F12":
            passphrase = passphraseentry.value().strip()

        self.rc = passphrase
        return self.rc

    def pop(self):
        self.screen.popWindow()

class InstallInterface(InstallInterfaceBase):
    def progressWindow(self, title, text, total, updpct = 0.05, pulse = False):
        return ProgressWindow(self.screen, title, text, total, updpct, pulse)

    def reinitializeWindow(self, title, path, size, description):
        grid = GridForm(self.screen, title, 1, 3)
        text = TEXT_REINITIALIZE % {"description": description, "size": size, "devicePath": path}
        grid.add(TextboxReflowed(70, text), 0, 0)

        all_devices_cb = Checkbox(TEXT_REINITIALIZE_ALL, isOn=False)
        grid.add(all_devices_cb, 0, 1, padding=(0, 1, 0, 0))

        buttons = [(_("Yes, discard any data"), "yes"),
                   (_("No, keep any data"), "no")]
        grid.buttons = ButtonBar(self.screen, buttons)
        grid.add(grid.buttons, 0, 2, padding=(0, 1, 0, 0))

        result = grid.run()
        button_check = grid.buttons.buttonPressed(result)
        self.screen.popWindow()
        rc = 2 if button_check == "yes" else 0
        if all_devices_cb.selected():
            rc += 1
        return rc

    def setInstallProgressClass(self, c):
        self.instProgress = c

    def exitWindow(self, title, text):
        return self.messageWindow(title, text, type="custom",
                                  custom_buttons=[_("Exit installer")])

    def messageWindow(self, title, text, type="ok", default = None,
		      custom_icon=None, custom_buttons=[]):
        text = str(text)
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
                              custom_buttons=[], expanded=False):
        t = TextboxReflowed(60, text, maxHeight=8)
        
        # if it is a string, just print it as it is (#674322)
        if isinstance(longText, basestring):
            lt = Textbox(60, 6, longText, scroll=1, wrap=1)
        # if the argument is anything else we have to join it together (#654074)
        else:
            lt = Textbox(60, 6, "\n".join(longText), scroll=1, wrap=1)
            
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

    def editRepoWindow(self, repoObj):
        self.messageWindow(_("Error"),
                           _("Repository editing is not available in text mode."))

    def getLuksPassphrase(self, passphrase = "", preexist = False):
        w = LuksPassphraseWindow(self.screen, passphrase = passphrase,
                                 preexist = preexist)
        rc = w.run()
        w.pop()
        return rc

    def passphraseEntryWindow(self, device):
        w = PassphraseEntryWindow(self.screen, device)
        passphrase = w.run()
        w.pop()
        return passphrase

    def enableNetwork(self):
        if len(getDevices) == 0:
            return False
        from textw.netconfig_text import NetworkConfiguratorText
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

    def saveExceptionWindow(self, accountManager, signature, *args, **kwargs):
        from meh.ui.text import SaveExceptionWindow
        import urlgrabber

        if not hasActiveNetDev():
            if self.messageWindow(_("Warning"), 
                   _("You do not have an active network connection.  This is "
                     "required by some exception saving methods.  Would you "
                     "like to configure your network now?"),
                   type = "yesno"):

                if not self.enableNetwork():
                    self.messageWindow(_("No Network Available"),
                                       _("Remote exception saving methods will not work."))
                else:
                    urlgrabber.grabber.reset_curl_obj()

        win = SaveExceptionWindow (accountManager, signature, screen=self.screen,
                                   *args, **kwargs)
        win.run()

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

    def run(self, anaconda):
        self.anaconda = anaconda

	if not self.isRealConsole():
	    self.screen.suspendCallback(spawnShell, self.screen)

        # drop into the python debugger on ctrl-z if we're running in test mode
        if flags.debug:
            self.screen.suspendCallback(debugSelf, self.screen)

        # draw the frame after setting up the fallback
        self.drawFrame()
        # and now descend into the dispatcher
        self.anaconda.dispatch.dispatch()

    def display_step(self, step):
        (file, className) = stepToClasses[step]
        while True:
            try:
                found = imp.find_module(file, textw.__path__)
                moduleName = 'pyanaconda.textw.%s' % file
                loaded = imp.load_module(moduleName, *found)
                nextWindow = loaded.__dict__[className]
                break
            except ImportError as e:
                log.error("loading interface component %s" % className)
                log.error(traceback.format_exc())
                rc = ButtonChoiceWindow(self.screen, _("Error!"),
                                  _("An error occurred when attempting "
                                    "to load an installer interface "
                                    "component.\n\nclassName = %s")
                                  % className,
                                  buttons=[_("Exit"), _("Retry")])

                if rc == string.lower(_("Exit")):
                    sys.exit(0)
        win = nextWindow()

        while True:
            rc = win(self.screen, self.anaconda)
            if rc == INSTALL_OK:
                return DISPATCH_FORWARD
            elif rc == INSTALL_NOOP:
                return DISPATCH_DEFAULT
            elif rc == INSTALL_BACK:
                if self.anaconda.dispatch.can_go_back():
                    return DISPATCH_BACK
                else:
                    ButtonChoiceWindow(self.screen, _("Cancelled"),
                                       _("I can't go to the previous step "
                                         "from here. You will have to try "
                                         "again."),
                                       buttons=[_("OK")])
                    # keep displaying the same dialog until the user gives us
                    # a better answer
                    continue

    def unsupported_steps(self):
        l = ["cleardiskssel", "filtertype", "filter", "group-selection",
             "partition"]
        if not iutil.isS390():
            l.append("bootloader")
        return l

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
