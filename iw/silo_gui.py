# must replace with explcit form so update disks will work
from iw_gui import *

from gtk import *
from translate import _
from xpms_gui import SMALL_CHECK
import GdkImlib

class SiloWindow (InstallWindow):
    foo = GdkImlib.create_image_from_xpm (SMALL_CHECK)
    foo.render()
    checkMark = foo.make_pixmap()
    del foo

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

	ics.readHTML ("silo")

	ics.setTitle (_("Silo Configuration"))
	ics.setNextEnabled (1)
	self.type = None
	self.bootdisk = None
	self.silo = None
	self.linuxAlias = None
	self.linuxAliasLabel = None
	self.bootDevice = None

    def getNext (self):
	# XXX
	if not self.bootdisk:
	    if self.todo.silo.hasUsableFloppy() == 2:
		self.todo.bootdisk = 1
	    else:
		self.todo.bootdisk = 0
	    return None

	if self.bootdisk.get_active ():
	    self.todo.bootdisk = 1
	else:
	    self.todo.bootdisk = 0

	if self.silo.get_active ():
	    self.todo.silo.setDevice(None)
	elif self.todo.silo.allowSiloLocationConfig(self.todo.fstab):
	    if self.mbr.get_active ():
		self.todo.silo.setDevice("mbr")
	    else:
		self.todo.silo.setDevice("partition")

	self.todo.silo.setAppend(self.appendEntry.get_text())
	self.todo.silo.setSiloImages(self.images)

	linuxAlias = 0
	bootDevice = 0
	if self.linuxAlias.get_active ():
	    linuxAlias = 1
	if self.bootDevice.get_active ():
	    bootDevice = 1
	    
	self.todo.silo.setPROM(linuxAlias, bootDevice)

    def typeName(self, type):
	if (type == 2):
	    return "Linux Native"
	elif (type == 6):
	    return "UFS"
	else:
	    return "Other"

    def toggled (self, widget, *args):
	if widget.get_active ():
	    state = FALSE
	else:
	    state = TRUE

	for n in [ self.radioBox, self.editBox, self.imageList ]:
	    n.set_sensitive (state)

    def mbr_toggled (self, widget, *args):
	if widget.get_active ():
	    part = self.mbrpart
	else:
	    part = self.bootpart
	prompath = self.todo.silo.disk2PromPath(part)
	if prompath and len(prompath) > 0:
	    self.linuxAliasLabel.set_text ("linux " + prompath)
	    if self.todo.silo.hasAliases():
		self.linuxAliasLabel.set_sensitive (TRUE)
		self.linuxAlias.set_sensitive (TRUE)
		return
	self.linuxAliasLabel.set_sensitive (FALSE)
	self.linuxAlias.set_sensitive (FALSE)

    def labelUpdated(self, *args):
	index = self.imageList.selection[0]
	device = self.imageList.get_text(index, 1)

	label = self.labelEntry.get_text()
	self.imageList.set_text(index, 3, label)

	if label:
	    self.defaultCheck.set_sensitive (TRUE)
	else:
	    self.defaultCheck.set_sensitive (FALSE)

    def defaultUpdated(self, *args):
	if self.ignoreSignals: return

	index = self.imageList.selection[0]

	if self.defaultCheck.get_active():
	    if self.default != None:
		self.imageList.set_text(self.default, 0, "")

	    self.imageList.set_pixmap(index, 0, self.checkMark)
	    self.default = index
	else:
	    self.imageList.set_text(index, 0, "")
	    self.default = None

    def labelSelected(self, *args):
	index = self.imageList.selection[0]
	device = self.imageList.get_text(index, 1)
	label = self.imageList.get_text(index, 3)

	self.deviceLabel.set_text(_("Partition") + ": " + device)
	device = device[5:]

	type = self.images[device][1]

	self.typeLabel.set_text(_("Type") + ":" + self.typeName(type))
	self.labelEntry.set_text(label)

	if not label:
	    self.defaultCheck.set_sensitive (FALSE)

	self.ignoreSignals = 1
	if index == self.default:
	    self.defaultCheck.set_active(1)
	else:
	    self.defaultCheck.set_active(0)
	self.ignoreSignals = 0

    # SiloWindow tag="silo"
    def getScreen (self):
	(self.images, defaultLabel) = self.todo.silo.getSiloImages(self.todo.fstab)
	self.ignoreSignals = 0

	(mount, dev, fstype, format, size) = self.todo.fstab.mountList()[0]
	if mount != '/': return None

	self.bootpart = self.todo.fstab.getBootDevice()
	self.mbrpart = self.todo.silo.getMbrDevice(self.todo.fstab)
	format = "/dev/%s"

	self.radioBox = GtkTable(2, 7)
	self.radioBox.set_border_width (5)
	
	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
	self.radioBox.attach(spacer, 0, 1, 2, 4, FALSE)

	label = GtkLabel(_("Install SILO boot record on:"))
	label.set_alignment(0.0, 0.5)
	self.radioBox.attach(label, 0, 2, 1, 2)

	mbrpart = self.mbrpart
	if self.bootpart[:2] == "md":
	    mbrpart = self.bootpart
	# FIXME: Should be Master Boot Records (MBR) in the RAID1 case
	self.mbr = GtkRadioButton(None, 
	    ("/dev/%s %s" % (mbrpart, _("Master Boot Record (MBR)"))))
	part = GtkRadioButton(self.mbr,
	    ("/dev/%s %s" % (self.bootpart, 
		_("First sector of boot partition"))))
	self.radioBox.attach(self.mbr, 1, 2, 2, 3)
	self.radioBox.attach(part, 1, 2, 3, 4)

	self.linuxAlias = GtkCheckButton(
	    _("Create PROM alias") + ":")
	if (self.todo.silo.hasAliases()):
	    self.linuxAlias.set_active (TRUE)
	else:
	    self.linuxAlias.set_active (FALSE)
	self.linuxAliasLabel = GtkLabel("")
	self.mbr_toggled(self.mbr)
	tempBox = GtkHBox (FALSE, 5)
	tempBox.pack_start(self.linuxAlias)
	tempBox.pack_start(self.linuxAliasLabel)
	self.radioBox.attach(tempBox, 0, 2, 4, 5)

	self.mbr.connect("toggled", self.mbr_toggled)
	if self.bootpart[:2] == "md":
	    self.mbr.set_active (TRUE)
	    label.set_sensitive (FALSE)
	    self.mbr.set_sensitive (FALSE)
	    part.set_sensitive (FALSE)
	if self.todo.silo.getSiloMbrDefault(self.todo.fstab) == 'mbr':
	    self.mbr.set_active (TRUE)
	else:
	    part.set_active (TRUE);

	self.bootDevice = GtkCheckButton(_("Set default PROM boot device to linux"))
	self.radioBox.attach(self.bootDevice, 0, 2, 5, 6)
	self.bootDevice.set_active (TRUE)

	label = GtkLabel(_("Kernel parameters") + ":")
	label.set_alignment(0.0, 0.5)
	self.appendEntry = GtkEntry(15)
	if self.todo.silo.getAppend():
	    self.appendEntry.set_text(self.todo.silo.getAppend())
	box = GtkHBox(FALSE, 5)
	box.pack_start(label)
	box.pack_start(self.appendEntry)
	alignment = GtkAlignment()
	alignment.set(0.0, 0.5, 0, 1.0)
	alignment.add(box)
	self.radioBox.attach(alignment, 0, 2, 6, 7)
	
	box = GtkVBox (FALSE, 0)

	topBox = GtkHBox (FALSE, 2)
	optionBox = GtkVBox (FALSE, 5)
	optionBox.set_border_width (5)
	self.bootdisk = GtkCheckButton (_("Create boot disk"))
	floppy = self.todo.silo.hasUsableFloppy()
	if floppy == 2:
	    self.bootdisk.set_active (TRUE)
	else:
	    self.bootdisk.set_active (FALSE)
	if floppy == 0:
	    self.bootdisk.set_sensitive (FALSE)
	optionBox.pack_start (self.bootdisk)

	self.silo = GtkCheckButton (_("Do not install SILO"))
	self.silo.set_active (FALSE)
	self.silo.connect ("toggled", self.toggled)
	optionBox.pack_start (self.silo, FALSE)
	topBox.pack_start (optionBox)

	im = self.ics.readPixmap ("silo.png")
	if im:
	    im.render ()
	    pix = im.make_pixmap ()
	    a = GtkAlignment ()
	    a.add (pix)
	    a.set (1.0, 0.0, 0.0, 0.0)
	    topBox.pack_start (a, FALSE)

	box.pack_start (topBox, FALSE)

	box.pack_start (GtkHSeparator (), FALSE)
	box.pack_start (self.radioBox, FALSE)

	self.imageList = GtkCList (4,
	    ( _("Default"), _("Device"), _("Partition type"), _("Boot label")))
	self.imageList.set_selection_mode (SELECTION_BROWSE)

	sortedKeys = self.images.keys()
	sortedKeys.sort()

	self.default = None
	count = 0
	for n in sortedKeys:
	    (label, type) = self.images[n]
	    self.imageList.append(("", "/dev/" + n, self.typeName(type), 
				    label))
	    if (label == defaultLabel):
		self.default = count
		self.imageList.set_pixmap(count, 0, self.checkMark)
	    count = count + 1

	self.imageList.columns_autosize ()
	self.imageList.column_title_passive (1)
	self.imageList.set_border_width (5)
	self.imageList.connect("select_row", self.labelSelected)
	self.imageList.set_column_justification(2, JUSTIFY_CENTER)

	self.deviceLabel = GtkLabel(_("Partition") + ":")
	self.typeLabel = GtkLabel(_("Type") + ":")

	tempBox = GtkHBox(TRUE)
	self.deviceLabel.set_alignment(0.0, 0.0)
	self.typeLabel.set_alignment(0.0, 0.0)
	tempBox.pack_start(self.deviceLabel, FALSE)
	tempBox.pack_start(self.typeLabel, FALSE)
	self.defaultCheck = GtkCheckButton(_("Default boot image"))
	self.defaultCheck.connect("toggled", self.defaultUpdated)

	# Alliteration!
	self.labelLabel = GtkLabel(_("Boot label") + ":")
	self.labelEntry = GtkEntry(15)
	self.labelEntry.connect("changed", self.labelUpdated)

	tempBox2 = GtkHBox(FALSE, 5)
	self.labelLabel.set_alignment(0.0, 0.5)
	tempBox2.pack_start(self.labelLabel, FALSE)
	tempBox2.pack_start(self.labelEntry, FALSE)

	self.editBox = GtkVBox ()
	self.editBox.pack_start (tempBox, FALSE)
	self.editBox.pack_start (self.defaultCheck, FALSE)
	self.editBox.pack_start (tempBox2, FALSE)
	self.editBox.set_border_width (5)

	box.pack_start (GtkHSeparator (), FALSE)
	box.pack_start (self.editBox, FALSE)
	box.pack_start (self.imageList, TRUE)

	return box
