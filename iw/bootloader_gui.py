#
# bootloader_gui.py: gui bootloader configuration dialog
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gobject
import iutil
import partedUtils
import gui
from iw_gui import *
from translate import _, N_

class BootloaderWindow (InstallWindow):
    windowTitle = N_("Boot Loader Configuration")
    htmlTag = "bootloader"

    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        self.parent = ics.getICW().window
        

    def getPrev(self):
        pass


    def getNext(self):
        if self.forceLBA.get_active() and not self.bl.forceLBA32:
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
        
        # set the bootloader type
        if self.none_radio.get_active():
            self.dispatch.skipStep("instbootloader")
            self.dispatch.skipStep("bootloaderadvanced")            
            return
        else:
            self.bl.setUseGrub(self.grub_radio.get_active())
            self.dispatch.skipStep("instbootloader", skip = 0)
            self.dispatch.skipStep("bootloaderadvanced", skip = 0)            
        
        # set the bootloader pass XXX should handle the only crypted pass case
        if self.usePassCb and self.password:
            self.bl.setPassword(self.password, isCrypted = 0)
        else:
            self.bl.setPassword(None)

        # set kernel args
        self.bl.args.set(self.appendEntry.get_text())

        # set forcelba
        self.bl.setForceLBA(self.forceLBA.get_active())

    def bootloaderChanged(self, widget, *args):
        if widget == self.grub_radio and self.grub_radio.get_active():
            self.options_vbox.set_sensitive(gtk.TRUE)
        elif widget == self.lilo_radio and self.lilo_radio.get_active():
            self.options_vbox.set_sensitive(gtk.TRUE)
        elif widget == self.none_radio and self.none_radio.get_active():
            self.options_vbox.set_sensitive(gtk.FALSE)
        else:
            # punt
            pass
        
    # get the bootloader password
    def passwordWindow(self, *args):
        dialog = gtk.Dialog(_("Enter Boot Loader Password"), self.parent)
        dialog.add_button('gtk-ok', 1)
        dialog.add_button('gtk-cancel', 2)
        dialog.set_position(gtk.WIN_POS_CENTER)
        gui.addFrame(dialog)
        
        label = gui.WrappingLabel(_("A boot loader password prevents users "
                                    "from passing arbitrary options to the "
                                    "kernel.  For highest security, we "
                                    "recommend setting a password, but this "
                                    "is not necessary for more casual users."))
        label.set_alignment(0.0, 0.0)
        dialog.vbox.pack_start(label)

        table = gtk.Table(2, 2)
        table.set_row_spacings(5)
        table.set_col_spacings(5)
        table.attach(gtk.Label(_("Password:")), 0, 1, 2, 3,
                              gtk.FILL, 0, 10)
        pwEntry = gtk.Entry (16)
        pwEntry.set_visibility (gtk.FALSE)
        table.attach(pwEntry, 1, 2, 2, 3, gtk.FILL, 0, 10)
        table.attach(gtk.Label(_("Confirm:")), 0, 1, 3, 4,
                              gtk.FILL, 0, 10) 
        confirmEntry = gtk.Entry (16)
        confirmEntry.set_visibility (gtk.FALSE)
        table.attach(confirmEntry, 1, 2, 3, 4, gtk.FILL, 0, 10)
        dialog.vbox.pack_start(table)

        # set the default
        if self.password:
            pwEntry.set_text(self.password)
            confirmEntry.set_text(self.password)

        dialog.show_all()

        while 1:
            rc = dialog.run()
            if rc == 2:
                break

            if pwEntry.get_text() != confirmEntry.get_text():
                self.intf.messageWindow(_("Passwords don't match"),
                                        _("Passwords do not match"),
                                        type='warning')
                continue

            thePass = pwEntry.get_text()
            if not thePass:
                continue
            if len(thePass) < 6:
                ret = self.intf.messageWindow(_("Warning"),
                                    _("Your boot loader password is less than "
                                      "six characters.  We recommend a longer "
                                      "boot loader password."
                                      "\n\n"
                                      "Would you like to continue with this "
                                      "password?"),
                                             type = "yesno")
                if ret == 0:
                    continue

            self.password = thePass
            break

        dialog.destroy()
        return rc

    # set the label on the button for the bootloader password
    def setPassLabel(self):
        if not self.usePassCb.get_active() or not self.password:
            self.passButton.set_label(_("No password"))
        else:
            self.passButton.set_label(_("Change password"))
            self.passButton.set_sensitive(gtk.TRUE)

    # callback for when the password checkbox is clicked
    def passCallback(self, widget, *args):
        if not widget.get_active():
            self.passButton.set_sensitive(gtk.FALSE)
            self.setPassLabel()
        else:
            if self.passwordWindow() == 2:
                widget.set_active(0)
            self.setPassLabel()

    # callback for when the password button is clicked
    def passButtonCallback(self, widget, *args):
        self.passwordWindow()
        self.setPassLabel()

    # LiloWindow tag="lilo"
    def getScreen(self, dispatch, bl, fsset, diskSet):
	self.dispatch = dispatch
	self.bl = bl
        self.intf = dispatch.intf

        # find the video mode... this is pretty ugly
        args = self.bl.args.get()
        
        if self.bl.getPassword():
            self.usePass = 1
            self.password = self.bl.getPassword()
        else:
            self.usePass = 0
            self.password = None

        # main vbox
        thebox = gtk.VBox (gtk.FALSE, 10)


        # radio buttons for type of boot loader to use
        self.radio_vbox = gtk.VBox(gtk.FALSE, 2)
        self.radio_vbox.set_border_width(5)

        label = gui.WrappingLabel(_("Please select the boot loader that "
                                    "the computer will use.  GRUB is the "
                                    "default boot loader. However, if you "
                                    "do not wish to overwrite your current "
                                    "boot loader, select \"Do not install "
                                    "a boot loader.\"  "))
        label.set_alignment(0.0, 0.0)
                           
        self.grub_radio = gtk.RadioButton(None, (_("Use _GRUB as the "
                                                   "boot loader")))
        self.lilo_radio = gtk.RadioButton(self.grub_radio, (_("Use _LILO as "
                                                              "the boot loader")))
        self.none_radio = gtk.RadioButton(self.grub_radio, (_("Do not "
                                                              "install a "
                                                              "boot loader")))


        self.radio_vbox.pack_start(label, gtk.FALSE)
        self.radio_vbox.pack_start(self.grub_radio, gtk.FALSE)
        self.radio_vbox.pack_start(self.lilo_radio, gtk.FALSE)
        self.radio_vbox.pack_start(self.none_radio, gtk.FALSE)

        # XXX this is kind of ugly
        if dispatch.stepInSkipList("instbootloader"):
            self.none_radio.set_active(gtk.TRUE)
        elif not bl.useGrub():
            self.lilo_radio.set_active(gtk.TRUE)
        else:
            self.grub_radio.set_active(gtk.TRUE)

        self.grub_radio.connect("toggled", self.bootloaderChanged)
        self.lilo_radio.connect("toggled", self.bootloaderChanged)
        self.none_radio.connect("toggled", self.bootloaderChanged)
        thebox.pack_start(self.radio_vbox, gtk.FALSE)

        thebox.pack_start (gtk.HSeparator(), gtk.FALSE)

        # kernel parameters: append, password, lba32
        self.options_vbox = gtk.VBox(gtk.FALSE, 5)
        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        self.options_vbox.pack_start(spacer, gtk.FALSE)
        
        label = gui.WrappingLabel(_("The following affect options passed to "
                                    "the kernel on boot.  FIXME."
                                    "Obviously there needs to be more explanatory text here and throughout and better spacing"))
        label.set_alignment(0.0, 0.5)
        self.options_vbox.pack_start(label, gtk.FALSE)

        # password widgets + callback
        self.usePassCb = gtk.CheckButton(_("Use a Boot Loader Password"))
        self.passButton = gtk.Button(_("Set Password"))
        if self.usePass:
            self.usePassCb.set_active(gtk.TRUE)
            self.passButton.set_sensitive(gtk.TRUE)
        else:
            self.usePassCb.set_active(gtk.FALSE)
            self.passButton.set_sensitive(gtk.FALSE)
        self.usePassCb.connect("toggled", self.passCallback)
        self.passButton.connect("clicked", self.passButtonCallback)
            
        box = gtk.HBox(gtk.FALSE, 5)
        box.pack_start(self.usePassCb)
        box.pack_start(self.passButton)
        self.options_vbox.pack_start(box, gtk.FALSE)

        self.forceLBA = gtk.CheckButton(_("Force LBA32"))
        self.options_vbox.pack_start(self.forceLBA, gtk.FALSE)
        self.forceLBA.set_active(self.bl.forceLBA32)

        label = gtk.Label(_("General kernel parameters"))
        self.appendEntry = gtk.Entry()
        if args:
            self.appendEntry.set_text(args)
        box = gtk.HBox(gtk.FALSE, 5)
        box.pack_start(label)
        box.pack_start(self.appendEntry)
        self.options_vbox.pack_start(box, gtk.FALSE)
        if self.none_radio.get_active():
            self.options_vbox.set_sensitive(gtk.FALSE)
            
        alignment = gtk.Alignment()
        alignment.set(0.1, 0.5, 0, 1.0)
        alignment.add(self.options_vbox)

        thebox.pack_start(alignment, gtk.FALSE)
        
        return thebox


class AdvancedBootloaderWindow (InstallWindow):
    windowTitle = N_("Boot Loader Configuration")
    htmlTag = "bootloader"

    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        self.parent = ics.getICW().window
        

    def getPrev(self):
        pass


    def getNext(self):
        # make a copy of our image list to shove into the bl struct
        self.bl.images.images = {}
        for key in self.imagelist.keys():
            self.bl.images.images[key] = self.imagelist[key]
        self.bl.images.setDefault(self.defaultDev)

        for key in self.bootDevices.keys():
            if self.bootDevices[key][0].get_active():
#                print "setting device to %s" % (self.bootDevices[key][1],)
                self.bl.setDevice(self.bootDevices[key][1])

        self.bl.drivelist = self.driveOrder
                

    # adds/edits a new "other" os to the boot loader config
    def editOther(self, oldDevice, oldLabel, isDefault, isRoot = 0):
        dialog = gtk.Dialog(_("Image"), self.parent)
        dialog.add_button('gtk-ok', 1)
        dialog.add_button('gtk-cancel', 2)
        dialog.set_position(gtk.WIN_POS_CENTER)
        gui.addFrame(dialog)

        dialog.vbox.pack_start(gui.WrappingLabel(
            _("The label is what is displayed in the boot loader to "
              "choose to boot this operating system.  The device "
              "is the device which it boots from.")))

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        dialog.vbox.pack_start(spacer, gtk.FALSE)

        table = gtk.Table(2, 5)
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        table.attach(gtk.Label(_("Label")), 0, 1, 1, 2, gtk.FILL, 0, 10)
        labelEntry = gtk.Entry(32)
        table.attach(labelEntry, 1, 2, 1, 2, gtk.FILL, 0, 10)
        if oldLabel:
            labelEntry.set_text(oldLabel)

        table.attach(gtk.Label(_("Device")), 0, 1, 2, 3, gtk.FILL, 0, 10)
        if not isRoot:
            # XXX should potentially abstract this out into a function
            pedparts = []
            parts = []
            disks = self.diskset.disks
            for drive in disks.keys():
                pedparts.extend(partedUtils.get_all_partitions(disks[drive]))
            for part in pedparts:
                parts.append(partedUtils.get_partition_name(part))
            parts.sort()
            
            deviceOption = gtk.OptionMenu()
            deviceMenu = gtk.Menu()
            defindex = None
            i = 0
            for part in  parts:
                item = gtk.MenuItem("/dev/" + part)
                item.set_data("part", part)
                # XXX gtk bug -- have to show so that the menu is sized right
                item.show()
                deviceMenu.add(item)
                if oldDevice and oldDevice == part:
                    defindex = i
                i = i + 1
            deviceOption.set_menu(deviceMenu)
            if defindex:
                deviceOption.set_history(defindex)
            
            table.attach(deviceOption, 1, 2, 2, 3, gtk.FILL, 0, 10)
        else:
            table.attach(gtk.Label(oldDevice), 1, 2, 2, 3, gtk.FILL, 0, 10)

        default = gtk.CheckButton(_("Default Boot Target"))
        table.attach(default, 0, 2, 3, 4, gtk.FILL, 0, 10)
        if isDefault != 0:
            default.set_active(gtk.TRUE)
        
        dialog.vbox.pack_start(table)
        dialog.show_all()

        while 1:
            rc = dialog.run()

            # cancel
            if rc == 2:
                break

            label = labelEntry.get_text()

            if not isRoot:
                dev = deviceMenu.get_active().get_data("part")
            else:
                dev = oldDevice

            if not label:
                self.intf.messageWindow(_("Error"),
                                        _("You must specify a label for the "
                                          "entry"),
                                        type="warning")
                continue

            foundBad = 0
            for char in self.illegalChars:
                if char in label:
                    self.intf.messageWindow(_("Error"),
                                            _("Boot label contains illegal "
                                              "characters"),
                                            type="warning")
                    foundBad = 1
                    break
            if foundBad:
                continue

            # verify that the label hasn't been used
            foundBad = 0
            for key in self.imagelist.keys():
                if dev == key:
                    continue
                if self.bl.useGrub():
                    thisLabel = self.imagelist[key][1]
                else:
                    thisLabel = self.imagelist[key][0]

                # if the label is the same as it used to be, they must
                # have changed the device which is fine
                if thisLabel == oldLabel:
                    continue

                if thisLabel == label:
                    self.intf.messageWindow(_("Duplicate Label"),
                                            _("This label is already in "
                                              "use for another boot entry."),
                                            type="warning")
                    foundBad = 1
                    break
            if foundBad:
                continue

            # XXX need to do some sort of validation of the device?

            # they could be duplicating a device, which we don't handle
            if dev in self.imagelist.keys() and (not oldDevice or
                                                 dev != oldDevice):
                self.intf.messageWindow(_("Duplicate Device"),
                                        _("This device is already being "
                                          "used for another boot entry."),
                                        type="warning")
                continue

            # if we're editing and the device has changed, delete the old
            if oldDevice and dev != oldDevice:
                del self.imagelist[oldDevice]
                

            # go ahead and add it
            if self.bl.useGrub():
                self.imagelist[dev] = (None, label, isRoot)
            else:
                self.imagelist[dev] = (label, None, isRoot)

            if default.get_active():
                self.defaultDev = dev

            # refill the os list store
            self.fillOSList()
            break
        
        dialog.destroy()

    def getSelected(self):
        selection = self.osTreeView.get_selection()
        rc = selection.get_selected()
        if not rc:
            return None
        model, iter = rc

        dev = model.get_value(iter, 2)
        theDev = dev[5:] # strip /dev/
        
        label = model.get_value(iter, 1)
        isRoot = model.get_value(iter, 3)
        isDefault = model.get_value(iter, 0)
        return (theDev, label, isDefault, isRoot)


    def addEntry(self, widget, *args):
        self.editOther(None, None, 0)

    def deleteEntry(self, widget, *args):
        rc = self.getSelected()
        if not rc:
            return
        (dev, label, isDefault, isRoot) = rc
        if not isRoot:
            del self.imagelist[dev]
            self.fillOSList()
        else:
            self.intf.messageWindow(_("Cannot Delete"),
                                    _("This boot target cannot be deleted "
				      "because it is for the Red Hat Linux "
				      "system you are about to install."),
                                      type="warning")

    def editEntry(self, widget, *args):
        rc = self.getSelected()
        if not rc:
            return
        (dev, label, isDefault, isRoot) = rc
        self.editOther(dev, label, isDefault, isRoot)

    # the default os was changed in the treeview
    def toggledDefault(self, widget, *args):
        if widget.get_active():
            return

        rc = self.getSelected()
        if not rc:
            return
        self.defaultDev = rc[0]
        self.fillOSList()

    # fill in the os list tree view
    def fillOSList(self):
        self.osStore.clear()
        
        keys = self.imagelist.keys()
        keys.sort()

        for dev in keys:
            (label, longlabel, fstype) = self.imagelist[dev]
            if self.bl.useGrub():
                theLabel = longlabel
            else:
                theLabel = label

            # if the label is empty, remove from the image list and don't
            # worry about it
            if not theLabel:
                del self.imagelist[dev]
                continue

	    isRoot = 0
	    fsentry = self.fsset.getEntryByDeviceName(dev)
	    if fsentry and fsentry.getMountPoint() == '/':
		isRoot = 1

            iter = self.osStore.append()
            self.osStore.set_value(iter, 1, theLabel)
            self.osStore.set_value(iter, 2, "/dev/%s" % (dev,))
            self.osStore.set_value(iter, 3, isRoot)
            if self.defaultDev == dev:
                self.osStore.set_value(iter, 0, gtk.TRUE)
            else:
                self.osStore.set_value(iter, 0, gtk.FALSE)

    def arrowClicked(self, widget, direction, *args):
        selection = self.driveOrderView.get_selection()
        rc = selection.get_selected()
        if not rc:
            return
        model, iter = rc

        # there has got to be a better way to do this =\
        drive = model.get_value(iter, 0)[5:]
        index = self.driveOrder.index(drive)
        if direction == gtk.ARROW_DOWN:
            self.driveOrder.remove(drive)
            self.driveOrder.insert(index + 1, drive)
        elif direction == gtk.ARROW_UP:
            self.driveOrder.remove(drive)
            self.driveOrder.insert(index - 1, drive)
        self.makeDriveOrderStore()
        
        self.setMbrLabel(self.driveOrder[0])


    # make the store for the drive order
    def makeDriveOrderStore(self):
        self.driveOrderStore.clear()
        iter = self.driveOrderStore.append()
        for drive in self.driveOrder:
            self.driveOrderStore.set_value(iter, 0, "/dev/%s" % (drive,))
            iter = self.driveOrderStore.append()

    # set the label on the mbr radio button to show the right device.
    # kind of a hack
    def setMbrLabel(self, firstDrive):
        if not self.bootDevices.has_key("mbr"):
            return

        (radio, olddev, desc) = self.bootDevices["mbr"]
        radio.set_label("/dev/%s %s" % (firstDrive, _(desc)))
        self.bootDevices["mbr"] = (radio, firstDrive, desc)

        
    # LiloWindow tag="lilo"
    def getScreen(self, dispatch, bl, fsset, diskSet):
	self.dispatch = dispatch
	self.bl = bl
        self.fsset = fsset
        self.intf = dispatch.intf
        self.diskset = diskSet

        # illegal characters for boot loader labels
        if self.bl.useGrub():
            self.illegalChars = [ "$", "=" ]
        else:
            self.illegalChars = [ "$", "=", " " ]

        # XXX more debug fun
#        self.driveOrder = ["hda", "hdb"]
        self.driveOrder = self.bl.drivelist
            
        # main vbox
        thebox = gtk.VBox (gtk.FALSE, 10)

        vbox = gtk.VBox(gtk.FALSE, 5)
        label = gui.WrappingLabel(_("Insert some text about booting other operating systems"))
        vbox.pack_start(label, gtk.FALSE)

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        vbox.pack_start(spacer, gtk.FALSE)

        box = gtk.HBox (gtk.FALSE, 5)
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.set_size_request(300, 100)
        box.pack_start(sw, gtk.TRUE)


        self.osStore = gtk.ListStore(gobject.TYPE_BOOLEAN, gobject.TYPE_STRING,
                                     gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
        self.osTreeView = gtk.TreeView(self.osStore)
        theColumns = [ "Default", "Label", "Device" ]

        self.checkboxrenderer = gtk.CellRendererToggle()
        column = gtk.TreeViewColumn(theColumns[0], self.checkboxrenderer,
                                    active = 0)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.checkboxrenderer.connect("toggled", self.toggledDefault)
        self.osTreeView.append_column(column)

        for columnTitle in theColumns[1:]:
            renderer = gtk.CellRendererText()
            column = gtk.TreeViewColumn(columnTitle, renderer,
                                        text = theColumns.index(columnTitle))
            column.set_clickable(gtk.FALSE)
            self.osTreeView.append_column(column)

        self.osTreeView.set_headers_visible(gtk.TRUE)
        self.osTreeView.columns_autosize()
        self.osTreeView.set_size_request(100, 100)
        sw.add(self.osTreeView)

        self.imagelist = self.bl.images.getImages()
        self.defaultDev = self.bl.images.getDefault()

        # XXX debug spew, remove me
##         if len(self.imagelist.keys()) <= 1:
##             self.imagelist = { 'hda2': ('linux', 'Red Hat Linux', 1),
##                           'hda1': ('windows', 'Windows', 0) }
##             self.defaultDev = 'hda1'

        self.fillOSList()

        buttonbar = gtk.VButtonBox()
        buttonbar.set_layout(gtk.BUTTONBOX_START)
        buttonbar.set_border_width(5)
        add = gtk.Button(_("_Add"))
        buttonbar.pack_start(add, gtk.FALSE)
        add.connect("clicked", self.addEntry)

        edit = gtk.Button(_("_Edit"))
        buttonbar.pack_start(edit, gtk.FALSE)
        edit.connect("clicked", self.editEntry)

        delete = gtk.Button(_("_Delete"))
        buttonbar.pack_start(delete, gtk.FALSE)
        delete.connect("clicked", self.deleteEntry)
        box.pack_start(buttonbar, gtk.FALSE)

        vbox.pack_start(box, gtk.FALSE)

        alignment = gtk.Alignment()
        alignment.set(0.1, 0, 0, 0)
        alignment.add(vbox)
        thebox.pack_start(alignment, gtk.FALSE)

        thebox.pack_start (gtk.HSeparator(), gtk.FALSE)

        label = gtk.Label(_("Install Boot Loader record on:"))
        label.set_alignment(0.0, 0.5)
        locationBox = gtk.VBox (gtk.FALSE, 2)
        locationBox.pack_start(label)

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        locationBox.pack_start(spacer, gtk.FALSE)

        # XXX switch over to real and not debug crap
#        choices = { 'mbr': ("hda", "MBR"), 'boot': ("hda2", "/boot") }
        choices = fsset.bootloaderChoices(diskSet, self.bl)
        self.bootDevices = {}
        
	if choices:
	    radio = None
            keys = choices.keys()
            keys.reverse()
            for key in keys:
                (device, desc) = choices[key]
		radio = gtk.RadioButton(radio,  
				("/dev/%s %s" % (device, _(desc))))
                locationBox.pack_start(radio, gtk.FALSE)
                self.bootDevices[key] = (radio, device, desc)

                if self.bl.getDevice() == device:
                    radio.set_active(gtk.TRUE)
                else:
                    radio.set_active(gtk.FALSE)

        alignment = gtk.Alignment()
        alignment.set(0.1, 0, 0, 0)
        alignment.add(locationBox)
        thebox.pack_start(alignment, gtk.FALSE)

        if not self.bl.useGrub():
            return thebox
        
        thebox.pack_start (gtk.HSeparator(), gtk.FALSE)

        drivebox = gtk.VBox(gtk.FALSE, 5)
        label = gui.WrappingLabel(_("Blah, this is the BIOS drive order, more information, etc"))
        drivebox.pack_start(label, gtk.FALSE)

        hbox = gtk.HBox(gtk.FALSE, 5)

        # different widget for this maybe?
        self.driveOrderStore = gtk.ListStore(gobject.TYPE_STRING)
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        
        self.driveOrderView = gtk.TreeView(self.driveOrderStore)
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Text', renderer, text = 0)
        column.set_clickable(gtk.FALSE)
        self.driveOrderView.append_column(column)
        self.driveOrderView.set_rules_hint(gtk.FALSE)
        self.driveOrderView.set_headers_visible(gtk.FALSE)
        self.driveOrderView.set_enable_search(gtk.FALSE)

        self.makeDriveOrderStore()

        sw.add(self.driveOrderView)
        sw.set_size_request(100, 100)
        hbox.pack_start(sw, gtk.FALSE)

        arrowbox = gtk.VBox(gtk.FALSE, 5)
        arrowButton = gtk.Button()
        arrow = gtk.Arrow(gtk.ARROW_UP, gtk.SHADOW_ETCHED_IN)
        arrowButton.add(arrow)
        arrowButton.connect("clicked", self.arrowClicked, gtk.ARROW_UP)
        arrowbox.pack_start(arrowButton, gtk.FALSE)
        
        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        arrowbox.pack_start(spacer, gtk.FALSE)

        arrowButton = gtk.Button()
        arrow = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_ETCHED_IN)
        arrowButton.add(arrow)
        arrowButton.connect("clicked", self.arrowClicked, gtk.ARROW_DOWN)
        arrowbox.pack_start(arrowButton, gtk.FALSE)

        alignment = gtk.Alignment()
        alignment.set(0, 0.5, 0, 0)
        alignment.add(arrowbox)
        hbox.pack_start(alignment, gtk.FALSE)

        drivebox.pack_start(hbox, gtk.FALSE)
        alignment = gtk.Alignment()
        alignment.set(0.1, 0, 0, 0)
        alignment.add(drivebox)
        thebox.pack_start(alignment, gtk.FALSE)

        self.setMbrLabel(self.driveOrder[0])

        return thebox
