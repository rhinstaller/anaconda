# vim: set fileencoding=utf-8
# Custom partitioning classes.
#
# Copyright (C) 2012, 2013  Red Hat, Inc.
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
# - Implement striping and mirroring for LVM.
# - Activating reformat should always enable resize for existing devices.

from contextlib import contextmanager
import re

from pykickstart.constants import CLEARPART_TYPE_NONE, AUTOPART_TYPE_PLAIN, AUTOPART_TYPE_BTRFS, AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP

from pyanaconda.i18n import _, N_, P_
from pyanaconda.product import productName, productVersion
from pyanaconda.threads import AnacondaThread, threadMgr
from pyanaconda.constants import THREAD_EXECUTE_STORAGE, THREAD_STORAGE, THREAD_CUSTOM_STORAGE_INIT
from pyanaconda.iutil import lowerASCII
from pyanaconda.bootloader import BootLoaderError

from blivet import devicefactory
from blivet.formats import device_formats
from blivet.formats import getFormat
from blivet.formats.fs import FS
from blivet.platform import platform
from blivet.size import Size
from blivet import Root
from blivet.devicefactory import DEVICE_TYPE_LVM
from blivet.devicefactory import DEVICE_TYPE_BTRFS
from blivet.devicefactory import DEVICE_TYPE_PARTITION
from blivet.devicefactory import DEVICE_TYPE_MD
from blivet.devicefactory import DEVICE_TYPE_DISK
from blivet.devicefactory import DEVICE_TYPE_LVM_THINP
from blivet.devicefactory import get_raid_level
from blivet.devicefactory import SIZE_POLICY_AUTO
from blivet.devicefactory import SIZE_POLICY_MAX
from blivet import findExistingInstallations
from blivet.partitioning import doAutoPartition
from blivet.errors import StorageError
from blivet.errors import NoDisksError
from blivet.errors import NotEnoughFreeSpaceError
from blivet.errors import SizeParamsError, SizeNotPositiveError
from blivet.devicelibs import mdraid
from blivet.devices import LUKSDevice

from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.storage import StorageChecker
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.passphrase import PassphraseDialog
from pyanaconda.ui.gui.spokes.lib.accordion import selectorFromDevice, Accordion, Page, CreateNewPage, UnknownPage
from pyanaconda.ui.gui.spokes.lib.refresh import RefreshDialog
from pyanaconda.ui.gui.spokes.lib.summary import ActionSummaryDialog
from pyanaconda.ui.gui.utils import setViewportBackground, gtk_action_wait, enlightbox, fancy_set_sensitive, ignoreEscape,\
        really_hide, really_show
from pyanaconda.ui.gui.categories.system import SystemCategory
from pyanaconda.ui.lib.disks import size_str

from gi.repository import Gdk, Gtk
from gi.repository.AnacondaWidgets import MountpointSelector

import logging
log = logging.getLogger("anaconda")

__all__ = ["CustomPartitioningSpoke"]

NOTEBOOK_LABEL_PAGE = 0
NOTEBOOK_DETAILS_PAGE = 1
NOTEBOOK_LUKS_PAGE = 2
NOTEBOOK_UNEDITABLE_PAGE = 3
NOTEBOOK_INCOMPLETE_PAGE = 4

new_install_name = N_("New %(name)s %(version)s Installation")
new_container_text = N_("Create a new %(container_type)s ...")
container_tooltip = N_("Create or select %(container_type)s")
container_dialog_title = N_("CONFIGURE %(container_type)s")
container_dialog_text = N_("Please create a name for this %(container_type)s "
                           "and select at least one disk below.")
lvm_container_name = N_("Volume Group")
btrfs_container_name = N_("Volume")
unrecoverable_error_msg = N_("Storage configuration reset due to unrecoverable "
                             "error. Click for details.")
device_configuration_error_msg = N_("Device reconfiguration failed. Click for "
                                    "details.")

empty_mountpoint_msg = N_("Please enter a valid mountpoint.")
invalid_mountpoint_msg = N_("That mount point is invalid. Try something else?")
mountpoint_in_use_msg = N_("That mount point is already in use. Try something else?")

raid_level_not_enough_disks_msg = N_("The RAID level you have selected (%(level)s) "
                                     "requires more disks (%(min)d) than you "
                                     "currently have selected (%(count)d).")
empty_name_msg = N_("Please enter a valid name.")
invalid_name_msg = N_("That name is invalid. Try something else?")

container_type_names = {DEVICE_TYPE_LVM: lvm_container_name,
                        DEVICE_TYPE_LVM_THINP: lvm_container_name,
                        DEVICE_TYPE_BTRFS: btrfs_container_name}

MOUNTPOINT_OK = 0
MOUNTPOINT_INVALID = 1
MOUNTPOINT_IN_USE = 2
MOUNTPOINT_EMPTY = 3

mountpoint_validation_msgs = {MOUNTPOINT_OK: "",
                              MOUNTPOINT_INVALID: invalid_mountpoint_msg,
                              MOUNTPOINT_IN_USE: mountpoint_in_use_msg,
                              MOUNTPOINT_EMPTY: empty_mountpoint_msg}

DEVICE_TEXT_LVM = N_("LVM")
DEVICE_TEXT_LVM_THINP = N_("LVM Thin Provisioning")
DEVICE_TEXT_MD = N_("RAID")
DEVICE_TEXT_PARTITION = N_("Standard Partition")
DEVICE_TEXT_BTRFS = N_("BTRFS")
DEVICE_TEXT_DISK = N_("Disk")

device_text_map = {DEVICE_TYPE_LVM: DEVICE_TEXT_LVM,
                   DEVICE_TYPE_MD: DEVICE_TEXT_MD,
                   DEVICE_TYPE_PARTITION: DEVICE_TEXT_PARTITION,
                   DEVICE_TYPE_BTRFS: DEVICE_TEXT_BTRFS,
                   DEVICE_TYPE_LVM_THINP: DEVICE_TEXT_LVM_THINP}

partition_only_format_types = ["efi", "hfs+", "prepboot", "biosboot",
                               "appleboot"]

def size_from_entry(entry):
    size_text = entry.get_text().strip()

    # if no unit was specified, default to MB
    if not re.search(r'[A-Za-z]+$', size_text):
        size_text += "MB"

    try:
        size = Size(spec=size_text)
    except (SizeParamsError, SizeNotPositiveError, ValueError):
        return None
    else:
        # Minimium size for ui-created partitions is 1MB.
        if size.convertTo(spec="mb") < 1:
            size = Size(spec="1mb")

    return size

class UIStorageFilter(logging.Filter):
    def filter(self, record):
        record.name = "storage.ui"
        return True

@contextmanager
def ui_storage_logger():
    storage_log = logging.getLogger("blivet")
    f = UIStorageFilter()
    storage_log.addFilter(f)
    yield
    storage_log.removeFilter(f)

def populate_mountpoint_store(store, used_mountpoints):
    # sure, add whatever you want to this list. this is just a start.
    paths = ["/", "/boot", "/home", "/var"] + \
            platform.bootStage1ConstraintDict["mountpoints"]

    # Sort the list now so all the real mountpoints go to the front, then
    # add all the pseudo mountpoints we have.
    paths.sort()
    paths += ["swap"]

    for fmt in ["appleboot", "biosboot", "prepboot"]:
        if getFormat(fmt).supported:
            paths += [fmt]

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
    elif mountpoint.startswith("/dev") or mountpoint.startswith("/proc") or \
         mountpoint.startswith("/sys"):
        valid = MOUNTPOINT_INVALID
    elif (lowerASCII(mountpoint) not in fake_mountpoints and
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

def selectedRaidLevel(raidLevelCombo):
    """Interpret the selection of a RAID level combo box."""
    itr = raidLevelCombo.get_active_iter()
    store = raidLevelCombo.get_model()

    if not itr:
        return

    selected_level_string = store[itr][0]   # eg: "RAID1 (Redundancy)"
    level = selected_level_string.split()[0]    # -> "RAID1"

    # The RAID level strings are not translated, but the "None" string in
    # the container dialog is. Transformations in relation to "None" need
    # to happen within the locale settings, but transformations in
    # relation to "RAID* ..." need to happen only within ASCII. For example,
    # "RAID1".lower() in Turkish would become "raıd1", which is not what
    # we want.
    levelLocale = level.lower()
    levelASCII = lowerASCII(level)

    if levelASCII == "none" or levelLocale == _("None").lower():
        return None

    return levelASCII

class AddDialog(GUIObject):
    builderObjects = ["addDialog", "mountPointStore", "mountPointCompletion", "mountPointEntryBuffer"]
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
        self.builder.get_object("addMountPointEntry").set_model(store)

        completion = self.builder.get_object("mountPointCompletion")
        completion.set_text_column(0)
        completion.set_popup_completion(True)

        self._warningLabel = self.builder.get_object("mountPointWarningLabel")

    def on_add_confirm_clicked(self, button, *args):
        self.mountpoint = self.builder.get_object("addMountPointEntry").get_active_text()
        self._error = validate_mountpoint(self.mountpoint, self.mountpoints,
                                          strict=False)
        self._warningLabel.set_text(_(mountpoint_validation_msgs[self._error]))
        self.window.show_all()
        if self._error:
            return

        self.size = size_from_entry(self.builder.get_object("addSizeEntry"))
        self.window.destroy()

    def refresh(self):
        GUIObject.refresh(self)
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

    def __init__(self, *args, **kwargs):
        GUIObject.__init__(self, *args, **kwargs)
        self._removeAll = self.builder.get_object("removeAllCheckbox")

    @property
    def deleteAll(self):
        return self._removeAll.get_active()

    def on_delete_confirm_clicked(self, button, *args):
        self.window.destroy()

    # pylint: disable-msg=W0221
    def refresh(self, mountpoint, device, rootName):
        GUIObject.refresh(self)
        label = self.builder.get_object("confirmLabel")

        if rootName and "_" in rootName:
            rootName = rootName.replace("_", "__")
        self._removeAll.set_label(
                _("Delete _all other filesystems in the %s root as well.") % rootName)
        self._removeAll.set_sensitive(rootName is not None)

        if mountpoint:
            txt = "%s (%s)" % (mountpoint, device)
        else:
            txt = device

        label_text = _("Are you sure you want to delete all of the data on %s?") % txt

        label.set_text(label_text)

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

class ContainerDialog(GUIObject):
    builderObjects = ["container_dialog", "disk_store", "container_disk_view",
                      "containerRaidStoreFiltered", "containerRaidLevelLabel",
                      "containerRaidLevelCombo", "raidLevelStore",
                      "containerSizeCombo", "containerSizeEntry",
                      "containerSizeLabel", "containerEncryptedCheckbox"]
    mainWidgetName = "container_dialog"
    uiFile = "spokes/custom.glade"

    def __init__(self, *args, **kwargs):
        # these are all absolutely required. not getting them is fatal.
        self._disks = kwargs.pop("disks")
        free = kwargs.pop("free")
        self.selected = kwargs.pop("selected")[:]
        self.name = kwargs.pop("name") or "" # make sure it's a string
        self.device_type = kwargs.pop("device_type")

        # these are less critical
        self.raid_level = kwargs.pop("raid_level", None) or None # not ""
        self.encrypted = kwargs.pop("encrypted", False)
        self.exists = kwargs.pop("exists", False)

        self.size_policy = kwargs.pop("size_policy", SIZE_POLICY_AUTO)
        self.size = kwargs.pop("size", 0)

        self._error = None
        GUIObject.__init__(self, *args, **kwargs)

        self._grabObjects()

        # set up the dialog labels with device-type-specific text
        container_type = container_type_names.get(self.device_type,
                                                  _("container"))
        title_text = container_dialog_title % {"container_type": container_type.upper()}
        self._title_label.set_text(title_text)

        dialog_text = container_dialog_text % {"container_type": container_type.lower()}
        self._dialog_label.set_text(dialog_text)

        # populate the dialog widgets
        self._name_entry.set_text(self.name)

        # populate the store
        for disk in self._disks:
            self._store.append([disk.description,
                                str(Size(spec="%dMB" % disk.size)),
                                str(free[disk.name][0]),
                                disk.serial,
                                disk.id])

        model = self._treeview.get_model()
        itr = model.get_iter_first()

        selected_ids = [d.id for d in self.selected]
        selection = self._treeview.get_selection()
        while itr:
            disk_id = model.get_value(itr, 4)
            if disk_id in selected_ids:
                selection.select_iter(itr)

            itr = model.iter_next(itr)

        # XXX how will this be related to the device encryption setting?
        self._encryptCheckbutton.set_active(self.encrypted)

        # set up the raid level combo
        # XXX how will this be related to the device raid level setting?
        self._raidStoreFilter.set_visible_func(self._raid_level_visible)
        self._raidStoreFilter.refilter()
        self._populate_raid()

        size = Size(spec="%d mb" % self.size)
        self._sizeEntry.set_text(size.humanReadable(max_places=None))
        if self.size_policy == SIZE_POLICY_AUTO:
            self._sizeCombo.set_active(0)
        elif self.size_policy == SIZE_POLICY_MAX:
            self._sizeCombo.set_active(1)
        else:
            self._sizeCombo.set_active(2)

        if self.exists:
            fancy_set_sensitive(self._name_entry, False)
            self._treeview.set_sensitive(False)
            fancy_set_sensitive(self._encryptCheckbutton, False)
            fancy_set_sensitive(self._sizeCombo, False)
            self._sizeEntry.set_sensitive(False)

    def _grabObjects(self):
        self._title_label = self.builder.get_object("container_dialog_title_label")
        self._dialog_label = self.builder.get_object("container_dialog_label")
        self._error_label = self.builder.get_object("containerErrorLabel")

        self._name_entry = self.builder.get_object("container_name_entry")

        self._encryptCheckbutton = self.builder.get_object("containerEncryptedCheckbox")
        self._raidStoreFilter = self.builder.get_object("containerRaidStoreFiltered")

        self._store = self.builder.get_object("disk_store")
        self._treeview = self.builder.get_object("container_disk_view")

        self._sizeCombo = self.builder.get_object("containerSizeCombo")
        self._sizeEntry = self.builder.get_object("containerSizeEntry")

        self._raidLevelCombo = self.builder.get_object("containerRaidLevelCombo")
        self._raidLevelLabel = self.builder.get_object("containerRaidLevelLabel")

    def _get_disk_by_id(self, disk_id):
        for disk in self._disks:
            if disk.id == disk_id:
                return disk

    def on_save_clicked(self, button):
        if self.exists:
            self.window.destroy()
            return

        # If no name was entered, quit the dialog as if they did nothing.
        name = self._name_entry.get_text().strip()
        if not name:
            self._error = _(empty_name_msg)
            self._error_label.set_text(self._error)
            self.window.show_all()
            return

        model, paths = self._treeview.get_selection().get_selected_rows()

        raid_level = selectedRaidLevel(self._raidLevelCombo)
        if raid_level:
            md_level = mdraid.raidLevel(raid_level)
            min_disks = mdraid.get_raid_min_members(md_level)
            if len(paths) < min_disks:
                self._error = (_(raid_level_not_enough_disks_msg)
                                 % {"level" : raid_level,
                                     "min" : min_disks,
                                     "count" : len(paths)})
                self._error_label.set_text(self._error)
                self.window.show_all()
                return

        idx = self._sizeCombo.get_active()
        if idx == 0:
            size = SIZE_POLICY_AUTO
        elif idx == 1:
            size = SIZE_POLICY_MAX
        elif idx == 2:
            size = size_from_entry(self._sizeEntry)
            if size:
                size = int(size.convertTo(spec="MB"))
            elif size is None:
                size = SIZE_POLICY_MAX

        # now save the changes

        self.selected = []
        for path in paths:
            itr = model.get_iter(path)
            disk_id = model.get_value(itr, 4)
            self.selected.append(self._get_disk_by_id(disk_id))

        self.name = name
        self.raid_level = raid_level
        self.encrypted = self._encryptCheckbutton.get_active()
        self.size_policy = size

        self._error_label.set_text("")
        self.window.destroy()

    def run(self):
        while True:
            self._error = None
            rc = self.window.run()
            if not self._error:
                return rc

    def on_size_changed(self, combo):
        active_index = combo.get_active()
        if active_index == 0:
            self._sizeEntry.set_sensitive(False)
        elif active_index == 1:
            self._sizeEntry.set_sensitive(False)
        else:
            self._sizeEntry.set_sensitive(True)

    def _raid_level_visible(self, model, itr, user_data):
        # This is weird because for lvm's container-wide raid we use md.
        if self.device_type in (DEVICE_TYPE_LVM, DEVICE_TYPE_LVM_THINP):
            return model[itr][4]
        elif self.device_type == DEVICE_TYPE_BTRFS:
            return model[itr][3]

    def _populate_raid(self):
        """ Set up the raid-specific portion of the device details. """
        if self.device_type not in [DEVICE_TYPE_LVM, DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM_THINP]:
            map(really_hide, [self._raidLevelLabel, self._raidLevelCombo])
            return

        raid_level = self.raid_level
        if not raid_level or raid_level == "single":
            raid_level = _("None")

        # Set a default RAID level in the combo.
        for (i, row) in enumerate(self._raidLevelCombo.get_model()):
            log.debug("container dialog: raid level %s", row[0])
            if row[0].upper().startswith(raid_level.upper()):
                self._raidLevelCombo.set_active(i)
                break

        map(really_show, [self._raidLevelLabel, self._raidLevelCombo])
        fancy_set_sensitive(self._raidLevelCombo, not self.exists)

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
    builderObjects = ["customStorageWindow",
                      "partitionStore", "raidStoreFiltered", "raidLevelStore",
                      "addImage", "removeImage", "settingsImage",
                      "mountPointCompletion", "mountPointStore"]
    mainWidgetName = "customStorageWindow"
    uiFile = "spokes/custom.glade"

    category = SystemCategory
    title = N_("MANUAL PARTITIONING")

    def __init__(self, data, storage, payload, instclass):
        StorageChecker.__init__(self)
        NormalSpoke.__init__(self, data, storage, payload, instclass)

        self.__storage = None

        self.passphrase = ""

        self._current_selector = None
        self._devices = []
        self._error = None
        self._media_disks = []
        self._fs_types = []             # list of supported fstypes
        self._free_space = Size(bytes=0)

        self._device_disks = []
        self._device_container_name = None
        self._device_container_raid_level = None
        self._device_container_encrypted = False
        self._device_container_size = SIZE_POLICY_AUTO
        self._device_name_dict = {DEVICE_TYPE_LVM: None,
                                  DEVICE_TYPE_MD: None,
                                  DEVICE_TYPE_LVM_THINP: None,
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

        new_swaps = (dev for dev in self.new_devices if dev.format.type == "swap")
        self.storage.setFstabSwaps(new_swaps)

        # update the global passphrase
        self.data.autopart.passphrase = self.passphrase

        # make sure any device/passphrase pairs we've obtained are remebered
        for device in self.storage.devices:
            if device.format.type == "luks" and not device.format.exists:
                if not device.format.hasKey:
                    device.format.passphrase = self.passphrase

                self.storage.savePassphrase(device)

        StorageChecker.errors = []
        # set up bootloader and check the configuration
        try:
            self.storage.setUpBootLoader()
        except BootLoaderError as e:
            log.error("storage configuration failed: %s", e)
            StorageChecker.errors = str(e).split("\n")
            self.data.bootloader.bootDrive = ""

        StorageChecker.run(self)
        hubQ.send_ready("StorageSpoke", True)

    @property
    def indirect(self):
        return True

    def _grabObjects(self):
        self._configureBox = self.builder.get_object("configureBox")

        self._partitionsViewport = self.builder.get_object("partitionsViewport")
        self._partitionsNotebook = self.builder.get_object("partitionsNotebook")

        self._whenCreateLabel = self.builder.get_object("whenCreateLabel")

        self._availableSpaceLabel = self.builder.get_object("availableSpaceLabel")
        self._totalSpaceLabel = self.builder.get_object("totalSpaceLabel")
        self._summaryLabel = self.builder.get_object("summary_label")

        # Buttons
        self._addButton = self.builder.get_object("addButton")
        self._applyButton = self.builder.get_object("applyButton")
        self._configButton = self.builder.get_object("configureButton")
        self._removeButton = self.builder.get_object("removeButton")

        # Detailed configuration stuff
        self._encryptCheckbox = self.builder.get_object("encryptCheckbox")
        self._fsCombo = self.builder.get_object("fileSystemTypeCombo")
        self._labelEntry = self.builder.get_object("labelEntry")
        self._mountPointEntry = self.builder.get_object("mountPointEntry")
        self._nameEntry = self.builder.get_object("nameEntry")
        self._raidLevelCombo = self.builder.get_object("raidLevelCombo")
        self._raidLevelLabel = self.builder.get_object("raidLevelLabel")
        self._reformatCheckbox = self.builder.get_object("reformatCheckbox")
        self._sizeEntry = self.builder.get_object("sizeEntry")
        self._typeCombo = self.builder.get_object("deviceTypeCombo")
        self._modifyContainerButton = self.builder.get_object("modifyContainerButton")
        self._containerCombo = self.builder.get_object("containerCombo")

        self._passphraseEntry = self.builder.get_object("passphraseEntry")

        # Stores
        self._raidStoreFilter = self.builder.get_object("raidStoreFiltered")

        # Labels
        self._selectedDeviceLabel = self.builder.get_object("selectedDeviceLabel")
        self._selectedDeviceDescLabel = self.builder.get_object("selectedDeviceDescLabel")
        self._encryptedDeviceLabel = self.builder.get_object("encryptedDeviceLabel")
        self._encryptedDeviceDescLabel = self.builder.get_object("encryptedDeviceDescriptionLabel")
        self._incompleteDeviceLabel = self.builder.get_object("incompleteDeviceLabel")
        self._incompleteDeviceDescLabel = self.builder.get_object("incompleteDeviceDescriptionLabel")
        self._incompleteDeviceOptionsLabel = self.builder.get_object("incompleteDeviceOptionsLabel")
        self._uneditableDeviceLabel = self.builder.get_object("uneditableDeviceLabel")
        self._uneditableDeviceDescLabel = self.builder.get_object("uneditableDeviceDescriptionLabel")
        self._containerLabel = self.builder.get_object("containerLabel")

    def initialize(self):
        NormalSpoke.initialize(self)
        self._grabObjects()

        setViewportBackground(self.builder.get_object("availableSpaceViewport"), "#db3279")
        setViewportBackground(self.builder.get_object("totalSpaceViewport"), "#60605b")

        self._raidStoreFilter.set_visible_func(self._raid_level_visible)

        self._accordion = Accordion()
        self._partitionsViewport.add(self._accordion)

        # Populate the list of valid filesystem types from the format classes.
        # Unfortunately, we have to narrow them down a little bit more because
        # this list will include things like PVs and RAID members.
        self._fsCombo.remove_all()

        threadMgr.add(AnacondaThread(name=THREAD_CUSTOM_STORAGE_INIT, target=self._initialize))

    def _initialize(self):
        @gtk_action_wait
        def gtk_action(name):
            self._fsCombo.append_text(name)

        self._fs_types = []
        for cls in device_formats.itervalues():
            obj = cls()

            # btrfs is always handled by on_device_type_changed
            supported_fs = (obj.type != "btrfs" and
                            obj.supported and obj.formattable and
                            (isinstance(obj, FS) or
                             obj.type in ["biosboot", "prepboot", "swap"]))
            if supported_fs:
                gtk_action(obj.name)
                self._fs_types.append(obj.name)

    @property
    def _clearpartDevices(self):
        return [d for d in self._devices if d.name in self.data.clearpart.drives and d.partitioned]

    @property
    def unusedDevices(self):
        unused_devices = [d for d in self.__storage.unusedDevices
                                if d.disks and d.mediaPresent and
                                not d.partitioned and d.isleaf]
        # add incomplete VGs and MDs
        incomplete = [d for d in self.__storage.devicetree._devices
                            if not getattr(d, "complete", True)]
        unused_devices.extend(incomplete)
        return unused_devices

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
        self._free_space = sum(f[0] for f in self._currentFreeInfo.values())

    def _currentTotalSpace(self):
        """Add up the sizes of all selected disks and return it as a Size."""
        totalSpace = 0

        for disk in self._clearpartDevices:
            totalSpace += disk.size

        return Size(spec="%s MB" % totalSpace)

    def _updateSpaceDisplay(self):
        # Set up the free space/available space displays in the bottom left.
        self._setCurrentFreeSpace()

        self._availableSpaceLabel.set_text(str(self._free_space))
        self._totalSpaceLabel.set_text(str(self._currentTotalSpace()))

        count = len(self.data.clearpart.drives)
        summary = P_("%d _storage device selected",
                     "%d _storage devices selected",
                     count) % count

        self._summaryLabel.set_markup("<span foreground='blue'><u>%s</u></span>" % summary)
        self._summaryLabel.set_use_underline(True)

    def _reset_storage(self):
        self.__storage = self.storage.copy()
        self._media_disks = []

        # hide removable disks containing install media
        for disk in self.__storage.disks:
            if disk.removable and disk.protected:
                self._media_disks.append(disk)
                self.__storage.devicetree.hide(disk)

        self._devices = self.__storage.devices

    def refresh(self):
        self.clear_errors()
        NormalSpoke.refresh(self)

        # Make sure the storage spoke execute method has finished before we
        # copy the storage instance.
        for thread_name in [THREAD_EXECUTE_STORAGE, THREAD_STORAGE]:
            threadMgr.wait(thread_name)

        self.passphrase = self.data.autopart.passphrase
        self._reset_storage()
        self._do_refresh()
        # update our free space number based on Storage
        self._setCurrentFreeSpace()

        self._updateSpaceDisplay()
        self._applyButton.set_sensitive(False)

    @property
    def translated_new_install_name(self):
        return _(new_install_name) % {"name" : productName, "version" : productVersion}

    @property
    def _current_page(self):
        # The current page is really a function of the current selector.
        # Whatever selector on the LHS is selected, the current page is the
        # page containing that selector.
        if not self._current_selector:
            return None

        for page in self._accordion.allPages:
            if self._current_selector in page.members:
                return page

        return None

    def _clear_current_selector(self):
        """ If something is selected, deselect it
        """
        if self._current_selector:
            self._current_selector.set_chosen(False)
            self._current_selector = None

    @property
    def new_devices(self):
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
            new_devices.extend(self.bootLoaderDevices)

        new_devices = list(set(new_devices))

        return new_devices

    def _do_refresh(self, mountpointToShow=None):
        # block mountpoint selector signal handler for now
        self._initialized = False
        self._clear_current_selector()

        # Make sure we start with a clean slate.
        self._accordion.removeAllPages()

        # Start with buttons disabled, since nothing is selected.
        self._removeButton.set_sensitive(False)
        self._configButton.set_sensitive(False)

        # Now it's time to populate the accordion.
        log.debug("ui: devices=%s", [d.name for d in self._devices])
        log.debug("ui: unused=%s", [d.name for d in self.unusedDevices])
        log.debug("ui: new_devices=%s", [d.name for d in self.new_devices])

        ui_roots = self.__storage.roots[:]

        # If we've not yet run autopart, add an instance of CreateNewPage.  This
        # ensures it's only added once.
        if not self.new_devices:
            page = CreateNewPage(self.translated_new_install_name,
                                 self.on_create_clicked,
                                 partitionsToReuse=bool(ui_roots))
            self._accordion.addPage(page, cb=self.on_page_clicked)

            self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
            self._whenCreateLabel.set_text(
                    _("When you create mount points for your %(name)s %(version)s installation, you'll be able to view their details here.") %\
                            {"name" : productName, "version" : productVersion})
        else:
            swaps = [d for d in self.new_devices if d.format.type == "swap"]
            mounts = dict((d.format.mountpoint, d) for d in self.new_devices
                                if getattr(d.format, "mountpoint", None))

            for device in self.new_devices:
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

            page = Page(root.name)

            for (mountpoint, device) in root.mounts.iteritems():
                if device not in self._devices or \
                   not device.disks or \
                   (root.name != self.translated_new_install_name and not device.format.exists):
                    continue

                selector = page.addSelector(device, self.on_selector_clicked,
                                            mountpoint=mountpoint)
                selector._root = root

            for device in root.swaps:
                if device not in self._devices or \
                   (root.name != self.translated_new_install_name and not device.format.exists):
                    continue

                selector = page.addSelector(device, self.on_selector_clicked)
                selector._root = root

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

        # Anything that doesn't go with an OS we understand?  Put it in the Other box.
        if self.unusedDevices:
            page = UnknownPage(_("Unknown"))

            for u in sorted(self.unusedDevices, key=lambda d: d.name):
                page.addSelector(u, self.on_selector_clicked)

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

        # And then open the first page by default.  Most of the time, this will
        # be fine since it'll be the new installation page.
        self._initialized = True
        firstPage = self._accordion.allPages[0]
        self._accordion.expandPage(firstPage.pageTitle)
        self._show_mountpoint(page=firstPage, mountpoint=mountpointToShow)

        self._applyButton.set_sensitive(False)

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
        if not page.members:
            # remove the CreateNewPage and replace it with a regular Page
            expander = self._accordion._find_by_title(self.translated_new_install_name)
            expander.remove(expander.get_child())

            page = Page(self.translated_new_install_name)
            expander.add(page)

            # also pull in biosboot and prepboot that are on our boot disk
            devices.extend(self.bootLoaderDevices)

        for _device in devices:
            page.addSelector(_device, self.on_selector_clicked)

        page.show_all()

    def _update_selectors(self):
        """ Update all btrfs selectors' size properties. """
        # we're only updating selectors in the new root. problem?
        page = self._accordion._find_by_title(self.translated_new_install_name).get_child()
        for selector in page.members:
            selectorFromDevice(selector._device, selector=selector)

    def _replace_device(self, *args, **kwargs):
        """ Create a replacement device and update the device selector. """
        selector = kwargs.pop("selector", None)
        new_device = self.__storage.factoryDevice(*args, **kwargs)

        self._devices = self.__storage.devices

        if selector:
            # update the selector with the new device and its size
            selectorFromDevice(new_device,
                               selector=selector)

    def _update_device_in_selectors(self, old_device, new_device):
        for s in self._accordion.allSelectors:
            if s._device == old_device:
                selectorFromDevice(new_device, selector=s)

    def _update_all_devices_in_selectors(self):
        for s in self._accordion.allSelectors:
            replaced = False
            for new_device in self.__storage.devices:
                if (s._device.name == new_device.name and
                    s._device.type == new_device.type and
                    s._device.format.type == new_device.format.type):
                    selectorFromDevice(new_device, selector=s)
                    replaced = True
                    break

            if not replaced:
                log.warning("failed to replace device: %s", s._device)

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

        log.info("ui: saving changes to device %s", device.name)

        # TODO: member type (as a device type?)

        # NAME
        old_name = getattr(use_dev, "lvname", use_dev.name)
        name = old_name
        changed_name = False
        if self._nameEntry.get_sensitive():
            name = self._nameEntry.get_text()
            changed_name = (name != old_name)
        else:
            # name entry insensitive means we don't control the name
            name = None

        log.debug("old name: %s", old_name)
        log.debug("new name: %s", name)

        # SIZE
        old_size = device.size
        size = size_from_entry(self._sizeEntry)
        if size:
            size = int(size.convertTo(spec="MB"))
        changed_size = ((use_dev.resizable or not use_dev.exists) and
                        size != int(old_size))
        log.debug("old size: %s", old_size)
        log.debug("new size: %s", size)

        # DEVICE TYPE
        device_type = self._get_current_device_type()
        old_device_type = devicefactory.get_device_type(device)
        changed_device_type = (old_device_type != device_type)
        log.debug("old device type: %s", old_device_type)
        log.debug("new device type: %s", device_type)

        # REFORMAT
        reformat = self._reformatCheckbox.get_active()
        log.debug("reformat: %s", reformat)

        # FS TYPE
        old_fs_type = device.format.type
        fs_type_index = self._fsCombo.get_active()
        fs_type = self._fsCombo.get_model()[fs_type_index][0]
        fs_type_short = getFormat(fs_type).type
        changed_fs_type = (old_fs_type != fs_type_short)
        log.debug("old fs type: %s", old_fs_type)
        log.debug("new fs type: %s", fs_type_short)

        # ENCRYPTION
        old_encrypted = isinstance(device, LUKSDevice)
        encrypted = self._encryptCheckbox.get_active()
        changed_encryption = (old_encrypted != encrypted)
        log.debug("old encryption setting: %s", old_encrypted)
        log.debug("new encryption setting: %s", encrypted)

        # FS LABEL
        label = ""
        if self._labelEntry.get_sensitive():
            label = self._labelEntry.get_text()

        old_label = getattr(device.format, "label", "") or ""
        changed_label = (label != old_label)
        log.debug("old label: %s", old_label)
        log.debug("new_label: %s", label)

        # MOUNTPOINT
        mountpoint = None   # None means format type is not mountable
        if self._mountPointEntry.get_sensitive():
            mountpoint = self._mountPointEntry.get_text()

        old_mountpoint = getattr(device.format, "mountpoint", "") or ""
        log.debug("old mountpoint: %s", old_mountpoint)
        log.debug("new mountpoint: %s", mountpoint or "")
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

        if not old_mountpoint:
            # prevent false positives below when "" != None
            old_mountpoint = None

        changed_mountpoint = (old_mountpoint != mountpoint)

        # RAID LEVEL
        raid_level = selectedRaidLevel(self._raidLevelCombo)
        old_raid_level = get_raid_level(device)
        changed_raid_level = (old_device_type == device_type and
                              device_type in (DEVICE_TYPE_MD,
                                              DEVICE_TYPE_BTRFS) and
                              old_raid_level != raid_level)
        log.debug("old raid level: %s", old_raid_level)
        log.debug("new raid level: %s", raid_level)

        ##
        ## VALIDATION
        ##
        error = None
        if device_type != DEVICE_TYPE_PARTITION and mountpoint == "/boot/efi":
            error = (_("/boot/efi must be on a device of type %s")
                     % _(DEVICE_TEXT_PARTITION))
        elif device_type != DEVICE_TYPE_PARTITION and \
             fs_type_short in partition_only_format_types:
            error = (_("%(fs)s must be on a device of type %(type)s")
                       % {"fs" : fs_type, "type" : _(DEVICE_TEXT_PARTITION)})
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
                error = _(raid_level_not_enough_disks_msg) % \
                        {"level": raid_level,
                         "min" : min_disks,
                         "count": len(self._device_disks)}

        if error:
            self.set_warning(error)
            self.window.show_all()
            self._populate_right_side(selector)
            return

        with ui_storage_logger():
            # create a new factory using the appropriate size and type
            factory = devicefactory.get_device_factory(self.__storage,
                                                      device_type, size,
                                                      disks=device.disks,
                                                      encrypted=encrypted,
                                                      raid_level=raid_level)

        # CONTAINER
        changed_container = False
        old_container_name = None
        container_name = self._device_container_name
        container = factory.get_container()
        old_container_encrypted = False
        old_container_raid_level = None
        old_container = None
        old_container_size = SIZE_POLICY_AUTO
        if not changed_device_type:
            old_container = factory.get_container(device=use_dev)
            if old_container:
                old_container_name = old_container.name
                old_container_encrypted = old_container.encrypted
                old_container_raid_level = get_raid_level(old_container)
                old_container_size = getattr(old_container, "size_policy",
                                                            old_container.size)

            container = factory.get_container(name=container_name)
            if old_container and container_name != old_container.name:
                changed_container = True

        log.debug("old container: %s", old_container_name)
        log.debug("new container: %s", container_name)

        container_encrypted = self._device_container_encrypted
        log.debug("old container encrypted: %s", old_container_encrypted)
        log.debug("new container encrypted: %s", container_encrypted)
        changed_container_encrypted = (container_encrypted != old_container_encrypted)

        container_raid_level = self._device_container_raid_level
        if container_raid_level == "single" and device_type != DEVICE_TYPE_BTRFS:
            container_raid_level = None

        log.debug("old container raid level: %s", old_container_raid_level)
        log.debug("new container raid level: %s", container_raid_level)
        changed_container_raid_level = (old_container_raid_level != container_raid_level)

        container_size = self._device_container_size
        log.debug("old container size request: %s", old_container_size)
        log.debug("new container size request: %s", container_size)
        changed_container_size = (old_container_size != container_size)

        # DISK SET
        old_disks = device.disks
        if hasattr(device, "req_disks") and not device.exists:
            old_disks = device.req_disks

        disks = self._device_disks[:]
        if container and changed_device_type:
            log.debug("overriding disk set with container's")
            disks = container.disks[:]
        changed_disk_set = (set(old_disks) != set(disks))
        log.debug("old disks: %s", [d.name for d in old_disks])
        log.debug("new disks: %s", [d.name for d in disks])

        # XXX prevent multiple raid or encryption layers?

        changed = (changed_name or changed_size or changed_device_type or
                   changed_label or changed_mountpoint or changed_disk_set or
                   changed_encryption or changed_raid_level or
                   changed_fs_type or
                   changed_container or changed_container_encrypted or
                   changed_container_raid_level or changed_container_size)

        if not use_dev.exists:
            if not changed:
                log.debug("nothing changed for new device")
                return

            self.clear_errors()

            #
            # Handle change of device type and change of container
            #
            if changed_device_type or changed_container:
                # remove the current device
                self._destroy_device(device)
                if device in self._devices:
                    # the removal failed. don't continue.
                    log.error("device removal failed")
                    return

                _device = None
                _old_device = None
            else:
                _device = device

            with ui_storage_logger():
                try:
                    self._replace_device(device_type, size, fstype=fs_type,
                                         disks=disks, mountpoint=mountpoint,
                                         label=label, raid_level=raid_level,
                                         encrypted=encrypted, name=name,
                                         container_name=container_name,
                                         container_encrypted=container_encrypted,
                                         container_raid_level=container_raid_level,
                                         container_size=container_size,
                                         device=_device,
                                         selector=selector)
                except StorageError as e:
                    log.error("factoryDevice failed: %s", e)
                    # the factory's error handling has replaced all of the
                    # devices with copies, so update the selectors' devices
                    # accordingly
                    self._update_all_devices_in_selectors()
                    self._error = e
                    self.set_warning(_(device_configuration_error_msg)) 
                    self.window.show_all()

                    if _device is None:
                        # in this case we have removed the old device so we now have
                        # to re-create it
                        try:
                            self._replace_device(old_device_type, device.size,
                                                 disks=old_disks,
                                                 fstype=old_fs_type,
                                                 mountpoint=old_mountpoint,
                                                 label=old_label,
                                                 raid_level=old_raid_level,
                                                 encrypted=old_encrypted,
                                                 name=old_name,
                                                 container_name=old_container_name,
                                                 container_encrypted=old_container_encrypted,
                                                 container_raid_level=old_container_raid_level,
                                                 container_size=old_container_size,
                                                 selector=selector)
                        except StorageError as e:
                            # failed to recover.
                            self.refresh()  # this calls self.clear_errors
                            self._error = e
                            self.set_warning(_(unrecoverable_error_msg))
                            self.window.show_all()
                            return

            self._update_device_in_selectors(device, selector._device)
            self._devices = self.__storage.devices

            # update size props of all btrfs devices' selectors
            self._update_selectors()

            self._updateSpaceDisplay()

            self._populate_right_side(selector)
            log.debug("leaving save_right_side")
            return

        ##
        ## Handle changes to preexisting devices
        ##

        # Handle deactivation of the reformat checkbutton after having committed
        # a reformat.
        if not reformat and (not use_dev.format.exists or
                             not device.format.exists):
            # figure out the existing device and reset it
            if not use_dev.format.exists:
                original_device = use_dev
            else:
                original_device = device

            log.debug("resetting device %s", original_device.name)

            with ui_storage_logger():
                self.__storage.resetDevice(original_device)

        if changed_size and device.resizable:
            # If no size was specified, we just want to grow to
            # the maximum.  But resizeDevice doesn't take None for
            # a value.
            if not size:
                size = device.maxSize

            # And then we need to re-check that the max size is actually
            # different from the current size.
            if size != device.size:
                log.debug("scheduling resize of device %s to %s MB", device.name, size)

                with ui_storage_logger():
                    try:
                        self.__storage.resizeDevice(device, size)
                    except StorageError as e:
                        log.error("failed to schedule device resize: %s", e)
                        device.size = old_size
                        self._error = e
                        self.set_warning(_("Device resize request failed. "
                                           "Click for details."))
                        self.window.show_all()
                    else:
                        log.debug("%r", device)
                        log.debug("new size: %s", device.size)
                        log.debug("target size: %s", device.targetSize)

                        # update the selector's size property
                        for s in self._accordion.allSelectors:
                            if s._device == device:
                                s.size = size_str(device.size)

                # update size props of all btrfs devices' selectors
                self._update_selectors()
                self._updateSpaceDisplay()

        # it's possible that reformat is active but fstype is unchanged, in
        # which case we're not going to schedule another reformat unless
        # encryption got toggled
        do_reformat = (reformat and (changed_encryption or
                                     changed_fs_type or
                                     device.format.exists))
        if do_reformat:
            self.clear_errors()
            #
            # ENCRYPTION
            #
            old_device = None
            if changed_encryption:
                if not encrypted:
                    log.info("removing encryption from %s", device.name)
                    with ui_storage_logger():
                        self.__storage.destroyDevice(device)
                        self._devices.remove(device)
                        old_device = device
                        device = device.slave
                        selector._device = device
                        self._update_device_in_selectors(old_device, device)
                elif encrypted:
                    log.info("applying encryption to %s", device.name)
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
                        self._update_device_in_selectors(old_device, device)

                self._devices = self.__storage.devices

            #
            # FORMATTING
            #
            log.info("scheduling reformat of %s as %s", device.name, fs_type_short)
            with ui_storage_logger():
                old_format = device.format
                new_format = getFormat(fs_type,
                                       mountpoint=mountpoint, label=label,
                                       device=device.path)
                try:
                    self.__storage.formatDevice(device, new_format)
                except StorageError as e:
                    log.error("failed to register device format action: %s", e)
                    device.format = old_format
                    self._error = e
                    self.set_warning(_("Device reformat request failed. "
                                       "Click for details."))
                    self.window.show_all()
                else:
                    # first, remove this selector from any old install page(s)
                    new_selector = None
                    for (page, _selector) in self._accordion.allMembers:
                        if _selector._device in (device, old_device):
                            if page.pageTitle == self.translated_new_install_name:
                                new_selector = _selector
                                continue

                            page.removeSelector(_selector)
                            if not page.members:
                                log.debug("removing empty page %s", page.pageTitle)
                                self._accordion.removePage(page.pageTitle)

                    # either update the existing selector or add a new one
                    if new_selector:
                        selectorFromDevice(device, selector=new_selector)
                    else:
                        self.add_new_selector(device)

        if not do_reformat:
            # Set various attributes that do not require actions.
            if old_label != label and hasattr(device.format, "label") and \
               not device.format.exists:
                self.clear_errors()
                log.debug("updating label on %s to %s", device.name, label)
                device.format.label = label

            if mountpoint and old_mountpoint != mountpoint:
                self.clear_errors()
                log.debug("updating mountpoint of %s to %s", device.name, mountpoint)
                device.format.mountpoint = mountpoint
                if old_mountpoint:
                    selectorFromDevice(device, selector=selector)
                else:
                    # add an entry to the new page but do not remove any entries
                    # from other pages since we haven't altered the filesystem
                    self.add_new_selector(device)

        #
        # NAME
        #
        if changed_name:
            self.clear_errors()
            use_dev._name = name
            new_name = use_dev.name
            log.debug("changing name of %s to %s", old_name, new_name)
            if new_name in self.__storage.names:
                use_dev._name = old_name
                self.set_info(_("Specified name %s already in use.") % new_name)
            else:
                selectorFromDevice(device, selector=selector)

        self._populate_right_side(selector)

    def _raid_level_visible(self, model, itr, user_data):
        device_type = self._get_current_device_type()
        if device_type == DEVICE_TYPE_LVM:
            return model[itr][1]
        elif device_type == DEVICE_TYPE_MD:
            return model[itr][2]
        elif device_type == DEVICE_TYPE_BTRFS:
            return model[itr][3]

    def _populate_raid(self, raid_level):
        """ Set up the raid-specific portion of the device details. """
        device_type = self._get_current_device_type()
        log.debug("populate_raid: %s, %s", device_type, raid_level)

        if device_type == DEVICE_TYPE_MD:
            base_level = "raid1"
        else:
            map(really_hide, [self._raidLevelLabel, self._raidLevelCombo])
            return

        if not raid_level:
            raid_level = base_level

        # Set a default RAID level in the combo.
        for (i, row) in enumerate(self._raidLevelCombo.get_model()):
            if row[0].upper().startswith(raid_level.upper()):
                self._raidLevelCombo.set_active(i)
                break

        map(really_show, [self._raidLevelLabel, self._raidLevelCombo])

    def _get_current_device_type(self):
        device_type_text = self._typeCombo.get_active_text()
        log.info("getting device type for %s", device_type_text)
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
        elif device_type_text == _(DEVICE_TEXT_LVM_THINP):
            device_type = DEVICE_TYPE_LVM_THINP
        else:
            log.error("unknown device type: '%s'", device_type_text)

        return device_type

    def _populate_right_side(self, selector):
        log.debug("populate_right_side: %s", selector._device)

        device = selector._device
        if device.type == "luks/dm-crypt":
            use_dev = device.slave
        else:
            use_dev = device

        if hasattr(use_dev, "req_disks") and not use_dev.exists:
            self._device_disks = use_dev.req_disks[:]
        else:
            self._device_disks = device.disks[:]

        log.debug("updated device_disks to %s", [d.name for d in self._device_disks])

        if hasattr(use_dev, "vg"):
            self._device_container_name = use_dev.vg.name
            self._device_container_raid_level = get_raid_level(use_dev.vg)
            self._device_container_encrypted = use_dev.vg.encrypted
            self._device_container_size = use_dev.vg.size_policy
        elif hasattr(use_dev, "volume"):
            self._device_container_name = use_dev.volume.name
            self._device_container_raid_level = get_raid_level(use_dev.volume)
            self._device_container_encrypted = use_dev.volume.encrypted
            self._device_container_size = use_dev.volume.size_policy
        else:
            self._device_container_name = None
            self._device_container_raid_level = None
            self._device_container_encrypted = False
            self._device_container_size = SIZE_POLICY_AUTO

        log.debug("updated device_container_name to %s", self._device_container_name)
        log.debug("updated device_container_raid_level to %s", self._device_container_raid_level)
        log.debug("updated device_container_encrypted to %s", self._device_container_encrypted)
        log.debug("updated device_container_size to %s", self._device_container_size)

        self._selectedDeviceLabel.set_text(selector.props.name)
        self._selectedDeviceDescLabel.set_text(self._description(selector.props.name))

        device_name = getattr(use_dev, "lvname", use_dev.name)
        self._nameEntry.set_text(device_name)

        self._mountPointEntry.set_text(getattr(device.format, "mountpoint", "") or "")
        fancy_set_sensitive(self._mountPointEntry, device.format.mountable)

        self._labelEntry.set_text(getattr(device.format, "label", "") or "")
        # We could label existing formats that have a labelFsProg if we added an
        # ActionLabelFormat class.
        can_label = (hasattr(device.format, "label") and
                     not device.format.exists and
                     device.format.type != "btrfs")
        fancy_set_sensitive(self._labelEntry, can_label)

        if hasattr(device.format, "label"):
            self._labelEntry.props.has_tooltip = False
        else:
            self._labelEntry.set_tooltip_text(_("This file system does not support labels."))

        self._sizeEntry.set_text(Size(spec="%d MB" % device.size).humanReadable(max_places=None))

        self._reformatCheckbox.set_active(not device.format.exists)
        fancy_set_sensitive(self._reformatCheckbox, not device.protected and
                                                          use_dev.exists and
                                                          not use_dev.type.startswith("btrfs"))

        self._encryptCheckbox.set_active(isinstance(device, LUKSDevice))
        self._encryptCheckbox.set_sensitive(self._reformatCheckbox.get_active())
        ancestors = use_dev.ancestors
        ancestors.remove(use_dev)
        if any(a.format.type == "luks" and a.format.exists for a in ancestors):
            # The encryption checkbutton should not be sensitive if there is
            # existing encryption below the leaf layer.
            self._encryptCheckbox.set_sensitive(False)

        ##
        ## Set up the filesystem type combo.
        ##

        # remove any fs types that aren't supported
        remove_indices = []
        for idx, data in enumerate(self._fsCombo.get_model()):
            fs_type = data[0]
            if fs_type not in self._fs_types:
                remove_indices.insert(0, idx)
                continue

            if fs_type == device.format.name:
                self._fsCombo.set_active(idx)

        for remove_idx in remove_indices:
            self._fsCombo.remove(remove_idx)

        # if the current device has unsupported formatting, add an entry for it
        if device.format.name not in self._fs_types:
            self._fsCombo.append_text(device.format.name)
            self._fsCombo.set_active(len(self._fsCombo.get_model()) - 1)

        # Give them a way to reset to original formatting. Whenever we add a
        # "reformat this" widget this will need revisiting.
        if device.exists and \
           device.format.type != device.originalFormat.type and \
           device.originalFormat.type not in self._fs_types:
            self._fsCombo.append_text(device.originalFormat.name)

        ##
        ## Set up the device type combo.
        ##

        btrfs_pos = None
        btrfs_included = False
        md_pos = None
        md_included = False
        disk_pos = None
        disk_included = False
        for idx, itr in enumerate(self._typeCombo.get_model()):
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
            self._typeCombo.append_text(_(DEVICE_TEXT_MD))
        elif md_included and not include_md:
            remove_indices.append(md_pos)

        # if the format is swap the device type can't be btrfs
        include_btrfs = (use_dev.format.type not in
                            partition_only_format_types + ["swap"])
        if include_btrfs and not btrfs_included:
            self._typeCombo.append_text(_(DEVICE_TEXT_BTRFS))
        elif btrfs_included and not include_btrfs:
            remove_indices.append(btrfs_pos)

        # only include disk if the current device is a disk
        include_disk = use_dev.isDisk
        if include_disk and not disk_included:
            self._typeCombo.append_text(_(DEVICE_TEXT_DISK))
        elif disk_included and not include_disk:
            remove_indices.append(disk_pos)

        remove_indices.sort(reverse=True)
        map(self._typeCombo.remove, remove_indices)

        md_pos = None
        btrfs_pos = None
        partition_pos = None
        lvm_pos = None
        thinp_pos = None
        for idx, itr in enumerate(self._typeCombo.get_model()):
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
            elif itr[0] == _(DEVICE_TEXT_LVM_THINP):
                thinp_pos = idx

        device_type = devicefactory.get_device_type(device)
        raid_level = devicefactory.get_raid_level(device)
        type_index_map = {DEVICE_TYPE_PARTITION: partition_pos,
                          DEVICE_TYPE_BTRFS: btrfs_pos,
                          DEVICE_TYPE_LVM: lvm_pos,
                          DEVICE_TYPE_LVM_THINP: thinp_pos,
                          DEVICE_TYPE_MD: md_pos,
                          DEVICE_TYPE_DISK: disk_pos}

        for _type in self._device_name_dict.iterkeys():
            if _type == device_type:
                self._device_name_dict[_type] = device_name
                continue
            elif _type not in (DEVICE_TYPE_LVM, DEVICE_TYPE_MD, DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM_THINP):
                continue

            swap = (device.format.type == "swap")
            mountpoint = getattr(device.format, "mountpoint", None)

            with ui_storage_logger():
                name = self.__storage.suggestDeviceName(swap=swap,
                                                        mountpoint=mountpoint)

            self._device_name_dict[_type] = name

        self._typeCombo.set_active(type_index_map[device_type])
        fancy_set_sensitive(self._fsCombo, self._reformatCheckbox.get_active() and
                                           device_type != DEVICE_TYPE_BTRFS)

        # you can't change the type of an existing device
        fancy_set_sensitive(self._typeCombo, not use_dev.exists)
        fancy_set_sensitive(self._raidLevelCombo, not use_dev.exists)

        # FIXME: device encryption should be mutually exclusive with container
        # encryption

        # FIXME: device raid should be mutually exclusive with container raid

        # you can't encrypt a btrfs subvolume -- only the volume/container
        # XXX CHECKME: encryption of thin logical volumes is not supported at this time
        if device_type in [DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM_THINP]:
            fancy_set_sensitive(self._encryptCheckbox, False)

        # The size entry is only sensitive for resizable existing devices and
        # new devices that are not btrfs subvolumes.
        # Do this after the device type combo is set since
        # on_device_type_changed doesn't account for device existence.
        fancy_set_sensitive(self._sizeEntry, device.resizable or (not device.exists and device.format.type != "btrfs"))

        if self._sizeEntry.get_sensitive():
            self._sizeEntry.props.has_tooltip = False
        elif device.format.type == "btrfs":
            self._sizeEntry.set_tooltip_text(_("The space available to this mountpoint can be changed by modifying the volume below."))
        else:
            self._sizeEntry.set_tooltip_text(_("This file system may not be resized."))

        self._populate_raid(raid_level)
        self._populate_container(device=use_dev)
        # do this last in case this was set sensitive in on_device_type_changed
        if use_dev.exists:
            fancy_set_sensitive(self._nameEntry, False)

    ###
    ### SIGNAL HANDLERS
    ###

    def on_key_pressed(self, window, event, *args):
        # Handle any keyboard events.  Right now this is just delete for
        # removing an existing mountpoint, but it could include more later.
        if not event or event and event.type != Gdk.EventType.KEY_RELEASE:
            return

        if event.keyval == Gdk.KEY_Delete:
            # But we only want delete to work if you have focused a MountpointSelector,
            # and not just any random widget.  For those, it's likely the user wants
            # to delete a character.
            if isinstance(window.get_focus(), MountpointSelector):
                self._removeButton.emit("clicked")

    def on_back_clicked(self, button):
        # First, save anything from the currently displayed mountpoint.
        self._save_right_side(self._current_selector)

        # And then display the summary screen.  From there, the user will either
        # head back to the hub, or stay on the custom screen.
        self.__storage.devicetree.pruneActions()
        self.__storage.devicetree.sortActions()

        dialog = ActionSummaryDialog(self.data)
        with enlightbox(self.window, dialog.window):
            dialog.refresh(self.__storage.devicetree.findActions())
            rc = dialog.run()

        if rc == 0:
            # Cancel.  Stay on the custom screen.
            return

        # Then if they did anything that resulted in new LUKS devices, we need
        # to prompt for passphrases.
        new_luks = any(d for d in self.__storage.devices
                       if d.format.type == "luks" and not d.format.exists)
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
        log.debug("requested size = %s  ; available space = %s", dialog.size, self._free_space)

        # if no size was entered, request as much of the free space as possible
        if dialog.size is not None and dialog.size.convertTo(spec="mb") < 1:
            size = None
        else:
            size = dialog.size

        fstype = self.storage.getFSType(mountpoint)

        # The encryption setting as applied here means "encrypt leaf devices".
        # If you want "encrypt my VG/PVs" you'll have to either use the autopart
        # button or wait until we have a way to control container-level
        # encryption.
        encrypted = self.data.autopart.encrypted

        # we're doing nothing here to ensure that bootable requests end up on
        # the boot disk, but the weight from platform should take care of this

        if lowerASCII(mountpoint) in ("swap", "biosboot", "prepboot"):
            mountpoint = None

        device_type_from_autopart = {AUTOPART_TYPE_LVM: DEVICE_TYPE_LVM,
                                     AUTOPART_TYPE_LVM_THINP: DEVICE_TYPE_LVM_THINP,
                                     AUTOPART_TYPE_PLAIN: DEVICE_TYPE_PARTITION,
                                     AUTOPART_TYPE_BTRFS: DEVICE_TYPE_BTRFS}
        device_type = device_type_from_autopart[self.data.autopart.type]
        if (device_type != DEVICE_TYPE_PARTITION and
            ((mountpoint and mountpoint.startswith("/boot")) or
             fstype in partition_only_format_types)):
            device_type = DEVICE_TYPE_PARTITION

        # we shouldn't create swap on a thinly provisioned volume
        if fstype == "swap" and device_type == DEVICE_TYPE_LVM_THINP:
            device_type = DEVICE_TYPE_LVM

        # encryption of thinly provisioned volumes isn't supported
        if encrypted and device_type == DEVICE_TYPE_LVM_THINP:
            encrypted = False

        # some devices should never be encrypted
        if ((mountpoint and mountpoint.startswith("/boot")) or
            fstype in partition_only_format_types):
            encrypted = False

        disks = self._clearpartDevices
        if size is not None:
            size = float(size.convertTo(spec="mb"))

        self.clear_errors()

        with ui_storage_logger():
            factory = devicefactory.get_device_factory(self.__storage,
                                                     device_type, size)
            container = factory.get_container()
            kwargs = {}
            if container:
                # don't override user-initiated changes to a defined container
                disks = container.disks
                kwargs = {"container_encrypted": container.encrypted,
                          "container_raid_level": get_raid_level(container),
                          "container_size": getattr(container, "size_policy",
                                                               container.size)}

            try:
                self.__storage.factoryDevice(device_type,
                                         size=size,
                                         fstype=fstype,
                                         mountpoint=mountpoint,
                                         encrypted=encrypted,
                                         disks=disks,
                                         **kwargs)
            except StorageError as e:
                log.error("factoryDevice failed: %s", e)
                log.debug("trying to find an existing container to use")
                container = factory.get_container(allow_existing=True)
                log.debug("found container %s", container)
                if container:
                    # don't override user-initiated changes to a defined container
                    disks = container.disks
                    kwargs = {"container_encrypted": container.encrypted,
                              "container_raid_level": get_raid_level(container),
                              "container_size": getattr(container, "size_policy",
                                                                   container.size)}
                    try:
                        self.__storage.factoryDevice(device_type,
                                                 size=size,
                                                 fstype=fstype,
                                                 mountpoint=mountpoint,
                                                 encrypted=encrypted,
                                                 disks=disks,
                                                 container_name=container.name,
                                                 **kwargs)
                    except StorageError as e2:
                        log.error("factoryDevice failed w/ old container: %s", e2)
                    else:
                        type_str = device_text_map[device_type]
                        self.set_info(_("Added new %(type)s to existing "
                                        "container %(name)s.")
                                        % {"type" : type_str, "name" : container.name})
                        self.window.show_all()
                        e = None

                # the factory's error handling has replaced all of the devices
                # with copies, so update the selectors' devices accordingly
                self._update_all_devices_in_selectors()

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
        if not self._error:
            self._do_refresh(mountpointToShow=mountpoint or fstype)
        else:
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
                log.error("failed to schedule device removal: %s", e)
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
            device_type = devicefactory.get_device_type(device)
        elif hasattr(device, "volume"):
            container = device.volume
            device_type = DEVICE_TYPE_BTRFS

        # adjust container to size of remaining devices, if auto-sized
        if container and not container.exists and \
           self.__storage.devicetree.getChildren(container) and \
           container.size_policy == SIZE_POLICY_AUTO:
            cont_encrypted = container.encrypted
            cont_raid = get_raid_level(container)
            cont_size = container.size_policy
            cont_name = container.name
            with ui_storage_logger():
                factory = devicefactory.get_device_factory(self.__storage,
                                            device_type, 0,
                                            disks=container.disks,
                                            container_name=cont_name,
                                            container_encrypted=cont_encrypted,
                                            container_raid_level=cont_raid,
                                            container_size=cont_size)
                factory.configure()

        # if this device has parents with no other children, remove them too
        for parent in device.parents:
            if parent.kids == 0 and not parent.isDisk:
                self._destroy_device(parent)

    def _show_mountpoint(self, page=None, mountpoint=None):
        if not self._initialized:
            return

        # Make sure there's something displayed on the RHS.  If a page and
        # mountpoint within that page is given, display that.  Otherwise, just
        # default to the first selector available.
        if not page:
            page = self._current_page

        log.debug("show mountpoint: %s", page.pageTitle)
        if not page.members:
            self._clear_current_selector()
            return

        if not mountpoint:
            self.on_selector_clicked(page.members[0])
            return

        for member in page.members:
            if member.get_property("mountpoint").lower() == mountpoint.lower():
                self.on_selector_clicked(member)
                break

    def on_remove_clicked(self, button):
        # Nothing displayed on the RHS?  Nothing to remove.
        if not self._current_selector:
            return

        page = self._current_page
        selector = self._current_selector
        device = self._current_selector._device
        root_name = None
        if selector._root:
            root_name = selector._root.name
        elif page:
            root_name = page.pageTitle

        log.debug("removing device '%s' from page %s", device, root_name)

        if root_name == self.translated_new_install_name:
            if device.exists:
                # This is an existing device that was added to the new page.
                # All we want to do is revert any changes to the device and
                # it will end up back in whatever old pages it came from.
                with ui_storage_logger():
                    self.__storage.resetDevice(device)

                log.debug("updated device: %s", device)
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
                for dev in (s._device for s in page.members):
                    self._destroy_device(dev)
            else:
                self._destroy_device(device)

        log.info("ui: removed device %s", device.name)

        # Now that devices have been removed from the installation root,
        # refreshing the display will have the effect of making them disappear.
        # It's like they never existed.
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
        with enlightbox(self.window, help_window.window):
            help_window.run()

    def on_configure_clicked(self, button):
        selector = self._current_selector
        if not selector:
            return

        device = selector._device
        if device.exists:
            return

        if self._get_current_device_type() in (DEVICE_TYPE_LVM, DEVICE_TYPE_LVM_THINP, DEVICE_TYPE_BTRFS):
            # disk set management happens through container edit on RHS
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
        log.debug("new disks for %s: %s", device.name, [d.name for d in disks])
        if not disks:
            self._error = "No disks selected. Keeping previous disk set."
            self.set_info(self._error)
            self.window.show_all()
            return

        if set(disks) != self._device_disks:
            self._applyButton.set_sensitive(True)

        self._device_disks = disks
        self._populate_raid(selectedRaidLevel(self._raidLevelCombo))

    def run_container_editor(self, container=None, name=None):
        size = 0
        size_policy = self._device_container_size
        if container:
            container_name = container.name
            size = container.size
            size_policy = container.size_policy
        elif name:
            container_name = name
            if name != self._device_container_name:
                # creating a new container -- switch to the default
                size_policy = SIZE_POLICY_AUTO

        dialog = ContainerDialog(self.data,
                                 device_type=self._get_current_device_type(),
                                 name=container_name,
                                 raid_level=self._device_container_raid_level,
                                 encrypted=self._device_container_encrypted,
                                 size_policy=size_policy,
                                 size=size,
                                 disks=self._clearpartDevices,
                                 free=self._currentFreeInfo,
                                 selected=self._device_disks,
                                 exists=getattr(container, "exists", False))

        with enlightbox(self.window, dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc == 0:
            return

        disks = dialog.selected
        name = dialog.name
        log.debug("new disks for %s: %s", name, [d.name for d in disks])
        if not disks:
            self._error = "No disks selected. Not saving changes."
            self.set_info(self._error)
            self.window.show_all()
            return

        log.debug("new container name: %s", name)
        if name != container_name and name in self.__storage.names:
            self._error = _("Volume Group name %s is already in use. Not "
                            "saving changes.") % name
            self.set_info(self._error)
            self.window.show_all()
            return

        if (set(disks) != set(self._device_disks) or
            name != container_name or
            dialog.raid_level != self._device_container_raid_level or
            dialog.encrypted != self._device_container_encrypted or
            dialog.size_policy != self._device_container_size):
            self._applyButton.set_sensitive(True)

        log.debug("new container raid level: %s", dialog.raid_level)
        log.debug("new container encrypted: %s", dialog.encrypted)
        log.debug("new container size: %s", dialog.size_policy)

        self._device_disks = disks
        self._device_container_name = name
        self._device_container_raid_level = dialog.raid_level
        self._device_container_encrypted = dialog.encrypted
        self._device_container_size = dialog.size_policy

    def on_modify_container_clicked(self, button):
        container_name = self._containerCombo.get_active_text()

        container = self.__storage.devicetree.getDeviceByName(container_name)

        # pass the name along with any found vg since we could be modifying a
        # vg that hasn't been instantiated yet
        self.run_container_editor(container=container, name=container_name)

        log.debug("%s -> %s", container_name, self._device_container_name)
        if container_name == self._device_container_name:
            return

        log.debug("renaming container %s to %s", container_name, self._device_container_name)
        if container:
            # btrfs volume name/label does not go in the name list
            if container.name in self.__storage.devicetree.names:
                self.__storage.devicetree.names.remove(container.name)
                self.__storage.devicetree.names.append(self._device_container_name)

            # until there's a setter for btrfs volume name 
            container._name = self._device_container_name
            if container.format.type == "btrfs":
                container.format.label = self._device_container_name

        container_exists = getattr(container, "exists", False)
        for idx, data in enumerate(self._containerCombo.get_model()):
            # we're looking for the original vg name
            if data[0] == container_name:
                self._containerCombo.remove(idx)
                self._containerCombo.insert_text(idx, self._device_container_name)
                self._containerCombo.set_active(idx)
                self._modifyContainerButton.set_sensitive(not container_exists)
                break

        self._update_selectors()

    def on_container_changed(self, combo):
        container_name = combo.get_active_text()
        log.debug("new container selection: %s", container_name)
        if container_name is None:
            return

        if self._device_container_name == container_name:
            return

        device_type = self._get_current_device_type()
        container_type = container_type_names[device_type].lower()
        new_text = _(new_container_text) % {"container_type": container_type}
        if container_name == new_text:
            # run the vg editor dialog with a default name and disk set
            hostname = self.data.network.hostname
            name = self.__storage.suggestContainerName(hostname=hostname)
            self.run_container_editor(name=name)
            for idx, data in enumerate(combo.get_model()):
                if data[0] == new_text:
                    combo.insert_text(idx, self._device_container_name)
                    combo.set_active(idx)   # triggers a call to this method
                    return
        else:
            self._device_container_name = container_name

        container = self.__storage.devicetree.getDeviceByName(self._device_container_name)
        container_exists = getattr(container, "exists", False)    # might not be in the tree

        if container:
            self._device_container_raid_level = get_raid_level(container)
            self._device_container_encrypted = container.encrypted
            self._device_container_size = getattr(container, "size_policy",
                                                             container.size)
        else:
            self._device_container_raid_level = None
            self._device_container_encrypted = self.data.autopart.encrypted
            self._device_container_size = SIZE_POLICY_AUTO

        self._modifyContainerButton.set_sensitive(not container_exists)

    def _save_current_selector(self):
        log.debug("current selector: %s", self._current_selector._device)
        nb_page = self._partitionsNotebook.get_current_page()
        log.debug("notebook page = %s", nb_page)
        if nb_page == NOTEBOOK_DETAILS_PAGE:
            self._save_right_side(self._current_selector)

        self._clear_current_selector()

    def on_selector_clicked(self, selector):
        if not self._initialized:
            return

        # Take care of the previously chosen selector.
        if self._current_selector and self._initialized and \
           self._current_selector != selector:
            self._save_current_selector()
            log.debug("new selector: %s", selector._device)

        no_edit = False
        if selector._device.format.type == "luks" and \
           selector._device.format.exists:
            self._partitionsNotebook.set_current_page(NOTEBOOK_LUKS_PAGE)
            selectedDeviceLabel = self._encryptedDeviceLabel
            selectedDeviceDescLabel = self._encryptedDeviceDescLabel
            no_edit = True
        elif not getattr(selector._device, "complete", True):
            self._partitionsNotebook.set_current_page(NOTEBOOK_INCOMPLETE_PAGE)
            selectedDeviceLabel = self._incompleteDeviceLabel
            selectedDeviceDescLabel = self._incompleteDeviceDescLabel

            if selector._device.type == "mdarray":
                total = selector._device.memberDevices
                missing = total - len(selector._device.parents)
                txt = _("This Software RAID array is missing %(missingMembers)d of %(totalMembers)d member "
                        "partitions. You can remove it or select a different "
                        "device.") % {"missingMembers": missing, "totalMembers": total}
            else:
                total = selector._device.pvCount
                missing = total - len(selector._device.parents)
                txt = _("This LVM Volume Group is missing %(missingPVs)d of %(totalPVs)d physical "
                        "volumes. You can remove it or select a different "
                        "device.") % {"missingPVs": missing, "totalPVs": total}
            self._incompleteDeviceOptionsLabel.set_text(txt)
            no_edit = True
        elif devicefactory.get_device_type(selector._device) is None:
            self._partitionsNotebook.set_current_page(NOTEBOOK_UNEDITABLE_PAGE)
            selectedDeviceLabel = self._uneditableDeviceLabel
            selectedDeviceDescLabel = self._uneditableDeviceDescLabel
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

        self._applyButton.set_sensitive(False)
        self._configButton.set_sensitive(not selector._device.exists and
                                         not selector._device.protected and
                                         devicefactory.get_device_type(selector._device) in (DEVICE_TYPE_PARTITION, DEVICE_TYPE_MD))
        self._removeButton.set_sensitive(not selector._device.protected)
        return True

    def on_page_clicked(self, page, mountpointToShow=None):
        if not self._initialized:
            return

        log.debug("page clicked: %s", page.pageTitle)
        if self._current_selector:
            self._save_current_selector()

        self._show_mountpoint(page=page, mountpoint=mountpointToShow)

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
                log.error("doAutoPartition failed: %s", e)
                self._error = e
                self.set_error(_("No disks selected."))
                self.window.show_all()
            except NotEnoughFreeSpaceError as e:
                # No handling should be required for this.
                log.error("doAutoPartition failed: %s", e)
                self._error = e
                self.set_error(_("Not enough free space on selected disks."))
                self.window.show_all()
            except (StorageError, BootLoaderError) as e:
                log.error("doAutoPartition failed: %s", e)
                self._reset_storage()
                self._error = e
                self.set_error(_("Automatic partitioning failed. Click "
                                 "for details."))
                self.window.show_all()
            else:
                self._devices = self.__storage.devices
                # mark all new containers for automatic size management
                for device in self._devices:
                    if not device.exists and hasattr(device, "size_policy"):
                        device.size_policy = SIZE_POLICY_AUTO
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

        self._encryptCheckbox.set_sensitive(active)
        if self._current_selector:
            device = self._current_selector._device
            if device.type == "luks/dm-crypt":
                device = device.slave

            ancestors = device.ancestors
            ancestors.remove(device)
            if any(a.format.type == "luks" and a.format.exists for a in ancestors):
                # The encryption checkbutton should not be sensitive if there is
                # existing encryption below the leaf layer.
                self._encryptCheckbox.set_sensitive(False)

        # you can't encrypt a btrfs subvolume -- only the volume/container
        device_type = self._get_current_device_type()
        if device_type == DEVICE_TYPE_BTRFS:
            self._encryptCheckbox.set_active(False)

        self._encryptCheckbox.set_sensitive(device_type != DEVICE_TYPE_BTRFS)
        fancy_set_sensitive(self._fsCombo, active)

        # The label entry can only be sensitive if reformat is active and the
        # currently selected filesystem can be labeled.
        label_active = active
        if active:
            fmt = getFormat(self._fsCombo.get_active_text())
            label_active = (active and hasattr(fmt, "label") and
                            fmt.type != "btrfs")

        fancy_set_sensitive(self._labelEntry, label_active)

    def on_fs_type_changed(self, combo):
        if not self._initialized:
            return

        new_type = combo.get_active_text()
        if new_type is None:
            return
        log.debug("fs type changed: %s", new_type)
        fmt = getFormat(new_type)
        # FIXME: can't set a label on an existing format as of now
        label_active = (self._reformatCheckbox.get_active() and
                        hasattr(fmt, "label") and
                        fmt.type != "btrfs")
        fancy_set_sensitive(self._labelEntry, label_active)
        fancy_set_sensitive(self._mountPointEntry, fmt.mountable)

    def _populate_container(self, device=None):
        """ Set up the vg widgets for lvm or hide them for other types. """
        device_type = self._get_current_device_type()
        if device is None:
            if self._current_selector is None:
                return

            device = self._current_selector._device
            if isinstance(device, LUKSDevice):
                device = device.slave

        container_size_policy = SIZE_POLICY_AUTO
        if device_type in (DEVICE_TYPE_LVM, DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM_THINP):
            # set up the vg widgets and then bail out
            if devicefactory.get_device_type(device) == device_type:
                _device = device
            else:
                _device = None

            with ui_storage_logger():
                factory = devicefactory.get_device_factory(self.__storage,
                                                         device_type,
                                                         0)
                container = factory.get_container(device=_device)
                default_container = getattr(container, "name", None)
                if container:
                    container_size_policy = container.size_policy

            container_type_text = container_type_names[device_type]
            self._containerLabel.set_text(container_type_text.title())
            self._containerCombo.remove_all()
            if device_type == DEVICE_TYPE_BTRFS:
                containers = self.__storage.btrfsVolumes
            else:
                containers = self.__storage.vgs

            default_seen = False
            for c in containers:
                self._containerCombo.append_text(c.name)
                if default_container and c.name == default_container:
                    default_seen = True
                    self._containerCombo.set_active(containers.index(c))

            if default_container is None:
                hostname = self.data.network.hostname
                default_container = self.__storage.suggestContainerName(hostname=hostname)

            log.debug("default container is %s", default_container)
            self._device_container_name = default_container
            self._device_container_size = container_size_policy

            if not default_seen:
                self._containerCombo.append_text(default_container)
                self._containerCombo.set_active(len(self._containerCombo.get_model()) - 1)

            self._containerCombo.append_text(_(new_container_text) % {"container_type": container_type_text.lower()})
            self._containerCombo.set_tooltip_text(_(container_tooltip) % {"container_type": container_type_text.lower()})
            if default_container is None:
                self._containerCombo.set_active(len(self._containerCombo.get_model()) - 1)

            map(really_show, [self._containerLabel, self._containerCombo, self._modifyContainerButton])

            # make the combo and button insensitive for existing LVs
            can_change_container = (device is not None and not device.exists)
            fancy_set_sensitive(self._containerCombo, can_change_container)
            container_exists = getattr(container, "exists", False)
            self._modifyContainerButton.set_sensitive(not container_exists)
        else:
            map(really_hide, [self._containerLabel, self._containerCombo, self._modifyContainerButton])

    def on_device_type_changed(self, combo):
        if not self._initialized:
            return

        new_type = self._get_current_device_type()
        log.debug("device_type_changed: %s %s", new_type, combo.get_active_text())
        if new_type is None:
            return

        # if device type is not btrfs we want to make sure btrfs is not in the
        # fstype combo
        include_btrfs = False
        fs_type_sensitive = True

        raid_level = None
        if new_type == DEVICE_TYPE_BTRFS:
            # add btrfs to the fstype combo and lock it in
            test_fmt = getFormat("btrfs")
            include_btrfs = test_fmt.supported and test_fmt.formattable
            fs_type_sensitive = False
            with ui_storage_logger():
                factory = devicefactory.get_device_factory(self.__storage,
                                                         DEVICE_TYPE_BTRFS, 0)
                container = factory.get_container()

            if container:
                raid_level = container.dataLevel or "single"
            else:
                # here I suppose we could alter the default based on disk count
                raid_level = "single"
        elif new_type == DEVICE_TYPE_MD:
            raid_level = "raid1"

        # lvm uses the RHS to set disk set. no foolish minds here.
        exists = self._current_selector and self._current_selector._device.exists
        self._configButton.set_sensitive(not exists and new_type not in (DEVICE_TYPE_LVM, DEVICE_TYPE_LVM_THINP, DEVICE_TYPE_BTRFS))

        # this has to be done before calling populate_raid since it will need
        # the raid level combo to contain the relevant raid levels for the new
        # device type
        self._raidStoreFilter.refilter()

        self._populate_raid(raid_level)
        self._populate_container()

        fancy_set_sensitive(self._nameEntry, new_type in (DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM, DEVICE_TYPE_MD, DEVICE_TYPE_LVM_THINP))
        self._nameEntry.set_text(self._device_name_dict[new_type])
        fancy_set_sensitive(self._sizeEntry, new_type != DEVICE_TYPE_BTRFS)

        # begin btrfs magic
        model = self._fsCombo.get_model()
        btrfs_included = False
        btrfs_pos = None
        for idx, data in enumerate(model):
            if data[0] == "btrfs":
                btrfs_included = True
                btrfs_pos = idx

        active_index = self._fsCombo.get_active()
        fstype = self._fsCombo.get_active_text()
        if btrfs_included and not include_btrfs:
            for i in range(0, len(model)):
                if fstype == "btrfs" and \
                   model[i][0] == self.storage.defaultFSType:
                    active_index = i
                    break
            self._fsCombo.remove(btrfs_pos)
        elif include_btrfs and not btrfs_included:
            self._fsCombo.append_text("btrfs")
            active_index = len(self._fsCombo.get_model()) - 1

        self._fsCombo.set_active(active_index)
        fancy_set_sensitive(self._fsCombo, self._reformatCheckbox.get_active() and
                                           fs_type_sensitive)
        # end btrfs magic

    def clear_errors(self):
        self._error = None
        self.clear_info()

    # This callback is for the button that just resets the UI to anaconda's
    # current understanding of the disk layout.
    def on_reset_clicked(self, *args):
        self.refresh()

    # This callback is for the button that has anaconda go back and rescan the
    # disks to pick up whatever changes the user made outside our control.
    def on_refresh_clicked(self, *args):
        dialog = RefreshDialog(self.data, self.storage)
        ignoreEscape(dialog.window)
        with enlightbox(self.window, dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc == 1:
            # User hit OK on the dialog, indicating they stayed on the dialog
            # until rescanning completed and now needs to go back to the
            # main storage spoke.
            self.skipTo = "StorageSpoke"
        elif rc != 2:
            # User either hit cancel on the dialog or closed it via escape, so
            # there was no rescanning done.
            # NOTE: rc == 2 means the user clicked on the link that takes them
            # back to the hub.
            return

        # Can't use this spoke's on_back_clicked method as that will try to
        # save the right hand side, which is no longer valid.  The user must
        # go back and select their disks all over again since whatever they
        # did on the shell could have changed what disks are available.
        NormalSpoke.on_back_clicked(self, None)

    def on_info_bar_clicked(self, *args):
        log.debug("info bar clicked: %s (%s)", self._error, args)
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
        self._applyButton.set_sensitive(False)

    def on_unlock_clicked(self, button):
        """ try to open the luks device, populate, then call _do_refresh. """
        self.clear_errors()
        device = self._current_selector._device
        log.info("trying to unlock %s...", device.name)
        passphrase = self._passphraseEntry.get_text()
        device.format.passphrase = passphrase
        try:
            device.setup()
            device.format.setup()
        except StorageError as e:
            log.error("failed to unlock %s: %s", device.name, e)
            device.teardown(recursive=True)
            self._error = e
            device.format.passphrase = None
            self._passphraseEntry.set_text("")
            self.set_warning(_("Failed to unlock encrypted block device. "
                               "Click for details"))
            self.window.show_all()
            return

        log.info("unlocked %s, now going to populate devicetree...", device.name)
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
        self._clear_current_selector()
        self._do_refresh()

    def on_value_changed(self, *args):
        self._applyButton.set_sensitive(True)

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
