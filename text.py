from snack import *
import sys
import isys
import os
import iutil
import rpm
import time
import gettext
import glob
from newtpyfsedit import fsedit        
import installclass

INSTALL_OK = 0
INSTALL_BACK = -1
INSTALL_NOOP = -2

cat = gettext.Catalog ("anaconda", "/usr/share/locale")
_ = cat.gettext

class LanguageWindow:
    def __call__(self, screen, todo):
        languages = todo.language.available ()
        descriptions = languages.keys ()
        locales = languages.values ()
        default = locales.index (todo.language.get ())

        (button, choice) = \
            ListboxChoiceWindow(screen, _("Language Selection"),
                                _("What language would you like to use during the "
                                  "installation process?"), descriptions, 
                                buttons = [_("OK")], width = 30, default = default)
        langs = gettext.getlangs ()
        langs = [languages [languages.keys()[choice]]] + langs
        gettext.setlangs (langs)
        global cat, _
        cat = gettext.Catalog ("anaconda-text", "/usr/share/locale")
        _ = cat.gettext
        todo.language.set (languages.keys()[choice])
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
        mice = todo.mouse.available ().keys ()
        mice.sort ()
	(default, emulate) = todo.mouse.get ()
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

	choices = [ _("Install GNOME Workstation"), 
		    _("Install KDE Workstation"),
		    _("Install Server System"),
		    _("Install Custom System"),
		    _("Upgrade Existing Installation") ]
	(button, choice) = ListboxChoiceWindow(screen, _("Installation Type"),
			_("What type of system would you like to install?"),
			    choices, [(_("OK"), "ok"), (_("Back"), "back")],
			    width = 40)

        if button == "back":
            return INSTALL_BACK
	if (choice == 4):
            intf.steps = intf.commonSteps + intf.upgradeSteps
            todo.upgrade = 1
        else:
            intf.steps = intf.commonSteps + intf.installSteps
            todo.upgrade = 0
	    if (choice == 0):
		todo.setClass(installclass.Workstation())
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

        
class RootPasswordWindow:
    def __call__ (self, screen, todo):
        toplevel = GridForm (screen, _("Root Password"), 1, 3)

        toplevel.add (TextboxReflowed(37, _("Pick a root password. You must "
				"type it twice to ensure you know "
				"what it is and didn't make a mistake "
				"in typing. Remember that the "
				"root password is a critical part "
				"of system security!")), 0, 0, (0, 0, 0, 1))

	pw = todo.rootpassword.getPure()
	if not pw: pw = ""

        entry1 = Entry (24, hidden = 1, text = pw)
        entry2 = Entry (24, hidden = 1, text = pw)
        passgrid = Grid (2, 2)
        passgrid.setField (Label (_("Password:")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (Label (_("Password (again):")), 0, 1, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (entry1, 1, 0)
        passgrid.setField (entry2, 1, 1)
        toplevel.add (passgrid, 0, 1, (0, 0, 0, 1))
        
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))
        toplevel.add (bb, 0, 2, growx = 1)

        while 1:
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

            entry1.set ("")
            entry2.set ("")

        screen.popWindow()
        todo.rootpassword.set (entry1.value ())
        return INSTALL_OK

class UsersWindow:
    def editWindow (self, user, text, edit = 0, cancelText = None):
	if (not cancelText):
	    cancelText = _("Cancel")

        userid = Entry (8, user["id"])
        currentid = user["id"]
        fullname = Entry (20, user["name"], scroll = 1)
        pass1 = Entry (10, user["password"], hidden = 1)
        pass2 = Entry (10, user["password"], hidden = 1)

	if edit:
	    title = _("Edit User")
	else:
	    title = _("Add User")

        while 1:
                
            (rc, ent) = EntryWindow (self.screen, title, text,
			 [ (_("User ID"), userid),
			   (_("Full Name"), fullname),
			   (_("Password"), pass1),
			   (_("Password (confirm)"), pass2) ],
			 buttons = [ (_("OK"), "ok"), (cancelText, "cancel") ])
            
            if rc == "cancel":
                return INSTALL_BACK
	    if not len(pass1.value()) and not len(pass2.value()) and \
	       not len(userid.value()) and not len(fullname.value()):
                return INSTALL_OK

	    if len (pass1.value ()) < 6:
		ButtonChoiceWindow(self.screen, _("Password Length"),
		       _("The password must be at least 6 characters "
			 "long."),
		       buttons = [ _("OK") ], width = 50)
		pass1.set ("")
		pass2.set ("")
		continue
	    elif pass1.value () != pass2.value ():
		ButtonChoiceWindow(self.screen, _("Password Mismatch"),
		   _("The passwords you entered were different. Please "
		     "try again."),
		   buttons = [ _("OK") ], width = 50)
		pass1.set ("")
		pass2.set ("")
		continue

            if self.users.has_key (userid.value ()) and  \
				   userid.value () != currentid:
                ButtonChoiceWindow(self.screen, _("User Exists"),
		       _("This user id already exists.  Choose another."),
			 buttons = [ _("OK") ], width = 50)
                continue

            # XXX FIXME - more data validity checks
            
            user["id"] = userid.value ()
            user["name"] = fullname.value ()
            user["password"] = pass1.value ()
            break

	return INSTALL_OK

    def __call__ (self, screen, todo):
        self.users = {}
        self.screen = screen
	user = { "id" : "", "name" : "", "password" : "" }

	for (account, name, password) in todo.getUserList():
	    user['id'] = account
	    user['name'] = name
	    user['password'] = password
	    self.users[account] = user
	    del user
	    user = { "id" : "", "name" : "", "password" : "" }

	if not self.users.keys():
	    rc = self.editWindow(user, _("You should use a normal user "
		"account for most activities on your system. By not using the "
		"root account casually, you'll reduce the chance of "
		"disrupting your system's configuration."), 
		cancelText = _("Back"))
	    if (rc == INSTALL_BACK):
		return INSTALL_BACK
	    if (not user['id']):
		return INSTALL_OK
	    self.users[user["id"]] = user
        
        g = GridForm (screen, _("User Account Setup"), 1, 4)

	t = TextboxReflowed(60, _("What user account would you like to have "
	    "on the system? You should have at least one non-root account "
	    "for normal work, but multi-user systems can have any number "
	    "of accounts set up."))
	g.add(t, 0, 0, anchorLeft = 1, padding = (0, 0, 0, 1))

        listformat = "%-15s  %-40s"
        userformat = "%(id)-15s  %(name)-40s"

	subgrid = Grid(1, 2)
        header = listformat % (_("User name"), _("Full Name"))
        label = Label (header)
        subgrid.setField (label, 0, 0, anchorLeft = 1)
        listbox = Listbox (5, scroll = 1, returnExit = 1, width = 54)
        subgrid.setField (listbox, 0, 1, (0, 0, 0, 1), anchorLeft = 1)

	g.add(subgrid, 0, 1)

        for user in self.users.values ():
            listbox.append (userformat % user, user["id"])

        bb = ButtonBar (screen, ((_("Add"), "add"), (_("Delete"), "delete"),
                                 (_("Edit"), "edit"), (_("OK"), "ok"), (_("Back"), "back")))
        
        g.add (bb, 0, 3, growx = 1)

        while 1:
            result = g.run ()
            
            rc = bb.buttonPressed (result)

            if rc == "add":
                user = { "id" : "", "name" : "", "password" : "" }
                self.editWindow (user, 
		    _("Enter the information for the user."), 0)
                listbox.append (userformat % user, user["id"])
                listbox.setCurrent (user["id"])
                self.users[user["id"]] = user
            elif rc == "delete":
                current = listbox.current ()
                listbox.delete (current)
                del self.users [current]
            elif rc == "edit" or result == listbox:
		current = listbox.current()
                user = self.users[current]
                self.editWindow (user, 
			_("Change the information for this user."), 1)
                # if the user id changed, we need to delete the old key
                # and insert this new one.
                if user["id"] != current:
                    del self.users [current]
                    listbox.insert (userformat % user, user["id"], current)
                    listbox.delete (current)
                # and if the user id didn't change, just replace the old
                # listbox entry.
                else:
                    listbox.replace (userformat % user, user["id"])
                self.users [user["id"]] = user
		listbox.setCurrent(user["id"])
            elif rc == "ok" or result == "F12":
                dir = INSTALL_OK
                break
            elif rc == "back":
                dir = INSTALL_BACK
                break
            else:
                raise NeverGetHereError, "I shouldn't be here w/ rc %s..." % rc
                
        screen.popWindow ()

        list = []
        for n in self.users.values():
	    info = ( n['id'], n['name'], n['password'] )
	    list.append(info)

	todo.setUserList(list)

        return dir

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

class AuthConfigWindow:
    def __call__(self, screen, todo):
        def setsensitive (self):
            server = FLAGS_RESET
            flag = FLAGS_RESET
            if self.broadcast.selected ():
                server = FLAGS_SET
            if not self.nis.selected ():
                flag = FLAGS_SET
                server = FLAGS_SET
            
            self.domain.setFlags (FLAG_DISABLED, flag)
            self.broadcast.setFlags (FLAG_DISABLED, flag)
            self.server.setFlags (FLAG_DISABLED, server)
        
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        toplevel = GridForm (screen, _("Authentication Configuration"), 1, 5)
        self.shadow = Checkbox (_("Use Shadow Passwords"), todo.auth.useShadow)
        toplevel.add (self.shadow, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        self.md5 = Checkbox (_("Enable MD5 Passwords"), todo.auth.useMD5)
        toplevel.add (self.md5, 0, 1, (0, 0, 0, 1), anchorLeft = 1)
        self.nis = Checkbox (_("Enable NIS"), todo.auth.useNIS)
        toplevel.add (self.nis, 0, 2, anchorLeft = 1)

        subgrid = Grid (2, 3)

        subgrid.setField (Label (_("NIS Domain:")),
                          0, 0, (0, 0, 1, 0), anchorRight = 1)
        subgrid.setField (Label (_("NIS Server:")),
                          0, 1, (0, 0, 1, 0), anchorRight = 1)
        subgrid.setField (Label (_("or use:")),
                          0, 2, (0, 0, 1, 0), anchorRight = 1)

        text = _("Request server via broadcast")
        self.domain = Entry (len (text) + 4)
        self.domain.set (todo.auth.domain)
        self.broadcast = Checkbox (text, todo.auth.useBroadcast)
        self.server = Entry (len (text) + 4)
        self.server.set (todo.auth.server)
        subgrid.setField (self.domain, 1, 0, anchorLeft = 1)
        subgrid.setField (self.broadcast, 1, 1, anchorLeft = 1)
        subgrid.setField (self.server, 1, 2, anchorLeft = 1)
        toplevel.add (subgrid, 0, 3, (2, 0, 0, 1))
        toplevel.add (bb, 0, 4, growx = 1)

        self.nis.setCallback (setsensitive, self)
        self.broadcast.setCallback (setsensitive, self)

        setsensitive (self)

        result = toplevel.runOnce ()

        todo.auth.useMD5 = self.md5.value ()
        todo.auth.shadow = self.shadow.value ()
        todo.auth.useNIS = self.nis.selected ()
        todo.auth.domain = self.domain.value ()
        todo.auth.useBroadcast = self.broadcast.selected ()
        todo.auth.server = self.server.value ()
                
        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

class NetworkWindow:
    def __call__(self, screen, todo):
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

class PartitionWindow:
    def __call__(self, screen, todo):
	#if (not todo.setupFilesystems): return INSTALL_NOOP

        fstab = []
        for mntpoint, (dev, fstype, reformat) in todo.mounts.items ():
            fstab.append ((dev, mntpoint))

        if not todo.ddruid:
            drives = todo.drives.available ().keys ()
            drives.sort ()
            todo.ddruid = fsedit(0, drives, fstab)

	dir = INSTALL_NOOP
	todo.instClass.finishPartitioning(todo.ddruid)
	if not todo.instClass.skipPartitioning:
	    dir = todo.ddruid.edit ()

	for partition, mount, fstype, size in todo.ddruid.getFstab ():
	    todo.addMount(partition, mount, fstype)
                
        return dir


class FormatWindow:
    def __call__(self, screen, todo):
        tb = TextboxReflowed (55,
                              _("What partitions would you like to "
                                "format? We strongly suggest formatting "
                                "all of the system partitions, including "
                                "/, /usr, and /var. There is no need to "
                                "format /home or /usr/local if they have "
                                "already been configured during a "
                                "previous install."))

        height = min (screen.height - 12, len (todo.mounts.items()))
        
        ct = CheckboxTree(height = height)

        mounts = todo.mounts.keys ()
        mounts.sort ()

        for mount in mounts:
            (dev, fstype, format) = todo.mounts[mount]
            if fstype == "ext2":
                ct.append("/dev/%s   %s" % (dev, mount), mount, format)

        cb = Checkbox (_("Check for bad blocks during format"))

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        g = GridForm (screen, _("Choose Partitions to Format"), 1, 4)
        g.add (tb, 0, 0, (0, 0, 0, 1))
        g.add (ct, 0, 1)
        g.add (cb, 0, 2, (0, 0, 0, 1))
        g.add (bb, 0, 3, growx = 1)

        result = g.runOnce()

        for mount in todo.mounts.keys ():
            (dev, fstype, format) = todo.mounts[mount]
            if fstype == "ext2":
                todo.mounts[mount] = (dev, fstype, 0)

        for mount in ct.getSelection():
            (dev, fstype, format) = todo.mounts[mount]
            todo.mounts[mount] = (dev, fstype, 1)

        todo.badBlockCheck = cb.selected ()

        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

class PackageGroupWindow:
    def __call__(self, screen, todo, individual):
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
            comp.select (1)

        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

class IndividualPackageWindow:
    def __call__(self, screen, todo, individual):
        if not individual.get():
            return
	todo.getHeaderList()
        todo.getCompsList()

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

class PackageDepWindow:
    def __call__(self, screen, todo):
        deps = todo.verifyDeps ()
        if not deps:
            return INSTALL_NOOP

        g = GridForm(screen, _("Package Dependencies"), 1, 5)
        g.add (TextboxReflowed (45, _("Some of the packages you have "
                                      "selected to install require "
                                      "packages you have not selected. If "
                                      "you just select Ok all of those "
                                      "required packages will be "
                                      "installed.")), 0, 0, (0, 0, 0, 1))
        g.add (Label ("%-20s %-20s" % (_("Package"), _("Requirement"))), 0, 1, anchorLeft = 1)
        text = ""
        for name, suggest in deps:
            text = text + "%-20s %-20s\n" % (name, suggest)
        
        if len (deps) > 5:
            scroll = 1
        else:
            scroll = 0
            
        g.add (Textbox (45, 5, text, scroll = scroll), 0, 2, anchorLeft = 1)
        
        cb = Checkbox (_("Install packages to satisfy dependencies"), 1)
        g.add (cb, 0, 3, (0, 1, 0, 1), growx = 1)
        
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))
        g.add (bb, 0, 4, growx = 1)

        result = g.runOnce ()

        if cb.selected ():
            todo.selectDeps (deps)
        
        rc = bb.buttonPressed (result)
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK

class BootDiskWindow:
    def __call__(self, screen, todo):
        rc = ButtonChoiceWindow(screen, _("Bootdisk"), 
		_("A custom bootdisk provides a way of booting into your "
		  "Linux system without depending on the normal bootloader. "
		  "This is useful if you don't want to install lilo on your "
		  "system, another operating system removes lilo, or lilo "
		  "doesn't work with your hardware configuration. A custom "
		  "bootdisk can also be used with the Red Hat rescue image, "
		  "making it much easier to recover from severe system "
		  "failures.\n\n"
		  "Would you like to create a bootdisk for your system?"),
		buttons = [ _("Yes"), _("No"), _("Back") ])
                                

        if rc == string.lower (_("Yes")):
            todo.bootdisk = 1
        
        if rc == string.lower (_("No")):
            todo.bootdisk = 0

        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK

class LiloAppendWindow:

    def __call__(self, screen, todo):
	t = TextboxReflowed(53,
		     _("A few systems will need to pass special options "
		       "to the kernel at boot time for the system to function "
		       "properly. If you need to pass boot options to the "
		       "kernel, enter them now. If you don't need any or "
		       "aren't sure, leave this blank."))

        cb = Checkbox(_("Use linear mode (needed for some SCSI drives)"))
	entry = Entry(48, scroll = 1, returnExit = 1)
	buttons = ButtonBar(screen, [(_("OK"), "ok"), (_("Skip"), "skip"),  
			     (_("Back"), "back") ] )

	grid = GridForm(screen, _("LILO Configuration"), 1, 4)
	grid.add(t, 0, 0)
	grid.add(cb, 0, 1, padding = (0, 1, 0, 1))
	grid.add(entry, 0, 2, padding = (0, 0, 0, 1))
	grid.add(buttons, 0, 3, growx = 1)

        result = grid.runOnce ()
        button = buttons.buttonPressed(result)
        
        if button == "back":
            return INSTALL_BACK

	if button == "skip":
	    todo.skipLilo = 1
	else:
	    todo.skipLilo = 0

	return INSTALL_OK

class LiloWindow:
    def __call__(self, screen, todo):
        if '/' not in todo.mounts.keys (): return INSTALL_NOOP
	if todo.skipLilo: return INSTALL_NOOP

	(bootpart, boothd) = todo.getLiloOptions()

	if (todo.getLiloLocation == "mbr"):
	    default = boothd
	elif (todo.getLiloLocation == "partition"):
	    default = bootpart
	else:
	    default = 0
            
        format = "/dev/%-11s %s" 
        locations = []
        locations.append (format % (boothd, "Master Boot Record (MBR)"))
        locations.append (format % (bootpart, "First sector of boot partition"))

        # XXX fixme restore state
        (rc, sel) = ListboxChoiceWindow (screen, _("LILO Configuration"),
                                         _("Where do you want to install the bootloader?"),
                                         locations, default = default,
                                         buttons = [ _("OK"), _("Back") ])

        if sel == 0:
            todo.setLiloLocation("mbr")
        else:
            todo.setLiloLocation("partition")

        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK

class LiloImagesWindow:
    def editItem(self, screen, partition, itemLabel):
	devLabel = Label(_("Device") + ":")
	bootLabel = Label(_("Boot label") + ":")
	device = Label("/dev/" + partition)
        newLabel = Entry (20, scroll = 1, returnExit = 1, text = itemLabel)

	buttons = ButtonBar(screen, [_("Ok"), _("Clear"), _("Cancel")])

	subgrid = Grid(2, 2)
	subgrid.setField(devLabel, 0, 0, anchorLeft = 1)
	subgrid.setField(device, 1, 0, padding = (1, 0, 0, 0), anchorLeft = 1)
	subgrid.setField(bootLabel, 0, 1, anchorLeft = 1)
	subgrid.setField(newLabel, 1, 1, padding = (1, 0, 0, 0), anchorLeft = 1)

	g = GridForm(screen, _("Edit Boot Label"), 1, 2)
	g.add(subgrid, 0, 0, padding = (0, 0, 0, 1))
	g.add(buttons, 0, 1, growx = 1)

	result = ""
	while (result != string.lower(_("Ok")) and result != newLabel):
	    result = g.run()
	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if (result == string.lower(_("Cancel"))):
		return itemLabel
	    elif (result == string.lower(_("Clear"))):
		newLabel.set("")

	screen.popWindow()

	return newLabel.value()

    def formatDevice(self, type, label, device, default):
	if (type == 2):
	    type = "Linux extended"
	elif (type == 1):
	    type = "DOS/Windows"
	elif (type == 4):	
	    type = "OS/2 / Windows NT"
	else:
	    type = "Other"

	if default == device:
	    default = '*'
	else:
	    default = ""
	    
	return "%-10s  %-25s %-7s %-10s" % ( "/dev/" + device, type, default, label)

    def __call__(self, screen, todo):
	images = todo.getLiloImages()
	if not images: return INSTALL_NOOP
	if todo.skipLilo: return INSTALL_NOOP

	sortedKeys = images.keys()
	sortedKeys.sort()

	listboxLabel = Label("%-10s  %-25s %-7s %-10s" % 
		( _("Device"), _("Partition type"), _("Default"), _("Boot label")))
	listbox = Listbox(5, scroll = 1, returnExit = 1)

	default = ""

	foundDos = 0
	for n in sortedKeys:
	    (label, type) = images[n]
	    if (type == 1):
		if (foundDos): continue
		foundDos = 1
		label = "dos"
		images[n] = (label, type)
	    listbox.append(self.formatDevice(type, label, n, default), n)

	buttons = ButtonBar(screen, [ (_("Ok"), "ok"), (_("Edit"), "edit"), 
				      (_("Back"), "back") ] )

	text = TextboxReflowed(55, _("The boot manager Red Hat uses can boot other " 
		      "operating systems as well. You need to tell me " 
		      "what partitions you would like to be able to boot " 
		      "and what label you want to use for each of them."))

	g = GridForm(screen, _("LILO Configuration"), 1, 4)
	g.add(text, 0, 0, anchorLeft = 1)
	g.add(listboxLabel, 0, 1, padding = (0, 1, 0, 0), anchorLeft = 1)
	g.add(listbox, 0, 2, padding = (0, 0, 0, 1), anchorLeft = 1)
	g.add(buttons, 0, 3, growx = 1)
	g.addHotKey("F2")

	result = None
	while (result != "ok" and result != "back" and result != "F12"):
	    result = g.run()
	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if (result == string.lower(_("Edit")) or result == listbox):
		item = listbox.current()
		(label, type) = images[item]
		label = self.editItem(screen, item, label)
		images[item] = (label, type)
		if (default == item and not label):
		    default = ""
		listbox.replace(self.formatDevice(type, label, item, default), item)
		listbox.setCurrent(item)
	    elif result == "F2":
		item = listbox.current()
		(label, type) = images[item]
		if (label):
		    if (default):
			(oldLabel, oldType) = images[default]
			listbox.replace(self.formatDevice(oldType, oldLabel, default, 
					""), default)
		    default = item
		    listbox.replace(self.formatDevice(type, label, item, default), 
				    item)
		    listbox.setCurrent(item)

	screen.popWindow()

	if (result == "back"):
	    return INSTALL_BACK

	todo.setLiloImages(images)

	return INSTALL_OK

class XConfigWindow:
    def __call__(self, screen, todo):
        todo.x.probe ()

        rc = ButtonChoiceWindow (screen, _("X probe results"),
                                 todo.x.probeReport (),
                                 buttons = [ _("OK"), _("Back") ])
        
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK


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
        todo.doInstall ()
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

	t = TextboxReflowed(width, text)

	g = GridForm(self.screen, title, 1, 1)
	g.add(t, 0, 0)
	g.draw()
	self.screen.refresh()

class TimezoneWindow:

    def getTimezoneList(self, test):
	if test:
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

	g = GridForm(screen, _("Mouse Selection"), 1, 4)
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

class InstallInterface:
    def messageWindow(self, title, text):
        self.screen.drawRootText(0 - len(title), 0, title)
	ButtonChoiceWindow(self.screen, title, text,
                           buttons = [ _("OK") ])
        self.screen.drawRootText(0 - len(title), 0,
                                 (self.screen.width - len(title)) * " ")
    
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
#	self.screen.suspendCallback(killSelf, self.screen)
	self.screen.suspendCallback(debugSelf, self.screen)
        self.individual = Flag(0)
        self.step = 0
        self.dir = 1

    def __del__(self):
        self.screen.finish()

    def run(self, todo, test = 0):
        self.commonSteps = [
            [_("Language Selection"), LanguageWindow, 
		    (self.screen, todo), "language" ],
            [_("Keyboard Selection"), KeyboardWindow, 
		    (self.screen, todo), "keyboard" ],
            [_("Welcome"), WelcomeWindow, (self.screen,), "welcome" ],
            [_("Installation Type"), InstallPathWindow, 
		    (self.screen, todo, self) ],
            ]
        
        self.installSteps = [
            [_("Partition"), PartitionWindow, (self.screen, todo),
		    "partition" ],
            [_("Filesystem Formatting"), FormatWindow, (self.screen, todo),
		    "format" ],
            [_("LILO Configuration"), LiloAppendWindow, 
		    (self.screen, todo), "lilo"],
            [_("LILO Configuration"), LiloWindow, 
		    (self.screen, todo), "lilo"],
	    [_("LILO Configuration"), LiloImagesWindow, 
		    (self.screen, todo), "lilo"],
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
                "config" ],
            [_("Boot Disk"), BootDiskWindow, (self.screen, todo),
		"bootdisk" ],
            [_("Installation Begins"), BeginInstallWindow, 
		(self.screen, todo), "begininstall" ],
            [_("Install System"), InstallWindow, (self.screen, todo) ],
            [_("Bootdisk"), BootdiskWindow, (self.screen, todo), "bootdisk"],
            [_("Installation Complete"), FinishedWindow, (self.screen,),
		"complete" ]
            ]

        self.upgradeSteps = [
            [_("Examine System"), UpgradeExamineWindow, (self.screen, todo)],
            [_("Customize Upgrade"), CustomizeUpgradeWindow, (self.screen, todo, self.individual)],            
            [_("Individual Packages"), IndividualPackageWindow, (self.screen, todo, self.individual)],
            [_("Upgrade System"), InstallWindow, (self.screen, todo)],
            [_("Upgrade Complete"), FinishedWindow, (self.screen,)]
            ]

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
		self.screen.drawRootText (len(self.welcomeText), 0,
			     (self.screen.width - len(self.welcomeText)) * " ")
		self.screen.drawRootText (0 - len(step[0]),
					 0, step[0])
		rc = apply (step[1](), step[2])

	    if rc == -1:
		dir = -1
	    elif rc == 0:
		dir = 1
	    self.step = self.step + dir
        self.screen.finish ()

def killSelf(screen):
    screen.finish()
    os._exit(0)

def debugSelf(screen):
    screen.finish ()
    import pdb
    pdb.set_trace()
