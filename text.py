from snack import *
import parted
import sys
import isys
import os
import rpm
import time
import gettext
import glob

INSTALL_OK = 0
INSTALL_BACK = -1
INSTALL_NOOP = -2

cat = gettext.Catalog ("anaconda-text", "/usr/share/locale")
_ = cat.gettext

class LanguageWindow:
    def run(self, screen, todo):
        languages = todo.language.available ()
        current = todo.language.get ()

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Language Selection"),
                                _("What language would you like to use during the "
                                  "installation process?"), languages.keys (), 
                                buttons = [_("Ok")], width = 30)
        langs = gettext.getlangs ()
        langs = [languages [languages.keys()[choice]]] + langs
        gettext.setlangs (langs)
        global cat, _
        cat = gettext.Catalog ("anaconda-text", "/usr/share/locale")
        _ = cat.gettext
        todo.language.set (languages.keys()[choice])
        return INSTALL_OK

class KeyboardWindow:
    def run(self, screen, todo):
        keyboards = todo.keyboard.available ()
        keyboards.sort ()
        current = todo.keyboard.get ()

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Keyboard Selection"),
                                _("Which model keyboard is attached to this computer?"), keyboards, 
                                buttons = [_("Ok"), _("Back")], width = 30, scroll = 1, height = 8)
        
        if button == string.lower (_("Back")):
            return INSTALL_BACK
        todo.keyboard.set (keyboards[choice])
        return INSTALL_OK


class RootPasswordWindow:
    def run(self, screen, todo):
        toplevel = GridForm (screen, _("Root Password"), 1, 3)

        toplevel.add (TextboxReflowed(37, _("Pick a root password. You must "
                                            "type it twice to ensure you know "
                                            "what it is and didn't make a mistake "
                                            "in typing. Remember that the "
                                            "root password is a critical part "
                                            "of system security!")), 0, 0, (0, 0, 0, 1))
        entry1 = Entry (24, hidden = 1)
        entry2 = Entry (24, hidden = 1)
        passgrid = Grid (2, 2)
        passgrid.setField (Label (_("Password:")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (Label (_("Password (again):")), 0, 1, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (entry1, 1, 0)
        passgrid.setField (entry2, 1, 1)
        toplevel.add (passgrid, 0, 1, (0, 0, 0, 1))
        
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))
        toplevel.add (bb, 0, 2, growx = 1)

        while 1:
            entry1.set ("")
            entry2.set ("")
            toplevel.setCurrent (entry1)
            result = toplevel.run ()
            rc = bb.buttonPressed (result)
            if rc == "back":
                screen.popWindow()
                return INSTALL_BACK
            if len (entry1.value ()) < 6:
                ButtonChoiceWindow(screen, _("Password Length"),
                                   _("The root password must be at least 6 characters "
                                     "long."),
                                   buttons = [ _("OK") ], width = 50)
            elif entry1.value () != entry2.value ():
                ButtonChoiceWindow(screen, _("Password Mismatch"),
                                   _("The passwords you entered were different. Please "
                                     "try again."),
                                   buttons = [ _("OK") ], width = 50)
            else:
                break
        screen.popWindow()
        todo.rootpassword.set (entry1.value ())
        return INSTALL_OK

class WelcomeWindow:
    def run(self, screen):
        rc = ButtonChoiceWindow(screen, _("Red Hat Linux"), 
                                _("Welcome to Red Hat Linux!\n\n"
                                  "This installation process is outlined in detail in the "
                                  "Official Red Hat Linux Installation Guide available from "
                                  "Red Hat Software. If you have access to this manual, you "
                                  "should read the installation section before continuing.\n\n"
                                  "If you have purchased Official Red Hat Linux, be sure to "
                                  "register your purchase through our web site, "
                                  "http://www.redhat.com/."),
                                buttons = [_("Ok"), _("Back")], width = 50)

	if rc == string.lower(_("Back")):
	    return INSTALL_BACK

        return INSTALL_OK

class NetworkWindow:
            
    def run(self, screen, todo):
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

        devices = todo.network.available ()
        dev = devices[devices.keys ()[0]]

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

        self.cb.setCallback (setsensitive, self)
        self.ip.setCallback (calcNM, self)
        self.nm.setCallback (calcGW, self)

        secondg.setField (self.ip, 1, 0, (1, 0, 0, 0))
	secondg.setField (self.nm, 1, 1, (1, 0, 0, 0))
	secondg.setField (self.gw, 1, 2, (1, 0, 0, 0))
        secondg.setField (self.ns, 1, 3, (1, 0, 0, 0))

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        toplevel = GridForm (screen, _("Network Configuration"), 1, 3)
        toplevel.add (firstg, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        toplevel.add (secondg, 0, 1, (0, 0, 0, 1))
        toplevel.add (bb, 0, 2, growx = 1)

        setsensitive (self)
        
        result = toplevel.runOnce ()
        
        if self.cb.selected ():
            dev.set (("bootproto", "dhcp"))
            dev.unset ("ipaddr", "netmask", "network", "broadcast")
        else:
            self.calculateIPs ()
            dev.set (("bootproto", "static"))
            dev.set (("ipaddr", self.ip.value ()), ("netmask", self.nm.value ()),
                     ("network", self.network), ("broadcast", self.broadcast))
            todo.network.gateway = self.gw.value ()
            todo.network.primaryNS = self.ns.value ()
            todo.network.guessHostnames ()
                     
        dev.set (("onboot", "yes"))

        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

class PartitionWindow:
    def run(self, screen, todo):
	if (not todo.setupFilesystems): return INSTALL_NOOP

        sys.path.append('libfdisk')
        from newtpyfsedit import fsedit        

        fstab = []
        for (dev, dir, reformat) in todo.mounts:
            fstab.append ((dev, dir))
        
        (dir, res) = fsedit(1, ['hda'], fstab)

        for (partition, mount, size) in res:
            todo.addMount(partition, mount)

        return dir

class PackageGroupWindow:
    def run(self, screen, todo, individual):
        # be sure that the headers and comps files have been read.
	todo.getHeaderList()
        todo.getCompsList()

        ct = CheckboxTree(height = 10, scroll = 1)
        for comp in todo.comps:
            if not comp.hidden:
                ct.append(comp.name, comp, comp.selected)

        cb = Checkbox (_("Select individual packages"), individual.get ())

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        g = GridForm (screen, _("Package Group Selection"), 1, 3)
        g.add (ct, 0, 0, (0, 0, 0, 1))
        g.add (cb, 0, 1, (0, 0, 0, 1))
        g.add (bb, 0, 2, growx = 1)

        result = g.runOnce()

        individual.set (cb.selected())
        # turn off all the comps
        for comp in todo.comps:
            if not comp.hidden: comp.unselect(0)

        # turn on all the comps we selected
        for comp in ct.getSelection():
            comp.select (0)

        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

class IndividualPackageWindow:
    def run(self, screen, todo, individual):
        if not individual.get():
            return
	todo.getHeaderList()

        ct = CheckboxTree(height = 10, scroll = 1)
        groups = {}

        # go through all the headers and grok out the group names, placing
        # packages in lists in the groups dictionary.
        
        for key in todo.hdList.packages.keys():
            header = todo.hdList.packages[key]
            # don't show this package if it is in the base group
            if not todo.comps["Base"].items.has_key (header):
                if not groups.has_key (header[rpm.RPMTAG_GROUP]):
                    groups[header[rpm.RPMTAG_GROUP]] = []
                groups[header[rpm.RPMTAG_GROUP]].append (header)

        # now insert the groups into the list, then each group's packages
        # after sorting the list
        def cmpHdrName(first, second):
            if first[rpm.RPMTAG_NAME] < second[rpm.RPMTAG_NAME]:
                return -1
            elif first[rpm.RPMTAG_NAME] == second[rpm.RPMTAG_NAME]:
                return 0
            return 1
        
        keys = groups.keys ()
        keys.sort ()
        index = 0
        for key in keys:
            groups[key].sort (cmpHdrName)
            ct.append (key)
            for header in groups[key]:
                ct.addItem (header[rpm.RPMTAG_NAME], (index, snackArgs["append"]),
                            header, header.selected)
            index = index + 1
                
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        g = GridForm (screen, _("Package Group Selection"), 1, 2)
        g.add (ct, 0, 0, (0, 0, 0, 1))
        g.add (bb, 0, 1, growx = 1)

        result = g.runOnce ()
 
        # turn off all the packages
        for key in todo.hdList.packages.keys ():
            todo.hdList.packages[key].selected = 0

        # turn on all the packages we selected
        for package in ct.getSelection ():
            package.selected = 1

        rc = bb.buttonPressed (result)
        
        if rc == "back":
            return INSTALL_BACK

        return INSTALL_OK


class MouseWindow:
    def run(self, screen, todo):
        mice = todo.mouse.available ()
        mice.sort ()
        current = todo.mouse.get ()

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Mouse Selection"),
                                _("Which model mouse is attached to this computer?"), mice, 
                                buttons = [_("Ok"), _("Back")], width = 30, scroll = 1, height = 8)
        
        if button == string.lower (_("Back")):
            return INSTALL_BACK
        todo.mouse.set (mice[choice])
        return INSTALL_OK



class BeginInstallWindow:
    def run(self, screen, todo):
        rc = ButtonChoiceWindow(screen, _("Installation to begin"),
                                _("A complete log of your installation will be in "
                                  "/tmp/install.log after rebooting your system. You "
                                  "may want to keep this file for later reference."),
                                buttons = [ _("Ok"), _("Back") ])
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
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
	self.sizeCompleteW.setText("%10d M" % (self.sizeComplete / (1024 * 1024)))
	self.numRemainingW.setText("%12d" % (self.numTotal - self.numComplete))
	self.sizeRemainingW.setText("%10d M" % ((self.sizeTotal - self.sizeComplete) / (1024 * 1024)))
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
	self.size.setText("%d k" % (header[rpm.RPMTAG_SIZE] / 1024))
	summary = header[rpm.RPMTAG_SUMMARY]
	if (summary != None):
	    self.summ.setText(summary)
	else:
            self.summ.setText("(none)")

	self.g.draw()
	self.screen.refresh()

    def __del__(self):
        self.screen.drawRootText(0 - len(_("Package Installation")), 0,
                                 (self.screen.width - len(_("Package Installation"))) * " ")
	self.screen.popWindow()
	self.screen.refresh()
        
    def __init__(self, screen, total, totalSize):
	self.screen = screen
        self.screen.drawRootText(0 - len(_("Package Installation")), 0, _("Package Installation"))
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
	self.total = Scale (width, totalSize)
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


class Flag:
    """a quick mutable boolean class"""
    def __init__(self, value = 0):
        self.flag = value

    def set(self, value):
        self.flag = value;

    def get(self):
        return self.flag

class InstallInterface:
    def messageWindow(self, title, text):
        self.screen.drawRootText(0 - len(title), 0, title)
	ButtonChoiceWindow(self.screen, title, text,
                           buttons = [ _("Ok") ])
        self.screen.drawRootText(0 - len(title), 0,
                                 (self.screen.width - len(title)) * " ")
    
    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def packageProgressWindow(self, total, totalSize):
	return InstallProgressWindow(self.screen, total, totalSize)

    def exceptionWindow(self, (type, value, tb)):
        import traceback
        list = traceback.format_exception (type, value, tb)
        text = string.joinfields (list, "")
        ButtonChoiceWindow(self.screen, _("Exception occured"), 
                           text, buttons = [_("Exit")],
                           width = 70)
        self.screen.finish ()

    def __init__(self):
        self.screen = SnackScreen()
        self.welcomeText = _("Red Hat Linux (C) 1999 Red Hat, Inc.")
        self.screen.drawRootText (0, 0, self.welcomeText)
        self.screen.pushHelpLine (_("  <Tab>/<Alt-Tab> between elements   |  <Space> selects   |  <F12> next screen"))
	self.screen.suspendCallback(killSelf, self.screen)

    def __del__(self):
        self.screen.finish()

    def run(self, todo):
        individual = Flag(0)
        steps = [
            [_("Language Selection"), LanguageWindow, (self.screen, todo)],
            [_("Keyboard Selection"), KeyboardWindow, (self.screen, todo)],
            [_("Welcome"), WelcomeWindow, (self.screen,)],
            [_("Partition"), PartitionWindow, (self.screen, todo)],
            [_("Network Setup"), NetworkWindow, (self.screen, todo)],
            [_("Package Groups"), PackageGroupWindow, (self.screen, todo, individual)],
            [_("Individual Packages"), IndividualPackageWindow, (self.screen, todo, individual)],
            [_("Mouse Configuration"), MouseWindow, (self.screen, todo)],
            [_("Root Password"), RootPasswordWindow, (self.screen, todo)],
            [_("Installation Begins"), BeginInstallWindow, (self.screen, todo)],
        ]
        
        step = 0
        dir = 1

        while step >= 0 and step < len(steps) and steps[step]:
            # clear out the old root text by writing spaces in the blank
            # area on the right side of the screen
            self.screen.drawRootText(len(self.welcomeText), 0,
                                     (self.screen.width - len(self.welcomeText)) * " ")
            self.screen.drawRootText(0 - len(steps[step][0]), 0, steps[step][0])
            rc = apply(steps[step][1]().run, steps[step][2])
            if rc == -1:
                dir = -1
            elif rc == 0:
                dir = 1
            step = step + dir
                
        todo.setLiloLocation("hda")

def killSelf(screen):
    screen.finish()
    os._exit(0)



