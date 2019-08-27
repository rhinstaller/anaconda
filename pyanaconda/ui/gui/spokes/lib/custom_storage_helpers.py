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

"""Helper functions and classes for custom partitioning."""
from collections import namedtuple
from contextlib import contextmanager

import functools
from functools import wraps

import logging

from blivet.devicefactory import SIZE_POLICY_AUTO, SIZE_POLICY_MAX, DEVICE_TYPE_LVM, \
    DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM_THINP, DEVICE_TYPE_MD
from blivet.devicefactory import get_supported_raid_levels as get_blivet_supported_raid_levels
from blivet.devicelibs import btrfs, mdraid, raid
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger, get_blivet_logger
from pyanaconda.core.constants import SIZE_UNITS_DEFAULT
from pyanaconda.core.i18n import _, N_, CN_
from pyanaconda.core.util import lowerASCII
from pyanaconda.modules.storage.partitioning.interactive_utils import collect_mount_points, \
    validate_mount_point, validate_raid_level
from pyanaconda.storage.utils import size_from_input
from pyanaconda.ui.helpers import InputCheck
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.helpers import GUIDialogInputCheckHandler
from pyanaconda.ui.gui.utils import fancy_set_sensitive, really_hide, really_show

log = get_module_logger(__name__)

NOTEBOOK_LABEL_PAGE = 0
NOTEBOOK_DETAILS_PAGE = 1
NOTEBOOK_LUKS_PAGE = 2
NOTEBOOK_UNEDITABLE_PAGE = 3
NOTEBOOK_INCOMPLETE_PAGE = 4

NEW_CONTAINER_TEXT = N_("Create a new %(container_type)s ...")
CONTAINER_TOOLTIP = N_("Create or select %(container_type)s")
CONTAINER_DIALOG_TITLE = N_("CONFIGURE %(container_type)s")
CONTAINER_DIALOG_TEXT = N_("Please create a name for this %(container_type)s "
                           "and select at least one disk below.")

ContainerType = namedtuple("ContainerType", ["name", "label"])

CONTAINER_TYPES = {
    DEVICE_TYPE_LVM: ContainerType(
        N_("Volume Group"),
        CN_("GUI|Custom Partitioning|Configure|Devices", "_Volume Group:")),
    DEVICE_TYPE_LVM_THINP: ContainerType(
        N_("Volume Group"),
        CN_("GUI|Custom Partitioning|Configure|Devices", "_Volume Group:")),
    DEVICE_TYPE_BTRFS: ContainerType(
        N_("Volume"),
        CN_("GUI|Custom Partitioning|Configure|Devices", "_Volume:"))
}


def get_size_from_entry(entry, lower_bound=None, units=None):
    """ Get a Size object from an entry field.

        :param lower_bound: lower bound for size returned,
        :type lower_bound: :class:`blivet.size.Size` or NoneType
        :param units: units to use if none obtained from entry
        :type units: str or NoneType
        :returns: a Size object corresponding to the text in the entry field
        :rtype: :class:`blivet.size.Size` or NoneType

        Units default to bytes if no units specified in entry or units.

        Rounds up to lower_bound, if value in entry field corresponds
        to a smaller value. The default for lower_bound is None, yielding
        no rounding.
    """
    size_text = entry.get_text().strip()
    size = size_from_input(size_text, units=units)
    if size is None:
        return None
    if lower_bound is not None and size < lower_bound:
        return lower_bound
    return size


def get_selected_raid_level(raid_level_combo):
    """Interpret the selection of a RAID level combo box.

       :returns: the selected raid level, None if none selected
       :rtype: instance of blivet.devicelibs.raid.RaidLevel or NoneType
    """
    if not raid_level_combo.get_property("visible"):
        # the combo is hidden when raid level isn't applicable
        return None

    itr = raid_level_combo.get_active_iter()
    store = raid_level_combo.get_model()

    if not itr:
        return

    selected_level = store[itr][1]
    if selected_level == "none":
        return None
    else:
        return raid.get_raid_level(selected_level)


def get_selected_raid_level_name(raid_level_combo):
    raid_level = get_selected_raid_level(raid_level_combo)
    return raid_level.name if raid_level else ""


def get_raid_level_selection(raid_level):
    """ Returns a string corresponding to the RAID level.

        :param raid_level: a raid level
        :type raid_level: instance of blivet.devicelibs.raid.RAID or None
        :returns: a string corresponding to this raid level
        :rtype: str
    """
    return raid_level.name if raid_level else "none"


def get_default_raid_level(device_type):
    """ Returns the default RAID level for this device type.

        :param int device_type: an int representing the device_type
        :returns: the default RAID level for this device type or None
        :rtype: blivet.devicelibs.raid.RAIDLevel or NoneType
    """
    if device_type == DEVICE_TYPE_MD:
        return mdraid.raid_levels.raid_level("raid1")

    return None


def get_default_container_raid_level(device_type):
    """ Returns the default RAID level for this device type's container type.

        :param int device_type: an int representing the device_type
        :returns: the default RAID level for this device type's container or None
        :rtype: blivet.devicelibs.raid.RAIDLevel or NoneType
    """
    if device_type == DEVICE_TYPE_BTRFS:
        return btrfs.raid_levels.raid_level("single")

    return None


def memoizer(f):
    """ A simple decorator that memoizes by means of the shared default
        value for cache in the result function.

        :param f: a function of a single argument
        :returns: a memoizing version of f
    """

    @functools.wraps(f)
    def new_func(arg, cache={}):
        # pylint: disable=dangerous-default-value
        if arg in cache:
            return cache[arg]

        result = f(arg)
        cache[arg] = result
        return result

    return new_func


@memoizer
def get_supported_container_raid_levels(device_type):
    """ The raid levels anaconda supports for a container for this
        device_type.

        For LVM, anaconda supports LVM on RAID, but also allows no RAID.

        :param int device_type: one of an enumeration of device types
        :returns: a set of supported raid levels
        :rtype: a set of instances of blivet.devicelibs.raid.RAIDLevel
    """
    if device_type in (DEVICE_TYPE_LVM, DEVICE_TYPE_LVM_THINP):
        supported = set(raid.RAIDLevels(["raid0", "raid1", "raid4", "raid5", "raid6", "raid10"]))
        return get_blivet_supported_raid_levels(DEVICE_TYPE_MD)\
            .intersection(supported)\
            .union({None})

    elif device_type == DEVICE_TYPE_BTRFS:
        supported = set(raid.RAIDLevels(["raid0", "raid1", "raid10", "single"]))
        return get_blivet_supported_raid_levels(DEVICE_TYPE_BTRFS)\
            .intersection(supported)

    return set()


def get_container_type(device_type):
    return CONTAINER_TYPES.get(device_type, ContainerType(N_("container"), CN_(
        "GUI|Custom Partitioning|Configure|Devices", "container")))


@contextmanager
def ui_storage_logger():
    """Context manager that applies the UIStorageFilter for its block"""

    storage_log = get_blivet_logger()
    storage_filter = UIStorageFilter()
    storage_log.addFilter(storage_filter)
    yield
    storage_log.removeFilter(storage_filter)


def ui_storage_logged(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        with ui_storage_logger():
            return func(*args, **kwargs)

    return decorated


class UIStorageFilter(logging.Filter):
    """Logging filter for UI storage events"""

    def filter(self, record):
        record.name = "storage.ui"
        return True


class AddDialog(GUIObject):
    builderObjects = ["addDialog", "mountPointStore", "mountPointCompletion",
                      "mountPointEntryBuffer"]
    mainWidgetName = "addDialog"
    uiFile = "spokes/lib/custom_storage_helpers.glade"

    # If the user enters a smaller size, the GUI changes it to this value
    MIN_SIZE_ENTRY = Size("1 MiB")

    def __init__(self, data, storage):
        super().__init__(data)
        self.storage = storage
        self.mount_points = storage.mountpoints.keys()
        self.size = Size(0)
        self.mount_point = ""
        self._error = False

        store = self.builder.get_object("mountPointStore")
        paths = collect_mount_points()

        for path in paths:
            if path not in self.mount_points:
                store.append([path])

        self.builder.get_object("addMountPointEntry").set_model(store)

        completion = self.builder.get_object("mountPointCompletion")
        completion.set_text_column(0)
        completion.set_popup_completion(True)

        self._warningLabel = self.builder.get_object("mountPointWarningLabel")

    def on_add_confirm_clicked(self, button, *args):
        self.mount_point = self.builder.get_object("addMountPointEntry").get_active_text()

        if lowerASCII(self.mount_point) in ("swap", "biosboot", "prepboot"):
            self._error = None
        else:
            self._error = validate_mount_point(self.mount_point, self.mount_points)

        self._warningLabel.set_text(self._error or "")
        self.window.show_all()
        if self._error:
            return

        self.size = get_size_from_entry(
            self.builder.get_object("addSizeEntry"),
            lower_bound=self.MIN_SIZE_ENTRY,
            units=SIZE_UNITS_DEFAULT
        )
        self.window.destroy()

    def refresh(self):
        super().refresh()
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
        super().__init__(*args, **kwargs)
        self._optional_checkbox = self.builder.get_object("optionalCheckbox")

    @property
    def option_checked(self):
        return self._optional_checkbox.get_active()

    def on_delete_confirm_clicked(self, button, *args):
        self.window.destroy()

    # pylint: disable=arguments-differ
    def refresh(self, mountpoint, device, checkbox_text="", snapshots=False, bootpart=False):
        """ Show confirmation dialog with the optional checkbox. If the
            `checkbox_text` for the checkbox is not set then the checkbox
            will not be showed.

            :param str mountpoint: Mountpoint for device.
            :param str device: Name of the device.
            :param str checkbox_text: Text for checkbox. If nothing set do
                                      not display the checkbox.
            :param bool snapshots: If true warn user he's going to delete snapshots too.
        """
        super().refresh()
        label = self.builder.get_object("confirmLabel")

        if checkbox_text:
            self._optional_checkbox.set_label(checkbox_text)
        else:
            self._optional_checkbox.hide()

        if mountpoint:
            txt = "%s (%s)" % (mountpoint, device)
        else:
            txt = device

        if bootpart:
            label_text = _("%s may be a system boot partition! Deleting it may break other "
                           "operating systems. Are you sure you want to delete it?") % txt
        elif not snapshots:
            label_text = _("Are you sure you want to delete all of the data on %s?") % txt
        else:
            label_text = _("Are you sure you want to delete all of the data on %s, including "
                           "snapshots and/or subvolumes?") % txt

        label.set_text(label_text)

    def run(self):
        return self.window.run()


class DisksDialog(GUIObject):
    builderObjects = ["disks_dialog", "disk_store", "disk_view"]
    mainWidgetName = "disks_dialog"
    uiFile = "spokes/lib/custom_storage_helpers.glade"

    def __init__(self, data, storage, disks, selected):
        super().__init__(data)
        self._disks = disks
        self.selected = selected
        self._store = self.builder.get_object("disk_store")
        # populate the store
        for disk in self._disks:
            self._store.append(["%s (%s)" % (disk.description, disk.serial),
                                str(disk.size),
                                str(storage.get_disk_free_space([disk])),
                                disk.name,
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


class ContainerDialog(GUIObject, GUIDialogInputCheckHandler):
    builderObjects = ["container_dialog", "disk_store", "container_disk_view",
                      "containerRaidStoreFiltered", "containerRaidLevelLabel",
                      "containerRaidLevelCombo", "raidLevelStore",
                      "containerSizeCombo", "containerSizeEntry",
                      "containerSizeLabel", "containerEncryptedCheckbox"]
    mainWidgetName = "container_dialog"
    uiFile = "spokes/lib/custom_storage_helpers.glade"

    # If the user enters a smaller size, the GUI changes it to this value
    MIN_SIZE_ENTRY = Size("1 MiB")

    def __init__(self, data, storage, **kwargs):
        GUIObject.__init__(self, data)
        # these are all absolutely required. not getting them is fatal.
        self.storage = storage
        self._disks = kwargs.pop("disks")
        self.selected = kwargs.pop("selected")[:]
        self.name = kwargs.pop("name") or ""  # make sure it's a string
        self.device_type = kwargs.pop("device_type")

        # these are less critical
        self.raid_level = kwargs.pop("raid_level", None) or None  # not ""
        self.encrypted = kwargs.pop("encrypted", False)
        self.exists = kwargs.pop("exists", False)

        self.size_policy = kwargs.pop("size_policy", SIZE_POLICY_AUTO)
        self.size = kwargs.pop("size", Size(0))

        self._error = None

        self._grab_objects()
        GUIDialogInputCheckHandler.__init__(self, self._save_button)

        # set up the dialog labels with device-type-specific text
        container_type = get_container_type(self.device_type)
        title_text = _(CONTAINER_DIALOG_TITLE) % {"container_type": _(container_type.name).upper()}
        self._title_label.set_text(title_text)

        dialog_text = _(CONTAINER_DIALOG_TEXT) % {"container_type": _(container_type.name).lower()}
        self._dialog_label.set_text(dialog_text)

        # populate the dialog widgets
        self._name_entry.set_text(self.name)

        # populate the store
        for disk in self._disks:
            self._store.append([disk.description,
                                str(disk.size),
                                str(storage.get_disk_free_space([disk])),
                                disk.name,
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

        self._original_size = self.size
        self._original_size_text = self.size.human_readable(max_places=2)
        self._sizeEntry.set_text(self._original_size_text)
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

        # Check that the container name configured is valid
        self.add_check(self._name_entry, self._check_name_entry)

    def _grab_objects(self):
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

        self._save_button = self.builder.get_object("container_save_button")

    def _get_disk_by_id(self, disk_id):
        for disk in self._disks:
            if disk.id == disk_id:
                return disk

    def _save_clicked(self):
        if self.exists:
            return

        model, paths = self._treeview.get_selection().get_selected_rows()

        raid_level = get_selected_raid_level(self._raidLevelCombo)
        if raid_level:
            self._error = validate_raid_level(raid_level, len(paths))

            if self._error:
                self._error_label.set_text(self._error)
                self.window.show_all()
                return

        idx = self._sizeCombo.get_active()
        if idx == 0:
            size = SIZE_POLICY_AUTO
        elif idx == 1:
            size = SIZE_POLICY_MAX
        elif idx == 2:
            if self._original_size_text != self._sizeEntry.get_text():
                size = get_size_from_entry(
                    self._sizeEntry,
                    lower_bound=self.MIN_SIZE_ENTRY,
                    units=SIZE_UNITS_DEFAULT
                )
                if size is None:
                    size = SIZE_POLICY_MAX
            else:
                size = self._original_size

        # now save the changes

        self.selected = []
        for path in paths:
            itr = model.get_iter(path)
            disk_id = model.get_value(itr, 4)
            self.selected.append(self._get_disk_by_id(disk_id))

        self.name = self._name_entry.get_text().strip()
        self.raid_level = raid_level
        self.encrypted = self._encryptCheckbutton.get_active()
        self.size_policy = size

        self._error_label.set_text("")

    def run(self):
        while True:
            self._error = None
            rc = self.window.run()
            if rc == 1:
                # Save clicked and input validation passed, try saving it
                if self.on_ok_clicked():
                    self._save_clicked()

                    # If that failed, try again
                    if self._error:
                        continue
                    else:
                        break
                # Save clicked with invalid input, try again
                else:
                    continue
            else:
                # Cancel or something similar, just exit
                break

        self.window.destroy()
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
        raid_level_str = model[itr][1]
        raid_level = raid.get_raid_level(raid_level_str) if raid_level_str != "none" else None
        return raid_level in get_supported_container_raid_levels(self.device_type)

    def _populate_raid(self):
        """ Set up the raid-specific portion of the device details.

            Hide the RAID level menu if this device type does not support RAID.
            Choose a default RAID level.
        """
        if not get_supported_container_raid_levels(self.device_type):
            for widget in [self._raidLevelLabel, self._raidLevelCombo]:
                really_hide(widget)
            return

        raid_level = self.raid_level or get_default_container_raid_level(self.device_type)
        raid_level_name = get_raid_level_selection(raid_level)

        # Set a default RAID level in the combo.
        for (i, row) in enumerate(self._raidLevelCombo.get_model()):
            log.debug("container dialog: raid level %s", row[1])
            if row[1] == raid_level_name:
                self._raidLevelCombo.set_active(i)
                break

        for widget in [self._raidLevelLabel, self._raidLevelCombo]:
            really_show(widget)
        fancy_set_sensitive(self._raidLevelCombo, not self.exists)

    def _check_name_entry(self, inputcheck):
        container_name = self.get_input(inputcheck.input_obj).strip()

        # Check that the container name is valid
        safename = self.storage.safe_device_name(container_name)
        if container_name != safename:
            return _("Invalid container name")

        return InputCheck.CHECK_OK
