# Text storage configuration spoke classes
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
from collections import OrderedDict

from blivet.size import Size
from simpleline.render.adv_widgets import YesNoDialog
from simpleline.render.containers import ListColumnContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import CheckboxWidget, EntryWidget, TextWidget

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    BOOTLOADER_LOCATION_MBR,
    CLEAR_PARTITIONS_ALL,
    CLEAR_PARTITIONS_DEFAULT,
    CLEAR_PARTITIONS_LINUX,
    CLEAR_PARTITIONS_NONE,
    PARTITIONING_METHOD_AUTOMATIC,
    PARTITIONING_METHOD_MANUAL,
    PASSWORD_POLICY_LUKS,
    PAYLOAD_STATUS_PROBING_STORAGE,
    THREAD_STORAGE,
    THREAD_STORAGE_WATCHER,
    WARNING_NO_DISKS_DETECTED,
    WARNING_NO_DISKS_SELECTED,
    SecretType,
)
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.storage import get_supported_autopart_choices
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import (
    BOOTLOADER,
    DEVICE_TREE,
    DISK_INITIALIZATION,
    DISK_SELECTION,
)
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.partitioning import (
    MountPointRequest,
    PartitioningRequest,
)
from pyanaconda.modules.common.structures.storage import DeviceData, DeviceFormatData
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.threading import AnacondaThread, threadMgr
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.lib.format_dasd import DasdFormatting
from pyanaconda.ui.lib.storage import (
    apply_disk_selection,
    apply_partitioning,
    create_partitioning,
    filter_disks_by_names,
    find_partitioning,
    get_disks_summary,
    is_passphrase_required,
    reset_storage,
    select_default_disks,
    set_required_passphrase,
)
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import Dialog, PasswordDialog

log = get_module_logger(__name__)

__all__ = ["StorageSpoke"]

# TRANSLATORS: 's' to rescan devices
PROMPT_SCAN_DESCRIPTION = N_("to rescan devices")
PROMPT_SCAN_KEY = 's'

CLEARALL = N_("Use All Space")
CLEARLINUX = N_("Replace Existing Linux system(s)")
CLEARNONE = N_("Use Free Space")

INIT_MODES = {CLEARALL: CLEAR_PARTITIONS_ALL, CLEARLINUX: CLEAR_PARTITIONS_LINUX,
              CLEARNONE: CLEAR_PARTITIONS_NONE}


class StorageSpoke(NormalTUISpoke):
    """Storage spoke where users proceed to customize storage features such
       as disk selection, partitioning, and fs type.

       .. inheritance-diagram:: StorageSpoke
          :parts: 3
    """
    category = SystemCategory

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "storage-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Don't run the storage spoke on dir installations."""
        if not NormalTUISpoke.should_run(environment, data):
            return False

        return not conf.target.is_directory

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self.title = N_("Installation Destination")
        self._container = None
        self._ready = False
        self._select_all = False

        self._storage_module = STORAGE.get_proxy()
        self._device_tree = STORAGE.get_proxy(DEVICE_TREE)
        self._bootloader_module = STORAGE.get_proxy(BOOTLOADER)
        self._disk_init_module = STORAGE.get_proxy(DISK_INITIALIZATION)
        self._disk_select_module = STORAGE.get_proxy(DISK_SELECTION)

        self._available_disks = []
        self._selected_disks = []

        # Is the partitioning already configured?
        self._is_preconfigured = bool(self._storage_module.CreatedPartitioning)

        # Find a partitioning to use.
        self._partitioning = find_partitioning()

        self.errors = []
        self.warnings = []

    @property
    def completed(self):
        return self.ready and not self.errors and self._device_tree.GetRootDevice()

    @property
    def ready(self):
        # By default, the storage spoke is not ready.  We have to wait until
        # storageInitialize is done.
        return self._ready \
            and not threadMgr.get(THREAD_STORAGE) \
            and not threadMgr.get(THREAD_STORAGE_WATCHER)

    @property
    def mandatory(self):
        return True

    @property
    def status(self):
        """ A short string describing the current status of storage setup. """
        if not self.ready:
            return _("Processing...")
        elif flags.automatedInstall and not self._device_tree.GetRootDevice():
            return _("Kickstart insufficient")
        elif not self._disk_select_module.SelectedDisks:
            return _("No disks selected")
        if self.errors:
            return _("Error checking storage configuration")
        elif self.warnings:
            return _("Warning checking storage configuration")
        elif self._partitioning.PartitioningMethod == PARTITIONING_METHOD_AUTOMATIC:
            return _("Automatic partitioning selected")
        else:
            return _("Custom partitioning selected")

    def _update_disk_list(self, name):
        """ Update self.selected_disks based on the selection."""
        # if the disk isn't already selected, select it.
        if name not in self._selected_disks:
            self._selected_disks.append(name)
        # If the disk is already selected, deselect it.
        elif name in self._selected_disks:
            self._selected_disks.remove(name)

    def _update_summary(self):
        """ Update the summary based on the UI. """
        # Get the summary message.
        if not self._available_disks:
            summary = _(WARNING_NO_DISKS_DETECTED)
        elif not self._selected_disks:
            summary = _(WARNING_NO_DISKS_SELECTED)
        else:
            disks = filter_disks_by_names(self._available_disks, self._selected_disks)
            summary = get_disks_summary(disks)

        # Append storage errors to the summary
        if self.errors or self.warnings:
            summary = summary + "\n" + "\n".join(self.errors or self.warnings)

        return summary

    def setup(self, args=None):
        """Set up the spoke right before it is used."""
        super().setup(args)

        # Join the initialization thread to block on it
        # This print is foul.  Need a better message display
        print(_(PAYLOAD_STATUS_PROBING_STORAGE))
        threadMgr.wait(THREAD_STORAGE_WATCHER)

        self._available_disks = self._disk_select_module.GetUsableDisks()
        self._selected_disks = self._disk_select_module.SelectedDisks

        # Get the available selected disks.
        self._selected_disks = filter_disks_by_names(self._available_disks, self._selected_disks)

        return True

    def refresh(self, args=None):
        """Prepare the content of the screen."""
        super().refresh(args)
        threadMgr.wait(THREAD_STORAGE_WATCHER)

        # Get the available partitioning.
        object_path = self._storage_module.CreatedPartitioning[-1]
        self._partitioning = STORAGE.get_proxy(object_path)

        # Create a new container.
        self._container = ListColumnContainer(1, spacing=1)

        # loop through the disks and present them.
        for disk_name in self._available_disks:
            disk_info = self._format_disk_info(disk_name)
            c = CheckboxWidget(title=disk_info, completed=(disk_name in self._selected_disks))
            self._container.add(c, self._update_disk_list_callback, disk_name)

        # if we have more than one disk, present an option to just
        # select all disks
        if len(self._available_disks) > 1:
            c = CheckboxWidget(title=_("Select all"), completed=self._select_all)
            self._container.add(c, self._select_all_disks_callback)

        self.window.add_with_separator(self._container)
        self.window.add_with_separator(TextWidget(self._update_summary()))

    def _select_all_disks_callback(self, data):
        """ Mark all disks as selected for use in partitioning. """
        self._select_all = True
        for disk_name in self._available_disks:
            if disk_name not in self._selected_disks:
                self._update_disk_list(disk_name)

    def _update_disk_list_callback(self, data):
        disk = data
        self._select_all = False
        self._update_disk_list(disk)

    def _format_disk_info(self, disk):
        """ Some specialized disks are difficult to identify in the storage
            spoke, so add and return extra identifying information about them.

            Since this is going to be ugly to do within the confines of the
            CheckboxWidget, pre-format the display string right here.
        """
        data = DeviceData.from_structure(
            self._device_tree.GetDeviceData(disk)
        )

        # show this info for all disks
        format_str = "{}: {} ({})".format(
            data.attrs.get("model", "DISK"),
            Size(data.size),
            data.name
        )

        # now append all additional attributes to our string
        disk_attrs = filter(None, map(data.attrs.get, (
            "wwn", "bus-id", "fcp-lun", "wwpn", "hba-id"
        )))

        for attr in disk_attrs:
            format_str += ", %s" % attr

        return format_str

    def input(self, args, key):
        """Grab the disk choice and update things"""
        self.errors = []
        if self._container.process_user_input(key):
            return InputState.PROCESSED_AND_REDRAW
        else:
            if key.lower() == Prompt.CONTINUE:
                if self._selected_disks:
                    # Is DASD formatting supported?
                    if DasdFormatting.is_supported():
                        # Wait for storage.
                        threadMgr.wait(THREAD_STORAGE)

                        # Allow to format DASDs.
                        self._disk_init_module.SetFormatUnrecognizedEnabled(True)
                        self._disk_init_module.SetFormatLDLEnabled(True)

                        # Get selected disks.
                        disks = filter_disks_by_names(self._available_disks, self._selected_disks)

                        # Check if some of the disks should be formatted.
                        dasd_formatting = DasdFormatting()
                        dasd_formatting.search_disks(disks)

                        if dasd_formatting.should_run():
                            # We want to apply current selection before running dasdfmt to
                            # prevent this information from being lost afterward
                            apply_disk_selection(self._selected_disks)

                            # Run the dialog.
                            self.run_dasdfmt_dialog(dasd_formatting)
                            return InputState.PROCESSED_AND_REDRAW

                    # make sure no containers were split up by the user's disk
                    # selection
                    report = ValidationReport.from_structure(
                        self._disk_select_module.ValidateSelectedDisks(self._selected_disks)
                    )
                    self.errors.extend(report.get_messages())

                    if self.errors:
                        # The disk selection has to make sense before we can
                        # proceed.
                        return InputState.PROCESSED_AND_REDRAW

                    self.apply()
                    new_spoke = PartTypeSpoke(self.data, self.storage, self.payload,
                                              self._storage_module, self._partitioning)
                    ScreenHandler.push_screen_modal(new_spoke)
                    self._partitioning = new_spoke.partitioning
                    self.apply()
                    self.execute()

                return InputState.PROCESSED_AND_CLOSE
            else:
                return super().input(args, key)

    def run_dasdfmt_dialog(self, dasd_formatting):
        """Do DASD formatting if user agrees."""
        # Prepare text of the dialog.
        text = ""
        text += _("The following unformatted or LDL DASDs have been "
                  "detected on your system. You can choose to format them "
                  "now with dasdfmt or cancel to leave them unformatted. "
                  "Unformatted DASDs cannot be used during installation.\n\n")

        text += dasd_formatting.dasds_summary + "\n\n"

        text += _("Warning: All storage changes made using the installer will "
                  "be lost when you choose to format.\n\nProceed to run dasdfmt?\n")

        # Run the dialog.
        question_window = YesNoDialog(text)
        ScreenHandler.push_screen_modal(question_window)
        if not question_window.answer:
            return None

        print(_("This may take a moment."), flush=True)

        # Do the DASD formatting.
        dasd_formatting.report.connect(self._show_dasdfmt_report)
        dasd_formatting.run()
        dasd_formatting.report.disconnect(self._show_dasdfmt_report)

    def _show_dasdfmt_report(self, msg):
        print(msg, flush=True)

    def run_passphrase_dialog(self):
        """Ask user for a default passphrase."""
        if not is_passphrase_required(self._partitioning):
            return

        dialog = PasswordDialog(
            title=_("Passphrase"),
            message=_("Please provide a default LUKS passphrase for all devices "
                      "you want to encrypt. You will have to type it twice."),
            secret_type=SecretType.PASSPHRASE,
            policy_name=PASSWORD_POLICY_LUKS,
            process_func=lambda x: x
        )

        passphrase = None
        while passphrase is None:
            passphrase = dialog.run()

        set_required_passphrase(self._partitioning, passphrase)

    def apply(self):
        self._bootloader_module.SetPreferredLocation(BOOTLOADER_LOCATION_MBR)
        apply_disk_selection(self._selected_disks, reset_boot_drive=True)

    def execute(self):
        report = apply_partitioning(self._partitioning, self._show_execute_message)

        log.debug("Partitioning has been applied: %s", report)
        self.errors = list(report.error_messages)
        self.warnings = list(report.warning_messages)

        print("\n".join(report.get_messages()))
        self._ready = True

    def _show_execute_message(self, msg):
        print(msg)
        log.debug(msg)

    def initialize(self):
        NormalTUISpoke.initialize(self)
        self.initialize_start()

        # Ask for a default passphrase.
        if flags.automatedInstall and flags.ksprompt:
            self.run_passphrase_dialog()

        threadMgr.add(AnacondaThread(name=THREAD_STORAGE_WATCHER,
                                     target=self._initialize))

    def _initialize(self):
        """
        Secondary initialize so wait for the storage thread to complete before
        populating our disk list
        """
        # Wait for storage.
        threadMgr.wait(THREAD_STORAGE)

        # Automatically format DASDs if allowed.
        disks = self._disk_select_module.GetUsableDisks()
        DasdFormatting.run_automatically(disks)

        # Update the selected disks.
        select_default_disks()

        # Automatically apply the preconfigured partitioning.
        if flags.automatedInstall and self._is_preconfigured:
            self.execute()

        # Storage is ready.
        self._ready = True

        # Report that the storage spoke has been initialized.
        self.initialize_done()


class PartTypeSpoke(NormalTUISpoke):
    """ Partitioning options are presented here.

       .. inheritance-diagram:: PartTypeSpoke
          :parts: 3
    """
    category = SystemCategory

    def __init__(self, data, storage, payload, storage_module, partitioning):
        super().__init__(data, storage, payload)
        self.title = N_("Partitioning Options")
        self._container = None

        # Choose the partitioning method.
        self._storage_module = storage_module
        self._partitioning = partitioning
        self._orig_part_method = self._partitioning.PartitioningMethod
        self._part_method = self._orig_part_method

        # Choose the initialization mode.
        self._disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
        self._orig_init_mode = self._disk_init_proxy.InitializationMode
        self._init_mode = self._get_init_mode()
        self._init_mode_list = sorted(INIT_MODES.keys())

    def _get_init_mode(self):
        """Return the initial value of the initialization mode."""
        if self._orig_part_method == PARTITIONING_METHOD_MANUAL:
            return CLEAR_PARTITIONS_NONE

        if self._orig_init_mode == CLEAR_PARTITIONS_DEFAULT:
            return CLEAR_PARTITIONS_ALL

        return self._orig_init_mode

    @property
    def indirect(self):
        return True

    @property
    def partitioning(self):
        return self._partitioning

    def refresh(self, args=None):
        super().refresh(args)
        self._container = ListColumnContainer(1)

        for init_mode in self._init_mode_list:
            c = CheckboxWidget(title=_(init_mode), completed=(
                self._part_method == PARTITIONING_METHOD_AUTOMATIC
                and self._init_mode == INIT_MODES[init_mode]
            ))
            self._container.add(c, self._select_partition_type_callback, init_mode)

        c = CheckboxWidget(title=_("Manually assign mount points"), completed=(
            self._part_method == PARTITIONING_METHOD_MANUAL
        ))

        self._container.add(c, self._select_mount_assign)
        self.window.add_with_separator(self._container)

        message = _("Installation requires partitioning of your hard drive. "
                    "Select what space to use for the install target or "
                    "manually assign mount points.")

        self.window.add_with_separator(TextWidget(message))

    def _select_mount_assign(self, data=None):
        self._part_method = PARTITIONING_METHOD_MANUAL
        self._init_mode = CLEAR_PARTITIONS_NONE

    def _select_partition_type_callback(self, data):
        self._part_method = PARTITIONING_METHOD_AUTOMATIC
        self._init_mode = INIT_MODES[data]

    def apply(self):
        # kind of a hack, but if we're actually getting to this spoke, there
        # is no doubt that we are doing autopartitioning, so set autopart to
        # True. In the case of ks installs which may not have defined any
        # partition options, autopart was never set to True, causing some
        # issues. (rhbz#1001061)
        self._disk_init_proxy.SetInitializationMode(self._init_mode)
        self._disk_init_proxy.SetInitializeLabelsEnabled(
            self._part_method == PARTITIONING_METHOD_AUTOMATIC
        )

        if self._orig_part_method != self._part_method:
            self._partitioning = create_partitioning(self._part_method)

    def _ensure_init_storage(self):
        """
        If a different clearpart type was chosen or mount point assignment was
        chosen instead, we need to reset/rescan storage to revert all changes
        done by the previous run of doKickstartStorage() and get everything into
        the initial state.
        """
        # the only safe options are:
        # 1) if nothing was set before (self._orig_clearpart_type is None) or
        if self._orig_init_mode == CLEAR_PARTITIONS_DEFAULT:
            return

        # 2) mount point assignment was done before and user just wants to tweak it
        if self._orig_part_method == self._part_method == PARTITIONING_METHOD_MANUAL:
            return

        # else
        print(_("Reverting previous configuration. This may take a moment..."))
        reset_storage(scan_all=True)

    def input(self, args, key):
        """Grab the choice and update things"""
        if not self._container.process_user_input(key):
            if key.lower() == Prompt.CONTINUE:
                self.apply()
                self._ensure_init_storage()
                if self._part_method == PARTITIONING_METHOD_MANUAL:
                    new_spoke = MountPointAssignSpoke(
                        self.data, self.storage, self.payload, self._partitioning
                    )
                else:
                    new_spoke = PartitionSchemeSpoke(
                        self.data, self.storage, self.payload, self._partitioning
                    )
                ScreenHandler.push_screen_modal(new_spoke)
                return InputState.PROCESSED_AND_CLOSE
            else:
                return super().input(args, key)

        return InputState.PROCESSED_AND_REDRAW


class PartitionSchemeSpoke(NormalTUISpoke):
    """ Spoke to select what partitioning scheme to use on disk(s). """
    category = SystemCategory

    def __init__(self, data, storage, payload, partitioning):
        super().__init__(data, storage, payload)
        self.title = N_("Partition Scheme Options")
        self._container = None
        self._part_schemes = OrderedDict()
        self._partitioning = partitioning
        self._request = PartitioningRequest.from_structure(
            self._partitioning.Request
        )

        supported_choices = get_supported_autopart_choices()

        if supported_choices:
            # Fallback value (eg when default is not supported)
            self._selected_scheme_value = supported_choices[0][1]

        selected_choice = self._request.partitioning_scheme

        for item in supported_choices:
            self._part_schemes[item[0]] = item[1]
            if item[1] == selected_choice:
                self._selected_scheme_value = item[1]

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)

        self._container = ListColumnContainer(1)

        for scheme, value in self._part_schemes.items():
            box = CheckboxWidget(title=_(scheme), completed=(value == self._selected_scheme_value))
            self._container.add(box, self._set_part_scheme_callback, value)

        self.window.add_with_separator(self._container)

        message = _("Select a partition scheme configuration.")
        self.window.add_with_separator(TextWidget(message))

    def _set_part_scheme_callback(self, data):
        self._selected_scheme_value = data
        self._request.partitioning_scheme = data

    def input(self, args, key):
        """ Grab the choice and update things. """
        if not self._container.process_user_input(key):
            if key.lower() == Prompt.CONTINUE:
                self.apply()
                return InputState.PROCESSED_AND_CLOSE
            else:
                return super().input(args, key)

        return InputState.PROCESSED_AND_REDRAW

    def apply(self):
        """ Apply our selections. """
        self._partitioning.SetRequest(
            PartitioningRequest.to_structure(self._request)
        )


class MountPointAssignSpoke(NormalTUISpoke):
    """ Assign mount points to block devices. """
    category = SystemCategory

    def __init__(self, data, storage, payload, partitioning):
        super().__init__(data, storage, payload)
        self.title = N_("Assign mount points")
        self._container = None
        self._partitioning = partitioning
        self._device_tree = STORAGE.get_proxy(self._partitioning.GetDeviceTree())
        self._requests = self._gather_requests()

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        """Refresh the window."""
        super().refresh(args)
        self._container = ListColumnContainer(2)

        for request in self._requests:
            widget = TextWidget(self._get_request_description(request))
            self._container.add(widget, self._configure_request, request)

        message = _(
            "Choose device from above to assign mount point and set format.\n"
            "Formats marked with * are new formats meaning ALL DATA on the "
            "original format WILL BE LOST!"
        )

        self.window.add_with_separator(self._container)
        self.window.add_with_separator(TextWidget(message))

    def prompt(self, args=None):
        prompt = super().prompt(args)
        prompt.add_option(PROMPT_SCAN_KEY, _(PROMPT_SCAN_DESCRIPTION))
        return prompt

    def input(self, args, key):
        """ Grab the choice and update things. """
        if self._container.process_user_input(key):
            return InputState.PROCESSED

        if key.lower() == PROMPT_SCAN_KEY:
            self._rescan_devices()
            return InputState.PROCESSED_AND_REDRAW

        elif key.lower() == Prompt.CONTINUE:
            self.apply()

        return super().input(args, key)

    def apply(self):
        """ Apply our selections. """
        mount_points = []

        for request in self._requests:
            if request.reformat or request.mount_point:
                if not request.mount_point:
                    request.mount_point = "none"

                mount_points.append(request)

        self._partitioning.SetRequests(
            MountPointRequest.to_structure_list(mount_points)
        )

    def _gather_requests(self):
        """Gather info about mount points."""
        return MountPointRequest.from_structure_list(
            self._partitioning.GatherRequests()
        )

    def _get_request_description(self, request):
        """Get description of the given mount info."""
        # Get the device data.
        device_name = self._device_tree.ResolveDevice(request.device_spec)
        device_data = DeviceData.from_structure(
            self._device_tree.GetDeviceData(device_name)
        )

        # Generate the description.
        description = "{} ({})".format(request.device_spec, Size(device_data.size))

        if request.format_type:
            description += "\n {}".format(request.format_type)

            if request.reformat:
                description += "*"

            if request.mount_point:
                description += ", {}".format(request.mount_point)

        return description

    def _configure_request(self, request):
        """Configure the given mount request."""
        spoke = ConfigureDeviceSpoke(
            self.data, self.storage, self.payload, self._device_tree, request
        )
        ScreenHandler.push_screen(spoke)

    def _rescan_devices(self):
        """Rescan devices."""
        text = _("Warning: This will revert all changes done so far.\n"
                 "Do you want to proceed?\n")

        question_window = YesNoDialog(text)
        ScreenHandler.push_screen_modal(question_window)

        if not question_window.answer:
            return

        print(_("Scanning disks. This may take a moment..."))
        reset_storage(scan_all=True)

        # Forget the mount point requests.
        self._partitioning.SetRequests([])
        self._requests = self._gather_requests()


class ConfigureDeviceSpoke(NormalTUISpoke):
    """ Assign mount point to a block device and (optionally) reformat it. """
    category = SystemCategory

    def __init__(self, data, storage, payload, device_tree, request):
        super().__init__(data, storage, payload)
        self.title = N_("Configure device: %s") % request.device_spec
        self._container = None
        self._device_tree = device_tree
        self._request = request
        self._supported_filesystems = set(device_tree.GetSupportedFileSystems())

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        """Refresh window."""
        super().refresh(args)
        self._container = ListColumnContainer(1)
        self._add_mount_point_widget()
        self._add_format_widget()
        self._add_reformat_widget()

        self.window.add_with_separator(self._container)
        self.window.add_with_separator(TextWidget(
            _("Choose from above to assign mount point and/or set format.")
        ))

    def input(self, args, key):
        """Grab the choice and update things."""
        if not self._container.process_user_input(key):
            return super().input(args, key)

        return InputState.PROCESSED_AND_REDRAW

    def apply(self):
        """Nothing to apply here."""
        pass

    def _add_mount_point_widget(self):
        """Add a widget for mount point assignment."""
        title = _("Mount point")
        fmt = DeviceFormatData.from_structure(
            self._device_tree.GetFormatTypeData(self._request.format_type)
        )

        if fmt.mountable:
            # mount point can be set
            value = self._request.mount_point or _("none")
            callback = self._assign_mount_point
        elif not fmt.type:
            # mount point cannot be set for no format
            # (fmt.name = "Unknown" in this case which would look weird)
            value = _("none")
            callback = None
        else:
            # mount point cannot be set for format that is not mountable, just
            # show the format's name in square brackets instead
            value = fmt.description
            callback = None

        dialog = Dialog(title, conditions=[self._check_assign_mount_point])
        widget = EntryWidget(dialog.title, value)
        self._container.add(widget, callback, dialog)

    def _check_assign_mount_point(self, user_input, report_func):
        """Check the mount point assignment."""
        # a valid mount point must start with / or user set nothing
        if user_input == "" or user_input.startswith("/"):
            return True
        else:
            report_func(_("Invalid mount point given"))
            return False

    def _assign_mount_point(self, dialog):
        """Change the mount point assignment."""
        self._request.mount_point = dialog.run()

        # Always reformat root.
        if self._request.mount_point == "/":
            self._request.reformat = True

    def _add_format_widget(self):
        """Add a widget for format."""
        dialog = Dialog(_("Format"), conditions=[self._check_format])
        widget = EntryWidget(dialog.title, self._request.format_type or _("none"))
        self._container.add(widget, self._set_format, dialog)

    def _check_format(self, user_input, report_func):
        """Check value of format."""
        user_input = user_input.lower()
        if user_input in self._supported_filesystems:
            return True
        else:
            msg = _("Invalid or unsupported format given")
            msg += "\n"
            msg += (_("Supported formats: %s") % ", ".join(self._supported_filesystems))
            report_func(msg)
            return False

    def _set_format(self, dialog):
        """Change value of format."""
        old_format = self._request.format_type
        new_format = dialog.run()

        # Reformat to a new format.
        if new_format != old_format:
            self._request.format_type = new_format
            self._request.reformat = True

    def _add_reformat_widget(self):
        """Add a widget for reformat."""
        widget = CheckboxWidget(
            title=_("Reformat"),
            completed=self._request.reformat
        )
        self._container.add(widget, self._switch_reformat)

    def _switch_reformat(self, data):
        """Change value of reformat."""
        device_name = self._device_tree.ResolveDevice(
            self._request.device_spec
        )
        format_data = DeviceFormatData.from_structure(
            self._device_tree.GetFormatData(device_name)
        )
        device_format = format_data.type

        if device_format and device_format != self._request.format_type:
            reformat = True
        elif self._request.mount_point == "/":
            reformat = True
        else:
            reformat = not self._request.reformat

        self._request.reformat = reformat
