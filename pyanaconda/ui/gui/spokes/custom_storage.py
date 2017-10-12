#
# Custom partitioning classes.
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

# TODO:
# - Deleting an LV is not reflected in available space in the bottom left.
#   - this is only true for preexisting LVs
# - Device descriptions, suggested sizes, etc. should be moved out into a support file.
# - Tabbing behavior in the accordion is weird.
# - Implement striping and mirroring for LVM.
# - Activating reformat should always enable resize for existing devices.

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("AnacondaWidgets", "3.3")

from gi.repository import Gdk, Gtk
from gi.repository.AnacondaWidgets import MountpointSelector

from pykickstart.constants import CLEARPART_TYPE_NONE

from pyanaconda.i18n import _, N_, CP_, C_
from pyanaconda.product import productName, productVersion, translated_new_install_name
from pyanaconda.threading import AnacondaThread, threadMgr
from pyanaconda.constants import THREAD_EXECUTE_STORAGE, THREAD_STORAGE, THREAD_CUSTOM_STORAGE_INIT
from pyanaconda.constants import SIZE_UNITS_DEFAULT, UNSUPPORTED_FILESYSTEMS
from pyanaconda.iutil import lowerASCII
from pyanaconda.bootloader import BootLoaderError
from pyanaconda.kickstart import refreshAutoSwapSize
from pyanaconda import network

from blivet import devicefactory
from blivet.formats import get_format
from blivet.size import Size
from blivet.devicefactory import DEVICE_TYPE_LVM
from blivet.devicefactory import DEVICE_TYPE_BTRFS
from blivet.devicefactory import DEVICE_TYPE_PARTITION
from blivet.devicefactory import DEVICE_TYPE_MD
from blivet.devicefactory import DEVICE_TYPE_DISK
from blivet.devicefactory import DEVICE_TYPE_LVM_THINP
from blivet.devicefactory import SIZE_POLICY_AUTO
from blivet.devicefactory import is_supported_device_type
from blivet.osinstall import find_existing_installations, Root
from blivet.autopart import do_autopart
from blivet.errors import StorageError
from blivet.errors import NoDisksError
from blivet.errors import NotEnoughFreeSpaceError
from blivet.devicelibs import raid, crypto
from blivet.devices import LUKSDevice, MDRaidArrayDevice, LVMVolumeGroupDevice
from blivet.platform import platform

from pyanaconda.storage_utils import ui_storage_logger, device_type_from_autopart, storage_checker, \
    verify_luks_devices_have_key, get_supported_filesystems
from pyanaconda.storage_utils import DEVICE_TEXT_PARTITION, DEVICE_TEXT_MAP, DEVICE_TEXT_MD
from pyanaconda.storage_utils import PARTITION_ONLY_FORMAT_TYPES, MOUNTPOINT_DESCRIPTIONS
from pyanaconda.storage_utils import NAMED_DEVICE_TYPES, CONTAINER_DEVICE_TYPES
from pyanaconda.storage_utils import try_populate_devicetree
from pyanaconda.storage_utils import filter_unsupported_disklabel_devices
from pyanaconda import storage_utils

from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.helpers import StorageCheckHandler
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.passphrase import PassphraseDialog
from pyanaconda.ui.gui.spokes.lib.accordion import update_selector_from_device, Accordion, Page, CreateNewPage, UnknownPage
from pyanaconda.ui.gui.spokes.lib.refresh import RefreshDialog
from pyanaconda.ui.gui.spokes.lib.summary import ActionSummaryDialog

from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import size_from_entry
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import validate_label, validate_mountpoint, get_raid_level
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import selectedRaidLevel, raidLevelSelection, defaultRaidLevel, requiresRaidSelection, containerRaidLevelsSupported, raidLevelsSupported, defaultContainerRaidLevel
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import get_container_type, RAID_NOT_ENOUGH_DISKS
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import AddDialog, ConfirmDeleteDialog, DisksDialog, ContainerDialog

from pyanaconda.ui.gui.utils import setViewportBackground, fancy_set_sensitive, ignoreEscape
from pyanaconda.ui.gui.utils import really_hide, really_show, timed_action, escape_markup
from pyanaconda.ui.categories.system import SystemCategory

from functools import wraps
from itertools import chain

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["CustomPartitioningSpoke"]

NOTEBOOK_LABEL_PAGE = 0
NOTEBOOK_DETAILS_PAGE = 1
NOTEBOOK_LUKS_PAGE = 2
NOTEBOOK_UNEDITABLE_PAGE = 3
NOTEBOOK_INCOMPLETE_PAGE = 4

NEW_CONTAINER_TEXT = N_("Create a new %(container_type)s ...")
CONTAINER_TOOLTIP = N_("Create or select %(container_type)s")

DEVICE_CONFIGURATION_ERROR_MSG = N_("Device reconfiguration failed. <a href=\"\">Click for "
                                    "details.</a>")
UNRECOVERABLE_ERROR_MSG = N_("Storage configuration reset due to unrecoverable "
                             "error. <a href=\"\">Click for details.</a>")

def dev_type_from_const(dev_type_const):
    """ Return integer corresponding to name for device type defined as
        a constant in blivet.devicefactory.

        :param str dev_type_const: the name of a DEVICE_TYPE_*
        :returns: the corresponding integer code, if there is one
        :rtype: int or NoneType
    """
    return getattr(devicefactory, dev_type_const, None)

def ui_storage_logged(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        with ui_storage_logger():
            return func(*args, **kwargs)

    return decorated

class CustomPartitioningSpoke(NormalSpoke, StorageCheckHandler):
    """
       .. inheritance-diagram:: CustomPartitioningSpoke
          :parts: 3
    """
    builderObjects = ["customStorageWindow", "containerStore", "deviceTypeStore",
                      "partitionStore", "raidStoreFiltered", "raidLevelStore",
                      "addImage", "removeImage", "settingsImage",
                      "mountPointCompletion", "mountPointStore", "fileSystemStore"]
    mainWidgetName = "customStorageWindow"
    uiFile = "spokes/custom_storage.glade"
    helpFile = "CustomSpoke.xml"

    category = SystemCategory
    title = N_("MANUAL PARTITIONING")

    # The maximum number of places to show when displaying a size
    MAX_SIZE_PLACES = 2

    # If the user enters a smaller size, the GUI changes it to this value
    MIN_SIZE_ENTRY = Size("1 MiB")

    def __init__(self, data, storage, payload, instclass):
        StorageCheckHandler.__init__(self)
        NormalSpoke.__init__(self, data, storage, payload, instclass)

        self._back_already_clicked = False
        self._storage_playground = None

        self.passphrase = ""

        self._devices = []
        self._error = None
        self._hidden_disks = []
        self._fs_types = set()             # set of supported fstypes
        self._free_space = Size(0)

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

        self._unhide_unusable_disks()

        new_swaps = (dev for dev in self.get_new_devices() if dev.format.type == "swap")
        self.storage.set_fstab_swaps(new_swaps)

        # update the global passphrase
        self.data.autopart.passphrase = self.passphrase

        # make sure any device/passphrase pairs we've obtained are remembered
        for device in self.storage.devices:
            if device.format.type == "luks" and not device.format.exists:
                if not device.format.has_key:
                    device.format.passphrase = self.passphrase

                self.storage.save_passphrase(device)

        hubQ.send_ready("StorageSpoke", True)

    @property
    def indirect(self):
        return True

    # This spoke has no status since it's not in a hub
    @property
    def status(self):
        return None

    def _grabObjects(self):
        self._configureBox = self.builder.get_object("configureBox")

        self._partitionsViewport = self.builder.get_object("partitionsViewport")
        self._partitionsNotebook = self.builder.get_object("partitionsNotebook")

        # Connect partitionsNotebook focus events to scrolling in the parent viewport
        partitionsNotebookViewport = self.builder.get_object("partitionsNotebookViewport")
        self._partitionsNotebook.set_focus_vadjustment(Gtk.Scrollable.get_vadjustment(partitionsNotebookViewport))

        self._pageLabel = self.builder.get_object("pageLabel")

        self._availableSpaceLabel = self.builder.get_object("availableSpaceLabel")
        self._totalSpaceLabel = self.builder.get_object("totalSpaceLabel")
        self._summaryLabel = self.builder.get_object("summary_label")

        # Buttons
        self._addButton = self.builder.get_object("addButton")
        self._applyButton = self.builder.get_object("applyButton")
        self._configButton = self.builder.get_object("configureButton")
        self._removeButton = self.builder.get_object("removeButton")
        self._resetButton = self.builder.get_object("resetButton")

        # Detailed configuration stuff
        self._encryptCheckbox = self.builder.get_object("encryptCheckbox")
        self._fsCombo = self.builder.get_object("fileSystemTypeCombo")
        self._fsStore = self.builder.get_object("fileSystemStore")
        self._labelEntry = self.builder.get_object("labelEntry")
        self._mountPointEntry = self.builder.get_object("mountPointEntry")
        self._nameEntry = self.builder.get_object("nameEntry")
        self._raidLevelCombo = self.builder.get_object("raidLevelCombo")
        self._raidLevelLabel = self.builder.get_object("raidLevelLabel")
        self._reformatCheckbox = self.builder.get_object("reformatCheckbox")
        self._sizeEntry = self.builder.get_object("sizeEntry")
        self._typeStore = self.builder.get_object("deviceTypeStore")
        self._typeCombo = self.builder.get_object("deviceTypeCombo")
        self._modifyContainerButton = self.builder.get_object("modifyContainerButton")
        self._containerCombo = self.builder.get_object("containerCombo")
        self._containerStore = self.builder.get_object("containerStore")
        self._deviceDescLabel = self.builder.get_object("deviceDescLabel")

        # Set the fixed-size properties on the volume group ComboBox renderers to
        # False so that the "Create a new..." row can overlap with the free space
        # on the other rows. These properties are not accessible from glade.
        cell_area = self._containerCombo.get_area()
        descRenderer = self.builder.get_object("descRenderer")
        freeSpaceRenderer = self.builder.get_object("freeSpaceRenderer")
        cell_area.cell_set_property(descRenderer, "fixed-size", False)
        cell_area.cell_set_property(freeSpaceRenderer, "fixed-size", False)

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
        self.initialize_start()
        self._grabObjects()

        setViewportBackground(self.builder.get_object("availableSpaceViewport"), "#db3279")
        setViewportBackground(self.builder.get_object("totalSpaceViewport"), "#60605b")

        self._raidStoreFilter.set_visible_func(self._raid_level_visible)

        self._accordion = Accordion()
        self._partitionsViewport.add(self._accordion)

        # Connect viewport scrolling with accordion focus events
        self._accordion.set_focus_hadjustment(Gtk.Scrollable.get_hadjustment(self._partitionsViewport))
        self._accordion.set_focus_vadjustment(Gtk.Scrollable.get_vadjustment(self._partitionsViewport))

        threadMgr.add(AnacondaThread(name=THREAD_CUSTOM_STORAGE_INIT, target=self._initialize))

    def _initialize(self):
        """ Populate the set of valid filesystem types from the format classes.

            Restrict the set to ones that we might allow users to select.
        """
        self._fs_types = {fs.name for fs in get_supported_filesystems()} - set(UNSUPPORTED_FILESYSTEMS)

        # report that the custom spoke has been initialized
        self.initialize_done()

    @property
    def _clearpartDevices(self):
        return [d for d in self._devices if d.name in self.data.clearpart.drives and d.partitioned]

    @property
    def unusedDevices(self):
        unused_devices = [d for d in self._storage_playground.unused_devices
                                if d.disks and d.media_present and
                                not d.partitioned and (d.direct or d.isleaf)]
        # add incomplete VGs and MDs
        incomplete = [d for d in self._storage_playground.devicetree._devices
                            if not getattr(d, "complete", True)]
        unused_devices.extend(incomplete)
        unused_devices.extend(d for d in self._storage_playground.partitioned if not d.format.supported)
        return unused_devices

    @property
    def bootLoaderDevices(self):
        devices = []
        format_types = ["biosboot", "prepboot"]
        for device in self._devices:
            if device.format.type not in format_types:
                continue

            disk_names = (d.name for d in device.disks)
            # bootDrive may not be setup because it IS one of these.
            if not self.data.bootloader.bootDrive or \
               self.data.bootloader.bootDrive in disk_names:
                devices.append(device)

        return devices

    @property
    def _currentFreeInfo(self):
        return self._storage_playground.get_free_space(clear_part_type=CLEARPART_TYPE_NONE)

    def _setCurrentFreeSpace(self):
        """Add up all the free space on selected disks and return it as a Size."""
        self._free_space = sum(f[0] for f in self._currentFreeInfo.values())

    def _currentTotalSpace(self):
        """Add up the sizes of all selected disks and return it as a Size."""
        totalSpace = sum((disk.size for disk in self._clearpartDevices),
                         Size(0))
        return totalSpace

    def _updateSpaceDisplay(self):
        # Set up the free space/available space displays in the bottom left.
        self._setCurrentFreeSpace()

        self._availableSpaceLabel.set_text(str(self._free_space))
        self._totalSpaceLabel.set_text(str(self._currentTotalSpace()))

        count = len(self.data.clearpart.drives)
        summary = CP_("GUI|Custom Partitioning",
                "%d _storage device selected",
                "%d _storage devices selected",
                count) % count

        self._summaryLabel.set_text(summary)
        self._summaryLabel.set_use_underline(True)

    @ui_storage_logged
    def _hide_unusable_disks(self):
        self._hidden_disks = []

        for disk in self._storage_playground.disks:
            if disk.protected or not disk.media_present:
                # hide removable disks containing install media
                self._hidden_disks.append(disk)
                self._storage_playground.devicetree.hide(disk)

    def _unhide_unusable_disks(self):
        for disk in reversed(self._hidden_disks):
            self._storage_playground.devicetree.unhide(disk)

    def _reset_storage(self):
        self._storage_playground = self.storage.copy()
        self._hide_unusable_disks()
        self._devices = self._storage_playground.devices

    def refresh(self):
        self.clear_errors()
        NormalSpoke.refresh(self)

        # Make sure the storage spoke execute method has finished before we
        # copy the storage instance.
        for thread_name in [THREAD_EXECUTE_STORAGE, THREAD_STORAGE]:
            threadMgr.wait(thread_name)

        self._back_already_clicked = False

        self.passphrase = self.data.autopart.passphrase
        self._reset_storage()
        self._do_refresh()

        self._updateSpaceDisplay()
        self._applyButton.set_sensitive(False)

    def _get_container_names(self):
        for data in self._containerStore:
            yield data[0]

    def _get_fstype(self, fstypeCombo):
        itr = fstypeCombo.get_active_iter()
        if not itr:
            return None

        model = fstypeCombo.get_model()
        return model[itr][0]

    def _get_autopart_type(self, autopartTypeCombo):
        itr = autopartTypeCombo.get_active_iter()
        if not itr:
            return None

        model = autopartTypeCombo.get_model()
        return model[itr][1]

    def _change_autopart_type(self, autopartTypeCombo):
        """
        This is called when the autopart type combo on the left hand side of
        custom partitioning is changed.  We already know how to handle the case
        where the user changes the type and then clicks the autopart link
        button.  This handles the case where the user changes the type and then
        clicks the '+' button.

        """

        self.data.autopart.type = self._get_autopart_type(autopartTypeCombo)

    def get_new_devices(self):
        # A device scheduled for formatting only belongs in the new root.
        new_devices = [d for d in self._devices if d.direct and
                                                   not d.format.exists and
                                                   not d.partitioned]

        # If mountpoints have been assigned to any existing devices, go ahead
        # and pull those in along with any existing swap devices. It doesn't
        # matter if the formats being mounted exist or not.
        new_mounts = [d for d in self._storage_playground.mountpoints.values() if d.exists]
        if new_mounts or new_devices:
            new_devices.extend(self._storage_playground.mountpoints.values())
            new_devices.extend(self.bootLoaderDevices)

        new_devices = list(set(new_devices))

        return new_devices

    def _set_page_label_text(self):
        if self._accordion.is_multiselection:
            select_tmpl = _("%(items_selected)s of %(items_total)s mount points in %(page_name)s")
            span_tmpl = "<span size='large' weight='bold' fgcolor='%s'>%s</span>"
            pages_count = ""
            for page in self._accordion.all_pages:
                if not page.members:
                    continue

                if page.selected_members:
                    highlight_color = "black"
                    page_text_tmpl = select_tmpl
                else:
                    highlight_color = "gray"
                    page_text_tmpl = "<span fgcolor='gray'>%s</span>" % escape_markup(select_tmpl)

                selected_str = span_tmpl % (escape_markup(highlight_color),
                                            escape_markup(str(len(page.selected_members))))
                total_str = span_tmpl % (escape_markup(highlight_color),
                                         escape_markup(str(len(page.members))))
                page_name = span_tmpl % (escape_markup(highlight_color),
                                         escape_markup(page.pageTitle))

                page_line = page_text_tmpl % {"items_selected" : selected_str,
                                              "items_total"    : total_str,
                                              "page_name"      : page_name}
                pages_count += page_line + "\n"

            self._pageLabel.set_markup(_("Please select a single mount point to edit properties.\n\n"
                                         "You have currently selected:\n"
                                         "%s") % (pages_count))
        else:
            self._pageLabel.set_text(_("When you create mount points for "
                    "your %(name)s %(version)s installation, you'll be able to "
                    "view their details here.") % {"name"    : productName,
                                                   "version" : productVersion})

    def _populate_accordion(self):
        # Make sure we start with a clean state.
        self._accordion.remove_all_pages()

        new_devices = filter_unsupported_disklabel_devices(self.get_new_devices())
        all_devices = filter_unsupported_disklabel_devices(self._devices)
        unused_devices = filter_unsupported_disklabel_devices(self.unusedDevices)

        # Now it's time to populate the accordion.
        log.debug("ui: devices=%s", [d.name for d in all_devices])
        log.debug("ui: unused=%s", [d.name for d in unused_devices])
        log.debug("ui: new_devices=%s", [d.name for d in new_devices])

        ui_roots = []
        for root in self._storage_playground.roots:
            root_devices = list(chain(root.swaps, root.mounts.values()))
            # Don't make a page if none of the root's devices are left.
            # Also, only include devices in an old page if the format is intact.
            if not any(d for d in root_devices if d in all_devices and d.disks and
                       (root.name == translated_new_install_name() or d.format.exists)):
                continue

            if not filter_unsupported_disklabel_devices(root_devices):
                continue

            ui_roots.append(root)

        # If we've not yet run autopart, add an instance of CreateNewPage.  This
        # ensures it's only added once.
        if not new_devices:
            page = CreateNewPage(translated_new_install_name(),
                                 self.on_create_clicked,
                                 self._change_autopart_type,
                                 partitionsToReuse=bool(ui_roots) or bool(unused_devices))
            self._accordion.add_page(page, cb=self.on_page_clicked)

            self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
            self._set_page_label_text()

        else:
            swaps = [d for d in new_devices if d.format.type == "swap"]
            mounts = dict((d.format.mountpoint, d) for d in new_devices
                                if getattr(d.format, "mountpoint", None))

            for device in new_devices:
                if device in self.bootLoaderDevices:
                    mounts[device.format.name] = device

            new_root = Root(mounts=mounts, swaps=swaps, name=translated_new_install_name())
            ui_roots.insert(0, new_root)

        # Add in all the existing (or autopart-created) operating systems.
        for root in ui_roots:
            page = Page(root.name)
            self._accordion.add_page(page, cb=self.on_page_clicked)

            for (mountpoint, device) in root.mounts.items():
                # by using all_devices we've already accounted for devices on unsupported disklabels
                if device not in all_devices or \
                   not device.disks or \
                   (root.name != translated_new_install_name() and not device.format.exists):
                    continue

                selector = page.add_selector(device, self.on_selector_clicked,
                                            mountpoint=mountpoint)
                selector.root = root

            for device in root.swaps:
                # by using all_devices we've already accounted for devices on unsupported disklabels
                if device not in all_devices or \
                   (root.name != translated_new_install_name() and not device.format.exists):
                    continue

                selector = page.add_selector(device, self.on_selector_clicked)
                selector.root = root

            page.show_all()

        # Anything that doesn't go with an OS we understand?  Put it in the Other box.
        if self.unusedDevices:
            page = UnknownPage(_("Unknown"))
            self._accordion.add_page(page, cb=self.on_page_clicked)

            for u in sorted(unused_devices, key=lambda d: d.name):
                page.add_selector(u, self.on_selector_clicked)

            page.show_all()

    def _do_refresh(self, mountpointToShow=None):
        # block mountpoint selector signal handler for now
        self._initialized = False
        self._accordion.clear_current_selector()

        # Start with buttons disabled, since nothing is selected.
        self._removeButton.set_sensitive(False)
        self._configButton.set_sensitive(False)

        # populate the accorion with roots and mount points
        self._populate_accordion()

        # And then open the first page by default.  Most of the time, this will
        # be fine since it'll be the new installation page.
        self._initialized = True
        firstPage = self._accordion.all_pages[0]
        self._accordion.expand_page(firstPage.pageTitle)
        self._show_mountpoint(page=firstPage, mountpoint=mountpointToShow)

        self._applyButton.set_sensitive(False)
        self._resetButton.set_sensitive(len(self._storage_playground.devicetree.actions.find()) > 0)

    ###
    ### RIGHT HAND SIDE METHODS
    ###
    def add_new_selector(self, device):
        """ Add an entry for device to the new install Page. """
        page = self._accordion.find_page_by_title(translated_new_install_name())
        devices = [device]
        if not page.members:
            # remove the CreateNewPage and replace it with a regular Page
            expander = self._accordion.find_page_by_title(translated_new_install_name()).get_parent()
            expander.remove(expander.get_child())

            page = Page(translated_new_install_name())
            expander.add(page)

            # also pull in biosboot and prepboot that are on our boot disk
            devices.extend(self.bootLoaderDevices)
            devices = list(set(devices))

        for _device in devices:
            page.add_selector(_device, self.on_selector_clicked)

        page.show_all()

    def _update_selectors(self):
        """ Update all btrfs selectors' size properties. """
        # we're only updating selectors in the new root. problem?
        page = self._accordion.find_page_by_title(translated_new_install_name())
        for selector in page.members:
            update_selector_from_device(selector, selector.device)

    def _replace_device(self, **kwargs):
        """ Create a replacement device and update the device selector. """
        selector = kwargs.pop("selector", None)
        dev_type = kwargs.pop("device_type")
        size = kwargs.pop("size")
        new_device = self._storage_playground.factory_device(dev_type, size, **kwargs)

        self._devices = self._storage_playground.devices

        if selector:
            # update the selector with the new device and its size
            update_selector_from_device(selector, new_device)

    def _update_device_in_selectors(self, old_device, new_device):
        for s in self._accordion.all_selectors:
            if s._device == old_device:
                update_selector_from_device(s, new_device)

    def _update_all_devices_in_selectors(self):
        for s in self._accordion.all_selectors:
            for new_device in self._storage_playground.devices:
                if ((s._device.name == new_device.name) or
                    (getattr(s._device, "req_name", 1) == getattr(new_device, "req_name", 2)) and
                    s._device.type == new_device.type and
                    s._device.format.type == new_device.format.type):
                    update_selector_from_device(s, new_device)
                    break
            else:
                log.warning("failed to replace device: %s", s._device)

    def _add_device_type(self, dev_type_const):
        self._typeStore.append([_(DEVICE_TEXT_MAP[dev_type_from_const(dev_type_const)]),
                                dev_type_const])

    def _validate_mountpoint(self, mountpoint, device, device_type, new_fs_type,
                            reformat, encrypted, raid_level):
        """ Validate various aspects of a mountpoint.

            :param str mountpoint: the mountpoint
            :param device: blivet.devices.Device instance
            :param int device_type: one of an enumeration of device types
            :param str new_fs_type: string representing the new filesystem type
            :param bool reformat: whether the device is to be reformatted
            :param bool encrypted: whether the device is to be encrypted
            :param raid_level: instance of blivet.devicelibs.raid.RAIDLevel or None
        """
        error = None
        if device_type not in (DEVICE_TYPE_PARTITION, DEVICE_TYPE_MD) and \
           mountpoint == "/boot/efi":
            error = (_("/boot/efi must be on a device of type %(oneFsType)s or %(anotherFsType)s")
                       % {"oneFsType": _(DEVICE_TEXT_PARTITION), "anotherFsType": _(DEVICE_TEXT_MD)})
        elif device_type != DEVICE_TYPE_PARTITION and \
             new_fs_type in PARTITION_ONLY_FORMAT_TYPES:
            error = (_("%(fs)s must be on a device of type %(type)s")
                       % {"fs" : new_fs_type, "type" : _(DEVICE_TEXT_PARTITION)})
        elif mountpoint and encrypted and mountpoint.startswith("/boot"):
            error = _("%s cannot be encrypted") % mountpoint
        elif encrypted and new_fs_type in PARTITION_ONLY_FORMAT_TYPES:
            error = _("%s cannot be encrypted") % new_fs_type
        elif mountpoint == "/" and device.format.exists and not reformat:
            error = _("You must create a new file system on the root device.")

        if not error and \
           (raid_level is not None or requiresRaidSelection(device_type)) and \
           raid_level not in raidLevelsSupported(device_type):
            error = _("Device does not support RAID level selection %s.") % raid_level

        if not error and raid_level is not None:
            min_disks = raid_level.min_members
            if len(self._device_disks) < min_disks:
                error = _(RAID_NOT_ENOUGH_DISKS) % {"level": raid_level,
                                                    "min" : min_disks,
                                                    "count": len(self._device_disks)}

        return error

    def _update_size_props(self):
        self._update_selectors()
        self._updateSpaceDisplay()

    def _try_replace_device(self, selector, removed_device, new_device_info,
                            old_device_info):
        if removed_device:
            # we don't want to pass the device if we removed it
            new_device_info["device"] = None
        try:
            self._replace_device(selector=selector, **new_device_info)
            return True
        except StorageError as e:
            log.error("factory_device failed: %s", e)
            # the factory's error handling has replaced all of the
            # devices with copies, so update the selectors' devices
            # accordingly
            self._update_all_devices_in_selectors()
            self._error = e
            self.set_warning(_(DEVICE_CONFIGURATION_ERROR_MSG))

            if not removed_device:
                # nothing more to do
                return True
            else:
                # we have removed the old device so we now have to re-create it
                # the disks need to be updated since we've replaced all
                # of the devices with copies in the devicefactory error
                # handler
                old_disk_names = (d.name for d in old_device_info["disks"])
                old_device_info["disks"] = [self._storage_playground.devicetree.get_device_by_name(n) for n in old_disk_names]
                try:
                    self._replace_device(selector=selector, **old_device_info)
                    return True
                except StorageError as e:
                    # failed to recover.
                    self.refresh()  # this calls self.clear_errors
                    self._error = e
                    self.set_warning(_(UNRECOVERABLE_ERROR_MSG))
                    return False

    @ui_storage_logged
    def _revert_reformat(self, device):
        """ Revert reformat.

            :param device: the device being displayed
            :type device: :class:`blivet.devices.StorageDevice`
        """
        use_dev = device.raw_device

        # figure out the existing device and reset it
        if not use_dev.format.exists:
            original_device = use_dev
        else:
            original_device = device

        log.debug("resetting device %s", original_device.name)
        self._storage_playground.reset_device(original_device)

    @ui_storage_logged
    def _handle_size_change(self, size, old_size, device):
        """ Handle size change.

            :param device: the device being displayed
            :type device: :class:`blivet.devices.StorageDevice`
        """
        use_dev = device.raw_device

        # If a LUKS device is being displayed, adjust the size
        # to the appropriate size for the raw device.
        use_size = size
        use_old_size = old_size
        if use_dev is not device:
            use_size = size + crypto.LUKS_METADATA_SIZE
            use_old_size = use_dev.size

        # bound size to boundaries given by the device
        use_size = use_dev.align_target_size(use_size)
        use_size = storage_utils.bound_size(use_size, use_dev, use_old_size)
        use_size = use_dev.align_target_size(use_size)

        # And then we need to re-check that the max size is actually
        # different from the current size.
        _changed_size = False
        if use_size != device.size and size == device.current_size:
            # size has been set back to its original value
            actions = self._storage_playground.devicetree.actions.find(
               action_type="resize",
               devid=use_dev.id
            )
            for action in reversed(actions):
                self._storage_playground.devicetree.actions.remove(action)
                _changed_size = True
        elif use_size != use_dev.size:
            log.debug("scheduling resize of device %s to %s", use_dev.name, use_size)

            try:
                self._storage_playground.resize_device(use_dev, use_size)
            except StorageError as e:
                log.error("failed to schedule device resize: %s", e)
                use_dev.size = use_old_size
                self._error = e
                self.set_warning(_("Device resize request failed. "
                                   "<a href=\"\">Click for details.</a>"))
            else:
                _changed_size = True

        if _changed_size:
            log.debug("new size: %s", use_dev.size)
            log.debug("target size: %s", use_dev.target_size)

            # update the selector's size property
            # The selector shows the visible disk, so it is necessary
            # to use device and size, which are the values visible to
            # the user.
            for s in self._accordion.all_selectors:
                if s._device == device:
                    s.size = str(device.size)

            # update size props of all btrfs devices' selectors
            self._update_size_props()

    @ui_storage_logged
    def _handle_encryption_change(self, encrypted, device, old_device, selector):
        if not encrypted:
            log.info("removing encryption from %s", device.name)
            self._storage_playground.destroy_device(device)
            self._devices.remove(device)
            old_device = device
            device = device.slave
            selector.device = device
            self._update_device_in_selectors(old_device, device)
        else:
            log.info("applying encryption to %s", device.name)
            old_device = device
            new_fmt = get_format("luks", device=device.path)
            self._storage_playground.format_device(device, new_fmt)
            luks_dev = LUKSDevice("luks-" + device.name,
                                  parents=[device])
            self._storage_playground.create_device(luks_dev)
            self._devices.append(luks_dev)
            device = luks_dev
            selector.device = device
            self._update_device_in_selectors(old_device, device)

        self._devices = self._storage_playground.devices

        # possibly changed device and old_device, need to return the new ones
        return (device, old_device)

    @ui_storage_logged
    def _do_reformat(self, device, mountpoint, label, changed_encryption,
                     encrypted, selector, fs_type):
        self.clear_errors()
        #
        # ENCRYPTION
        #
        old_device = None
        if changed_encryption:
            device, old_device = self._handle_encryption_change(encrypted,
                                                device, old_device, selector)
        #
        # FORMATTING
        #
        log.info("scheduling reformat of %s as %s", device.name, fs_type)
        old_format = device.format
        new_format = get_format(fs_type,
                               mountpoint=mountpoint, label=label,
                               device=device.path)
        try:
            self._storage_playground.format_device(device, new_format)
        except (StorageError, ValueError) as e:
            log.error("failed to register device format action: %s", e)
            device.format = old_format
            self._error = e
            self.set_warning(_("Device reformat request failed. "
                               "<a href=\"\">Click for details.</a>"))
        else:
            # first, remove this selector from any old install page(s)
            new_selector = None
            for (page, _selector) in self._accordion.all_members:
                if _selector.device in (device, old_device):
                    if page.pageTitle == translated_new_install_name():
                        new_selector = _selector
                        continue

                    page.remove_selector(_selector)
                    if not page.members:
                        log.debug("removing empty page %s", page.pageTitle)
                        self._accordion.remove_page(page.pageTitle)

            # either update the existing selector or add a new one
            if new_selector:
                update_selector_from_device(new_selector, device)
            else:
                self.add_new_selector(device)

        # possibly changed device, need to return the new one
        return device

    def _save_right_side(self, selector):
        """ Save settings from RHS and apply changes to the device.

            This method must never trigger a call to self._do_refresh.
        """

        self.clear_errors()

        # check if initialized and have something to operate on
        if not self._initialized or not selector:
            return

        # only call _save_right_side if on the right page and some changes need
        # to be saved (sensitivity of the Update Settings button reflects that)
        if self._partitionsNotebook.get_current_page() != NOTEBOOK_DETAILS_PAGE or \
           not self._applyButton.get_sensitive():
            return

        device = selector.device
        if device not in self._devices:
            # just-removed device
            return

        self._back_already_clicked = False

        # dictionaries for many, many pieces of information about the device and
        # requested changes, minimum required entropy for LUKS creation is
        # always the same
        new_device_info = {"min_luks_entropy": crypto.MIN_CREATE_ENTROPY}
        old_device_info = {"min_luks_entropy": crypto.MIN_CREATE_ENTROPY}

        new_device_info["device"] = device
        use_dev = device.raw_device

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

        old_device_info["name"] = old_name
        new_device_info["name"] = name

        # SIZE
        old_size = device.size

        # If the size text hasn't changed at all from that displayed,
        # assume no change intended.
        if old_size.human_readable(max_places=self.MAX_SIZE_PLACES) == self._sizeEntry.get_text():
            size = old_size
        else:
            size = size_from_entry(
               self._sizeEntry,
               lower_bound=self.MIN_SIZE_ENTRY,
               units=SIZE_UNITS_DEFAULT
            )
        changed_size = ((use_dev.resizable or not use_dev.exists) and
                        size != old_size)
        old_device_info["size"] = old_size
        new_device_info["size"] = size

        # DEVICE TYPE
        device_type = self._get_current_device_type()
        old_device_type = devicefactory.get_device_type(device)
        changed_device_type = (old_device_type != device_type)
        old_device_info["device_type"] = old_device_type
        new_device_info["device_type"] = device_type

        # REFORMAT
        reformat = self._reformatCheckbox.get_active()
        log.debug("reformat: %s", reformat)

        # FS TYPE
        old_fs_type = device.format.type
        fs_type_index = self._fsCombo.get_active()
        fs_type_str = self._fsCombo.get_model()[fs_type_index][0]
        new_fs = get_format(fs_type_str)
        fs_type = new_fs.type
        changed_fs_type = (old_fs_type != fs_type)
        old_device_info["fstype"] = old_fs_type
        new_device_info["fstype"] = fs_type

        # ENCRYPTION
        old_encrypted = isinstance(device, LUKSDevice)
        encrypted = self._encryptCheckbox.get_active() and self._encryptCheckbox.is_sensitive()
        changed_encryption = (old_encrypted != encrypted)
        old_device_info["encrypted"] = old_encrypted
        new_device_info["encrypted"] = encrypted

        # FS LABEL
        label = self._labelEntry.get_text()
        old_label = getattr(device.format, "label", "")
        changed_label = (label != old_label)
        old_device_info["label"] = old_label
        new_device_info["label"] = label
        if changed_label or changed_fs_type:
            error = validate_label(label, new_fs)
            if error:
                self._error = error
                self.set_warning(self._error)
                self._populate_right_side(selector)
                return

        # MOUNTPOINT
        mountpoint = None   # None means format type is not mountable
        if self._mountPointEntry.get_sensitive():
            mountpoint = self._mountPointEntry.get_text()

        old_mountpoint = getattr(device.format, "mountpoint", "") or ""
        old_device_info["mountpoint"] = old_mountpoint
        new_device_info["mountpoint"] = mountpoint
        if mountpoint is not None and (reformat or
                                       mountpoint != old_mountpoint):
            mountpoints = self._storage_playground.mountpoints.copy()
            if old_mountpoint:
                del mountpoints[old_mountpoint]

            error = validate_mountpoint(mountpoint, mountpoints.keys())
            if error:
                self._error = error
                self.set_warning(self._error)
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
                              old_raid_level is not raid_level)
        old_device_info["raid_level"] = old_raid_level
        new_device_info["raid_level"] = raid_level

        ##
        ## VALIDATION
        ##
        error = self._validate_mountpoint(mountpoint, device, device_type,
                                          fs_type_str, reformat, encrypted,
                                          raid_level)
        if error:
            self.set_warning(error)
            self._populate_right_side(selector)
            return

        # If the device is a btrfs volume, the only things we can set/update
        # are mountpoint and container-wide settings.
        if device_type == DEVICE_TYPE_BTRFS and hasattr(use_dev, "subvolumes"):
            size = Size(0)
            changed_size = False
            encrypted = False
            changed_encryption = False
            raid_level = None
            changed_raid_level = False

        with ui_storage_logger():
            # create a new factory using the appropriate size and type
            factory = devicefactory.get_device_factory(self._storage_playground,
                                                      device_type, size,
                                                      disks=device.disks,
                                                      encrypted=encrypted,
                                                      raid_level=raid_level,
                                                      min_luks_entropy=crypto.MIN_CREATE_ENTROPY)

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

        old_device_info["container_name"] = old_container_name
        new_device_info["container_name"] = container_name

        container_encrypted = self._device_container_encrypted
        old_device_info["container_encrypted"] = old_container_encrypted
        new_device_info["container_encrypted"] = container_encrypted
        changed_container_encrypted = (container_encrypted != old_container_encrypted)

        container_raid_level = self._device_container_raid_level
        if container_raid_level not in containerRaidLevelsSupported(device_type):
            container_raid_level = defaultContainerRaidLevel(device_type)

        old_device_info["container_raid_level"] = old_container_raid_level
        new_device_info["container_raid_level"] = container_raid_level
        changed_container_raid_level = (old_container_raid_level != container_raid_level)

        container_size = self._device_container_size
        old_device_info["container_size"] = old_container_size
        new_device_info["container_size"] = container_size
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
        old_device_info["disks"] = old_disks
        new_device_info["disks"] = disks
        log.debug("old disks: %s", [d.name for d in old_disks])
        log.debug("new disks: %s", [d.name for d in disks])

        log.debug("device: %s", device)
        already_logged = {"disks", "device"}
        # log the other changes (old_device_info doesn't have the 'device' key)
        for key in (to_log for to_log in
                    old_device_info.keys() if to_log not in already_logged):
            log.debug("old %s: %s", key, old_device_info[key])
            log.debug("new %s: %s", key, new_device_info[key])

        # XXX prevent multiple raid or encryption layers?

        changed = (changed_name or changed_size or changed_device_type or
                   changed_label or changed_mountpoint or changed_disk_set or
                   changed_encryption or changed_raid_level or
                   changed_fs_type or
                   changed_container or changed_container_encrypted or
                   changed_container_raid_level or changed_container_size)

        # If something has changed but the device does not exist,
        # there is no need to schedule actions on the device.
        # It is only necessary to create a new device object
        # which reflects the current choices.
        if not use_dev.exists:
            if not changed:
                log.debug("nothing changed for new device")
                return

            self.clear_errors()

            if changed_device_type or changed_container:
                # remove the current device
                self._destroy_device(device)
                if device in self._devices:
                    # the removal failed. don't continue.
                    log.error("device removal failed")
                    return
                removed_device = True
            else:
                removed_device = False

            with ui_storage_logger():
                succ = self._try_replace_device(selector, removed_device,
                                                new_device_info, old_device_info)
            if not succ:
                # failed, nothing more to be done
                return

            self._update_device_in_selectors(device, selector.device)
            self._devices = self._storage_playground.devices

            # update size properties and the right side
            self._update_size_props()
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
            self._revert_reformat(device)

        # Handle size change
        if changed_size:
            self._handle_size_change(size, old_size, device)

        # it's possible that reformat is active but fstype is unchanged, in
        # which case we're not going to schedule another reformat unless
        # encryption got toggled
        do_reformat = (reformat and (changed_encryption or
                                     changed_fs_type or
                                     device.format.exists))

        # Handle reformat
        if do_reformat:
            device = self._do_reformat(device, mountpoint, label, changed_encryption,
                                       encrypted, selector, fs_type)
        else:
            # Set various attributes that do not require actions.
            if old_label != label and hasattr(device.format, "label") and \
               validate_label(label, device.format) == "":
                self.clear_errors()
                log.debug("updating label on %s to %s", device.name, label)
                device.format.label = label

            if mountpoint and old_mountpoint != mountpoint:
                self.clear_errors()
                log.debug("updating mountpoint of %s to %s", device.name, mountpoint)
                device.format.mountpoint = mountpoint
                if old_mountpoint:
                    update_selector_from_device(selector, device)
                else:
                    # add an entry to the new page but do not remove any entries
                    # from other pages since we haven't altered the filesystem
                    self.add_new_selector(device)

        #
        # NAME
        #
        if changed_name:
            self.clear_errors()
            try:
                use_dev.name = name
            except ValueError as e:
                self._error = e
                self.set_error(_("Invalid device name: %s") % name)
            else:
                new_name = use_dev.name
                log.debug("changing name of %s to %s", old_name, new_name)
                if new_name in self._storage_playground.names:
                    use_dev.name = old_name
                    self.set_info(_("Specified name %s already in use.") % new_name)
                else:
                    update_selector_from_device(selector, device)

        self._populate_right_side(selector)

    def _raid_level_visible(self, model, itr, user_data):
        device_type = self._get_current_device_type()
        raid_level = raid.get_raid_level(model[itr][1])
        return raid_level in raidLevelsSupported(device_type)

    def _populate_raid(self, raid_level):
        """ Set up the raid-specific portion of the device details.

            :param raid_level: RAID level
            :type raid_level: instance of blivet.devicelibs.raid.RAIDLevel or None
        """
        device_type = self._get_current_device_type()
        log.debug("populate_raid: %s, %s", device_type, raid_level)

        if not raidLevelsSupported(device_type):
            for widget in [self._raidLevelLabel, self._raidLevelCombo]:
                really_hide(widget)
            return

        raid_level = raid_level or defaultRaidLevel(device_type)
        raid_level_name = raidLevelSelection(raid_level)

        # Set a default RAID level in the combo.
        for (i, row) in enumerate(self._raidLevelCombo.get_model()):
            if row[1] == raid_level_name:
                self._raidLevelCombo.set_active(i)
                break
        for widget in [self._raidLevelLabel, self._raidLevelCombo]:
            really_show(widget)

    def _get_current_device_type_name(self):
        """ Return name for type combo selection.

            :returns: the corresponding name extracted from the combo
            :rtype: str or NoneType
        """
        itr = self._typeCombo.get_active_iter()
        if not itr:
            return None

        # we have the constant name in the second column of the store
        return self._typeStore[itr][1]

    def _get_current_device_type(self):
        """ Return integer for type combo selection.

            :returns: the corresponding integer code, a constant in
            blivet.devicefactory.
            :rtype: int or NoneType
        """
        device_type_name = self._get_current_device_type_name()
        return dev_type_from_const(device_type_name) if device_type_name else None

    def _update_container_info(self, use_dev):
        if hasattr(use_dev, "vg"):
            self._device_container_name = use_dev.vg.name
            self._device_container_raid_level = get_raid_level(use_dev.vg)
            self._device_container_encrypted = use_dev.vg.encrypted
            self._device_container_size = use_dev.vg.size_policy
        elif hasattr(use_dev, "volume") or hasattr(use_dev, "subvolumes"):
            volume = getattr(use_dev, "volume", use_dev)
            self._device_container_name = volume.name
            self._device_container_raid_level = get_raid_level(volume)
            self._device_container_encrypted = volume.encrypted
            self._device_container_size = volume.size_policy
        else:
            self._device_container_name = None
            self._device_container_raid_level = None
            self._device_container_encrypted = False
            self._device_container_size = SIZE_POLICY_AUTO

        self._device_container_raid_level = self._device_container_raid_level \
           or defaultContainerRaidLevel(devicefactory.get_device_type(use_dev))

    def _setup_fstype_combo(self, device):
        """ Setup the filesystem combo box.

            :param device: blivet.devices.Device instance
        """
        type_name = device.format.name

        # Possibly unsupported but still required filesystem names
        if device.exists and \
           device.format.type != device.original_format.type and \
           device.original_format.type not in self._fs_types:
            extra_names = (type_name, device.original_format.name)
        else:
            extra_names = (type_name,)

        names = list(self._fs_types.union(extra_names))
        names.sort()

        # Add all desired fileystem type names to the box, sorted alphabetically
        self._fsStore.clear()
        for ty in names:
            self._fsStore.append([ty])

        # set the active filesystem type
        idx = next(i for i, data in enumerate(self._fsCombo.get_model()) if data[0] == type_name)
        self._fsCombo.set_active(idx)

        # do additional updating handled by other method
        self._update_fstype_combo(devicefactory.get_device_type(device))

    def _btrfs_in_typecombo(self, device):
        """ Whether BTRFS should appear in device type combo box.

            :param device: the device being displayed
            :type device: :class:`blivet.devices.StorageDevice`
            :rtype: bool
            :returns: True if BTRFS should appear, otherwise False
        """
        device = device.raw_device

        # The device is btrfs, so btrfs must be shown.
        if device.format.type == "btrfs":
            return True

        # Return True if btrfs filesystem is both allowed and supported.
        fmt = get_format("btrfs")
        return fmt.supported and fmt.formattable and \
           device.format.type not in PARTITION_ONLY_FORMAT_TYPES + ("swap",)

    def _setup_device_type_combo(self, device, device_name):
        """ Set up device type combo.

            :param device: the device
            :type device: :class:`blivet.devices.StorageDevice`
            :param str device_name: the device name

            :returns: the device type that was decided on
            :rtype: int (an enumeration defined in blivet.devicefactory)
        """
        use_dev = device.raw_device

        # these device types should always be listed
        should_appear = {"DEVICE_TYPE_PARTITION", "DEVICE_TYPE_LVM", "DEVICE_TYPE_LVM_THINP"}

        # only include md if there are two or more disks
        if (use_dev.type == "mdarray" or len(self._clearpartDevices) > 1):
            should_appear.add("DEVICE_TYPE_MD")

        if self._btrfs_in_typecombo(device):
            should_appear.add("DEVICE_TYPE_BTRFS")

        # only include disk if the current device is a disk
        if use_dev.is_disk:
            should_appear.add("DEVICE_TYPE_DISK")

        should_appear = set(dt for dt in should_appear if is_supported_device_type(dev_type_from_const(dt)))

        # go through the store and remove things that shouldn't be included
        # store.remove() updates or invalidates the passed iterator
        itr = self._typeStore.get_iter_first()
        valid = True
        while itr and valid:
            dev_type_const = self._typeStore[itr][1]
            if dev_type_const not in should_appear:
                valid = self._typeStore.remove(itr)
            elif dev_type_const in should_appear:
                # already seen, shouldn't be added to the list again
                should_appear.remove(dev_type_const)
                itr = self._typeStore.iter_next(itr)

        # add missing device types
        for dev_type_const in should_appear:
            self._add_device_type(dev_type_const)

        device_type = devicefactory.get_device_type(device)

        for _type in self._device_name_dict.keys():
            if _type == device_type:
                self._device_name_dict[_type] = device_name
                continue
            elif _type not in NAMED_DEVICE_TYPES:
                continue

            is_swap = device.format.type == "swap"
            mountpoint = getattr(device.format, "mountpoint", None)

            with ui_storage_logger():
                name = self._storage_playground.suggest_device_name(swap=is_swap,
                                                        mountpoint=mountpoint)

            self._device_name_dict[_type] = name

        itr = self._typeStore.get_iter_first()
        while itr:
            if dev_type_from_const(self._typeStore[itr][1]) == device_type:
                self._typeCombo.set_active_iter(itr)
                break
            itr = self._typeStore.iter_next(itr)
        else:
            msg = "Didn't find device type %s in device type combobox" % device_type
            raise KeyError(msg)

        return device_type

    def _set_devices_label(self):
        device_disks = self._device_disks
        if not device_disks:
            devices_desc = _("No disks assigned")
        else:
            devices_desc = "%s (%s)" % (device_disks[0].description, device_disks[0].name)
            num_disks = len(device_disks)
            if num_disks > 1:
                devices_desc += CP_("GUI|Custom Partitioning|Devices",
                                    " and %d other", " and %d others",
                                    num_disks - 1) % (num_disks - 1)
        self._deviceDescLabel.set_text(devices_desc)

    def _populate_right_side(self, selector):
        log.debug("populate_right_side: %s", selector.device)

        device = selector.device
        use_dev = device.raw_device

        if hasattr(use_dev, "req_disks") and not use_dev.exists:
            self._device_disks = use_dev.req_disks[:]
        else:
            self._device_disks = device.disks[:]

        self._update_container_info(use_dev)

        log.debug("updated device_disks to %s", [d.name for d in self._device_disks])
        log.debug("updated device_container_name to %s", self._device_container_name)
        log.debug("updated device_container_raid_level to %s", self._device_container_raid_level)
        log.debug("updated device_container_encrypted to %s", self._device_container_encrypted)
        log.debug("updated device_container_size to %s", self._device_container_size)

        self._selectedDeviceLabel.set_text(selector.props.name)
        desc = _(MOUNTPOINT_DESCRIPTIONS.get(selector.props.name, ""))
        self._selectedDeviceDescLabel.set_text(desc)

        self._set_devices_label()

        device_name = getattr(use_dev, "lvname", use_dev.name)
        self._nameEntry.set_text(device_name)

        self._mountPointEntry.set_text(getattr(device.format, "mountpoint", "") or "")
        fancy_set_sensitive(self._mountPointEntry, device.format.mountable)

        if hasattr(device.format, "label"):
            if device.format.label is None:
                device.format.label = ""
            self._labelEntry.set_text(device.format.label)
        else:
            self._labelEntry.set_text("")
        fancy_set_sensitive(self._labelEntry, True)

        self._sizeEntry.set_text(device.size.human_readable(max_places=self.MAX_SIZE_PLACES))

        self._reformatCheckbox.set_active(not device.format.exists)
        fancy_set_sensitive(self._reformatCheckbox,
                            use_dev.exists and not use_dev.format_immutable)

        self._encryptCheckbox.set_active(isinstance(device, LUKSDevice))
        self._encryptCheckbox.set_sensitive(self._reformatCheckbox.get_active())
        ancestors = use_dev.ancestors
        ancestors.remove(use_dev)
        if any(a.format.type == "luks" for a in ancestors):
            # The encryption checkbutton should not be sensitive if there is
            # existing encryption below the leaf layer.
            self._encryptCheckbox.set_sensitive(False)
            self._encryptCheckbox.set_active(True)
            self._encryptCheckbox.set_tooltip_text(_("The container is encrypted."))
        else:
            self._encryptCheckbox.set_tooltip_text("")

        # Set up the filesystem type combo.
        self._setup_fstype_combo(device)

        # Set up the device type combo.
        orig_device_type = self._get_current_device_type()
        device_type = self._setup_device_type_combo(device, device_name)

        # If the device type did not change, run the signal handler anyway
        # to update widgets for the new device
        if orig_device_type == device_type:
            self.on_device_type_changed(self._typeCombo)

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
            self._sizeEntry.set_tooltip_text(_("The space available to this mount point can be changed by modifying the volume below."))
        else:
            self._sizeEntry.set_tooltip_text(_("This file system may not be resized."))

        self._populate_raid(get_raid_level(device))
        self._populate_container(device=use_dev)

        # do this last to override the decision made by on_device_type_changed if necessary
        if use_dev.exists or use_dev.type == "btrfs volume":
            fancy_set_sensitive(self._nameEntry, False)

    ###
    ### SIGNAL HANDLERS
    ###

    def on_key_pressed(self, widget, event, *args):
        if not event or event and event.type != Gdk.EventType.KEY_RELEASE:
            return

        if event.keyval in [Gdk.KEY_Delete, Gdk.KEY_minus]:
            # But we only want delete to work if you have focused a MountpointSelector,
            # and not just any random widget.  For those, it's likely the user wants
            # to delete a character.
            if isinstance(self.main_window.get_focus(), MountpointSelector):
                self._removeButton.emit("clicked")
        elif event.keyval == Gdk.KEY_plus:
            # And we only want '+' to work if you don't have a text entry focused, since
            # the user might be entering some free-form text that can include a plus.
            if not isinstance(self.main_window.get_focus(), Gtk.Entry):
                self._addButton.emit("clicked")

    def _do_check(self):
        self.clear_errors()
        StorageCheckHandler.errors = []
        StorageCheckHandler.warnings = []

        # We can't overwrite the main Storage instance because all the other
        # spokes have references to it that would get invalidated, but we can
        # achieve the same effect by updating/replacing a few key attributes.
        self.storage.devicetree._devices = self._storage_playground.devicetree._devices
        self.storage.devicetree._actions = self._storage_playground.devicetree._actions
        self.storage.devicetree._hidden = self._storage_playground.devicetree._hidden
        self.storage.devicetree.names = self._storage_playground.devicetree.names
        self.storage.roots = self._storage_playground.roots

        # set up bootloader and check the configuration
        try:
            self.storage.set_up_bootloader()
        except BootLoaderError as e:
            log.error("storage configuration failed: %s", e)
            StorageCheckHandler.errors = str(e).split("\n")
            self.data.bootloader.bootDrive = ""

        StorageCheckHandler.checkStorage(self)

        if self.errors:
            self.set_warning(_("Error checking storage configuration.  <a href=\"\">Click for details</a> or press Done again to continue."))
        elif self.warnings:
            self.set_warning(_("Warning checking storage configuration.  <a href=\"\">Click for details</a> or press Done again to continue."))

        # on_info_bar_clicked requires self._error to be set, so set it to the
        # list of all errors and warnings that storage checking found.
        self._error = "\n".join(self.errors + self.warnings)

        return self._error == ""

    def on_back_clicked(self, button):
        # Clear any existing errors
        self.clear_errors()

        # Save anything from the currently displayed mountpoint.
        self._save_right_side(self._accordion.current_selector)
        self._applyButton.set_sensitive(False)

        # And then display the summary screen.  From there, the user will either
        # head back to the hub, or stay on the custom screen.
        self._storage_playground.devicetree.actions.prune()
        self._storage_playground.devicetree.actions.sort()


        # If back has been clicked on once already and no other changes made on the screen,
        # run the storage check now.  This handles displaying any errors in the info bar.
        if not self._back_already_clicked:
            self._back_already_clicked = True

            # If we hit any errors while saving things above, stop and let the
            # user think about what they have done
            if self._error is not None:
                return

            new_luks = [d for d in self._storage_playground.devices
                       if d.format.type == "luks" and not d.format.exists]
            if new_luks:
                dialog = PassphraseDialog(self.data)
                with self.main_window.enlightbox(dialog.window):
                    rc = dialog.run()

                if rc != 1:
                    # Cancel. Leave the old passphrase set if there was one.
                    return

                self.passphrase = dialog.passphrase

            for luks in new_luks:
                if not luks.format.has_key:
                    luks.format.passphrase = self.passphrase

            if not self._do_check():
                return

        if len(self._storage_playground.devicetree.actions.find()) > 0:
            dialog = ActionSummaryDialog(self.data)
            dialog.refresh(self._storage_playground.devicetree.actions.find())
            with self.main_window.enlightbox(dialog.window):
                rc = dialog.run()

            if rc != 1:
                # Cancel.  Stay on the custom screen.
                return

        NormalSpoke.on_back_clicked(self, button)

    @ui_storage_logged
    def _add_device(self, dev_info):
        factory = devicefactory.get_device_factory(self._storage_playground,
                                                   dev_info["device_type"], dev_info["size"],
                                                   min_luks_entropy=crypto.MIN_CREATE_ENTROPY)
        container = factory.get_container()
        if container:
            # don't override user-initiated changes to a defined container
            dev_info["disks"] = container.disks
            dev_info.update({"container_encrypted": container.encrypted,
                             "container_raid_level": get_raid_level(container),
                             "container_size": getattr(container, "size_policy",
                                                       container.size)})

            # The container is already encrypted
            if container.encrypted:
                dev_info["encrypted"] = False

        device_type = dev_info.pop("device_type")
        try:
            self._storage_playground.factory_device(device_type,
                                                    **dev_info)
        except StorageError as e:
            log.error("factory_device failed: %s", e)
            log.debug("trying to find an existing container to use")
            container = factory.get_container(allow_existing=True)
            log.debug("found container %s", container)
            if container:
                # don't override user-initiated changes to a defined container
                dev_info["disks"] = container.disks
                dev_info.update({"container_encrypted": container.encrypted,
                                 "container_raid_level": get_raid_level(container),
                                 "container_size": getattr(container, "size_policy",
                                                               container.size),
                                 "container_name": container.name})
                try:
                    self._storage_playground.factory_device(device_type,
                                                            **dev_info)
                except StorageError as e2:
                    log.error("factory_device failed w/ old container: %s", e2)
                else:
                    type_str = _(DEVICE_TEXT_MAP[device_type])
                    self.set_info(_("Added new %(type)s to existing "
                                    "container %(name)s.")
                                    % {"type" : type_str, "name" : container.name})
                    e = None

            # the factory's error handling has replaced all of the devices
            # with copies, so update the selectors' devices accordingly
            self._update_all_devices_in_selectors()

            if e:
                self._error = e
                self.set_error(_("Failed to add new device. <a href=\"\">Click for "
                                 "details.</a>"))
        except OverflowError as e:
            log.error("invalid size set for partition")
            self._error = e
            self.set_error(_("Invalid partition size set. Use a valid integer."))

    def on_add_clicked(self, button):
        self._save_right_side(self._accordion.current_selector)

        ## initialize and run the AddDialog
        dialog = AddDialog(self.data,
                           mountpoints=self._storage_playground.mountpoints.keys())
        dialog.refresh()
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()

            if rc != 1:
                # user cancel
                dialog.window.destroy()
                return

        self._back_already_clicked = False

        ## gather data about the added mountpoint
        # minimum entropy required for LUKS creation is always the same
        # TODO: use instance of a class with properly named attributes
        dev_info = {"min_luks_entropy": crypto.MIN_CREATE_ENTROPY}

        # create a device of the default type, using any disks, with an
        # appropriate fstype and mountpoint
        dev_info["mountpoint"] = dialog.mountpoint
        log.debug("requested size = %s  ; available space = %s", dialog.size, self._free_space)

        # if no requested size, or size less than 1 MB, request maximum size
        if dialog.size is None or dialog.size < Size("1 MB"):
            dev_info["size"] = None
        else:
            dev_info["size"] = dialog.size

        dev_info["fstype"] = self.storage.get_fstype(dev_info["mountpoint"])

        # The encryption setting as applied here means "encrypt leaf devices".
        # If you want "encrypt my VG/PVs" you'll have to either use the autopart
        # button or wait until we have a way to control container-level
        # encryption.
        dev_info["encrypted"] = self.data.autopart.encrypted

        # we're doing nothing here to ensure that bootable requests end up on
        # the boot disk, but the weight from platform should take care of this

        if lowerASCII(dev_info["mountpoint"]) in ("swap", "biosboot", "prepboot"):
            dev_info["mountpoint"] = None

        dev_info["device_type"] = device_type_from_autopart(self.data.autopart.type)
        if (dev_info["device_type"] != DEVICE_TYPE_PARTITION and
            ((dev_info["mountpoint"] and dev_info["mountpoint"].startswith("/boot")) or
             dev_info["fstype"] in PARTITION_ONLY_FORMAT_TYPES)):
            dev_info["device_type"] = DEVICE_TYPE_PARTITION

        # we shouldn't create swap on a thinly provisioned volume
        if dev_info["fstype"] == "swap" and dev_info["device_type"] == DEVICE_TYPE_LVM_THINP:
            dev_info["device_type"] = DEVICE_TYPE_LVM

        # encryption of thinly provisioned volumes isn't supported
        if dev_info["encrypted"] and dev_info["device_type"] == DEVICE_TYPE_LVM_THINP:
            dev_info["encrypted"] = False

        # some devices should never be encrypted
        if ((dev_info["mountpoint"] and dev_info["mountpoint"].startswith("/boot")) or
            dev_info["fstype"] in PARTITION_ONLY_FORMAT_TYPES):
            dev_info["encrypted"] = False

        dev_info["disks"] = self._clearpartDevices

        ## clear errors and try to add the mountpoint/device
        self.clear_errors()
        self._add_device(dev_info)

        ## refresh internal state and UI elements
        self._devices = self._storage_playground.devices
        if not self._error:
            self._do_refresh(mountpointToShow=dev_info["mountpoint"] or dev_info["fstype"])
        else:
            self._do_refresh()
        self._updateSpaceDisplay()

    @ui_storage_logged
    def _remove_empty_parents(self, device):
        # if this device has parents with no other children, remove them too
        for parent in device.parents:
            if not parent.children and not parent.is_disk:
                self._destroy_device(parent)

    @ui_storage_logged
    def _destroy_device(self, device):
        self.clear_errors()
        is_logical_partition = getattr(device, "isLogical", False)
        try:
            if device.is_disk:
                if device.partitioned and not device.format.supported:
                    self._storage_playground.recursive_remove(device)
                self._storage_playground.initialize_disk(device)
            elif device.direct and not device.isleaf:
                # we shouldn't call this method for with non-leaf devices except
                # for those which are also directly accessible like lvm
                # snapshot origins and btrfs subvolumes that contain other
                # subvolumes
                self._storage_playground.recursive_remove(device)
            else:
                self._storage_playground.destroy_device(device)
        except StorageError as e:
            log.error("failed to schedule device removal: %s", e)
            self._error = e
            self.set_warning(_("Device removal request failed. <a href=\"\">Click "
                               "for details.</a>"))
        else:
            if is_logical_partition:
                self._storage_playground.remove_empty_extended_partitions()

        # If we've just removed the last partition and the disklabel is pre-
        # existing, reinitialize the disk.
        if device.type == "partition" and device.exists and \
           device.disk.format.exists:
            if self._storage_playground.should_clear(device.disk):
                self._storage_playground.initialize_disk(device.disk)

        self._devices = self._storage_playground.devices

        # should this be in DeviceTree._removeDevice?
        container = None
        if hasattr(device, "vg"):
            container = device.vg
            device_type = devicefactory.get_device_type(device)
        elif hasattr(device, "volume"):
            container = device.volume
            device_type = DEVICE_TYPE_BTRFS

        if not container:
            # no container, just remove empty parents of the device
            self._remove_empty_parents(device)
            return

        # adjust container to size of remaining devices, if auto-sized
        if container and not container.exists and container.children and \
           container.size_policy == SIZE_POLICY_AUTO:
            cont_encrypted = container.encrypted
            cont_raid = get_raid_level(container)
            cont_size = container.size_policy
            cont_name = container.name
            factory = devicefactory.get_device_factory(self._storage_playground,
                                        device_type, Size(0),
                                        disks=container.disks,
                                        container_name=cont_name,
                                        container_encrypted=cont_encrypted,
                                        container_raid_level=cont_raid,
                                        container_size=cont_size,
                                        min_luks_entropy=crypto.MIN_CREATE_ENTROPY)
            factory.configure()

        self._remove_empty_parents(device)

    def _show_mountpoint(self, page, mountpoint=None):
        if not self._initialized:
            return

        # Make sure there's something displayed on the RHS.  If a page and
        # mountpoint within that page is given, display that.
        log.debug("show mountpoint: %s", page.pageTitle)
        if not page.members:
            self._accordion.clear_current_selector()
            return

        if not mountpoint and len(self._accordion.selected_items) == 0 \
           and not page.get_parent().get_expanded():
            self._accordion.select(page.members[0])
            self.on_selector_clicked(None, page.members[0])
            return


        if mountpoint:
            for member in page.members:
                if member.get_property("mountpoint").lower() == mountpoint.lower():
                    self._accordion.select(member)
                    self.on_selector_clicked(None, member)
                    break

    def _show_confirmation_dialog(self, root_name, device, protected_types):
        dialog = ConfirmDeleteDialog(self.data)
        bootpart = device.format.type in protected_types
        snapshots = (device.direct and not device.isleaf)
        checkbox_text = None
        if not self._accordion.is_multiselection:
            if root_name and "_" in root_name:
                root_name = root_name.replace("_", "__")
                checkbox_text = (C_("GUI|Custom Partitioning|Confirm Delete Dialog",
                                    "Delete _all file systems which are only used by %s.")
                                    % root_name)
        else:
            checkbox_text = C_("GUI|Custom Partitioning|Confirm Delete Dialog",
                               "Do _not show this dialog for other selected file systems.")
        dialog.refresh(getattr(device.format, "mountpoint", ""),
                       device.name, checkbox_text=checkbox_text,
                       snapshots=snapshots, bootpart=bootpart)
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()
            option_checked = dialog.option_checked
            dialog.window.destroy()
            return (rc, option_checked)

    def on_remove_clicked(self, button):
        # Nothing selected?  Nothing to remove.
        if not self._accordion.is_current_selected and not self._accordion.is_multiselection:
            return

        option_checked = False
        part_removed = False
        is_multiselection = self._accordion.is_multiselection
        protected_types = platform.boot_stage1_constraint_dict["format_types"]
        for selector in self._accordion.selected_items:
            page = self._accordion.page_for_selector(selector)
            device = selector.device
            root_name = None
            if selector.root:
                root_name = selector.root.name
            elif page:
                root_name = page.pageTitle

            log.debug("removing device '%s' from page %s", device, root_name)

            if root_name == translated_new_install_name():
                if is_multiselection and not option_checked:
                    (rc, option_checked) = self._show_confirmation_dialog(root_name, device, protected_types)

                    if rc != 1:
                        if option_checked:
                            break # skip evaluation of all other mountpoints
                        continue

                if device.exists:
                    # This is an existing device that was added to the new page.
                    # All we want to do is revert any changes to the device and
                    # it will end up back in whatever old pages it came from.
                    with ui_storage_logger():
                        self._storage_playground.reset_device(device)

                    log.debug("updated device: %s", device)
                else:
                    # Destroying a non-existing device doesn't require any
                    # confirmation.
                    self._destroy_device(device)
            else:
                # This is a device that exists on disk and most likely has data
                # on it.  Thus, we first need to confirm with the user and then
                # schedule actions to delete the thing.
                # In multiselection user could confirm once for all next
                # selections.
                if not option_checked:
                    (rc, option_checked) = self._show_confirmation_dialog(root_name, device, protected_types)

                    if rc != 1:
                        if option_checked:
                            break # skip evaluation of all other mountpoints
                        continue

                if option_checked and not is_multiselection:
                    otherpgs = (pg for pg in self._accordion.all_pages
                                if pg is not page)
                    otherdevs = []
                    for otherpg in otherpgs:
                        otherdevs.extend(mem._device.id for mem in otherpg.members)
                    # We never want to delete known-shared devs here.
                    # The same rule applies for selected device. If it's shared do not
                    # remove it in other pages when Delete all option is checked.
                    for dev in (s._device for s in page.members
                                if s._device.id not in otherdevs):
                        # we only want to delete boot partitions if they're not
                        # shared *and* we have no unknown partitions
                        if (not self.unusedDevices or dev.format.type not in protected_types):
                            log.debug("deleteall: removed %s", dev.name)
                            self._destroy_device(dev)
                        else:
                            log.debug("deleteall: didn't remove %s", dev.name)
                else:
                    self._destroy_device(device)

            part_removed = True
            log.info("ui: removed device %s", device.name)

        # Now that devices have been removed from the installation root,
        # refreshing the display will have the effect of making them disappear.
        # It's like they never existed.
        if part_removed:
            self._storage_playground.roots = find_existing_installations(self._storage_playground.devicetree)
            self._updateSpaceDisplay()
            self._do_refresh()

    def on_summary_clicked(self, button):
        dialog = SelectedDisksDialog(self.data)
        dialog.refresh(self._clearpartDevices, self._currentFreeInfo,
                       showRemove=False, setBoot=False)
        with self.main_window.enlightbox(dialog.window):
            dialog.run()

    def on_configure_clicked(self, button):
        selector = self._accordion.current_selector
        if not selector:
            return

        device = selector.device
        if device.exists:
            return

        if self._get_current_device_type() in CONTAINER_DEVICE_TYPES:
            # disk set management happens through container edit on RHS
            return

        self.clear_errors()

        dialog = DisksDialog(self.data,
                             disks=self._clearpartDevices,
                             free=self._currentFreeInfo,
                             selected=self._device_disks)
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()

        if rc != 1:
            return

        disks = dialog.selected
        log.debug("new disks for %s: %s", device.name, [d.name for d in disks])
        if not disks:
            self._error = _("No disks selected. Keeping previous disk set.")
            self.set_info(self._error)
            return

        if set(disks) != self._device_disks:
            self._applyButton.set_sensitive(True)

        self._device_disks = disks
        self._set_devices_label()
        self._populate_raid(selectedRaidLevel(self._raidLevelCombo))

    def _container_encryption_change(self, old_encrypted, new_encrypted):
        if not old_encrypted and new_encrypted:
            # container set to be encrypted, we should make sure the leaf device
            # is not encrypted and make the encryption checkbox insensitive
            self._encryptCheckbox.set_active(False)
            fancy_set_sensitive(self._encryptCheckbox, False)
        elif old_encrypted and not new_encrypted:
            fancy_set_sensitive(self._encryptCheckbox, True)

    def run_container_editor(self, container=None, name=None, new_container=False):
        """ Run container edit dialog and return True if changes were made. """
        size = Size(0)
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
                                 storage=self._storage_playground,
                                 exists=getattr(container, "exists", False))

        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc != 1:
            return

        disks = dialog.selected
        name = dialog.name
        log.debug("new disks for %s: %s", name, [d.name for d in disks])
        if not disks:
            self._error = _("No disks selected. Not saving changes.")
            self.set_info(self._error)
            log.error("No disks selected. Not saving changes.")
            return

        log.debug("new container name: %s", name)
        if (name != container_name and name in self._storage_playground.names or
            name in self._get_container_names() and new_container):
            self._error = _("Volume Group name %s is already in use. Not "
                            "saving changes.") % name
            self.set_info(self._error)
            log.error("Volume group name %s already in use.", name)
            return

        if (new_container or
            set(disks) != set(self._device_disks) or
            name != container_name or
            dialog.raid_level != self._device_container_raid_level or
            dialog.encrypted != self._device_container_encrypted or
            dialog.size_policy != self._device_container_size):
            self._applyButton.set_sensitive(True)

        log.debug("new container raid level: %s", dialog.raid_level)
        log.debug("new container encrypted: %s", dialog.encrypted)
        log.debug("new container size: %s", dialog.size_policy)

        if dialog.encrypted:
            self._container_encryption_change(self._device_container_encrypted,
                                              dialog.encrypted)
        self._device_disks = disks
        self._device_container_name = name
        self._device_container_raid_level = dialog.raid_level
        self._device_container_encrypted = dialog.encrypted
        self._device_container_size = dialog.size_policy
        self._set_devices_label()

        return True

    def _container_store_row(self, name, freeSpace=None):
        if freeSpace is not None:
            return [name, _("(%s free)") % freeSpace]
        else:
            return [name, ""]

    def on_modify_container_clicked(self, button):
        container_name = self._containerStore[self._containerCombo.get_active()][0]
        container = self._storage_playground.devicetree.get_device_by_name(container_name)

        # pass the name along with any found vg since we could be modifying a
        # vg that hasn't been instantiated yet
        if not self.run_container_editor(container=container, name=container_name):
            return

        log.debug("%s -> %s", container_name, self._device_container_name)
        if container_name == self._device_container_name:
            self.on_update_settings_clicked(None)
            return

        log.debug("renaming container %s to %s", container_name, self._device_container_name)
        if container:
            # remove the names of the container and its child devices from the
            # list of already-used names
            for device in chain([container], container.children):
                if device.name in self._storage_playground.devicetree.names:
                    self._storage_playground.devicetree.names.remove(device.name)
                luks_name = "luks-%s" % device.name
                if luks_name in self._storage_playground.devicetree.names:
                    self._storage_playground.devicetree.names.remove(luks_name)

            try:
                container.name = self._device_container_name
            except ValueError as e:
                self._error = e
                self.set_error(_("Invalid device name: %s") % self._device_container_name)
                self._device_container_name = container_name
                self.on_update_settings_clicked(None)
                return
            else:
                if container.format.type == "btrfs":
                    container.format.label = self._device_container_name
            finally:
                # add the new names to the list of the already-used names and
                # prevent potential issues with making the devices encrypted
                # later
                for device in chain([container], container.children):
                    self._storage_playground.devicetree.names.append(device.name)
                    luks_name = "luks-%s" % device.name
                    self._storage_playground.devicetree.names.append(luks_name)

        container_exists = getattr(container, "exists", False)

        # TODO: implement and use function for finding item in combobox
        for idx, data in enumerate(self._containerStore):
            # we're looking for the original vg name
            if data[0] == container_name:
                break
        else:
            # no match found, just update selectors and return
            self._update_selectors()
            self.on_update_settings_clicked(None)
            return

        c = self._storage_playground.devicetree.get_device_by_name(self._device_container_name)
        freeSpace = getattr(c, "free_space", None)

        # else branch of for loop above ensures idx is defined
        # pylint: disable=undefined-loop-variable
        self._containerStore.insert(idx, self._container_store_row(self._device_container_name, freeSpace))
        self._containerCombo.set_active(idx)
        self._modifyContainerButton.set_sensitive(not container_exists)
        self._containerStore.remove(self._containerStore.get_iter_from_string("%s" % (idx + 1)))

        self._update_selectors()
        self.on_update_settings_clicked(None)

    def on_container_changed(self, combo):
        ndx = combo.get_active()
        if ndx == -1:
            return

        container_name = self._containerStore[ndx][0]

        log.debug("new container selection: %s", container_name)
        if container_name is None:
            return

        if self._device_container_name == container_name:
            return

        device_type = self._get_current_device_type()
        container_type_name = _(get_container_type(device_type).name).lower()
        new_text = _(NEW_CONTAINER_TEXT) % {"container_type": container_type_name}
        create_new_container = container_name == new_text
        user_changed_container = True
        if create_new_container:
            # run the vg editor dialog with a default name and disk set
            hostname = self.data.network.hostname
            if hostname == network.DEFAULT_HOSTNAME:
                hostname = network.current_hostname()
            name = self._storage_playground.suggest_container_name(hostname=hostname)
            # user_changed_container flips to False if "cancel" picked
            user_changed_container = self.run_container_editor(name=name, new_container=True)
            for idx, data in enumerate(self._containerStore):
                if user_changed_container and data[0] == new_text:
                    c = self._storage_playground.devicetree.get_device_by_name(self._device_container_name)
                    freeSpace = getattr(c, "free_space", None)
                    row = self._container_store_row(self._device_container_name, freeSpace)

                    self._containerStore.insert(idx, row)
                    combo.set_active(idx)   # triggers a call to this method
                    return
                elif not user_changed_container and data[0] == self._device_container_name:
                    combo.set_active(idx)
                    return
        # else clause runs if an already existing container is picked
        else:
            self._device_container_name = container_name

        if user_changed_container:
            self._applyButton.set_sensitive(True)

        container = self._storage_playground.devicetree.get_device_by_name(self._device_container_name)
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

    def _save_current_page(self, selector = None):
        if selector is None:
            selector = self._accordion.current_selector
        log.debug("Saving current selector: %s", selector.device)
        self._save_right_side(selector)

    def on_selector_clicked(self, old_selector, selector):
        if not self._initialized \
           or ((old_selector or self._accordion.current_selector)   # one of them must be set
               and (old_selector is self._accordion.current_selector)): # and they need to differ
            return

        # Take care of the previously chosen selector.
        if old_selector:
            self._save_current_page(old_selector)

        curr_selector = self._accordion.current_selector
        no_edit = False
        currentPageType = None
        if self._accordion.is_multiselection or not curr_selector:
            currentPageType = NOTEBOOK_LABEL_PAGE
            self._set_page_label_text()
            no_edit = True
        elif curr_selector.device.format.type == "luks" and \
           curr_selector.device.format.exists:
            currentPageType = NOTEBOOK_LUKS_PAGE
            selectedDeviceLabel = self._encryptedDeviceLabel
            selectedDeviceDescLabel = self._encryptedDeviceDescLabel
            no_edit = True
        elif not getattr(curr_selector.device, "complete", True):
            currentPageType = NOTEBOOK_INCOMPLETE_PAGE
            selectedDeviceLabel = self._incompleteDeviceLabel
            selectedDeviceDescLabel = self._incompleteDeviceDescLabel

            if isinstance(curr_selector.device, MDRaidArrayDevice):
                total = curr_selector.device.member_devices
                missing = total - len(curr_selector.device.parents)
                txt = _("This Software RAID array is missing %(missingMembers)d of %(totalMembers)d member "
                        "partitions. You can remove it or select a different "
                        "device.") % {"missingMembers": missing, "totalMembers": total}
            elif isinstance(curr_selector.device, LVMVolumeGroupDevice):
                total = curr_selector.device.pv_count
                missing = total - len(curr_selector.device.parents)
                txt = _("This LVM Volume Group is missing %(missingPVs)d of %(totalPVs)d physical "
                        "volumes. You can remove it or select a different "
                        "device.") % {"missingPVs": missing, "totalPVs": total}
            else:
                txt = _("This %(type)s device is missing member devices. You can remove it or"
                        " select a different device.") % curr_selector.device.type

            self._incompleteDeviceOptionsLabel.set_text(txt)
            no_edit = True
        elif devicefactory.get_device_type(curr_selector.device) is None:
            currentPageType = NOTEBOOK_UNEDITABLE_PAGE
            selectedDeviceLabel = self._uneditableDeviceLabel
            selectedDeviceDescLabel = self._uneditableDeviceDescLabel
            no_edit = True

        if no_edit:
            self._partitionsNotebook.set_current_page(currentPageType)
            if currentPageType != NOTEBOOK_LABEL_PAGE:
                selectedDeviceLabel.set_text(curr_selector.device.name)
                desc = _(MOUNTPOINT_DESCRIPTIONS.get(curr_selector.device.type, ""))
                selectedDeviceDescLabel.set_text(desc)

            self._configButton.set_sensitive(False)
            self._removeButton.set_sensitive(True)
            return

        # Make sure we're showing details instead of the "here's how you create
        # a new OS" label.
        self._partitionsNotebook.set_current_page(NOTEBOOK_DETAILS_PAGE)

        # Set up the newly chosen selector.
        self._populate_right_side(curr_selector)

        self._applyButton.set_sensitive(False)
        container_device = devicefactory.get_device_type(curr_selector.device) in CONTAINER_DEVICE_TYPES
        self._configButton.set_sensitive(not curr_selector.device.exists and
                                         not curr_selector.device.protected and
                                         not container_device)
        self._removeButton.set_sensitive(not curr_selector.device.protected)

    def on_page_clicked(self, page, mountpointToShow=None):
        if not self._initialized:
            return

        log.debug("page clicked: %s", page.pageTitle)
        if self._accordion.is_current_selected:
            self._save_current_page()

        self._show_mountpoint(page=page, mountpoint=mountpointToShow)

        # This is called when a Page header is clicked upon so we can support
        # deleting an entire installation at once and displaying something
        # on the RHS.
        if isinstance(page, CreateNewPage):
            # Make sure we're showing "here's how you create a new OS" or
            # multiselection label instead of device/mountpoint details.
            self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
            self._set_page_label_text()
            self._removeButton.set_sensitive(False)
        else:
            self._removeButton.set_sensitive(True)

    @ui_storage_logged
    def _do_autopart(self):
        """Helper function for on_create_clicked.
           Assumes a non-final context in which at least some errors
           discovered by storage checker are not considered fatal because they
           will be dealt with later.

           Note: There are never any non-existent devices around when this runs.
        """
        log.debug("running automatic partitioning")
        self._storage_playground.do_autopart = True
        self.clear_errors()
        try:
            self._storage_playground.create_free_space_snapshot()
            # do_autoparts needs stage1_disk setup so it will reuse existing partitions
            self._storage_playground.set_up_bootloader(early=True)

            refreshAutoSwapSize(self._storage_playground)
            do_autopart(self._storage_playground, self.data,
                            min_luks_entropy=crypto.MIN_CREATE_ENTROPY)
        except NoDisksError as e:
            # No handling should be required for this.
            log.error("do_autopart failed: %s", e)
            self._error = e
            self.set_error(_("No disks selected."))
        except NotEnoughFreeSpaceError as e:
            # No handling should be required for this.
            log.error("do_autopart failed: %s", e)
            self._error = e
            self.set_error(_("Not enough free space on selected disks."))
        except (StorageError, BootLoaderError) as e:
            log.error("do_autopart failed: %s", e)
            self._reset_storage()
            self._error = e
            self.set_error(_("Automatic partitioning failed. <a href=\"\">Click "
                             "for details.</a>"))
        else:
            self._devices = self._storage_playground.devices
            # mark all new containers for automatic size management
            for device in self._devices:
                if not device.exists and hasattr(device, "size_policy"):
                    device.size_policy = SIZE_POLICY_AUTO
        finally:
            self._storage_playground.do_autopart = False
            log.debug("finished automatic partitioning")

        report = storage_checker.check(self._storage_playground,
                                       skip=(verify_luks_devices_have_key,))
        report.log(log)

        if report.errors:
            messages = "\n".join(report.errors)
            log.error("do_autopart failed: %s", messages)
            self._reset_storage()
            self._error = messages
            self.set_error(_("Automatic partitioning failed. <a href=\"\">Click "
                             "for details.</a>"))

    def on_create_clicked(self, button, autopartTypeCombo):
        # Then do autopartitioning.  We do not do any clearpart first.  This is
        # custom partitioning, so you have to make your own room.
        self._storage_playground.autopart_type = self._get_autopart_type(autopartTypeCombo)
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

        encrypt_sensitive = active
        if self._accordion.current_selector:
            device = self._accordion.current_selector.device.raw_device

            ancestors = device.ancestors
            ancestors.remove(device)
            if any(a.format.type == "luks" and a.format.exists for a in ancestors):
                # The encryption checkbutton should not be sensitive if there is
                # existing encryption below the leaf layer.
                encrypt_sensitive = False

        # you can't encrypt a btrfs subvolume -- only the volume/container
        device_type = self._get_current_device_type()
        if device_type == DEVICE_TYPE_BTRFS:
            self._encryptCheckbox.set_active(False)

        self._encryptCheckbox.set_sensitive(encrypt_sensitive and device_type != DEVICE_TYPE_BTRFS)
        fancy_set_sensitive(self._fsCombo, active)

    def on_fs_type_changed(self, combo):
        if not self._initialized:
            return

        itr = combo.get_active_iter()
        if not itr:
            return

        new_type = self._get_fstype(combo)

        fmt = get_format(new_type)
        fancy_set_sensitive(self._mountPointEntry, fmt.mountable)

    def _populate_container(self, device=None):
        """ Set up the vg widgets for lvm or hide them for other types. """
        device_type = self._get_current_device_type()
        if device is None:
            if self._accordion.current_selector is None:
                return

            device = self._accordion.current_selector.device
            if device:
                device = device.raw_device

        container_size_policy = SIZE_POLICY_AUTO
        if device_type not in CONTAINER_DEVICE_TYPES:
            # just hide the buttons with no meaning for non-container devices
            for widget in [self._containerLabel, self._containerCombo, self._modifyContainerButton]:
                really_hide(widget)
            return

        # else really populate the container
        # set up the vg widgets and then bail out
        if devicefactory.get_device_type(device) == device_type:
            _device = device
        else:
            _device = None

        with ui_storage_logger():
            factory = devicefactory.get_device_factory(self._storage_playground,
                                                     device_type,
                                                     0, min_luks_entropy=crypto.MIN_CREATE_ENTROPY)
            container = factory.get_container(device=_device)
            default_container_name = getattr(container, "name", None)
            if container:
                container_size_policy = container.size_policy

        container_type = get_container_type(device_type)
        self._containerLabel.set_text(C_("GUI|Custom Partitioning|Configure|Devices", container_type.label).title())
        self._containerLabel.set_use_underline(True)
        self._containerStore.clear()
        if device_type == DEVICE_TYPE_BTRFS:
            containers = self._storage_playground.btrfs_volumes
        else:
            containers = self._storage_playground.vgs

        default_seen = False
        for c in containers:
            self._containerStore.append(self._container_store_row(c.name, getattr(c, "free_space", None)))
            if default_container_name and c.name == default_container_name:
                default_seen = True
                self._containerCombo.set_active(containers.index(c))

        if default_container_name is None:
            hostname = self.data.network.hostname
            if hostname == network.DEFAULT_HOSTNAME:
                hostname = network.current_hostname()
            default_container_name = self._storage_playground.suggest_container_name(hostname=hostname)

        log.debug("default container is %s", default_container_name)
        self._device_container_name = default_container_name
        self._device_container_size = container_size_policy

        if not default_seen:
            self._containerStore.append(self._container_store_row(default_container_name))
            self._containerCombo.set_active(len(self._containerStore) - 1)

        self._containerStore.append(self._container_store_row(_(NEW_CONTAINER_TEXT) % {"container_type": _(container_type.name).lower()}))
        self._containerCombo.set_tooltip_text(_(CONTAINER_TOOLTIP) % {"container_type": _(container_type.name).lower()})
        if default_container_name is None:
            self._containerCombo.set_active(len(self._containerStore) - 1)

        for widget in [self._containerLabel, self._containerCombo, self._modifyContainerButton]:
            really_show(widget)

        # make the combo and button insensitive for existing LVs
        can_change_container = (device is not None and not device.exists and
                                device != container)
        fancy_set_sensitive(self._containerCombo, can_change_container)
        container_exists = getattr(container, "exists", False)
        self._modifyContainerButton.set_sensitive(not container_exists)

    def _update_fstype_combo(self, device_type):
        """ Set up device type dependent portion of filesystem combo.

            :param int device_type: an int representing the device type

            Generally speaking, the filesystem combo can be set up without
            reference to the device type because the choice of filesystem
            combo and of device type is orthogonal.

            However, choice of btrfs device type requires choice of btrfs
            filesystem type, and choice of any other device type precludes
            choice of btrfs filesystem type.

            Preconditions are:
            * the filesystem combo contains at least the default filesystem
            * the default filesystem is not the same as btrfs
            * if device_type is DEVICE_TYPE_BTRFS, btrfs is supported

            This method is idempotent, and must remain so.
        """
        # Find unique instance of btrfs in fsCombo, if any.
        model = self._fsCombo.get_model()
        btrfs_iter = ((idx, row) for idx, row in enumerate(model) if row[0] == "btrfs")
        btrfs_idx, btrfs_row = next(btrfs_iter, (None, None))

        if device_type == DEVICE_TYPE_BTRFS:
            # If no btrfs entry, add one, and select the new entry
            if btrfs_idx is None:
                self._fsStore.append(["btrfs"])
                active_index = len(self._fsCombo.get_model()) - 1
            # Otherwise, select the already located btrfs entry
            else:
                active_index = btrfs_idx
        else:
            # Get the currently active index
            active_index = self._fsCombo.get_active()

            # If there is a btrfs entry, remove and adjust active_index
            if btrfs_idx is not None:
                self._fsStore.remove(btrfs_row.iter)

                # If btrfs previously selected, select default filesystem
                if active_index == btrfs_idx:
                    active_index = next(idx for idx, data in enumerate(self._fsCombo.get_model()) if data[0] == self.storage.default_fstype)
                # Otherwise, shift index left by one if after removed entry
                elif active_index > btrfs_idx:
                    active_index = active_index - 1
            # If there is no btrfs entry, stick with user's previous choice
            else:
                pass

        self._fsCombo.set_active(active_index)
        fancy_set_sensitive(self._fsCombo, self._reformatCheckbox.get_active() and device_type != DEVICE_TYPE_BTRFS)

    def on_device_type_changed(self, combo):
        if combo is not self._typeCombo:
            return

        if not self._initialized:
            return

        # The name of the device type is more informative than the numeric id
        new_type = self._get_current_device_type_name()
        log.debug("device_type_changed: %s", new_type)

        # Quit if no device type is selected.
        if new_type is None:
            return

        # The numeric id of the device is what is needed by blivet.
        new_type = dev_type_from_const(new_type)

        # Quit if device type name is unrecognized by blivet.
        if new_type is None:
            return

        # lvm uses the RHS to set disk set. no foolish minds here.
        exists = self._accordion.current_selector and self._accordion.current_selector.device.exists
        self._configButton.set_sensitive(not exists and new_type not in CONTAINER_DEVICE_TYPES)

        # this has to be done before calling populate_raid since it will need
        # the raid level combo to contain the relevant raid levels for the new
        # device type
        self._raidStoreFilter.refilter()

        self._populate_raid(defaultRaidLevel(new_type))
        self._populate_container()

        fancy_set_sensitive(self._nameEntry, new_type in NAMED_DEVICE_TYPES)
        self._nameEntry.set_text(self._device_name_dict[new_type])
        fancy_set_sensitive(self._sizeEntry, new_type != DEVICE_TYPE_BTRFS)

        self._update_fstype_combo(new_type)

    def clear_errors(self):
        self._error = None
        self.clear_info()

    # This callback is for the button that just resets the UI to anaconda's
    # current understanding of the disk layout.
    def on_reset_clicked(self, *args):
        msg = _("Continuing with this action will reset all your partitioning selections "
                "to their current on-disk state.")

        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.NONE,
                                message_format=msg)
        dlg.set_decorated(False)
        dlg.add_buttons(C_("GUI|Custom Partitioning|Reset Dialog", "_Reset selections"), 0,
                        C_("GUI|Custom Partitioning|Reset Dialog", "_Preserve current selections"), 1)
        dlg.set_default_response(1)

        with self.main_window.enlightbox(dlg):
            rc = dlg.run()
            dlg.destroy()

        if rc == 0:
            self.refresh()

    # This callback is for the button that has anaconda go back and rescan the
    # disks to pick up whatever changes the user made outside our control.
    def on_refresh_clicked(self, *args):
        dialog = RefreshDialog(self.data, self.storage)
        ignoreEscape(dialog.window)
        with self.main_window.enlightbox(dialog.window):
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

        with self.main_window.enlightbox(dlg):
            dlg.run()
            dlg.destroy()

    @timed_action(delay=50, threshold=100)
    def on_update_settings_clicked(self, button):
        """ call _save_right_side, then, perhaps, populate_right_side. """
        self._save_right_side(self._accordion.current_selector)
        self._applyButton.set_sensitive(False)

    @timed_action(delay=50, threshold=100)
    def on_unlock_clicked(self, *args):
        """ try to open the luks device, populate, then call _do_refresh. """
        self.clear_errors()
        device = self._accordion.current_selector.device
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
                               "<a href=\"\">Click for details.</a>"))
            return

        # set the passphrase also to the original_format of the device (a
        # different object than '.format', but the same contents)
        device.original_format.passphrase = passphrase
        log.info("unlocked %s, now going to populate devicetree...", device.name)
        with ui_storage_logger():
            luks_dev = LUKSDevice(device.format.map_name,
                                  parents=[device],
                                  exists=True)
            self._storage_playground.devicetree._add_device(luks_dev)
            # save the passphrase for possible reset and to try for other devs
            self._storage_playground.save_passphrase(device)
            # XXX What if the user has changed things using the shell?
            try_populate_devicetree(self._storage_playground.devicetree)
            # look for new roots
            self._storage_playground.roots = find_existing_installations(self._storage_playground.devicetree)

        self._devices = self._storage_playground.devices
        self._accordion.clear_current_selector()
        self._do_refresh()

    def on_value_changed(self, *args):
        self._applyButton.set_sensitive(True)
