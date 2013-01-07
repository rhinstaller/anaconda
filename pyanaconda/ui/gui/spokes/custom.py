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
#                    David Lehman <dlehman@redhat.com>
#

# TODO:
# - Add a way for users to specify the names of subvols.
# - We should either remove boot disk selection from the cart we show from here
#   or re-partition when it gets changed to make a best-effort at keeping up.
# - Deleting an LV is not reflected in available space in the bottom left.
#   - this is only true for preexisting LVs
# - Device descriptions, suggested sizes, etc. should be moved out into a support file.
# - Tabbing behavior in the accordion is weird.
# - Update feature space costs when size spinner changes.
# - Implement striping and mirroring for LVM.
# - Implement container management for btrfs.
# - If you click to add a mountpoint while editing a device the lightbox
#   screenshot is taken prior to the ui update so the background shows the old
#   size and free space while you're deciding on a size for the new device.
# - DeviceTree.populate brings back deleted devices when unlocking LUKS.

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

from contextlib import contextmanager
import re

from pykickstart.constants import *

from pyanaconda.product import productName, productVersion
from pyanaconda.threads import threadMgr

from pyanaconda.storage.formats import device_formats
from pyanaconda.storage.formats import getFormat
from pyanaconda.storage.formats.fs import FS
from pyanaconda.storage.size import Size
from pyanaconda.storage import Root
from pyanaconda.storage import DEVICE_TYPE_LVM
from pyanaconda.storage import DEVICE_TYPE_BTRFS
from pyanaconda.storage import DEVICE_TYPE_PARTITION
from pyanaconda.storage import DEVICE_TYPE_MD
from pyanaconda.storage import DEVICE_TYPE_DISK
from pyanaconda.storage import getDeviceType
from pyanaconda.storage import getRAIDLevel
from pyanaconda.storage import findExistingInstallations
from pyanaconda.storage.partitioning import doPartitioning
from pyanaconda.storage.partitioning import doAutoPartition
from pyanaconda.storage.errors import StorageError
from pyanaconda.storage.errors import NoDisksError
from pyanaconda.storage.errors import NotEnoughFreeSpaceError
from pyanaconda.storage.errors import ErrorRecoveryFailure
from pyanaconda.storage.errors import CryptoError
from pyanaconda.storage.errors import MDRaidError
from pyanaconda.storage.devicelibs import mdraid
from pyanaconda.storage.devices import LUKSDevice

from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui import communication
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.storage import StorageChecker
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.passphrase import PassphraseDialog
from pyanaconda.ui.gui.spokes.lib.accordion import *
from pyanaconda.ui.gui.utils import enlightbox, setViewportBackground
from pyanaconda.ui.gui.categories.storage import StorageCategory

from gi.repository import Gtk

import logging
log = logging.getLogger("anaconda")

__all__ = ["CustomPartitioningSpoke"]

NOTEBOOK_LABEL_PAGE = 0
NOTEBOOK_DETAILS_PAGE = 1
NOTEBOOK_LUKS_PAGE = 2
NOTEBOOK_UNEDITABLE_PAGE = 3
NOTEBOOK_INCOMPLETE_PAGE = 4

new_install_name = N_("New %s %s Installation")
new_vg_text = N_("Create a new volume group ...")
unrecoverable_error_msg = N_("Storage configuration reset due to unrecoverable "
                             "error. Click for details.")
device_configuration_error_msg = N_("Device reconfiguration failed. Click for "
                                    "details.")

empty_mountpoint_msg = N_("Please enter a valid mountpoint.")
invalid_mountpoint_msg = N_("That mount point is invalid. Try something else?")
mountpoint_in_use_msg = N_("That mount point is already in use. Try something else?")

MOUNTPOINT_OK = 0
MOUNTPOINT_INVALID = 1
MOUNTPOINT_IN_USE = 2
MOUNTPOINT_EMPTY = 3

mountpoint_validation_msgs = {MOUNTPOINT_OK: "",
                              MOUNTPOINT_INVALID: invalid_mountpoint_msg,
                              MOUNTPOINT_IN_USE: mountpoint_in_use_msg,
                              MOUNTPOINT_EMPTY: empty_mountpoint_msg}

DEVICE_TEXT_LVM = N_("LVM")
DEVICE_TEXT_MD = N_("RAID")
DEVICE_TEXT_PARTITION = N_("Standard Partition")
DEVICE_TEXT_BTRFS = N_("BTRFS")
DEVICE_TEXT_DISK = N_("Disk")

device_text_map = {DEVICE_TYPE_LVM: DEVICE_TEXT_LVM,
                   DEVICE_TYPE_MD: DEVICE_TEXT_MD,
                   DEVICE_TYPE_PARTITION: DEVICE_TEXT_PARTITION,
                   DEVICE_TYPE_BTRFS: DEVICE_TEXT_BTRFS}

options_page_dict = {DEVICE_TYPE_LVM: 0,
                     DEVICE_TYPE_MD: 1,
                     DEVICE_TYPE_BTRFS: 2}

# raid feature names. These are the basis for some UI widget names.
raid_features = ["Performance", "Redundancy", "Error", "DistError",
                 "RedundantError"]

# feature names by raid level
raid_level_features = {"raid0": ["Performance"],
                       "raid1": ["Redundancy"],
                       "raid10": ["Performance", "Redundancy"],
                       "raid4": ["Performance", "Error"],
                       "raid5": ["Performance", "DistError"],
                       "raid6": ["Performance", "RedundantError"],
                       "single": []}

# disabled features by raid_level
raid_disabled_features = {"raid1": ["Error", "DistError", "RedundantError"],
                          "raid10": ["Error", "DistError", "RedundantError"],
                          "raid4": ["Performance", "Redundancy", "DistError", "RedundantError"],
                          "raid5": ["Performance", "Redundancy", "Error", "RedundantError"],
                          "raid6": ["Performance", "Redundancy", "Error", "DistError"],
                          None: ["Error", "DistError", "RedundantError"],
}

# reference raid level by feature name
feature_raid_levels = {"Performance": "raid0",
                       "Redundancy": "raid1",
                       "Error": "raid4",
                       "DistError": "raid5",
                       "RedundantError": "raid6"}

partition_only_format_types = ["efi", "hfs+", "prepboot", "biosboot",
                               "appleboot"]

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

def populate_mountpoint_store(store, used_mountpoints):
    # sure, add whatever you want to this list. this is just a start.
    paths = ["/", "/boot", "/home", "/usr", "/var",
             "swap", "biosboot", "prepboot"]
    for path in paths:
        if path not in used_mountpoints:
            store.append([path])

def validate_mountpoint(mountpoint, used_mountpoints, strict=True):
    if strict:
        fake_mountpoints = []
    else:
        fake_mountpoints = ["swap", "biosboot", "prepboot"]

    valid = MOUNTPOINT_OK
    if mountpoint in used_mountpoints:
        valid = MOUNTPOINT_IN_USE
    elif not mountpoint:
        valid = MOUNTPOINT_EMPTY
    elif (mountpoint.lower() not in fake_mountpoints and
          ((len(mountpoint) > 1 and mountpoint.endswith("/")) or
           not mountpoint.startswith("/") or
           " " in mountpoint or
           re.search(r'/\.*/', mountpoint) or
           re.search(r'/\.+$', mountpoint))):
        # - does not end with '/' unless mountpoint _is_ '/'
        # - starts with '/' except for "swap", &c
        # - does not contain spaces
        # - does not contain pairs of '/' enclosing zero or more '.'
        # - does not end with '/' followed by one or more '.'
        valid = MOUNTPOINT_INVALID

    return valid

class AddDialog(GUIObject):
    builderObjects = ["addDialog", "mountPointStore", "mountPointCompletion"]
    mainWidgetName = "addDialog"
    uiFile = "spokes/custom.glade"

    def __init__(self, *args, **kwargs):
        self.mountpoints = kwargs.pop("mountpoints", [])
        GUIObject.__init__(self, *args, **kwargs)
        self.size = Size(bytes=0)
        self.mountpoint = ""
        self._error = False

        store = self.builder.get_object("mountPointStore")
        populate_mountpoint_store(store, self.mountpoints)

        completion = self.builder.get_object("mountPointCompletion")
        completion.set_text_column(0)
        completion.set_popup_completion(True)

    def on_add_confirm_clicked(self, button, *args):
        self.mountpoint = self.builder.get_object("addMountPointEntry").get_text()
        self._error = validate_mountpoint(self.mountpoint, self.mountpoints,
                                          strict=False)
        self._warningLabel.set_text(_(mountpoint_validation_msgs[self._error]))
        self.window.show_all()
        if self._error:
            return

        size_text = self.builder.get_object("sizeEntry").get_text().strip()

        # if no unit was specified, default to MB
        if not re.search(r'[A-Za-z]+$', size_text):
            size_text += "MB"

        try:
            self.size = Size(spec=size_text)
        except Exception:
            pass
        else:
            # Minimum size for ui-created partitions is 1MB.
            if self.size.convertTo(spec="mb") < 1:
                self.size = Size(spec="1mb")

        self.window.destroy()

    def refresh(self):
        GUIObject.refresh(self)
        self._warningLabel = self.builder.get_object("mountPointWarningLabel")
        self._warningLabel.set_text("")

    def run(self):
        while True:
            self._error = None
            rc = self.window.run()
            if not self._error:
                return rc

class ConfirmDeleteDialog(GUIObject):
    builderObjects = ["confirmDeleteDialog"]
    mainWidgetName = "confirmDeleteDialog"
    uiFile = "spokes/custom.glade"

    @property
    def deleteAll(self):
        return self._removeAll.get_active()

    def on_delete_confirm_clicked(self, button, *args):
        self.window.destroy()

    def refresh(self, mountpoint, device, rootName):
        GUIObject.refresh(self)
        label = self.builder.get_object("confirmLabel")

        self._removeAll = self.builder.get_object("removeAllCheckbox")
        self._removeAll.set_label(self._removeAll.get_label() % rootName)
        self._removeAll.set_sensitive(rootName is not None)

        if mountpoint:
            txt = "%s (%s)" % (mountpoint, device)
        else:
            txt = device

        label.set_text(label.get_text() % txt)

    def run(self):
        return self.window.run()

class DisksDialog(GUIObject):
    builderObjects = ["disks_dialog", "disk_store", "disk_view"]
    mainWidgetName = "disks_dialog"
    uiFile = "spokes/custom.glade"

    def __init__(self, *args, **kwargs):
        self._disks = kwargs.pop("disks")
        free = kwargs.pop("free")
        self.selected = kwargs.pop("selected")[:]
        GUIObject.__init__(self, *args, **kwargs)
        self._store = self.builder.get_object("disk_store")
        # populate the store
        for disk in self._disks:
            self._store.append([disk.description,
                                str(Size(spec="%dMB" % disk.size)),
                                str(free[disk.name][0]),
                                disk.serial,
                                disk.id])

        treeview = self.builder.get_object("disk_view")
        model = treeview.get_model()
        itr = model.get_iter_first()
        selected_ids = [d.id for d in self.selected]
        selection = treeview.get_selection()
        while itr:
            disk_id = model.get_value(itr, 4)
            if disk_id in selected_ids:
                selection.select_iter(itr)

            itr = model.iter_next(itr)

    def on_cancel_clicked(self, button):
        self.window.destroy()

    def _get_disk_by_id(self, disk_id):
        for disk in self._disks:
            if disk.id == disk_id:
                return disk

    def on_select_clicked(self, button):
        treeview = self.builder.get_object("disk_view")
        model, paths = treeview.get_selection().get_selected_rows()
        self.selected = []
        for path in paths:
            itr = model.get_iter(path)
            disk_id = model.get_value(itr, 4)
            self.selected.append(self._get_disk_by_id(disk_id))

        self.window.destroy()

    def run(self):
        return self.window.run()

class VolumeGroupDialog(GUIObject):
    builderObjects = ["vg_dialog", "disk_store", "vg_disk_view"]
    mainWidgetName = "vg_dialog"
    uiFile = "spokes/custom.glade"

    def __init__(self, *args, **kwargs):
        self._disks = kwargs.pop("disks")
        free = kwargs.pop("free")
        self.name = kwargs.pop("name") or ""
        self.selected = kwargs.pop("selected")[:]
        GUIObject.__init__(self, *args, **kwargs)

        self.builder.get_object("vg_name_entry").set_text(self.name)

        self._store = self.builder.get_object("disk_store")
        # populate the store
        for disk in self._disks:
            self._store.append([disk.description,
                                str(Size(spec="%dMB" % disk.size)),
                                str(free[disk.name][0]),
                                disk.serial,
                                disk.id])

        treeview = self.builder.get_object("vg_disk_view")
        model = treeview.get_model()
        itr = model.get_iter_first()

        selected_ids = [d.id for d in self.selected]
        log.debug("selected: %s" % [d.name for d in self.selected])
        log.debug("selected: %s" % selected_ids)
        selection = treeview.get_selection()
        while itr:
            disk_id = model.get_value(itr, 4)
            log.debug("store: %d" % disk_id)
            if disk_id in selected_ids:
                selection.select_iter(itr)

            itr = model.iter_next(itr)

    def on_cancel_clicked(self, button):
        self.window.destroy()

    def _get_disk_by_id(self, disk_id):
        for disk in self._disks:
            if disk.id == disk_id:
                return disk

    def on_save_clicked(self, button):
        treeview = self.builder.get_object("vg_disk_view")
        model, paths = treeview.get_selection().get_selected_rows()
        self.selected = []
        for path in paths:
            itr = model.get_iter(path)
            disk_id = model.get_value(itr, 4)
            self.selected.append(self._get_disk_by_id(disk_id))

        self.name = self.builder.get_object("vg_name_entry").get_text()

        self.window.destroy()

    def run(self):
        return self.window.run()

class HelpDialog(GUIObject):
    builderObjects = ["help_dialog", "help_text_view", "help_text_buffer"]
    mainWidgetName = "help_dialog"
    uiFile = "spokes/custom.glade"

    def run(self):
        help_text = help_text_template % {"productName": productName}
        help_buffer = self.builder.get_object("help_text_buffer")
        help_buffer.set_text(_(help_text))
        self.window.run()

    def on_close(self, button):
        self.window.destroy()

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
        self._media_disks = []
        self._fs_types = []             # list of supported fstypes
        self._unused_devices = None     # None indicates uninitialized
        self._free_space = Size(bytes=0)

        self._device_disks = []
        self._device_container_name = None
        self._device_name_dict = {DEVICE_TYPE_LVM: None,
                                  DEVICE_TYPE_MD: None,
                                  DEVICE_TYPE_PARTITION: "",
                                  DEVICE_TYPE_BTRFS: "",
                                  DEVICE_TYPE_DISK: ""}

        self._initialized = False

    def apply(self):
        self.clear_errors()

        # unhide any removable install media we hid prior to partitioning
        with ui_storage_logger():
            for disk in reversed(self._media_disks):
                self.__storage.devicetree.unhide(disk)

        # We can't overwrite the main Storage instance because all the other
        # spokes have references to it that would get invalidated, but we can
        # achieve the same effect by updating/replacing a few key attributes.
        self.storage.devicetree._devices = self.__storage.devicetree._devices
        self.storage.devicetree._actions = self.__storage.devicetree._actions
        self.storage.devicetree._hidden = self.__storage.devicetree._hidden
        self.storage.devicetree.names = self.__storage.devicetree.names
        self.storage.roots = self.__storage.roots

        # update the global passphrase
        self.data.autopart.passphrase = self.passphrase

        # make sure any device/passphrase pairs we've obtained are remebered
        for device in self.storage.devices:
            if device.format.type == "luks" and not device.format.exists:
                if not device.format.hasKey:
                    device.format.passphrase = self.passphrase

                self.storage.savePassphrase(device)

        # set up bootloader and check the configuration
        self.storage.setUpBootLoader()

        StorageChecker.errors = []
        StorageChecker.run(self)
        communication.send_ready("StorageSpoke", justUpdate=True)

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

        self._reformatCheckbox = self.builder.get_object("reformatCheckbox")

    def initialize(self):
        NormalSpoke.initialize(self)

        label = self.builder.get_object("whenCreateLabel")
        self._when_create_text = label.get_text()

        self._grabObjects()
        setViewportBackground(self.builder.get_object("availableSpaceViewport"), "#db3279")
        setViewportBackground(self.builder.get_object("totalSpaceViewport"), "#60605b")

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
        fsCombo = self.builder.get_object("fileSystemTypeCombo")
        fsCombo.remove_all()
        self._fs_types = []
        for cls in device_formats.itervalues():
            obj = cls()

            # btrfs is always handled by on_device_type_changed
            supported_fs = (obj.type != "btrfs" and
                            obj.supported and obj.formattable and
                            (isinstance(obj, FS) or
                             obj.type in ["biosboot", "prepboot", "swap"]))
            if supported_fs:
                fsCombo.append_text(obj.name)
                self._fs_types.append(obj.name)

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
        return [d for d in self._devices if d.name in self.data.clearpart.drives and d.partitioned]

    @property
    def unusedDevices(self):
        if self._unused_devices is None:
            self._unused_devices = [d for d in self.__storage.unusedDevices
                                        if d.disks and not d.partitioned and
                                           d.isleaf]
            # add incomplete VGs and MDs
            incomplete = [d for d in self.__storage.devicetree._devices
                                if not getattr(d, "complete", True)]
            self._unused_devices.extend(incomplete)

        return self._unused_devices

    @property
    def existingSwaps(self):
        return [d for d in self._devices
                    if d.format.type == "swap" and d.format.exists]

    @property
    def bootLoaderDevices(self):
        devices = []
        format_types = ["biosboot", "prepboot"]
        for device in self._devices:
            if device.format.type not in format_types:
                continue

            disk_names = [d.name for d in device.disks]
            if self.data.bootloader.bootDrive in disk_names:
                devices.append(device)

        return devices

    @property
    def _currentFreeInfo(self):
        return self.__storage.getFreeSpace(clearPartType=CLEARPART_TYPE_NONE)

    def _setCurrentFreeSpace(self):
        """Add up all the free space on selected disks and return it as a Size."""
        self._free_space = sum([f[0] for f in self._currentFreeInfo.values()])

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

    def _reset_storage(self):
        self.__storage = self.storage.copy()
        self._media_disks = []

        # hide removable disks containing install media
        for disk in self.__storage.disks:
            if disk.removable and disk.protected:
                self._media_disks.append(disk)
                self.__storage.devicetree.hide(disk)

        self._devices = self.__storage.devices
        self._unused_devices = None

    def refresh(self):
        self.clear_errors()
        NormalSpoke.refresh(self)

        # Make sure the storage spoke execute method has finished before we
        # copy the storage instance.
        for thread_name in ["AnaExecuteStorageThread", "AnaStorageThread"]:
            t = threadMgr.get(thread_name)
            if t:
                t.join()

        self.passphrase = self.data.autopart.passphrase
        self._reset_storage()
        self._do_refresh()
        # update our free space number based on Storage
        self._setCurrentFreeSpace()

        self._updateSpaceDisplay()

    @property
    def translated_new_install_name(self):
        return _(new_install_name) % (productName, productVersion)

    def _do_refresh(self):
        # block mountpoint selector signal handler for now
        self._initialized = False
        if self._current_selector:
            self._current_selector.set_chosen(False)
            self._current_selector = None

        # We can only have one page expanded at a time.
        page_order = []
        if self._accordion.currentPage():
            page_order.append(self._accordion.currentPage().pageTitle)

        # Make sure we start with a clean slate.
        self._accordion.removeAllPages()

        # Start with buttons disabled, since nothing is selected.
        self._removeButton.set_sensitive(False)
        self._configButton.set_sensitive(False)

        # Now it's time to populate the accordion.

        # A device scheduled for formatting only belongs in the new root.
        new_devices = [d for d in self._devices if d.isleaf and
                                                   not d.format.exists and
                                                   not d.partitioned]

        # If mountpoints have been assigned to any existing devices, go ahead
        # and pull those in along with any existing swap devices. It doesn't
        # matter if the formats being mounted exist or not.
        new_mounts = [d for d in self.__storage.mountpoints.values() if d.exists]
        if new_mounts or new_devices:
            new_devices.extend(self.__storage.mountpoints.values())
            new_devices.extend(self.existingSwaps)
            new_devices.extend(self.bootLoaderDevices)

        new_devices = list(set(new_devices))

        log.debug("ui: devices=%s" % [d.name for d in self._devices])
        log.debug("ui: unused=%s" % [d.name for d in self.unusedDevices])
        log.debug("ui: new_devices=%s" % [d.name for d in new_devices])

        ui_roots = self.__storage.roots[:]

        # If we've not yet run autopart, add an instance of CreateNewPage.  This
        # ensures it's only added once.
        if not new_devices:
            page = CreateNewPage(self.on_create_clicked)
            page.pageTitle = self.translated_new_install_name
            self._accordion.addPage(page, cb=self.on_page_clicked)

            if page.pageTitle not in page_order:
                page_order.append(page.pageTitle)

            self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
            label = self.builder.get_object("whenCreateLabel")
            label.set_text(self._when_create_text % (productName, productVersion))
        else:
            swaps = [d for d in new_devices if d.format.type == "swap"]
            mounts = dict([(d.format.mountpoint, d) for d in new_devices
                                if getattr(d.format, "mountpoint", None)])

            for device in new_devices:
                if device in self.bootLoaderDevices:
                    mounts[device.format.type] = device

            new_root = Root(mounts=mounts, swaps=swaps, name=self.translated_new_install_name)
            ui_roots.insert(0, new_root)

        # Add in all the existing (or autopart-created) operating systems.
        for root in ui_roots:
            # Don't make a page if none of the root's devices are left.
            # Also, only include devices in an old page if the format is intact.
            if not [d for d in root.swaps + root.mounts.values()
                        if d in self._devices and d.disks and
                           (root.name == self.translated_new_install_name or d.format.exists)]:
                continue

            page = Page()
            page.pageTitle = root.name

            for (mountpoint, device) in root.mounts.iteritems():
                if device not in self._devices or \
                   not device.disks or \
                   (root.name != self.translated_new_install_name and not device.format.exists):
                    continue

                selector = page.addDevice(self._mountpointName(mountpoint) or device.format.name, Size(spec="%f MB" % device.size), mountpoint, self.on_selector_clicked)
                selector._device = device
                selector._root = root

            for device in root.swaps:
                if device not in self._devices or \
                   (root.name != self.translated_new_install_name and not device.format.exists):
                    continue

                selector = page.addDevice("Swap",
                                          Size(spec="%f MB" % device.size),
                                          None, self.on_selector_clicked)
                selector._device = device
                selector._root = root

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

            if root.name not in page_order:
                page_order.append(root.name)

        # Anything that doesn't go with an OS we understand?  Put it in the Other box.
        if self.unusedDevices:
            page = UnknownPage()
            page.pageTitle = _("Unknown")

            for u in sorted(self.unusedDevices, key=lambda d: d.name):
                selector = page.addDevice(u.name, Size(spec="%f MB" % u.size), u.format.name, self.on_selector_clicked)
                selector._device = u

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

            if page.pageTitle not in page_order:
                page_order.append(page.pageTitle)

        for page_name in page_order:
            try:
                self._accordion.expandPage(page_name)
            except LookupError:
                continue
            else:
                break

        self._initialized = True
        self.on_page_clicked(self._accordion.currentPage())

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
            return _("The BIOS boot partition is required to enable booting\n"
                     "from GPT-partitioned disks on BIOS hardware.")
        elif name == "PReP Boot":
            return _("The PReP boot partition is required as part of the\n"
                     "bootloader configuration on some PPC platforms.")
        else:
            return ""

    def add_new_selector(self, device):
        """ Add an entry for device to the new install Page. """
        page = self._accordion._find_by_title(self.translated_new_install_name).get_child()
        devices = [device]
        if not hasattr(page, "_members"):
            # remove the CreateNewPage and replace it with a regular Page
            expander = self._accordion._find_by_title(self.translated_new_install_name)
            expander.remove(expander.get_child())

            page = Page()
            page.pageTitle = self.translated_new_install_name
            expander.add(page)

            # pull in all the existing swap devices
            devices.extend(self.existingSwaps)

            # also pull in biosboot and prepboot that are on our boot disk
            devices.extend(self.bootLoaderDevices)

        for _device in devices:
            mountpoint = getattr(_device.format, "mountpoint", "") or ""

            if _device.format.type == "swap":
                name = "Swap"
            else:
                name = self._mountpointName(mountpoint) or _device.format.name

            selector = page.addDevice(name, Size(spec="%f MB" % _device.size),
                                      mountpoint, self.on_selector_clicked)
            selector._device = _device

        page.show_all()

    def _update_btrfs_selectors(self):
        """ Update all btrfs selectors' size properties. """
        # we're only updating selectors in the new root. problem?
        page = self._accordion._find_by_title(self.translated_new_install_name).get_child()
        if not hasattr(page, "_members"):
            return

        for selector in page._members:
            if selector._device.type.startswith("btrfs"):
                selector.props.size = str(Size(spec="%f MB" % selector._device.size)).upper()

    def _replace_device(self, *args, **kwargs):
        """ Create a replacement device and update the device selector. """
        selector = kwargs.pop("selector", None)
        self.__storage.newDevice(*args, **kwargs)

        self._devices = self.__storage.devices

        if selector:
            # newest device should be the one with the highest id
            max_id = max([d.id for d in self._devices])

            # update the selector with the new device and its size
            selector._device = self.__storage.devicetree.getDeviceByID(max_id)
            selector.props.size = str(Size(spec="%f MB" % selector._device.size)).upper()

    def _save_right_side(self, selector):
        """ Save settings from RHS and apply changes to the device.

            This method must never trigger a call to self._do_refresh.
        """
        if not self._initialized or not selector:
            return

        device = selector._device
        if device not in self._devices:
            # just-removed device
            return

        if self._partitionsNotebook.get_current_page() != NOTEBOOK_DETAILS_PAGE:
            return

        use_dev = device
        if device.type == "luks/dm-crypt":
            use_dev = device.slave

        log.info("ui: saving changes to device %s" % device.name)

        # TODO: member type
        old_name = getattr(use_dev, "lvname", use_dev.name)
        name = old_name
        changed_name = False
        name_entry = self.builder.get_object("nameEntry")
        if name_entry.get_sensitive():
            name = name_entry.get_text()
            changed_name = (name != old_name)
        else:
            # name entry insensitive means we don't control the name
            name = None

        log.debug("old_name: %s" % old_name)
        log.debug("new_name: %s" % name)

        size = self.builder.get_object("sizeSpinner").get_value()
        log.debug("new size: %s" % size)
        log.debug("old size: %s" % device.size)

        device_type = self._get_current_device_type()
        log.debug("new device type: %s" % device_type)

        reformat = self._reformatCheckbox.get_active()
        log.debug("reformat: %s" % reformat)

        fs_type_combo = self.builder.get_object("fileSystemTypeCombo")
        fs_type_index = fs_type_combo.get_active()
        fs_type = fs_type_combo.get_model()[fs_type_index][0]
        log.debug("new fs type: %s" % fs_type)

        prev_encrypted = device.encrypted
        log.debug("old encryption setting: %s" % prev_encrypted)
        encryption_checkbox = self.builder.get_object("encryptCheckbox")
        encrypted = encryption_checkbox.get_active()

        changed_encryption = (prev_encrypted != encrypted)
        log.debug("new encryption setting: %s" % encrypted)

        label_entry = self.builder.get_object("labelEntry")
        label = ""
        if label_entry.get_sensitive():
            label = label_entry.get_text()

        old_label = getattr(device.format, "label", "") or ""

        mountpoint = None   # None means format type is not mountable
        mountPointEntry = self.builder.get_object("mountPointEntry")
        if mountPointEntry.get_sensitive():
            mountpoint = mountPointEntry.get_text()

        old_mountpoint = getattr(device.format, "mountpoint", "") or ""
        log.debug("old mountpoint: %s" % old_mountpoint)
        log.debug("new mountpoint: %s" % mountpoint)
        if mountpoint is not None and (reformat or
                                       mountpoint != old_mountpoint):
            mountpoints = self.__storage.mountpoints.copy()
            if old_mountpoint:
                del mountpoints[old_mountpoint]

            error = validate_mountpoint(mountpoint, mountpoints.keys())
            if error:
                self._error = _(mountpoint_validation_msgs[error])
                self.set_warning(self._error)
                self.window.show_all()
                self._populate_right_side(selector)
                return

        raid_level = self._get_raid_level()

        fs_type_short = getFormat(fs_type).type

        ##
        ## VALIDATION
        ##
        error = None
        if device_type != DEVICE_TYPE_PARTITION and mountpoint == "/boot/efi":
            error = (_("/boot/efi must be on a device of type %s")
                     % _(DEVICE_TEXT_PARTITION))
        elif device_type != DEVICE_TYPE_PARTITION and \
             fs_type_short in partition_only_format_types:
            error = (_("%s must be on a device of type %s")
                     % (fs_type, _(DEVICE_TEXT_PARTITION)))
        elif mountpoint and encrypted and mountpoint.startswith("/boot"):
            error = _("%s cannot be encrypted") % mountpoint
        elif encrypted and fs_type_short in partition_only_format_types:
            error = _("%s cannot be encrypted") % fs_type
        elif mountpoint == "/" and device.format.exists and not reformat:
            error = _("You must create a new filesystem on the root device.")
        elif device_type == DEVICE_TYPE_MD and raid_level in (None, "single"):
            error = _("Devices of type %s require a valid RAID level selection.") % DEVICE_TEXT_MD

        if not error and raid_level not in (None, "single"):
            md_level = mdraid.raidLevel(raid_level)
            min_disks = mdraid.get_raid_min_members(md_level)
            if len(self._device_disks) < min_disks:
                error = _("The RAID level you have selected requires more "
                          "disks than you currently have selected.")

        if error:
            self.set_warning(error)
            self.window.show_all()
            self._populate_right_side(selector)
            return

        # XXX Now we have to do something squirrely with the encryption setting.
        # We've done the checks for things that cannot be on an encrypted
        # device. From here on out, it means "encrypt new devices we create",
        # which we don't want to do in the event that encryption is already
        # present below the surface of an existing device stack.
        encrypted = encrypted and encryption_checkbox.get_sensitive()

        with ui_storage_logger():
            # create a new factory using the appropriate size and type
            factory = self.__storage.getDeviceFactory(device_type, size,
                                                      disks=device.disks,
                                                      encrypted=encrypted,
                                                      raid_level=raid_level)

        # for member type, we'll have to adjust the member set.
        # XXX not going to worry about this for now

        ##
        ## DEVICE TYPE (early return)
        ##
        current_device_type = getDeviceType(device)
        old_raid_level = getRAIDLevel(device)
        changed_device_type = (current_device_type != device_type)
        changed_raid_level = (current_device_type == device_type and
                              device_type in (DEVICE_TYPE_MD,
                                              DEVICE_TYPE_BTRFS) and
                              old_raid_level != raid_level)
        old_disk_set = device.disks
        if hasattr(device, "req_disks") and not device.exists:
            old_disk_set = device.req_disks

        changed_disk_set = (set(old_disk_set) != set(self._device_disks))

        changed_container = False
        old_container_name = None
        container = self.__storage.getContainer(factory)
        if not changed_device_type and device_type == DEVICE_TYPE_LVM:
            old_container = self.__storage.getContainer(factory,
                                                        device=use_dev)
            container = self.__storage.getContainer(factory,
                                                    name=self._device_container_name)
            if self._device_container_name != old_container.name:
                old_container_name = old_container.name
                changed_container = True

        if changed_device_type or changed_raid_level or changed_container:
            if changed_device_type:
                log.info("changing device type from %s to %s"
                            % (current_device_type, device_type))

            if changed_raid_level:
                log.info("changing raid level from %s to %s"
                            % (old_raid_level, raid_level))

            if changed_disk_set:
                log.info("changing disk set from %s to %s"
                            % ([d.name for d in device.disks],
                               [d.name for d in self._device_disks]))

            if changed_container:
                log.info("changing container from %s to %s"
                            % (old_container.name, self._device_container_name))

            # remove the current device
            self.clear_errors()
            root = self._current_selector._root
            self._destroy_device(device)
            if device in self._devices:
                # the removal failed. don't continue.
                return

            with ui_storage_logger():
                disks = self._device_disks[:]
                if container and changed_device_type:
                    log.debug("overriding disk set with container's")
                    disks = container.disks[:]
                log.debug("disks: %s" % [d.name for d in disks])
                try:
                    self._replace_device(device_type, size, fstype=fs_type,
                                         disks=disks, mountpoint=mountpoint,
                                         label=label, raid_level=raid_level,
                                         encrypted=encrypted, name=name,
                                         container_name=self._device_container_name,
                                         selector=selector)
                except ErrorRecoveryFailure as e:
                    self._error = e
                    self.set_warning(_(unrecoverable_error_msg))
                    self.window.show_all()
                    self._reset_storage()
                except StorageError as e:
                    log.error("newDevice failed: %s" % e)
                    self._error = e
                    self.set_warning(_(device_configuration_error_msg)) 
                    self.window.show_all()

                    # in this case we have removed the old device so we now have
                    # to re-create it
                    try:
                        self._replace_device(current_device_type, device.size,
                                             disks=old_disk_set,
                                             fstype=device.format.type,
                                             mountpoint=old_mountpoint,
                                             label=old_label,
                                             raid_level=old_raid_level,
                                             encrypted=prev_encrypted,
                                             name=old_name,
                                             container_name=old_container_name,
                                             selector=selector)
                    except StorageError as e:
                        # failed to recover.
                        self.clear_errors()
                        self._error = e
                        self.set_warning(_(unrecoverable_error_msg))
                        self.window.show_all()
                        self._reset_storage()
                else:
                    # you can't change the type of an existing device, so we
                    # don't need to concern ourselves with adding a new
                    # selector to the new page
                    selector.props.mountpoint = (mountpoint or
                                                 selector._device.format.name)
                    selector.props.name = (self._mountpointName(mountpoint) or
                                           selector._device.format.name)

            self._devices = self.__storage.devices
            # update size props of all btrfs devices' selectors
            self._update_btrfs_selectors()

            self._updateSpaceDisplay()
            self._populate_right_side(selector)
            return

        ##
        ## SIZE
        ##
        # new size means resize for existing devices and adjust for new ones
        changed_size = (int(size) != int(device.size))
        if changed_size or changed_disk_set or \
           (changed_encryption and factory.encrypt_members and
            not device.exists):
            self.clear_errors()
            old_size = device.size
            if changed_size and device.exists and device.resizable:
                with ui_storage_logger():
                    try:
                        self.__storage.resizeDevice(device, size)
                    except StorageError as e:
                        log.error("failed to schedule device resize: %s" % e)
                        device.size = old_size
                        self._error = e
                        self.set_warning(_("Device resize request failed. "
                                           "Click for details."))
                        self.window.show_all()
                    else:
                        log.debug("%r" % device)
                        log.debug("new size: %s" % device.size)
                        log.debug("target size: %s" % device.targetSize)
            elif not device.exists:
                if changed_disk_set:
                    log.info("changing disk set from %s to %s"
                                % ([d.name for d in device.disks],
                                   [d.name for d in self._device_disks]))

                with ui_storage_logger():
                    try:
                        self.__storage.newDevice(device_type, size,
                                                 device=device,
                                                 disks=self._device_disks[:],
                                                 encrypted=encrypted,
                                                 container_name=self._device_container_name,
                                                 raid_level=raid_level)
                    except ErrorRecoveryFailure as e:
                        self._error = e
                        self.set_warning(_(unrecoverable_error_msg))
                        self.window.show_all()
                        self._reset_storage()
                    except StorageError as e:
                        log.error("newDevice failed: %s" % e)
                        self._error = e
                        self.set_warning(_(device_configuration_error_msg))
                        self.window.show_all()

                    self._devices = self.__storage.devices

            log.debug("updating selector size to '%s'"
                       % str(Size(spec="%f MB" % device.size)).upper())
            # update the selector's size property
            selector.props.size = str(Size(spec="%f MB" % device.size)).upper()

            # update size props of all btrfs devices' selectors
            self._update_btrfs_selectors()

            self._updateSpaceDisplay()
            self._populate_right_side(selector)


        ##
        ## NAME
        ##
        if changed_name:
            use_dev._name = name
            new_name = use_dev.name
            if new_name in self.__storage.names:
                use_dev._name = old_name
                self.set_info(_("Specified name %s already in use.") % new_name)
            else:
                if old_name == selector.props.name:
                    selector.props.name = new_name

        if reformat:
            ##
            ## ENCRYPTION
            ##

            # for existing devices, we always encrypt the leaf
            old_fs_type = device.format.type
            old_device = device

            # if the encryption is on member devices it was handled above
            if changed_encryption and (device.exists or factory.encrypt_leaves):
                if prev_encrypted and not encrypted:
                    log.info("removing encryption from %s" % device.name)
                    with ui_storage_logger():
                        self.__storage.destroyDevice(device)
                        self._devices.remove(device)
                        old_device = device
                        device = device.slave
                        selector._device = device
                        for s in self._accordion.allSelectors:
                            if s._device == old_device:
                                s._device = device
                elif encrypted and not prev_encrypted:
                    log.info("applying encryption to %s" % device.name)
                    with ui_storage_logger():
                        old_device = device
                        new_fmt = getFormat("luks", device=device.path)
                        self.__storage.formatDevice(device, new_fmt)
                        luks_dev = LUKSDevice("luks-" + device.name,
                                              parents=[device])
                        self.__storage.createDevice(luks_dev)
                        self._devices.append(luks_dev)
                        device = luks_dev
                        selector._device = device
                        for s in self._accordion.allSelectors:
                            if s._device == old_device:
                                s._device = device

            ##
            ## FORMATTING
            ##
            encryption_changed = (device != old_device)
            if encryption_changed:
                self._devices = self.__storage.devices

            fs_type_changed = (fs_type_short != old_fs_type)
            fs_exists = old_device.format.exists
            if encryption_changed or fs_type_changed or fs_exists:
                log.info("scheduling reformat of %s as %s" % (device.name,
                                                              fs_type_short))
                self.clear_errors()
                with ui_storage_logger():
                    old_format = device.format
                    new_format = getFormat(fs_type,
                                           mountpoint=mountpoint, label=label,
                                           device=device.path)
                    try:
                        self.__storage.formatDevice(device, new_format)
                    except StorageError as e:
                        log.error("failed to register device format action: %s" % e)
                        device.format = old_format
                        self._error = e
                        self.set_warning(_("Device reformat request failed. "
                                           "Click for details."))
                        self.window.show_all()
                    else:
                        # first, remove this selector from any old install page(s)
                        new_selector = None
                        for page in self._accordion.allPages:
                            for _selector in getattr(page, "_members", []):
                                if _selector._device in (device, old_device):
                                    if page.pageTitle == self.translated_new_install_name:
                                        new_selector = _selector
                                        continue

                                    page.removeSelector(_selector)
                                    if not page._members:
                                        log.debug("removing empty page %s" % page.pageTitle)
                                        self._accordion.removePage(page.pageTitle)

                        # either update the existing selector or add a new one
                        if new_selector:
                            new_selector.props.mountpoint = mountpoint or ""
                            new_selector.props.name = (self._mountpointName(mountpoint)
                                                       or device.format.name)
                            new_selector._device = device
                        else:
                            self.add_new_selector(device)

                self._populate_right_side(selector)
                return

        ##
        ## FORMATTING ATTRIBUTES
        ##
        # Set various attributes that do not require actions.
        if old_label != label and hasattr(device.format, "label") and \
           not device.format.exists:
            log.debug("updating label to %s" % label)
            device.format.label = label

        if mountpoint and old_mountpoint != mountpoint:
            log.debug("updating mountpoint to %s" % mountpoint)
            device.format.mountpoint = mountpoint
            if old_mountpoint:
                selector.props.mountpoint = mountpoint
                selector.props.name = (self._mountpointName(mountpoint)
                                       or selector._device.format.name)
            else:
                # add an entry to the new page but do not remove any entries
                # from other pages since we haven't altered the filesystem
                self.add_new_selector(device)

    def _get_raid_widget_dict(self, device_type):
        """ Return dict of widget tuples with feature keys for device_type. """
        if device_type == DEVICE_TYPE_MD:
            prefix = "raid"
        elif device_type == DEVICE_TYPE_BTRFS:
            prefix = "btrfs"
        elif device_type == DEVICE_TYPE_LVM:
            prefix = "lvm"
        else:
            return {}

        widget_dict = {}
        for feature in raid_features:
            button = self.builder.get_object("%s%sCheckbox" % (prefix, feature))
            label = self.builder.get_object("%s%sLabel" % (prefix, feature))
            if button and label:
                widget_dict[feature] = (button, label)

        return widget_dict

    def _get_raid_level(self):
        """ Return the raid level string based on the current ui selections. """
        device_type = self._get_current_device_type()
        widget_dict = self._get_raid_widget_dict(device_type)
        if not widget_dict:
            return None

        active = []
        for feature in raid_features:
            if feature not in widget_dict:
                continue

            (button, label) = widget_dict[feature]
            if button.get_active():
                active.append(feature)

        raid_level = None
        for (level, feature_set) in raid_level_features.items():
            if set(active) == set(feature_set):
                raid_level = level
                break

        if raid_level is None:
            # this is okay for lvm or btrfs but not for md until we add linear
            log.error("UI: failed to get raid level (%s)" % active)

        return raid_level

    def on_raid_feature_toggled(self, widget):
        new_state = widget.get_active()
        log.debug("widget %s new state: %s" % (widget, new_state))

        raid_level = self._get_raid_level()

        # now that we've established a raid level, update disabled features
        self._update_disabled_raid_features(raid_level)

    def _get_raid_disabled_features(self, raid_level):
        """ Return a list of disabled features based on raid level. """
        disabled = raid_disabled_features.get(raid_level, [])
        disk_count = len(self._device_disks)
        # go through each feature's reference raid level, filtering any that
        # require more disks than we have available
        for feature in raid_features:
            # XXX we're using the mdraid rules for min members
            level = mdraid.raidLevel(feature_raid_levels[feature])
            min_disks = mdraid.get_raid_min_members(level)
            if min_disks > disk_count and feature not in disabled:
                disabled.append(feature)

        return disabled

    def _update_disabled_raid_features(self, raid_level):
        """ Update disabled feature widgets based on raid level. """
        device_type = self._get_current_device_type()
        widget_dict = self._get_raid_widget_dict(device_type)
        disabled = self._get_raid_disabled_features(raid_level)
        for feature in raid_features:
            if feature not in widget_dict:
                continue

            (button, label) = widget_dict[feature]
            button.set_sensitive(feature not in disabled)

    def _populate_raid(self, raid_level, size):
        """ Set up the raid-specific portion of the device details. """
        device_type = self._get_current_device_type()
        log.debug("populate_raid: %s, %s" % (device_type, raid_level))

        if device_type == DEVICE_TYPE_MD:
            base_level = "raid0"    # FIXME: should be linear

            level_label = self.builder.get_object("raidLevelLabel")
            level_label.set_text(raid_level.upper())
        elif device_type == DEVICE_TYPE_BTRFS:
            base_level = "single"
        else:
            return

        # Create a DeviceFactory to use to calculate the disk space needs for
        # this device with various raid features enabled.
        with ui_storage_logger():
            factory = self.__storage.getDeviceFactory(device_type, size,
                                                      disks=self._device_disks,
                                                      raid_level=base_level)

        widget_dict = self._get_raid_widget_dict(device_type)
        try:
            base_size = factory.device_size
        except MDRaidError as e:
            log.error("failed to populate UI raid options: %s" % e)
            self._error = e
            self.set_warning(str(e))
            self.window.show_all()
            return

        active = raid_level_features[raid_level]
        disabled = self._get_raid_disabled_features(raid_level)
        for feature in raid_features:
            if feature not in widget_dict:
                # this feature isn't supported for this device type
                continue

            (button, label) = widget_dict[feature]

            # is this feature enabled for the current raid level?
            button.set_active(feature in active)

            # what is the incremental disk space requirement for this feature?
            # TODO: update this when the size spinner changes
            level = mdraid.raidLevel(feature_raid_levels[feature])
            min_disks = mdraid.get_raid_min_members(level)
            if min_disks <= len(factory.disks):
                factory.raid_level = feature_raid_levels[feature]
                delta = factory.device_size - base_size
                label.set_text("+%s" % str(Size(spec="%fmb" % delta)).upper())
            else:
                label.set_text("(not enough disks)")

            # some features are not available to some raid levels
            button.set_sensitive(feature not in disabled)

    def _get_current_device_type(self):
        typeCombo = self.builder.get_object("deviceTypeCombo")
        device_type_text = typeCombo.get_active_text()
        log.info("getting device type for %s" % device_type_text)
        device_type = None
        if device_type_text == _(DEVICE_TEXT_LVM):
            device_type = DEVICE_TYPE_LVM
        elif device_type_text == _(DEVICE_TEXT_MD):
            device_type = DEVICE_TYPE_MD
        elif device_type_text == _(DEVICE_TEXT_PARTITION):
            device_type = DEVICE_TYPE_PARTITION
        elif device_type_text == _(DEVICE_TEXT_BTRFS):
            device_type = DEVICE_TYPE_BTRFS
        elif device_type_text == _(DEVICE_TEXT_DISK):
            device_type = DEVICE_TYPE_DISK
        else:
            log.error("unknown device type: '%s'" % device_type_text)

        return device_type

    def _populate_right_side(self, selector):
        log.debug("populate_right_side: %s" % selector._device)
        encryptCheckbox = self.builder.get_object("encryptCheckbox")
        labelEntry = self.builder.get_object("labelEntry")
        mountPointEntry = self.builder.get_object("mountPointEntry")
        nameEntry = self.builder.get_object("nameEntry")
        selectedDeviceLabel = self.builder.get_object("selectedDeviceLabel")
        selectedDeviceDescLabel = self.builder.get_object("selectedDeviceDescLabel")
        sizeSpinner = self.builder.get_object("sizeSpinner")
        typeCombo = self.builder.get_object("deviceTypeCombo")
        fsCombo = self.builder.get_object("fileSystemTypeCombo")

        device = selector._device
        if device.type == "luks/dm-crypt":
            use_dev = device.slave
        else:
            use_dev = device

        if hasattr(use_dev, "req_disks") and not use_dev.exists:
            self._device_disks = use_dev.req_disks[:]
        else:
            self._device_disks = device.disks[:]

        log.debug("updated device_disks to %s" % [d.name for d in self._device_disks])

        if hasattr(use_dev, "vg"):
            self._device_container_name = use_dev.vg.name
        else:
            self._device_container_name = None

        log.debug("updated device_vg_name to %s" % self._device_container_name)

        selectedDeviceLabel.set_text(selector.props.name)
        selectedDeviceDescLabel.set_text(self._description(selector.props.name))

        device_name = getattr(use_dev, "lvname", use_dev.name)
        nameEntry.set_text(device_name)

        mountPointEntry.set_text(getattr(device.format, "mountpoint", "") or "")
        mountPointEntry.set_sensitive(hasattr(device.format, "mountpoint"))

        labelEntry.set_text(getattr(device.format, "label", "") or "")
        # We could label existing formats that have a labelFsProg if we added an
        # ActionLabelFormat class.
        can_label = (hasattr(device.format, "label") and
                     not device.format.exists)
        labelEntry.set_sensitive(can_label)

        if hasattr(device.format, "label"):
            labelEntry.props.has_tooltip = False
        else:
            labelEntry.set_tooltip_text(_("This file system does not support labels."))

        if device.exists:
            min_size = device.minSize
            max_size = device.maxSize
        else:
            min_size = max(device.format.minSize, 1.0)
            max_size = device.size + float(self._free_space.convertTo(spec="mb")) # FIXME

        log.debug("min: %s  max: %s  current: %s" % (min_size, max_size, device.size))
        sizeSpinner.set_range(min_size,
                              max_size)
        sizeSpinner.set_value(device.size)
        sizeSpinner.set_sensitive(device.resizable or not device.exists)

        if sizeSpinner.get_sensitive():
            sizeSpinner.props.has_tooltip = False
        else:
            sizeSpinner.set_tooltip_text(_("This file system may not be resized."))

        self._reformatCheckbox.set_active(not device.format.exists)
        self._reformatCheckbox.set_sensitive(not device.protected and
                                             use_dev.exists and
                                             not use_dev.type.startswith("btrfs"))

        encryptCheckbox.set_active(device.encrypted)
        encryptCheckbox.set_sensitive(self._reformatCheckbox.get_active())
        ancestors = use_dev.ancestors
        ancestors.remove(use_dev)
        if any([a.format.type == "luks" and a.format.exists for a in ancestors]):
            # The encryption checkbutton should not be sensitive if there is
            # existing encryption below the leaf layer.
            encryptCheckbox.set_sensitive(False)

        ##
        ## Set up the filesystem type combo.
        ##

        # remove any fs types that aren't supported
        remove_indices = []
        for idx, data in enumerate(fsCombo.get_model()):
            fs_type = data[0]
            if fs_type not in self._fs_types:
                remove_indices.insert(0, idx)
                continue

            if fs_type == device.format.name:
                fsCombo.set_active(idx)

        for remove_idx in remove_indices:
            fsCombo.remove(remove_idx)

        # if the current device has unsupported formatting, add an entry for it
        if device.format.name not in self._fs_types:
            fsCombo.append_text(device.format.name)
            fsCombo.set_active(len(fsCombo.get_model()) - 1)

        # Give them a way to reset to original formatting. Whenever we add a
        # "reformat this" widget this will need revisiting.
        if device.exists and \
           device.format.type != device.originalFormat.type and \
           device.originalFormat.type not in self._fs_types:
            fsCombo.append_text(device.originalFormat.name)

        fsCombo.set_sensitive(self._reformatCheckbox.get_active())

        ##
        ## Set up the device type combo.
        ##

        btrfs_pos = None
        btrfs_included = False
        md_pos = None
        md_included = False
        disk_pos = None
        disk_included = False
        for idx, itr in enumerate(typeCombo.get_model()):
            if itr[0] == _(DEVICE_TEXT_BTRFS):
                btrfs_pos = idx
                btrfs_included = True
            elif itr[0] == _(DEVICE_TEXT_MD):
                md_pos = idx
                md_included = True
            elif itr[0] == _(DEVICE_TEXT_DISK):
                disk_pos = idx
                disk_included = True

        remove_indices = []

        # only include md if there are two or more disks
        include_md = (use_dev.type == "mdarray" or
                      len(self._clearpartDevices) > 1)
        if include_md and not md_included:
            typeCombo.append_text(_(DEVICE_TEXT_MD))
        elif md_included and not include_md:
            remove_indices.append(md_pos)

        # if the format is swap the device type can't be btrfs
        include_btrfs = (use_dev.format.type not in
                            partition_only_format_types + ["swap"])
        if include_btrfs and not btrfs_included:
            typeCombo.append_text(_(DEVICE_TEXT_BTRFS))
        elif btrfs_included and not include_btrfs:
            remove_indices.append(btrfs_pos)

        # only include disk if the current device is a disk
        include_disk = use_dev.isDisk
        if include_disk and not disk_included:
            typeCombo.append_text(_(DEVICE_TEXT_DISK))
        elif disk_included and not include_disk:
            remove_indices.append(disk_pos)

        remove_indices.sort(reverse=True)
        map(typeCombo.remove, remove_indices)

        md_pos = None
        btrfs_pos = None
        partition_pos = None
        lvm_pos = None
        for idx, itr in enumerate(typeCombo.get_model()):
            if itr[0] == _(DEVICE_TEXT_BTRFS):
                btrfs_pos = idx
            elif itr[0] == _(DEVICE_TEXT_MD):
                md_pos = idx
            elif itr[0] == _(DEVICE_TEXT_PARTITION):
                partition_pos = idx
            elif itr[0] == _(DEVICE_TEXT_LVM):
                lvm_pos = idx
            elif itr[0] == _(DEVICE_TEXT_DISK):
                disk_pos = idx

        device_type = getDeviceType(device)
        raid_level = getRAIDLevel(device)
        type_index_map = {DEVICE_TYPE_PARTITION: partition_pos,
                          DEVICE_TYPE_BTRFS: btrfs_pos,
                          DEVICE_TYPE_LVM: lvm_pos,
                          DEVICE_TYPE_MD: md_pos,
                          DEVICE_TYPE_DISK: disk_pos}

        for _type in self._device_name_dict.iterkeys():
            if _type == device_type:
                self._device_name_dict[_type] = device_name
                continue
            elif _type not in (DEVICE_TYPE_LVM, DEVICE_TYPE_MD):
                continue

            swap = (device.format.type == "swap")
            mountpoint = getattr(device.format, "mountpoint", None)

            with ui_storage_logger():
                name = self.__storage.suggestDeviceName(swap=swap,
                                                        mountpoint=mountpoint)

            self._device_name_dict[_type] = name

        typeCombo.set_active(type_index_map[device_type])

        # you can't change the type of an existing device
        typeCombo.set_sensitive(not use_dev.exists)

        self._populate_raid(raid_level, device.size)
        self._populate_lvm(device=use_dev)
        self.builder.get_object("optionsNotebook").set_sensitive(not device.exists)
        # do this last in case this was set sensitive in on_device_type_changed
        if use_dev.exists:
            nameEntry.set_sensitive(False)

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

        new_luks = any([d for d in self.__storage.devices
                            if d.format.type == "luks" and
                               not d.format.exists])
        if new_luks:
            dialog = PassphraseDialog(self.data)
            with enlightbox(self.window, dialog.window):
                rc = dialog.run()

            if rc == 0:
                # Cancel. Leave the old passphrase set if there was one.
                return

            self.passphrase = dialog.passphrase

        NormalSpoke.on_back_clicked(self, button)

    def on_add_clicked(self, button):
        self._save_right_side(self._current_selector)

        dialog = AddDialog(self.data,
                           mountpoints=self.__storage.mountpoints.keys())
        dialog.refresh()
        rc = dialog.run()

        if rc != 1:
            # user cancel
            dialog.window.destroy()
            return

        # create a device of the default type, using any disks, with an
        # appropriate fstype and mountpoint
        mountpoint = dialog.mountpoint
        log.debug("requested size = %s  ; available space = %s"
                    % (dialog.size, self._free_space))

        # if no size was entered, request as much of the free space as possible
        if dialog.size.convertTo(spec="mb") < 1:
            size = self._free_space
        else:
            size = dialog.size

        fstype = self.storage.getFSType(mountpoint)
        encrypted = self.data.autopart.encrypted

        # we're doing nothing here to ensure that bootable requests end up on
        # the boot disk, but the weight from platform should take care of this

        if mountpoint.lower() in ("swap", "biosboot", "prepboot"):
            mountpoint = None

        device_type_from_autopart = {AUTOPART_TYPE_LVM: DEVICE_TYPE_LVM,
                                     AUTOPART_TYPE_PLAIN: DEVICE_TYPE_PARTITION,
                                     AUTOPART_TYPE_BTRFS: DEVICE_TYPE_BTRFS}
        device_type = device_type_from_autopart[self.data.autopart.type]
        if (device_type != DEVICE_TYPE_PARTITION and
            ((mountpoint and mountpoint.startswith("/boot")) or
             fstype in partition_only_format_types)):
            device_type = DEVICE_TYPE_PARTITION

        # some devices should never be encrypted
        if ((mountpoint and mountpoint.startswith("/boot")) or
            fstype in partition_only_format_types):
            encrypted = False

        disks = self._clearpartDevices
        size = float(size.convertTo(spec="mb"))
        self.clear_errors()

        with ui_storage_logger():
            factory = self.__storage.getDeviceFactory(device_type, size)
            container = self.__storage.getContainer(factory)

            if container:
                # don't override user-initiated changes to a defined container
                if factory.encrypt_members:
                    encrypted = container.encrypted

                disks = container.disks

            try:
                self.__storage.newDevice(device_type,
                                         size=size,
                                         fstype=fstype,
                                         mountpoint=mountpoint,
                                         encrypted=encrypted,
                                         disks=disks)
            except ErrorRecoveryFailure as e:
                log.error("error recovery failure")
                self._error = e
                self.set_error(_(unrecoverable_error_msg))
                self.window.show_all()
                self._reset_storage()
            except StorageError as e:
                log.error("newDevice failed: %s" % e)
                log.debug("trying to find an existing container to use")
                container = self.__storage.getContainer(factory, existing=True)
                log.debug("found container %s" % container)
                if container:
                    try:
                        self.__storage.newDevice(device_type,
                                                 size=size,
                                                 fstype=fstype,
                                                 mountpoint=mountpoint,
                                                 encrypted=encrypted,
                                                 disks=disks,
                                                 container_name=container.name)
                    except StorageError as e2:
                        log.error("newDevice failed w/ old container: %s" % e2)
                    else:
                        type_str = device_text_map[device_type]
                        self.set_info(_("Added new %s to existing "
                                        "container %s.")
                                      % (type_str, container.name))
                        self.window.show_all()
                        e = None

                if e:
                    self._error = e
                    self.set_error(_("Failed to add new device. Click for "
                                     "details."))
                    self.window.show_all()
            except OverflowError as e:
                 log.error("invalid size set for partition")
                 self._error = e
                 self.set_error(_("Invalid partition size set. Use a "
                                  "valid integer."))
                 self.window.show_all()

        self._devices = self.__storage.devices
        self._do_refresh()
        self._updateSpaceDisplay()

    def _destroy_device(self, device):
        self.clear_errors()
        with ui_storage_logger():
            is_logical_partition = getattr(device, "isLogical", False)
            try:
                if device.isDisk:
                    self.__storage.initializeDisk(device)
                else:
                    self.__storage.destroyDevice(device)
            except StorageError as e:
                log.error("failed to schedule device removal: %s" % e)
                self._error = e
                self.set_warning(_("Device removal request failed. Click "
                                   "for details."))
                self.window.show_all()
            else:
                if is_logical_partition:
                    self.__storage.removeEmptyExtendedPartitions()

        # If we've just removed the last partition and the disklabel is pre-
        # existing, reinitialize the disk.
        if device.type == "partition" and device.exists and \
           device.disk.format.exists:
            with ui_storage_logger():
                if self.__storage.shouldClear(device.disk):
                    self.__storage.initializeDisk(device.disk)

        self._devices = self.__storage.devices

        # should this be in DeviceTree._removeDevice?
        container = None
        if hasattr(device, "vg"):
            container = device.vg
            device_type = DEVICE_TYPE_LVM
            raid_level = None
        elif hasattr(device, "volume"):
            container = device.volume
            device_type = DEVICE_TYPE_BTRFS
            raid_level = container.dataLevel

        if container and not container.exists and \
           self.__storage.devicetree.getChildren(container):
            # adjust container to size of remaining devices
            with ui_storage_logger():
                factory = self.__storage.getDeviceFactory(device_type, 0,
                                                          disks=container.disks,
                                                          encrypted=container.encrypted,
                                                          raid_level=raid_level)
                parents = self.__storage.setContainerMembers(container, factory)

        # if this device has parents with no other children, remove them too
        for parent in device.parents:
            if parent.kids == 0 and not parent.isDisk:
                self._destroy_device(parent)

    def _show_first_mountpoint(self, page=None):
        if not self._initialized:
            return

        # Make sure there's something displayed on the RHS.  Just default to
        # the first mountpoint in the page.
        if not page:
            page = self._accordion.currentPage()

        log.debug("show first mountpoint: %s" % getattr(page, "pageTitle", None))
        if getattr(page, "_members", []):
            self.on_selector_clicked(page._members[0])
        else:
            self._current_selector = None

    def on_remove_clicked(self, button):
        # Nothing displayed on the RHS?  Nothing to remove.
        if not self._current_selector:
            return

        page = self._accordion.currentPage()
        selector = self._current_selector
        device = self._current_selector._device
        root_name = None
        if selector._root:
            root_name = selector._root.name
        elif page:
            root_name = page.pageTitle

        log.debug("removing device '%s' from page %s" % (device, root_name))

        if root_name == self.translated_new_install_name:
            if device.exists:
                # This is an existing device that was added to the new page.
                # All we want to do is revert any changes to the device and
                # it will end up back in whatever old pages it came from.
                with ui_storage_logger():
                    self.__storage.resetDevice(device)

                log.debug("updated device: %s" % device)
            else:
                # Destroying a non-existing device doesn't require any
                # confirmation.
                self._destroy_device(device)
        else:
            # This is a device that exists on disk and most likely has data
            # on it.  Thus, we first need to confirm with the user and then
            # schedule actions to delete the thing.
            dialog = ConfirmDeleteDialog(self.data)
            with enlightbox(self.window, dialog.window):
                dialog.refresh(getattr(device.format, "mountpoint", ""),
                               device.name, root_name)
                rc = dialog.run()

                if rc == 0:
                    dialog.window.destroy()
                    return

            if dialog.deleteAll:
                for dev in [s._device for s in page._members]:
                    self._destroy_device(dev)
            else:
                self._destroy_device(device)

        log.info("ui: removed device %s" % device.name)

        # Now that devices have been removed from the installation root,
        # refreshing the display will have the effect of making them disappear.
        # It's like they never existed.
        self._unused_devices = None     # why do we cache this?
        self._updateSpaceDisplay()
        self._do_refresh()

    def on_summary_clicked(self, button):
        dialog = SelectedDisksDialog(self.data)

        with enlightbox(self.window, dialog.window):
            dialog.refresh(self._clearpartDevices, self._currentFreeInfo,
                           showRemove=False, setBoot=False)
            dialog.run()

    def on_help_clicked(self, button):
        help_window = HelpDialog(self.data)
        help_window.run()

    def on_configure_clicked(self, button):
        selector = self._current_selector
        if not selector:
            return

        device = selector._device
        if device.exists:
            return

        if self._get_current_device_type() == DEVICE_TYPE_LVM:
            # LVM disk set management happens through VG edit on RHS
            return

        self.clear_errors()

        dialog = DisksDialog(self.data,
                             disks=self._clearpartDevices,
                             free=self._currentFreeInfo,
                             selected=self._device_disks)
        with enlightbox(self.window, dialog.window):
            rc = dialog.run()

        if rc == 0:
            return

        disks = dialog.selected
        log.debug("new disks for %s: %s" % (device.name,
                                            [d.name for d in disks]))
        if not disks:
            self._error = "No disks selected. Keeping previous disk set."
            self.set_info(self._error)
            self.window.show_all()
            return

        self._device_disks = disks
        self._populate_raid(self._get_raid_level(),
                            self.builder.get_object("sizeSpinner").get_value())

    def run_vg_editor(self, vg=None, name=None):
        if vg:
            vg_name = vg.name
        elif name:
            vg_name = name

        dialog = VolumeGroupDialog(self.data,
                                   name=vg_name,
                                   disks=self._clearpartDevices,
                                   free=self._currentFreeInfo,
                                   selected=self._device_disks)

        with enlightbox(self.window, dialog.window):
            rc = dialog.run()

        if rc == 0:
            return

        disks = dialog.selected
        name = dialog.name
        log.debug("new disks for %s: %s" % (name, [d.name for d in disks]))
        if not disks:
            self._error = "No disks selected. Not saving changes."
            self.set_info(self._error)
            self.window.show_all()
            return

        log.debug("new VG name: %s" % name)
        if name != vg_name and name in self.__storage.names:
            self._error = _("Volume Group name %s is already in use. Not "
                            "saving changes.") % name
            self.set_info(self._error)
            self.window.show_all()
            return

        self._device_disks = disks
        self._device_container_name = name

    def on_modify_vg_clicked(self, button):
        vg_name = self.builder.get_object("volumeGroupCombo").get_active_text()

        vg = self.__storage.devicetree.getDeviceByName(vg_name)

        # pass the name along with any found vg since we could be modifying a
        # vg that hasn't been instantiated yet
        self.run_vg_editor(vg=vg, name=vg_name)

        log.debug("%s -> %s" % (vg_name, self._device_container_name))
        if vg_name == self._device_container_name:
            return

        log.debug("renaming VG %s to %s" % (vg_name, self._device_container_name))
        if vg:
            self.__storage.devicetree.names.remove(vg.name)
            self.__storage.devicetree.names.append(self._device_container_name)
            vg.name = self._device_container_name

        vg_combo = self.builder.get_object("volumeGroupCombo")
        for idx, data in enumerate(vg_combo.get_model()):
            # we're looking for the original vg name
            if data[0] == vg_name:
                vg_combo.remove(idx)
                vg_combo.insert_text(idx, self._device_container_name)
                vg_combo.set_active(idx)
                break

    def on_vg_changed(self, combo):
        vg_name = combo.get_active_text()
        log.debug("new vg selection: %s" % vg_name)
        if vg_name is None:
            return

        if vg_name == new_vg_text:
            # run the vg editor dialog with a default name and disk set
            hostname = self.data.network.hostname
            name = self.__storage.suggestContainerName(hostname=hostname)
            self.run_vg_editor(name=name)
            for idx, data in enumerate(combo.get_model()):
                if data[0] == new_vg_text:
                    combo.insert_text(idx, self._device_container_name)
                    combo.set_active(idx)
                    break
        else:
            self._device_container_name = vg_name

        vg = self.__storage.devicetree.getDeviceByName(self._device_container_name)
        vg_exists = getattr(vg, "exists", False)    # might not be in the tree
        self.builder.get_object("modifyVGButton").set_sensitive(not vg_exists)

    def on_selector_clicked(self, selector):
        if not self._initialized:
            return

        # Take care of the previously chosen selector.
        if self._current_selector and self._initialized:
            log.debug("current selector: %s" % self._current_selector._device)
            log.debug("new selector: %s" % selector._device)
            nb_page = self._partitionsNotebook.get_current_page()
            log.debug("notebook page = %s" % nb_page)
            if nb_page == NOTEBOOK_DETAILS_PAGE:
                self._save_right_side(self._current_selector)

            self._current_selector.set_chosen(False)

        no_edit = False
        if selector._device.format.type == "luks" and \
           selector._device.format.exists:
            self._partitionsNotebook.set_current_page(NOTEBOOK_LUKS_PAGE)
            selectedDeviceLabel = self.builder.get_object("encryptedDeviceLabel")
            selectedDeviceDescLabel = self.builder.get_object("encryptedDeviceDescriptionLabel")
            no_edit = True
        elif not getattr(selector._device, "complete", True):
            self._partitionsNotebook.set_current_page(NOTEBOOK_INCOMPLETE_PAGE)
            selectedDeviceLabel = self.builder.get_object("incompleteDeviceLabel")
            selectedDeviceDescLabel = self.builder.get_object("incompleteDeviceDescriptionLabel")
            optionsLabel = self.builder.get_object("incompleteDeviceOptionsLabel")

            if selector._device.type == "mdarray":
                total = selector._device.memberDevices
                missing = total - len(selector._device.parents)
                txt = _("This Software RAID array is missing %d of %d member "
                        "partitions. You can remove it or select a different "
                        "device.") % (missing, total)
            else:
                total = selector._device.pvCount
                missing = total - len(selector._device.parents)
                txt = _("This LVM Volume Group is missing %d of %d physical "
                        "volumes. You can remove it or select a different "
                        "device.") % (missing, total)
            optionsLabel.set_text(txt)
            no_edit = True
        elif getDeviceType(selector._device) is None:
            self._partitionsNotebook.set_current_page(NOTEBOOK_UNEDITABLE_PAGE)
            selectedDeviceLabel = self.builder.get_object("uneditableDeviceLabel")
            selectedDeviceDescLabel = self.builder.get_object("uneditableDeviceDescriptionLabel")
            no_edit = True

        if no_edit:
            selectedDeviceLabel.set_text(selector._device.name)
            selectedDeviceDescLabel.set_text(self._description(selector._device.type))
            selector.set_chosen(True)
            self._current_selector = selector
            self._configButton.set_sensitive(False)
            self._removeButton.set_sensitive(True)
            return

        # Make sure we're showing details instead of the "here's how you create
        # a new OS" label.
        self._partitionsNotebook.set_current_page(NOTEBOOK_DETAILS_PAGE)

        # Set up the newly chosen selector.
        self._populate_right_side(selector)
        selector.set_chosen(True)
        self._current_selector = selector

        self._configButton.set_sensitive(not selector._device.protected and
                                         getDeviceType(selector._device) != DEVICE_TYPE_LVM)
        self._removeButton.set_sensitive(not selector._device.protected)
        return True

    def on_page_clicked(self, page):
        if not self._initialized:
            return

        log.debug("page clicked: %s" % getattr(page, "pageTitle", None))
        if self._current_selector:
            nb_page = self._partitionsNotebook.get_current_page()
            log.debug("notebook page = %s" % nb_page)
            if nb_page == NOTEBOOK_DETAILS_PAGE:
                self._save_right_side(self._current_selector)

            self._current_selector.set_chosen(False)
            self._current_selector = None

        self._show_first_mountpoint(page=page)

        # This is called when a Page header is clicked upon so we can support
        # deleting an entire installation at once and displaying something
        # on the RHS.
        if isinstance(page, CreateNewPage):
            # Make sure we're showing "here's how you create a new OS" label
            # instead of device/mountpoint details.
            self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
            self._removeButton.set_sensitive(False)
        else:
            self._removeButton.set_sensitive(True)

    def _do_autopart(self):
        # There are never any non-existent devices around when this runs.
        log.debug("running automatic partitioning")
        self.__storage.doAutoPart = True
        self.clear_errors()
        with ui_storage_logger():
            try:
                doAutoPartition(self.__storage, self.data)
            except NoDisksError as e:
                # No handling should be required for this.
                log.error("doAutoPartition failed: %s" % e)
                self._error = e
                self.set_error(_("No disks selected."))
                self.window.show_all()
            except NotEnoughFreeSpaceError as e:
                # No handling should be required for this.
                log.error("doAutoPartition failed: %s" % e)
                self._error = e
                self.set_error(_("Not enough free space on selected disks."))
                self.window.show_all()
            except StorageError as e:
                log.error("doAutoPartition failed: %s" % e)
                self._reset_storage()
                self._error = e
                self.set_error(_("Automatic partitioning failed. Click "
                                 "for details."))
                self.window.show_all()
            else:
                self._devices = self.__storage.devices
            finally:
                self.__storage.doAutoPart = False
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

    def on_reformat_toggled(self, widget):
        active = widget.get_active()

        encryption_checkbutton = self.builder.get_object("encryptCheckbox")
        encryption_checkbutton.set_sensitive(active)
        if self._current_selector:
            device = self._current_selector._device
            if device.type == "luks/dm-crypt":
                device = device.slave

            ancestors = device.ancestors
            ancestors.remove(device)
            if any([a.format.type == "luks" and a.format.exists for a in ancestors]):
                # The encryption checkbutton should not be sensitive if there is
                # existing encryption below the leaf layer.
                encryption_checkbutton.set_sensitive(False)

        fs_combo = self.builder.get_object("fileSystemTypeCombo")
        fs_combo.set_sensitive(active)

        # The label entry can only be sensitive if reformat is active and the
        # currently selected filesystem can be labeled.
        label_active = active
        if active:
            fmt = getFormat(fs_combo.get_active_text())
            label_active = active and hasattr(fmt, "label")

        label_entry = self.builder.get_object("labelEntry")
        label_entry.set_sensitive(label_active)

    def on_fs_type_changed(self, combo):
        if not self._initialized:
            return

        new_type = combo.get_active_text()
        if new_type is None:
            return
        log.debug("fs type changed: %s" % new_type)
        fmt = getFormat(new_type)
        mountPointEntry = self.builder.get_object("mountPointEntry")
        labelEntry = self.builder.get_object("labelEntry")
        # FIXME: can't set a label on an existing format as of now
        labelEntry.set_sensitive(self._reformatCheckbox.get_active() and
                                 hasattr(fmt, "label"))
        mountPointEntry.set_sensitive(fmt.mountable)

    def _populate_lvm(self, device=None):
        """ Set up the vg widgets for lvm or hide them for other types. """
        device_type = self._get_current_device_type()
        if device is None:
            if self._current_selector is None:
                return

            device = self._current_selector._device

        vg_combo = self.builder.get_object("volumeGroupCombo")
        vg_button = self.builder.get_object("modifyVGButton")
        vg_label = self.builder.get_object("volumeGroupLabel")
        if device_type == DEVICE_TYPE_LVM:
            # set up the vg widgets and then bail out
            if self._device_container_name:
                default_vg = self._device_container_name
            else:
                with ui_storage_logger():
                    factory = self.__storage.getDeviceFactory(DEVICE_TYPE_LVM,
                                                              0)
                    container = self.__storage.getContainer(factory)
                    default_vg = getattr(container, "name", None)

            log.debug("default vg is %s" % default_vg)
            vg_combo.remove_all()
            vgs = self.__storage.vgs
            for vg in vgs:
                vg_combo.append_text(vg.name)
                if default_vg and vg.name == default_vg:
                    vg_combo.set_active(vgs.index(vg))

            if default_vg is None:
                hostname = self.data.network.hostname
                default_vg = self.__storage.suggestContainerName(hostname=hostname)
                vg_combo.append_text(default_vg)
                vg_combo.set_active(len(vg_combo.get_model()) - 1)

            vg_combo.append_text(new_vg_text)
            if default_vg is None:
                vg_combo.set_active(len(vg_combo.get_model()) - 1)

            for widget in [vg_label, vg_combo, vg_button]:
                widget.set_no_show_all(False)
                widget.show()

            # make the combo and button insensitive for existing LVs
            can_change_vg = (device is not None and not device.exists)
            vg_combo.set_sensitive(can_change_vg)
        else:
            for widget in [vg_label, vg_combo, vg_button]:
                widget.set_no_show_all(True)
                widget.hide()

    def on_device_type_changed(self, combo):
        if not self._initialized:
            return

        new_type = self._get_current_device_type()
        log.debug("device_type_changed: %s %s" % (new_type,
                                                  combo.get_active_text()))
        if new_type is None:
            return

        # if device type is not btrfs we want to make sure btrfs is not in the
        # fstype combo
        include_btrfs = False
        fs_type_sensitive = True

        # eventually LVM will be handled in the else clause
        if new_type in (DEVICE_TYPE_PARTITION, DEVICE_TYPE_LVM, DEVICE_TYPE_DISK):
            self._optionsNotebook.hide()
        else:
            self._optionsNotebook.show()
            self._optionsNotebook.set_current_page(options_page_dict[new_type])

        raid_level = None
        if new_type == DEVICE_TYPE_BTRFS:
            # add btrfs to the fstype combo and lock it in
            test_fmt = getFormat("btrfs")
            include_btrfs = test_fmt.supported and test_fmt.formattable
            fs_type_sensitive = False
            with ui_storage_logger():
                factory = self.__storage.getDeviceFactory(DEVICE_TYPE_BTRFS, 0)
                container = self.__storage.getContainer(factory)

            if container:
                raid_level = container.dataLevel or "single"
            else:
                # here I suppose we could alter the default based on disk count
                raid_level = "single"
        elif new_type == DEVICE_TYPE_MD:
            raid_level = "raid0"

        # lvm uses the RHS to set disk set. no foolish minds here.
        self._configButton.set_sensitive(new_type != DEVICE_TYPE_LVM)

        size = self.builder.get_object("sizeSpinner").get_value()
        self._populate_raid(raid_level, size)
        self._populate_lvm()

        nameEntry = self.builder.get_object("nameEntry")
        nameEntry.set_sensitive(new_type in (DEVICE_TYPE_LVM, DEVICE_TYPE_MD))
        nameEntry.set_text(self._device_name_dict[new_type])

        # begin btrfs magic
        fsCombo = self.builder.get_object("fileSystemTypeCombo")
        model = fsCombo.get_model()
        btrfs_included = False
        btrfs_pos = None
        for idx, data in enumerate(model):
            if data[0] == "btrfs":
                btrfs_included = True
                btrfs_pos = idx

        active_index = fsCombo.get_active()
        fstype = fsCombo.get_active_text()
        if btrfs_included and not include_btrfs:
            for i in range(0, len(model)):
                if fstype == "btrfs" and \
                   model[i][0] == self.storage.defaultFSType:
                    active_index = i
                    break
            fsCombo.remove(btrfs_pos)
        elif include_btrfs and not btrfs_included:
            fsCombo.append_text("btrfs")
            active_index = len(fsCombo.get_model()) - 1

        fsCombo.set_active(active_index)
        fsCombo.set_sensitive(self._reformatCheckbox.get_active() and
                              fs_type_sensitive)
        # end btrfs magic

    def clear_errors(self):
        self._error = None
        self.clear_info()

    def on_info_bar_clicked(self, *args):
        log.debug("info bar clicked: %s (%s)" % (self._error, args))
        if not self._error:
            return

        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.CLOSE,
                                message_format=str(self._error))
        dlg.set_decorated(False)

        with enlightbox(self.window, dlg):
            dlg.run()
            dlg.destroy()

    def on_apply_clicked(self, button):
        """ call _save_right_side, then, perhaps, populate_right_side. """
        self._save_right_side(self._current_selector)

    def on_unlock_clicked(self, button):
        """ try to open the luks device, populate, then call _do_refresh. """
        self.clear_errors()
        device = self._current_selector._device
        log.info("trying to unlock %s..." % device.name)
        entry = self.builder.get_object("passphraseEntry")
        passphrase = entry.get_text()
        device.format.passphrase = passphrase
        try:
            device.setup()
            device.format.setup()
        except StorageError as e:
            log.error("failed to unlock %s: %s" % (device.name, e))
            device.teardown(recursive=True)
            self._error = e
            device.format.passphrase = None
            entry.set_text("")
            self.set_warning(_("Failed to unlock encrypted block device. "
                               "Click for details"))
            self.window.show_all()
            return

        log.info("unlocked %s, now going to populate devicetree..." % device.name)
        with ui_storage_logger():
            luks_dev = LUKSDevice(device.format.mapName,
                                  parents=[device],
                                  exists=True)
            self.__storage.devicetree._addDevice(luks_dev)
            # save the passphrase for possible reset and to try for other devs
            self.__storage.savePassphrase(device)
            # XXX What if the user has changed things using the shell?
            self.__storage.devicetree.populate()
            # look for new roots
            self.__storage.roots = findExistingInstallations(self.__storage.devicetree)

        self._devices = self.__storage.devices
        self._unused_devices = None     # why do we cache this?
        self._current_selector = None
        self._do_refresh()

help_text_template = N_("""You have chosen to manually set up the filesystems for your new %(productName)s installation. Before you begin, you might want to take a minute to learn the lay of the land. Quite a bit has changed.

The most important change is that creation of new filesystems has been streamlined. You no longer have to build complex devices like LVM logical volumes in stages (physical volume, then volume group, then logical volume) -- now you just create a logical volume and we'll handle the legwork of setting up the physical volumes and volume group to contain it. We'll also handle adjusting the volume group as you add, remove, and resize logical volumes so you don't have to worry about the mundane details.


Screen Layout

The left-hand side of the screen shows the OS installations we were able to find on this computer. The new %(productName)s installation is at the top of the list. You can click on the names of the installations to see what filesystems they contain.

Below the various installations and mountpoints on the left-hand side there are buttons to add a new filesystem, remove the selected filesystem, or configure the selected filesystem.

The right-hand side of the screen is where you can customize the currently-selected mountpoint.

On the bottom-left you will see a summary of the disks you have chosen to use for the installation. You can click on the blue text to see more detailed information about your selected disks.


How to create a new filesystem on a new device

1. Click on the + button.
2. Enter the mountpoint and size. (Hint: Hover the mouse pointer over either of the text entry areas for help.)
3. Select the new mountpoint under "New %(productName)s Installation" on the left-hand side of the screen and customize it to suit your needs.


How to reformat a device/filesystem that already exists on your disk

1. Select the filesystem from the left-hand side of the screen.
2. Click on the "Customize" expander in the mountpoint customization area on the right-hand side of the screen.
3. Activate the "Reformat" checkbutton, select a filesystem type and, if applicable, enter a mountpoint above in the "Mountpoint" text entry area.
4. Click on "Apply changes"


How to set a mountpoint for a filesystem that already exists on your disk

1. Select the filesystem from the left-hand side of the screen.
2. Enter a mountpoint in the "Mountpoint" text entry area in the mountpoint customization area.
3. Click on "Apply changes"


How to remove a filesystem that already exists on your disk

1. Select the filesystem you wish to remove on the left-hand side of the screen.
2. Click the - button.

Hint: Removing a device that already exists on your disk from the "New %(productName)s Installation" does not remove it from the disk. It only resets that device to its original state. To remove a device that already exists on your disk, you must select it from under any of the other detected installations (or "Unknown") and hit the - button.


Tips and hints

You can enter sizes for new filesystems that are greater than the total available free space. The installer will come as close as possible to the size you request.

By default, new devices use any/all of your selected disks.

You can change which disks a new device may be allocated from by clicking the configure button (the one with a tools graphic) while that device is selected.

When adding a new mountpoint by clicking the + button, leave the size entry blank to make the new device use all available free space.

When you remove the last device from a container device like an LVM volume group, we will automatically remove that container device to make room for new devices.

When the last partition is removed from a disk, that disk may be reinitialized with a new partition table if we think there is a more appropriate type for that disk.
""")
