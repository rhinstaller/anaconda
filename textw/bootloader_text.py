#
# bootloader_text.py: text mode bootloader setup
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
from constants import *
from constants_text import *
from rhpl.translate import _
from flags import flags
import string
import iutil
import bootloader

class BootloaderChoiceWindow:

    def __call__(self, screen, anaconda):
        # XXX need more text here
        t = TextboxReflowed(53,
                   _("Which boot loader would you like to use?"))

        if anaconda.dispatch.stepInSkipList("instbootloader"):
            useGrub = 0
            noBl = 1
        else:
            useGrub = 1
            noBl = 0

        blradio = RadioGroup()
        grub = blradio.add(_("Use GRUB Boot Loader"), "grub", useGrub)
        skipbl = blradio.add(_("No Boot Loader"), "nobl", noBl)
	buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON ] )

        grid = GridFormHelp(screen, _("Boot Loader Configuration"),
                            "btloadinstall", 1, 5)
        grid.add(t, 0, 0, (0,0,0,1))
        grid.add(grub, 0, 1, (0,0,0,0))
        grid.add(skipbl, 0, 3, (0,0,0,1))
        grid.add(buttons, 0, 4, growx = 1)

        while 1:
            result = grid.run()

            button = buttons.buttonPressed(result)
        
            if button == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK        

            if blradio.getSelection() == "nobl":
                rc = ButtonChoiceWindow(screen, _("Skip Boot Loader"),
				_("You have elected to not install "
				  "any boot loader. It is strongly recommended "
				  "that you install a boot loader unless "
				  "you have an advanced need.  A boot loader "
				  "is almost always required in order "
				  "to reboot your system into Linux "
				  "directly from the hard drive.\n\n"
				  "Are you sure you want to skip boot loader "
				  "installation?"),
				[ (_("Yes"), "yes"), (_("No"), "no") ],
				width = 50)
                if rc == "no":
                    continue
                anaconda.dispatch.skipStep("instbootloader", skip = (rc == "yes"))
                anaconda.dispatch.skipStep("bootloaderadvanced", skip = (rc == "yes"))

                # kind of a hack...
                anaconda.id.bootloader.defaultDevice = None
            else:
                anaconda.id.bootloader.setUseGrub(1)
                anaconda.dispatch.skipStep("instbootloader", 0)
                anaconda.dispatch.skipStep("bootloaderadvanced", 0)                

            screen.popWindow()
            return INSTALL_OK
        

class BootloaderAppendWindow:

    def __call__(self, screen, anaconda):
	if anaconda.dispatch.stepInSkipList("instbootloader"): return INSTALL_NOOP
        
	t = TextboxReflowed(53,
		     _("A few systems will need to pass special options "
		       "to the kernel at boot time for the system to function "
		       "properly. If you need to pass boot options to the "
		       "kernel, enter them now. If you don't need any or "
		       "aren't sure, leave this blank."))

	entry = Entry(48, scroll = 1, returnExit = 1)
	entry.set(anaconda.id.bootloader.args.get())

        cb = Checkbox(_("Force use of LBA32 (not normally required)"))
        if anaconda.id.bootloader.forceLBA32:
            cb.setValue("*")

	buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON ] )

	grid = GridFormHelp(screen, _("Boot Loader Configuration"), "kernelopts", 1, 5)
	grid.add(t, 0, 0, padding = (0, 0, 0, 1))

	grid.add(entry, 0, 2, padding = (0, 0, 0, 1))
        grid.add(cb, 0, 3, padding = (0,0,0,1))
	grid.add(buttons, 0, 4, growx = 1)

        while 1:
            result = grid.run()
            button = buttons.buttonPressed(result)

            if button == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            if cb.selected() and not anaconda.id.bootloader.forceLBA32:
                rc = anaconda.intf.messageWindow(_("Warning"),
                        _("Forcing the use of LBA32 for your bootloader when "
                          "not supported by the BIOS can cause your machine "
                          "to be unable to boot.\n\n"                          
                          "Would you like to continue and force LBA32 mode?"),
                                             type = "yesno")

                if rc != 1:
                    continue

            anaconda.id.bootloader.args.set(entry.value())
            anaconda.id.bootloader.setForceLBA(cb.selected())

            screen.popWindow()
            return INSTALL_OK

class BootloaderLocationWindow:
    def __call__(self, screen, anaconda):
	if anaconda.dispatch.stepInSkipList("instbootloader"): return INSTALL_NOOP

	choices = anaconda.id.fsset.bootloaderChoices(anaconda.id.diskset, anaconda.id.bootloader)
	if len(choices.keys()) == 1:
	    anaconda.id.bootloader.setDevice(choices[choices.keys()[0]][0])
	    return INSTALL_NOOP
        if len(choices.keys()) == 0:
            return INSTALL_NOOP

        format = "/dev/%-11s %s" 
        locations = []
        devices = []
	default = 0

        keys = choices.keys()
        keys.reverse()
        for key in keys:
            (device, desc) = choices[key]
	    if device == anaconda.id.bootloader.getDevice():
		default = len(locations)
            locations.append (format % (device, _(desc)))
            devices.append(device)

        (rc, sel) = ListboxChoiceWindow (screen, _("Boot Loader Configuration"),
			 _("Where do you want to install the boot loader?"),
			 locations, default = default,
			 buttons = [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON ],
			 help = "bootloaderlocation")

        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK

	anaconda.id.bootloader.setDevice(devices[sel])

        return INSTALL_OK

class BootloaderImagesWindow:
    def validBootloaderLabel(self, label):
        i=0
        while i < len(label):
            cur = label[i]
            if cur == '#' or cur == '$' or cur == '=':
                return 0
            elif cur == ' ' and not self.bl.useGrub():
                return 0
            i = i + 1

        return 1

    
    def editItem(self, screen, partition, itemLabel, allowNone=0):
	devLabel = Label(_("Device") + ":")
	bootLabel = Label(_("Boot label") + ":")
	device = Label("/dev/" + partition)
        newLabel = Entry (20, scroll = 1, returnExit = 1, text = itemLabel)

	buttons = ButtonBar(screen, [TEXT_OK_BUTTON, (_("Clear"), "clear"),
			    (_("Cancel"), "cancel")])

	subgrid = Grid(2, 2)
	subgrid.setField(devLabel, 0, 0, anchorLeft = 1)
	subgrid.setField(device, 1, 0, padding = (1, 0, 0, 0), anchorLeft = 1)
	subgrid.setField(bootLabel, 0, 1, anchorLeft = 1)
	subgrid.setField(newLabel, 1, 1, padding = (1, 0, 0, 0), anchorLeft = 1)
	g = GridFormHelp(screen, _("Edit Boot Label"), "bootlabel", 1, 2)
	g.add(subgrid, 0, 0, padding = (0, 0, 0, 1))
	g.add(buttons, 0, 1, growx = 1)

	result = ""
	while (result != TEXT_OK_CHECK and result != TEXT_F12_CHECK and result != newLabel):
	    result = g.run()

	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if (result == "cancel"):
		screen.popWindow ()
		return itemLabel
	    elif (result == "clear"):
		newLabel.set("")
            elif (result == TEXT_OK_CHECK or result == TEXT_F12_CHECK or result == newLabel):
		if not allowNone and not newLabel.value():
                    ButtonChoiceWindow (screen, _("Invalid Boot Label"),
                                        _("Boot label may not be empty."),
                                        [ TEXT_OK_BUTTON ])
                    result = ""
                elif not self.validBootloaderLabel(newLabel.value()):
                    ButtonChoiceWindow (screen, _("Invalid Boot Label"),
                                        _("Boot label contains "
                                          "illegal characters."),
                                        [ TEXT_OK_BUTTON ])
                    result = ""

	screen.popWindow()

	return newLabel.value()

    def formatDevice(self, label, device, default):
	if default == device:
	    default = '*'
	else:
	    default = ""

        if not label:
            label = ""
	    
	return "   %-4s  %-25s %-25s" % ( default, label, "/dev/" + device)

    def __call__(self, screen, anaconda):
	if anaconda.dispatch.stepInSkipList("instbootloader"): return INSTALL_NOOP
        
        self.bl = anaconda.id.bootloader

	images = self.bl.images.getImages()
	default = self.bl.images.getDefault()

	listboxLabel = Label(     "%-7s  %-25s %-12s" % 
		( _("Default"), _("Boot label"), _("Device")))
	listbox = Listbox(5, scroll = 1, returnExit = 1)

	sortedKeys = images.keys()
	sortedKeys.sort()

	for dev in sortedKeys:
	    (label, longlabel, isRoot) = images[dev]
            if not self.bl.useGrub():
                listbox.append(self.formatDevice(label, dev, default), dev)
            else:
                listbox.append(self.formatDevice(longlabel, dev, default), dev)                

	listbox.setCurrent(dev)

	buttons = ButtonBar(screen, [ TEXT_OK_BUTTON, (_("Edit"), "edit"), 
				      TEXT_BACK_BUTTON ] )

	text = TextboxReflowed(55,
		    _("The boot manager %s uses can boot other " 
		      "operating systems as well. You need to tell me " 
		      "what partitions you would like to be able to boot " 
		      "and what label you want to use for each of them.") % (productName,))

	g = GridFormHelp(screen, _("Boot Loader Configuration"), 
			 "bootloaderlabels", 1, 4)
	g.add(text, 0, 0, anchorLeft = 1)
	g.add(listboxLabel, 0, 1, padding = (0, 1, 0, 0), anchorLeft = 1)
	g.add(listbox, 0, 2, padding = (0, 0, 0, 1), anchorLeft = 1)
	g.add(buttons, 0, 3, growx = 1)
        g.addHotKey("F2")
        g.addHotKey("F4")
        screen.pushHelpLine(_(" <Space> select | <F2> select default | <F4> delete | <F12> next screen>"))        

	rootdev = anaconda.id.fsset.getEntryByMountPoint("/").device.getDevice()

	result = None
	while (result != TEXT_OK_CHECK and result != TEXT_BACK_CHECK and result != TEXT_F12_CHECK):
	    result = g.run()
	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if (result == "edit" or result == listbox):
		item = listbox.current()
		(label, longlabel, type) = images[item]
                if self.bl.useGrub():
                    label = longlabel
                if label == None:
                    label = ""

		label = self.editItem(screen, item, label, allowNone = (rootdev != item and item != default))
		images[item] = (label, label, type)
		if (default == item and not label):
		    default = ""
		listbox.replace(self.formatDevice(label, item, default), item)
		listbox.setCurrent(item)
	    elif result == "F2":
		item = listbox.current()
		(label, longlabel, isRoot) = images[item]
                if self.bl.useGrub():
                    label = longlabel
                
		if (label):
		    if (default):
			(oldLabel, oldLong, oldIsRoot) = images[default]
                        if self.bl.useGrub():
                            oldLabel = oldLong
			listbox.replace(self.formatDevice(oldLabel, default, 
					""), default)
		    default = item
		    listbox.replace(self.formatDevice(label, item, default), 
				    item)
		    listbox.setCurrent(item)
            elif result == "F4":
                item = listbox.current()
                
                (label, longlabel, isRoot) = images[item]
                if rootdev != item:
                    del images[item]
                    listbox.delete(item)
                    if default == item:
                        default = ""
                else:
                    anaconda.intf.messageWindow(_("Cannot Delete"),
                                       _("This boot target cannot be "
                                         "deleted because it is for "
                                         "the %s system you are about "
                                         "to install.")
                                       %(productName,))
                    

        screen.popHelpLine()
	screen.popWindow()

	if (result == TEXT_BACK_CHECK):
	    return INSTALL_BACK

        if not default:
            default = rootdev

        # copy our version over
        self.bl.images.images = {}
	for (dev, (label, longlabel, isRoot)) in images.items():
            self.bl.images.images[dev] = (label, longlabel, isRoot)
	self.bl.images.setDefault(default)

	return INSTALL_OK

class BootloaderPasswordWindow:
    def usepasscb(self, *args):
        flag = FLAGS_RESET
        if not self.checkbox.selected():
            flag = FLAGS_SET
        self.entry1.setFlags(FLAG_DISABLED, flag)
        self.entry2.setFlags(FLAG_DISABLED, flag)        
        
    def __call__(self, screen, anaconda):
	if anaconda.dispatch.stepInSkipList("instbootloader"): return INSTALL_NOOP

        intf = anaconda.intf
        self.bl = anaconda.id.bootloader

        if not self.bl.useGrub():
            return INSTALL_NOOP

	buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON])

	text = TextboxReflowed(55,
		    _("A boot loader password prevents users from passing arbitrary "
                      "options to the kernel.  For highest security, we "
                      "recommend setting a password, but this is not "
                      "necessary for more casual users."))

	g = GridFormHelp(screen, _("Boot Loader Configuration"), 
			 "grubpasswd", 1, 6)
	g.add(text, 0, 0, (0,0,0,1), anchorLeft = 1)


        self.checkbox = Checkbox(_("Use a GRUB Password"))
        g.add(self.checkbox, 0, 1, (0,0,0,1))

        if self.bl.password:
            self.checkbox.setValue("*")

        pw = self.bl.pure
	if not pw: pw = ""

        self.entry1 = Entry (24, password = 1, text = pw)
        self.entry2 = Entry (24, password = 1, text = pw)
        passgrid = Grid (2, 2)
        passgrid.setField (Label (_("Boot Loader Password:")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (Label (_("Confirm:")), 0, 1, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (self.entry1, 1, 0)
        passgrid.setField (self.entry2, 1, 1)
        g.add (passgrid, 0, 2, (0, 0, 0, 1))

        self.checkbox.setCallback(self.usepasscb, None)
        self.usepasscb()

        g.add(buttons, 0, 3, growx=1)

        while 1:
            result = g.run()

	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if result == TEXT_BACK_CHECK:
		screen.popWindow()
                return INSTALL_BACK

            if not self.checkbox.selected():
                self.bl.setPassword(None)
                screen.popWindow()
                return INSTALL_OK

            pw = self.entry1.value()
            confirm = self.entry2.value()

            if pw != confirm:
                anaconda.intf.messageWindow(_("Passwords Do Not Match"),
                        _("Passwords do not match"))
                continue

            if len(pw) < 1:
                anaconda.intf.messageWindow(_("Password Too Short"),
                        _("Boot loader password is too short"))
                continue

            if len(pw) < 6:
                rc = anaconda.intf.messageWindow(_("Warning"),
                                    _("Your boot loader password is less than "
                                      "six characters.  We recommend a longer "
                                      "boot loader password."
                                      "\n\n"
                                      "Would you like to continue with this "
                                      "password?"),
                                    type = "yesno")
                if rc == 0:
                    continue

            self.bl.setPassword(pw, isCrypted = 0)            

            screen.popWindow()
            return INSTALL_OK
