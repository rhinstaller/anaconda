#
# text.py - text mode frontend to anaconda
#
# Erik Troan <ewt@redhat.com>
# Matt Wilson <msw@redhat.com>
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

from snack import *
import sys
import os
import iutil
import time
import gettext_rh
import signal
import parted
from translate import _, cat, N_
from language import expandLangs
from log import log
from flags import flags
from constants_text import *

stepToClasses = {
    "language" : ( "language_text", "LanguageWindow" ),
    "keyboard" : ( "keyboard_text", "KeyboardWindow" ),
    "mouse" : ( "mouse_text", ( "MouseWindow", "MouseDeviceWindow" ) ),
    "welcome" : ("welcome_text", "WelcomeWindow" ),
    "reconfigwelcome" : ("welcome_text", "ReconfigWelcomeWindow" ),
    "installtype" : ("installpath_text", "InstallPathWindow" ),
    "autopartition" : ("partition_text", "AutoPartitionWindow"),
    "custom-upgrade" : ("upgrade_text", "UpgradeExamineWindow" ),
    "addswap" : ("upgrade_text", "UpgradeSwapWindow" ),
    "fdisk" : ("fdisk_text", "fdiskPartitionWindow" ),
    "partitionmethod" : ("partmethod_text", ("PartitionMethod") ),
    "partition": ("partition_text", ("PartitionWindow") ),
    "findinstall" : ( "upgrade_text", "UpgradeExamineWindow" ),
    "addswap" : ( "upgrade_text", "UpgradeSwapWindow" ),
    "bootloader" : ("bootloader_text", ("BootloaderAppendWindow",
				  "BootloaderWindow",
				  "BootloaderImagesWindow" ) ),
    "network" : ("network_text", ( "NetworkWindow", "HostnameWindow" ) ),
    "firewall" : ( "firewall_text", "FirewallWindow" ),
    "languagesupport" : ( "language_text", ( "LanguageSupportWindow",
                                             "LanguageDefaultWindow") ),
    "timezone" : ( "timezone_text", "TimezoneWindow" ),
    "accounts" : ( "userauth_text", ( "RootPasswordWindow", "UsersWindow" ) ),
    "authentication" : ( "userauth_text", ( "AuthConfigWindow" ) ),
    "package-selection"  : ( "packages_text", "PackageGroupWindow" ),
    "indivpackage" : ("packages_text", ( "IndividualPackageWindow" ) ),
    "dependencies" : ( "packages_text", "PackageDepWindow" ),
    "videocard" : ( "xconfig_text", "XConfigWindowCard"),
    "monitor" : ( "xconfig_text", "MonitorWindow" ),
    "xcustom" : ( "xconfig_text", "XCustomWindow" ),
    "confirminstall" : ( "confirm_text", "BeginInstallWindow" ),
    "confirmupgrade" : ( "confirm_text", "BeginUpgradeWindow" ),
    "install" : ( "progress_text", "setupForInstall" ),
    "bootdisk" : ( "bootdisk_text", ( "BootDiskWindow",
                                      "MakeBootDiskWindow" ) ),
    "complete" : ( "complete_text", "FinishedWindow" ),
    "reconfigcomplete" : ( "complete_text", "ReconfigFinishedWindow" ),
}

stepToClasses["reconfigkeyboard"] = stepToClasses["keyboard"]

if iutil.getArch() == 'sparc':
    stepToClasses["bootloader"] = ( "silo_text", ( "SiloAppendWindow",
                                                   "SiloWindow"
                                                   "SiloImagesWindow" ) )
else:
    stepToClasses["bootloader"] = ( "bootloader_text", ( "BootloaderAppendWindow",
                                                   "BootloaderWindow",
                                                   "BootloaderImagesWindow") )



class InstallWindow:
    def __call__ (self, screen, todo):
        if todo.doInstall ():
            return INSTALL_BACK

        return INSTALL_OK

class WaitWindow:

    def pop(self):
	self.screen.popWindow()
	self.screen.refresh()

    def __init__(self, screen, title, text):
	self.screen = screen
	width = 40
	if (len(text) < width): width = len(text)

	t = TextboxReflowed(width, _(text))

	g = GridForm(self.screen, _(title), 1, 1)
	g.add(t, 0, 0)
	g.draw()
	self.screen.refresh()

class Flag:
    """a quick mutable boolean class"""
    def __init__(self, value = 0):
        self.flag = value

    def set(self, value):
        self.flag = value;

    def get(self):
        return self.flag

class OkCancelWindow:

    def getrc(self):
	return self.rc

    def __init__(self, screen, title, text):
	rc = ButtonChoiceWindow(screen, _(title), _(text),
			        buttons = [ TEXT_OK_BUTTON, _("Cancel") ])
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

    def set (self, amount):
        self.scale.set (amount)
	self.screen.refresh()

    def __init__(self, screen, title, text, total):
	self.screen = screen
	width = 55
	if (len(text) > width): width = len(text)

	t = TextboxReflowed(width, text)

	g = GridForm(self.screen, title, 1, 2)
	g.add(t, 0, 0, (0, 0, 0, 1), anchorLeft = 1)

        self.scale = Scale (width, total)
        g.add(self.scale, 0, 1)
                
	g.draw()
	self.screen.refresh()

class InstallInterface:
    def helpWindow(self, screen, key, firstTime = 1):
	try:
            f = None

	    # XXX
	    #
	    # HelpWindow can't get to the langauge

            for lang in self.langSearchPath:
                fn = "/usr/share/anaconda/help/%s/s1-help-screens-%s.txt" \
                     % (lang, key)
                try:
                    f = open (fn)
                except IOError, msg:
                    continue
                break
                    
# uncomment to test help text installed in local directory instead            
#	    fn = "./text-help/%s/s1-help-screens-%s.txt" \
#			% (lang, key)

            if not f:
		if firstTime:	
		    return self.helpWindow(screen, "helponhelp", firstTime = 0)
		else:
		    ButtonChoiceWindow(screen, _("Help not available"), 
				_("No help is available for this install."),
				       buttons = [ TEXT_OK_BUTTON ])
		    return None

	    l = f.readlines()
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

	    bb = ButtonBar(screen, [ TEXT_OK_BUTTON ] )
	    t = Textbox(width, height, stream, scroll = scroll)

	    g = GridFormHelp(screen, title, "helponhelp", 1, 2)
	    g.add(t, 0, 0, padding = (0, 0, 0, 1))
	    g.add(bb, 0, 1, growx = 1)

	    g.runOnce()
	except:
	    import traceback
	    (type, value, tb) = sys.exc_info()
	    from string import joinfields
	    list = traceback.format_exception (type, value, tb)
	    text = joinfields (list, "")
	    rc = self.exceptionWindow (_("Exception Occurred"), text)
	    if rc:
		import pdb
		pdb.post_mortem (tb)
	    os._exit (1)

    def progressWindow(self, title, text, total):
        return ProgressWindow (self.screen, _(title), _(text), total)

    def messageWindow(self, title, text, type = "ok"):
	if type == "ok":
	    ButtonChoiceWindow(self.screen, _(title), _(text),
			       buttons = [ TEXT_OK_BUTTON ])
        elif type == "yesno":
	    rc = ButtonChoiceWindow(self.screen, _(title), _(text),
			       buttons = [ TEXT_YES_BUTTON, TEXT_NO_BUTTON ])
            if rc == "yes":
                return 1
            else:
                return 0
	else:
	    return OkCancelWindow(self.screen, _(title), _(text))

    def dumpWindow(self):
	rc = ButtonChoiceWindow(self.screen, _("Save Crash Dump"),
	    _("Please insert a floppy now. All contents of the disk "
	      "will be erased, so please choose your diskette carefully."),
	    [ TEXT_OK_BUTTON, _("Cancel") ])

        if rc == string.lower (_("Cancel")):
	    return 1

	return 0
    
    def exceptionWindow(self, title, text):
	ugh = _("An internal error occurred in the installation program. "
		"Please report this error to Red Hat (through the "
		"bugzilla.redhat.com web site) as soon as possible. The "
		"information on this failure may be saved to a floppy disk, "
		"and will help Red Hat in fixing the problem.\n\n")

	rc = ButtonChoiceWindow(self.screen, title, ugh + text,
                           buttons = [ TEXT_OK_BUTTON, _("Save"), _("Debug") ])
        if rc == string.lower (_("Debug")):
            return 1
	elif rc == string.lower (_("Save")):
            return 2
        return None

    def partedExceptionWindow(self, exc):
        buttons = []
        buttonToAction = {}
        flags = ((parted.EXCEPTION_YES, N_("Yes")),
                 (parted.EXCEPTION_NO, N_("No")),
                 (parted.EXCEPTION_OK, N_("Ok")),
                 (parted.EXCEPTION_RETRY, N_("Retry")),
                 (parted.EXCEPTION_IGNORE, N_("Ignore")),
                 (parted.EXCEPTION_CANCEL, N_("Cancel")))
        for flag, string in flags:
            if exc.options & flag:
                buttons.append(_(string))
                buttonToAction[_(string)] = flag
        rc = ButtonChoiceWindow(self.screen, exc.type_string, exc.message,
                                buttons = buttons)
        return buttonToAction[rc]
    

    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def drawFrame(self):
        self.welcomeText = _("Red Hat Linux (C) 2001 Red Hat, Inc.")
        self.screen.drawRootText (0, 0, self.welcomeText)
	if (os.access("/usr/share/anaconda/help/C/s1-help-screens-lang.txt", os.R_OK)):
	    self.screen.pushHelpLine (_(" <F1> for help | <Tab> between elements | <Space> selects | <F12> next screen"))
	else:
	    self.screen.pushHelpLine (_("  <Tab>/<Alt-Tab> between elements   |  <Space> selects   |  <F12> next screen"))

    def shutdown(self):
	self.screen.finish()
	self.screen = None

    def __init__(self):
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	signal.signal(signal.SIGTSTP, signal.SIG_IGN)
	self.screen = None

    def __del__(self):
	if self.screen:
	    self.screen.finish()

    def run(self, id, dispatch):
        self.screen = SnackScreen()
	self.screen.helpCallback(self.helpWindow)
	self.drawFrame()

# uncomment this line to make the installer quit on <Ctrl+Z>
# handy for quick debugging.
#	self.screen.suspendCallback(killSelf, self.screen)
# uncomment this line to drop into the python debugger on <Ctrl+Z>
# --VERY handy--
	self.screen.suspendCallback(debugSelf, self.screen)

	if flags.serial:
	    self.screen.suspendCallback(spawnShell, self.screen)

	# clear out the old root text by writing spaces in the blank
	# area on the right side of the screen
	#self.screen.drawRootText (len(_(self.welcomeText)), 0,
		  #(self.screen.width - len(_(self.welcomeText))) * " ")
	#self.screen.drawRootText (0 - len(_(step[0])), 0, _(step[0]))

        lang = id.instLanguage.getCurrent()
        lang = id.instLanguage.getLangNick(lang)
        self.langSearchPath = expandLangs(lang) + ['C']

        id.fsset.registerMessageWindow(self.messageWindow)
        id.fsset.registerProgressWindow(self.progressWindow)
        parted.exception_set_handler(self.partedExceptionWindow)        
        
	lastrc = INSTALL_OK
	(step, args) = dispatch.currentStep()
	while step:
	    (file, classNames) = stepToClasses[step]

	    if type(classNames) != type(()):
		classNames = (classNames,)

	    if lastrc == INSTALL_OK:
		step = 0
	    else:
		step = len(classNames) - 1

	    while step >= 0 and step < len(classNames):
                nextWindow = None
		s = "from %s import %s; nextWindow = %s" % \
			(file, classNames[step], classNames[step])
		exec s

		win = nextWindow()

		#log("TUI running step %s (class %s, file %s)" % 
			    #(step, file, classNames))

		rc = apply(win, (self.screen, ) + args)

		if rc == INSTALL_NOOP:
		    rc = lastrc

		if rc == INSTALL_BACK:
		    step = step - 1
		elif rc == INSTALL_OK:
		    step = step + 1

		lastrc = rc

	    if step == -1:
                if not dispatch.canGoBack():
                    ButtonChoiceWindow(self.screen, _("Cancelled"),
                                       _("I can't go to the previous step "
                                         "from here. You will have to try "
                                         "again."),
                                       buttons = [ _("OK") ])
		dispatch.gotoPrev()
	    else:
		dispatch.gotoNext()

	    (step, args) = dispatch.currentStep()

        self.screen.finish ()

def killSelf(screen):
    screen.finish()
    os._exit(0)

def debugSelf(screen):
    screen.suspend ()
    import pdb
    try:
        pdb.set_trace()
    except:
        sys.exit(-1)
    screen.resume ()

def spawnShell(screen):
    screen.suspend ()
    print "\n\nType <exit> to return to the install program.\n"
    iutil.execWithRedirect ("/bin/sh", ["-/bin/sh"])
    time.sleep(5)
    screen.resume ()
