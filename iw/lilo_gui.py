# must replace with explcit form so update disks will work
from iw_gui import *

from gtk import *
from translate import _
from xpms_gui import CHECKBOX_ON_XPM
from xpms_gui import CHECKBOX_OFF_XPM
import GdkImlib
import iutil
if iutil.getArch() == 'i386':
    import edd

class LiloWindow (InstallWindow):
    foo = GdkImlib.create_image_from_xpm (CHECKBOX_ON_XPM)
    foo.render()
    checkMark = foo.make_pixmap()
    del foo

    foo = GdkImlib.create_image_from_xpm (CHECKBOX_OFF_XPM)
    foo.render()
    checkMark_Off = foo.make_pixmap()
    del foo


    def __init__ (self, ics):
        InstallWindow.__init__ (self, ics)

        ics.readHTML ("lilo")

        ics.setTitle (_("Lilo Configuration"))
        ics.setNextEnabled (1)
        self.ics = ics
        self.type = None
        self.bootdisk = None
        self.lilo = None

    def getPrev (self):
        # avoid coming back in here if the user backs past and then tries
        # to skip this screen
        self.bootdisk = None

    def getNext (self):
        if not self.bootdisk: return None

        if self.bootdisk.get_active ():
            self.todo.bootdisk = 1
            self.todo.bdstate = "TRUE"
        else:
            self.todo.bootdisk = 0
            self.todo.bdstate = "FALSE"

        if not self.lilo.get_active ():
            self.todo.lilo.setDevice(None)
            self.todo.lilostate = "FALSE"
        elif self.todo.lilo.allowLiloLocationConfig(self.todo.fstab):
            self.todo.lilostate = "TRUE"
            if self.mbr.get_active ():
                self.todo.lilo.setDevice("mbr")
            else:
                self.todo.lilo.setDevice("partition")

        images = {}
        default = None
        linuxDevice = None
        for index in range(self.numImages):
            device = self.imageList.get_text(index, 1)[5:]
            type = self.types[index]
            label = self.imageList.get_text(index, 3)
            images[device] = (label, type)
            if self.default == index:
                default = label
            if type == 2:
                linuxDevice = label

        if not default:
            default = linuxDevice

        self.todo.lilo.setLiloImages(images)
        self.todo.lilo.setLinear(self.linearCheck.get_active())
        self.todo.lilo.setAppend(self.appendEntry.get_text())
        self.todo.lilo.setDefault(default)

    def typeName(self, type):
        if (type == 2):
            return "Linux Native"
        elif (type == 1):
            return "DOS/Windows"
        elif (type == 4):       
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
        if widget.get_active ():
            state = TRUE
        else:
            state = FALSE

        for n in [self.mbr, self.part, self.appendEntry, self.editBox, 
                  self.imageList, self.liloLocationBox, self.radioBox, self.sw ]:
            n.set_sensitive (state)

        if state and not self.todo.lilo.allowLiloLocationConfig(self.todo.fstab):
            self.liloLocationBox.set_sensitive(0)
            self.mbr.set_sensitive(0)
            self.part.set_sensitive(0)
            self.linearCheck.set_sensitive(0)

    def labelInsertText(self, entry, text, len, data):
        i = 0
        while i < len:
            cur = text[i]
            if cur == ' ' or cur == '#' or cur == '$' or cur == '=':
                entry.emit_stop_by_name ("insert_text");
                return;
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

        if self.defaultCheck.get_active():
            if self.default != None:
                self.imageList.set_text(self.default, 0, "")

            self.imageList.set_pixmap(index, 0, self.checkMark)
            self.default = index
        else:
#            self.imageList.set_text(index, 0, "")
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
    def getScreen (self):
        (self.rootdev, rootfs) = self.todo.fstab.getRootDevice()

        if self.todo.fstab.rootOnLoop():
            self.todo.bootdisk = 1
            return None

# comment these two lines to get lilo screen in test mode
#        if not self.todo.fstab.setupFilesystems:
#            return None
        
        (imageList, defaultLabel) = \
                self.todo.lilo.getLiloImages(self.todo.fstab)
        self.ignoreSignals = 0

        if self.todo.fstab.mountList()[0][0] != '/': return None

        bootpart = self.todo.fstab.getBootDevice()
        boothd = self.todo.fstab.getMbrDevice()
            
        format = "/dev/%s"

        self.radioBox = GtkTable(2, 6)
        self.radioBox.set_border_width (5)
        
        spacer = GtkLabel("")
        spacer.set_usize(10, 1)
        self.radioBox.attach(spacer, 0, 1, 2, 4, FALSE)

        label = GtkLabel(_("Install LILO boot record on:"))
        label.set_alignment(0.0, 0.5)
        self.liloLocationBox = GtkVBox (FALSE, 0)
        self.liloLocationBox.pack_start(label)
        self.radioBox.attach(self.liloLocationBox, 0, 2, 1, 2)

        self.mbr = GtkRadioButton(None, 
            ("/dev/%s %s" % (boothd, _("Master Boot Record (MBR)"))))
        self.radioBox.attach(self.mbr, 1, 2, 2, 3)
        self.part = GtkRadioButton(self.mbr, 
            ("/dev/%s %s" % (bootpart, 
                _("First sector of boot partition"))))
        self.radioBox.attach(self.part, 1, 2, 3, 4)

        self.linearCheck = GtkCheckButton(
            _("Use linear mode (needed for some SCSI drives)"))
        self.linearCheck.set_active(self.todo.lilo.getLinear())

	if not edd.detect():
	    self.radioBox.attach(self.linearCheck, 0, 2, 4, 5)

        if not self.todo.lilo.allowLiloLocationConfig(self.todo.fstab):
            self.liloLocationBox.set_sensitive(0)
            self.mbr.set_sensitive(0)
            self.part.set_sensitive(0)
            self.linearCheck.set_sensitive(0)

        label = GtkLabel(_("Kernel parameters") + ":")
        label.set_alignment(0.0, 0.5)
        self.appendEntry = GtkEntry()
        if self.todo.lilo.getAppend():
            self.appendEntry.set_text(self.todo.lilo.getAppend())
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

        # If this screen hasn't been reached before, then activate self.bootdisk
        if self.todo.bdstate == "":
            self.todo.bdstate = "TRUE"

        # If first time or self.bootdisk was activated in the past, activate now.  Else deactivate
        if self.todo.bdstate == "TRUE":
            self.bootdisk.set_active (TRUE)
        else:
            self.bootdisk.set_active (FALSE)

        optionBox.pack_start (self.bootdisk)

        self.lilo = GtkCheckButton (_("Install LILO"))

        if self.todo.lilostate == "":
            self.todo.lilostate = "TRUE"
            

        # If first time or self.lilo was activated in the past, activate now.  Else deactivate
        if self.todo.lilostate == "TRUE":
            self.lilo.set_active (TRUE)
        else:
            self.lilo.set_active (FALSE)
            self.toggled (self.lilo)

            for n in [self.mbr, self.part, self.appendEntry, self.editBox, 
                      self.imageList, self.liloLocationBox, self.radioBox ]:
                n.set_sensitive (FALSE)


        self.lilo.connect ("toggled", self.toggled)
        optionBox.pack_start (self.lilo, FALSE)

        box.pack_start (optionBox, FALSE)

        box.pack_start (GtkHSeparator (), FALSE)
        box.pack_start (self.radioBox, FALSE)

        self.imageList = GtkCList (4,
            ( _("Default"), _("Device"), _("Partition type"), _("Boot label")))

        sortedKeys = imageList.keys()
        sortedKeys.sort()
        self.numImages = len(sortedKeys)

        self.default = None
        count = 0
        self.types = []
        for n in sortedKeys:
            (label, type) = imageList[n]
            self.types.append(type)
            self.imageList.append(("", "/dev/" + n, self.typeName(type), 
                                    label))
            if (label == defaultLabel):
                self.default = count
                self.imageList.set_pixmap(count, 0, self.checkMark)
            else:
                self.imageList.set_pixmap(count, 0, self.checkMark_Off)
            count = count + 1

        self.imageList.connect("select_row", self.labelSelected)
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
        self.defaultCheck.connect("toggled", self.defaultUpdated)

        # Alliteration!
        self.labelLabel = GtkLabel(_("Boot label") + ":")
        self.labelEntry = GtkEntry(15)
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

        where = self.todo.lilo.getDevice()

        if self.todo.lilostate == "TRUE":
            self.editBox.set_sensitive(TRUE)
            tempBox2.set_sensitive(TRUE)
            self.radioBox.set_sensitive(TRUE)
            self.sw.set_sensitive(TRUE)

            if not where:
                self.lilo.set_active(1)
            elif where == "mbr":
                self.mbr.set_active(1)
            else:
                self.part.set_active(1)
        else:
            self.editBox.set_sensitive(FALSE)
            self.radioBox.set_sensitive(FALSE)
            self.sw.set_sensitive(FALSE)


        return box









