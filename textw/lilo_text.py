#import gettext
from snack import *
from constants_text import *
from translate import _
from flags import flags
import string
import iutil
if iutil.getArch() == 'i386':
    import edd
    
#cat = gettext.Catalog ("anaconda", "/usr/share/locale")
#_ = cat.gettext

class LiloAppendWindow:

    def __call__(self, screen, dispatch, bl, fsset, diskSet):
	t = TextboxReflowed(53,
		     _("A few systems will need to pass special options "
		       "to the kernel at boot time for the system to function "
		       "properly. If you need to pass boot options to the "
		       "kernel, enter them now. If you don't need any or "
		       "aren't sure, leave this blank."))

        cb = Checkbox(_("Use LILO bootloader (instead of Grub)"),
		      isOn = not bl.useGrub())
	entry = Entry(48, scroll = 1, returnExit = 1)
	entry.set(bl.args.get())

	buttons = ButtonBar(screen, [TEXT_OK_BUTTON, (_("Skip"), "skip"),  
			     TEXT_BACK_BUTTON ] )

	grid = GridFormHelp(screen, _("Bootloader Configuration"), "kernelopts", 1, 4)
	grid.add(t, 0, 0, padding = (0, 0, 0, 1))

	if not edd.detect():
	    grid.add(cb, 0, 1, padding = (0, 0, 0, 1))

	grid.add(entry, 0, 2, padding = (0, 0, 0, 1))
	grid.add(buttons, 0, 3, growx = 1)

        result = grid.runOnce ()
        button = buttons.buttonPressed(result)
        
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

	if button == "skip":
            rc = ButtonChoiceWindow(screen, _("Skip Bootloader"),
				_("You have elected to not install "
				  "any bootloader. It is strongly recommended "
				  "that you install a bootloader unless "
				  "you have an advanced need.  A bootloader "
				  "is almost always required in order "
				  "to reboot your system into Linux "
				  "directly from the hard drive.\n\n"
				  "Are you sure you want to skip bootloader "
				  "installation?"),
				[ (_("Yes"), "yes"), (_("No"), "no") ],
				width = 50)
	    dispatch.skipStep("instbootloader", skip = (rc == "yes"))
	else:
	    dispatch.skipStep("instbootloader", 0)

	bl.args.set(entry.value())
	bl.setUseGrub(not cb.value())

	return INSTALL_OK

class LiloWindow:
    def __call__(self, screen, dispatch, bl, fsset, diskSet):
	if dispatch.stepInSkipList("instbootloader"): return INSTALL_NOOP

	choices = fsset.bootloaderChoices(diskSet)
	if len(choices) == 1:
	    bl.setDevice(choices[0][0])
	    return INSTALL_NOOP

        format = "/dev/%-11s %s" 
        locations = []
	default = 0
	for (device, desc) in choices:
	    if device == bl.getDevice():
		default = len(locations)
	    locations.append (format % (device, _(desc)))

        (rc, sel) = ListboxChoiceWindow (screen, _("Bootloader Configuration"),
			 _("Where do you want to install the bootloader?"),
			 locations, default = default,
			 buttons = [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON ],
			 help = "lilolocation")

        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK

	bl.setDevice(choices[sel][0])

        return INSTALL_OK

class LiloImagesWindow:
    def validLiloLabel(self, label):
        i=0
        while i < len(label):
            cur = label[i]
            if cur == ' ' or cur == '#' or cur == '$' or cur == '=':
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

	g = GridFormHelp(screen, _("Edit Boot Label Please"), "bootlabel", 1, 2)
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
                elif not self.validLiloLabel(newLabel.value()):
                    ButtonChoiceWindow (screen, _("Invalid Boot Label"),
                                        _("Boot label contains "
                                          "illegal characters."),
                                        [ TEXT_OK_BUTTON ])
                    result = ""

	screen.popWindow()

	return newLabel.value()

    def formatDevice(self, type, label, device, default):
	if (type == "ext2"):
	    type = "Linux Native"
	elif (type == "FAT"):
	    type = "DOS/Windows"
	elif (type == "ntfs" or type == "hpfs"):	
	    type = "OS/2 / Windows NT"
	else:
	    type = "Other"

	if default == device:
	    default = '*'
	else:
	    default = ""
	    
	return "%-10s  %-25s %-7s %-10s" % ( "/dev/" + device, type, default, label)

    def __call__(self, screen, dispatch, bl, fsset, diskSet):
	if dispatch.stepInSkipList("instbootloader"): return INSTALL_NOOP

	images = bl.images.getImages()
	default = bl.images.getDefault()

	listboxLabel = Label("%-10s  %-25s %-7s %-10s" % 
		( _("Device"), _("Partition type"), _("Default"), _("Boot label")))
	listbox = Listbox(5, scroll = 1, returnExit = 1)

	sortedKeys = images.keys()
	sortedKeys.sort()

	for dev in sortedKeys:
	    (label, type) = images[dev]
	    listbox.append(self.formatDevice(type, label, dev, default), dev)

	listbox.setCurrent(dev)

	buttons = ButtonBar(screen, [ TEXT_OK_BUTTON, (_("Edit"), "edit"), 
				      TEXT_BACK_BUTTON ] )

	text = TextboxReflowed(55,
		    _("The boot manager Red Hat uses can boot other " 
		      "operating systems as well. You need to tell me " 
		      "what partitions you would like to be able to boot " 
		      "and what label you want to use for each of them."))

	g = GridFormHelp(screen, _("Bootloader Configuration"), 
			 "lilolabels", 1, 4)
	g.add(text, 0, 0, anchorLeft = 1)
	g.add(listboxLabel, 0, 1, padding = (0, 1, 0, 0), anchorLeft = 1)
	g.add(listbox, 0, 2, padding = (0, 0, 0, 1), anchorLeft = 1)
	g.add(buttons, 0, 3, growx = 1)
	g.addHotKey(" ")

	rootdev = fsset.getEntryByMountPoint("/").device.getDevice()

	result = None
	while (result != TEXT_OK_CHECK and result != TEXT_BACK_CHECK and result != TEXT_F12_CHECK):
	    result = g.run()
	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if (result == "edit" or result == listbox):
		item = listbox.current()
		(label, type) = images[item]

		label = self.editItem(screen, item, label, allowNone = (rootdev != item and item != default))
		images[item] = (label, type)
		if (default == item and not label):
		    default = ""
		listbox.replace(self.formatDevice(type, label, item, default), item)
		listbox.setCurrent(item)
#	    elif result == "F2":
	    elif result == " ":
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

	if (result == TEXT_BACK_CHECK):
	    return INSTALL_BACK

	for (dev, (label, type)) in images.items():
	    bl.images.setImageLabel(dev, label)
	bl.images.setDefault(default)

	return INSTALL_OK

