from iw import *
from gtk import *
from gui import _
from xpms import SMALL_CHECK
import GdkImlib

class LiloWindow (InstallWindow):

    foo = GdkImlib.create_image_from_xpm (SMALL_CHECK)
    foo.render()
    checkMark = foo.make_pixmap()
    del foo

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Lilo Configuration"))
        ics.setNextEnabled (1)
        self.type = None

    def getNext (self):
	return
        if self.lilo.get_active ():
            self.todo.setLiloLocation (None)
        else:
            self.type = self.list.selection[0]
            if self.list.selection[0] == 0:
                self.todo.setLiloLocation (self.boothd)
            else:
                self.todo.setLiloLocation (self.bootpart)

        if self.bootdisk.get_active ():
            self.todo.bootdisk = 1
        else:
            self.todo.bootdisk = 0

    def typeName(self, type):
	if (type == 2):
	    return "Linux extended"
	elif (type == 1):
	    return "DOS/Windows"
	elif (type == 4):	
	    return "OS/2 / Windows NT"
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

    def defaultUpdated(self, *args):
	if self.ignoreSignals: return

	index = self.imageList.selection[0]

	print "old default", self.default

	if self.defaultCheck.get_active():
	    if self.default != None:
		print "off:", self.default
		self.imageList.set_text(self.default, 0, "")

	    self.imageList.set_pixmap(index, 0, self.checkMark)
	    self.default = index
	else:
	    self.imageList.set_text(index, 0, "")
	    self.default = None

	print "new default", self.default

    def labelSelected(self, *args):
	index = self.imageList.selection[0]
	device = self.imageList.get_text(index, 1)
	label = self.imageList.get_text(index, 3)

	self.deviceLabel.set_text(_("Partition") + ": " + device)
	device = device[5:]

	type = self.images[device][1]

	self.typeLabel.set_text(_("Type") + ":" + self.typeName(type))
	self.labelEntry.set_text(label)

	print (index, self.default)

        self.ignoreSignals = 1
	if index == self.default:
	    self.defaultCheck.set_active(1)
	else:
	    self.defaultCheck.set_active(0)
        self.ignoreSignals = 0

    def getScreen (self):
	self.images = self.todo.getLiloImages()
        self.ignoreSignals = 0

        if '/' not in self.todo.mounts.keys (): return None

        if self.todo.mounts.has_key ('/boot'):
            self.bootpart = self.todo.mounts['/boot'][0]
        else:
            self.bootpart = self.todo.mounts['/'][0]
        i = len (self.bootpart) - 1
        while i < 0 and self.bootpart[i] in digits:
            i = i - 1
        self.boothd = self.bootpart[0:i]
            
        format = "/dev/%s"

        self.radioBox = GtkVBox (FALSE, 10)
        group = GtkRadioButton(None, 
	    ("/dev/%s %s" % (self.boothd, _("Master Boot Record (MBR)"))))
	self.radioBox.pack_start(group, FALSE)
        group = GtkRadioButton(group, 
	    ("/dev/%s %s" % (self.bootpart, 
		_("First sector of boot partition"))))
	self.radioBox.pack_start(group, FALSE)
	
        box = GtkVBox (FALSE, 5)
        self.bootdisk = GtkCheckButton (_("Create boot disk"))
        self.bootdisk.set_active (TRUE)
        box.pack_start (self.bootdisk, FALSE)
        box.pack_start (GtkHSeparator (), FALSE, padding=3)

        self.lilo = GtkCheckButton (_("Skip LILO install"))
        self.lilo.set_active (FALSE)
        self.lilo.connect ("toggled", self.toggled)
        box.pack_start (self.lilo, FALSE)

        self.radioBox.set_border_width (10)
        box.pack_start (self.radioBox, FALSE)

	self.imageList = GtkCList (4,
	    ( _("Default"), _("Device"), _("Partition type"), _("Boot label")))
        self.imageList.set_selection_mode (SELECTION_SINGLE)

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

	tempBox = GtkHBox()
	self.deviceLabel.set_alignment(0.0, 0.0)
	self.typeLabel.set_alignment(0.0, 0.0)
	tempBox.set_homogeneous(1)
	tempBox.pack_start(self.deviceLabel, FALSE)
	tempBox.pack_start(self.typeLabel, FALSE)
	self.defaultCheck = GtkCheckButton("Default boot image")
	self.defaultCheck.connect("toggled", self.defaultUpdated)

	# Alliteration!
	self.labelLabel = GtkLabel(_("Boot label") + ":")
	self.labelEntry = GtkEntry(15)
	self.labelEntry.connect("changed", self.labelUpdated)

	tempBox2 = GtkHBox()
	self.labelLabel.set_alignment(0.0, 0.0)
	tempBox2.pack_start(self.labelLabel, FALSE)
	tempBox2.pack_start(self.labelEntry, FALSE, padding = 5)

	self.editBox = GtkVBox()
	self.editBox.pack_start(tempBox, FALSE)
	self.editBox.pack_start(self.defaultCheck, FALSE)
	self.editBox.pack_start(tempBox2, FALSE)
	self.editBox.set_border_width(5)

        box.pack_start (GtkHSeparator (), FALSE, padding=3)
        box.pack_start (self.editBox, FALSE)
        box.pack_start (self.imageList, TRUE)

        return box
