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
from collections import namedtuple

from dasbus.structure import get_fields

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import C_, CN_, N_, _
from pyanaconda.core.storage import (
    DEVICE_TYPE_BTRFS,
    DEVICE_TYPE_LVM,
    DEVICE_TYPE_LVM_THINP,
    DEVICE_TYPE_MD,
    PROTECTED_FORMAT_TYPES,
    SIZE_POLICY_AUTO,
    SIZE_POLICY_MAX,
    Size,
)
from pyanaconda.core.string import lower_ascii
from pyanaconda.modules.common.structures.device_factory import (
    DeviceFactoryPermissions,
    DeviceFactoryRequest,
)
from pyanaconda.modules.common.structures.storage import DeviceData, DeviceFormatData
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.helpers import GUIDialogInputCheckHandler
from pyanaconda.ui.gui.utils import fancy_set_sensitive, really_hide, really_show
from pyanaconda.ui.helpers import InputCheck
from pyanaconda.ui.lib.storage import size_from_input

log = get_module_logger(__name__)

# Default to these units when reading user input when no units given
SIZE_UNITS_DEFAULT = "MiB"

# If the user enters a smaller size, the UI changes it to this value.
MIN_SIZE_ENTRY = Size("1 MiB")

# If the user enters a larger size, the UI changes it to this value.
MAX_SIZE_ENTRY = Size(2**64 - 1)

# If the user enters a larger size, the UI changes it to this value.
MAX_SIZE_POLICY_ENTRY = Size(2**63 - 1)

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
DESIRED_CAPACITY_HINT = N_(
    "Specify the Desired Capacity in whole or decimal numbers, with an appropriate unit.\n\n"
    "Spaces separating digit groups are not allowed. Units consist of a decimal or binary "
    "prefix, and optionally the letter B. Letter case does not matter for units. The default "
    "unit used when units are left out is MiB.\n\n"
    "Examples of valid input:\n"
    "'100 GiB' = 100 gibibytes\n"
    "'512m' = 512 megabytes\n"
    "'123456789' = 123 terabytes and a bit less than a half\n"
)

DESIRED_CAPACITY_ERROR = DESIRED_CAPACITY_HINT

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


def generate_request_description(request, original=None):
    """Generate a description of a device factory request.

    :param request: a device factory request
    :param original: an original device factory request or None
    :return: a string with the description
    """
    attributes = []
    original = original or request

    if not isinstance(request, DeviceFactoryRequest) \
            or not isinstance(original, DeviceFactoryRequest):
        raise ValueError("Not instances of DeviceFactoryRequest")

    for name, field in get_fields(request).items():
        new_value = field.get_data(request)
        old_value = field.get_data(original)

        if new_value == old_value:
            attribute = "{} = {}".format(
                name, repr(new_value)
            )
        else:
            attribute = "{} = {} -> {}".format(
                name, repr(old_value), repr(new_value)
            )

        attributes.append(attribute)

    return "\n".join(["{"] + attributes + ["}"])


def get_size_from_entry(entry, lower_bound=MIN_SIZE_ENTRY, upper_bound=MAX_SIZE_ENTRY,
                        units=SIZE_UNITS_DEFAULT):
    """ Get a Size object from an entry field.

        :param entry: an entry field with a specified size
        :param lower_bound: lower bound for size returned,
        :type lower_bound: :class:`blivet.size.Size` or NoneType
        :param upper_bound: upper bound for size returned,
        :type upper_bound: :class:`blivet.size.Size` or NoneType
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

    if upper_bound is not None and size > upper_bound:
        return upper_bound

    return size


def get_selected_raid_level(raid_level_combo):
    """Interpret the selection of a RAID level combo box.

    :return str: the selected raid level, an empty string if none selected
    """
    if not raid_level_combo.get_property("visible"):
        # the combo is hidden when raid level isn't applicable
        return ""

    itr = raid_level_combo.get_active_iter()
    store = raid_level_combo.get_model()

    if not itr:
        return ""

    selected_level = store[itr][1]
    return selected_level


def get_default_raid_level(device_type):
    """Returns the default RAID level for this device type.

    :param int device_type: an int representing the device_type
    :return str: the default RAID level for this device type or an empty string
    """
    if device_type == DEVICE_TYPE_MD:
        return "raid1"

    return ""


def get_supported_device_raid_levels(device_tree, device_type):
    """Get RAID levels supported for the given device type.

    It supports any RAID levels that it expects to support and that blivet
    supports for the given device type.

    Since anaconda only ever allows the user to choose RAID levels for
    device type DEVICE_TYPE_MD, hiding the RAID menu for all other device
    types, the function only returns a non-empty set for this device type.
    If this changes, then so should this function, but at this time it
    is not clear what RAID levels should be offered for other device types.

    :param device_tree: a proxy of a device tree
    :param int device_type: one of an enumeration of device types
    :return: a set of supported raid levels
    :rtype: a set of strings
    """
    if device_type == DEVICE_TYPE_MD:
        supported = {"raid0", "raid1", "raid4", "raid5", "raid6", "raid10"}
        levels = set(device_tree.GetSupportedRaidLevels(DEVICE_TYPE_MD))
        return levels.intersection(supported)

    return set()


def get_supported_container_raid_levels(device_tree, device_type):
    """The raid levels anaconda supports for a container for this device_type.

    For LVM, anaconda supports LVM on RAID, but also allows no RAID.

    :param device_tree: a proxy of a device tree
    :param int device_type: one of an enumeration of device types
    :return: a set of supported raid levels
    :rtype: a set of strings
    """
    if device_type in (DEVICE_TYPE_LVM, DEVICE_TYPE_LVM_THINP):
        supported = {"raid0", "raid1", "raid4", "raid5", "raid6", "raid10"}
        levels = set(device_tree.GetSupportedRaidLevels(DEVICE_TYPE_MD))
        return levels.intersection(supported).union({""})

    if device_type == DEVICE_TYPE_BTRFS:
        supported = {"raid0", "raid1", "raid10", "single"}
        levels = set(device_tree.GetSupportedRaidLevels(DEVICE_TYPE_BTRFS))
        return levels.intersection(supported)

    return set()


def get_container_type(device_type):
    return CONTAINER_TYPES.get(device_type, ContainerType(N_("container"), CN_(
        "GUI|Custom Partitioning|Configure|Devices", "container")))


class AddDialog(GUIObject):
    builderObjects = ["addDialog", "mountPointStore", "mountPointCompletion",
                      "mountPointEntryBuffer"]
    mainWidgetName = "addDialog"
    uiFile = "spokes/lib/custom_storage_helpers.glade"

    def __init__(self, data, device_tree):
        super().__init__(data)
        self._device_tree = device_tree
        self._size = Size(0)
        self._mount_point = ""
        self._error = ""

        self._warning_label = self.builder.get_object("mountPointWarningLabel")

        self._size_entry = self.builder.get_object("addSizeEntry")
        self._size_entry.set_tooltip_text(DESIRED_CAPACITY_HINT)

        self._populate_mount_points()

    @property
    def mount_point(self):
        """The requested mount point."""
        return self._mount_point

    @property
    def size(self):
        """The requested size."""
        return self._size

    def _populate_mount_points(self):
        mount_points = self._device_tree.CollectUnusedMountPoints()
        mount_point_store = self.builder.get_object("mountPointStore")

        for path in mount_points:
            mount_point_store.append([path])

        entry = self.builder.get_object("addMountPointEntry")
        entry.set_model(mount_point_store)

        completion = self.builder.get_object("mountPointCompletion")
        completion.set_text_column(0)
        completion.set_popup_completion(True)

    def on_add_confirm_clicked(self, button, *args):
        self._error = ""
        self._set_mount_point()
        self._set_size()

        self._warning_label.set_text(self._error)
        self.window.show_all()

        if not self._error:
            self.window.destroy()

    def _set_mount_point(self):
        self._mount_point = self.builder.get_object("addMountPointEntry").get_active_text()

        if lower_ascii(self._mount_point) in ("swap", "biosboot", "prepboot"):
            return

        report = ValidationReport.from_structure(
            self._device_tree.ValidateMountPoint(self._mount_point)
        )
        self._error = " ".join(report.get_messages())

    def _set_size(self):
        self._size = get_size_from_entry(self._size_entry) or Size(0)

    def refresh(self):
        super().refresh()
        self._warning_label.set_text("")

    def run(self):
        while True:
            self._error = ""
            rc = self.window.run()
            if not self._error:
                return rc


class ConfirmDeleteDialog(GUIObject):
    builderObjects = ["confirmDeleteDialog"]
    mainWidgetName = "confirmDeleteDialog"
    uiFile = "spokes/lib/custom_storage_helpers.glade"

    def __init__(self, data, device_tree, root_name, device_name, is_multiselection):
        super().__init__(data)
        self._device_tree = device_tree
        self._root_name = root_name
        self._device_name = device_name
        self._is_multiselection = is_multiselection

        self._label = self.builder.get_object("confirmLabel")
        self._label.set_text(self._get_label_text())

        self._optional_checkbox = self.builder.get_object("optionalCheckbox")
        self._optional_checkbox.set_label(self._get_checkbox_text())

        if not self._optional_checkbox.get_label():
            self._optional_checkbox.hide()

    @property
    def option_checked(self):
        return self._optional_checkbox.get_active()

    def on_delete_confirm_clicked(self, button, *args):
        self.window.destroy()

    def _get_checkbox_text(self):
        root_name = self._root_name

        if root_name and "_" in root_name:
            root_name = root_name.replace("_", "__")

        if self._is_multiselection:
            return C_(
                "GUI|Custom Partitioning|Confirm Delete Dialog",
                "Do _not show this dialog for other selected file systems."
            )

        if root_name:
            return C_(
                "GUI|Custom Partitioning|Confirm Delete Dialog",
                "Delete _all file systems which are only used by {}."
            ).format(root_name)

        return None

    def _get_label_text(self):
        device_data = DeviceData.from_structure(
            self._device_tree.GetDeviceData(self._device_name)
        )

        format_data = DeviceFormatData.from_structure(
            self._device_tree.GetFormatData(self._device_name)
        )
        device_name = self._device_name
        mount_point = format_data.attrs.get("mount-point", "")

        if mount_point:
            device_name = "{} ({})".format(mount_point, self._device_name)

        if format_data.type in PROTECTED_FORMAT_TYPES:
            return _(
                "{} may be a system boot partition! Deleting it may break "
                "other operating systems. Are you sure you want to delete it?"
            ).format(device_name)

        if device_data.type == "btrfs" and device_data.children:
            return _(
                "Are you sure you want to delete all of the data on {}, including subvolumes?"
            ).format(device_name)

        if device_data.type == "lvmthinlv" and device_data.children:
            return _(
                "Are you sure you want to delete all of the data on {}, including snapshots?"
            ).format(device_name)

        return _("Are you sure you want to delete all of the data on {}?").format(device_name)

    def run(self):
        return self.window.run()


class DisksDialog(GUIObject):
    builderObjects = ["disks_dialog", "disk_store", "disk_view"]
    mainWidgetName = "disks_dialog"
    uiFile = "spokes/lib/custom_storage_helpers.glade"

    def __init__(self, data, device_tree, disks, selected_disks, is_md):
        super().__init__(data)
        self._device_tree = device_tree
        self._selected_disks = selected_disks
        self._disks = disks
        self.is_md = is_md
        self.instruction_label = self.builder.get_object("disk_selection_label")
        self._store = self.builder.get_object("disk_store")
        self._view = self.builder.get_object("disk_view")
        self._populate_disks()
        self._select_disks()
        self._view.set_tooltip_column(0)
        self._set_instruction_label()

    @property
    def selected_disks(self):
        """Selected disks."""
        return self._selected_disks

    def _set_instruction_label(self):
        if self.is_md:
            self.instruction_label.set_text(_("Select all of the drives you would like the "
                                              "mount point to be created on."))
        else:
            self.instruction_label.set_text(_("Select a drive for the mount point to be created on. "
                                              "If you select multiple, only 1 drive will be used."))

    def _populate_disks(self):
        for device_name in self._disks:
            device_data = DeviceData.from_structure(
                self._device_tree.GetDeviceData(device_name)
            )
            device_free_space = self._device_tree.GetDiskFreeSpace(
                [device_name]
            )
            self._store.append([
                "{} ({})".format(
                    device_data.description,
                    device_data.attrs.get("serial", "")
                ),
                str(Size(device_data.size)),
                str(Size(device_free_space)),
                device_name
            ])

    def _select_disks(self):
        model = self._view.get_model()
        itr = model.get_iter_first()
        selection = self._view.get_selection()

        while itr:
            device_name = model.get_value(itr, 3)
            if device_name in self._selected_disks:
                selection.select_iter(itr)

            itr = model.iter_next(itr)

    def on_cancel_clicked(self, button):
        self.window.destroy()

    def on_select_clicked(self, button):
        treeview = self.builder.get_object("disk_view")
        model, paths = treeview.get_selection().get_selected_rows()
        self._selected_disks = []

        for path in paths:
            itr = model.get_iter(path)
            device_name = model.get_value(itr, 3)
            self._selected_disks.append(device_name)

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

    def __init__(self, data, device_tree, request: DeviceFactoryRequest,
                 permissions: DeviceFactoryPermissions, disks, names):
        GUIObject.__init__(self, data)
        self._device_tree = device_tree
        self._disks = disks
        self._request = request
        self._permissions = permissions
        self._original_name = request.container_name
        self._container_names = names
        self._error = ""

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

        GUIDialogInputCheckHandler.__init__(self, self._save_button)

        self._supported_raid_levels = get_supported_container_raid_levels(
            self._device_tree, self._request.device_type
        )

        self._set_labels()
        self._populate_disks()
        self._select_disks()
        self._populate_raid()
        self._set_name()
        self._set_size()
        self._set_encryption()

    def _set_labels(self):
        container_type = get_container_type(self._request.device_type)
        title_text = _(CONTAINER_DIALOG_TITLE) % {
            "container_type": _(container_type.name).upper()
        }
        self._title_label.set_text(title_text)

        dialog_text = _(CONTAINER_DIALOG_TEXT) % {
            "container_type": _(container_type.name).lower()
        }
        self._dialog_label.set_text(dialog_text)

    def _populate_disks(self):
        for device_name in self._disks:
            device_data = DeviceData.from_structure(
                self._device_tree.GetDeviceData(device_name)
            )
            device_free_space = self._device_tree.GetDiskFreeSpace(
                [device_name]
            )
            self._store.append([
                "{} ({})".format(
                    device_data.description,
                    device_data.attrs.get("serial", "")
                ),
                str(Size(device_data.size)),
                str(Size(device_free_space)),
                device_name
            ])

    def _select_disks(self):
        model = self._treeview.get_model()
        itr = model.get_iter_first()
        selection = self._treeview.get_selection()

        while itr:
            device_name = model.get_value(itr, 3)
            if device_name in self._request.disks:
                selection.select_iter(itr)

            itr = model.iter_next(itr)

        if not self._permissions.can_modify_container():
            self._treeview.set_sensitive(False)

    def _populate_raid(self):
        """Set up the raid-specific portion of the device details.

        Hide the RAID level menu if this device type does not support RAID.
        Choose a default RAID level.
        """
        self._raidStoreFilter.set_visible_func(self._raid_level_visible)
        self._raidStoreFilter.refilter()

        if not self._supported_raid_levels:
            for widget in [self._raidLevelLabel, self._raidLevelCombo]:
                really_hide(widget)
            return

        raid_level = self._request.container_raid_level

        for (i, row) in enumerate(self._raidLevelCombo.get_model()):
            if row[1] == raid_level:
                self._raidLevelCombo.set_active(i)
                break

        for widget in [self._raidLevelLabel, self._raidLevelCombo]:
            really_show(widget)

        fancy_set_sensitive(self._raidLevelCombo, self._permissions.container_raid_level)

    def _raid_level_visible(self, model, itr, user_data):
        raid_level = model[itr][1]
        return raid_level in self._supported_raid_levels

    def _set_name(self):
        self._name_entry.set_text(self._request.container_name)
        self.add_check(self._name_entry, self._check_name_entry)

        if not self._permissions.container_name:
            fancy_set_sensitive(self._name_entry, False)

    def _check_name_entry(self, inputcheck):
        container_name = self.get_input(inputcheck.input_obj).strip()

        if container_name == self._original_name:
            return InputCheck.CHECK_OK

        if container_name in self._container_names:
            return _("Name is already in use.")

        report = ValidationReport.from_structure(
            self._device_tree.ValidateContainerName(container_name)
        )

        if not report.is_valid():
            return " ".join(report.get_messages())

        return InputCheck.CHECK_OK

    def _set_size(self):
        if self._request.container_size_policy == SIZE_POLICY_AUTO:
            self._sizeCombo.set_active(0)
            self._sizeEntry.set_text("")
        elif self._request.container_size_policy == SIZE_POLICY_MAX:
            self._sizeCombo.set_active(1)
            self._sizeEntry.set_text("")
        else:
            self._sizeCombo.set_active(2)
            size = Size(self._request.container_size_policy)
            self._sizeEntry.set_text(size.human_readable(max_places=2))

        if not self._permissions.container_size_policy:
            fancy_set_sensitive(self._sizeCombo, False)
            self._sizeEntry.set_sensitive(False)

    def _set_encryption(self):
        self._encryptCheckbutton.set_active(self._request.container_encrypted)

        if not self._permissions.container_encrypted:
            fancy_set_sensitive(self._encryptCheckbutton, False)

    def run(self):
        while True:
            self._error = ""
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

    def _save_clicked(self):
        if not self._permissions.can_modify_container():
            return

        if not self._validate_disks():
            return

        if not self._validate_raid_level():
            return

        self._request.disks = self._get_disks()
        self._request.container_name = self._name_entry.get_text().strip()
        self._request.container_encrypted = self._encryptCheckbutton.get_active()
        self._request.container_size_policy = self._get_size_policy()
        self._request.container_raid_level = get_selected_raid_level(self._raidLevelCombo)
        self._error_label.set_text("")

    def _validate_disks(self):
        if not self._get_disks():
            self._error = _("No disks selected.")
            self._error_label.set_text(self._error)
            self.window.show_all()
            return False

        return True

    def _validate_raid_level(self):
        raid_level = get_selected_raid_level(self._raidLevelCombo)
        self._error = ""

        if raid_level:
            paths = self._treeview.get_selection().get_selected_rows()[1]
            report = ValidationReport.from_structure(
                self._device_tree.ValidateRaidLevel(raid_level, len(paths))
            )

            if not report.is_valid():
                self._error = " ".join(report.get_messages())
                self._error_label.set_text(self._error)
                self.window.show_all()
                return False

        return True

    def _get_disks(self):
        model, paths = self._treeview.get_selection().get_selected_rows()
        disks = []

        for path in paths:
            itr = model.get_iter(path)
            device_name = model.get_value(itr, 3)
            disks.append(device_name)

        return disks

    def _get_size_policy(self):
        idx = self._sizeCombo.get_active()

        if idx == 0:
            return SIZE_POLICY_AUTO

        if idx == 1:
            return SIZE_POLICY_MAX

        original_size = Size(self._request.container_size_policy)
        original_entry = original_size.human_readable(max_places=2)

        if self._sizeEntry.get_text() == original_entry:
            return self._request.container_size_policy

        size = get_size_from_entry(self._sizeEntry, upper_bound=MAX_SIZE_POLICY_ENTRY)

        if size is None:
            return SIZE_POLICY_MAX

        return size.get_bytes()

    def on_size_changed(self, combo):
        active_index = combo.get_active()
        if active_index == 0:
            self._sizeEntry.set_sensitive(False)
        elif active_index == 1:
            self._sizeEntry.set_sensitive(False)
        else:
            self._sizeEntry.set_sensitive(True)
