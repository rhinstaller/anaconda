from snack import *
import sys
import isys
import os
import iutil
import rpm
import time
import gettext
import glob

cat = gettext.Catalog ("anaconda", "/usr/share/locale")

def _(string):
    return cat.gettext (string)

from textw.constants import *
from textw.lilo import LiloWindow
from textw.lilo import LiloAppendWindow
from textw.lilo import LiloImagesWindow
from textw.silo import SiloWindow
from textw.silo import SiloAppendWindow
from textw.silo import SiloImagesWindow
from textw.userauth import RootPasswordWindow
from textw.userauth import UsersWindow
from textw.userauth import AuthConfigWindow
from textw.partitioning import PartitionMethod
from textw.partitioning import ManualPartitionWindow
from textw.partitioning import AutoPartitionWindow
from textw.partitioning import PartitionWindow
from textw.partitioning import TurnOnSwapWindow
from textw.partitioning import FormatWindow
from textw.packages import PackageGroupWindow
from textw.packages import IndividualPackageWindow
from textw.packages import PackageDepWindow
import installclass

class LanguageWindow:
    def __call__(self, screen, todo):
        languages = todo.language.available ()
        descriptions = languages.keys ()
        descriptions.sort ()
        current = todo.language.get ()
        for lang in descriptions:
            if languages[lang] == current:
                default = descriptions.index (lang)
            
        height = min((screen.height - 16, len(descriptions)))
        (button, choice) = \
            ListboxChoiceWindow(screen, _("Language Selection"),
			_("What language would you like to use during the "
			  "installation process?"), descriptions, 
			buttons = [_("OK")], width = 30, default = default, scroll = 1,
                                height = height)
        choice = descriptions[choice]
        lang = languages [choice]
        newlangs = [lang]
	if len(lang) > 2:
            newlangs.append(lang[:2])
        gettext.setlangs (newlangs)
        global cat
        cat = gettext.Catalog ("anaconda", "/usr/share/locale")
        todo.language.set (choice)
        return INSTALL_OK

class MouseDeviceWindow:
    def __call__(self, screen, todo):
	choices = { _("/dev/ttyS0 (COM1 under DOS)") : "ttyS0",
		    _("/dev/ttyS1 (COM2 under DOS)") : "ttyS1",
		    _("/dev/ttyS2 (COM3 under DOS)") : "ttyS2",
		    _("/dev/ttyS3 (COM4 under DOS)") : "ttyS3" }

	i = 0
	default = 0
	mouse = todo.mouse.getDevice()
	if (mouse[0:4] != "ttyS"): return INSTALL_NOOP

	l = choices.keys()
	l.sort()
	for choice in l:
	    if choices[choice] == mouse:
		default = i
		break
	    i = i + 1

	(button, result) = ListboxChoiceWindow(screen, _("Device"),
		    _("What device is your mouse located on? %s %i") % (mouse, default), l,
		    [ _("Ok"), _("Back") ], default = default )
	if (button == string.lower(_("Back"))): return INSTALL_BACK

	todo.mouse.setDevice(choices[l[result]])

	#import sys; sys.exit(0)

	return INSTALL_OK

class MouseWindow:
    def __call__(self, screen, todo):
	if todo.serial:
	    return INSTALL_NOOP
        mice = todo.mouse.available ().keys ()
        mice.sort ()
	(default, emulate) = todo.mouse.get ()
	if default == "Sun - Mouse":
	    return INSTALL_NOOP
        default = mice.index (default)

	bb = ButtonBar(screen, [_("OK"), _("Back")])
	t = TextboxReflowed(40, 
		_("Which model mouse is attached to this computer?"))
	l = Listbox(8, scroll = 1, returnExit = 0)

        key = 0
        for mouse in mice:
	    l.append(mouse, key)
	    key = key + 1
	l.setCurrent(default)

	c = Checkbox(_("Emulate 3 Buttons?"), isOn = emulate)

	g = GridForm(screen, _("Mouse Selection"), 1, 4)
	g.add(t, 0, 0)
	g.add(l, 0, 1, padding = (0, 1, 0, 1))
	g.add(c, 0, 2, padding = (0, 0, 0, 1))
	g.add(bb, 0, 3, growx = 1)

	rc = g.runOnce()

        button = bb.buttonPressed(rc)
        
        if button == string.lower (_("Back")):
            return INSTALL_BACK

	choice = l.current()
	emulate = c.selected()

        todo.mouse.set(mice[choice], emulate)

	oldDev = todo.mouse.getDevice()
	if (oldDev):
	    newDev = todo.mouse.available()[mice[choice]][2]
	    if ((oldDev[0:4] == "ttyS" and newDev[0:4] == "ttyS") or
		(oldDev == newDev)):
		pass
	    else:
		todo.mouse.setDevice(newDev)

	return INSTALL_OK

class KeyboardWindow:
    def __call__(self, screen, todo):
	if todo.serial:
	    return INSTALL_NOOP
        keyboards = todo.keyboard.available ()
        keyboards.sort ()
        default = keyboards.index (todo.keyboard.get ())

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Keyboard Selection"),
                                _("Which model keyboard is attached to this computer?"), keyboards, 
                                buttons = [_("OK"), _("Back")], width = 30, scroll = 1, height = 8,
                                default = default)
        
        if button == string.lower (_("Back")):
            return INSTALL_BACK
        todo.keyboard.set (keyboards[choice])
        return INSTALL_OK
    
class InstallPathWindow:
    def __call__ (self, screen, todo, intf):
	if (todo.instClass.installType == "install"):
            intf.steps = intf.commonSteps + intf.installSteps
            todo.upgrade = 0
	    return INSTALL_NOOP
	elif (todo.instClass.installType == "upgrade"):
            intf.steps = intf.commonSteps + intf.upgradeSteps
            todo.upgrade = 1
	    return INSTALL_NOOP

	if (todo.upgrade):
	    default = 4
	    orig = None
	else:
	    instClass = todo.getClass()
	    orig = None
	    if isinstance(instClass, installclass.GNOMEWorkstation):
		orig = 0
	    elif isinstance(instClass, installclass.KDEWorkstation):
		orig = 1
	    elif isinstance(instClass, installclass.Server):
		orig = 2
	    elif isinstance(instClass, installclass.CustomInstall):
		orig = 3
	    if (orig):
		default = orig
	    else:
		default = 0

	choices = [ _("Install GNOME Workstation"), 
		    _("Install KDE Workstation"),
		    _("Install Server System"),
		    _("Install Custom System"),
		    _("Upgrade Existing Installation") ]
	(button, choice) = ListboxChoiceWindow(screen, _("Installation Type"),
			_("What type of system would you like to install?"),
			    choices, [(_("OK"), "ok"), (_("Back"), "back")],
			    width = 40, default = default)

        if button == "back":
            return INSTALL_BACK
	if (choice == 4):
            intf.steps = intf.commonSteps + intf.upgradeSteps
            todo.upgrade = 1
        else:
            intf.steps = intf.commonSteps + intf.installSteps
            todo.upgrade = 0
	    if (choice == 0 and orig != 0):
		todo.setClass(installclass.GNOMEWorkstation())
	    elif (choice == 1 and orig != 1):
		todo.setClass(installclass.KDEWorkstation())
	    elif (choice == 2 and orig != 2):
		todo.setClass(installclass.Server())
	    elif (choice == 3 and orig != 3):
		todo.setClass(installclass.CustomInstall())
        return INSTALL_OK

class UpgradeExamineWindow:
    def __call__ (self, screen, todo):
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

            (button, choice) = \
                ListboxChoiceWindow(screen, _("System to Upgrade"),
                                    _("What partition holds the root partition "
                                      "of your installation?"), parts, 
                                    [ _("OK"), _("Back") ], width = 30,
                                    scroll = scroll, height = height)
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
                                 buttons = [ _("Yes"), _("No"), _("Back") ])

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
                                buttons = [_("OK"), _("Back")], width = 50)

	if rc == string.lower(_("Back")):
	    return INSTALL_BACK

        return INSTALL_OK

class NetworkWindow:
    def setsensitive (self):
        if self.cb.selected ():
            sense = FLAGS_SET
        else:
            sense = FLAGS_RESET

        for n in self.ip, self.nm, self.gw, self.ns:
            n.setFlags (FLAG_DISABLED, sense)

    def calcNM (self):
        ip = self.ip.value ()
        if ip and not self.nm.value ():
            try:
                mask = isys.inet_calcNetmask (ip)
            except ValueError:
                return

            self.nm.set (mask)

    def calcGW (self):
        ip = self.ip.value ()
        nm = self.nm.value ()
        if ip and nm:
            try:
                (net, bcast) = isys.inet_calcNetBroad (ip, nm)
            except ValueError:
                return

            if not self.gw.value ():
                gw = isys.inet_calcGateway (bcast)
                self.gw.set (gw)
            if not self.ns.value ():
                ns = isys.inet_calcNS (net)
                self.ns.set (ns)

    def __call__(self, screen, todo):


        devices = todo.network.available ()
        if not devices:
            return INSTALL_NOOP

        if todo.network.readData:
            # XXX expert mode, allow changing network settings here
            return INSTALL_NOOP
        
	list = devices.keys ()
	list.sort()
        dev = devices[list[0]]

        firstg = Grid (1, 1)
        boot = dev.get ("bootproto")
        
        if not boot:
            boot = "dhcp"
        self.cb = Checkbox (_("Use bootp/dhcp"),
                            isOn = (boot == "dhcp"))
        firstg.setField (self.cb, 0, 0, anchorLeft = 1)

        secondg = Grid (2, 4)
        secondg.setField (Label (_("IP address:")), 0, 0, anchorLeft = 1)
	secondg.setField (Label (_("Netmask:")), 0, 1, anchorLeft = 1)
	secondg.setField (Label (_("Default gateway (IP):")), 0, 2, anchorLeft = 1)
        secondg.setField (Label (_("Primary nameserver:")), 0, 3, anchorLeft = 1)

        self.ip = Entry (16)
        self.ip.set (dev.get ("ipaddr"))
        self.nm = Entry (16)
        self.nm.set (dev.get ("netmask"))
        self.gw = Entry (16)
        self.gw.set (todo.network.gateway)
        self.ns = Entry (16)
        self.ns.set (todo.network.primaryNS)

        self.cb.setCallback (self.setsensitive)
        self.ip.setCallback (self.calcNM)
        self.nm.setCallback (self.calcGW)

        secondg.setField (self.ip, 1, 0, (1, 0, 0, 0))
	secondg.setField (self.nm, 1, 1, (1, 0, 0, 0))
	secondg.setField (self.gw, 1, 2, (1, 0, 0, 0))
        secondg.setField (self.ns, 1, 3, (1, 0, 0, 0))

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        toplevel = GridForm (screen, _("Network Configuration"), 1, 3)
        toplevel.add (firstg, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        toplevel.add (secondg, 0, 1, (0, 0, 0, 1))
        toplevel.add (bb, 0, 2, growx = 1)

        self.setsensitive ()

        while 1:
            result = toplevel.run ()
            if self.cb.selected ():
                dev.set (("bootproto", "dhcp"))
                dev.unset ("ipaddr", "netmask", "network", "broadcast")
            else:
                try:
                    (network, broadcast) = isys.inet_calcNetBroad (self.ip.value (), self.nm.value ())
                except:
                    ButtonChoiceWindow(screen, _("Invalid information"),
                                       _("You must enter valid IP information to continue"),
                                       buttons = [ _("OK") ])
                    continue

                dev.set (("bootproto", "static"))
                dev.set (("ipaddr", self.ip.value ()), ("netmask", self.nm.value ()),
                         ("network", network), ("broadcast", broadcast))
                todo.network.gateway = self.gw.value ()
                todo.network.primaryNS = self.ns.value ()
                todo.network.guessHostnames ()
            screen.popWindow()
            break
                     
        dev.set (("onboot", "yes"))

        rc = bb.buttonPressed (result)

        todo.log ("\"" + dev.get ("device") + "\"")

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

class HostnameWindow:
    def __call__(self, screen, todo):
        entry = Entry (24)
        if todo.network.hostname != "localhost.localdomain":
            entry.set (todo.network.hostname)
        rc, values = EntryWindow(screen, _("Hostname Configuration"),
             _("The hostname is the name of your computer.  If your "
               "computer is attached to a network, this may be "
               "assigned by your network administrator."),
             [(_("Hostname"), entry)], buttons = [ _("OK"), _("Back")])

        if rc == string.lower (_("Back")):
            return INSTALL_BACK

        todo.network.hostname = entry.value ()
        
        return INSTALL_OK

class BootDiskWindow:
    def __call__(self, screen, todo):
	buttons = [ _("Yes"), _("No"), _("Back") ]
	text =  _("A custom boot disk provides a way of booting into your "
		  "Linux system without depending on the normal bootloader. "
		  "This is useful if you don't want to install lilo on your "
		  "system, another operating system removes lilo, or lilo "
		  "doesn't work with your hardware configuration. A custom "
		  "boot disk can also be used with the Red Hat rescue image, "
		  "making it much easier to recover from severe system "
		  "failures.\n\n"
		  "Would you like to create a boot disk for your system?")

	if iutil.getArch () == "sparc":
	    floppy = todo.silo.hasUsableFloppy()
	    if floppy == 0:
		todo.bootdisk = 0
		return INSTALL_NOOP
	    text = string.replace (text, "lilo", "silo")
	    if floppy == 1:
		buttons = [ _("No"), _("Yes"), _("Back") ]
		text = string.replace (text, "\n\n",
				       _("\nOn SMCC made Ultra machines floppy booting "
					 "probably does not work\n\n"))

	rc = ButtonChoiceWindow(screen, _("Bootdisk"), text, buttons = buttons)

	if rc == string.lower (_("Yes")):
	    todo.bootdisk = 1
	
	if rc == string.lower (_("No")):
	    todo.bootdisk = 0

	if rc == string.lower (_("Back")):
	    return INSTALL_BACK
	return INSTALL_OK

class XConfigWindow:
    def __call__(self, screen, todo):
        # we need to get the package list here for things like
        # workstation install - which will not have read the
        # package list yet.
        todo.getCompsList ()

	if not todo.hdList.packages.has_key('XFree86') or \
	   not todo.hdList.packages['XFree86'].selected: return None

        todo.x.probe (probeMonitor = 0)

        if todo.x.server:
            rc = ButtonChoiceWindow (screen, _("X probe results"),
                                     todo.x.probeReport (),
                                     buttons = [ _("OK"), _("Back") ])
        
            if rc == string.lower (_("Back")):
                return INSTALL_BACK

	    # 6.1 sparc hack - remove once supported
	    if todo.x.server == "3DLabs":
		todo.x.server = None

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
	server = None

	rc = INSTALL_NOOP
	while rc != INSTALL_OK:
	    (rc, choice) = ListboxChoiceWindow(screen, _("Video Card Selection"),
					       _("Which video card do you have?"),
					       cards,
					       buttons = [_("OK"), _("Back")],
					       width = 70, scroll = 1,
					       height = screen.height - 14)
	    if rc == string.lower (_("Back")):
		return INSTALL_BACK

	    todo._cardindex = -1

	    if cards[choice] == _("Unlisted Card"):
		(rc , choice) = \
		    ListboxChoiceWindow(screen, _("X Server Selection"), _("Choose a server"),
					servers,
					buttons = [ (_("Ok"), "ok"), (_("Back"), "back") ],
					scroll = 1,
					height = screen.height - 14)

		if (rc == "back"):
		    rc = INSTALL_BACK
		else:
		    rc = INSTALL_OK
		    server = servers[choice]
	    else:
		todo._cardindex = choice
		rc = INSTALL_OK

	if server:
	    todo.x.setVidcard ( { "NAME" : "Generic " + server,
				  "SERVER" : server } )
	else:
	    card = carddb[cards[choice]]

	    if card.has_key ("SEE"):
		card = carddb[card["SEE"]]

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
                          os.X_OK): return INSTALL_NOOP

        f = open (todo.instPath + "/tmp/SERVER", "w")
        f.write ("%s %d\n" % (todo.x.server, todo._cardindex))
        f.close ()

        screen.suspend ()
        iutil.execWithRedirect ("/usr/X11R6/bin/Xconfigurator",
                                ["xconfigurator", "--continue"],
                                root = todo.instPath)
        screen.resume ()
	todo.x.skip = 1
        return INSTALL_NOOP
        
class BeginInstallWindow:
    def __call__ (self, screen, todo):
        rc = ButtonChoiceWindow (screen, _("Installation to begin"),
                                _("A complete log of your installation will be in "
                                  "/tmp/install.log after rebooting your system. You "
                                  "may want to keep this file for later reference."),
                                buttons = [ _("OK"), _("Back") ])
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK

class InstallWindow:
    def __call__ (self, screen, todo):
        if todo.doInstall ():
            return INSTALL_BACK
        return INSTALL_OK

class FinishedWindow:
    def __call__ (self, screen):
        rc = ButtonChoiceWindow (screen, _("Complete"), 
	 _("Congratulations, installation is complete.\n\n"
	   "Remove the boot media and "
	   "press return to reboot. For information on fixes which are "
	   "available for this release of Red Hat Linux, consult the "
	   "Errata available from http://www.redhat.com.\n\n"
	   "Information on configuring your system is available in the post "
	   "install chapter of the Official Red Hat Linux User's Guide."),
	 [ _("OK") ])
        return INSTALL_OK

class BootdiskWindow:
    def __call__ (self, screen, todo):
        if not todo.bootdisk:
            return INSTALL_NOOP

        rc = ButtonChoiceWindow (screen, _("Bootdisk"),
		     _("Insert a blank floppy in the first floppy drive. "
		       "All data on this disk will be erased during creation "
		       "of the boot disk."),
		     [ _("OK"), _("Skip") ])                
        if rc == string.lower (_("Skip")):
            return INSTALL_OK
            
        while 1:
            try:
                todo.makeBootdisk ()
            except:
                rc = ButtonChoiceWindow (screen, _("Error"),
			_("An error occured while making the boot disk. "
			  "Please make sure that there is a formatted floppy "
			  "in the first floppy drive."),
			  [ _("OK"), _("Skip")] )
                if rc == string.lower (_("Skip")):
                    break
                continue
            else:
                break
            
        return INSTALL_OK

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
	self.sizeCompleteW.setText("%10dM" % (self.sizeComplete / (1024 * 1024)))
	self.numRemainingW.setText("%12d" % (self.numTotal - self.numComplete))
	self.sizeRemainingW.setText("%10dM" % ((self.sizeTotal - self.sizeComplete) / (1024 * 1024)))
	self.total.set(self.sizeComplete)

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
	overall.setField (Label ("%10dM" % (totalSize / (1024 * 1024))),
                          2, 1, anchorLeft = 1)
	self.timeTotalW = Label("")
	overall.setField(self.timeTotalW, 3, 1, anchorLeft = 1)

	overall.setField (Label (_("Completed:   ")), 0, 2, anchorLeft = 1)
	self.numComplete = 0
	self.numCompleteW = Label("%12d" % self.numComplete)
	overall.setField(self.numCompleteW, 1, 2, anchorLeft = 1)
	self.sizeComplete = 0
        self.sizeCompleteW = Label("%10dM" % (self.sizeComplete / (1024 * 1024)))
	overall.setField(self.sizeCompleteW, 2, 2, anchorLeft = 1)
	self.timeCompleteW = Label("")
	overall.setField(self.timeCompleteW, 3, 2, anchorLeft = 1)

	overall.setField (Label (_("Remaining:  ")), 0, 3, anchorLeft = 1)
	self.numRemainingW = Label("%12d" % total)
        self.sizeRemainingW = Label("%10dM" % (totalSize / (1024 * 1024)))
	overall.setField(self.numRemainingW, 1, 3, anchorLeft = 1)
	overall.setField(self.sizeRemainingW, 2, 3, anchorLeft = 1)
	self.timeRemainingW = Label("")
	overall.setField(self.timeRemainingW, 3, 3, anchorLeft = 1)

	toplevel.add(overall, 0, 3)

	self.numTotal = total
	self.sizeTotal = totalSize
	self.total = Scale (width, totalSize)
	toplevel.add(self.total, 0, 4, (0, 1, 0, 0))

	self.timeStarted = time.time()	
	
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

class TimezoneWindow:

    def getTimezoneList(self, test):
	if test and not os.access("/usr/lib/timezones.gz", os.R_OK):
	    cmd = "./gettzlist"
	    stdin = None
	else:
	    cmd = "/usr/bin/gunzip"
	    stdin = os.open("/usr/lib/timezones.gz", 0)

	zones = iutil.execWithCapture(cmd, [ cmd ], stdin = stdin)
	zoneList = string.split(zones)

	if (stdin != None): os.close(stdin)

	return zoneList

    def __call__(self, screen, todo, test):
	timezones = self.getTimezoneList(test)
	rc = todo.getTimezoneInfo()
	if rc:
	    (default, asUtc, asArc) = rc
	else:
	    default = "US/Eastern"
	    asUtc = 0

	bb = ButtonBar(screen, [_("OK"), _("Back")])
	t = TextboxReflowed(30, 
			_("What time zone are you located in?"))
		
	l = Listbox(8, scroll = 1, returnExit = 0)

        for tz in timezones:
	    l.append(tz, tz)
	l.setCurrent(default)

	c = Checkbox(_("Hardware clock set to GMT?"), isOn = asUtc)

	g = GridForm(screen, _("Time Zone Selection"), 1, 4)
	g.add(t, 0, 0)
	g.add(c, 0, 1, padding = (0, 1, 0, 1), anchorLeft = 1)
	g.add(l, 0, 2, padding = (0, 0, 0, 1))
	g.add(bb, 0, 3, growx = 1)

	rc = g.runOnce()

        button = bb.buttonPressed(rc)
        
        if button == string.lower (_("Back")):
            return INSTALL_BACK

	todo.setTimezoneInfo(l.current(), asUtc = c.selected())

	return INSTALL_OK

class Flag:
    """a quick mutable boolean class"""
    def __init__(self, value = 0):
        self.flag = value

    def set(self, value):
        self.flag = value;

    def get(self):
        return self.flag


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
	g.add(t, 0, 0, (0, 0, 0, 1))

        self.scale = Scale (width, total)
        g.add(self.scale, 0, 1)
                
	g.draw()
	self.screen.refresh()

class InstallInterface:
    def progressWindow(self, title, text, total):
        return ProgressWindow (self.screen, _(title), _(text), total)

    def messageWindow(self, title, text):
	ButtonChoiceWindow(self.screen, _(title), _(text),
                           buttons = [ _("OK") ])
    
    def exceptionWindow(self, title, text):
	rc = ButtonChoiceWindow(self.screen, title, text,
                           buttons = [ _("OK"), _("Debug") ])
        if rc == string.lower (_("Debug")):
            return 1
        return None

    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def packageProgressWindow(self, total, totalSize):
	return InstallProgressWindow(self.screen, total, totalSize)

    def __init__(self):
        self.screen = SnackScreen()
        self.welcomeText = _("Red Hat Linux (C) 1999 Red Hat, Inc.")
        self.screen.drawRootText (0, 0, self.welcomeText)
        self.screen.pushHelpLine (_("  <Tab>/<Alt-Tab> between elements   |  <Space> selects   |  <F12> next screen"))
# uncomment this line to make the installer quit on <Ctrl+Z>
# handy for quick debugging.
#	self.screen.suspendCallback(killSelf, self.screen)
# uncomment this line to drop into the python debugger on <Ctrl+Z>
# --VERY handy--
#	self.screen.suspendCallback(debugSelf, self.screen)
        self.individual = Flag(0)
        self.step = 0
        self.dir = 1

    def __del__(self):
        self.screen.finish()

    def run(self, todo, test = 0):
	if todo.serial:
	    self.screen.suspendCallback(spawnShell, self.screen)
        self.commonSteps = [
            [_("Language Selection"), LanguageWindow, 
		    (self.screen, todo), "language" ],
            [_("Keyboard Selection"), KeyboardWindow, 
		    (self.screen, todo), "keyboard" ],
            [_("Welcome"), WelcomeWindow, (self.screen,), "welcome" ],
            [_("Installation Type"), InstallPathWindow, 
		    (self.screen, todo, self) ],
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
            [_("Partition"), PartitionMethod,
		    (self.screen, todo), "partition" ],
            [_("Manually Partition"), ManualPartitionWindow, 
		    (self.screen, todo), "partition" ],
            [_("Automatic Partition"), AutoPartitionWindow, 
		    (self.screen, todo), "partition" ],
            [_("Partition"), PartitionWindow, (self.screen, todo),
		    "partition" ],
            [_("Swap"), TurnOnSwapWindow, (self.screen, todo),
		    "partition" ],
            [_("Filesystem Formatting"), FormatWindow, (self.screen, todo),
		    "format" ],
            [BootloaderConfiguration, BootloaderAppendWindow, 
		    (self.screen, todo), BootloaderSkipName ],
            [BootloaderConfiguration, BootloaderWindow, 
		    (self.screen, todo), BootloaderSkipName ],
	    [BootloaderConfiguration, BootloaderImagesWindow, 
		    (self.screen, todo), BootloaderSkipName ],
            [_("Hostname Setup"), HostnameWindow, (self.screen, todo), 
		    "network"],
            [_("Network Setup"), NetworkWindow, (self.screen, todo), 
		    "network"],
            [_("Mouse Configuration"), MouseWindow, (self.screen, todo),
		    "mouse" ],
            [_("Mouse Configuration"), MouseDeviceWindow, (self.screen, todo),
		    "mouse" ],
            [_("Time Zone Setup"), TimezoneWindow, 
		    (self.screen, todo, test), "timezone" ],
            [_("Root Password"), RootPasswordWindow, 
		    (self.screen, todo), "accounts" ],
            [_("User Account Setup"), UsersWindow, 
		    (self.screen, todo), "accounts" ],
            [_("Authentication"), AuthConfigWindow, (self.screen, todo),
		    "authentication" ],
            [_("Package Groups"), PackageGroupWindow, 
		(self.screen, todo, self.individual), "package-selection" ],
            [_("Individual Packages"), IndividualPackageWindow, 
		(self.screen, todo, self.individual), "package-selection" ],
            [_("Package Dependencies"), PackageDepWindow, (self.screen, todo),
		"package-selection" ],
            [_("X Configuration"), XConfigWindow, (self.screen, todo),
                "xconfig" ],
            [_("Boot Disk"), BootDiskWindow, (self.screen, todo),
		"bootdisk" ],
            [_("Installation Begins"), BeginInstallWindow, 
		(self.screen, todo), "confirm-install" ],
            [_("Install System"), InstallWindow, (self.screen, todo) ],
            [_("Boot Disk"), BootdiskWindow, (self.screen, todo), "bootdisk"],
            [_("X Configuration"), XconfiguratorWindow, (self.screen, todo), 
		    "xconfig"],
            [_("Installation Complete"), FinishedWindow, (self.screen,),
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
	    [_("Customize Upgrade"), CustomizeUpgradeWindow, (self.screen, todo, self.individual)],
            [_("Individual Packages"), IndividualPackageWindow, (self.screen, todo, self.individual)],
            [_("Boot Disk"), BootDiskWindow, (self.screen, todo),
		"bootdisk" ],
            [_("Upgrade System"), InstallWindow, (self.screen, todo)],
            [_("Boot Disk"), BootdiskWindow, (self.screen, todo), "bootdisk"],
            [_("Upgrade Complete"), FinishedWindow, (self.screen,)]
            ]

        self.steps = self.commonSteps
	dir = 1

        while self.step >= 0 and self.step < len(self.steps) and self.steps[self.step]:
	    step = self.steps[self.step]

	    rc = INSTALL_OK
	    if (len(step) == 4):
		if (todo.instClass.skipStep(step[3])):
		    rc = INSTALL_NOOP

	    if (rc != INSTALL_NOOP):
		# clear out the old root text by writing spaces in the blank
		# area on the right side of the screen
		self.screen.drawRootText (len(self.welcomeText), 0,
			     (self.screen.width - len(self.welcomeText)) * " ")
		self.screen.drawRootText (0 - len(step[0]),
					 0, step[0])
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
    pdb.set_trace()
    screen.resume ()

def spawnShell(screen):
    screen.suspend ()
    print "\n\nType <exit> to return to the install program.\n"
    iutil.execWithRedirect ("/bin/sh", ["-/bin/sh"])
    time.sleep(5)
    screen.resume ()
