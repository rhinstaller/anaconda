from snack import *
import sys
import isys
import os
import stat
import iutil
import rpm
import time
import gettext_rh
import signal
import installclass
from translate import _, cat, N_
from log import log

from constants_text import *
from lilo_text import LiloWindow
from lilo_text import LiloAppendWindow
from lilo_text import LiloImagesWindow
from silo_text import SiloWindow
from silo_text import SiloAppendWindow
from silo_text import SiloImagesWindow
from network_text import NetworkWindow
from network_text import HostnameWindow
from userauth_text import RootPasswordWindow
from userauth_text import UsersWindow
from userauth_text import AuthConfigWindow
from partitioning_text import PartitionMethod
from partitioning_text import LoopSizeWindow
from partitioning_text import ManualPartitionWindow
from partitioning_text import AutoPartitionWindow
from partitioning_text import PartitionWindow
from partitioning_text import TurnOnSwapWindow
from partitioning_text import FormatWindow
from partitioning_text import LBA32WarningWindow
from packages_text import PackageGroupWindow
from packages_text import IndividualPackageWindow
from packages_text import PackageDepWindow
from timezone_text import TimezoneWindow
from bootdisk_text import BootDiskWindow
from bootdisk_text import MakeBootDiskWindow
from mouse_text import MouseWindow, MouseDeviceWindow
from firewall_text import FirewallWindow

import installclass

class LanguageWindow:
    def __call__(self, screen, todo, textInterface):
        languages = todo.language.available ()

        haveKon = os.access ("/sbin/continue", os.X_OK)
        if languages.has_key ("Japanese") and not haveKon:
            del languages["Japanese"]

        descriptions = languages.keys ()
        descriptions.sort ()
        current = todo.language.get ()

        for lang in descriptions:
            if languages[lang] == current:
                default = descriptions.index (lang)
            
        height = min((screen.height - 16, len(descriptions)))
        if todo.reconfigOnly:
            buttons = [_("Ok"), _("Back")]
        else:
            buttons = [_("Ok")]

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Language Selection"),
			_("What language would you like to use during the "
			  "installation process?"), descriptions, 
			buttons, width = 30, default = default, scroll = 1,
                                height = height, help = "lang")

	if (button == string.lower(_("Back"))): return INSTALL_BACK

        choice = descriptions[choice]
        lang = languages [choice]
        
        if (todo.setupFilesystems
            and lang[:2] == "ja" and not isys.isPsudoTTY(0)):
            # we're not running KON yet, lets fire it up
            os.environ["ANACONDAARGS"] = (os.environ["ANACONDAARGS"] +
                                          " --lang ja_JP.eucJP")
            os.environ["TERM"] = "kon"
            os.environ["LANG"] = "ja_JP.eucJP"
            os.environ["LC_ALL"] = "ja_JP.eucJP"
            os.environ["LC_NUMERIC"] = "C"
            if os.access("/tmp/updates/anaconda", os.X_OK):
                prog = "/tmp/updates/anaconda"
            else:
                prog = "/usr/bin/anaconda"
            args = [ "kon", "-e", prog ]
            screen.finish()
            os.execv ("/sbin/loader", args)

        os.environ["LC_ALL"] = lang
        os.environ["LANG"] = lang
        newlangs = [lang]
	if len(lang) > 2:
            newlangs.append(lang[:2])
        cat.setlangs (newlangs)
        todo.language.set (choice)
                
	if not todo.serial:
	    map = todo.language.getFontMap(choice)
	    font = todo.language.getFontFile(choice)
	    if map != "None":
		if os.access("/bin/consolechars", os.X_OK):
		    iutil.execWithRedirect ("/bin/consolechars",
					["/bin/consolechars", "-f", font, "-m", map])
		else:
		    try:
			isys.loadFont(map)
		    except SystemError, (errno, msg):
			log("Could not load font %s: %s" % (font, msg))
	    elif os.access("/bin/consolechars", os.X_OK):
		# test and reconfig
		iutil.execWithRedirect ("/bin/consolechars", 
			["/bin/consolechars", "-d", "-m", "iso01"])

	textInterface.drawFrame()
	    
        return INSTALL_OK

class LanguageSupportWindow:
    def __call__(self, screen, todo):

        languages = todo.language.available ()
        descriptions = languages.keys ()
        descriptions.sort ()
        current = todo.language.get ()

        langs = todo.language.getSupported ()
#        print langs
#        time.sleep(2)

        ct = CheckboxTree(height = 8, scroll = 1)


        for lang in descriptions:
            if languages[lang] == current:
                ct.append(lang, lang, 1)
            else:
                ct.append(lang, lang, 0)

        if langs != None:
            for lang in langs:
                ct.setEntryValue(lang, 1)

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        message = (_("Choose the languages to be installed:"))
        width = len(message)
        tb = Textbox (width, 2, message)


        g = GridFormHelp (screen, _("Language Support"), "langsupport", 1, 4)

        g.add (tb, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        g.add (ct, 0, 1, (0, 0, 0, 1))
        g.add (bb, 0, 3, growx = 1)

        result = g.runOnce()

        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK

        #--If they selected all langs, then set todo.language.setSupported to None.  This installs all langs
        if todo.language.getSupported () == descriptions:
            todo.language.setSupported (None)
        else:
            todo.language.setSupported (ct.getSelection())

        return INSTALL_OK


class LanguageDefaultWindow:
    def __call__(self,screen, todo):
        languages = todo.language.available ()
        langs = todo.language.getSupported ()

        if len(langs) <= 1:
            return

        descriptions = languages.keys ()
        descriptions.sort ()
        current = todo.language.get ()

        found = 0
        for lang in langs:
            if languages[lang] == current:
                default = langs.index (lang)
                found = 1
            else:
                if found == 0:
                    default = langs[0]
                
        height = min((screen.height - 16, len(langs)))
        
        buttons = [_("Ok"), _("Back")]

        (button, choice) = ListboxChoiceWindow(screen, _("Default Language"),
			_("Choose the default language: "), langs, 
			buttons, width = 30, default = default, scroll = 1,
                                               height = height, help = "langdefault")

	if (button == string.lower(_("Back"))): return INSTALL_BACK


        choice = langs[choice]
        todo.language.set (choice)
        return INSTALL_OK


class KeyboardWindow:
    beenRun = 0

    def __call__(self, screen, todo):
	if todo.serial:
	    return INSTALL_NOOP
        keyboards = todo.keyboard.available ()
        keyboards.sort ()

	if self.beenRun:
	    default = todo.keyboard.get ()
	else:
            default = iutil.defaultKeyboard(todo.language.get())

        try:
            default = keyboards.index (default)
        except ValueError:
            default = keyboards.index ("us")

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Keyboard Selection"),
                                _("Which model keyboard is attached to this computer?"), keyboards, 
                                buttons = [_("OK"), _("Back")], width = 30, scroll = 1, height = 8,
                                default = default, help = "kybd")
        
        if button == string.lower (_("Back")):
            return INSTALL_BACK

        todo.keyboard.set (keyboards[choice])
	self.beenRun = 1

	if not todo.serial:
            if todo.reconfigOnly:
                iutil.execWithRedirect ("/bin/loadkeys",
                                        ["/bin/loadkeys", keyboards[choice]],
					stderr = "/dev/null")
            else:
                try:
                    isys.loadKeymap(keyboards[choice])
                except SystemError, (errno, msg):
		    log("Could not install keymap %s: %s" % (keyboards[choice], msg))
        return INSTALL_OK
    
class InstallPathWindow:
    def __call__ (self, screen, todo, intf):
	from fstab import NewtFstab

        # see if kickstart specified install type
	showScreen = 1
	if (todo.instClass.installType == "install"):
            intf.steps = intf.commonSteps + intf.installSteps
            todo.upgrade = 0
	    showScreen = 0
	elif (todo.instClass.installType == "upgrade"):
            intf.steps = intf.commonSteps + intf.upgradeSteps
            todo.upgrade = 1
	    showScreen = 0

        # this is (probably) the first place todo.fstab gets created
        if not showScreen:
	    todo.fstab = NewtFstab(todo.setupFilesystems, 
                                   todo.serial, todo.zeroMbr, 0,
                                   todo.intf.waitWindow,
                                   todo.intf.messageWindow,
                                   todo.intf.progressWindow,
                                   not todo.expert,
                                   todo.method.protectedPartitions(),
                                   todo.expert, todo.upgrade)
	    return INSTALL_NOOP

	classes = installclass.availableClasses()

	choices = []
	for (name, object, icon) in classes:
	    choices.append(_(name))
	upgradeChoice = len(choices)
	choices.append(_("Upgrade Existing Installation"))

	if (todo.upgrade):
	    default = upgradeChoice
	    orig = None
	else:
	    instClass = todo.getClass()
	    orig = None
	    default = 0
	    i = 0
	    for (name, object, icon) in classes:
		if isinstance(instClass, object):
		    orig = i
		    break
		elif object.default:
		    default = i
		    
		i = i + 1

	    if (orig):
		default = orig

	(button, choice) = ListboxChoiceWindow(screen, _("Installation Type"),
			_("What type of system would you like to install?"),
			    choices, [(_("OK"), "ok"), (_("Back"), "back")],
			    width = 40, default = default, help = "installpath")

        if button == "back":
            return INSTALL_BACK

	needNewDruid = 0

	if (choice == upgradeChoice):
            intf.steps = intf.commonSteps + intf.upgradeSteps
            todo.upgrade = 1
        else:
            intf.steps = intf.commonSteps + intf.installSteps
            todo.upgrade = 0
	    if (choice != orig):
		(name, objectClass, logo) = classes[choice]
		todo.setClass(objectClass(todo.expert))
		needNewDruid = 1

	if needNewDruid or not todo.fstab:
	    todo.fstab = NewtFstab(todo.setupFilesystems, 
                                   todo.serial, 0, 0,
                                   todo.intf.waitWindow,
                                   todo.intf.messageWindow,
                                   todo.intf.progressWindow,
                                   not todo.expert,
                                   todo.method.protectedPartitions(),
                                   todo.expert, todo.upgrade)

        return INSTALL_OK

class UpgradeExamineWindow:
    def __call__ (self, dir, screen, todo):
	if dir == -1:
	    # Hack to let backing out of upgrades work properly
	    from fstab import NewtFstab
	    if todo.fstab:
		todo.fstab.turnOffSwap()
	    todo.fstab = NewtFstab(todo.setupFilesystems, 
                                   todo.serial, 0, 0,
                                   todo.intf.waitWindow,
                                   todo.intf.messageWindow,
                                   todo.intf.progressWindow,
                                   not todo.expert,
                                   todo.method.protectedPartitions(),
                                   todo.expert, 1)

	    return INSTALL_NOOP

        parts = todo.upgradeFindRoot ()

        if not parts:
            ButtonChoiceWindow(screen, _("Error"),
                               _("You don't have any Linux partitions. You "
                                 "can't upgrade this system!"),
                               [ _("Back") ], width = 50)
            return INSTALL_BACK
        
        if len (parts) > 1:
            height = min (len (parts), 12)
            if height == 12:
                scroll = 1
            else:
                scroll = 0

	    partList = []
	    for (drive, fs) in parts:
		partList.append(drive)

            (button, choice) = \
                ListboxChoiceWindow(screen, _("System to Upgrade"),
                                    _("What partition holds the root partition "
                                      "of your installation?"), partList, 
                                    [ _("OK"), _("Back") ], width = 30,
                                    scroll = scroll, height = height,
				    help = "multipleroot")
            if button == string.lower (_("Back")):
                return INSTALL_BACK
            else:
                root = parts[choice]
        else:
            root = parts[0]

        todo.upgradeFindPackages (root)

class CustomizeUpgradeWindow:
    def __call__ (self, screen, todo, indiv):
        rc = ButtonChoiceWindow (screen, _("Customize Packages to Upgrade"),
                                 _("The packages you have installed, "
                                   "and any other packages which are "
                                   "needed to satisfy their "
                                   "dependencies, have been selected "
                                   "for installation. Would you like "
                                   "to customize the set of packages "
                                   "that will be upgraded?"),
                                 buttons = [ _("Yes"), _("No"), _("Back") ],
				help = "custupgrade")

        if rc == string.lower (_("Back")):
            return INSTALL_BACK

        if rc == string.lower (_("No")):
            indiv.set (0)
        else:
            indiv.set (1)

        return INSTALL_OK


class WelcomeWindow:
    def __call__(self, screen):
        rc = ButtonChoiceWindow(screen, _("Red Hat Linux"), 
                                _("Welcome to Red Hat Linux!\n\n"
                                  "This installation process is outlined in detail in the "
                                  "Official Red Hat Linux Installation Guide available from "
                                  "Red Hat Software. If you have access to this manual, you "
                                  "should read the installation section before continuing.\n\n"
                                  "If you have purchased Official Red Hat Linux, be sure to "
                                  "register your purchase through our web site, "
                                  "http://www.redhat.com/."),
                                buttons = [_("OK"), _("Back")], width = 50,
				help = "welcome")

	if rc == string.lower(_("Back")):
	    return INSTALL_BACK

        return INSTALL_OK

class ReconfigWelcomeWindow:
    def __call__(self, screen):
        rc = ButtonChoiceWindow(screen, _("Red Hat Linux"), 
                                _("Welcome to the Red Hat Linux!\n\n"
                                  "You have entered reconfiguration mode, "
                                  "which will allow you to configure "
                                  "site-specific options of your computer."
                                  "\n\n"
                                  "To exit without changing your setup "
                                  "select the ""Cancel"" button below."),
                                buttons = [_("OK"), _("Cancel")], width = 50,
				help = "reconfigwelcome")

	if rc == string.lower(_("Cancel")):
            screen.finish()
	    os._exit(0)

        return INSTALL_OK

class XConfigWindow:
    def __call__(self, screen, todo):
        #
        # if in reconfigOnly mode we query existing rpm db
        # if X not installed, just skip this step
        #
        if todo.reconfigOnly:
#            import rpm
#            db = rpm.opendb()
#            rc = db.findbyname ("XFree86")
#            if len(rc) == 0:
#                return None

#
#       for now ignore request to configure X11 in reconfig mode
#
            return None
        
        else:
            # we need to get the package list here for things like
            # workstation install - which will not have read the
            # package list yet.
            todo.getCompsList ()

            if not todo.hdList.packages.has_key('XFree86') or \
               not todo.hdList.packages['XFree86'].selected:
                return None

        todo.x.probe (probeMonitor = 0)
#        todo.x.server = None  #-hack
        if todo.x.server:
            rc = ButtonChoiceWindow (screen, _("X probe results"),
                                     todo.x.probeReport (),
                                     buttons = [ _("OK"), _("Back") ],
                                     help = 'xprobe')
        
            if rc == string.lower (_("Back")):
                return INSTALL_BACK

	    todo._cardindex = -1
            return INSTALL_OK

	if todo.serial:
	    # if doing serial installation and no card was probed,
	    # assume no card is present (typical case).
	    return INSTALL_NOOP

	# if we didn't find a server, we need the user to choose...
	carddb = todo.x.cards()
	cards = carddb.keys ()
	cards.sort ()
	cards.append (_("Unlisted Card"))

	servers = [ "Mono", "VGA16", "SVGA", "S3", "Mach32", "Mach8", "8514", "P9000", "AGX",
		    "W32", "W32", "Mach64", "I128", "S3V", "3DLabs" ]

	rc = INSTALL_NOOP
	while rc != INSTALL_OK:
	    (rc, choice) = ListboxChoiceWindow(screen, _("Video Card Selection"),
					       _("Which video card do you have?"),
					       cards,
					       buttons = [_("OK"), _("Back")],
					       width = 70, scroll = 1,
					       height = screen.height - 14,
					       help = "videocard")
	    if rc == string.lower (_("Back")):
		return INSTALL_BACK

	    todo._cardindex = -1

	    if cards[choice] == _("Unlisted Card"):
		(rc , choice) = \
		    ListboxChoiceWindow(screen, _("X Server Selection"), _("Choose a server"),
					servers,
					buttons = [ (_("Ok"), "ok"), (_("Back"), "back") ],
					scroll = 1,
					height = screen.height - 14,
					help = "xserver")

		if (rc == "back"):
		    rc = INSTALL_BACK
		else:
		    rc = INSTALL_OK
		    server = "XF86_" + servers[choice]
	    else:
		todo._cardindex = choice
		rc = INSTALL_OK

	if server:
	    todo.x.setVidcard ( { "NAME" : "Generic " + server,
				  "SERVER" : server } )
	else:
	    card = carddb[cards[choice]]

            depth = 0
            while depth < 16 and card.has_key ("SEE"):
                card = carddb[card["SEE"]]
                depth = depth + 1

	    todo.x.setVidcard (card)
	
	return INSTALL_OK


class XconfiguratorWindow:
    def __call__ (self, screen, todo):
        if not todo.x.server: return INSTALL_NOOP

	# if serial install, we can't run it.
	if todo.serial:
	    todo.x.skip = 1
	    return INSTALL_NOOP

        # if Xconfigurator isn't installed, we can't run it.
        if not os.access (todo.instPath + '/usr/X11R6/bin/Xconfigurator',
                          os.X_OK):
            log("Could not find Xconfigurator, skipping X configuration.")
            return INSTALL_NOOP

        f = open (todo.instPath + "/tmp/SERVER", "w")
	if todo._cardindex == -1:
	    f.write ("%d\n" % todo._cardindex)
	else:
	    f.write ("%s %d\n" % (todo.x.server, todo._cardindex))
        f.close ()

	args = ["xconfigurator", "--continue"]
	if todo.expert:
	    args = args + [ '--noddcprobe' ]

        screen.suspend ()
        iutil.execWithRedirect ("/usr/X11R6/bin/Xconfigurator", args,
                                root = todo.instPath)
        screen.resume ()
	todo.x.skip = 1
        return INSTALL_NOOP
        
class BeginInstallWindow:
    def __call__ (self, dir, screen, todo):

        if dir == -1:
            return INSTALL_NOOP
        
        rc = ButtonChoiceWindow (screen, _("Installation to begin"),
                                _("A complete log of your installation will be in "
                                  "/tmp/install.log after rebooting your system. You "
                                  "may want to keep this file for later reference."),
                                buttons = [ _("OK"), _("Back") ],
				help = "begininstall")
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK

class BeginUpgradeWindow:
    def __call__ (self, screen, todo):
        rc = ButtonChoiceWindow (screen, _("Upgrade to begin"),
                                _("A complete log of your upgrade will be in "
                                  "/tmp/upgrade.log after rebooting your system. You "
                                  "may want to keep this file for later reference."),
                                buttons = [ _("OK"), _("Back") ],
				help = "beginupgrade")
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK

class InstallWindow:
    def __call__ (self, screen, todo):
        if todo.doInstall ():
            return INSTALL_BACK
        return INSTALL_OK

class FinishedWindow:
    def __call__ (self, screen, todo):


        screen.pushHelpLine (_("                              <Return> to reboot                              "))

	rc = ButtonChoiceWindow (screen, _("Complete"), 
		 _("Congratulations, installation is complete.\n\n"
		   "Press return to reboot, and be sure to remove your "
		   "boot medium after the system reboots, or your system "
		   "will rerun the install. For information on fixes which "
		   "are available for this release of Red Hat Linux, "
		   "consult the "
		   "Errata available from http://www.redhat.com/errata.\n\n"
		   "Information on configuring and using your Red Hat "
		   "Linux system is contained in the Red Hat Linux "
		   "manuals."),
		[ _("OK") ], help = "finished")

        return INSTALL_OK


class ReconfigFinishedWindow:
    def __call__ (self, screen, todo):

        screen.pushHelpLine (_("                                <Return> to exit                              "))

        todo.writeConfiguration()
            
        rc = ButtonChoiceWindow (screen, _("Complete"), 
                                 _("Congratulations, configuration is complete.\n\n"
                                   " For information on fixes which "
                                   "are available for this release of Red Hat Linux, "
                                   "consult the "
                                   "Errata available from http://www.redhat.com.\n\n"
                                   "Information on further configuring your system is "
                                   "available at http://www.redhat.com/support/manuals/"),

                                 [ _("OK") ], help = "reconfigfinished")

        return INSTALL_OK

class InstallProgressWindow:
    def completePackage(self, header, timer):
        def formatTime(amt):
            hours = amt / 60 / 60
            amt = amt % (60 * 60)
            min = amt / 60
            amt = amt % 60
            secs = amt

            return "%01d:%02d.%02d" % (int(hours) ,int(min), int(secs))

       	self.numComplete = self.numComplete + 1
	self.sizeComplete = self.sizeComplete + (header[rpm.RPMTAG_SIZE] / 1024)
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

    def setPackage(self, header):
	self.name.setText("%s-%s-%s" % (header[rpm.RPMTAG_NAME],
                                        header[rpm.RPMTAG_VERSION],
                                        header[rpm.RPMTAG_RELEASE]))
	self.size.setText("%dk" % (header[rpm.RPMTAG_SIZE] / 1024))
	summary = header[rpm.RPMTAG_SUMMARY]
	if (summary != None):
	    self.summ.setText(summary)
	else:
            self.summ.setText("(none)")

	self.g.draw()
	self.screen.refresh()

    def __init__(self, screen, total, totalSize):
	self.screen = screen
        toplevel = GridForm(self.screen, _("Package Installation"), 1, 5)
        
        name = _("Name   : ")
        size = _("Size   : ")
        sum =  _("Summary: ")
        
        width = 40 + max (len (name), len (size), len (sum))
	self.name = Label(" " * 40)
	self.size = Label(" ")
	detail = Grid(2, 2)
	detail.setField(Label(name), 0, 0, anchorLeft = 1)
	detail.setField(Label(size), 0, 1, anchorLeft = 1)
	detail.setField(self.name, 1, 0, anchorLeft = 1)
	detail.setField(self.size, 1, 1, anchorLeft = 1)
	toplevel.add(detail, 0, 0)

	summary = Grid(2, 1)
	summlabel = Label(sum)
	self.summ = Textbox(40, 2, "", wrap = 1)
	summary.setField(summlabel, 0, 0)
	summary.setField(self.summ, 1, 0)
	toplevel.add(summary, 0, 1)

	self.s = Scale (width, 100)
	toplevel.add (self.s, 0, 2, (0, 1, 0, 1))

	overall = Grid(4, 4)
	# don't ask me why, but if this spacer isn"t here then the 
        # grid code gets unhappy
	overall.setField (Label (" "), 0, 0, anchorLeft = 1)
	overall.setField (Label (_("    Packages")), 1, 0, anchorLeft = 1)
	overall.setField (Label (_("       Bytes")), 2, 0, anchorLeft = 1)
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

	toplevel.add(overall, 0, 3)

	self.numTotal = total
	self.sizeTotal = totalSize
	self.total = Scale (width, totalSize)
	toplevel.add(self.total, 0, 4, (0, 1, 0, 0))

	self.timeStarted = -1
	
	toplevel.draw()
	self.g = toplevel
	screen.refresh()

    def __del__ (self):
        self.screen.popWindow ()

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
			        buttons = [ _("OK"), _("Cancel") ])
	if rc == string.lower(_("Cancel")):
	    self.rc = 1
	else:
	    self.rc = 0

class ProgressWindow:
    def pop(self):
	self.screen.popWindow()
	self.screen.refresh()

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
	    langs = cat.getlangs()
	    if not langs or langs[0] == "en_US":
		langs = [ 'C' ]

            f = None
            for lang in langs:
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
				       buttons = [ _("OK") ])
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

	    bb = ButtonBar(screen, [ (_("OK"), "ok" ) ] )
	    t = Textbox(width, height, stream, scroll = scroll)

	    g = GridFormHelp(screen, title, "helponhelp", 1, 2)
	    g.add(t, 0, 0, padding = (0, 0, 0, 1))
	    g.add(bb, 0, 1, growx = 1)

	    g.runOnce()
	except:
	    import sys, traceback
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
			       buttons = [ _("OK") ])
	else:
	    return OkCancelWindow(self.screen, _(title), _(text))

    def dumpWindow(self):
	rc = ButtonChoiceWindow(self.screen, _("Save Crash Dump"),
	    _("Please insert a floppy now. All contents of the disk "
	      "will be erased, so please choose your diskette carefully."),
	    [ _("OK"), _("Cancel") ])

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
                           buttons = [ _("OK"), _("Save"), _("Debug") ])
        if rc == string.lower (_("Debug")):
            return 1
	elif rc == string.lower (_("Save")):
            return 2
        return None

    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def packageProgressWindow(self, total, totalSize):
        self.screen.pushHelpLine (_(" "))
	return InstallProgressWindow(self.screen, total, totalSize)

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
        self.screen = SnackScreen()
	self.screen.helpCallback(self.helpWindow)
	self.drawFrame()
# uncomment this line to make the installer quit on <Ctrl+Z>
# handy for quick debugging.
	self.screen.suspendCallback(killSelf, self.screen)
# uncomment this line to drop into the python debugger on <Ctrl+Z>
# --VERY handy--
	#self.screen.suspendCallback(debugSelf, self.screen)
        self.individual = Flag(0)
        self.step = 0
        self.dir = 1
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	signal.signal(signal.SIGTSTP, signal.SIG_IGN)
        if os.environ.has_key ("LC_ALL"):
            cat.setlangs ([os.environ["LC_ALL"][:2]])

    def __del__(self):
        self.screen.finish()

    def run(self, todo, test = 0):
	if todo.serial:
	    self.screen.suspendCallback(spawnShell, self.screen)

        if todo.reconfigOnly:
            self.commonSteps = [
                [N_("Welcome"), ReconfigWelcomeWindow, 
                 (self.screen,), "reconfig" ],
                [N_("Language Selection"), LanguageWindow, 
                 (self.screen, todo, self), "language" ],
                [N_("Keyboard Selection"), KeyboardWindow, 
                 (self.screen, todo), "keyboard" ],
                [N_("Hostname Setup"), HostnameWindow, (self.screen, todo), 
                 "network"],
                [N_("Network Setup"), NetworkWindow, (self.screen, todo), 
                 "network"],
		[N_("Firewall Configuration"), FirewallWindow, (self.screen, todo),
		 "firewall" ],

#                [N_("Mouse Configuration"), MouseWindow, (self.screen, todo),
#                 "mouse" ],
#                [N_("Mouse Configuration"), MouseDeviceWindow, (self.screen, todo),
#                 "mouse" ],

                [N_("Time Zone Setup"), TimezoneWindow, 
                 (self.screen, todo, test), "timezone" ],
                [N_("Root Password"), RootPasswordWindow, 
                 (self.screen, todo), "accounts" ],
                [N_("User Account Setup"), UsersWindow, 
                 (self.screen, todo), "accounts" ],
                [N_("Authentication"), AuthConfigWindow, (self.screen, todo),
                 "authentication" ],
#                [N_("X Configuration"), XConfigWindow, (self.screen, todo),
#                 "xconfig" ],
#                [N_("X Configuration"), XconfiguratorWindow, (self.screen, todo), 
#		    "xconfig"],
                [N_("Configuration Complete"), ReconfigFinishedWindow, (self.screen,todo),
                 "complete" ],
                ]
        else:
            self.commonSteps = [
                [N_("Language Selection"), LanguageWindow, 
                 (self.screen, todo, self), "language" ],
#                [N_("Language Support"), LanguageSupportWindow, 
#                 (self.screen, todo), "languagesupport" ],
#                [N_("Language Default"), LanguageDefaultWindow, 
#                 (self.screen, todo), "languagedefault" ],
                [N_("Keyboard Selection"), KeyboardWindow, 
                 (self.screen, todo), "keyboard" ],
                [N_("Welcome"), WelcomeWindow, (self.screen,), "welcome" ],
                [N_("Installation Type"), InstallPathWindow, 
                 (self.screen, todo, self), "installtype" ],
                ]

	if iutil.getArch() == 'sparc':
	    BootloaderAppendWindow = SiloAppendWindow
	    BootloaderWindow = SiloWindow
	    BootloaderImagesWindow = SiloImagesWindow
	    BootloaderConfiguration = _("SILO Configuration")
            BootloaderSkipName = "silo"
	else:
	    BootloaderAppendWindow = LiloAppendWindow
	    BootloaderWindow = LiloWindow
	    BootloaderImagesWindow = LiloImagesWindow
	    BootloaderConfiguration = _("LILO Configuration")
            BootloaderSkipName = "lilo"            

        self.installSteps = [
            [N_("Automatic Partition"), AutoPartitionWindow, 
		    (self.screen, todo), "partition" ],
            [N_("Partition"), PartitionMethod,
		    (self.screen, todo), "partition" ],
            [N_("Manually Partition"), ManualPartitionWindow, 
		    (self.screen, todo), "partition" ],
            [N_("Partition"), PartitionWindow, (self.screen, todo),
		    "partition" ],
            [N_("Root Filesystem Size"), LoopSizeWindow, (self.screen, todo),
		    "partition" ],
            [N_("Swap"), TurnOnSwapWindow, (self.screen, todo),
		    "partition" ],
            [N_("Boot Partition Warning"), LBA32WarningWindow, (self.screen, todo),
		    "lba32warning" ],
            [N_("Filesystem Formatting"), FormatWindow, (self.screen, todo),
		    "format" ],
            [BootloaderConfiguration, BootloaderAppendWindow, 
		    (self.screen, todo), BootloaderSkipName ],
            [BootloaderConfiguration, BootloaderWindow, 
		    (self.screen, todo), BootloaderSkipName ],
	    [BootloaderConfiguration, BootloaderImagesWindow, 
		    (self.screen, todo), BootloaderSkipName ],
#            [N_("Hostname Setup"), HostnameWindow, (self.screen, todo), 
#		    "network"],
            [N_("Network Setup"), NetworkWindow, (self.screen, todo), 
		    "network"],

            [N_("Hostname Setup"), HostnameWindow, (self.screen, todo), 
		    "network"],
	    [N_("Firewall Configuration"), FirewallWindow, (self.screen, todo),
		 "firewall" ],
            [N_("Mouse Configuration"), MouseWindow, (self.screen, todo.mouse),
		    "mouse" ],
            [N_("Mouse Configuration"), MouseDeviceWindow, (self.screen, todo.mouse),
		    "mouse" ],

            [N_("Language Support"), LanguageSupportWindow, 
             (self.screen, todo), "languagesupport" ],
            [N_("Language Default"), LanguageDefaultWindow, 
             (self.screen, todo), "languagedefault" ],

            [N_("Time Zone Setup"), TimezoneWindow, 
		    (self.screen, todo, test), "timezone" ],
            [N_("Root Password"), RootPasswordWindow, 
		    (self.screen, todo), "accounts" ],
            [N_("User Account Setup"), UsersWindow, 
		    (self.screen, todo), "accounts" ],
            [N_("Authentication"), AuthConfigWindow, (self.screen, todo),
		    "authentication" ],
            [N_("Package Groups"), PackageGroupWindow, 
		(self.screen, todo, self.individual), "package-selection" ],
            [N_("Individual Packages"), IndividualPackageWindow, 
		(self.screen, todo, self.individual), "package-selection" ],
            [N_("Package Dependencies"), PackageDepWindow, (self.screen, todo),
		"package-selection" ],
            [N_("X Configuration"), XConfigWindow, (self.screen, todo),
                "xconfig" ],
            [N_("Installation Begins"), BeginInstallWindow, 
		(self.screen, todo), "confirm-install" ],
            [N_("Install System"), InstallWindow, (self.screen, todo) ],
            [N_("Boot Disk"), BootDiskWindow, (self.screen, todo),
		"bootdisk" ],
            [N_("Boot Disk"), MakeBootDiskWindow, (self.screen, todo), "bootdisk"],
            [N_("X Configuration"), XconfiguratorWindow, (self.screen, todo), 
		    "xconfig"],
            [N_("Installation Complete"), FinishedWindow, (self.screen, todo),
		"complete" ]
            ]

	self.upgradeSteps = [
	    [_("Examine System"), UpgradeExamineWindow, (self.screen, todo)],
            [BootloaderConfiguration, BootloaderAppendWindow, 
		    (self.screen, todo), "lilo"],
            [BootloaderConfiguration, BootloaderWindow, 
		    (self.screen, todo), "lilo"],
	    [BootloaderConfiguration, BootloaderImagesWindow, 
		    (self.screen, todo), "lilo"],
	    [_("Customize Upgrade"), CustomizeUpgradeWindow, 
		    (self.screen, todo, self.individual), "custom-upgrade" ],
            [_("Individual Packages"), IndividualPackageWindow, (self.screen, todo, self.individual)],
            [N_("Upgrade Begins"), BeginUpgradeWindow, 
		(self.screen, todo), "confirm-upgrade" ],
            [_("Upgrade System"), InstallWindow, (self.screen, todo)],
            [_("Boot Disk"), BootDiskWindow, (self.screen, todo),
		"bootdisk" ],
            [_("Boot Disk"), MakeBootDiskWindow, (self.screen, todo), "bootdisk"],
            [_("Upgrade Complete"), FinishedWindow, (self.screen, todo),
             "complete"]
            ]

	dir = 1
        self.steps = self.commonSteps

        while self.step >= 0 and self.step < len(self.steps) and self.steps[self.step]:
	    step = self.steps[self.step]

	    rc = INSTALL_OK
	    if (len(step) == 4):
		if (todo.instClass.skipStep(step[3])):
		    rc = INSTALL_NOOP

	    if (rc != INSTALL_NOOP):
		# clear out the old root text by writing spaces in the blank
		# area on the right side of the screen
		self.screen.drawRootText (len(_(self.welcomeText)), 0,
			  (self.screen.width - len(_(self.welcomeText))) * " ")
		self.screen.drawRootText (0 - len(_(step[0])), 0, _(step[0]))
		# This is *disgusting* (ewt)
		if step[1] == UpgradeExamineWindow:
		    rc = apply (step[1](), (dir,) + step[2])
                elif step[1] == LBA32WarningWindow:
		    rc = apply (step[1](), (dir,) + step[2])
                elif step[1] == BeginInstallWindow:
		    rc = apply (step[1](), (dir,) + step[2])
		else:
		    rc = apply (step[1](), step[2])

	    if rc == INSTALL_BACK:
		dir = -1
	    elif rc == INSTALL_OK:
		dir = 1

	    self.step = self.step + dir
            if self.step < 0:
                ButtonChoiceWindow(self.screen, _("Cancelled"),
                                   _("I can't go to the previous step"
                                     " from here. You will have to try again."),
                                   buttons = [ _("OK") ])
                                   
                self.step = 0
                dir = 1
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
