# must replace with explcit form so update disks will work
from iw_gui import *

from gtk import *
from translate import _, N_
from xpms_gui import CHECKBOX_ON_XPM
from xpms_gui import CHECKBOX_OFF_XPM
import GdkImlib
import iutil
from package_gui import queryUpgradeContinue
import gui

class BootloaderWindow (InstallWindow):
    foo = GdkImlib.create_image_from_xpm (CHECKBOX_ON_XPM)
    foo.render()
    checkMark = foo.make_pixmap()
    del foo

    foo = GdkImlib.create_image_from_xpm (CHECKBOX_OFF_XPM)
    foo.render()
    checkMark_Off = foo.make_pixmap()
    del foo

    windowTitle = N_("Boot Loader Configuration")
    htmlTag = "bootloader"

    def getPrev (self):
        # avoid coming back in here if the user backs past and then tries
        # to skip this screen
        #self.bootdisk = None
	pass

	# XXX
	#
        # if doing an upgrade, offer choice of aborting upgrade.
        # we can't allow them to go back in install, since we've
        # started swap and mounted the systems filesystems
        # if we've already started an upgrade, cannot back out
        #
        # if we are skipping indivual package selection, must stop it here
        # very messy.
        #
        #if self.todo.upgrade and self.todo.instClass.skipStep("indivpackage"):
            #rc = queryUpgradeContinue(self.todo.intf)
            #if not rc:
                #raise gui.StayOnScreen
            #else:
                #import sys
                #print _("Aborting upgrade")
                #sys.exit(0)

    def getNext (self):
        if not self.bootdisk: return None

        if self.bootdisk.get_active ():
	    self.dispatch.skipStep("bootdisk", skip = 0)
        else:
	    self.dispatch.skipStep("bootdisk")

        if not self.bootloader.get_active ():
	    self.dispatch.skipStep("instbootloader")
        elif len(self.bootDevice.keys()) > 0:
	    self.dispatch.skipStep("instbootloader", skip = 0)

	    for (widget, device) in self.bootDevice.items():
		if widget.get_active():
		    self.bl.setDevice(device)

        default = None
        linuxDevice = None
        for index in range(self.numImages):
            device = self.imageList.get_text(index, 1)[5:]
            type = self.types[index]
            label = self.imageList.get_text(index, 3)

	    self.bl.images.setImageLabel(device, label)

            if self.default == index:
                default = device
            if type == 2:
                linuxDevice = device

        if not default:
            default = linuxDevice

        self.bl.setUseGrub(self.grub_radio.get_active())
        self.bl.args.set(self.appendEntry.get_text())
        self.bl.images.setDefault(default)

    def typeName(self, type):
        if (type == "ext2"):
            return "Linux Native"
        elif (type == "FAT"):
            return "DOS/Windows"
        elif (type == "hpfs"):       
            return "OS/2 / Windows NT"
        else:
            return "Other"

    def checkLiloReqs(self):
        if self.default == None:
            return 0

        defaultlabel = self.imageList.get_text(self.default, 3)
        if defaultlabel == "" or defaultlabel == None:
            return 0

        device = None
        label = None
        for i in range(self.numImages):
            device = self.imageList.get_text(i, 1)[5:]
            label  = self.imageList.get_text(i, 3)
            if device == self.rootdev:
                break

        if label == "":
            return 0

        for i in range(self.numImages):
            label1 = self.imageList.get_text(i, 3)
            j = i+1
            while j < self.numImages:
                label2 = self.imageList.get_text(j, 3)
                if label1 == label2:
                    return 0
                j = j + 1


        return 1

    def toggled (self, widget, *args):
        if self.ignoreSignals:
            return
        
        if widget.get_active ():
            state = TRUE
        else:
            state = FALSE

        list = self.bootDevice.keys()
        list.extend ([self.appendEntry, self.editBox, self.imageList,
                      self.liloLocationBox, self.radioBox, self.sw,
                      self.radio_hbox])
        for n in list:
            n.set_sensitive (state)

#        if state and not len(self.bootDevice.keys()) < 2:
#            self.liloLocationBox.set_sensitive(0)
#            self.grubCheck.set_sensitive(0)
#            print "here"
#            self.radio_hbox.set_sensitive(0)
#	    for n in self.bootDevice.keys():
#		n.set_sensitive(0)

    def labelInsertText(self, entry, text, len, data):
        i = 0
        while i < len:
            cur = text[i]
# lilo did not allow ' '!, grub does
#            if cur == ' ' or cur == '#' or cur == '$' or cur == '=':
            if cur == '#' or cur == '$' or cur == '=':
                entry.emit_stop_by_name ("insert_text")
                return
            i = i + 1

    def labelUpdated(self, *args):
        index = self.imageList.selection[0]
        device = self.imageList.get_text(index, 1)

        label = self.labelEntry.get_text()
        self.imageList.set_text(index, 3, label)

        # cannot allow user to select as default is zero length
        if label:
            self.defaultCheck.set_sensitive (TRUE)
        else:
            self.ignoreSignals = 1
            self.defaultCheck.set_active(0)
            self.defaultCheck.set_sensitive (FALSE)
            if self.default != None and self.default == index:
                self.imageList.set_text(self.default, 0, "")
                self.default = None
            self.ignoreSignals = 0
            
        if self.checkLiloReqs():
            self.ics.setNextEnabled (1)
        else:
            self.ics.setNextEnabled (0)


    def defaultUpdated(self, *args):
        if self.ignoreSignals: return

        index = self.imageList.selection[0]
        
        if range(self.count) > 0:
            for i in range(self.count):
                self.imageList.set_pixmap(i, 0, self.checkMark_Off)
        
        if self.defaultCheck.get_active():
            if self.default != None:
                self.imageList.set_pixmap(self.default, 0, self.checkMark_Off)

            self.imageList.set_pixmap(index, 0, self.checkMark)
            self.default = index
        else:
            self.imageList.set_pixmap(index, 0, self.checkMark_Off)
            self.default = None

        if self.checkLiloReqs():
            self.ics.setNextEnabled (1)
        else:
            self.ics.setNextEnabled (0)
        

    def labelSelected(self, *args):
        index = self.imageList.selection[0]
        device = self.imageList.get_text(index, 1)
        type = self.imageList.get_text(index, 2)
        label = self.imageList.get_text(index, 3)

        self.deviceLabel.set_text(_("Partition") + ": " + device)
        device = device[5:]

        self.typeLabel.set_text(_("Type") + ":" + type)
        self.labelEntry.set_text(label)
        
        # do not allow blank label to be default
        if not label:
            self.defaultCheck.set_active(0)
            self.defaultCheck.set_sensitive (FALSE)

        self.ignoreSignals = 1
        if index == self.default:
            self.defaultCheck.set_active(1)
        else:
            self.defaultCheck.set_active(0)
        self.ignoreSignals = 0

    # LiloWindow tag="lilo"
    def getScreen(self, dispatch, bl, fsset, diskSet):
	self.dispatch = dispatch
	self.bl = bl

	self.rootdev = fsset.getEntryByMountPoint("/").device.getDevice()

	imageList = bl.images.getImages()
	defaultDevice = bl.images.getDefault()
        self.ignoreSignals = 0

        format = "/dev/%s"

        self.radioBox = GtkTable(2, 6)
	self.bootDevice = {}
        self.radioBox.set_border_width (5)
        
        spacer = GtkLabel("")
        spacer.set_usize(10, 1)
        self.radioBox.attach(spacer, 0, 1, 2, 4, FALSE)

        label = GtkLabel(_("Install boot loader on:"))
        label.set_alignment(0.0, 0.5)
        self.liloLocationBox = GtkVBox (FALSE, 0)
        self.liloLocationBox.pack_start(label)
        self.radioBox.attach(self.liloLocationBox, 0, 2, 1, 2)

	choices = fsset.bootloaderChoices(diskSet)
	if choices:
	    radio = None
	    count = 0
	    for (device, desc) in choices:
		radio = GtkRadioButton(radio,  
				("/dev/%s %s" % (device, _(desc))))
		self.radioBox.attach(radio, 1, 2, count + 2, count + 3)
		self.bootDevice[radio] = device

		if bl.getDevice() == device:
		    radio.set_active(1)

		count = count + 1

        label = GtkLabel(_("Kernel parameters") + ":")
        label.set_alignment(0.0, 0.5)
        self.appendEntry = GtkEntry()
        if bl.args.get():
            self.appendEntry.set_text(bl.args.get())
        box = GtkHBox(FALSE, 5)
        box.pack_start(label)
        box.pack_start(self.appendEntry)
        alignment = GtkAlignment()
        alignment.set(0.0, 0.5, 0, 1.0)
        alignment.add(box)
        self.radioBox.attach(alignment, 0, 2, 5, 6)
        
        box = GtkVBox (FALSE, 0)

        optionBox = GtkVBox (FALSE, 5)
        optionBox.set_border_width (5)
        self.bootdisk = GtkCheckButton (_("Create boot disk"))

	self.bootdisk.set_active(not dispatch.stepInSkipList("bootdisk"))

        optionBox.pack_start (self.bootdisk)

        self.bootloader = GtkCheckButton (_("Install Bootloader"))

	if not dispatch.stepInSkipList("instbootloader"):
	    self.bootloader.set_active (TRUE)
	else:
            self.bootloader.set_active (FALSE)
            self.toggled (self.bootloader)

            for n in (self.mbr, self.part, self.appendEntry, self.editBox, 
                      self.imageList, self.liloLocationBox, self.radioBox ):
                n.set_sensitive (FALSE)

        self.bootloader.connect ("toggled", self.toggled)
        optionBox.pack_start (self.bootloader, FALSE)

        box.pack_start (optionBox, FALSE)

        box.pack_start(GtkHSeparator(), FALSE)
        label = GtkLabel(_("Boot loader:"))
        self.grub_radio = GtkRadioButton(None, (_("GRUB")))
        self.lilo_radio = GtkRadioButton(self.grub_radio, (_("LILO")))

        self.radio_hbox = GtkHBox(FALSE, 5)
        self.radio_hbox.set_border_width(5)
        self.radio_hbox.pack_start(label, FALSE)
        self.radio_hbox.pack_start(self.grub_radio, FALSE)
        self.radio_hbox.pack_start(self.lilo_radio, FALSE)
        box.pack_start(self.radio_hbox, FALSE)

        box.pack_start (GtkHSeparator (), FALSE)
        box.pack_start (self.radioBox, FALSE)

        self.imageList = GtkCList (4, ( _("Default"), _("Device"),
                                        _("Partition type"), _("Boot label")))

        sortedKeys = imageList.keys()
        sortedKeys.sort()
        self.numImages = len(sortedKeys)

        self.default = None
        self.count = 0
        self.types = []
        for n in sortedKeys:
            (label, longlabel, type) = imageList[n]
            self.types.append(type)
            if label == None:
                print "label is None!!"
                label = ""
            if not bl.useGrub():
                row = ("", "/dev/" + n, self.typeName(type), label)
            else:
                row = ("", "/dev/" + n, self.typeName(type), longlabel)
            self.imageList.append(row)

            if (n == defaultDevice):
                self.default = self.count
                self.imageList.set_pixmap(self.count, 0, self.checkMark)
            else:
                self.imageList.set_pixmap(self.count, 0, self.checkMark_Off)
            self.count = self.count + 1

        self.imageList.columns_autosize ()
        self.imageList.column_title_passive (1)
        self.imageList.set_border_width (5)

        self.deviceLabel = GtkLabel(_("Partition") + ":")
        self.typeLabel = GtkLabel(_("Type") + ":")

        tempBox = GtkHBox(TRUE)
        self.deviceLabel.set_alignment(0.0, 0.0)
        self.typeLabel.set_alignment(0.0, 0.0)
        tempBox.pack_start(self.deviceLabel, FALSE)
        tempBox.pack_start(self.typeLabel, FALSE)
        self.defaultCheck = GtkCheckButton(_("Default boot image"))

        # Alliteration!
        self.labelLabel = GtkLabel(_("Boot label") + ":")
        self.labelEntry = GtkEntry(15)

        self.imageList.connect("select_row", self.labelSelected)
        self.defaultCheck.connect("toggled", self.defaultUpdated)
        self.labelEntry.connect("changed", self.labelUpdated)
        self.labelEntry.connect("insert_text", self.labelInsertText)

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

        self.imageList.set_selection_mode (SELECTION_BROWSE)

        self.sw = GtkScrolledWindow ()
        self.sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.sw.add (self.imageList)
        box.pack_start (self.sw, TRUE)

	if not dispatch.stepInSkipList("instbootloader"):
            self.editBox.set_sensitive(TRUE)
            tempBox2.set_sensitive(TRUE)
            self.radioBox.set_sensitive(TRUE)
            self.sw.set_sensitive(TRUE)
        else:
            self.editBox.set_sensitive(FALSE)
            self.radioBox.set_sensitive(FALSE)
            self.sw.set_sensitive(FALSE)
            
        self.ignoreSignals = 0

        return box









