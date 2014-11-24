# Storage configuration spoke classes
#
# Copyright (C) 2011-2014  Red Hat, Inc.
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#                    Chris Lumens <clumens@redhat.com>
#

"""
    TODO:

        - add button within sw_needs text in options dialogs 2,3
        - udev data gathering
            - udev fwraid, mpath would sure be nice
        - status/completed
            - what are noteworthy status events?
                - disks selected
                    - exclusiveDisks non-empty
                - sufficient space for software selection
                - autopart selected
                - custom selected
                    - performing custom configuration
                - storage configuration complete
        - spacing and border width always 6

"""

from gi.repository import Gdk, GLib, AnacondaWidgets

from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.lib.disks import getDisks, isLocalDisk, applyDiskSelection
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.passphrase import PassphraseDialog
from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
from pyanaconda.ui.gui.spokes.lib.resize import ResizeDialog
from pyanaconda.ui.gui.spokes.lib.dasdfmt import DasdFormatDialog
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.gui.utils import escape_markup, gtk_action_nowait, ignoreEscape
from pyanaconda.ui.helpers import StorageChecker

from pyanaconda.kickstart import doKickstartStorage, refreshAutoSwapSize, resetCustomStorageData
from blivet import arch
from blivet.size import Size
from blivet.devices import MultipathDevice
from blivet.errors import StorageError, DasdFormatError
from blivet.platform import platform
from blivet.devicelibs import swap as swap_lib
from blivet.devicelibs.dasd import make_unformatted_dasd_list, format_dasd
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.product import productName
from pyanaconda.flags import flags
from pyanaconda.i18n import _, C_, CN_, P_
from pyanaconda import constants
from pyanaconda import isys
from pyanaconda.bootloader import BootLoaderError

from pykickstart.constants import CLEARPART_TYPE_NONE, AUTOPART_TYPE_LVM
from pykickstart.errors import KickstartValueError

import sys

import logging
log = logging.getLogger("anaconda")

__all__ = ["StorageSpoke"]

# Response ID codes for all the various buttons on all the dialogs.
RESPONSE_CANCEL = 0
RESPONSE_MODIFY_SW = 2
RESPONSE_RECLAIM = 3
RESPONSE_QUIT = 4

class InstallOptionsDialogBase(GUIObject):
    uiFile = "spokes/storage.glade"

    def __init__(self, *args, **kwargs):
        self.payload = kwargs.pop("payload", None)
        GUIObject.__init__(self, *args, **kwargs)

        self._grabObjects()

    def _grabObjects(self):
        pass

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    def _modify_sw_link_clicked(self, label, uri):
        if self._software_is_ready():
            self.window.response(RESPONSE_MODIFY_SW)

        return True

    def _get_sw_needs_text(self, required_space, auto_swap):
        tooltip = _("Please wait... software metadata still loading.")
        sw_text = (_("Your current <a href=\"\" title=\"%(tooltip)s\"><b>%(product)s</b> software "
                     "selection</a> requires <b>%(total)s</b> of available "
                     "space, including <b>%(software)s</b> for software and "
                     "<b>%(swap)s</b> for swap space.")
                   % {"tooltip": escape_markup(tooltip),
                      "product": escape_markup(productName),
                      "total": escape_markup(str(required_space + auto_swap)),
                      "software": escape_markup(str(required_space)),
                      "swap": escape_markup(str(auto_swap))})
        return sw_text

    # Methods to handle sensitivity of the modify button.
    def _software_is_ready(self):
        # FIXME:  Would be nicer to just ask the spoke if it's ready.
        return (not threadMgr.get(constants.THREAD_PAYLOAD) and
                not threadMgr.get(constants.THREAD_SOFTWARE_WATCHER) and
                not threadMgr.get(constants.THREAD_CHECK_SOFTWARE) and
                self.payload.baseRepo is not None)

    def _check_for_storage_thread(self, button):
        if self._software_is_ready():
            button.set_has_tooltip(False)

            # False means this function should never be called again.
            return False
        else:
            return True

    def _add_modify_watcher(self, widget):
        # If the payload fetching thread is still running, the user can't go to
        # modify the software selection screen.  Thus, we have to set the button
        # insensitive and wait until software selection is ready to go.
        if not self._software_is_ready():
            GLib.timeout_add_seconds(1, self._check_for_storage_thread, widget)

class NeedSpaceDialog(InstallOptionsDialogBase):
    builderObjects = ["need_space_dialog"]
    mainWidgetName = "need_space_dialog"

    def _grabObjects(self):
        self.disk_free_label = self.builder.get_object("need_space_disk_free_label")
        self.fs_free_label = self.builder.get_object("need_space_fs_free_label")

    def _set_free_space_labels(self, disk_free, fs_free):
        self.disk_free_label.set_text(str(disk_free))
        self.fs_free_label.set_text(str(fs_free))

    # pylint: disable=arguments-differ
    def refresh(self, required_space, auto_swap, disk_free, fs_free):
        sw_text = self._get_sw_needs_text(required_space, auto_swap)
        label_text = _("%s The disks you've selected have the following "
                       "amounts of free space:") % sw_text
        label = self.builder.get_object("need_space_desc_label")
        label.set_markup(label_text)
        label.connect("activate-link", self._modify_sw_link_clicked)

        self._set_free_space_labels(disk_free, fs_free)

        label_text = _("<b>You don't have enough space available to install "
                       "%s</b>.  You can shrink or remove existing partitions "
                       "via our guided reclaim space tool, or you can adjust your "
                       "partitions on your own in the custom partitioning "
                       "interface.") % escape_markup(productName)
        self.builder.get_object("need_space_options_label").set_markup(label_text)

        self._add_modify_watcher(label)

class NoSpaceDialog(InstallOptionsDialogBase):
    builderObjects = ["no_space_dialog"]
    mainWidgetName = "no_space_dialog"

    def _grabObjects(self):
        self.disk_free_label = self.builder.get_object("no_space_disk_free_label")
        self.fs_free_label = self.builder.get_object("no_space_fs_free_label")

    def _set_free_space_labels(self, disk_free, fs_free):
        self.disk_free_label.set_text(str(disk_free))
        self.fs_free_label.set_text(str(fs_free))

    # pylint: disable=arguments-differ
    def refresh(self, required_space, auto_swap, disk_free, fs_free):
        sw_text = self._get_sw_needs_text(required_space, auto_swap)
        label_text = (_("%(sw_text)s You don't have enough space available to install "
                        "<b>%(product)s</b>, even if you used all of the free space "
                        "available on the selected disks.")
                      % {"sw_text": escape_markup(sw_text),
                         "product": escape_markup(productName)})
        label = self.builder.get_object("no_space_desc_label")
        label.set_markup(label_text)
        label.connect("activate-link", self._modify_sw_link_clicked)

        self._set_free_space_labels(disk_free, fs_free)

        label_text = _("<b>You don't have enough space available to install "
                       "%(productName)s</b>, even if you used all of the free space "
                       "available on the selected disks.  You could add more "
                       "disks for additional space, "
                       "modify your software selection to install a smaller "
                       "version of <b>%(productName)s</b>, or quit the installer.") % \
                               {"productName": escape_markup(productName)}
        self.builder.get_object("no_space_options_label").set_markup(label_text)

        self._add_modify_watcher(label)

class StorageSpoke(NormalSpoke, StorageChecker):
    builderObjects = ["storageWindow", "addSpecializedImage"]
    mainWidgetName = "storageWindow"
    uiFile = "spokes/storage.glade"
    helpFile = "StorageSpoke.xml"

    category = SystemCategory

    # other candidates: computer-symbolic, folder-symbolic
    icon = "drive-harddisk-symbolic"
    title = CN_("GUI|Spoke", "INSTALLATION _DESTINATION")

    def __init__(self, *args, **kwargs):
        StorageChecker.__init__(self, min_ram=isys.MIN_GUI_RAM)
        NormalSpoke.__init__(self, *args, **kwargs)
        self.applyOnSkip = True

        self._ready = False
        self.autoPartType = None
        self.encrypted = False
        self.passphrase = ""
        self.selected_disks = self.data.ignoredisk.onlyuse[:]

        # This list contains all possible disks that can be included in the install.
        # All types of advanced disks should be set up for us ahead of time, so
        # there should be no need to modify this list.
        self.disks = []

        if not flags.automatedInstall:
            # default to using autopart for interactive installs
            self.data.autopart.autopart = True

        self.autopart = self.data.autopart.autopart
        self.autoPartType = None
        self.clearPartType = CLEARPART_TYPE_NONE

        if self.data.zerombr.zerombr and arch.isS390():
            # run dasdfmt on any unformatted DASDs automatically
            threadMgr.add(AnacondaThread(name=constants.THREAD_DASDFMT,
                            target=self.run_dasdfmt))

        self._previous_autopart = False

        self._last_clicked_overview = None
        self._cur_clicked_overview = None

        self._grabObjects()

    def _grabObjects(self):
        self._customPart = self.builder.get_object("customRadioButton")
        self._encrypted = self.builder.get_object("encryptionCheckbox")
        self._reclaim = self.builder.get_object("reclaimCheckbox")

    def apply(self):
        applyDiskSelection(self.storage, self.data, self.selected_disks)
        self.data.autopart.autopart = self.autopart
        self.data.autopart.type = self.autoPartType
        self.data.autopart.encrypted = self.encrypted
        self.data.autopart.passphrase = self.passphrase

        self.clearPartType = CLEARPART_TYPE_NONE

        if self.data.bootloader.bootDrive and \
           self.data.bootloader.bootDrive not in self.selected_disks:
            self.data.bootloader.bootDrive = ""
            self.storage.bootloader.reset()

        self.data.clearpart.initAll = True
        self.data.clearpart.type = self.clearPartType
        self.storage.config.update(self.data)
        self.storage.autoPartType = self.data.autopart.type
        self.storage.encryptedAutoPart = self.data.autopart.encrypted
        self.storage.encryptionPassphrase = self.data.autopart.passphrase

        # If autopart is selected we want to remove whatever has been
        # created/scheduled to make room for autopart.
        # If custom is selected, we want to leave alone any storage layout the
        # user may have set up before now.
        self.storage.config.clearNonExistent = self.data.autopart.autopart

    @gtk_action_nowait
    def execute(self):
        # Spawn storage execution as a separate thread so there's no big delay
        # going back from this spoke to the hub while StorageChecker.run runs.
        # Yes, this means there's a thread spawning another thread.  Sorry.
        threadMgr.add(AnacondaThread(name=constants.THREAD_EXECUTE_STORAGE,
                                     target=self._doExecute))

    def _doExecute(self):
        self._ready = False
        hubQ.send_not_ready(self.__class__.__name__)
        # on the off-chance dasdfmt is running, we can't proceed further
        threadMgr.wait(constants.THREAD_DASDFMT)
        hubQ.send_message(self.__class__.__name__, _("Saving storage configuration..."))
        try:
            doKickstartStorage(self.storage, self.data, self.instclass)
        except (StorageError, KickstartValueError) as e:
            log.error("storage configuration failed: %s", e)
            StorageChecker.errors = str(e).split("\n")
            hubQ.send_message(self.__class__.__name__, _("Failed to save storage configuration..."))
            self.data.bootloader.bootDrive = ""
            self.data.ignoredisk.drives = []
            self.data.ignoredisk.onlyuse = []
            self.storage.config.update(self.data)
            self.storage.reset()
            self.disks = getDisks(self.storage.devicetree)
            # now set ksdata back to the user's specified config
            applyDiskSelection(self.storage, self.data, self.selected_disks)
        except BootLoaderError as e:
            log.error("BootLoader setup failed: %s", e)
            StorageChecker.errors = str(e).split("\n")
            hubQ.send_message(self.__class__.__name__, _("Failed to save storage configuration..."))
            self.data.bootloader.bootDrive = ""
        else:
            if self.autopart:
                self.run()
        finally:
            resetCustomStorageData(self.data)
            self._ready = True
            hubQ.send_ready(self.__class__.__name__, True)

    @property
    def completed(self):
        retval = (threadMgr.get(constants.THREAD_EXECUTE_STORAGE) is None and
                  threadMgr.get(constants.THREAD_CHECK_STORAGE) is None and
                  self.storage.rootDevice is not None and
                  not self.errors)
        return retval

    @property
    def ready(self):
        # By default, the storage spoke is not ready.  We have to wait until
        # storageInitialize is done.
        return self._ready

    @property
    def showable(self):
        return not flags.dirInstall

    @property
    def status(self):
        """ A short string describing the current status of storage setup. """
        msg = _("No disks selected")

        if flags.automatedInstall and not self.storage.rootDevice:
            return msg
        elif threadMgr.get(constants.THREAD_DASDFMT):
            msg = _("Formatting DASDs")
        elif self.data.ignoredisk.onlyuse:
            msg = P_(("%d disk selected"),
                     ("%d disks selected"),
                     len(self.data.ignoredisk.onlyuse)) % len(self.data.ignoredisk.onlyuse)

            if self.errors:
                msg = _("Error checking storage configuration")
            elif self.warnings:
                msg = _("Warning checking storage configuration")
            elif self.data.autopart.autopart:
                msg = _("Automatic partitioning selected")
            else:
                msg = _("Custom partitioning selected")

        return msg

    @property
    def localOverviews(self):
        return self.local_disks_box.get_children()

    @property
    def advancedOverviews(self):
        return filter(lambda child: isinstance(child, AnacondaWidgets.DiskOverview),
                      self.specialized_disks_box.get_children())

    def _on_disk_clicked(self, overview, event):
        # This handler only runs for these two kinds of events, and only for
        # activate-type keys (space, enter) in the latter event's case.
        if not event.type in [Gdk.EventType.BUTTON_PRESS, Gdk.EventType.KEY_RELEASE]:
            return

        if event.type == Gdk.EventType.KEY_RELEASE and \
           event.keyval not in [Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter, Gdk.KEY_KP_Space]:
            return

        if event.type == Gdk.EventType.BUTTON_PRESS and \
                event.state & Gdk.ModifierType.SHIFT_MASK:
            # clicked with Shift held down

            if self._last_clicked_overview is None:
                # nothing clicked before, cannot apply Shift-click
                return

            local_overviews = self.localOverviews
            advanced_overviews = self.advancedOverviews

            # find out which list of overviews the clicked one belongs to
            if overview in local_overviews:
                from_overviews = local_overviews
            elif overview in advanced_overviews:
                from_overviews = advanced_overviews
            else:
                # should never happen, but if it does, no other actions should be done
                return

            if self._last_clicked_overview in from_overviews:
                # get index of the last clicked overview
                last_idx = from_overviews.index(self._last_clicked_overview)
            else:
                # overview from the other list clicked before, cannot apply "Shift-click"
                return

            # get index and state of the clicked overview
            cur_idx = from_overviews.index(overview)
            state = self._last_clicked_overview.get_chosen()

            if cur_idx > last_idx:
                copy_to = from_overviews[last_idx:cur_idx+1]
            else:
                copy_to = from_overviews[cur_idx:last_idx]

            # copy the state of the last clicked overview to the ones between it and the
            # one clicked with the Shift held down
            for disk_overview in copy_to:
                disk_overview.set_chosen(state)

        self._update_disk_list()
        self._update_summary()

    def _on_disk_focus_in(self, overview, event):
        self._last_clicked_overview = self._cur_clicked_overview
        self._cur_clicked_overview = overview

    def refresh(self):
        self.disks = getDisks(self.storage.devicetree)

        # synchronize our local data store with the global ksdata
        disk_names = [d.name for d in self.disks]
        # don't put disks with hidden formats in selected_disks
        self.selected_disks = [d for d in self.data.ignoredisk.onlyuse
                                    if d in disk_names]
        self.autopart = self.data.autopart.autopart
        self.autoPartType = self.data.autopart.type
        if self.autoPartType is None:
            self.autoPartType = AUTOPART_TYPE_LVM
        self.encrypted = self.data.autopart.encrypted
        self.passphrase = self.data.autopart.passphrase

        self._previous_autopart = self.autopart

        # First, remove all non-button children.
        for child in self.localOverviews + self.advancedOverviews:
            child.destroy()

        # Then deal with local disks, which are really easy.  They need to be
        # handled here instead of refresh to take into account the user pressing
        # the rescan button on custom partitioning.
        for disk in filter(isLocalDisk, self.disks):
            self._add_disk_overview(disk, self.local_disks_box)

        # Advanced disks are different.  Because there can potentially be a lot
        # of them, we do not display them in the box by default.  Instead, only
        # those selected in the filter UI are displayed.  This means refresh
        # needs to know to create and destroy overviews as appropriate.
        for name in self.data.ignoredisk.onlyuse:
            if name not in disk_names:
                continue
            obj = self.storage.devicetree.getDeviceByName(name, hidden=True)
            if isLocalDisk(obj):
                continue

            self._add_disk_overview(obj, self.specialized_disks_box)

        # update the selections in the ui
        for overview in self.localOverviews + self.advancedOverviews:
            name = overview.get_property("name")
            overview.set_chosen(name in self.selected_disks)

        self._customPart.set_active(not self.autopart)

        self._update_summary()

        if self.errors:
            self.set_warning(_("Error checking storage configuration.  Click for details."))
        elif self.warnings:
            self.set_warning(_("Warning checking storage configuration.  Click for details."))
        self.window.show_all()

    def initialize(self):
        NormalSpoke.initialize(self)

        self.local_disks_box = self.builder.get_object("local_disks_box")
        self.specialized_disks_box = self.builder.get_object("specialized_disks_box")

        threadMgr.add(AnacondaThread(name=constants.THREAD_STORAGE_WATCHER,
                      target=self._initialize))

    def _add_disk_overview(self, disk, box):
        if disk.removable:
            kind = "drive-removable-media"
        else:
            kind = "drive-harddisk"

        if disk.serial:
            popup_info = "%s" % disk.serial
        else:
            popup_info = None

        # We don't want to display the whole huge WWID for a multipath device.
        # That makes the DO way too wide.
        if isinstance(disk, MultipathDevice):
            desc = disk.wwid.split(":")
            description = ":".join(desc[0:3]) + "..." + ":".join(desc[-4:])
        else:
            description = disk.description

        free = self.storage.getFreeSpace(disks=[disk])[disk.name][0]

        overview = AnacondaWidgets.DiskOverview(description,
                                                kind,
                                                str(disk.size),
                                                _("%s free") % free,
                                                disk.name,
                                                popup=popup_info)
        box.pack_start(overview, False, False, 0)

        # FIXME: this will need to get smarter
        #
        # maybe a little function that resolves each item in onlyuse using
        # udev_resolve_devspec and compares that to the DiskDevice?
        overview.set_chosen(disk.name in self.selected_disks)
        overview.connect("button-press-event", self._on_disk_clicked)
        overview.connect("key-release-event", self._on_disk_clicked)
        overview.connect("focus-in-event", self._on_disk_focus_in)
        overview.show_all()

    def _initialize(self):
        hubQ.send_message(self.__class__.__name__, _("Probing storage..."))

        threadMgr.wait(constants.THREAD_STORAGE)
        threadMgr.wait(constants.THREAD_CUSTOM_STORAGE_INIT)

        self.disks = getDisks(self.storage.devicetree)

        # if there's only one disk, select it by default
        if len(self.disks) == 1 and not self.selected_disks:
            applyDiskSelection(self.storage, self.data, [self.disks[0].name])

        self._ready = True
        hubQ.send_ready(self.__class__.__name__, False)

    def _update_summary(self):
        """ Update the summary based on the UI. """
        count = 0
        capacity = Size(0)
        free = Size(0)

        # pass in our disk list so hidden disks' free space is available
        free_space = self.storage.getFreeSpace(disks=self.disks)
        selected = [d for d in self.disks if d.name in self.selected_disks]

        for disk in selected:
            capacity += disk.size
            free += free_space[disk.name][0]
            count += 1

        anySelected = count > 0

        summary = (P_("%(count)d disk selected; %(capacity)s capacity; %(free)s free",
                      "%(count)d disks selected; %(capacity)s capacity; %(free)s free",
                      count) % {"count" : count,
                                "capacity" : capacity,
                                "free" : free})
        summary_label = self.builder.get_object("summary_label")
        summary_label.set_text(summary)
        summary_label.set_sensitive(anySelected)

        # only show the "we won't touch your other disks" labels and summary button when
        # some disks are selected
        self.builder.get_object("summary_button_revealer").set_reveal_child(anySelected)
        self.builder.get_object("local_untouched_label_revealer").set_reveal_child(anySelected)
        self.builder.get_object("special_untouched_label_revealer").set_reveal_child(anySelected)
        self.builder.get_object("other_options_label").set_sensitive(anySelected)
        self.builder.get_object("other_options_grid").set_sensitive(anySelected)

        if len(self.disks) == 0:
            self.set_warning(_("No disks detected.  Please shut down the computer, connect at least one disk, and restart to complete installation."))
        elif not anySelected:
            self.set_warning(_("No disks selected; please select at least one disk to install to."))
        else:
            self.clear_info()

    def _update_disk_list(self):
        """ Update self.selected_disks based on the UI. """
        for overview in self.localOverviews + self.advancedOverviews:
            selected = overview.get_chosen()
            name = overview.get_property("name")

            if selected and name not in self.selected_disks:
                self.selected_disks.append(name)

            if not selected and name in self.selected_disks:
                self.selected_disks.remove(name)

    def run_dasdfmt(self):
        """
        Though the same function exists in pyanaconda.ui.gui.spokes.lib.dasdfmt,
        this instance doesn't include any of the UI pieces and should only
        really be getting called on ks installations with "zerombr".
        """
        # wait for the initial storage thread to complete before taking any new
        # actions on storage devices
        threadMgr.wait(constants.THREAD_STORAGE)

        to_format = make_unformatted_dasd_list(d.name for d in getDisks(self.storage.devicetree))
        if not to_format:
            # nothing to do here; bail
            return

        hubQ.send_message(self.__class__.__name__, _("Formatting DASDs"))
        for disk in to_format:
            try:
                format_dasd(disk)
            except DasdFormatError as err:
                # Log errors if formatting fails, but don't halt the installer
                log.error(str(err))
                continue

        # I really hate doing this, but the way is the way; probably the most
        # correct way to kajigger the storage spoke into becoming ready
        self.execute()

    # signal handlers
    def on_summary_clicked(self, button):
        # show the selected disks dialog
        # pass in our disk list so hidden disks' free space is available
        free_space = self.storage.getFreeSpace(disks=self.disks)
        dialog = SelectedDisksDialog(self.data,)
        dialog.refresh([d for d in self.disks if d.name in self.selected_disks],
                       free_space)
        self.run_lightbox_dialog(dialog)

        # update selected disks since some may have been removed
        self.selected_disks = [d.name for d in dialog.disks]

        # update the UI to reflect changes to self.selected_disks
        for overview in self.localOverviews:
            name = overview.get_property("name")

            overview.set_chosen(name in self.selected_disks)

        self._update_summary()

        self.data.bootloader.seen = True

        if self.data.bootloader.location == "none":
            self.set_warning(_("You have chosen to skip bootloader installation.  Your system may not be bootable."))
            self.window.show_all()
        else:
            self.clear_info()

    def run_lightbox_dialog(self, dialog):
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()

        return rc

    def _check_encrypted(self):
        # even if they're not doing autopart, setting autopart.encrypted
        # establishes a default of encrypting new devices
        if not self.encrypted:
            return True

        dialog = PassphraseDialog(self.data)
        rc = self.run_lightbox_dialog(dialog)
        if rc != 1:
            return False

        self.passphrase = dialog.passphrase

        for device in self.storage.devices:
            if device.format.type == "luks" and not device.format.exists:
                if not device.format.hasKey:
                    device.format.passphrase = self.passphrase

        return True

    def on_back_clicked(self, button):
        # We can't exit early if it looks like nothing has changed because the
        # user might want to change settings presented in the dialogs shown from
        # within this method.

        # Remove all non-existing devices if autopart was active when we last
        # refreshed.
        if self._previous_autopart:
            self._previous_autopart = False
            for partition in self.storage.partitions[:]:
                # check if it's been removed in a previous iteration
                if not partition.exists and \
                   partition in self.storage.partitions:
                    self.storage.recursiveRemove(partition)

        # hide/unhide disks as requested
        for disk in self.disks:
            if disk.name not in self.selected_disks and \
               disk in self.storage.devices:
                self.storage.devicetree.hide(disk)
            elif disk.name in self.selected_disks and \
                 disk not in self.storage.devices:
                self.storage.devicetree.unhide(disk)

        # show the installation options dialog
        disks = [d for d in self.disks if d.name in self.selected_disks]
        disks_size = sum((d.size for d in disks), Size(0))

        # No disks selected?  The user wants to back out of the storage spoke.
        if not disks:
            NormalSpoke.on_back_clicked(self, button)
            return

        if arch.isS390():
            # check for unformatted DASDs and launch dasdfmt if any discovered
            dasds = make_unformatted_dasd_list(self.selected_disks)
            if len(dasds) > 0:
                # We want to apply current selection before running dasdfmt to
                # prevent this information from being lost afterward
                applyDiskSelection(self.storage, self.data, self.selected_disks)
                dialog = DasdFormatDialog(self.data, self.storage, dasds)
                ignoreEscape(dialog.window)
                rc = self.run_lightbox_dialog(dialog)
                if rc == 1:
                    # User hit OK on the dialog
                    self.refresh()
                elif rc == 2:
                    # User clicked uri to return to hub.
                    NormalSpoke.on_back_clicked(self, button)
                    return
                elif rc != 2:
                    # User either hit cancel on the dialog or closed it via escape,
                    # there was no formatting done.
                    # NOTE: rc == 2 means the user clicked on the link that takes t
                    # back to the hub.
                    return

        # Figure out if the existing disk labels will work on this platform
        # you need to have at least one of the platform's labels in order for
        # any of the free space to be useful.
        disk_labels = set(disk.format.labelType for disk in disks
                              if hasattr(disk.format, "labelType"))
        platform_labels = set(platform.diskLabelTypes)
        if disk_labels and platform_labels.isdisjoint(disk_labels):
            disk_free = 0
            fs_free = 0
            log.debug("Need disklabel: %s have: %s", ", ".join(platform_labels),
                                                     ", ".join(disk_labels))
        else:
            free_space = self.storage.getFreeSpace(disks=disks,
                                                   clearPartType=CLEARPART_TYPE_NONE)
            disk_free = sum(f[0] for f in free_space.itervalues())
            fs_free = sum(f[1] for f in free_space.itervalues())

        required_space = self.payload.spaceRequired
        auto_swap = sum((r.size for r in self.storage.autoPartitionRequests
                                if r.fstype == "swap"), Size(0))
        if self.autopart and auto_swap == Size(0):
            # autopartitioning requested, but not applied yet (=> no auto swap
            # requests), ask user for enough space to fit in the suggested swap
            auto_swap = swap_lib.swapSuggestion()

        log.debug("disk free: %s  fs free: %s  sw needs: %s  auto swap: %s",
                  disk_free, fs_free, required_space, auto_swap)

        if disk_free >= required_space + auto_swap:
            dialog = None
        elif disks_size >= required_space:
            if self._customPart.get_active() or self._reclaim.get_active():
                dialog = None
            else:
                dialog = NeedSpaceDialog(self.data, payload=self.payload)
                dialog.refresh(required_space, auto_swap, disk_free, fs_free)
                rc = self.run_lightbox_dialog(dialog)
        else:
            dialog = NoSpaceDialog(self.data, payload=self.payload)
            dialog.refresh(required_space, auto_swap, disk_free, fs_free)
            rc = self.run_lightbox_dialog(dialog)

        if not dialog:
            # Plenty of room - there's no need to pop up a dialog, so just send
            # the user to wherever they asked to go.  That's either the custom
            # spoke or the hub.
            #    - OR -
            # Not enough room, but the user checked the reclaim button.

            self.encrypted = self._encrypted.get_active()

            if self._customPart.get_active():
                self.autopart = False
                self.skipTo = "CustomPartitioningSpoke"
            else:
                self.autopart = True

                # We might first need to ask about an encryption passphrase.
                if not self._check_encrypted():
                    return

                # Oh and then we might also want to go to the reclaim dialog.
                if self._reclaim.get_active():
                    self.apply()
                    if not self._show_resize_dialog(disks):
                        # User pressed cancel on the reclaim dialog, so don't leave
                        # the storage spoke.
                        return
        elif rc == RESPONSE_CANCEL:
            # A cancel button was clicked on one of the dialogs.  Stay on this
            # spoke.  Generally, this is because the user wants to add more disks.
            return
        elif rc == RESPONSE_MODIFY_SW:
            # The "Fedora software selection" link was clicked on one of the
            # dialogs.  Send the user to the software spoke.
            self.skipTo = "SoftwareSelectionSpoke"
        elif rc == RESPONSE_RECLAIM:
            # Not enough space, but the user can make enough if they do some
            # work and free up space.
            self.encrypted = self._encrypted.get_active()

            if not self._check_encrypted():
                return

            self.apply()
            if not self._show_resize_dialog(disks):
                # User pressed cancel on the reclaim dialog, so don't leave
                # the storage spoke.
                return

            # And then go to the custom partitioning spoke if they chose to
            # do so.
            if self._customPart.get_active():
                self.autopart = False
                self.skipTo = "CustomPartitioningSpoke"
            else:
                self.autopart = True
        elif rc == RESPONSE_QUIT:
            # Not enough space, and the user can't do anything about it so
            # they chose to quit.
            raise SystemExit("user-selected exit")
        else:
            # I don't know how we'd get here, but might as well have a
            # catch-all.  Just stay on this spoke.
            return

        if self.autopart:
            refreshAutoSwapSize(self.storage)
        self.applyOnSkip = True
        NormalSpoke.on_back_clicked(self, button)

    def _show_resize_dialog(self, disks):
        resizeDialog = ResizeDialog(self.data, self.storage, self.payload)
        resizeDialog.refresh(disks)

        rc = self.run_lightbox_dialog(resizeDialog)
        return rc

    def on_custom_toggled(self, button):
        # The custom button won't be active until after this handler is run,
        # so we have to negate everything here.
        self._reclaim.set_sensitive(not button.get_active())

        if self._reclaim.get_sensitive():
            self._reclaim.set_has_tooltip(False)
        else:
            self._reclaim.set_tooltip_text(_("You'll be able to make space available during custom partitioning."))

    def on_specialized_clicked(self, button):
        # Don't want to run apply or execute in this case, since we have to
        # collect some more disks first.  The user will be back to this spoke.
        self.applyOnSkip = False

        # However, we do want to apply current selections so the disk cart off
        # the filter spoke will display the correct information.
        applyDiskSelection(self.storage, self.data, self.selected_disks)

        self.skipTo = "FilterSpoke"
        NormalSpoke.on_back_clicked(self, button)

    def on_info_bar_clicked(self, *args):
        if self.errors:
            label = _("The following errors were encountered when checking your storage "
                      "configuration.  You can modify your storage layout or quit the "
                      "installer.")

            dialog = DetailedErrorDialog(self.data, buttons=[
                    C_("GUI|Storage|Error Dialog", "_Quit"),
                    C_("GUI|Storage|Error Dialog", "_Modify Storage Layout")],
                label=label)
            with self.main_window.enlightbox(dialog.window):
                errors = "\n".join(self.errors)
                dialog.refresh(errors)
                rc = dialog.run()

            dialog.window.destroy()

            if rc == 0:
                # Quit.
                sys.exit(0)
        elif self.warnings:
            label = _("The following warnings were encountered when checking your storage "
                      "configuration.  These are not fatal, but you may wish to make "
                      "changes to your storage layout.")

            dialog = DetailedErrorDialog(self.data, buttons=[_("_OK")], label=label)
            with self.main_window.enlightbox(dialog.window):
                warnings = "\n".join(self.warnings)
                dialog.refresh(warnings)
                rc = dialog.run()

            dialog.window.destroy()

    def on_disks_key_released(self, box, event):
        # we want to react only on Ctrl-A being pressed
        if not bool(event.state & Gdk.ModifierType.CONTROL_MASK) or \
                (event.keyval not in (Gdk.KEY_a, Gdk.KEY_A)):
            return

        # select disks in the right box
        if box is self.local_disks_box:
            overviews = self.localOverviews
        elif box is self.specialized_disks_box:
            overviews = self.advancedOverviews
        else:
            # no other box contains disk overviews
            return

        for overview in overviews:
            overview.set_chosen(True)

        self._update_disk_list()
