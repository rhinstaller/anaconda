from iw import *
from gtk import *
from gui import _
from xpms import SMALL_CHECK
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
	self.bootDevice = None

    def getNext (self):
        # XXX
        if not self.bootdisk: return None

        if self.bootdisk.get_active ():
            self.todo.bootdisk = 1
        else:
            self.todo.bootdisk = 0

        if self.silo.get_active ():
            self.todo.setLiloLocation (None)
        else:
            if self.mbr.get_active ():
                self.todo.setLiloLocation ("mbr")
            else:
                self.todo.setLiloLocation ("partition")

	self.todo.setLiloImages(self.images)

    def typeName(self, type):
	if (type == 2):
	    return "Linux Native"
	elif (type == 6):
	    return "SunOS/Solaris"
	else:
	    return "Other"

    def toggled (self, widget, *args):
        if widget.get_active ():
	    state = FALSE
        else:
	    state = TRUE

	for n in [self.radioBox, self.editBox, self.imageList ]:
            n.set_sensitive (state)

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

    def getScreen (self):
	self.images = self.todo.silo.getSiloImages()
        self.ignoreSignals = 0

        if '/' not in self.todo.mounts.keys (): return None
	(bootpart, boothd) = self.todo.silo.getSiloOptions()
            
        format = "/dev/%s"

        self.radioBox = GtkTable(2, 7)
        self.radioBox.set_border_width (5)
        
	spacer = GtkLabel("")
	spacer.set_usize(10, 1)
	self.radioBox.attach(spacer, 0, 1, 2, 4, FALSE)

	label = GtkLabel(_("Install SILO boot record on:"))
	label.set_alignment(0.0, 0.5)
	self.radioBox.attach(label, 0, 2, 1, 2)

        part = GtkRadioButton(None,
	    ("/dev/%s %s" % (bootpart, 
		_("First sector of boot partition"))))
        self.mbr = GtkRadioButton(part, 
	    ("/dev/%s %s" % (boothd, _("Master Boot Record (MBR)"))))
	self.radioBox.attach(part, 1, 2, 2, 3)
	self.radioBox.attach(self.mbr, 1, 2, 3, 4)

	print "bootpart ", bootpart, " ", self.todo.silo.disk2PromPath(bootpart)

	# FIXME: Position this correctly
        self.linuxAlias = GtkCheckButton(
	    ("%s: linux %s" % (_("Create PROM alias"), self.todo.silo.disk2PromPath(bootpart))))
        self.radioBox.attach(self.linuxAlias, 0, 2, 4, 5)
	if (self.todo.silo.hasAliases()):
	    self.linuxAlias.set_active (TRUE)
	else:
	    self.linuxAlias.set_active (FALSE)
	    self.linuxAlias.set_sensitive (FALSE)

        self.bootDevice = GtkCheckButton(_("Set default PROM boot device to linux"))
        self.radioBox.attach(self.bootDevice, 0, 2, 4, 6)
	self.bootDevice.set_active (TRUE)

	label = GtkLabel(_("Kernel parameters") + ":")
	label.set_alignment(0.0, 0.5)
	self.appendEntry = GtkEntry(15)
	box = GtkHBox(FALSE, 5)
	box.pack_start(label)
	box.pack_start(self.appendEntry)
	alignment = GtkAlignment()
	alignment.set(0.0, 0.5, 0, 1.0)
	alignment.add(box)
	self.radioBox.attach(alignment, 0, 2, 5, 7)
	
        box = GtkVBox (FALSE, 0)

        optionBox = GtkVBox (FALSE, 5)
        optionBox.set_border_width (5)
        self.bootdisk = GtkCheckButton (_("Create boot disk"))
	if self.todo.silo.hasUsableFloppy():
	    self.bootdisk.set_active (TRUE)
	else:
	    self.bootdisk.set_active (FALSE)
	    self.bootdisk.set_sensitive (FALSE)
        optionBox.pack_start (self.bootdisk)

        self.silo = GtkCheckButton (_("Do not install SILO"))
        self.silo.set_active (FALSE)
        self.silo.connect ("toggled", self.toggled)
        optionBox.pack_start (self.silo, FALSE)

        box.pack_start (optionBox, FALSE)

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
	    if (label == "linux"):
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
	self.defaultCheck = GtkCheckButton("Default boot image")
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
