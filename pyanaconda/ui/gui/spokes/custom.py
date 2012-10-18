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
# - Deleting an LV is not reflected in available space in the bottom left.
#   - this is only true for preexisting LVs
# - Device descriptions, suggested sizes, etc. should be moved out into a support file.
# - Tabbing behavior in the accordion is weird.
# - Update feature space costs when size spinner changes.
# - Either disable stripe/mirror for LVM or implement it for device creation.
# - If you click to add a mountpoint while editing a device the lightbox
#   screenshot is taken prior to the ui update so the background shows the old
#   size and free space while you're deciding on a size for the new device.

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
from pyanaconda.storage import findExistingInstallations
from pyanaconda.storage.partitioning import doPartitioning
from pyanaconda.storage.partitioning import doAutoPartition
from pyanaconda.storage.errors import StorageError
from pyanaconda.storage.errors import NoDisksError
from pyanaconda.storage.errors import NotEnoughFreeSpaceError
from pyanaconda.storage.errors import ErrorRecoveryFailure
from pyanaconda.storage.errors import CryptoError
from pyanaconda.storage.devicelibs import mdraid
from pyanaconda.storage.devices import LUKSDevice

from pyanaconda.ui.gui import GUIObject
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

new_install_name = _("New %s %s Installation") % (productName, productVersion)
unrecoverable_error_msg = _("Storage configuration reset due to unrecoverable "
                            "error. Click for details.")
device_configuration_error_msg = _("Device reconfiguration failed. Click for "
                                   "details.")

empty_mountpoint_msg = _("Please enter a valid mountpoint.")
invalid_mountpoint_msg = _("That mount point is invalid. Try something else?")
mountpoint_in_use_msg = _("That mount point is already in use. Try something else?")

MOUNTPOINT_OK = 0
MOUNTPOINT_INVALID = 1
MOUNTPOINT_IN_USE = 2
MOUNTPOINT_EMPTY = 3

mountpoint_validation_msgs = {MOUNTPOINT_OK: "",
                              MOUNTPOINT_INVALID: invalid_mountpoint_msg,
                              MOUNTPOINT_IN_USE: mountpoint_in_use_msg,
                              MOUNTPOINT_EMPTY: empty_mountpoint_msg}

DEVICE_TEXT_LVM = _("LVM")
DEVICE_TEXT_MD = _("RAID")
DEVICE_TEXT_PARTITION = _("Standard Partition")
DEVICE_TEXT_BTRFS = _("BTRFS")

# FIXME: use these everywhere instead of the AUTOPART_TYPE constants
DEVICE_TYPE_LVM = 0
DEVICE_TYPE_MD = 1
DEVICE_TYPE_PARTITION = 2
DEVICE_TYPE_BTRFS = 3

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
                          "raid4": ["Redundancy", "DistError", "RedundantError"],
                          "raid5": ["Redundancy", "Error", "RedundantError"],
                          "raid6": ["Redundancy", "Error", "DistError"]}

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
        self._warningLabel.set_text(mountpoint_validation_msgs[self._error])
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

    def on_delete_cancel_clicked(self, button, *args):
        self.window.destroy()

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
        self._fs_types = []             # list of supported fstypes
        self._unused_devices = None     # None indicates uninitialized
        self._free_space = Size(bytes=0)

        self._initialized = False

    def _propagate_actions(self, actions):
        """ Register actions from the UI with the main Storage instance. """
        for ui_action in actions:
            ui_device = ui_action.device
            if isinstance(ui_device, LUKSDevice) and ui_device.exists:
                # LUKS device that was unlocked during this spoke visit
                # The ids won't match in this case because we instantiated the
                # LUKSDevice both in the spoke's devicetree and in the main one.
                device = self.storage.devicetree.getDeviceByName(ui_device.name)
            else:
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
                if ui_device.format.type == "disklabel":
                    # A DiskLabel instance will have partitions already in it.
                    args.append(getFormat("disklabel",
                                          device=ui_device.path,
                                          labelType=ui_device.format.labelType))
                else:
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
        self.clear_errors()
        ui_devicetree = self.__storage.devicetree

        log.debug("converting custom spoke changes into actions")
        for action in ui_devicetree.findActions():
            log.debug("%s" % action)

        # Find any LUKS devices that have been unlocked in this visit to the
        # custom spoke and find their descendant devices before we do anything
        # else.
        ui_luks_devices = [d for d in self._devices
                                if isinstance(d, LUKSDevice) and
                                   d.exists and not
                                   self.storage.devicetree.getDeviceByID(d.id)]
        for ui_luks_device in ui_luks_devices:
            if ui_luks_device not in self._devices:
                # since removed
                continue

            ui_slave = ui_luks_device.slave
            slave = self.storage.devicetree.getDeviceByID(ui_slave.id)
            slave.format.passphrase = ui_slave.format._LUKS__passphrase
            luks_device = LUKSDevice(slave.format.mapName,
                                     parents=[slave],
                                     exists=True)
            luks_device.setup()
            self.storage.savePassphrase(slave)
            self.storage.devicetree._addDevice(luks_device)

        # XXX What if the user has changed storage config in the shell?
        if ui_luks_devices:
            self.storage.devicetree.populate()

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

        # catch changed size of partitions defined prior to this visit
        for ui_device in self.__storage.partitions:
            device = self.storage.devicetree.getDeviceByID(ui_device.id)
            if device and not device.exists and ui_device.size != device.size:
                device.req_base_size = ui_device.req_base_size
                device.req_size = ui_device.req_size

        if partition_creates or partition_destroys:
            try:
                doPartitioning(self.storage)
            except Exception as e:
                # TODO: error handling
                raise

        # catch changed size of non-partition devices defined prior to this
        # visit
        for ui_device in self.__storage.devices:
            if ui_device in self.__storage.partitions:
                # did partitions before doPartitioning
                continue

            device = self.storage.devicetree.getDeviceByID(ui_device.id)
            if device and not device.exists and ui_device.size != device.size:
                device._size = ui_device._size

        # register all other create actions
        already_handled = disklabel_creates + partition_creates
        actions = [a for a in ui_devicetree.findActions(type="create")
                        if a not in already_handled]
        self._propagate_actions(actions)

        # check for changes that do not use actions
        for ui_device in self.__storage.devices:
            device = self.storage.devicetree.getDeviceByID(ui_device.id)
            if not device:
                continue

            if device.format.mountable and \
               ui_device.format.mountpoint != device.format.mountpoint:
                device.format.mountpoint = ui_device.format.mountpoint

            # we can only label new formats as of now
            if hasattr(device.format, "label") and \
               not device.format.exists and \
               ui_device.format.label != device.format.label:
                device.format.label = ui_device.format.label

            # if this device was removed from the new installation it should be
            # completely reset to its initial state
            if ui_device.format == ui_device.originalFormat and \
               ui_device.size == ui_device.currentSize:
                self.storage.resetDevice(device)

        # apply global passphrase to all new encrypted devices
        self.data.autopart.passphrase = self.passphrase
        for device in self.storage.devices:
            if device.format.type == "luks" and not device.format.exists:
                log.debug("using global passphrase for %s" % device.name)
                device.format.passphrase = self.data.autopart.passphrase

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
        return [d for d in self._devices if d.name in self.data.clearpart.drives]

    @property
    def unusedDevices(self):
        if self._unused_devices is None:
            self._unused_devices = [d for d in self.__storage.unusedDevices
                                        if d.disks and not d.isDisk and
                                           d.isleaf]

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
        self.__storage.devicetree._actions = [] # keep things simple

        # hide removable disks containing install media
        for disk in self.__storage.disks:
            if disk.removable and disk.protected:
                self.__storage.devicetree.hide(disk)

        self._devices = self.__storage.devices
        self._unused_devices = None

    def refresh(self):
        self.clear_errors()
        NormalSpoke.refresh(self)

        # Make sure the storage spoke execute method has finished before we
        # copy the storage instance.
        t = threadMgr.get("AnaExecuteStorageThread")
        if t:
            t.join()

        self.passphrase = self.data.autopart.passphrase
        self._reset_storage()
        self._do_refresh()
        # update our free space number based on Storage
        self._setCurrentFreeSpace()

        self._updateSpaceDisplay()

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
            page.pageTitle = new_install_name
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

            new_root = Root(mounts=mounts, swaps=swaps, name=new_install_name)
            ui_roots.insert(0, new_root)

        # Add in all the existing (or autopart-created) operating systems.
        for root in ui_roots:
            # Don't make a page if none of the root's devices are left.
            # Also, only include devices in an old page if the format is intact.
            if not [d for d in root.swaps + root.mounts.values()
                        if d in self._devices and
                           (root.name == new_install_name or d.format.exists)]:
                continue

            page = Page()
            page.pageTitle = root.name

            for (mountpoint, device) in root.mounts.iteritems():
                if device not in self._devices or \
                   (root.name != new_install_name and not device.format.exists):
                    continue

                selector = page.addDevice(self._mountpointName(mountpoint) or device.format.name, Size(spec="%f MB" % device.size), mountpoint, self.on_selector_clicked)
                selector._device = device
                selector._root = root

            for device in root.swaps:
                if device not in self._devices or \
                   (root.name != new_install_name and not device.format.exists):
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

            for u in self.unusedDevices:
                selector = page.addDevice(u.format.name, Size(spec="%f MB" % u.size), None, self.on_selector_clicked)
                selector._device = u
                selector._root = None

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
        page = self._accordion._find_by_title(new_install_name).get_child()
        devices = [device]
        if not hasattr(page, "_members"):
            # remove the CreateNewPage and replace it with a regular Page
            expander = self._accordion._find_by_title(new_install_name)
            expander.remove(expander.get_child())

            page = Page()
            page.pageTitle = new_install_name
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
        page = self._accordion._find_by_title(new_install_name).get_child()
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

        log.info("ui: saving changes to device %s" % device.name)

        # TODO: member type, disk set

        size = self.builder.get_object("sizeSpinner").get_value()
        log.debug("new size: %s" % size)
        log.debug("old size: %s" % device.size)

        device_type = self._get_current_device_type()
        device_type_map = {DEVICE_TYPE_PARTITION: AUTOPART_TYPE_PLAIN,
                           DEVICE_TYPE_BTRFS: AUTOPART_TYPE_BTRFS,
                           DEVICE_TYPE_LVM: AUTOPART_TYPE_LVM,
                           DEVICE_TYPE_MD: None}
        device_type = device_type_map[device_type]
        log.debug("new device type: %s" % device_type)

        fs_type_combo = self.builder.get_object("fileSystemTypeCombo")
        fs_type_index = fs_type_combo.get_active()
        fs_type = fs_type_combo.get_model()[fs_type_index][0]
        log.debug("new fs type: %s" % fs_type)

        prev_encrypted = device.encrypted
        log.debug("old encryption setting: %s" % prev_encrypted)
        encrypted = self.builder.get_object("encryptCheckbox").get_active()
        log.debug("new encryption setting: %s" % encrypted)

        label = self.builder.get_object("labelEntry").get_text()
        old_label = getattr(device.format, "label", "") or ""

        mountpoint = None   # None means format type is not mountable
        mountPointEntry = self.builder.get_object("mountPointEntry")
        if mountPointEntry.get_sensitive():
            mountpoint = mountPointEntry.get_text()

        old_mountpoint = getattr(device.format, "mountpoint", "") or ""
        log.debug("old mountpoint: %s" % old_mountpoint)
        log.debug("new mountpoint: %s" % mountpoint)
        if mountpoint is not None and mountpoint != old_mountpoint:
            error = validate_mountpoint(mountpoint, self.__storage.mountpoints.keys())
            if error:
                self._error = mountpoint_validation_msgs[error]
                self.window.set_info(Gtk.MessageType.WARNING, self._error)
                self.window.show_all()
                return

        raid_level = self._get_raid_level()

        fs_type_short = getFormat(fs_type).type

        ##
        ## VALIDATION
        ##
        error = None
        if device_type != AUTOPART_TYPE_PLAIN and mountpoint == "/boot/efi":
            error = (_("/boot/efi must be on a device of type %s")
                     % DEVICE_TEXT_PARTITION)
        elif device_type != AUTOPART_TYPE_PLAIN and \
             fs_type_short in partition_only_format_types:
            error = (_("%s must be on a device of type %s")
                     % (fs_type, DEVICE_TEXT_PARTITION))
        elif mountpoint and encrypted and mountpoint.startswith("/boot"):
            error = _("%s cannot be encrypted") % mountpoint
        elif encrypted and fs_type_short in partition_only_format_types:
            error = _("%s cannot be encrypted") % fs_type

        if error:
            self.window.set_info(Gtk.MessageType.WARNING, error)
            self.window.show_all()
            return

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
        device_types = {"partition": AUTOPART_TYPE_PLAIN,
                        "lvmlv": AUTOPART_TYPE_LVM,
                        "btrfs subvolume": AUTOPART_TYPE_BTRFS,
                        "btrfs volume": AUTOPART_TYPE_BTRFS,
                        "mdarray": None}
        current_device_type = device.type
        use_dev = device
        if current_device_type == "luks/dm-crypt":
            current_device_type = device.slave.type
            use_dev = device.slave
        current_device_type = device_types.get(current_device_type)

        old_raid_level = None
        if current_device_type is None:
            old_raid_level = mdraid.raidLevelString(use_dev.level)
        elif current_device_type == AUTOPART_TYPE_BTRFS:
            if hasattr(use_dev, "dataLevel"):
                old_raid_level = use_dev.dataLevel or "single"
            else:
                old_raid_level = use_dev.volume.dataLevel or "single"

        changed_device_type = (current_device_type != device_type)
        changed_raid_level = (current_device_type == device_type and
                              device_type in (None, AUTOPART_TYPE_BTRFS) and
                              old_raid_level != raid_level)

        if changed_device_type or changed_raid_level:
            if changed_device_type:
                log.info("changing device type from %s to %s"
                            % (current_device_type, device_type))
            else:
                log.info("changing raid level from %s to %s"
                            % (old_raid_level, raid_level))

            # remove the current device
            self.clear_errors()
            root = self._current_selector._root
            self._destroy_device(device)
            if device in self._devices:
                # the removal failed. don't continue.
                return

            with ui_storage_logger():
                # Use any disks with space in addition to any disks used by
                # a defined container.
                disks = [d for d in self._clearpartDevices
                            if getattr(d.format, "free", 0) > 500]
                container = self.__storage.getContainer(factory)
                if container:
                    disks = list(set(disks).union(container.disks))
                log.debug("disks: %s" % [d.name for d in disks])
                try:
                    self._replace_device(device_type, size, fstype=fs_type,
                                         disks=disks, mountpoint=mountpoint,
                                         label=label, raid_level=raid_level,
                                         encrypted=encrypted,
                                         selector=selector)
                except ErrorRecoveryFailure as e:
                    self._error = e
                    self.window.set_info(Gtk.MessageType.WARNING,
                                         unrecoverable_error_msg)
                    self.window.show_all()
                    self._reset_storage()
                except StorageError as e:
                    log.error("newDevice failed: %s" % e)
                    self._error = e
                    self.window.set_info(Gtk.MessageType.WARNING,
                                         device_configuration_error_msg)
                    self.window.show_all()

                    # in this case we have removed the old device so we now have
                    # to re-create it
                    device_type = device_types.get(device.type)
                    raid_level = None
                    if hasattr(device, "level"):
                        # md
                        raid_level = mdraid.raidLevelString(device.level)
                    elif hasattr(device, "dataLevel"):
                        raid_level = device.dataLevel
                    elif hasattr(device, "volume"):
                        # btrfs subvol
                        raid_level = device.volume.dataLevel

                    try:
                        # XXX FIXME: pass old raid level -- not new one
                        self._replace_device(device_type, device.size,
                                             disks=disks,
                                             fstype=device.format.type,
                                             mountpoint=old_mountpoint,
                                             label=old_label,
                                             raid_level=raid_level,
                                             encrypted=encrypted,
                                             selector=selector)
                    except StorageError as e:
                        # failed to recover.
                        self.clear_errors()
                        self._error = e
                        self.window.set_info(Gtk.MessageType.WARNING,
                                             unrecoverable_error_msg)
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

            # update size props of all btrfs devices' selectors
            self._update_btrfs_selectors()

            self._updateSpaceDisplay()
            self._populate_right_side(selector)
            return

        ##
        ## SIZE
        ##
        # new size means resize for existing devices and adjust for new ones
        if int(size) != int(device.size):
            self.clear_errors()
            old_size = device.size
            if device.exists and device.resizable:
                with ui_storage_logger():
                    try:
                        self.__storage.resizeDevice(device, size)
                    except StorageError as e:
                        log.error("failed to schedule device resize: %s" % e)
                        device.size = old_size
                        self._error = e
                        self.window.set_info(Gtk.MessageType.WARNING,
                                             _("Device resize request failed. "
                                               "Click for details."))
                        self.window.show_all()
                    else:
                        log.debug("%r" % device)
                        log.debug("new size: %s" % device.size)
                        log.debug("target size: %s" % device.targetSize)
            else:
                with ui_storage_logger():
                    try:
                        self.__storage.newDevice(device_type, size,
                                                 device=device,
                                                 disks=device.disks,
                                                 raid_level=raid_level)
                    except ErrorRecoveryFailure as e:
                        self._error = e
                        self.window.set_info(Gtk.MessageType.WARNING,
                                             unrecoverable_error_msg)
                        self.window.show_all()
                        self._reset_storage()
                    except StorageError as e:
                        log.error("newDevice failed: %s" % e)
                        self._error = e
                        self.window.set_info(Gtk.MessageType.WARNING,
                                             device_configuration_error_msg)
                        self.window.show_all()

            log.debug("updating selector size to '%s'"
                       % str(Size(spec="%f MB" % device.size)).upper())
            # update the selector's size property
            selector.props.size = str(Size(spec="%f MB" % device.size)).upper()

            # update size props of all btrfs devices' selectors
            self._update_btrfs_selectors()

            self._updateSpaceDisplay()
            self._populate_right_side(selector)

        ##
        ## ENCRYPTION
        ##
        old_device = device
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
        if fs_type != device.format.name:
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
                    self.window.set_info(Gtk.MessageType.WARNING,
                                         _("Device reformat request failed. "
                                           "Click for details."))
                    self.window.show_all()
                else:
                    if old_mountpoint:
                        selector.props.mountpoint = (mountpoint or
                                                     selector._device.format.name)
                        selector.props.name = (self._mountpointName(mountpoint)
                                               or selector._device.format.name)
                    else:
                        # first, remove this selector from any page(s) and add
                        # it to the new page
                        for page in self._accordion.allPages:
                            for _selector in getattr(page, "_members", []):
                                if _selector._device in (device, old_device):
                                    page.removeSelector(_selector)
                                    if not page._members:
                                        log.debug("removing empty page %s" % page.pageTitle)
                                        self._accordion.removePage(page.pageTitle)

                        self.add_new_selector(device)

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
        disk_count = len(self._clearpartDevices)
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
            factory_type = None
        elif device_type == DEVICE_TYPE_BTRFS:
            base_level = "single"
            factory_type = AUTOPART_TYPE_BTRFS
        else:
            return

        # Create a DeviceFactory to use to calculate the disk space needs for
        # this device with various raid features enabled.
        with ui_storage_logger():
            factory = self.__storage.getDeviceFactory(factory_type, size,
                                                      disks=self._clearpartDevices, 
                                                      raid_level=base_level)

        widget_dict = self._get_raid_widget_dict(device_type)
        try:
            base_size = factory.device_size
        except ValueError as e:
            log.error("failed to populate UI raid options: %s" % e)
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
        if device_type_text == DEVICE_TEXT_LVM:
            device_type = DEVICE_TYPE_LVM
        elif device_type_text == DEVICE_TEXT_MD:
            device_type = DEVICE_TYPE_MD
        elif device_type_text == DEVICE_TEXT_PARTITION:
            device_type = DEVICE_TYPE_PARTITION
        elif device_type_text == DEVICE_TEXT_BTRFS:
            device_type = DEVICE_TYPE_BTRFS
        else:
            log.error("unknown device type: '%s'" % device_type_text)

        return device_type

    def _populate_right_side(self, selector):
        log.debug("populate_right_side: %s" % selector._device)
        encryptCheckbox = self.builder.get_object("encryptCheckbox")
        labelEntry = self.builder.get_object("labelEntry")
        mountPointEntry = self.builder.get_object("mountPointEntry")
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

        selectedDeviceLabel.set_text(selector.props.name)
        selectedDeviceDescLabel.set_text(self._description(selector.props.name))

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

        encryptCheckbox.set_active(device.encrypted)

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

        ##
        ## Set up the device type combo.
        ##

        btrfs_pos = None
        btrfs_included = False
        md_pos = None
        md_included = False
        for idx, itr in enumerate(typeCombo.get_model()):
            if itr[0] == DEVICE_TEXT_BTRFS:
                btrfs_pos = idx
                btrfs_included = True
            elif itr[0] == DEVICE_TEXT_MD:
                md_pos = idx
                md_included = True

        # only include md if there are two or more disks
        include_md = (use_dev.type == "mdarray" or
                      len(self._clearpartDevices) > 1)
        if include_md and not md_included:
            typeCombo.append_text(DEVICE_TEXT_RAID)
        elif md_included and not include_md:
            typeCombo.remove(md_pos)

        # if the format is swap the device type can't be btrfs
        include_btrfs = (use_dev.format.type not in
                            partition_only_format_types + ["swap"])
        if include_btrfs and not btrfs_included:
            typeCombo.append_text(DEVICE_TEXT_BTRFS)
        elif btrfs_included and not include_btrfs:
            typeCombo.remove(btrfs_pos)

        md_pos = None
        btrfs_pos = None
        partition_pos = None
        lvm_pos = None
        for idx, itr in enumerate(typeCombo.get_model()):
            if itr[0] == DEVICE_TEXT_BTRFS:
                btrfs_pos = idx
            elif itr[0] == DEVICE_TEXT_MD:
                md_pos = idx
            elif itr[0] == DEVICE_TEXT_PARTITION:
                partition_pos = idx
            elif itr[0] == DEVICE_TEXT_LVM:
                lvm_pos = idx

        raid_level = None
        if use_dev.type == "lvmlv":
            # TODO: striping/mirroring
            typeCombo.set_active(lvm_pos)
        elif use_dev.type == "mdarray":
            typeCombo.set_active(md_pos)
            raid_level = mdraid.raidLevelString(use_dev.level)
        elif use_dev.type == "partition":
            typeCombo.set_active(partition_pos)
        elif use_dev.type.startswith("btrfs"):
            typeCombo.set_active(btrfs_pos)
            if hasattr(use_dev, "volume"):
                raid_level = use_dev.volume.dataLevel or "single"
            else:
                raid_level = use_dev.dataLevel or "single"

        # you can't change the type of an existing device
        typeCombo.set_sensitive(not device.exists)

        self._populate_raid(raid_level, device.size)
        self.builder.get_object("optionsNotebook").set_sensitive(not device.exists)

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
        with enlightbox(self.window, dialog.window):
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
        size = dialog.size
        fstype = self.storage.getFSType(mountpoint)
        encrypted = self.data.autopart.encrypted

        # we're doing nothing here to ensure that bootable requests end up on
        # the boot disk, but the weight from platform should take care of this

        if mountpoint.lower() in ("swap", "biosboot", "prepboot"):
            mountpoint = None

        device_type = self.data.autopart.type
        if device_type != AUTOPART_TYPE_PLAIN and \
             mountpoint == "/boot/efi":
            device_type = AUTOPART_TYPE_PLAIN
        elif device_type != AUTOPART_TYPE_PLAIN and \
             fstype in partition_only_format_types:
            device_type = AUTOPART_TYPE_PLAIN

        # some devices should never be encrypted
        if ((mountpoint and mountpoint.startswith("/boot")) or
            fstype in partition_only_format_types):
            encrypted = False

        disks = self._clearpartDevices
        self.clear_errors()

        with ui_storage_logger():
            try:
                self.__storage.newDevice(device_type,
                                         size=float(size.convertTo(spec="mb")),
                                         fstype=fstype,
                                         mountpoint=mountpoint,
                                         encrypted=encrypted,
                                         disks=disks)
            except ErrorRecoveryFailure as e:
                log.error("error recovery failure")
                self._error = e
                self.window.set_info(Gtk.MessageType.ERROR,
                                     unrecoverable_error_msg)
                self.window.show_all()
                self._reset_storage()
            except StorageError as e:
                log.error("newDevice failed: %s" % e)
                self._error = e
                self.window.set_info(Gtk.MessageType.ERROR,
                                     _("Failed to add new device. Click for "
                                       "details."))
                self.window.show_all()

        self._devices = self.__storage.devices
        self._do_refresh()
        self._updateSpaceDisplay()

    def _destroy_device(self, device):
        self.clear_errors()
        with ui_storage_logger():
            is_logical_partition = getattr(device, "isLogical", False)
            try:
                self.__storage.destroyDevice(device)
            except StorageError as e:
                log.error("failed to schedule device removal: %s" % e)
                self._error = e
                self.window.set_info(Gtk.MessageType.WARNING,
                                     _("Device removal request failed. Click "
                                       "for details."))
                self.window.show_all()
            else:
                if is_logical_partition:
                    self.__storage.removeEmptyExtendedPartitions()

        # If we've just removed the last partition and the disklabel is pre-
        # existing, reinitialize the disk.
        if device.type == "partition" and device.disk.format.exists:
            with ui_storage_logger():
                if self.__storage.shouldClear(device.disk):
                    self.__storage.initializeDisk(device.disk)

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

        if container and not container.exists and \
           self.__storage.devicetree.getChildren(container):
            # adjust container to size of remaining devices
            with ui_storage_logger():
                # TODO: raid
                factory = self.__storage.getDeviceFactory(device_type, 0)
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

        if root_name == new_install_name:
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
                           showRemove=False)
            dialog.run()

    def on_configure_clicked(self, button):
        pass

    def on_selector_clicked(self, selector):
        if not self._initialized:
            return

        # Take care of the previously chosen selector.
        if self._current_selector and self._initialized:
            log.debug("current selector: %s" % self._current_selector._device)
            log.debug("new selector: %s" % selector._device)
            nb_page = self._partitionsNotebook.get_current_page()
            log.debug("notebook page = %s" % nb_page)
            if nb_page != NOTEBOOK_LUKS_PAGE:
                self._save_right_side(self._current_selector)

            self._current_selector.set_chosen(False)

        if selector._device.format.type == "luks" and \
           selector._device.format.exists:
            self._partitionsNotebook.set_current_page(NOTEBOOK_LUKS_PAGE)
            selectedDeviceLabel = self.builder.get_object("encryptedDeviceLabel")
            selectedDeviceDescLabel = self.builder.get_object("encryptedDeviceDescriptionLabel")
            selectedDeviceLabel.set_text(selector.props.name)
            selectedDeviceDescLabel.set_text(self._description(selector.props.name))
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

        self._configButton.set_sensitive(True)
        self._removeButton.set_sensitive(True)
        return True

    def on_page_clicked(self, page):
        if not self._initialized:
            return

        log.debug("page clicked: %s" % getattr(page, "pageTitle", None))
        if self._current_selector:
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
                self.window.set_info(Gtk.MessageType.ERROR,
                                     _("No disks selected."))
                self.window.show_all()
            except NotEnoughFreeSpaceError as e:
                # No handling should be required for this.
                log.error("doAutoPartition failed: %s" % e)
                self._error = e
                self.window.set_info(Gtk.MessageType.ERROR,
                                     _("Not enough free space on selected disks."))
                self.window.show_all()
            except StorageError as e:
                log.error("doAutoPartition failed: %s" % e)
                self._reset_storage()
                self._error = e
                self.window.set_info(Gtk.MessageType.ERROR,
                                     _("Automatic partitioning failed. Click "
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
        labelEntry.set_sensitive(hasattr(fmt, "label"))
        mountPointEntry.set_sensitive(fmt.mountable)

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
        if new_type in (DEVICE_TYPE_PARTITION, DEVICE_TYPE_LVM):
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
            raid_level = "single"
        elif new_type == DEVICE_TYPE_MD:
            raid_level = "raid0"

        size = self.builder.get_object("sizeSpinner").get_value()
        self._populate_raid(raid_level, size)

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
        fsCombo.set_sensitive(fs_type_sensitive)
        # end btrfs magic

    def clear_errors(self):
        self._error = None
        self.window.clear_info()

    def on_info_bar_clicked(self, *args):
        log.debug("info bar clicked: %s (%s)" % (self._error, args))
        if not self._error:
            return

        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.CLOSE,
                                message_format=str(self._error))

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
            self.window.set_info(Gtk.MessageType.WARNING,
                                 _("Failed to unlock encrypted block device. "
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
