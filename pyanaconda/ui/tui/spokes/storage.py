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

from pyanaconda.modules.common.constants.objects import DISK_SELECTION, DISK_INITIALIZATION, \
    BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.ui.lib.disks import getDisks, applyDiskSelection, checkDiskSelection, getDisksByNames
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import Dialog
from pyanaconda.storage_utils import AUTOPART_CHOICES, storage_checker, get_supported_filesystems
from pyanaconda.format_dasd import DasdFormatting

from blivet.size import Size
from blivet.errors import StorageError
from blivet.devices import DASDDevice, FcoeDiskDevice, iScsiDiskDevice, MultipathDevice, ZFCPDiskDevice
from blivet.formats import get_format
from pyanaconda.flags import flags
from pyanaconda.kickstart import doKickstartStorage, resetCustomStorageData
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.core.constants import THREAD_STORAGE, THREAD_STORAGE_WATCHER, \
    DEFAULT_AUTOPART_TYPE, PAYLOAD_STATUS_PROBING_STORAGE, CLEAR_PARTITIONS_ALL, \
    CLEAR_PARTITIONS_LINUX, CLEAR_PARTITIONS_NONE, CLEAR_PARTITIONS_DEFAULT, \
    BOOTLOADER_LOCATION_MBR, BOOTLOADER_DRIVE_UNSET
from pyanaconda.core.i18n import _, P_, N_, C_
from pyanaconda.bootloader import BootLoaderError
from pyanaconda import kickstart
from pyanaconda.storage.osinstall import storage_initialize

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

    def __init__(self, data, storage, payload, instclass):
        super().__init__(data, storage, payload, instclass)

        self._bootloader_observer = STORAGE.get_observer(BOOTLOADER)
        self._bootloader_observer.connect()

        self._disk_init_observer = STORAGE.get_observer(DISK_INITIALIZATION)
        self._disk_init_observer.connect()

        self._disk_select_observer = STORAGE.get_observer(DISK_SELECTION)
        self._disk_select_observer.connect()

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
            self.data.autopart.autopart = True

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
        return not flags.dirInstall

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
        elif self.data.autopart.autopart:
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
        selected = [d for d in self.disks if d.name in self.selected_disks]

        for disk in selected:
            capacity += disk.size
            free += free_space[disk.name][0]
            count += 1

        summary = (P_(("%d disk selected; %s capacity; %s free ..."),
                      ("%d disks selected; %s capacity; %s free ..."),
                      count) % (count, str(Size(capacity)), free))

        if len(self.disks) == 0:
            summary = _("No disks detected.  Please shut down the computer, connect at least one disk, and restart to complete installation.")
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
        #self.selected_disks = self.data.ignoredisk.onlyuse[:]
        self.autopart = self.data.autopart.autopart

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
        if (isinstance(disk, MultipathDevice) or isinstance(disk, iScsiDiskDevice) or isinstance(disk, FcoeDiskDevice)):
            if hasattr(disk, "wwid"):
                disk_attrs.append(disk.wwid)
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
            self.redraw()
            return InputState.PROCESSED
        else:
            # TRANSLATORS: 'c' to continue
            if key.lower() == C_('TUI|Spoke Navigation', 'c'):
                if self.selected_disks:
                    # Is DASD formatting supported?
                    if DasdFormatting.is_supported():
                        # Wait for storage.
                        threadMgr.wait(THREAD_STORAGE)

                        # Get selected disks.
                        disks = getDisksByNames(self.disks, self.selected_disks)

                        # Check if some of the disks should be formatted.
                        dasd_formatting = DasdFormatting()
                        dasd_formatting.search_disks(disks)

                        if dasd_formatting.should_run():
                            # We want to apply current selection before running dasdfmt to
                            # prevent this information from being lost afterward
                            applyDiskSelection(self.storage, self.data, self.selected_disks)

                            # Run the dialog.
                            self.run_dasdfmt_dialog(dasd_formatting)
                            self.redraw()
                            return InputState.PROCESSED

                    # make sure no containers were split up by the user's disk
                    # selection
                    self.errors.extend(checkDiskSelection(self.storage,
                                                          self.selected_disks))
                    if self.errors:
                        # The disk selection has to make sense before we can
                        # proceed.
                        self.redraw()
                        return InputState.PROCESSED

                    self.apply()
                    new_spoke = PartTypeSpoke(self.data, self.storage,
                                              self.payload, self.instclass)
                    ScreenHandler.push_screen_modal(new_spoke)
                    self.apply()
                    self.execute()
                    self.close()

                return InputState.PROCESSED
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

    def apply(self):
        self.autopart = self.data.autopart.autopart

        self._disk_select_observer.proxy.SetSelectedDisks(self.selected_disks)
        self._disk_init_observer.proxy.SetDrivesToClear(self.selected_disks)

        if self.autopart and self.data.autopart.type is None:
            self.data.autopart.type = AUTOPART_TYPE_LVM

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

        self.storage.config.update()

        # If autopart is selected we want to remove whatever has been
        # created/scheduled to make room for autopart.
        # If custom is selected, we want to leave alone any storage layout the
        # user may have set up before now.
        self.storage.config.clear_non_existent = self.data.autopart.autopart

    def execute(self):
        print(_("Generating updated storage configuration"))
        try:
            doKickstartStorage(self.storage, self.data, self.instclass)
        except (StorageError, KickstartParseError) as e:
            log.error("storage configuration failed: %s", e)
            print(_("storage configuration failed: %s") % e)
            self.errors = [str(e)]

            # Prepare for reset.
            self._bootloader_observer.proxy.SetDrive(BOOTLOADER_DRIVE_UNSET)
            self._disk_init_observer.proxy.SetInitializationMode(CLEAR_PARTITIONS_ALL)
            self._disk_init_observer.proxy.SetInitializeLabelsEnabled(False)
            self.storage.autopart_type = self.data.autopart.type

            # The reset also calls self.storage.config.update().
            self.storage.reset()

            # Now set data back to the user's specified config.
            applyDiskSelection(self.storage, self.data, self.selected_disks)
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

        # Update disk list.
        self.update_disks()

        # Storage is ready.
        self._ready = True

        # Report that the storage spoke has been initialized.
        self.initialize_done()

    def update_disks(self):
        threadMgr.wait(THREAD_STORAGE)

        self.disks = sorted(getDisks(self.storage.devicetree),
                            key=lambda d: d.name)
        # if only one disk is available, go ahead and mark it as selected
        if len(self.disks) == 1:
            self._update_disk_list(self.disks[0])

class PartTypeSpoke(NormalTUISpoke):
    """ Partitioning options are presented here.

       .. inheritance-diagram:: PartTypeSpoke
          :parts: 3
    """
    category = SystemCategory

    def __init__(self, data, storage, payload, instclass):
        super().__init__(data, storage, payload, instclass)
        self.title = N_("Partitioning Options")
        self._container = None
        self.parttypelist = sorted(PARTTYPES.keys())

        # remember the original values so that we can detect a change
        self._disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
        self._orig_clearpart_type = self._disk_init_proxy.InitializationMode
        self._orig_mount_assign = len(self.data.mount.dataList()) != 0

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
        c = CheckboxWidget(title=_("Manually assign mount points") + _(" (EXPERIMENTAL)"),
                           completed=self._do_mount_assign)
        self._container.add(c, self._select_mount_assign)

        self.window.add_with_separator(self._container)

        message = _("Installation requires partitioning of your hard drive. "
                    "Select what space to use for the install target or manually assign mount points.")

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
            self.data.autopart.autopart = True
            self._disk_init_proxy.SetInitializationMode(self.clearPartType)
            self._disk_init_proxy.SetInitializeLabelsEnabled(True)
            self.data.mount.clear_mount_data()
        else:
            self.data.autopart.autopart = False
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
        # storage_initialize() processes all devices
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        selected_disks = disk_select_proxy.SelectedDisks
        disk_select_proxy.SetSelectedDisks([])

        storage_initialize(self.storage, self.data, self.storage.protected_dev_names)

        disk_select_proxy.SetSelectedDisks(selected_disks)
        self.data.mount.clear_mount_data()

    def input(self, args, key):
        """Grab the choice and update things"""
        if not self._container.process_user_input(key):
            # TRANSLATORS: 'c' to continue
            if key.lower() == C_('TUI|Spoke Navigation', 'c'):
                self.apply()
                self._ensure_init_storage()
                if self._do_mount_assign:
                    new_spoke = MountPointAssignSpoke(self.data, self.storage,
                                                      self.payload, self.instclass)
                else:
                    new_spoke = PartitionSchemeSpoke(self.data, self.storage,
                                                     self.payload, self.instclass)
                ScreenHandler.push_screen_modal(new_spoke)
                self.close()
                return InputState.PROCESSED
            else:
                return super().input(args, key)

        self.redraw()
        return InputState.PROCESSED


class PartitionSchemeSpoke(NormalTUISpoke):
    """ Spoke to select what partitioning scheme to use on disk(s). """
    category = SystemCategory

    def __init__(self, data, storage, payload, instclass):
        super().__init__(data, storage, payload, instclass)
        self.title = N_("Partition Scheme Options")
        self._container = None
        self.part_schemes = OrderedDict()
        pre_select = self.data.autopart.type or DEFAULT_AUTOPART_TYPE
        for item in AUTOPART_CHOICES:
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
                self.close()
                return InputState.PROCESSED
            else:
                return super().input(args, key)

        self.redraw()
        return InputState.PROCESSED

    def apply(self):
        """ Apply our selections. """
        self.data.autopart.type = self._selected_scheme_value

class MountDataRecorder(kickstart.MountData):
    """ An artificial subclass also recording changes. """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modified = False
        self.orig_format = None

class MountPointAssignSpoke(NormalTUISpoke):
    """ Assign mount points to block devices. """
    category = SystemCategory

    def __init__(self, data, storage, payload, instclass):
        super().__init__(data, storage, payload, instclass)
        self.title = N_("Assign mount points")
        self._container = None
        self._mds = None

        self._gather_mount_data_info()

    def _is_dev_usable(self, dev, selected_disks):
        maybe = not dev.protected and dev.size != Size(0)
        if maybe and selected_disks:
            # all device's disks have to be in selected disks
            maybe = set(selected_disks).issuperset({d.name for d in dev.disks})

        return maybe

    def _gather_mount_data_info(self):
        self._mds = OrderedDict()

        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        selected_disks = disk_select_proxy.SelectedDisks

        for device in self.storage.devicetree.leaves:
            if not self._is_dev_usable(device, selected_disks):
                continue

            fmt = device.format.type

            for ks_md in self.data.mount.dataList():
                if device is self.storage.devicetree.resolve_device(ks_md.device):
                    # already have a configuration for the device in ksdata,
                    # let's just copy it
                    mdrec = MountDataRecorder(device=ks_md.device, mount_point=ks_md.mount_point,
                                              format=ks_md.format, reformat=ks_md.reformat)
                    # and make sure the new version is put back
                    self.data.mount.remove_mount_data(ks_md)
                    mdrec.modified = True
                    break
            else:
                if device.format.mountable and device.format.mountpoint:
                    mpoint = device.format.mountpoint
                else:
                    mpoint = None

                mdrec = MountDataRecorder(device=device.path, mount_point=mpoint, format=fmt, reformat=False)

            mdrec.orig_format = fmt
            self._mds[device.name] = mdrec

    @property
    def indirect(self):
        return True

    def prompt(self, args=None):
        prompt = super().prompt(args)
        # TRANSLATORS: 's' to rescan devices
        prompt.add_option(C_('TUI|Spoke Navigation|Partitioning', 's'), _("rescan devices"))
        return prompt

    def refresh(self, args=None):
        super().refresh(args)

        self._container = ListColumnContainer(2)

        for md in self._mds.values():
            device = self.storage.devicetree.resolve_device(md.device)
            devspec = "%s (%s)" % (md.device, device.size)
            if md.format:
                devspec += "\n %s" % md.format
                if md.reformat:
                    devspec += "*"
                if md.mount_point:
                    devspec += ", %s" % md.mount_point
            w = TextWidget(devspec)
            self._container.add(w, self._configure_device, device)

        self.window.add_with_separator(self._container)

        message = _("Choose device from above to assign mount point and set format.\n" +
                    "Formats marked with * are new formats meaning ALL DATA on the original format WILL BE LOST!")
        self.window.add_with_separator(TextWidget(message))

    def _configure_device(self, device):
        md = self._mds[device.name]
        new_spoke = ConfigureDeviceSpoke(self.data, self.storage,
                                         self.payload, self.instclass, md)
        ScreenHandler.push_screen(new_spoke)

    def input(self, args, key):
        """ Grab the choice and update things. """
        if not self._container.process_user_input(key):
            # TRANSLATORS: 's' to rescan devices
            if key.lower() == C_('TUI|Spoke Navigation|Partitioning', 's'):
                text = _("Warning: This will revert all changes done so far.\nDo you want to proceed?\n")
                question_window = YesNoDialog(text)
                ScreenHandler.push_screen_modal(question_window)
                if question_window.answer:
                    # unset selected disks temporarily so that
                    # storage_initialize() processes all devices
                    disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
                    selected_disks = disk_select_proxy.SelectedDisks
                    disk_select_proxy.SetSelectedDisks([])

                    print(_("Scanning disks. This may take a moment..."))
                    storage_initialize(self.storage, self.data, self.storage.protected_dev_names)

                    disk_select_proxy.SetSelectedDisks(selected_disks)
                    self.data.mount.clear_mount_data()
                    self._gather_mount_data_info()
                self.redraw()
                return InputState.PROCESSED
            # TRANSLATORS: 'c' to continue
            elif key.lower() == C_('TUI|Spoke Navigation', 'c'):
                self.apply()

            return super().input(args, key)

        return InputState.PROCESSED

    def apply(self):
        """ Apply our selections. """
        for mount_data in self._mds.values():
            if mount_data.modified and (mount_data.reformat or mount_data.mount_point):
                self.data.mount.add_mount_data(mount_data)

class ConfigureDeviceSpoke(NormalTUISpoke):
    """ Assign mount point to a block device and (optionally) reformat it. """
    category = SystemCategory

    def __init__(self, data, storage, payload, instclass, mount_data):
        super().__init__(data, storage, payload, instclass)
        self._container = None
        self._mount_data = mount_data
        self.title = N_("Configure device: %s") % mount_data.device

        self._supported_filesystems = [fmt.type for fmt in get_supported_filesystems()]

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh( args)

        self._container = ListColumnContainer(1)

        mount_point_title = _("Mount point")
        reformat_title = _("Reformat")
        none_msg = _("none")

        fmt = get_format(self._mount_data.format)
        if fmt and fmt.mountable:
            dialog = Dialog(mount_point_title, conditions=[self._check_assign_mount_point])
            value = self._mount_data.mount_point or none_msg
            self._container.add(EntryWidget(dialog.title, value), self._assign_mount_point, dialog)
        elif fmt and fmt.type is None:
            # mount point cannot be set for no format
            # (fmt.name = "Unknown" in this case which would look weird)
            self._container.add(EntryWidget(mount_point_title, none_msg))
        else:
            # mount point cannot be set for format that is not mountable, just
            # show the format's name in square brackets instead
            self._container.add(EntryWidget(mount_point_title, fmt.name))

        dialog = Dialog(_("Format"), conditions=[self._check_format])
        value = self._mount_data.format or none_msg
        self._container.add(EntryWidget(dialog.title, value), self._set_format, dialog)

        if ((self._mount_data.orig_format and self._mount_data.orig_format != self._mount_data.format)
           or self._mount_data.mount_point == "/"):
            # changing format implies reformat and so does "/" mount point
            self._container.add(CheckboxWidget(title=reformat_title, completed=self._mount_data.reformat))
        else:
            self._container.add(CheckboxWidget(title=reformat_title, completed=self._mount_data.reformat),
                                self._switch_reformat)

        self.window.add_with_separator(self._container)
        self.window.add_with_separator(TextWidget(_("Choose from above to assign mount point and/or set format.")))

    def _check_format(self, user_input, report_func):
        user_input = user_input.lower()
        if user_input in self._supported_filesystems:
            return True
        else:
            msg = _("Invalid or unsupported format given")
            msg += "\n"
            msg += (_("Supported formats: %s") % ", ".join(self._supported_filesystems))
            report_func(msg)
            return False

    def _check_assign_mount_point(self, user_input, report_func):
        # a valid mount point must start with / or user set nothing
        if user_input == "" or user_input.startswith("/"):
            return True
        else:
            report_func(_("Invalid mount point given"))
            return False

    def input(self, args, key):
        """ Grab the choice and update things. """
        if not self._container.process_user_input(key):
            return super().input(args, key)

        self.redraw()
        return InputState.PROCESSED

    def apply(self):
        # nothing to do here, the callbacks below directly modify the data
        pass

    def _switch_reformat(self, args):
        self._mount_data.modified = True
        self._mount_data.reformat = not self._mount_data.reformat

    def _set_format(self, dialog):
        self._mount_data.modified = True
        value = dialog.run()

        if value != self._mount_data.format:
            self._mount_data.reformat = True
            self._mount_data.format = value

    def _assign_mount_point(self, dialog):
        self._mount_data.modified = True
        value = dialog.run()

        if value:
            self._mount_data.mount_point = value
        else:
            self._mount_data.mount_point = None
        if self._mount_data.mount_point == "/":
            self._mount_data.reformat = True
