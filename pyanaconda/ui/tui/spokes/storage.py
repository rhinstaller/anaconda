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

from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.input_checking import get_policy
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, DISK_INITIALIZATION, \
    BOOTLOADER, AUTO_PARTITIONING, MANUAL_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import Dialog, PasswordDialog
from pyanaconda.storage.utils import get_supported_filesystems, get_supported_autopart_choices, \
    get_available_disks, filter_disks_by_names, apply_disk_selection, check_disk_selection
from pyanaconda.storage.checker import storage_checker
from pyanaconda.storage.format_dasd import DasdFormatting

from blivet.size import Size
from blivet.errors import StorageError
from blivet.devices import DASDDevice, FcoeDiskDevice, iScsiDiskDevice, MultipathDevice, \
    ZFCPDiskDevice
from blivet.formats import get_format
from pyanaconda.flags import flags
from pyanaconda.kickstart import resetCustomStorageData
from pyanaconda.storage.execution import do_kickstart_storage
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import THREAD_STORAGE, THREAD_STORAGE_WATCHER, \
    DEFAULT_AUTOPART_TYPE, PAYLOAD_STATUS_PROBING_STORAGE, CLEAR_PARTITIONS_ALL, \
    CLEAR_PARTITIONS_LINUX, CLEAR_PARTITIONS_NONE, CLEAR_PARTITIONS_DEFAULT, \
    BOOTLOADER_LOCATION_MBR, BOOTLOADER_DRIVE_UNSET, AUTOPART_TYPE_DEFAULT, SecretType, \
    MOUNT_POINT_REFORMAT, MOUNT_POINT_PATH, MOUNT_POINT_DEVICE, MOUNT_POINT_FORMAT
from pyanaconda.core.i18n import _, P_, N_, C_
from pyanaconda.bootloader import BootLoaderError
from pyanaconda.storage.initialization import initialize_storage, update_storage_config, \
    reset_storage, select_all_disks_by_default

from pykickstart.base import BaseData
from pykickstart.constants import AUTOPART_TYPE_LVM
from pykickstart.errors import KickstartParseError

from simpleline.render.containers import ListColumnContainer
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget, CheckboxWidget, EntryWidget
from simpleline.render.adv_widgets import YesNoDialog

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["StorageSpoke", "PartTypeSpoke"]

CLEARALL = N_("Use All Space")
CLEARLINUX = N_("Replace Existing Linux system(s)")
CLEARNONE = N_("Use Free Space")

PARTTYPES = {CLEARALL: CLEAR_PARTITIONS_ALL, CLEARLINUX: CLEAR_PARTITIONS_LINUX,
             CLEARNONE: CLEAR_PARTITIONS_NONE}


class StorageSpoke(NormalTUISpoke):
    """Storage spoke where users proceed to customize storage features such
       as disk selection, partitioning, and fs type.

       .. inheritance-diagram:: StorageSpoke
          :parts: 3
    """
    helpFile = "StorageSpoke.txt"
    category = SystemCategory

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)

        self._bootloader_observer = STORAGE.get_observer(BOOTLOADER)
        self._bootloader_observer.connect()

        self._disk_init_observer = STORAGE.get_observer(DISK_INITIALIZATION)
        self._disk_init_observer.connect()

        self._disk_select_observer = STORAGE.get_observer(DISK_SELECTION)
        self._disk_select_observer.connect()

        self._auto_part_observer = STORAGE.get_observer(AUTO_PARTITIONING)
        self._auto_part_observer.connect()

        self.selected_disks = self._disk_select_observer.proxy.SelectedDisks

        self.title = N_("Installation Destination")
        self._ready = False
        self._container = None
        self.select_all = False
        self.autopart = None

        # This list gets set up once in initialize and should not be modified
        # except perhaps to add advanced devices. It will remain the full list
        # of disks that can be included in the install.
        self.disks = []
        self.errors = []
        self.warnings = []

        if not flags.automatedInstall:
            # default to using autopart for interactive installs
            self._auto_part_observer.proxy.SetEnabled(True)

    @property
    def completed(self):
        retval = bool(self.storage.root_device and not self.errors)

        return retval

    @property
    def ready(self):
        # By default, the storage spoke is not ready.  We have to wait until
        # storageInitialize is done.
        return self._ready and not threadMgr.get(THREAD_STORAGE_WATCHER)

    @property
    def mandatory(self):
        return True

    @property
    def showable(self):
        return not conf.target.is_directory

    @property
    def status(self):
        """ A short string describing the current status of storage setup. """
        if flags.automatedInstall and not self.storage.root_device:
            return _("Kickstart insufficient")
        elif not self._disk_select_observer.proxy.SelectedDisks:
            return _("No disks selected")
        if self.errors:
            return _("Error checking storage configuration")
        elif self.warnings:
            return _("Warning checking storage configuration")
        elif self._auto_part_observer.proxy.Enabled:
            return _("Automatic partitioning selected")
        else:
            return _("Custom partitioning selected")

    def _update_disk_list(self, disk):
        """ Update self.selected_disks based on the selection."""

        name = disk.name

        # if the disk isn't already selected, select it.
        if name not in self.selected_disks:
            self.selected_disks.append(name)
        # If the disk is already selected, deselect it.
        elif name in self.selected_disks:
            self.selected_disks.remove(name)

    def _update_summary(self):
        """ Update the summary based on the UI. """
        count = 0
        capacity = 0
        free = Size(0)

        # pass in our disk list so hidden disks' free space is available
        free_space = self.storage.get_free_space(disks=self.disks)
        selected = filter_disks_by_names(self.disks, self.selected_disks)

        for disk in selected:
            capacity += disk.size
            free += free_space[disk.name][0]
            count += 1

        summary = (P_(("%d disk selected; %s capacity; %s free ..."),
                      ("%d disks selected; %s capacity; %s free ..."),
                      count) % (count, str(Size(capacity)), free))

        if len(self.disks) == 0:
            summary = _("No disks detected.  Please shut down the computer, "
                        "connect at least one disk, and restart to complete installation.")
        elif count == 0:
            summary = (_("No disks selected; please select at least one disk to install to."))

        # Append storage errors to the summary
        if self.errors:
            summary = summary + "\n" + "\n".join(self.errors)
        elif self.warnings:
            summary = summary + "\n" + "\n".join(self.warnings)

        return summary

    def refresh(self, args=None):
        super().refresh(args)

        # Join the initialization thread to block on it
        # This print is foul.  Need a better message display
        print(_(PAYLOAD_STATUS_PROBING_STORAGE))
        threadMgr.wait(THREAD_STORAGE_WATCHER)

        if not any(d in self.storage.disks for d in self.disks):
            # something happened to self.storage (probably reset), need to
            # reinitialize the list of disks
            self.update_disks()

        # synchronize our local data store with the global ksdata
        # Commment out because there is no way to select a disk right
        # now without putting it in ksdata.  Seems wrong?
        # self.selected_disks = self.data.ignoredisk.onlyuse[:]
        self.autopart = self._auto_part_observer.proxy.Enabled

        self._container = ListColumnContainer(1, spacing=1)

        message = self._update_summary()

        # loop through the disks and present them.
        for disk in self.disks:
            disk_info = self._format_disk_info(disk)
            c = CheckboxWidget(title=disk_info, completed=(disk.name in self.selected_disks))
            self._container.add(c, self._update_disk_list_callback, disk)

        # if we have more than one disk, present an option to just
        # select all disks
        if len(self.disks) > 1:
            c = CheckboxWidget(title=_("Select all"), completed=self.select_all)
            self._container.add(c, self._select_all_disks_callback)

        self.window.add_with_separator(self._container)
        self.window.add_with_separator(TextWidget(message))

    def _select_all_disks_callback(self, data):
        """ Mark all disks as selected for use in partitioning. """
        self.select_all = True
        for disk in self.disks:
            if disk.name not in self.selected_disks:
                self._update_disk_list(disk)

    def _update_disk_list_callback(self, data):
        disk = data
        self.select_all = False
        self._update_disk_list(disk)

    def _format_disk_info(self, disk):
        """ Some specialized disks are difficult to identify in the storage
            spoke, so add and return extra identifying information about them.

            Since this is going to be ugly to do within the confines of the
            CheckboxWidget, pre-format the display string right here.
        """
        # show this info for all disks
        format_str = "%s: %s (%s)" % (disk.model, disk.size, disk.name)

        disk_attrs = []
        # now check for/add info about special disks
        if (isinstance(disk, MultipathDevice) or
                isinstance(disk, iScsiDiskDevice) or
                isinstance(disk, FcoeDiskDevice)):
            if hasattr(disk, "wwn"):
                disk_attrs.append(disk.wwn)
        elif isinstance(disk, DASDDevice):
            if hasattr(disk, "busid"):
                disk_attrs.append(disk.busid)
        elif isinstance(disk, ZFCPDiskDevice):
            if hasattr(disk, "fcp_lun"):
                disk_attrs.append(disk.fcp_lun)
            if hasattr(disk, "wwpn"):
                disk_attrs.append(disk.wwpn)
            if hasattr(disk, "hba_id"):
                disk_attrs.append(disk.hba_id)

        # now append all additional attributes to our string
        for attr in disk_attrs:
            format_str += ", %s" % attr

        return format_str

    def input(self, args, key):
        """Grab the disk choice and update things"""
        self.errors = []
        if self._container.process_user_input(key):
            return InputState.PROCESSED_AND_REDRAW
        else:
            # TRANSLATORS: 'c' to continue
            if key.lower() == C_('TUI|Spoke Navigation', 'c'):
                if self.selected_disks:
                    # Is DASD formatting supported?
                    if DasdFormatting.is_supported():
                        # Wait for storage.
                        threadMgr.wait(THREAD_STORAGE)

                        # Get selected disks.
                        disks = filter_disks_by_names(self.disks, self.selected_disks)

                        # Check if some of the disks should be formatted.
                        dasd_formatting = DasdFormatting()
                        dasd_formatting.search_disks(disks)

                        if dasd_formatting.should_run():
                            # We want to apply current selection before running dasdfmt to
                            # prevent this information from being lost afterward
                            apply_disk_selection(self.storage, self.selected_disks)

                            # Run the dialog.
                            self.run_dasdfmt_dialog(dasd_formatting)
                            return InputState.PROCESSED_AND_REDRAW

                    # make sure no containers were split up by the user's disk
                    # selection
                    self.errors.extend(check_disk_selection(self.storage,
                                                            self.selected_disks))
                    if self.errors:
                        # The disk selection has to make sense before we can
                        # proceed.
                        return InputState.PROCESSED_AND_REDRAW

                    self.apply()
                    new_spoke = PartTypeSpoke(self.data, self.storage, self.payload)
                    ScreenHandler.push_screen_modal(new_spoke)
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
        dasd_formatting.run(self.storage, self.data)
        dasd_formatting.report.disconnect(self._show_dasdfmt_report)

        self.update_disks()

    def _show_dasdfmt_report(self, msg):
        print(msg, flush=True)

    def run_passphrase_dialog(self):
        """Ask user for a default passphrase."""
        data_without_passphrase = self._get_data_without_passphrase()
        if not data_without_passphrase:
            return

        dialog = PasswordDialog(
            title=_("Passphrase"),
            message=_("Please provide a default LUKS passphrase for all devices "
                      "you want to encrypt. You will have to type it twice."),
            secret_type=SecretType.PASSPHRASE,
            policy=get_policy(self.data, "luks"),
            process_func=lambda x: x
        )

        passphrase = None
        while passphrase is None:
            passphrase = dialog.run()

        self._set_data_without_passphrase(data_without_passphrase, passphrase)

    def _get_data_without_passphrase(self):
        """Collect kickstart data and DBus proxies that require a passphrase."""
        result = []

        if self._auto_part_observer.proxy.Encrypted \
                and not self._auto_part_observer.proxy.Passphrase:
            result.append(self._auto_part_observer.proxy)

        for data in self.data.partition.dataList():
            if data.encrypted and not data.passphrase:
                result.append(data)

        for data in self.data.logvol.dataList():
            if data.encrypted and not data.passphrase:
                result.append(data)

        for data in self.data.raid.dataList():
            if data.encrypted and not data.passphrase:
                result.append(data)

        return result

    def _set_data_without_passphrase(self, data_without_passphrase, passphrase):
        """Set a passphrase to the collected kickstart data and DBus proxies."""
        for data in data_without_passphrase:
            if isinstance(data, BaseData):
                data.passphrase = passphrase
            else:
                data.SetPassphrase(passphrase)

    def apply(self):
        self.autopart = self._auto_part_observer.proxy.Enabled

        if self.autopart and self._auto_part_observer.proxy.Type == AUTOPART_TYPE_DEFAULT:
            self._auto_part_observer.proxy.SetType(AUTOPART_TYPE_LVM)

        for disk in self.disks:
            if disk.name not in self.selected_disks and \
               disk in self.storage.devices:
                self.storage.devicetree.hide(disk)
            elif disk.name in self.selected_disks and \
                 disk not in self.storage.devices:
                self.storage.devicetree.unhide(disk)

        self._bootloader_observer.proxy.SetPreferredLocation(BOOTLOADER_LOCATION_MBR)
        boot_drive = self._bootloader_observer.proxy.Drive

        if boot_drive and boot_drive not in self.selected_disks:
            self._bootloader_observer.proxy.SetDrive(BOOTLOADER_DRIVE_UNSET)
            self.storage.bootloader.reset()

        apply_disk_selection(self.storage, self.selected_disks)
        update_storage_config(self.storage.config)

        # If autopart is selected we want to remove whatever has been
        # created/scheduled to make room for autopart.
        # If custom is selected, we want to leave alone any storage layout the
        # user may have set up before now.
        self.storage.config.clear_non_existent = self._auto_part_observer.proxy.Enabled

    def execute(self):
        print(_("Generating updated storage configuration"))
        try:
            do_kickstart_storage(self.storage, self.data)
        except (StorageError, KickstartParseError) as e:
            log.error("storage configuration failed: %s", e)
            print(_("storage configuration failed: %s") % e)
            self.errors = [str(e)]

            # Prepare for reset.
            self._bootloader_observer.proxy.SetDrive(BOOTLOADER_DRIVE_UNSET)
            self._disk_init_observer.proxy.SetInitializationMode(CLEAR_PARTITIONS_ALL)
            self._disk_init_observer.proxy.SetInitializeLabelsEnabled(False)
            self.storage.autopart_type = self._auto_part_observer.proxy.Type

            # The reset also calls self.storage.config.update().
            reset_storage(self.storage)

            # Now set data back to the user's specified config.
            apply_disk_selection(self.storage, self.selected_disks)
        except BootLoaderError as e:
            log.error("BootLoader setup failed: %s", e)
            print(_("storage configuration failed: %s") % e)
            self.errors = [str(e)]
            self._bootloader_observer.proxy.SetDrive(BOOTLOADER_DRIVE_UNSET)
        else:
            print(_("Checking storage configuration..."))
            report = storage_checker.check(self.storage)
            print("\n".join(report.all_errors))
            report.log(log)
            self.errors = report.errors
            self.warnings = report.warnings
        finally:
            resetCustomStorageData(self.data)
            self._ready = True

    def initialize(self):
        NormalTUISpoke.initialize(self)
        self.initialize_start()

        # Ask for a default passphrase.
        if flags.automatedInstall and flags.ksprompt:
            self.run_passphrase_dialog()

        threadMgr.add(AnacondaThread(name=THREAD_STORAGE_WATCHER,
                                     target=self._initialize))

        self.selected_disks = self._disk_select_observer.proxy.SelectedDisks
        # Probably need something here to track which disks are selected?

    def _initialize(self):
        """
        Secondary initialize so wait for the storage thread to complete before
        populating our disk list
        """
        # Wait for storage.
        threadMgr.wait(THREAD_STORAGE)

        # Automatically format DASDs if allowed.
        DasdFormatting.run_automatically(self.storage, self.data)

        # Update the selected disks.
        if flags.automatedInstall:
            self.selected_disks = select_all_disks_by_default(self.storage)

        # Update disk list.
        self.update_disks()

        # Storage is ready.
        self._ready = True

        # Report that the storage spoke has been initialized.
        self.initialize_done()

    def update_disks(self):
        threadMgr.wait(THREAD_STORAGE)
        self.disks = get_available_disks(self.storage.devicetree)

        # if only one disk is available, go ahead and mark it as selected
        if len(self.disks) == 1:
            self._update_disk_list(self.disks[0])


class PartTypeSpoke(NormalTUISpoke):
    """ Partitioning options are presented here.

       .. inheritance-diagram:: PartTypeSpoke
          :parts: 3
    """
    category = SystemCategory

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self.title = N_("Partitioning Options")
        self._container = None
        self.parttypelist = sorted(PARTTYPES.keys())

        # remember the original values so that we can detect a change
        self._disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
        self._orig_clearpart_type = self._disk_init_proxy.InitializationMode
        self._manual_part_proxy = STORAGE.get_proxy(MANUAL_PARTITIONING)
        self._orig_mount_assign = self._manual_part_proxy.Enabled

        # Create the auto partitioning proxy
        self._auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)

        # default to mount point assignment if it is already (partially)
        # configured
        self._do_mount_assign = self._orig_mount_assign
        if not self._do_mount_assign:
            self.clearPartType = self._disk_init_proxy.InitializationMode
        else:
            self.clearPartType = CLEAR_PARTITIONS_NONE

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)
        self._container = ListColumnContainer(1)

        for part_type in self.parttypelist:
            c = CheckboxWidget(title=_(part_type),
                               completed=(not self._do_mount_assign and PARTTYPES[part_type] == self.clearPartType))
            self._container.add(c, self._select_partition_type_callback, part_type)
        c = CheckboxWidget(title=_("Manually assign mount points"),
                           completed=self._do_mount_assign)
        self._container.add(c, self._select_mount_assign)

        self.window.add_with_separator(self._container)

        message = _("Installation requires partitioning of your hard drive. "
                    "Select what space to use for the install target or "
                    "manually assign mount points.")

        self.window.add_with_separator(TextWidget(message))

    def _select_mount_assign(self, data=None):
        self.clearPartType = CLEAR_PARTITIONS_NONE
        self._do_mount_assign = True
        self.apply()

    def _select_partition_type_callback(self, data):
        self._do_mount_assign = False
        self.clearPartType = PARTTYPES[data]
        self.apply()

    def apply(self):
        # kind of a hack, but if we're actually getting to this spoke, there
        # is no doubt that we are doing autopartitioning, so set autopart to
        # True. In the case of ks installs which may not have defined any
        # partition options, autopart was never set to True, causing some
        # issues. (rhbz#1001061)
        if not self._do_mount_assign:
            self._auto_part_proxy.SetEnabled(True)
            self._manual_part_proxy.SetEnabled(False)
            self._disk_init_proxy.SetInitializationMode(self.clearPartType)
            self._disk_init_proxy.SetInitializeLabelsEnabled(True)
        else:
            self._auto_part_proxy.SetEnabled(False)
            self._manual_part_proxy.SetEnabled(True)
            self._disk_init_proxy.SetInitializationMode(CLEAR_PARTITIONS_NONE)
            self._disk_init_proxy.SetInitializeLabelsEnabled(False)

    def _ensure_init_storage(self):
        """
        If a different clearpart type was chosen or mount point assignment was
        chosen instead, we need to reset/rescan storage to revert all changes
        done by the previous run of doKickstartStorage() and get everything into
        the initial state.
        """
        # the only safe options are:
        # 1) if nothing was set before (self._orig_clearpart_type is None) or
        if self._orig_clearpart_type == CLEAR_PARTITIONS_DEFAULT:
            return

        # 2) mount point assignment was done before and user just wants to tweak it
        if self._orig_mount_assign and self._do_mount_assign:
            return

        # else
        print(_("Reverting previous configuration. This may take a moment..."))
        # unset selected disks temporarily so that
        # initialize_storage() processes all devices
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        selected_disks = disk_select_proxy.SelectedDisks
        disk_select_proxy.SetSelectedDisks([])

        initialize_storage(self.storage)

        disk_select_proxy.SetSelectedDisks(selected_disks)
        self._manual_part_proxy.SetMountPoints([])

    def input(self, args, key):
        """Grab the choice and update things"""
        if not self._container.process_user_input(key):
            # TRANSLATORS: 'c' to continue
            if key.lower() == C_('TUI|Spoke Navigation', 'c'):
                self.apply()
                self._ensure_init_storage()
                if self._do_mount_assign:
                    new_spoke = MountPointAssignSpoke(self.data, self.storage, self.payload)
                else:
                    new_spoke = PartitionSchemeSpoke(self.data, self.storage, self.payload)
                ScreenHandler.push_screen_modal(new_spoke)
                return InputState.PROCESSED_AND_CLOSE
            else:
                return super().input(args, key)

        return InputState.PROCESSED_AND_REDRAW


class PartitionSchemeSpoke(NormalTUISpoke):
    """ Spoke to select what partitioning scheme to use on disk(s). """
    category = SystemCategory

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self.title = N_("Partition Scheme Options")
        self._container = None
        self.part_schemes = OrderedDict()

        self._auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)
        pre_select = self._auto_part_proxy.Type

        if pre_select == AUTOPART_TYPE_DEFAULT:
            pre_select = DEFAULT_AUTOPART_TYPE

        supported_choices = get_supported_autopart_choices()
        if supported_choices:
            # Fallback value (eg when default is not supported)
            self._selected_scheme_value = supported_choices[0][1]
        for item in supported_choices:
            self.part_schemes[item[0]] = item[1]
            if item[1] == pre_select:
                self._selected_scheme_value = item[1]

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)

        self._container = ListColumnContainer(1)

        for scheme, value in self.part_schemes.items():
            box = CheckboxWidget(title=_(scheme), completed=(value == self._selected_scheme_value))
            self._container.add(box, self._set_part_scheme_callback, value)

        self.window.add_with_separator(self._container)

        message = _("Select a partition scheme configuration.")
        self.window.add_with_separator(TextWidget(message))

    def _set_part_scheme_callback(self, data):
        self._selected_scheme_value = data

    def input(self, args, key):
        """ Grab the choice and update things. """
        if not self._container.process_user_input(key):
            # TRANSLATORS: 'c' to continue
            if key.lower() == C_('TUI|Spoke Navigation', 'c'):
                self.apply()
                return InputState.PROCESSED_AND_CLOSE
            else:
                return super().input(args, key)

        return InputState.PROCESSED_AND_REDRAW

    def apply(self):
        """ Apply our selections. """
        self._auto_part_proxy.SetType(self._selected_scheme_value)


class MountPointAssignSpoke(NormalTUISpoke):
    """ Assign mount points to block devices. """
    category = SystemCategory

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self.title = N_("Assign mount points")
        self._container = None

        self._disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        self._manual_part_proxy = STORAGE.get_proxy(MANUAL_PARTITIONING)
        self._mount_info = self._gather_mount_info()

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        """Refresh the window."""
        super().refresh(args)
        self._container = ListColumnContainer(2)

        for info in self._mount_info:
            widget = TextWidget(self._get_mount_info_description(info))
            self._container.add(widget, self._configure_mount_info, info)

        message = _(
            "Choose device from above to assign mount point and set format.\n"
            "Formats marked with * are new formats meaning ALL DATA on the "
            "original format WILL BE LOST!"
        )

        self.window.add_with_separator(self._container)
        self.window.add_with_separator(TextWidget(message))

    def prompt(self, args=None):
        prompt = super().prompt(args)

        # TRANSLATORS: 's' to rescan devices
        prompt.add_option(C_('TUI|Spoke Navigation|Partitioning', 's'), _("rescan devices"))

        return prompt

    def input(self, args, key):
        """ Grab the choice and update things. """
        if self._container.process_user_input(key):
            return InputState.PROCESSED

        # TRANSLATORS: 's' to rescan devices
        if key.lower() == C_('TUI|Spoke Navigation|Partitioning', 's'):
            self._rescan_devices()
            return InputState.PROCESSED_AND_REDRAW

        # TRANSLATORS: 'c' to continue
        elif key.lower() == C_('TUI|Spoke Navigation', 'c'):
            self.apply()

        return super().input(args, key)

    def apply(self):
        """ Apply our selections. """
        mount_points = []

        for _device, data in self._mount_info:
            if data[MOUNT_POINT_REFORMAT] or data[MOUNT_POINT_PATH]:
                mount_points.append({
                    MOUNT_POINT_PATH: get_variant(Str, data[MOUNT_POINT_PATH] or "none"),
                    MOUNT_POINT_DEVICE: get_variant(Str, data[MOUNT_POINT_DEVICE]),
                    MOUNT_POINT_REFORMAT: get_variant(Bool, data[MOUNT_POINT_REFORMAT]),
                    MOUNT_POINT_FORMAT: get_variant(Str, data[MOUNT_POINT_FORMAT])
                })

        self._manual_part_proxy.SetMountPoints(mount_points)

    def _gather_mount_info(self):
        """Gather info about mount points."""
        selected_disks = self._disk_select_proxy.SelectedDisks
        mount_points = self._manual_part_proxy.MountPoints

        mount_info = []

        for device in self.storage.devicetree.leaves:
            # Is the device usable?
            if device.protected or device.size == Size(0):
                continue

            # All device's disks have to be in selected disks.
            device_disks = {d.name for d in device.disks}
            if selected_disks and not set(selected_disks).issuperset(device_disks):
                continue

            # Append new info about this device.
            data = self._get_mount_point_data(device, mount_points)
            mount_info.append((device, data))

            # Use the data only once.
            if data in mount_points:
                mount_points.remove(data)

        return mount_info

    def _get_mount_point_data(self, device, mount_points):
        """Get the mount point data for the given device."""

        # Try to find existing assignment for this device.
        for data in mount_points:
            if device is self.storage.devicetree.resolve_device(data[MOUNT_POINT_DEVICE]):
                return data

        # Or create a new assignment.
        if device.format.mountable and device.format.mountpoint:
            mount_point = device.format.mountpoint
        else:
            mount_point = ""

        return {
            MOUNT_POINT_DEVICE: device.path,
            MOUNT_POINT_PATH: mount_point,
            MOUNT_POINT_FORMAT: device.format.type,
            MOUNT_POINT_REFORMAT: False
        }

    def _get_mount_info_description(self, info):
        """Get description of the given mount info."""
        device, data = info
        description = "{} ({})".format(data[MOUNT_POINT_DEVICE], device.size)

        if data[MOUNT_POINT_FORMAT]:
            description += "\n {}".format(data[MOUNT_POINT_FORMAT])

            if data[MOUNT_POINT_REFORMAT]:
                description += "*"

            if data[MOUNT_POINT_PATH]:
                description += ", {}".format(data[MOUNT_POINT_PATH])

        return description

    def _configure_mount_info(self, info):
        """Configure the given mount info."""
        spoke = ConfigureDeviceSpoke(self.data, self.storage, self.payload, *info)
        ScreenHandler.push_screen(spoke)

    def _rescan_devices(self):
        """Rescan devices."""
        text = _("Warning: This will revert all changes done so far.\n"
                 "Do you want to proceed?\n")

        question_window = YesNoDialog(text)
        ScreenHandler.push_screen_modal(question_window)

        if not question_window.answer:
            return

        # unset selected disks temporarily so that
        # initialize_storage() processes all devices
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        selected_disks = disk_select_proxy.SelectedDisks
        disk_select_proxy.SetSelectedDisks([])

        print(_("Scanning disks. This may take a moment..."))
        initialize_storage(self.storage)

        disk_select_proxy.SetSelectedDisks(selected_disks)
        self._manual_part_proxy.SetMountPoints([])
        self._mount_info = self._gather_mount_info()


class ConfigureDeviceSpoke(NormalTUISpoke):
    """ Assign mount point to a block device and (optionally) reformat it. """
    category = SystemCategory

    def __init__(self, data, storage, payload, device, mount_data):
        super().__init__(data, storage, payload)
        self.title = N_("Configure device: %s") % mount_data[MOUNT_POINT_DEVICE]
        self._container = None

        self._supported_filesystems = [fmt.type for fmt in get_supported_filesystems()]
        self._mount_data = mount_data
        self._device = device

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
        fmt = get_format(self._mount_data[MOUNT_POINT_FORMAT])

        if fmt and fmt.mountable:
            # mount point can be set
            value = self._mount_data[MOUNT_POINT_PATH] or _("none")
            callback = self._assign_mount_point
        elif fmt and fmt.type is None:
            # mount point cannot be set for no format
            # (fmt.name = "Unknown" in this case which would look weird)
            value = _("none")
            callback = None
        else:
            # mount point cannot be set for format that is not mountable, just
            # show the format's name in square brackets instead
            value = fmt.name
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
        self._mount_data[MOUNT_POINT_PATH] = dialog.run()

        # Always reformat root.
        if self._mount_data[MOUNT_POINT_PATH] == "/":
            self._mount_data[MOUNT_POINT_REFORMAT] = True

    def _add_format_widget(self):
        """Add a widget for format."""
        dialog = Dialog(_("Format"), conditions=[self._check_format])
        widget = EntryWidget(dialog.title, self._mount_data[MOUNT_POINT_FORMAT] or _("none"))
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
        old_format = self._mount_data[MOUNT_POINT_FORMAT]
        new_format = dialog.run()

        # Reformat to a new format.
        if new_format != old_format:
            self._mount_data[MOUNT_POINT_FORMAT] = new_format
            self._mount_data[MOUNT_POINT_REFORMAT] = True

    def _add_reformat_widget(self):
        """Add a widget for reformat."""
        widget = CheckboxWidget(
            title=_("Reformat"),
            completed=self._mount_data[MOUNT_POINT_REFORMAT]
        )
        self._container.add(widget, self._switch_reformat)

    def _switch_reformat(self, data):
        """Change value of reformat."""
        device_format = self._device.format.type

        if device_format and device_format != self._mount_data[MOUNT_POINT_FORMAT]:
            reformat = True
        elif self._mount_data[MOUNT_POINT_PATH] == "/":
            reformat = True
        else:
            reformat = not self._mount_data[MOUNT_POINT_REFORMAT]

        self._mount_data[MOUNT_POINT_REFORMAT] = reformat
