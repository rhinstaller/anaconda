#import gettext
import iutil
from snack import *
from textw.constants import *
from text import _

#cat = gettext.Catalog ("anaconda", "/usr/share/locale")
#_ = cat.gettext

class SiloAppendWindow:

    def __call__(self, screen, todo):
	t = TextboxReflowed(53,
		     _("A few systems will need to pass special options "
		       "to the kernel at boot time for the system to function "
		       "properly. If you need to pass boot options to the "
		       "kernel, enter them now. If you don't need any or "
		       "aren't sure, leave this blank."))

	entry = Entry(48, scroll = 1, returnExit = 1)

	if todo.liloAppend:
	    entry.set(todo.liloAppend)

	buttons = ButtonBar(screen, [(_("OK"), "ok"), (_("Skip"), "skip"),  
			     (_("Back"), "back") ] )

	grid = GridForm(screen, _("SILO Configuration"), 1, 3)
	grid.add(t, 0, 0)
	grid.add(entry, 0, 1, padding = (0, 0, 0, 1))
	grid.add(buttons, 0, 2, growx = 1)

        result = grid.runOnce ()
        button = buttons.buttonPressed(result)
        
        if button == "back":
            return INSTALL_BACK

	if button == "skip":
	    todo.skipLilo = 1
	    todo.liloDevice = None
	else:
	    todo.skipLilo = 0

	if entry.value():
	    todo.liloAppend = string.strip(entry.value())
	else:
	    todo.liloAppend = None

	return INSTALL_OK

class SiloWindow:
    def __call__(self, screen, todo):
	(mount, dev, fstype, format, size) = todo.fstab.mountList()[0]
	if mount != '/': return INSTALL_NOOP
	if todo.skipLilo: return INSTALL_NOOP

	(bootpart, boothd, mbrpart) = todo.silo.getSiloOptions()

	format = "/dev/%-11s %s%*s" 
	str1 = _("Master Boot Record (MBR)")
	str2 = _("First sector of boot partition")
	str3 = _("Create PROM alias `linux'")
	str4 = _("Set default PROM boot device")
	len1 = len(str1) + 17
	len2 = len(str2) + 17
	len3 = len(str3)
	len4 = len(str4) 
	lenmax = max((len1, len2, len3, len4))
	if todo.silo.getSiloMbrDefault() == 'mbr':
	    dflt = 1
	else:
	    dflt = 0
	rc1 = SingleRadioButton (format % (boothd, str1, lenmax - len1, ""), None, dflt )
	rc2 = SingleRadioButton (format % (bootpart, str2, lenmax - len2, ""), rc1, 1 - dflt)

	prompath = todo.silo.disk2PromPath(bootpart)
	if prompath and len(prompath) > 0 and todo.silo.hasAliases():
	    default = 1
	else:
	    default = 0
	linuxAlias = Checkbox ("%s%*s" % (str3, lenmax - len3, ""), default)
	if not default:
	    linuxAlias.setFlags (FLAG_DISABLED, FLAGS_SET)
	bootDevice = Checkbox ("%s%*s" % (str4, lenmax - len4, ""), 1)

	bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

	g = GridForm (screen, _("SILO Configuration"), 1, 8)

	g.add (Label (_("Where do you want to install the bootloader?")), 0, 0)
	g.add (rc1, 0, 1)
	g.add (rc2, 0, 2, padding = (0, 0, 0, 1))
	g.add (linuxAlias, 0, 3)
	g.add (bootDevice, 0, 4, padding = (0, 0, 0, 1))
	g.add (bb, 0, 5, growx = 1)

	result = g.runOnce()

	if rc1.selected():
	    todo.setLiloLocation("mbr")
	else:
	    todo.setLiloLocation("partition")

	lAlias = linuxAlias.selected() != 0
	bDevice = bootDevice.selected() != 0

	todo.silo.setPROM(lAlias, bDevice)

	rc = bb.buttonPressed (result)

	if rc == "back":
	    return INSTALL_BACK
	return INSTALL_OK


class SiloImagesWindow:
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
	elif (type == 6):
	    type = "UFS"
	else:
	    type = "Other"

	if default == device:
	    default = '*'
	else:
	    default = ""
	    
	return "%-10s  %-25s %-7s %-10s" % ( "/dev/" + device, type, default, label)

    def __call__(self, screen, todo):
	images = todo.silo.getSiloImages()
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

	title = _("SILO Configuration")
	g = GridForm(screen, title, 1, 4)
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

