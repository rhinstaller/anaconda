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
# - Tabbing behavior in the accordion is weird.

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

from contextlib import contextmanager

from pykickstart.constants import *

from pyanaconda.product import productName, productVersion
from pyanaconda.storage.formats import device_formats
from pyanaconda.storage.formats import getFormat
from pyanaconda.storage.size import Size
from pyanaconda.storage import Root
from pyanaconda.storage.partitioning import doPartitioning
from pyanaconda.storage.partitioning import doAutoPartition
from pyanaconda.storage.errors import StorageError

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.storage import StorageChecker
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.accordion import *
from pyanaconda.ui.gui.utils import enlightbox, setViewportBackground
from pyanaconda.ui.gui.categories.storage import StorageCategory

from gi.repository import Gtk

import logging
log = logging.getLogger("anaconda")

__all__ = ["CustomPartitioningSpoke"]

new_install_name = _("New %s %s Installation") % (productName, productVersion)

class UIStorageFilter(logging.Filter):
    def filter(self, record):
        record.name = "storage.ui"
        return True

@contextmanager
def ui_storage_logger():
    storage_log = logging.getLogger("storage")
    f = UIStorageFilter()
    storage_log.addFilter(f)
    yield
    storage_log.removeFilter(f)

class AddDialog(UIObject):
    builderObjects = ["addDialog"]
    mainWidgetName = "addDialog"
    uiFile = "spokes/custom.glade"

    def __init__(self, *args, **kwargs):
        UIObject.__init__(self, *args, **kwargs)
        self.size = Size(bytes=0)
        self.mountpoint = ""

    def on_add_cancel_clicked(self, button, *args):
        self.window.destroy()

    def on_add_confirm_clicked(self, button, *args):
        self.mountpoint = self.builder.get_object("addMountPointEntry").get_text()

        size_text = self.builder.get_object("sizeEntry").get_text()
        try:
            self.size = Size(spec=size_text)
        except Exception:
            pass

        self.window.destroy()

    def refresh(self):
        UIObject.refresh(self)

    def run(self):
        return self.window.run()

class ConfirmDeleteDialog(UIObject):
    builderObjects = ["confirmDeleteDialog"]
    mainWidgetName = "confirmDeleteDialog"
    uiFile = "spokes/custom.glade"

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

class CustomPartitioningSpoke(NormalSpoke, StorageChecker):
    builderObjects = ["customStorageWindow", "sizeAdjustment",
                      "partitionStore",
                      "addImage", "removeImage", "settingsImage"]
    mainWidgetName = "customStorageWindow"
    uiFile = "spokes/custom.glade"

    category = StorageCategory
    title = N_("MANUAL PARTITIONING")

    def __init__(self, data, storage, payload, instclass):
        NormalSpoke.__init__(self, data, storage, payload, instclass)

        self._current_selector = None
        self._when_create_text = ""
        self._devices = []
        self._unused_devices = None     # None indicates uninitialized
        self._free_space = Size(bytes=0)

    def _propagate_actions(self, actions):
        """ Register actions from the UI with the main Storage instance. """
        for ui_action in actions:
            ui_device = ui_action.device
            device = self.storage.devicetree.getDeviceByID(ui_device.id)
            if device is None:
                # This device does not exist in the main devicetree.
                #
                # That means it was created in the ui. If it is still present in
                # the ui device list, schedule a create action for it. If not,
                # just ignore it.
                if not ui_action.isCreate or ui_device not in self._devices:
                    # this is a device that was created and then destroyed here
                    continue

            args = [device]
            if ui_action.isResize:
                args.append(ui_device.targetSize)

            if ui_action.isCreate and ui_action.isFormat:
                args.append(ui_device.format)

            if ui_action.isCreate and ui_action.isDevice:
                # We're going to just move the already-defined device into the
                # main devicetree, but first we need to replace its parents
                # with the corresponding devices from the main devicetree
                # instead of the ones from our local devicetree.
                parents = [self.storage.devicetree.getDeviceByID(p.id)
                            for p in ui_device.parents]

                if hasattr(ui_device, "partedPartition"):
                    # This cleans up any references to parted.Disk instances
                    # that only exist in our local devicetree.
                    ui_device.partedPartition = None

                    req_disks = [self.storage.devicetree.getDeviceByID(p.id)
                                    for p in ui_device.req_disks]
                    ui_device.req_disks = req_disks

                # If we somehow ended up with a different number of parents
                # go ahead and take a dump on the floor.
                assert(len(parents) == len(ui_device.parents))
                ui_device.parents = parents
                args = [ui_device]

            log.debug("duplicating action '%s'" % ui_action)
            action = ui_action.__class__(*args)
            self.storage.devicetree.registerAction(action)

    def apply(self):
        ui_devicetree = self.__storage.devicetree

        log.debug("converting custom spoke changes into actions")
        for action in ui_devicetree.findActions():
            log.debug("%s" % action)

        # schedule actions for device removals, resizes
        actions = ui_devicetree.findActions(type="destroy")
        partition_destroys = [a for a in actions
                                if a.device.type == "partition"]
        actions.extend(ui_devicetree.findActions(type="resize"))
        self._propagate_actions(actions)

        # register all disklabel create actions
        actions = ui_devicetree.findActions(type="create", object="format")
        disklabel_creates = [a for a in actions
                                if a.device.format.type == "disklabel"]
        self._propagate_actions(disklabel_creates)

        # register partition create actions, including formatting
        actions = ui_devicetree.findActions(type="create")
        partition_creates = [a for a in actions if a.device.type == "partition"]
        self._propagate_actions(partition_creates)

        if partition_creates or partition_destroys:
            try:
                doPartitioning(self.storage)
            except Exception as e:
                # TODO: error handling
                raise

        # register all other create actions
        already_handled = disklabel_creates + partition_creates
        actions = [a for a in ui_devicetree.findActions(type="create")
                        if a not in already_handled]
        self._propagate_actions(actions)

        # set up bootloader and check the configuration
        self.storage.setUpBootLoader()
        StorageChecker.run(self)

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

    @property
    def _clearpartDevices(self):
        return [d for d in self._devices if d.name in self.data.clearpart.drives]

    @property
    def unusedDevices(self):
        if self._unused_devices is None:
            self._unused_devices = [d for d in self.__storage.unusedDevices
                                        if d.disks and not d.isDisk]

        return self._unused_devices

    def _setCurrentFreeSpace(self):
        """Add up all the free space on selected disks and return it as a Size."""
        freeDisks = self.__storage.getFreeSpace(clearPartType=CLEARPART_TYPE_NONE)
        self._free_space = sum([f[0] for f in freeDisks.values()])

    def _currentTotalSpace(self):
        """Add up the sizes of all selected disks and return it as a Size."""
        totalSpace = 0

        for disk in self._clearpartDevices:
            totalSpace += disk.size

        return Size(spec="%s MB" % totalSpace)

    def _updateSpaceDisplay(self):
        # Set up the free space/available space displays in the bottom left.
        self._setCurrentFreeSpace()
        self._availableSpaceLabel = self.builder.get_object("availableSpaceLabel")
        self._totalSpaceLabel = self.builder.get_object("totalSpaceLabel")
        self._summaryButton = self.builder.get_object("summary_button")

        self._availableSpaceLabel.set_text(str(self._free_space))
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
        self.__storage = self.storage.copy()
        self.__storage.devicetree._actions = [] # keep things simple
        self._devices = self.__storage.devices
        self._do_refresh()

        # update our free space number based on Storage
        self._setCurrentFreeSpace()

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

        unused = [d for d in self.unusedDevices if d.isleaf]
        new_devices = [d for d in self._devices if not d.exists]

        log.debug("ui: unused=%s" % [d.name for d in unused])
        log.debug("ui: new_devices=%s" % [d.name for d in new_devices])

        ui_roots = self.__storage.roots[:]

        # If we've not yet run autopart, add an instance of CreateNewPage.  This
        # ensures it's only added once.
        if not new_devices:
            page = CreateNewPage(self.on_create_clicked)
            page.pageTitle = new_install_name
            self._accordion.addPage(page, cb=self.on_page_clicked)
            self._accordion.expandPage(page.pageTitle)
            did_expand = True

            self._partitionsNotebook.set_current_page(0)
            label = self.builder.get_object("whenCreateLabel")
            label.set_text(self._when_create_text % (productName, productVersion))
        else:
            swaps = [d for d in new_devices if d.format.type == "swap"]
            mounts = dict([(d.format.mountpoint, d) for d in new_devices
                                if getattr(d.format, "mountpoint", None)])
            new_root = Root(mounts=mounts, swaps=swaps, name=new_install_name)
            ui_roots.insert(0, new_root)

        # Add in all the existing (or autopart-created) operating systems.
        for root in ui_roots:
            # don't make a page if none of the root's devices are left
            if not [d for d in root.swaps + root.mounts.values()
                        if d in self._devices]:
                continue

            page = Page()
            page.pageTitle = root.name

            for device in root.swaps:
                if device not in self._devices:
                    continue

                selector = page.addDevice("Swap",
                                          Size(spec="%f MB" % device.size),
                                          None, self.on_selector_clicked)
                selector._device = device
                selector._root = root

            for (mountpoint, device) in root.mounts.iteritems():
                if device not in self._devices:
                    continue

                selector = page.addDevice(self._mountpointName(mountpoint) or device.format.name, Size(spec="%f MB" % device.size), mountpoint, self.on_selector_clicked)
                selector._device = device
                selector._root = root

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

            if not did_expand:
                did_expand = True
                self._accordion.expandPage(root.name)

        # Anything that doesn't go with an OS we understand?  Put it in the Other box.
        if unused:
            page = UnknownPage()
            page.pageTitle = _("Unknown")

            for u in unused:
                selector = page.addDevice(u.format.name, Size(spec="%f MB" % u.size), None, self.on_selector_clicked)
                selector._device = u
                selector._root = None

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

            if not did_expand:
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

        if labelEntry.get_text() and hasattr(device.format, "label"):
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
        can_label = getattr(device.format, "labelfsProg", "") != ""
        labelEntry.set_sensitive(can_label)

        if labelEntry.get_sensitive():
            labelEntry.props.has_tooltip = False
        else:
            labelEntry.set_tooltip_text(_("This file system does not support labels."))

        sizeSpinner.set_range(device.minSize,
                              device.maxSize)
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
        elif device.type == "mdarray":
            typeCombo.set_active(2)
        elif device.type == "partition":
            typeCombo.set_active(3)
        elif device.type.startswith("btrfs"):
            typeCombo.set_active(0)

        # FIXME:  What do we do if we can't figure it out?
        model = fsCombo.get_model()
        for i in range(0, len(model)):
            if model[i][0] == device.format.type:
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

            if rc != 1:
                # user cancel
                return

        # create a device of the default type, using any disks, with an
        # appropriate fstype and mountpoint
        mountpoint = dialog.mountpoint
        log.debug("requested size = %s  ; available space = %s"
                    % (dialog.size, self._free_space))
        size = min(dialog.size, self._free_space)
        fstype = self.storage.getFSType(mountpoint)
        encrypted = self.data.autopart.encrypted

        # we're doing nothing here to ensure that bootable requests end up on
        # the boot disk, but the weight from platform should take care of this

        if mountpoint.lower() == "swap":
            mountpoint = None

        # TODO: validate the mountpoint for sanity and uniqueness

        device_type = self.data.autopart.type
        if device_type == AUTOPART_TYPE_LVM and \
             mountpoint == "/boot/efi":
            device_type = AUTOPART_TYPE_PLAIN
        elif device_type == AUTOPART_TYPE_BTRFS and \
             (fstype == "swap" or \
              (mountpoint and mountpoint.startswith("/boot"))):
            device_type = AUTOPART_TYPE_PLAIN

        disks = self._clearpartDevices

        with ui_storage_logger():
            self.__storage.newDevice(device_type,
                                     size=float(size.convertTo(spec="mb")),
                                     fstype=fstype,
                                     mountpoint=mountpoint,
                                     encrypted=encrypted,
                                     disks=disks)
        self._devices = self.__storage.devices
        self._do_refresh()
        self._updateSpaceDisplay()

    def _destroy_device(self, device):
        with ui_storage_logger():
            self.__storage.destroyDevice(device)

        self._devices = self.__storage.devices

        # should this be in DeviceTree._removeDevice?
        container = None
        if hasattr(device, "vg"):
            device.vg._removeLogVol(device)
            container = device.vg
            device_type = AUTOPART_TYPE_LVM
        elif hasattr(device, "volume"):
            device.volume._removeSubVolume(device.name)
            container = device.volume
            device_type = AUTOPART_TYPE_BTRFS

        if container and not container.exists:
            # adjust container to size of remaining devices
            with ui_storage_logger():
                # TODO: raid
                factory = self.__storage.getDeviceFactory(device_type, 0)
                parents = self.__storage.setContainerMembers(container, factory)

        # if this device has parents with no other children, remove them too
        for parent in device.parents:
            if parent.kids == 0 and not parent.isDisk:
                self._destroy_device(parent)

    def _remove_from_root(self, root, device):
        if root is None:
            pass    # unused device
        elif device in root.swaps:
            root.swaps.remove(device)
        elif device in root.mounts.values():
            mountpoints = [m for (m,d) in root.mounts.items() if d == device]
            for mountpoint in mountpoints:
                root.mounts.pop(mountpoint)

    def _show_first_mountpoint(self):
        # Make sure there's something displayed on the RHS.  Just default to
        # the first mountpoint in the page.
        page = self._accordion.currentPage()
        if getattr(page, "_members", []):
            self._populate_right_side(page._members[0])
            page._members[0].grab_focus()

    def _update_ui_for_removals(self):
        # Now that devices have been removed from the installation root,
        # refreshing the display will have the effect of making them disappear.
        # It's like they never existed.
        self._do_refresh()

        self._show_first_mountpoint()
        self._updateSpaceDisplay()

    def on_remove_clicked(self, button):
        if self._current_selector:
            device = self._current_selector._device
            if device.exists:
                # This is a device that exists on disk and most likely has data
                # on it.  Thus, we first need to confirm with the user and then
                # schedule actions to delete the thing.
                dialog = ConfirmDeleteDialog(self.data)
                with enlightbox(self.window, dialog.window):
                    dialog.refresh(getattr(device.format, "mountpoint", ""),
                                   device.name)
                    rc = dialog.run()

                    if rc == 0:
                        return

            root = self._current_selector._root

            self._remove_from_root(root, device)
            self._destroy_device(device)
            self._update_ui_for_removals()
        elif self._accordion.currentPage():
            # This is a complete installed system.  Thus, we first need to confirm
            # with the user and then schedule actions to delete everything.
            page = self._accordion.currentPage()
            dialog = ConfirmDeleteDialog(self.data)

            # Find the root this page displays.
            root = None
            if len(page._members) > 0:
                root = page._members[0]._root

            if not root:
                return

            with enlightbox(self.window, dialog.window):
                dialog.refresh(None, page.pageTitle)
                rc = dialog.run()

                if rc == 0:
                    return

            # Destroy all devices.
            for device in root.swaps + root.mounts.values():
                self._destroy_device(device)

            self._update_ui_for_removals()

    def on_summary_clicked(self, button):
        free = self._free_space
        dialog = SelectedDisksDialog(self.data)

        with enlightbox(self.window, dialog.window):
            dialog.refresh(self._clearpartDevices, free, showRemove=False)
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
        self._removeButton.set_sensitive(True)

    def on_page_clicked(self, page):
        # This is called when a Page header is clicked upon so we can support
        # deleting an entire installation at once and displaying something
        # on the RHS.
        if isinstance(page, CreateNewPage) or isinstance(page, UnknownPage):
            self._removeButton.set_sensitive(False)
            return

        self._removeButton.set_sensitive(True)

    def _do_autopart(self):
        # There are never any non-existent devices around when this runs.
        log.debug("running automatic partitioning")
        self.__storage.doAutoPart = True
        with ui_storage_logger():
            doAutoPartition(self.__storage, self.data)
        self.__storage.doAutoPart = False
        self._devices = self.__storage.devices
        log.debug("finished automatic partitioning")

    def on_create_clicked(self, button):
        # Then do autopartitioning.  We do not do any clearpart first.  This is
        # custom partitioning, so you have to make your own room.
        self._do_autopart()

        # Refresh the spoke to make the new partitions appear.
        log.debug("refreshing ui")
        self._do_refresh()
        log.debug("finished refreshing ui")
        log.debug("updating space display")
        self._updateSpaceDisplay()
        log.debug("finished updating space display")
        self._accordion.expandPage(new_install_name)

        # And then display the first filesystem on the RHS.
        self._show_first_mountpoint()

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


