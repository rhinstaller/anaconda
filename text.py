#
# text.py - text mode frontend to anaconda
#
# Erik Troan <ewt@redhat.com>
# Matt Wilson <msw@redhat.com>
#
# Copyright 1999-2004 Red Hat, Inc.
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

from rhpl.log import log
from rhpl.translate import _, cat, N_

stepToClasses = {
    "language" : ("language_text", "LanguageWindow"),
    "keyboard" : ("keyboard_text", "KeyboardWindow"),
    "mouse" : ("mouse_text", ("MouseWindow", "MouseDeviceWindow")),
    "welcome" : ("welcome_text", "WelcomeWindow"),
    "installtype" : ("installpath_text", "InstallPathWindow"),
    "autopartition" : ("partition_text", "AutoPartitionWindow"),
    "custom-upgrade" : ("upgrade_text", "UpgradeExamineWindow"),
    "addswap" : ("upgrade_text", "UpgradeSwapWindow"),
    "upgrademigratefs" : ("upgrade_text", "UpgradeMigrateFSWindow"),
    "fdisk" : ("fdisk_text", "fdiskPartitionWindow"),
    "partitionmethod" : ("partmethod_text", ("PartitionMethod")),
    "partition": ("partition_text", ("PartitionWindow")),
    "zfcpconfig": ("zfcp_text", ("ZFCPWindow")),
    "findinstall" : ("upgrade_text", ("UpgradeExamineWindow")),
# replace with below if you want customize screen
#    "findinstall" : ("upgrade_text", ("UpgradeExamineWindow",
#                                      "CustomizeUpgradeWindow")),
    "addswap" : ("upgrade_text", "UpgradeSwapWindow"),
    "upgbootloader": ("upgrade_bootloader_text", "UpgradeBootloaderWindow"),
    "bootloader" : ("bootloader_text", ("BootloaderChoiceWindow",
                                        "BootloaderAppendWindow",
                                        "BootloaderPasswordWindow")),
    "bootloaderadvanced" : ("bootloader_text", ("BootloaderImagesWindow",
                                                "BootloaderLocationWindow")),
    "network" : ("network_text", ("NetworkDeviceWindow", "NetworkGlobalWindow",
                                  "HostnameWindow")),
    "firewall" : ("firewall_text", ("FirewallWindow",
                                    "SELinuxWindow")),
    "languagesupport" : ("language_text", ("LanguageSupportWindow",
                                           "LanguageDefaultWindow")),
    "timezone" : ("timezone_text", "TimezoneWindow"),
    "accounts" : ("userauth_text", "RootPasswordWindow"),
    "authentication" : ("userauth_text", ("AuthConfigWindow")),
    "desktopchoice": ("desktop_choice_text", "DesktopChoiceWindow"),
    "package-selection"  : ("packages_text", "PackageGroupWindow"),
    "indivpackage" : ("packages_text", ("IndividualPackageWindow")),
    "dependencies" : ("packages_text", "PackageDepWindow"),
    "videocard" : ("xconfig_text", "XConfigWindowCard"),
    "monitor" : ("xconfig_text", "MonitorWindow"),
    "xcustom" : ("xconfig_text", "XCustomWindow"),
    "confirminstall" : ("confirm_text", "BeginInstallWindow"),
    "confirmupgrade" : ("confirm_text", "BeginUpgradeWindow"),
    "install" : ("progress_text", "setupForInstall"),
    "bootdisk" : ("bootdisk_text", ("BootDiskWindow")),
    "complete" : ("complete_text", "FinishedWindow"),
}

if iutil.getArch() == 'sparc':
    stepToClasses["bootloader"] = ("silo_text", ("SiloAppendWindow",
                                                 "SiloWindow"
                                                 "SiloImagesWindow"))
if iutil.getArch() == 's390':
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
        self.scale.set(amount)
	self.screen.refresh()

    def __init__(self, screen, title, text, total):
	self.screen = screen
	width = 55
	if (len(text) > width): width = len(text)

	t = TextboxReflowed(width, text)

	g = GridForm(self.screen, title, 1, 2)
	g.add(t, 0, 0, (0, 0, 0, 1), anchorLeft=1)

        self.scale = Scale(width, total)
        g.add(self.scale, 0, 1)
                
	g.draw()
	self.screen.refresh()

class InstallInterface:
    def helpWindow(self, screen, key):
        lang = self.instLanguage.getCurrent()
        lang = self.instLanguage.getLangNick(lang)
        self.langSearchPath = expandLangs(lang) + ['C']

        if key == "helponhelp":
            if self.showingHelpOnHelp:
                return None
            else:
                self.showingHelpOnHelp = 1
	try:
            f = None

            if self.configFileData.has_key("helptag"):
                helpTag = "-%s" % (self.configFileData["helptag"],)
            else:
                helpTag = ""
            arch = "-%s" % (iutil.getArch(),)
            tags = [ "%s%s" % (helpTag, arch), "%s" % (helpTag,),
                     "%s" % (arch,), "" ]

	    # XXX
	    #
	    # HelpWindow can't get to the langauge

            found = 0
            for path in ("./text-", "/mnt/source/RHupdates/",
                         "/usr/share/anaconda/"):
                if found:
                    break
                for lang in self.langSearchPath:
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
	    rc = self.exceptionWindow(_("Exception Occurred"), text)
	    if rc:
		import pdb
		pdb.post_mortem(tb)
	    os._exit(1)

    def progressWindow(self, title, text, total):
        return ProgressWindow(self.screen, title, text, total)

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
		    return idx != 0
		idx = idx + 1
	    return 0
	else:
	    return OkCancelWindow(self.screen, title, text)

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
    
    def exceptionWindow(self, title, text):
        try:
            floppyDevices = 0
            for dev in kudzu.probe(kudzu.CLASS_FLOPPY, kudzu.BUS_UNSPEC,
                                   kudzu.PROBE_ALL):
                if not dev.detached:
                    floppyDevices = floppyDevices + 1
        except:
            floppyDevices = 0
        if floppyDevices > 0 or DEBUG:
            ugh = "%s\n\n" % (exceptionText,)
            buttons=[TEXT_OK_BUTTON, _("Save"), _("Debug")]
        else:
            ugh = "%s\n\n" % (exceptionTextNoFloppy,)
            buttons=[TEXT_OK_BUTTON, _("Debug")]

	rc = ButtonChoiceWindow(self.screen, title, ugh + text, buttons)
        if rc == string.lower(_("Debug")):
            return 1
	elif rc == string.lower(_("Save")):
            return 2
        return None

    def partedExceptionWindow(self, exc):
        # if our only option is to cancel, let us handle the exception
        # in our code and avoid popping up the exception window here.
        if exc.options == parted.EXCEPTION_CANCEL:
            return parted.EXCEPTION_UNHANDLED
        log("parted exception: %s: %s" %(exc.type_string,exc.message))
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

    def drawFrame(self):
        self.welcomeText = _("%s (C) 2004 Red Hat, Inc.") % (productName,)
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

    def __init__(self):
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	signal.signal(signal.SIGTSTP, signal.SIG_IGN)
	self.screen = None
        self.showingHelpOnHelp = 0

    def __del__(self):
	if self.screen:
	    self.screen.finish()

    def run(self, id, dispatch, configFileData):
        # set up for CJK text mode if needed
        oldlang = None
        if (flags.setupFilesystems and
            (id.instLanguage.getFontFile(id.instLanguage.getCurrent()) == "bterm")
            and not flags.serial and not flags.virtpconsole
            and not isys.isPsudoTTY(0) and not isys.isVioConsole() and
            not os.path.exists("/proc/xen")):
            log("starting bterm")
            rc = 1
            try:
                rc = isys.startBterm()
                time.sleep(1)
            except Exception, e:
                log("got an exception starting bterm: %s" %(e,))

            if rc == 1:
                log("unable to start bterm, falling back to english")
                oldlang = id.instLanguage.getCurrent()
                log("old language was %s" %(oldlang,))
                id.instLanguage.setRuntimeLanguage("English")
                id.instLanguage.setRuntimeDefaults(oldlang)

        if id.instLanguage.getFontFile(id.instLanguage.getCurrent()) == "none":
            oldlang = id.instLanguage.getCurrent()
            id.instLanguage.setRuntimeLanguage("English")
            id.instLanguage.setRuntimeDefaults(oldlang)
        
        self.screen = SnackScreen()
        self.configFileData = configFileData
	self.screen.helpCallback(self.helpWindow)

# uncomment this line to make the installer quit on <Ctrl+Z>
# handy for quick debugging.
#	self.screen.suspendCallback(killSelf, self.screen)
# uncomment this line to drop into the python debugger on <Ctrl+Z>
# --VERY handy--
        if DEBUG or flags.test:
            self.screen.suspendCallback(debugSelf, self.screen)

	if flags.serial or flags.virtpconsole or isys.isPsudoTTY(0) or isys.isVioConsole() or os.path.exists("/proc/xen"):
	    self.screen.suspendCallback(spawnShell, self.screen)

	# clear out the old root text by writing spaces in the blank
	# area on the right side of the screen
	#self.screen.drawRootText (len(_(self.welcomeText)), 0,
		  #(self.screen.width - len(_(self.welcomeText))) * " ")
	#self.screen.drawRootText (0 - len(_(step[0])), 0, _(step[0]))
        langname = id.instLanguage.getCurrent()
        lang = id.instLanguage.getLangNick(langname)

        self.langSearchPath = expandLangs(lang) + ['C']
        self.instLanguage = id.instLanguage

        # draw the frame after setting up the fallback
        self.drawFrame()

        # draw the frame after setting up the fallback
        self.drawFrame()

        if oldlang is not None:
            ButtonChoiceWindow(self.screen, "Language Unavailable",
                               "%s display is unavailable in text mode.  "
                               "The installation will continue in "
                               "English." % (oldlang,),
                               buttons=[TEXT_OK_BUTTON])
        

        id.fsset.registerMessageWindow(self.messageWindow)
        id.fsset.registerProgressWindow(self.progressWindow)
        id.fsset.registerWaitWindow(self.waitWindow)        
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
                # reget the args.  they could change (especially direction)
                (foo, args) = dispatch.currentStep()

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
                    dispatch.dir = DISPATCH_BACK
		elif rc == INSTALL_OK:
		    step = step + 1
                    dispatch.dir = DISPATCH_FORWARD

		lastrc = rc

	    if step == -1:
                if not dispatch.canGoBack():
                    ButtonChoiceWindow(self.screen, _("Cancelled"),
                                       _("I can't go to the previous step "
                                         "from here. You will have to try "
                                         "again."),
                                       buttons=[_("OK")])
		dispatch.gotoPrev()
	    else:
		dispatch.gotoNext()

	    (step, args) = dispatch.currentStep()

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
        iutil.execWithRedirect("/bin/sh", ["-/bin/sh"])
    else:
        print "Unable to find /bin/sh to execute!  Not starting shell"
    time.sleep(5)
    screen.resume()
