#
# bootloader_gui.py: gui bootloader configuration dialog
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

# must replace with explcit form so update disks will work
from iw_gui import *

from gtk import *
from gnome.ui import *
from translate import _, N_
import iutil
from package_gui import queryUpgradeContinue
import gui

class BootloaderWindow (InstallWindow):
    checkMark = None
    checkMark_Off = None

    windowTitle = N_("Boot Loader Configuration")
    htmlTag = "bootloader"

    def getPrev (self):
        # avoid coming back in here if the user backs past and then tries
        # to skip this screen
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
        if self.lba.get_active() and not self.bl.forceLBA32:
            rc = self.intf.messageWindow(_("Warning"),
                    _("Forcing the use of LBA32 for your bootloader when "
                      "not supported by the BIOS can cause your machine "
                      "to be unable to boot.  We highly recommend you "
                      "create a boot disk when asked later in the "
                      "install process.\n\n"
                      "Would you like to continue and force LBA32 mode?"),
                                    type = "yesno")
            if rc != 1:
                raise gui.StayOnScreen

        if self.none_radio.get_active ():
	    self.dispatch.skipStep("instbootloader")
            self.dispatch.skipStep("bootloaderpassword")
            return
        elif self.lilo_radio.get_active ():
            self.dispatch.skipStep("bootloaderpassword")
        elif self.grub_radio.get_active ():
            self.dispatch.skipStep("bootloaderpassword", skip = 0)

        if len(self.bootDevice.keys()) > 0:
	    self.dispatch.skipStep("instbootloader", skip = 0)

	    for (widget, device) in self.bootDevice.items():
		if widget.get_active():
		    self.bl.setDevice(device)

        self.bl.setUseGrub(self.grub_radio.get_active())
        self.bl.args.set(self.appendEntry.get_text())
        
        default = None
        linuxDevice = None
        for index in range(self.numImages):
            device = self.imageList.get_text(index, 1)[5:]
            type = self.types[index]
            label = self.imageList.get_text(index, 3)

	    self.bl.images.setImageLabel(device, label, self.bl.useGrub())

            if self.default == index:
                default = device
            if type == 2:
                linuxDevice = device

        if not default:
            default = linuxDevice

        self.bl.images.setDefault(default)
        self.bl.setForceLBA(self.lba.get_active())
        

    def typeName(self, type):
        if (type == "FAT"):
            return "DOS/Windows"
        elif (type == "hpfs"):       
            return "OS/2 / Windows NT"
        else:
            return type

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
                if label1 == label2 and label1 != "":
                    return 0
                j = j + 1


        return 1

    def toggled (self, widget, *args):
        if self.ignoreSignals:
            return
        
        if not widget.get_active ():
            state = TRUE
            if self.checkLiloReqs():
                self.ics.setNextEnabled (1)
            else:
                self.ics.setNextEnabled (0)            
        else:
            state = FALSE
            self.ics.setNextEnabled(1)

        list = self.bootDevice.keys()
        list.extend ([self.appendEntry, self.editBox, self.imageList,
                      self.liloLocationBox, self.radioBox, self.sw])
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

    def bootloaderchange(self, widget):
        if self.lilo_radio.get_active():
            selected = "lilo"
        elif self.grub_radio.get_active():
            selected = "grub"
        elif self.none_radio.get_active():
            return

        if not self.lastselected or selected == self.lastselected:
            return
        self.lastselected = selected

        # swap the label for what it was "last"...  this is conveniently
        # also the long form if we're switching back to grub or vice versa
        for index in range(self.numImages):
            tmp = self.oldLabels[index]
            self.oldLabels[index] = self.imageList.get_text(index, 3)
            self.imageList.set_text(index, 3, tmp)
        self.labelSelected()

    # LiloWindow tag="lilo"
    def getScreen(self, dispatch, bl, fsset, diskSet):
        if not BootloaderWindow.checkMark:
            BootloaderWindow.checkMark = self.ics.readPixmap("checkbox-on.png")
        if not BootloaderWindow.checkMark_Off:
            BootloaderWindow.checkMark_Off = self.ics.readPixmap("checkbox-off.png")            

	self.dispatch = dispatch
	self.bl = bl
        self.intf = dispatch.intf

	self.rootdev = fsset.getEntryByMountPoint("/").device.getDevice()

	imageList = bl.images.getImages()
	defaultDevice = bl.images.getDefault()
        self.ignoreSignals = 0

        self.radioBox = GtkTable(2, 6)
	self.bootDevice = {}
        self.radioBox.set_border_width (5)
        
        spacer = GtkLabel("")
        spacer.set_usize(10, 1)
        self.radioBox.attach(spacer, 0, 1, 2, 4, FALSE)

        label = GtkLabel(_("Install Boot Loader record on:"))
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

        label = GtkLabel(_("Kernel Parameters") + ":")
        label.set_alignment(0.0, 0.5)
        self.appendEntry = GtkEntry()
        if bl.args and bl.args.get():
            self.appendEntry.set_text(bl.args.get())
        box = GtkHBox(FALSE, 5)
        box.pack_start(label)
        box.pack_start(self.appendEntry)
        alignment = GtkAlignment()
        alignment.set(0.0, 0.5, 0, 1.0)
        alignment.add(box)
        self.lba = GtkCheckButton(_("Force use of LBA32 (not normally required)"))
        self.lba.set_active(self.bl.forceLBA32)
        vbox = GtkVBox(FALSE, 5)
        vbox.pack_start(alignment)
        vbox.pack_end(self.lba)
        self.radioBox.attach(vbox, 0, 2, 5, 6)
        
        box = GtkVBox (FALSE, 0)

        label = GtkLabel(_("Please select the boot loader that the computer will use.  GRUB is the default boot loader. "
                           "However, if you do not wish to overwrite your current boot loader, "
                           "select \"Do not install a boot loader.\"  "))
        label.set_usize(400, -1)
        label.set_line_wrap(TRUE)
        label.set_alignment(0.0, 0.0)
        self.editBox = GtkVBox ()
        self.imageList = GtkCList (4, ( _("Default"), _("Device"),
                                        _("Partition type"), _("Boot label")))
        self.sw = GtkScrolledWindow ()

                           
        self.grub_radio = GtkRadioButton(None, (_("Use GRUB as the boot loader")))
        self.lilo_radio = GtkRadioButton(self.grub_radio, (_("Use LILO as the boot loader")))
        self.none_radio = GtkRadioButton(self.grub_radio, (_("Do not install a boot loader")))


        self.lilo_radio.connect("toggled", self.bootloaderchange)
        self.grub_radio.connect("toggled", self.bootloaderchange)
        self.none_radio.connect("toggled", self.toggled)

 	if not dispatch.stepInSkipList("instbootloader"):
 	    self.none_radio.set_active (FALSE)
 	else:
             self.none_radio.set_active (TRUE)
             self.toggled (self.none_radio)

             for n in (self.appendEntry, self.editBox, 
                       self.imageList, self.liloLocationBox, self.radioBox ):
                 n.set_sensitive (FALSE)

        self.lastselected = None

        self.radio_vbox = GtkVBox(FALSE, 2)
        self.radio_vbox.set_border_width(5)
        self.radio_vbox.pack_start(label, FALSE)
        self.radio_vbox.pack_start(self.grub_radio, FALSE)
        self.radio_vbox.pack_start(self.lilo_radio, FALSE)
        self.radio_vbox.pack_start(self.none_radio, FALSE)
        
        box.pack_start(self.radio_vbox, FALSE)

        box.pack_start (GtkHSeparator (), FALSE)
        box.pack_start (self.radioBox, FALSE)
        
        sortedKeys = imageList.keys()
        sortedKeys.sort()
        self.numImages = len(sortedKeys)

        if not bl.useGrub():
            self.lilo_radio.set_active(1)
            self.lastselected = "lilo"
        else:
            self.grub_radio.set_active(1)
            self.lastselected = "grub"
                
        self.default = None
        self.count = 0
        self.types = []
        self.oldLabels = []
        for n in sortedKeys:
            (label, longlabel, type) = imageList[n]
            self.types.append(type)
            if label == None:
                label = ""
            if longlabel == None:
                longlabel = ""
            if self.lastselected == "lilo":
                row = ("", "/dev/" + n, self.typeName(type), label)
                self.oldLabels.append(longlabel)
            else:
                row = ("", "/dev/" + n, self.typeName(type), longlabel)
                self.oldLabels.append(label)
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

        self.editBox.pack_start (tempBox, FALSE)
        self.editBox.pack_start (self.defaultCheck, FALSE)
        self.editBox.pack_start (tempBox2, FALSE)
        self.editBox.set_border_width (5)

        box.pack_start (GtkHSeparator (), FALSE)
        box.pack_start (self.editBox, FALSE)

        self.imageList.set_selection_mode (SELECTION_BROWSE)

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









