# vim: set fileencoding=utf-8
#
# Copyright (C) 2012-2014  Red Hat, Inc.
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
#                    Vratislav Podzimek <vpodzime@redhat.com>
#

"""Helper functions and classes for custom partitioning."""

__all__ = ["size_from_entry", "populate_mountpoint_store", "validate_label",
           "validate_mountpoint", "selectedRaidLevel", "get_container_type_name",
           "AddDialog", "ConfirmDeleteDialog", "DisksDialog", "ContainerDialog",
           "HelpDialog"]

import re

from pyanaconda.product import productName
from pyanaconda.iutil import lowerASCII
from pyanaconda.storage_utils import size_from_input, get_supported_raid_levels
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import fancy_set_sensitive, really_hide, really_show
from pyanaconda.i18n import _, N_, C_

from blivet.size import Size
from blivet.platform import platform
from blivet.formats import getFormat
from blivet.devicefactory import SIZE_POLICY_AUTO
from blivet.devicefactory import SIZE_POLICY_MAX
from blivet.devicefactory import DEVICE_TYPE_LVM
from blivet.devicefactory import DEVICE_TYPE_MD
from blivet.devicefactory import DEVICE_TYPE_BTRFS
from blivet.devicefactory import DEVICE_TYPE_LVM_THINP
from blivet.devicelibs import mdraid

import logging
log = logging.getLogger("anaconda")

RAID_NOT_ENOUGH_DISKS = N_("The RAID level you have selected (%(level)s) "
                           "requires more disks (%(min)d) than you "
                           "currently have selected (%(count)d).")
EMPTY_NAME_MSG = N_("Please enter a valid name.")

CONTAINER_DIALOG_TITLE = N_("CONFIGURE %(container_type)s")
CONTAINER_DIALOG_TEXT = N_("Please create a name for this %(container_type)s "
                           "and select at least one disk below.")

CONTAINER_TYPE_NAMES = {DEVICE_TYPE_LVM: N_("Volume Group"),
                        DEVICE_TYPE_LVM_THINP: N_("Volume Group"),
                        DEVICE_TYPE_BTRFS: N_("Volume")}

def size_from_entry(entry):
    size_text = entry.get_text().decode("utf-8").strip()
    return size_from_input(size_text)

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

def validate_label(label, fmt):
    """Returns a code indicating either that the given label can be set for
       this filesystem or the reason why it can not.

       In the case where the format can not assign a label, the empty string
       stands for accept the default, but in the case where the format can
       assign a label the empty string represents itself.

       :param str label: The label
       :param DeviceFormat fmt: The device format to label

    """
    if fmt.exists:
        return _("Can not relabel already existing filesystem.")
    if not fmt.labeling():
        if label == "":
            return ""
        else:
            return _("Can not set label on filesystem.")
    if not fmt.labelFormatOK(label):
        return _("Unacceptable label format for filesystem.")
    return ""

def validate_mountpoint(mountpoint, used_mountpoints, strict=True):
    if strict:
        fake_mountpoints = []
    else:
        fake_mountpoints = ["swap", "biosboot", "prepboot"]

    if mountpoint in used_mountpoints:
        return _("That mount point is already in use. Try something else?")
    elif not mountpoint:
        return _("Please enter a valid mountpoint.")
    elif mountpoint.startswith("/dev") or mountpoint.startswith("/proc") or \
         mountpoint.startswith("/sys"):
        return _("That mount point is invalid. Try something else?")
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
        return _("That mount point is invalid. Try something else?")
    else:
        return ""

def selectedRaidLevel(raidLevelCombo):
    """Interpret the selection of a RAID level combo box."""
    if not raidLevelCombo.get_property("visible"):
        # the combo is hidden when raid level isn't applicable
        return None

    itr = raidLevelCombo.get_active_iter()
    store = raidLevelCombo.get_model()

    if not itr:
        return

    selected_level = store[itr][1]
    if selected_level == "none":
        return None
    else:
        return selected_level

def get_container_type_name(device_type):
    return CONTAINER_TYPE_NAMES.get(device_type, _("container"))

class AddDialog(GUIObject):
    builderObjects = ["addDialog", "mountPointStore", "mountPointCompletion", "mountPointEntryBuffer"]
    mainWidgetName = "addDialog"
    uiFile = "spokes/lib/custom_storage_helpers.glade"

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
        self._warningLabel.set_text(self._error)
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
    uiFile = "spokes/lib/custom_storage_helpers.glade"

    def __init__(self, *args, **kwargs):
        GUIObject.__init__(self, *args, **kwargs)
        self._removeAll = self.builder.get_object("removeAllCheckbox")

    @property
    def deleteAll(self):
        return self._removeAll.get_active()

    def on_delete_confirm_clicked(self, button, *args):
        self.window.destroy()

    # pylint: disable=W0221
    def refresh(self, mountpoint, device, rootName, subvols=False):
        GUIObject.refresh(self)
        label = self.builder.get_object("confirmLabel")

        if rootName and "_" in rootName:
            rootName = rootName.replace("_", "__")
        self._removeAll.set_label(
                C_("GUI|Custom Partitioning|Confirm Delete Dialog",
                    "Delete _all other filesystems in the %s root as well.")
                % rootName)
        self._removeAll.set_sensitive(rootName is not None)

        if mountpoint:
            txt = "%s (%s)" % (mountpoint, device)
        else:
            txt = device

        if not subvols:
            label_text = _("Are you sure you want to delete all of the data on %s?") % txt
        else:
            label_text = _("Are you sure you want to delete all of the data on %s, including subvolumes and/or snapshots?") % txt

        label.set_text(label_text)

    def run(self):
        return self.window.run()

class DisksDialog(GUIObject):
    builderObjects = ["disks_dialog", "disk_store", "disk_view"]
    mainWidgetName = "disks_dialog"
    uiFile = "spokes/lib/custom_storage_helpers.glade"

    def __init__(self, *args, **kwargs):
        self._disks = kwargs.pop("disks")
        free = kwargs.pop("free")
        self.selected = kwargs.pop("selected")[:]
        GUIObject.__init__(self, *args, **kwargs)
        self._store = self.builder.get_object("disk_store")
        # populate the store
        for disk in self._disks:
            self._store.append([disk.description,
                                str(disk.size),
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
    uiFile = "spokes/lib/custom_storage_helpers.glade"

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
        self.size = kwargs.pop("size", Size(bytes=0))

        self._error = None
        GUIObject.__init__(self, *args, **kwargs)

        self._grabObjects()

        # set up the dialog labels with device-type-specific text
        container_type = get_container_type_name(self.device_type)
        title_text = _(CONTAINER_DIALOG_TITLE) % {"container_type": container_type.upper()}
        self._title_label.set_text(title_text)

        dialog_text = _(CONTAINER_DIALOG_TEXT) % {"container_type": container_type.lower()}
        self._dialog_label.set_text(dialog_text)

        # populate the dialog widgets
        self._name_entry.set_text(self.name)

        # populate the store
        for disk in self._disks:
            self._store.append([disk.description,
                                str(disk.size),
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

        self._sizeEntry.set_text(self.size.humanReadable(max_places=None))
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
            self._error = _(EMPTY_NAME_MSG)
            self._error_label.set_text(self._error)
            self.window.show_all()
            return

        model, paths = self._treeview.get_selection().get_selected_rows()

        raid_level = selectedRaidLevel(self._raidLevelCombo)
        if raid_level:
            md_level = mdraid.getRaidLevel(raid_level)
            min_disks = md_level.min_members
            if len(paths) < min_disks:
                self._error = (_(RAID_NOT_ENOUGH_DISKS) % {"level" : md_level,
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
            if size is None:
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
        raid_level = model[itr][1]

        # This is weird because for lvm's container-wide raid we use md.
        if self.device_type in (DEVICE_TYPE_LVM, DEVICE_TYPE_LVM_THINP):
            return raid_level in get_supported_raid_levels(DEVICE_TYPE_MD)
        else:
            return raid_level in get_supported_raid_levels(self.device_type)

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
    uiFile = "spokes/lib/custom_storage_helpers.glade"

    def run(self):
        help_text = _(help_text_template) % {"productName": productName}
        help_buffer = self.builder.get_object("help_text_buffer")
        help_buffer.set_text(_(help_text))
        self.window.run()

    def on_close(self, button):
        self.window.destroy()

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
