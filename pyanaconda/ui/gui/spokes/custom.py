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

from pykickstart.constants import CLEARPART_TYPE_NONE, AUTOPART_TYPE_PLAIN, AUTOPART_TYPE_BTRFS, AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP

from pyanaconda.i18n import _, N_, CP_
from pyanaconda.product import productName, productVersion, translated_new_install_name
from pyanaconda.threads import AnacondaThread, threadMgr
from pyanaconda.constants import THREAD_EXECUTE_STORAGE, THREAD_STORAGE, THREAD_CUSTOM_STORAGE_INIT
from pyanaconda.iutil import lowerASCII
from pyanaconda.bootloader import BootLoaderError

from blivet import devicefactory
from blivet.formats import device_formats
from blivet.formats import getFormat
from blivet.formats.fs import FS
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
from blivet import findExistingInstallations
from blivet.partitioning import doAutoPartition
from blivet.errors import StorageError
from blivet.errors import NoDisksError
from blivet.errors import NotEnoughFreeSpaceError
from blivet.errors import SanityError
from blivet.errors import SanityWarning
from blivet.errors import LUKSDeviceWithoutKeyError
from blivet.devicelibs import mdraid
from blivet.devices import LUKSDevice

from pyanaconda.storage_utils import get_supported_raid_levels, ui_storage_logger

from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.storage import StorageChecker
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.passphrase import PassphraseDialog
from pyanaconda.ui.gui.spokes.lib.accordion import selectorFromDevice, Accordion, Page, CreateNewPage, UnknownPage
from pyanaconda.ui.gui.spokes.lib.refresh import RefreshDialog
from pyanaconda.ui.gui.spokes.lib.summary import ActionSummaryDialog

from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import size_from_entry
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import validate_label, validate_mountpoint, selectedRaidLevel
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import get_container_type_name, RAID_NOT_ENOUGH_DISKS
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import AddDialog, ConfirmDeleteDialog, DisksDialog, ContainerDialog, HelpDialog

from pyanaconda.ui.gui.utils import setViewportBackground, enlightbox, fancy_set_sensitive, ignoreEscape
from pyanaconda.ui.gui.utils import really_hide, really_show, GtkActionList
from pyanaconda.ui.gui.categories.system import SystemCategory

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


DEVICE_TEXT_LVM = N_("LVM")
DEVICE_TEXT_LVM_THINP = N_("LVM Thin Provisioning")
DEVICE_TEXT_MD = N_("RAID")
DEVICE_TEXT_PARTITION = N_("Standard Partition")
DEVICE_TEXT_BTRFS = N_("BTRFS")
DEVICE_TEXT_DISK = N_("Disk")

DEVICE_TEXT_MAP = {DEVICE_TYPE_LVM: DEVICE_TEXT_LVM,
                   DEVICE_TYPE_MD: DEVICE_TEXT_MD,
                   DEVICE_TYPE_PARTITION: DEVICE_TEXT_PARTITION,
                   DEVICE_TYPE_BTRFS: DEVICE_TEXT_BTRFS,
                   DEVICE_TYPE_LVM_THINP: DEVICE_TEXT_LVM_THINP}

NEW_CONTAINER_TEXT = N_("Create a new %(container_type)s ...")
CONTAINER_TOOLTIP = N_("Create or select %(container_type)s")

DEVICE_CONFIGURATION_ERROR_MSG = N_("Device reconfiguration failed. Click for "
                                    "details.")
UNRECOVERABLE_ERROR_MSG = N_("Storage configuration reset due to unrecoverable "
                             "error. Click for details.")

PARTITION_ONLY_FORMAT_TYPES = ["efi", "macefi", "prepboot", "biosboot",
                               "appleboot"]

MOUNTPOINT_DESCRIPTIONS = {"Swap": N_("The 'swap' area on your computer is used by the operating\n"
                                      "system when running low on memory."),
                           "Boot": N_("The 'boot' area on your computer is where files needed\n"
                                      "to start the operating system are stored."),
                           "Root": N_("The 'root' area on your computer is where core system\n"
                                      "files and applications are stored."),
                           "Home": N_("The 'home' area on your computer is where all your personal\n"
                                      "data is stored."),
                           "BIOS Boot": N_("The BIOS boot partition is required to enable booting\n"
                                           "from GPT-partitioned disks on BIOS hardware."),
                           "PReP Boot": N_("The PReP boot partition is required as part of the\n"
                                           "bootloader configuration on some PPC platforms.")
                            }

class CustomPartitioningSpoke(NormalSpoke, StorageChecker):
    builderObjects = ["customStorageWindow", "containerStore",
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

        self._back_already_clicked = False
        self._storage_playground = None

        self.passphrase = ""

        self._current_selector = None
        self._devices = []
        self._error = None
        self._hidden_disks = []
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

        self._unhide_unusable_disks()

        new_swaps = (dev for dev in self.get_new_devices() if dev.format.type == "swap")
        self.storage.setFstabSwaps(new_swaps)

        # update the global passphrase
        self.data.autopart.passphrase = self.passphrase

        # make sure any device/passphrase pairs we've obtained are remembered
        for device in self.storage.devices:
            if device.format.type == "luks" and not device.format.exists:
                if not device.format.hasKey:
                    device.format.passphrase = self.passphrase

                self.storage.savePassphrase(device)

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

        self._whenCreateLabel = self.builder.get_object("whenCreateLabel")

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
        self._containerStore = self.builder.get_object("containerStore")

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
        self._fs_types = []
        actions = GtkActionList()
        for cls in device_formats.itervalues():
            obj = cls()

            # btrfs is always handled by on_device_type_changed
            supported_fs = (obj.type != "btrfs" and
                            obj.type != "tmpfs" and
                            obj.supported and obj.formattable and
                            (isinstance(obj, FS) or
                             obj.type in ["biosboot", "prepboot", "swap"]))
            if supported_fs:
                actions.add_action(self._fsCombo.append_text, obj.name)
                self._fs_types.append(obj.name)

        actions.fire()

    @property
    def _clearpartDevices(self):
        return [d for d in self._devices if d.name in self.data.clearpart.drives and d.partitioned]

    @property
    def unusedDevices(self):
        unused_devices = [d for d in self._storage_playground.unusedDevices
                                if d.disks and d.mediaPresent and
                                not d.partitioned and
                                (d.isleaf or d.type.startswith("btrfs"))]
        # add incomplete VGs and MDs
        incomplete = [d for d in self._storage_playground.devicetree._devices
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
        return self._storage_playground.getFreeSpace(clearPartType=CLEARPART_TYPE_NONE)

    def _setCurrentFreeSpace(self):
        """Add up all the free space on selected disks and return it as a Size."""
        self._free_space = sum(f[0] for f in self._currentFreeInfo.values())

    def _currentTotalSpace(self):
        """Add up the sizes of all selected disks and return it as a Size."""
        totalSpace = sum((disk.size for disk in self._clearpartDevices),
                         Size(bytes=0))
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

    def _hide_unusable_disks(self):
        self._hidden_disks = []

        with ui_storage_logger():
            for disk in self._storage_playground.disks:
                if (disk.removable and disk.protected) or not disk.mediaPresent:
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

    def _change_autopart_type(self, autopartTypeCombo):
        # This is called when the autopart type combo on the left hand side of
        # custom partitioning is changed.  We already know how to handle the
        # case where the user changes the type and then clicks the autopart
        # link button.  This handles the case where the user changes the type
        # and then clicks the '+' button.

        # NOTE: This assumes the order of things in the combo box and the order
        # of the pykickstart AUTOPART_TYPE_* constants are the same.
        self.data.autopart.type = autopartTypeCombo.get_active()

    def get_new_devices(self):
        # A device scheduled for formatting only belongs in the new root.
        new_devices = [d for d in self._devices if (d.isleaf or
                                                    d.type.startswith("btrfs"))
                                                   and
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

    def _populate_accordion(self):
        # Make sure we start with a clean state.
        self._accordion.removeAllPages()

        new_devices = self.get_new_devices()

        # Now it's time to populate the accordion.
        log.debug("ui: devices=%s", [d.name for d in self._devices])
        log.debug("ui: unused=%s", [d.name for d in self.unusedDevices])
        log.debug("ui: new_devices=%s", [d.name for d in new_devices])

        ui_roots = self._storage_playground.roots[:]

        # If we've not yet run autopart, add an instance of CreateNewPage.  This
        # ensures it's only added once.
        if not new_devices:
            page = CreateNewPage(translated_new_install_name(),
                                 self.on_create_clicked,
                                 self._change_autopart_type,
                                 partitionsToReuse=bool(ui_roots))
            self._accordion.addPage(page, cb=self.on_page_clicked)

            self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
            self._whenCreateLabel.set_text(_("When you create mount points for "
                    "your %(name)s %(version)s installation, you'll be able to "
                    "view their details here.") % {"name" : productName,
                                                   "version" : productVersion})
        else:
            swaps = [d for d in new_devices if d.format.type == "swap"]
            mounts = dict((d.format.mountpoint, d) for d in new_devices
                                if getattr(d.format, "mountpoint", None))

            for device in new_devices:
                if device in self.bootLoaderDevices:
                    mounts[device.format.type] = device

            new_root = Root(mounts=mounts, swaps=swaps, name=translated_new_install_name())
            ui_roots.insert(0, new_root)

        # Add in all the existing (or autopart-created) operating systems.
        for root in ui_roots:
            # Don't make a page if none of the root's devices are left.
            # Also, only include devices in an old page if the format is intact.
            if not any(d for d in root.swaps + root.mounts.values()
                        if d in self._devices and d.disks and
                           (root.name == translated_new_install_name() or d.format.exists)):
                continue

            page = Page(root.name)

            for (mountpoint, device) in root.mounts.iteritems():
                if device not in self._devices or \
                   not device.disks or \
                   (root.name != translated_new_install_name() and not device.format.exists):
                    continue

                selector = page.addSelector(device, self.on_selector_clicked,
                                            mountpoint=mountpoint)
                selector.root = root

            for device in root.swaps:
                if device not in self._devices or \
                   (root.name != translated_new_install_name() and not device.format.exists):
                    continue

                selector = page.addSelector(device, self.on_selector_clicked)
                selector.root = root

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

        # Anything that doesn't go with an OS we understand?  Put it in the Other box.
        if self.unusedDevices:
            page = UnknownPage(_("Unknown"))

            for u in sorted(self.unusedDevices, key=lambda d: d.name):
                page.addSelector(u, self.on_selector_clicked)

            page.show_all()
            self._accordion.addPage(page, cb=self.on_page_clicked)

    def _do_refresh(self, mountpointToShow=None):
        # block mountpoint selector signal handler for now
        self._initialized = False
        self._clear_current_selector()

        # Start with buttons disabled, since nothing is selected.
        self._removeButton.set_sensitive(False)
        self._configButton.set_sensitive(False)

        # populate the accorion with roots and mount points
        self._populate_accordion()

        # And then open the first page by default.  Most of the time, this will
        # be fine since it'll be the new installation page.
        self._initialized = True
        firstPage = self._accordion.allPages[0]
        self._accordion.expandPage(firstPage.pageTitle)
        self._show_mountpoint(page=firstPage, mountpoint=mountpointToShow)

        self._applyButton.set_sensitive(False)
        self._resetButton.set_sensitive(len(self._storage_playground.devicetree.findActions()) > 0)

    ###
    ### RIGHT HAND SIDE METHODS
    ###
    def add_new_selector(self, device):
        """ Add an entry for device to the new install Page. """
        page = self._accordion._find_by_title(translated_new_install_name()).get_child()
        devices = [device]
        if not page.members:
            # remove the CreateNewPage and replace it with a regular Page
            expander = self._accordion._find_by_title(translated_new_install_name())
            expander.remove(expander.get_child())

            page = Page(translated_new_install_name())
            expander.add(page)

            # also pull in biosboot and prepboot that are on our boot disk
            devices.extend(self.bootLoaderDevices)

        for _device in devices:
            page.addSelector(_device, self.on_selector_clicked)

        page.show_all()

    def _update_selectors(self):
        """ Update all btrfs selectors' size properties. """
        # we're only updating selectors in the new root. problem?
        page = self._accordion._find_by_title(translated_new_install_name()).get_child()
        for selector in page.members:
            selectorFromDevice(selector.device, selector=selector)

    def _replace_device(self, *args, **kwargs):
        """ Create a replacement device and update the device selector. """
        selector = kwargs.pop("selector", None)
        new_device = self._storage_playground.factoryDevice(*args, **kwargs)

        self._devices = self._storage_playground.devices

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
            for new_device in self._storage_playground.devices:
                if ((s._device.name == new_device.name) or
                    (getattr(s._device, "req_name", 1) == getattr(new_device, "req_name", 2)) and
                    s._device.type == new_device.type and
                    s._device.format.type == new_device.format.type):
                    selectorFromDevice(new_device, selector=s)
                    break
            else:
                log.warning("failed to replace device: %s", s._device)

    def _save_right_side(self, selector):
        """ Save settings from RHS and apply changes to the device.

            This method must never trigger a call to self._do_refresh.
        """
        if not self._initialized or not selector:
            return

        device = selector.device
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
        changed_size = ((use_dev.resizable or not use_dev.exists) and
                        size != old_size)
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
        new_fs = getFormat(fs_type)
        new_fs_type = new_fs.type
        changed_fs_type = (old_fs_type != new_fs_type)
        log.debug("old fs type: %s", old_fs_type)
        log.debug("new fs type: %s", new_fs_type)

        # ENCRYPTION
        old_encrypted = isinstance(device, LUKSDevice)
        encrypted = self._encryptCheckbox.get_active()
        changed_encryption = (old_encrypted != encrypted)
        log.debug("old encryption setting: %s", old_encrypted)
        log.debug("new encryption setting: %s", encrypted)

        # FS LABEL
        label = self._labelEntry.get_text()
        old_label = getattr(device.format, "label", "")
        changed_label = (label != old_label)
        log.debug("old label: %s", old_label)
        log.debug("new_label: %s", label)
        if changed_label or changed_fs_type:
            error = validate_label(label, new_fs)
            if error:
                self._error = error
                self.set_warning(self._error)
                self.window.show_all()
                self._populate_right_side(selector)
                return

        # MOUNTPOINT
        mountpoint = None   # None means format type is not mountable
        if self._mountPointEntry.get_sensitive():
            mountpoint = self._mountPointEntry.get_text()

        old_mountpoint = getattr(device.format, "mountpoint", "") or ""
        log.debug("old mountpoint: %s", old_mountpoint)
        log.debug("new mountpoint: %s", mountpoint or "")
        if mountpoint is not None and (reformat or
                                       mountpoint != old_mountpoint):
            mountpoints = self._storage_playground.mountpoints.copy()
            if old_mountpoint:
                del mountpoints[old_mountpoint]

            error = validate_mountpoint(mountpoint, mountpoints.keys())
            if error:
                self._error = error
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
             new_fs_type in PARTITION_ONLY_FORMAT_TYPES:
            error = (_("%(fs)s must be on a device of type %(type)s")
                       % {"fs" : fs_type, "type" : _(DEVICE_TEXT_PARTITION)})
        elif mountpoint and encrypted and mountpoint.startswith("/boot"):
            error = _("%s cannot be encrypted") % mountpoint
        elif encrypted and new_fs_type in PARTITION_ONLY_FORMAT_TYPES:
            error = _("%s cannot be encrypted") % fs_type
        elif mountpoint == "/" and device.format.exists and not reformat:
            error = _("You must create a new filesystem on the root device.")
        elif device_type == DEVICE_TYPE_MD and raid_level in (None, "single"):
            error = _("Devices of type %s require a valid RAID level selection.") % _(DEVICE_TEXT_MD)

        if not error and raid_level not in (None, "single"):
            md_level = mdraid.getRaidLevel(raid_level)
            min_disks = md_level.min_members
            if len(self._device_disks) < min_disks:
                error = _(RAID_NOT_ENOUGH_DISKS) % {"level": md_level,
                                                    "min" : min_disks,
                                                    "count": len(self._device_disks)}

        if error:
            self.set_warning(error)
            self.window.show_all()
            self._populate_right_side(selector)
            return

        # If the device is a btrfs volume, the only things we can set/update
        # are mountpoint and container-wide settings.
        if device_type == DEVICE_TYPE_BTRFS and hasattr(use_dev, "subvolumes"):
            size = 0
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
                    self.set_warning(_(DEVICE_CONFIGURATION_ERROR_MSG))
                    self.window.show_all()

                    if _device is None:
                        # in this case we have removed the old device so we now have
                        # to re-create it

                        # the disks need to be updated since we've replaced all
                        # of the devices with copies in the devicefactory error
                        # handler
                        old_disk_names = [d.name for d in old_disks]
                        old_disks = [self._storage_playground.devicetree.getDeviceByName(n) for n in old_disk_names]
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
                            self.set_warning(_(UNRECOVERABLE_ERROR_MSG))
                            self.window.show_all()
                            return

            self._update_device_in_selectors(device, selector.device)
            self._devices = self._storage_playground.devices

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
                self._storage_playground.resetDevice(original_device)

        if changed_size and device.resizable:
            # If no size was specified, we just want to grow to
            # the maximum.  But resizeDevice doesn't take None for
            # a value.
            if not size:
                size = device.maxSize
            elif size < device.minSize:
                size = device.minSize
            elif size > device.maxSize:
                size = device.maxSize

            # And then we need to re-check that the max size is actually
            # different from the current size.
            _changed_size = False
            if size != device.size and size == device.currentSize:
                # size has been set back to its original value
                actions = self._storage_playground.devicetree.findActions(type="resize",
                                                                devid=device.id)
                with ui_storage_logger():
                    for action in reversed(actions):
                        self._storage_playground.devicetree.cancelAction(action)
                        _changed_size = True
            elif size != device.size:
                log.debug("scheduling resize of device %s to %s", device.name, size)

                with ui_storage_logger():
                    try:
                        self._storage_playground.resizeDevice(device, size)
                    except StorageError as e:
                        log.error("failed to schedule device resize: %s", e)
                        device.size = old_size
                        self._error = e
                        self.set_warning(_("Device resize request failed. "
                                           "Click for details."))
                        self.window.show_all()
                    else:
                        _changed_size = True

            if _changed_size:
                log.debug("new size: %s", device.size)
                log.debug("target size: %s", device.targetSize)

                # update the selector's size property
                for s in self._accordion.allSelectors:
                    if s._device == device:
                        s.size = str(device.size)

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
                        self._storage_playground.destroyDevice(device)
                        self._devices.remove(device)
                        old_device = device
                        device = device.slave
                        selector.device = device
                        self._update_device_in_selectors(old_device, device)
                elif encrypted:
                    log.info("applying encryption to %s", device.name)
                    with ui_storage_logger():
                        old_device = device
                        new_fmt = getFormat("luks", device=device.path)
                        self._storage_playground.formatDevice(device, new_fmt)
                        luks_dev = LUKSDevice("luks-" + device.name,
                                              parents=[device])
                        self._storage_playground.createDevice(luks_dev)
                        self._devices.append(luks_dev)
                        device = luks_dev
                        selector.device = device
                        self._update_device_in_selectors(old_device, device)

                self._devices = self._storage_playground.devices

            #
            # FORMATTING
            #
            log.info("scheduling reformat of %s as %s", device.name, new_fs_type)
            with ui_storage_logger():
                old_format = device.format
                new_format = getFormat(fs_type,
                                       mountpoint=mountpoint, label=label,
                                       device=device.path)
                try:
                    self._storage_playground.formatDevice(device, new_format)
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
                        if _selector.device in (device, old_device):
                            if page.pageTitle == translated_new_install_name():
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
               validate_label(label, device.format) == "":
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
            if new_name in self._storage_playground.names:
                use_dev._name = old_name
                self.set_info(_("Specified name %s already in use.") % new_name)
            else:
                selectorFromDevice(device, selector=selector)

        self._populate_right_side(selector)

    def _raid_level_visible(self, model, itr, user_data):
        device_type = self._get_current_device_type()
        raid_level = model[itr][1]
        return raid_level in get_supported_raid_levels(device_type)

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
            if row[1] == raid_level:
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
        log.debug("populate_right_side: %s", selector.device)

        device = selector.device
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

        log.debug("updated device_container_name to %s", self._device_container_name)
        log.debug("updated device_container_raid_level to %s", self._device_container_raid_level)
        log.debug("updated device_container_encrypted to %s", self._device_container_encrypted)
        log.debug("updated device_container_size to %s", self._device_container_size)

        self._selectedDeviceLabel.set_text(selector.props.name)
        desc = _(MOUNTPOINT_DESCRIPTIONS.get(selector.props.name, ""))
        self._selectedDeviceDescLabel.set_text(desc)

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

        self._sizeEntry.set_text(device.size.humanReadable(max_places=None))

        self._reformatCheckbox.set_active(not device.format.exists)
        fancy_set_sensitive(self._reformatCheckbox, not device.protected and
                                                          use_dev.exists and
                                                          not use_dev.type.startswith("btrfs"))

        self._encryptCheckbox.set_active(isinstance(device, LUKSDevice))
        self._encryptCheckbox.set_sensitive(self._reformatCheckbox.get_active())
        ancestors = use_dev.ancestors
        ancestors.remove(use_dev)
        if any(a.format.type == "luks" for a in ancestors):
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
                            PARTITION_ONLY_FORMAT_TYPES + ["swap"])
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
                name = self._storage_playground.suggestDeviceName(swap=swap,
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
        if use_dev.exists or use_dev.type == "btrfs volume":
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

    def _do_check(self):
        self.clear_errors()
        StorageChecker.errors = []
        StorageChecker.warnings = []

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
            self.storage.setUpBootLoader()
        except BootLoaderError as e:
            log.error("storage configuration failed: %s", e)
            StorageChecker.errors = str(e).split("\n")
            self.data.bootloader.bootDrive = ""

        StorageChecker.checkStorage(self)

        if self.errors:
            self.set_warning(_("Error checking storage configuration.  Click for details or press Done again to continue."))
        elif self.warnings:
            self.set_warning(_("Warning checking storage configuration.  Click for details or press Done again to continue."))

        # on_info_bar_clicked requires self._error to be set, so set it to the
        # list of all errors and warnings that storage checking found.
        self.window.show_all()
        self._error = "\n".join(self.errors + self.warnings)

        return bool(self._error == "")

    def on_back_clicked(self, button):
        # First, save anything from the currently displayed mountpoint.
        self._save_right_side(self._current_selector)

        # And then display the summary screen.  From there, the user will either
        # head back to the hub, or stay on the custom screen.
        self._storage_playground.devicetree.pruneActions()
        self._storage_playground.devicetree.sortActions()


        # If back has been clicked on once already and no other changes made on the screen,
        # run the storage check now.  This handles displaying any errors in the info bar.
        if not self._back_already_clicked:
            self._back_already_clicked = True

            new_luks = [d for d in self._storage_playground.devices
                       if d.format.type == "luks" and not d.format.exists]
            if new_luks:
                dialog = PassphraseDialog(self.data)
                with enlightbox(self.window, dialog.window):
                    rc = dialog.run()

                if rc != 1:
                    # Cancel. Leave the old passphrase set if there was one.
                    return

                self.passphrase = dialog.passphrase

            for luks in new_luks:
                if not luks.format.hasKey:
                    luks.format.passphrase = self.passphrase

            if not self._do_check():
                return

        if len(self._storage_playground.devicetree.findActions()) > 0:
            dialog = ActionSummaryDialog(self.data)
            with enlightbox(self.window, dialog.window):
                dialog.refresh(self._storage_playground.devicetree.findActions())
                rc = dialog.run()

            if rc != 1:
                # Cancel.  Stay on the custom screen.
                return

        NormalSpoke.on_back_clicked(self, button)

    def on_add_clicked(self, button):
        self._save_right_side(self._current_selector)
        self._back_already_clicked = False

        dialog = AddDialog(self.data,
                           mountpoints=self._storage_playground.mountpoints.keys())
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
             fstype in PARTITION_ONLY_FORMAT_TYPES)):
            device_type = DEVICE_TYPE_PARTITION

        # we shouldn't create swap on a thinly provisioned volume
        if fstype == "swap" and device_type == DEVICE_TYPE_LVM_THINP:
            device_type = DEVICE_TYPE_LVM

        # encryption of thinly provisioned volumes isn't supported
        if encrypted and device_type == DEVICE_TYPE_LVM_THINP:
            encrypted = False

        # some devices should never be encrypted
        if ((mountpoint and mountpoint.startswith("/boot")) or
            fstype in PARTITION_ONLY_FORMAT_TYPES):
            encrypted = False

        disks = self._clearpartDevices
        self.clear_errors()

        with ui_storage_logger():
            factory = devicefactory.get_device_factory(self._storage_playground,
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

                # The container is already encrypted
                if container.encrypted:
                    encrypted = False

            try:
                self._storage_playground.factoryDevice(device_type,
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
                        self._storage_playground.factoryDevice(device_type,
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
                        type_str = _(DEVICE_TEXT_MAP[device_type])
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

        self._devices = self._storage_playground.devices
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
                    self._storage_playground.initializeDisk(device)
                elif device.type.startswith("btrfs") and not device.isleaf:
                    self._storage_playground.recursiveRemove(device)
                else:
                    self._storage_playground.destroyDevice(device)
            except StorageError as e:
                log.error("failed to schedule device removal: %s", e)
                self._error = e
                self.set_warning(_("Device removal request failed. Click "
                                   "for details."))
                self.window.show_all()
            else:
                if is_logical_partition:
                    self._storage_playground.removeEmptyExtendedPartitions()

        # If we've just removed the last partition and the disklabel is pre-
        # existing, reinitialize the disk.
        if device.type == "partition" and device.exists and \
           device.disk.format.exists:
            with ui_storage_logger():
                if self._storage_playground.shouldClear(device.disk):
                    self._storage_playground.initializeDisk(device.disk)

        self._devices = self._storage_playground.devices

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
           self._storage_playground.devicetree.getChildren(container) and \
           container.size_policy == SIZE_POLICY_AUTO:
            cont_encrypted = container.encrypted
            cont_raid = get_raid_level(container)
            cont_size = container.size_policy
            cont_name = container.name
            with ui_storage_logger():
                factory = devicefactory.get_device_factory(self._storage_playground,
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
        device = self._current_selector.device
        root_name = None
        if selector.root:
            root_name = selector.root.name
        elif page:
            root_name = page.pageTitle

        log.debug("removing device '%s' from page %s", device, root_name)

        if root_name == translated_new_install_name():
            if device.exists:
                # This is an existing device that was added to the new page.
                # All we want to do is revert any changes to the device and
                # it will end up back in whatever old pages it came from.
                with ui_storage_logger():
                    self._storage_playground.resetDevice(device)

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
                subvols = (device.type.startswith("btrfs") and
                           not device.isleaf)
                dialog.refresh(getattr(device.format, "mountpoint", ""),
                               device.name, root_name, subvols=subvols)
                rc = dialog.run()

                if rc != 1:
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

        device = selector.device
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

        if rc != 1:
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
                                 exists=getattr(container, "exists", False))

        with enlightbox(self.window, dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc != 1:
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
        if name != container_name and name in self._storage_playground.names:
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

    def _container_store_row(self, name, freeSpace=None):
        if freeSpace is not None:
            return [name, _("(%s free)") % freeSpace]
        else:
            return [name, ""]

    def on_modify_container_clicked(self, button):
        container_name = self._containerStore[self._containerCombo.get_active()][0]
        container = self._storage_playground.devicetree.getDeviceByName(container_name)

        # pass the name along with any found vg since we could be modifying a
        # vg that hasn't been instantiated yet
        self.run_container_editor(container=container, name=container_name)

        log.debug("%s -> %s", container_name, self._device_container_name)
        if container_name == self._device_container_name:
            return

        log.debug("renaming container %s to %s", container_name, self._device_container_name)
        if container:
            # btrfs volume name/label does not go in the name list
            if container.name in self._storage_playground.devicetree.names:
                self._storage_playground.devicetree.names.remove(container.name)
                self._storage_playground.devicetree.names.append(self._device_container_name)

            # until there's a setter for btrfs volume name
            container._name = self._device_container_name
            if container.format.type == "btrfs":
                container.format.label = self._device_container_name

        container_exists = getattr(container, "exists", False)
        found = None

        for idx, data in enumerate(self._containerStore):
            # we're looking for the original vg name
            if data[0] == container_name:
                c = self._storage_playground.devicetree.getDeviceByName(self._device_container_name)
                freeSpace = getattr(c, "freeSpace", None)

                self._containerStore.insert(idx, self._container_store_row(self._device_container_name, freeSpace))
                self._containerCombo.set_active(idx)
                self._modifyContainerButton.set_sensitive(not container_exists)

                found = idx
                break

        if found:
            self._containerStore.remove(self._containerStore.get_iter_from_string("%s" % found))

        self._update_selectors()

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
        container_type = get_container_type_name(device_type).lower()
        new_text = _(NEW_CONTAINER_TEXT) % {"container_type": container_type}
        if container_name == new_text:
            # run the vg editor dialog with a default name and disk set
            hostname = self.data.network.hostname
            name = self._storage_playground.suggestContainerName(hostname=hostname)
            self.run_container_editor(name=name)
            for idx, data in enumerate(self._containerStore):
                if data[0] == new_text:
                    c = self._storage_playground.devicetree.getDeviceByName(self._device_container_name)
                    freeSpace = getattr(c, "freeSpace", None)
                    row = self._container_store_row(self._device_container_name, freeSpace)

                    self._containerStore.insert(idx, row)
                    combo.set_active(idx)   # triggers a call to this method
                    return
        else:
            self._device_container_name = container_name

        container = self._storage_playground.devicetree.getDeviceByName(self._device_container_name)
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
        log.debug("current selector: %s", self._current_selector.device)
        nb_page = self._partitionsNotebook.get_current_page()
        log.debug("notebook page = %s", nb_page)
        if nb_page == NOTEBOOK_DETAILS_PAGE:
            self._save_right_side(self._current_selector)
            self._back_already_clicked = False

        self._clear_current_selector()

    def on_selector_clicked(self, selector):
        if not self._initialized or (self._current_selector is selector):
            return

        # Take care of the previously chosen selector.
        if self._current_selector:
            # unselect the previously chosen selector
            self._current_selector.set_chosen(False)
            self._save_current_selector()
            log.debug("new selector: %s", selector.device)

        no_edit = False
        if selector.device.format.type == "luks" and \
           selector.device.format.exists:
            self._partitionsNotebook.set_current_page(NOTEBOOK_LUKS_PAGE)
            selectedDeviceLabel = self._encryptedDeviceLabel
            selectedDeviceDescLabel = self._encryptedDeviceDescLabel
            no_edit = True
        elif not getattr(selector.device, "complete", True):
            self._partitionsNotebook.set_current_page(NOTEBOOK_INCOMPLETE_PAGE)
            selectedDeviceLabel = self._incompleteDeviceLabel
            selectedDeviceDescLabel = self._incompleteDeviceDescLabel

            if selector.device.type == "mdarray":
                total = selector.device.memberDevices
                missing = total - len(selector.device.parents)
                txt = _("This Software RAID array is missing %(missingMembers)d of %(totalMembers)d member "
                        "partitions. You can remove it or select a different "
                        "device.") % {"missingMembers": missing, "totalMembers": total}
            else:
                total = selector.device.pvCount
                missing = total - len(selector.device.parents)
                txt = _("This LVM Volume Group is missing %(missingPVs)d of %(totalPVs)d physical "
                        "volumes. You can remove it or select a different "
                        "device.") % {"missingPVs": missing, "totalPVs": total}
            self._incompleteDeviceOptionsLabel.set_text(txt)
            no_edit = True
        elif devicefactory.get_device_type(selector.device) is None:
            self._partitionsNotebook.set_current_page(NOTEBOOK_UNEDITABLE_PAGE)
            selectedDeviceLabel = self._uneditableDeviceLabel
            selectedDeviceDescLabel = self._uneditableDeviceDescLabel
            no_edit = True

        if no_edit:
            selectedDeviceLabel.set_text(selector.device.name)
            desc = _(MOUNTPOINT_DESCRIPTIONS.get(selector.device.type, ""))
            selectedDeviceDescLabel.set_text(desc)
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
        self._configButton.set_sensitive(not selector.device.exists and
                                         not selector.device.protected and
                                         devicefactory.get_device_type(selector.device) in (DEVICE_TYPE_PARTITION, DEVICE_TYPE_MD))
        self._removeButton.set_sensitive(not selector.device.protected)
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
        """Helper function for on_create_clicked.
           Assumes a non-final context in which at least some errors
           discovered by sanityCheck are not considered fatal because they
           will be dealt with later.

           Note: There are never any non-existent devices around when this runs.
        """
        log.debug("running automatic partitioning")
        self._storage_playground.doAutoPart = True
        self.clear_errors()
        with ui_storage_logger():
            try:
                doAutoPartition(self._storage_playground, self.data)
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
                self._devices = self._storage_playground.devices
                # mark all new containers for automatic size management
                for device in self._devices:
                    if not device.exists and hasattr(device, "size_policy"):
                        device.size_policy = SIZE_POLICY_AUTO
            finally:
                self._storage_playground.doAutoPart = False
                log.debug("finished automatic partitioning")

            exns = self._storage_playground.sanityCheck()
            errors = [exn for exn in exns if isinstance(exn, SanityError) and not isinstance(exn, LUKSDeviceWithoutKeyError)]
            warnings = [exn for exn in exns if isinstance(exn, SanityWarning)]
            for error in errors:
                log.error(error.message)
            for warning in warnings:
                log.warning(warning.message)

            if errors:
                messages = "\n".join(error.message for error in errors)
                log.error("doAutoPartition failed: %s", messages)
                self._reset_storage()
                self._error = messages
                self.set_error(_("Automatic partitioning failed. Click "
                                 "for details."))
                self.window.show_all()

    def on_create_clicked(self, button, autopartTypeCombo):
        # Then do autopartitioning.  We do not do any clearpart first.  This is
        # custom partitioning, so you have to make your own room.
        self._storage_playground.autoPartType = autopartTypeCombo.get_active()
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
            device = self._current_selector.device
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

    def on_fs_type_changed(self, combo):
        if not self._initialized:
            return

        new_type = combo.get_active_text()
        if new_type is None:
            return
        log.debug("fs type changed: %s", new_type)
        fmt = getFormat(new_type)
        fancy_set_sensitive(self._mountPointEntry, fmt.mountable)

    def _populate_container(self, device=None):
        """ Set up the vg widgets for lvm or hide them for other types. """
        device_type = self._get_current_device_type()
        if device is None:
            if self._current_selector is None:
                return

            device = self._current_selector.device
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
                factory = devicefactory.get_device_factory(self._storage_playground,
                                                         device_type,
                                                         0)
                container = factory.get_container(device=_device)
                default_container = getattr(container, "name", None)
                if container:
                    container_size_policy = container.size_policy

            container_type_text = get_container_type_name(device_type)
            self._containerLabel.set_text(container_type_text.title())
            self._containerStore.clear()
            if device_type == DEVICE_TYPE_BTRFS:
                containers = self._storage_playground.btrfsVolumes
            else:
                containers = self._storage_playground.vgs

            default_seen = False
            for c in containers:
                self._containerStore.append(self._container_store_row(c.name, getattr(c, "freeSpace", None)))
                if default_container and c.name == default_container:
                    default_seen = True
                    self._containerCombo.set_active(containers.index(c))

            if default_container is None:
                hostname = self.data.network.hostname
                default_container = self._storage_playground.suggestContainerName(hostname=hostname)

            log.debug("default container is %s", default_container)
            self._device_container_name = default_container
            self._device_container_size = container_size_policy

            if not default_seen:
                self._containerStore.append(self._container_store_row(default_container))
                self._containerCombo.set_active(len(self._containerStore) - 1)

            self._containerStore.append(self._container_store_row(_(NEW_CONTAINER_TEXT) % {"container_type": container_type_text.lower()}))
            self._containerCombo.set_tooltip_text(_(CONTAINER_TOOLTIP) % {"container_type": container_type_text.lower()})
            if default_container is None:
                self._containerCombo.set_active(len(self._containerStore) - 1)

            map(really_show, [self._containerLabel, self._containerCombo, self._modifyContainerButton])

            # make the combo and button insensitive for existing LVs
            can_change_container = (device is not None and not device.exists and
                                    device != container)
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
                factory = devicefactory.get_device_factory(self._storage_playground,
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
        exists = self._current_selector and self._current_selector.device.exists
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
        msg = _("Continuing with this action will reset all your partitioning selections "
                "to their current on-disk state.")

        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.NONE,
                                message_format=msg)
        dlg.set_decorated(False)
        dlg.add_buttons(_("_Reset selections"), 0, _("_Preserve current selections"), 1)
        dlg.set_default_response(1)

        with enlightbox(self.window, dlg):
            rc = dlg.run()
            dlg.destroy()

        if rc == 0:
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
        self._back_already_clicked = False
        self._applyButton.set_sensitive(False)

    def on_unlock_clicked(self, button):
        """ try to open the luks device, populate, then call _do_refresh. """
        self.clear_errors()
        device = self._current_selector.device
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
            self._storage_playground.devicetree._addDevice(luks_dev)
            # save the passphrase for possible reset and to try for other devs
            self._storage_playground.savePassphrase(device)
            # XXX What if the user has changed things using the shell?
            self._storage_playground.devicetree.populate()
            # look for new roots
            self._storage_playground.roots = findExistingInstallations(self._storage_playground.devicetree)

        self._devices = self._storage_playground.devices
        self._clear_current_selector()
        self._do_refresh()

    def on_value_changed(self, *args):
        self._applyButton.set_sensitive(True)
