#import gettext
from snack import *
from constants_text import *
from translate import _
import string
import iutil
if iutil.getArch() == 'i386':
    import edd
    
#cat = gettext.Catalog ("anaconda", "/usr/share/locale")
#_ = cat.gettext

class LiloAppendWindow:

    def __call__(self, screen, todo):
	if not todo.fstab.setupFilesystems or todo.fstab.rootOnLoop():
	    todo.skipLilo = 1
	    #return INSTALL_NOOP

	t = TextboxReflowed(53,
		     _("A few systems will need to pass special options "
		       "to the kernel at boot time for the system to function "
		       "properly. If you need to pass boot options to the "
		       "kernel, enter them now. If you don't need any or "
		       "aren't sure, leave this blank."))

        cb = Checkbox(_("Use linear mode (needed for some SCSI drives)"),
		      isOn = todo.lilo.getLinear())
	entry = Entry(48, scroll = 1, returnExit = 1)
	if todo.lilo.getAppend():
	    entry.set(todo.lilo.getAppend())

	buttons = ButtonBar(screen, [(_("OK"), "ok"), (_("Skip"), "skip"),  
			     (_("Back"), "back") ] )

	grid = GridFormHelp(screen, _("LILO Configuration"), "kernelopts", 1, 4)
	grid.add(t, 0, 0, padding = (0, 0, 0, 1))

	if not edd.detect():
	    grid.add(cb, 0, 1, padding = (0, 0, 0, 1))

	grid.add(entry, 0, 2, padding = (0, 0, 0, 1))
	grid.add(buttons, 0, 3, growx = 1)

        result = grid.runOnce ()
        button = buttons.buttonPressed(result)
        
        if button == "back":
            return INSTALL_BACK

	if button == "skip":
	    todo.skipLilo = 1
            todo.lilo.setDevice(None)
	else:
	    todo.skipLilo = 0

	todo.lilo.setLinear(cb.selected())
	if entry.value():
	    todo.lilo.setAppend(string.strip(entry.value()))
	else:
	    todo.lilo.setAppend(None)

	return INSTALL_OK

class LiloWindow:
    def __call__(self, screen, todo):
        if not todo.setupFilesystems: return INSTALL_NOOP
	(mount, dev, fstype, format, size) = todo.fstab.mountList()[0]
	if mount != '/': return INSTALL_NOOP
	if todo.skipLilo: return INSTALL_NOOP

	if not todo.lilo.allowLiloLocationConfig(todo.fstab):
	    return INSTALL_NOOP

	bootpart = todo.fstab.getBootDevice()
	boothd = todo.fstab.getMbrDevice()

	if (todo.lilo.getDevice () == "mbr"):
	    default = 0
	elif (todo.lilo.getDevice () == "partition"):
	    default = 1
	else:
	    default = 0
            
        format = "/dev/%-11s %s" 
        locations = []
        locations.append (format % (boothd, _("Master Boot Record (MBR)")))
        locations.append (format % (bootpart, _("First sector of boot partition")))

        (rc, sel) = ListboxChoiceWindow (screen, _("LILO Configuration"),
                                         _("Where do you want to install the bootloader?"),
                                         locations, default = default,
                                         buttons = [ _("OK"), _("Back") ],
					 help = "lilolocation")

        if sel == 0:
            todo.lilo.setDevice("mbr")
        else:
            todo.lilo.setDevice("partition")

        if rc == string.lower (_("Back")):
            return INSTALL_BACK
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

	buttons = ButtonBar(screen, [(_("Ok"), "ok"), (_("Clear"), "clear"),
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
	while (result != "ok" and result != "F12" and result != newLabel):
	    result = g.run()

	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if (result == "cancel"):
		screen.popWindow ()
		return itemLabel
	    elif (result == "clear"):
		newLabel.set("")
            elif (result == "ok" or result == "F12" or result == newLabel):
		if not allowNone and not newLabel.value():
                    rc = ButtonChoiceWindow (screen, _("Invalid Boot Label"),
                                             _("Boot label may not be empty."),
                                             [ _("OK") ])
                    result = ""
                elif not self.validLiloLabel(newLabel.value()):
                    rc = ButtonChoiceWindow (screen, _("Invalid Boot Label"),
                                             _("Boot label contains "
                                               "illegal characters."),
                                             [ _("OK") ])
                    result = ""

	screen.popWindow()

	return newLabel.value()

    def formatDevice(self, type, label, device, default):
	if (type == 2):
	    type = "Linux Native"
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
	(images, default) = todo.lilo.getLiloImages(todo.fstab)
	if not images: return INSTALL_NOOP
	if todo.skipLilo: return INSTALL_NOOP

	# the default item is kept as a label (which makes more sense for the
	# user), but we want our listbox "indexed" by device, which so we keep
	# the default item as a device
	for (dev, (label, type)) in images.items():
	    if label == default:
		default = dev
		break

	sortedKeys = images.keys()
	sortedKeys.sort()

	listboxLabel = Label("%-10s  %-25s %-7s %-10s" % 
		( _("Device"), _("Partition type"), _("Default"), _("Boot label")))
	listbox = Listbox(5, scroll = 1, returnExit = 1)

	for n in sortedKeys:
	    (label, type) = images[n]
	    listbox.append(self.formatDevice(type, label, n, default), n)
	    if n == default:
		listbox.setCurrent(n)

	buttons = ButtonBar(screen, [ (_("Ok"), "ok"), (_("Edit"), "edit"), 
				      (_("Back"), "back") ] )

	text = TextboxReflowed(55,
		    _("The boot manager Red Hat uses can boot other " 
		      "operating systems as well. You need to tell me " 
		      "what partitions you would like to be able to boot " 
		      "and what label you want to use for each of them."))

	g = GridFormHelp(screen, _("LILO Configuration"), "lilolabels", 1, 4)
	g.add(text, 0, 0, anchorLeft = 1)
	g.add(listboxLabel, 0, 1, padding = (0, 1, 0, 0), anchorLeft = 1)
	g.add(listbox, 0, 2, padding = (0, 0, 0, 1), anchorLeft = 1)
	g.add(buttons, 0, 3, growx = 1)
	g.addHotKey(" ")

	result = None
        (rootdev, rootfs) = todo.fstab.getRootDevice()
	while (result != "ok" and result != "back" and result != "F12"):
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

	if (result == "back"):
	    return INSTALL_BACK

	# find the label for the default device
	for (dev, (label, type)) in images.items():
	    if dev == default:
		default = label
		break

	todo.lilo.setLiloImages(images)
	todo.lilo.setDefault(label)

	return INSTALL_OK

