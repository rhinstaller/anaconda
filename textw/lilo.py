import gettext
from snack import *
from textw.constants import *

cat = gettext.Catalog ("anaconda", "/usr/share/locale")
_ = cat.gettext

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
	    todo.liloDevice = None
	else:
	    todo.skipLilo = 0

	return INSTALL_OK

class LiloWindow:
    def __call__(self, screen, todo):
        if '/' not in todo.mounts.keys (): return INSTALL_NOOP
	if todo.skipLilo: return INSTALL_NOOP

	(bootpart, boothd) = todo.getLiloOptions()

	if (todo.getLiloLocation () == "mbr"):
	    default = 0
	elif (todo.getLiloLocation () == "partition"):
	    default = 1
	else:
	    default = 0
            
        format = "/dev/%-11s %s" 
        locations = []
        locations.append (format % (boothd, "Master Boot Record (MBR)"))
        locations.append (format % (bootpart, "First sector of boot partition"))

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
		screen.popWindow ()
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

	for n in sortedKeys:
	    (label, type) = images[n]
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

