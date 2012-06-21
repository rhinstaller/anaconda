# Custom partitioning classes.
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

# TODO:
# - Add button doesn't do anything.  It may need to ask for what kind of thing is being
#   added, too.
# - Deleting an LV is not reflected in available space in the bottom left.
# - Device descriptions, suggested sizes, etc. should be moved out into a support file.
# - Newly created devices can not be resized (because self.resizable requires self.exists).
# - Remove the entire installation if '-' is pressed when a Page has the focus.
# - Removing a device is not very smart.  It needs to take into account LUKS, LVM, RAID,
#   all that kind of stuff.  If this is the last device in one of those containers, all
#   the containers should be deleted too.
# - Tabbing behavior in the accordion is weird.
# - When all members of a page are removed, the page should be removed from the
#   accordion and the RHS should be updated to display something else.

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

from pyanaconda.product import productName, productVersion
from pyanaconda.storage.formats import device_formats
from pyanaconda.storage.size import Size

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.accordion import *
from pyanaconda.ui.gui.utils import enlightbox, setViewportBackground
from pyanaconda.ui.gui.categories.storage import StorageCategory

from gi.repository import Gtk

__all__ = ["CustomPartitioningSpoke"]

class AddDialog(UIObject):
    builderObjects = ["addDialog"]
    mainWidgetName = "addDialog"
    uiFile = "spokes/custom.ui"

    def on_add_cancel_clicked(self, button, *args):
        self.window.destroy()

    def on_add_confirm_clicked(self, button, *args):
        self.window.destroy()

    def refresh(self):
        UIObject.refresh(self)

    def run(self):
        return self.window.run()

class ConfirmDeleteDialog(UIObject):
    builderObjects = ["confirmDeleteDialog"]
    mainWidgetName = "confirmDeleteDialog"
    uiFile = "spokes/custom.ui"

    def on_delete_cancel_clicked(self, button, *args):
        self.window.destroy()

    def on_delete_confirm_clicked(self, button, *args):
        self.window.destroy()

    def refresh(self, mountpoint, device):
        UIObject.refresh(self)
        label = self.builder.get_object("confirmLabel")

        if mountpoint:
            txt = "%s (%s)" % (mountpoint, device)
        else:
            txt = device

        label.set_text(label.get_text() % txt)

    def run(self):
        return self.window.run()

class CustomPartitioningSpoke(NormalSpoke):
    builderObjects = ["customStorageWindow", "sizeAdjustment",
                      "partitionStore",
                      "addImage", "removeImage", "settingsImage"]
    mainWidgetName = "customStorageWindow"
    uiFile = "spokes/custom.ui"

    category = StorageCategory
    title = N_("MANUAL PARTITIONING")

    def __init__(self, data, storage, payload, instclass):
        NormalSpoke.__init__(self, data, storage, payload, instclass)

        self._current_selector = None
        self._ran_autopart = False
        self._when_create_text = ""

    def apply(self):
        pass

    @property
    def indirect(self):
        return True

    def _grabObjects(self):
        self._configureBox = self.builder.get_object("configureBox")

        self._partitionsViewport = self.builder.get_object("partitionsViewport")
        self._partitionsNotebook = self.builder.get_object("partitionsNotebook")

        self._optionsNotebook = self.builder.get_object("optionsNotebook")

        self._addButton = self.builder.get_object("addButton")
        self._removeButton = self.builder.get_object("removeButton")
        self._configButton = self.builder.get_object("configureButton")

    def initialize(self):
        from pyanaconda.storage.devices import DiskDevice
        from pyanaconda.storage.formats.fs import FS

        NormalSpoke.initialize(self)

        label = self.builder.get_object("whenCreateLabel")
        self._when_create_text = label.get_text()

        self._grabObjects()
        setViewportBackground(self.builder.get_object("availableSpaceViewport"), "#db3279")
        setViewportBackground(self.builder.get_object("totalSpaceViewport"), "#60605b")
        setViewportBackground(self._partitionsViewport)

        # Set the background of the options notebook to slightly darker than
        # everything else, and give it a border.
        provider = Gtk.CssProvider()
        provider.load_from_data("GtkNotebook { background-color: shade(@theme_bg_color, 0.95); border-width: 1px; border-style: solid; border-color: @borders; }")
        context = self._optionsNotebook.get_style_context()
        context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self._accordion = Accordion()
        self._partitionsViewport.add(self._accordion)

        # Populate the list of valid filesystem types from the format classes.
        # Unfortunately, we have to narrow them down a little bit more because
        # this list will include things like PVs and RAID members.
        combo = self.builder.get_object("fileSystemTypeCombo")
        for cls in device_formats.itervalues():
            obj = cls()
            if obj.supported and obj.formattable and \
               (isinstance(obj, FS) or obj.type in ["biosboot", "prepboot", "swap"]):
                combo.append_text(obj.name)

    def _mountpointName(self, mountpoint):
        # If there's a mount point, apply a kind of lame scheme to it to figure
        # out what the name should be.  Basically, just look for the last directory
        # in the mount point's path and capitalize the first letter.  So "/boot"
        # becomes "Boot", and "/usr/local" becomes "Local".
        if mountpoint == "/":
            return "Root"
        elif mountpoint != None:
            try:
                lastSlash = mountpoint.rindex("/")
            except ValueError:
                # No slash in the mount point?  I suppose that's possible.
                return None

            return mountpoint[lastSlash+1:].capitalize()
        else:
            return None

    def _clearpartDevices(self):
        return [d for d in self.storage.devicetree.devices if d.name in self.data.clearpart.drives]

    def _unusedDevices(self):
        from pyanaconda.storage.devices import DiskDevice
        return [d for d in self.storage.unusedDevices if d.disks and not isinstance(d, DiskDevice)]

    def _currentFreeSpace(self):
        """Add up all the free space on selected disks and return it as a Size."""
        totalFree = Size(bytes=0)

        freeDisks = self.storage.getFreeSpace(disks=self._clearpartDevices())
        for tup in freeDisks.values():
            for chunk in tup:
                totalFree += chunk

        return totalFree

    def _currentTotalSpace(self):
        """Add up the sizes of all selected disks and return it as a Size."""
        totalSpace = 0

        for disk in self._clearpartDevices():
            totalSpace += disk.size

        return Size(spec="%s MB" % totalSpace)

    def _updateSpaceDisplay(self):
        # Set up the free space/available space displays in the bottom left.
        self._availableSpaceLabel = self.builder.get_object("availableSpaceLabel")
        self._totalSpaceLabel = self.builder.get_object("totalSpaceLabel")
        self._summaryButton = self.builder.get_object("summary_button")

        self._availableSpaceLabel.set_text(str(self._currentFreeSpace()))
        self._totalSpaceLabel.set_text(str(self._currentTotalSpace()))

        summaryLabel = self._summaryButton.get_children()[0]
        count = len(self.data.clearpart.drives)
        summary = P_("%d storage device selected",
                     "%d storage devices selected",
                     count) % count

        summaryLabel.set_use_markup(True)
        summaryLabel.set_markup("<span foreground='blue'><u>%s</u></span>" % summary)

    def refresh(self):
        NormalSpoke.refresh(self)
        self._do_refresh()
        self._updateSpaceDisplay()

    def _do_refresh(self):
        # Make sure we start with a clean slate.
        self._accordion.removeAllPages()

        # Start with buttons disabled, since nothing is selected.
        self._removeButton.set_sensitive(False)
        self._configButton.set_sensitive(False)

        # Now it's time to populate the accordion.

        # We can only have one page expanded at a time.
        did_expand = False

        # If we've not yet run autopart, add an instance of CreateNewPage.  This
        # ensures it's only added once.
        if not self._ran_autopart:
            page = CreateNewPage(self.on_create_clicked)
            page.pageTitle = _("New %s %s Installation") % (productName, productVersion)
            self._accordion.addPage(page, cb=self.on_page_clicked)
            self._accordion.expandPage(page.pageTitle)
            did_expand = True

            self._partitionsNotebook.set_current_page(0)
            label = self.builder.get_object("whenCreateLabel")
            label.set_text(self._when_create_text % (productName, productVersion))

        # Add in all the existing (or autopart-created) operating systems.
        for root in self.storage.roots:
            page = Page()
            page.pageTitle = root.name

            for swap in root.swaps:
                selector = page.addDevice("Swap", swap.size, None, self.on_selector_clicked)
                selector._device = swap
                selector._root = root

            for (mountpoint, device) in root.mounts.iteritems():
                selector = page.addDevice(self._mountpointName(mountpoint) or device.format.name, device.size, mountpoint, self.on_selector_clicked)
                selector._device = device
                selector._root = root

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

            if not did_expand and self._current_selector and root == self._current_selector._root:
                did_expand = True
                self._accordion.expandPage(root.name)

        # Anything that doesn't go with an OS we understand?  Put it in the Other box.
        unused = self._unusedDevices()
        if unused:
            page = UnknownPage()
            page.pageTitle = _("Unknown")

            for u in unused:
                selector = page.addDevice(u.format.name, u.size, None, self.on_selector_clicked)
                selector._device = u
                selector._root = None

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

            if not did_expand and self._current_selector and unused == self._current_selector._root:
                did_expand = True
                self._accordion.expandPage(page.pageTitle)

    ###
    ### RIGHT HAND SIDE METHODS
    ###

    def _description(self, name):
        if name == "Swap":
            return _("The 'swap' area on your computer is used by the operating\n" \
                     "system when running low on memory.")
        elif name == "Boot":
            return _("The 'boot' area on your computer is where files needed\n" \
                     "to start the operating system are stored.")
        elif name == "Root":
            return _("The 'root' area on your computer is where core system\n" \
                     "files and applications are stored.")
        elif name == "Home":
            return _("The 'home' area on your computer is where all your personal\n" \
                     "data is stored.")
        elif name == "BIOS Boot":
            return _("No one knows what this could possibly be for.")
        else:
            return ""

    def _save_right_side(self, selector):
        if not selector:
            return

        labelEntry = self.builder.get_object("labelEntry")

        device = selector._device

        if hasattr(device.format, "label") and labelEntry.get_text():
            device.format.label = labelEntry.get_text()

    def _populate_right_side(self, selector):
        encryptCheckbox = self.builder.get_object("encryptCheckbox")
        labelEntry = self.builder.get_object("labelEntry")
        selectedDeviceLabel = self.builder.get_object("selectedDeviceLabel")
        selectedDeviceDescLabel = self.builder.get_object("selectedDeviceDescLabel")
        sizeSpinner = self.builder.get_object("sizeSpinner")
        typeCombo = self.builder.get_object("deviceTypeCombo")
        fsCombo = self.builder.get_object("fileSystemTypeCombo")

        device = selector._device

        selectedDeviceLabel.set_text(selector.props.name)
        selectedDeviceDescLabel.set_text(self._description(selector.props.name))

        labelEntry.set_text(getattr(device.format, "label", "") or "")
        labelEntry.set_sensitive(getattr(device.format, "labelfsProg", "") != "")

        if labelEntry.get_sensitive():
            labelEntry.props.has_tooltip = False
        else:
            labelEntry.set_tooltip_text(_("This file system does not support labels."))

        sizeSpinner.set_range(device.minSize, device.maxSize)
        sizeSpinner.set_value(device.size)
        sizeSpinner.set_sensitive(device.resizable)

        if sizeSpinner.get_sensitive():
            sizeSpinner.props.has_tooltip = False
        else:
            sizeSpinner.set_tooltip_text(_("This file system may not be resized."))

        encryptCheckbox.set_active(device.encrypted)

        # FIXME:  What do we do if we can't figure it out?
        if device.type == "lvmlv":
            typeCombo.set_active(1)
        elif device.type in ["dm-raid array", "mdarray"]:
            typeCombo.set_active(2)
        elif device.type == "partition":
            typeCombo.set_active(3)

        # FIXME:  What do we do if we can't figure it out?
        model = fsCombo.get_model()
        for i in range(0, len(model)):
            if model[i][0] == device.format.name:
                fsCombo.set_active(i)
                break

    ###
    ### SIGNAL HANDLERS
    ###

    def on_back_clicked(self, button):
        self.skipTo = "StorageSpoke"
        NormalSpoke.on_back_clicked(self, button)

    # Use the default back action here, since the finish button takes the user
    # to the install summary screen.
    def on_finish_clicked(self, button):
        self._save_right_side(self._current_selector)
        NormalSpoke.on_back_clicked(self, button)

    def on_add_clicked(self, button):
        dialog = AddDialog(self.data)
        with enlightbox(self.window, dialog.window):
            dialog.refresh()
            rc = dialog.run()

            if rc == 1:
                # FIXME:  Do creation.
                pass

    def _destroy_device(self, device):
        # if this device has parents with no other children, remove them too
        parents = device.parents[:]
        self.storage.destroyDevice(device)
        for parent in parents:
            if parent.kids == 0 and not parent.isDisk:
                self._destroy_device(parent)

    def _remove_from_ui(self, root, device):
        if root is None:
            pass    # unused device
        elif device in root.swaps:
            root.swaps.remove(device)
        elif hasattr(device.format, "mountpoint") and \
             device in root.mounts.values():
            mountpoints = [m for (m,d) in root.mounts.items() if d == device]
            for mountpoint in mountpoints:
                root.mounts.pop(mountpoint)

        self._destroy_device(device)

        # Now that it's removed from the installation root, refreshing the
        # display will have the effect of making it disappear.  It's like
        # it never existed.
        self._do_refresh()

        # Make sure there's something displayed on the RHS.  Just default to
        # the first mountpoint in the page.
        # FIXME: the current page appears to be the default/empty/create page,
        #        even if you've obviously gone into one of the roots to remove
        #        a device
        page = self._accordion.currentPage()
        if getattr(page, "_members", []):
            self._populate_right_side(page._members[0])

        self._updateSpaceDisplay()

    def on_remove_clicked(self, button):

        if not self._current_selector:
            return

        device = self._current_selector._device
        if device.exists:
            # This is a device that exists on disk and most likely has data
            # on it.  Thus, we first need to confirm with the user and then
            # schedule actions to delete the thing.
            dialog = ConfirmDeleteDialog(self.data)
            with enlightbox(self.window, dialog.window):
                dialog.refresh(getattr(device.format, "mountpoint", None), device.name)
                rc = dialog.run()

                if rc == 0:
                    return

        self._remove_from_ui(self._current_selector._root, device)

    def on_summary_clicked(self, button):
        dialog = SelectedDisksDialog(self.data)

        with enlightbox(self.window, dialog.window):
            dialog.refresh(self._clearpartDevices(), showRemove=False)
            dialog.run()

    def on_configure_clicked(self, button):
        pass

    def on_selector_clicked(self, selector):
        # Make sure we're showing details instead of the "here's how you create
        # a new OS" label.
        self._partitionsNotebook.set_current_page(1)

        # Take care of the previously chosen selector.
        if self._current_selector:
            self._save_right_side(self._current_selector)
            self._current_selector.set_chosen(False)

        # Set up the newly chosen selector.
        self._populate_right_side(selector)
        selector.set_chosen(True)
        self._current_selector = selector

        self._configButton.set_sensitive(True)

    def on_page_clicked(self, page):
        # This is called when a Page header is clicked upon so we can support
        # deleting an entire installation at once and displaying something
        # on the RHS.
        if isinstance(page, CreateNewPage) or isinstance(page, UnknownPage):
            self._removeButton.set_sensitive(False)
            return

        self._removeButton.set_sensitive(True)

    def on_create_clicked(self, button):
        from pyanaconda.storage import Root
        from pyanaconda.storage.devices import DiskDevice
        from pyanaconda.storage.partitioning import doAutoPartition

        # Then do autopartitioning.  We do not do any clearpart first.  This is
        # custom partitioning, so you have to make your own room.
        # FIXME:  Handle all the autopart exns here.
        self.data.autopart.autopart = True
        self.data.autopart.execute(self.storage, self.data, self.instclass)

        # Create a new Root object for the new installation and put it into
        # the storage object.  This means any boot-related devices we make for
        # this new install (biosboot, etc.) will show up as unused and therefore
        # be put into the Unknown page.
        mounts = {}
        swaps = []

        # Devices just created by autopartitioning will be listed as unused
        # since they are not yet a part of any known Root.
        for device in self._unusedDevices():
            if device.exists:
                continue

            if device.format.type == "swap":
                swaps.append(device)

            if getattr(device.format, "mountpoint", None):
                mounts[device.format.mountpoint] = device

        newName = _("New %s %s Installation") % (productName, productVersion)
        root = Root(mounts=mounts, swaps=swaps, name=newName)
        self.storage.roots.append(root)

        # Setting this ensures the CreateNewPage instance does not reappear when
        # refresh is called.
        self._ran_autopart = True

        # And refresh the spoke to make the new partitions appear.
        self.refresh()
        self._accordion.expandPage(newName)

    def on_device_type_changed(self, combo):
        text = combo.get_active_text()

        if text == _("BTRFS"):
            self._optionsNotebook.show()
            self._optionsNotebook.set_current_page(0)
        elif text == _("LVM"):
            self._optionsNotebook.show()
            self._optionsNotebook.set_current_page(1)
        elif text == _("RAID"):
            self._optionsNotebook.show()
            self._optionsNotebook.set_current_page(2)
        elif text == _("Standard Partition"):
            self._optionsNotebook.hide()
