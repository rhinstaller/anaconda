# Storage configuration spoke classes
#
# Copyright (C) 2011, 2012  Red Hat, Inc.
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

from gi.repository import Gdk, GLib, Gtk
from gi.repository import AnacondaWidgets
from pyanaconda.ui.gui import GUIObject, communication
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.passphrase import PassphraseDialog
from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
from pyanaconda.ui.gui.spokes.lib.resize import ResizeDialog
from pyanaconda.ui.gui.categories.storage import StorageCategory
from pyanaconda.ui.gui.utils import enlightbox, gtk_call_once, gtk_thread_wait

from pyanaconda.kickstart import doKickstartStorage
from pyanaconda.storage.size import Size
from pyanaconda.storage.errors import StorageError
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.product import productName
from pyanaconda.flags import flags

from pykickstart.constants import *

import gettext
import sys

_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

import logging
log = logging.getLogger("anaconda")

__all__ = ["StorageSpoke"]

class FakeDiskLabel(object):
    def __init__(self, free=0):
        self.free = free

class FakeDisk(object):
    def __init__(self, name, size=0, free=0, partitioned=True, vendor=None,
                 model=None, serial=None, removable=False):
        self.name = name
        self.size = size
        self.format = FakeDiskLabel(free=free)
        self.partitioned = partitioned
        self.vendor = vendor
        self.model = model
        self.serial = serial
        self.removable = removable

    @property
    def description(self):
        return "%s %s" % (self.vendor, self.model)

def getDisks(devicetree, fake=False):
    if not fake:
        devices = devicetree.devices + devicetree._hidden
        disks = [d for d in devices if d.isDisk and
                                       not d.format.hidden and
                                       not (d.protected and
                                            d.removable)]
    else:
        disks = []
        disks.append(FakeDisk("sda", size=300000, free=10000, serial="00001",
                              vendor="Seagate", model="Monster"))
        disks.append(FakeDisk("sdb", size=300000, free=300000, serial="00002",
                              vendor="Seagate", model="Monster"))
        disks.append(FakeDisk("sdc", size=8000, free=2100, removable=True,
                              vendor="SanDisk", model="Cruzer", serial="00003"))

    return disks

def size_str(mb):
    if isinstance(mb, Size):
        spec = str(mb)
    else:
        spec = "%s mb" % mb

    return str(Size(spec=spec)).upper()

class InstallOptions1Dialog(GUIObject):
    builderObjects = ["options1_dialog"]
    mainWidgetName = "options1_dialog"
    uiFile = "spokes/storage.glade"

    RESPONSE_CANCEL = 0
    RESPONSE_CONTINUE = 1
    RESPONSE_MODIFY_SW = 2
    RESPONSE_RECLAIM = 3
    RESPONSE_QUIT = 4

    def __init__(self, *args, **kwargs):
        self.payload = kwargs.pop("payload", None)
        GUIObject.__init__(self, *args, **kwargs)

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    def refresh(self, required_space, disks_size, disk_free, fs_free, autopart,
                autoPartType):
        self.custom = not autopart
        self.custom_checkbutton = self.builder.get_object("options1_custom_check")
        self.custom_checkbutton.set_active(self.custom)

        self.autoPartType = autoPartType
        self.autoPartTypeCombo = self.builder.get_object("options1_combo")
        self.autoPartTypeCombo.set_active(self.autoPartType)

        options_label = self.builder.get_object("options1_label")

        options_text = (_("You have plenty of space to install <b>%s</b>, so "
                          "we can automatically\n"
                          "configure the rest of the installation for you.\n\n"
                          "You're all set!")
                        % productName)
        options_label.set_markup(options_text)

    def _set_free_space_labels(self, disks_size, disk_free, fs_free):
        disks_size_text = size_str(disks_size)
        self.disks_size_label.set_text(disks_size_text)

        disk_free_text = size_str(disk_free)
        self.disk_free_label.set_text(disk_free_text)

        fs_free_text = size_str(fs_free)
        self.fs_free_label.set_text(fs_free_text)

    def _get_sw_needs_text(self, required_space):
        required_space_text = size_str(required_space)
        sw_text = (_("Your current <b>%s</b> software selection requires "
                      "<b>%s</b> of available space.")
                   % (productName, required_space_text))
        return sw_text

    # Methods to handle sensitivity of the modify button.
    def _software_is_ready(self):
        # FIXME:  Would be nicer to just ask the spoke if it's ready.
        return (not threadMgr.get("AnaPayloadThread") and
                not threadMgr.get("AnaSoftwareWatcher") and
                not threadMgr.get("AnaCheckSoftwareThread") and
                self.payload.baseRepo is not None)

    def _check_for_storage_thread(self, button):
        if self._software_is_ready():
            button.set_sensitive(True)
            button.set_has_tooltip(False)
            button.show_all()

            # False means this function should never be called again.
            return False
        else:
            return True

    def _add_button_watcher(self, widgetName):
        # If the payload fetching thread is still running, the user can't go to
        # modify the software selection screen.  Thus, we have to set the button
        # insensitive and wait until software selection is ready to go.
        modify_button = self.builder.get_object(widgetName)
        if not self._software_is_ready():
            modify_button.set_sensitive(False)
            GLib.timeout_add_seconds(1, self._check_for_storage_thread, modify_button)

    # signal handlers
    def on_cancel_clicked(self, button):
        # return to the spoke without making any changes
        print "CANCEL CLICKED"

    def on_quit_clicked(self, button):
        print "QUIT CLICKED"

    def on_modify_sw_clicked(self, button):
        # switch to the software selection hub
        print "MODIFY SOFTWARE CLICKED"

    def on_reclaim_clicked(self, button):
        # show reclaim screen/dialog
        print "RECLAIM CLICKED"

    def on_continue_clicked(self, button):
        print "CONTINUE CLICKED"

    def on_custom_toggled(self, checkbutton):
        self.custom = checkbutton.get_active()

    def on_type_changed(self, combo):
        self.autoPartType = combo.get_active()

class InstallOptions2Dialog(InstallOptions1Dialog):
    builderObjects = ["options2_dialog"]
    mainWidgetName = "options2_dialog"

    def refresh(self, required_space, disks_size, disk_free, fs_free, autopart,
                autoPartType):
        self.custom = not autopart
        self.custom_checkbutton = self.builder.get_object("options2_custom_check")
        self.custom_checkbutton.set_active(self.custom)

        self.autoPartType = autoPartType
        self.autoPartTypeCombo = self.builder.get_object("options2_combo")
        self.autoPartTypeCombo.set_active(self.autoPartType)

        sw_text = self._get_sw_needs_text(required_space)
        label_text = _("%s\nThe disks you've selected have the following "
                       "amounts of free space:") % sw_text
        self.builder.get_object("options2_label1").set_markup(label_text)

        self.disk_free_label = self.builder.get_object("options2_disk_free_label")
        self.fs_free_label = self.builder.get_object("options2_fs_free_label")
        self.disks_size_label = self.builder.get_object("options2_disks_size_label")
        self._set_free_space_labels(disks_size, disk_free, fs_free)

        label_text = (_("<b>You don't have enough space available to install "
                        "%s</b>, but we can help you\n"
                        "reclaim space by shrinking or removing existing partitions.")
                      % productName)
        self.builder.get_object("options2_label2").set_markup(label_text)

        self._add_button_watcher("options2_modify_sw_button")

    def on_custom_toggled(self, checkbutton):
        super(InstallOptions2Dialog, self).on_custom_toggled(checkbutton)
        self.builder.get_object("options2_cancel_button").set_sensitive(not self.custom)
        sensitive = not self.custom and self._software_is_ready()
        self.builder.get_object("options2_modify_sw_button").set_sensitive(sensitive)

class InstallOptions3Dialog(InstallOptions1Dialog):
    builderObjects = ["options3_dialog"]
    mainWidgetName = "options3_dialog"

    def refresh(self, required_space, disks_size, disk_free, fs_free, autopart,
                autoPartType):
        self.custom = not autopart
        sw_text = self._get_sw_needs_text(required_space)
        label_text = (_("%s\nYou don't have enough space available to install "
                        "<b>%s</b>, even if you used all of the free space\n"
                        "available on the selected disks.")
                      % (sw_text, productName))
        self.builder.get_object("options3_label1").set_markup(label_text)

        self.disk_free_label = self.builder.get_object("options3_disk_free_label")
        self.fs_free_label = self.builder.get_object("options3_fs_free_label")
        self.disks_size_label = self.builder.get_object("options3_disks_size_label")
        self._set_free_space_labels(disks_size, disk_free, fs_free)

        label_text = _("<b>You don't have enough space available to install "
                       "%s</b>, even if you used all of the free space\n"
                       "available on the selected disks.  You could add more "
                       "disks for additional space,\n"
                       "modify your software selection to install a smaller "
                       "version of <b>%s</b>, or quit the installer.") % (productName, productName)
        self.builder.get_object("options3_label2").set_markup(label_text)

        self._add_button_watcher("options3_modify_sw_button")

class StorageChecker(object):
    errors = []
    warnings = []
    _mainSpokeClass = "StorageSpoke"

    def run(self):
        communication.send_not_ready(self._mainSpokeClass)
        threadMgr.add(AnacondaThread(name="AnaCheckStorageThread",
                                     target=self.checkStorage))

    def checkStorage(self):
        communication.send_message(self._mainSpokeClass,
                                   _("Checking storage configuration..."))
        (StorageChecker.errors,
         StorageChecker.warnings) = self.storage.sanityCheck()
        communication.send_ready(self._mainSpokeClass, justUpdate=True)
        for e in StorageChecker.errors:
            log.error(e)
        for w in StorageChecker.warnings:
            log.warn(w)

class StorageSpoke(NormalSpoke, StorageChecker):
    builderObjects = ["storageWindow"]
    mainWidgetName = "storageWindow"
    uiFile = "spokes/storage.glade"

    category = StorageCategory

    # other candidates: computer-symbolic, folder-symbolic
    icon = "drive-harddisk-symbolic"
    title = N_("INSTALLATION DESTINATION")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self.applyOnSkip = True

        self._ready = False
        self.selected_disks = self.data.ignoredisk.onlyuse[:]

        # This list gets set up once in initialize and should not be modified
        # except perhaps to add advanced devices. It will remain the full list
        # of disks that can be included in the install.
        self.disks = []

        if not flags.automatedInstall:
            # default to using autopart for interactive installs
            self.data.autopart.autopart = True

        self.autopart = self.data.autopart.autopart
        self.autoPartType = None
        self.clearPartType = CLEARPART_TYPE_NONE

        self._previous_autopart = False

    def _applyDiskSelection(self, use_names):
        onlyuse = use_names[:]
        for disk in [d for d in self.storage.disks if d.name in onlyuse]:
            onlyuse.extend([d.name for d in disk.ancestors
                                        if d.name not in onlyuse])

        self.data.ignoredisk.onlyuse = onlyuse
        self.data.clearpart.drives = use_names[:]

    def apply(self):
        self._applyDiskSelection(self.selected_disks)
        self.data.autopart.autopart = self.autopart
        self.data.autopart.type = self.autoPartType
        self.data.autopart.encrypted = self.encrypted
        self.data.autopart.passphrase = self.passphrase

        self.clearPartType = CLEARPART_TYPE_NONE

        if self.data.bootloader.bootDrive and \
           self.data.bootloader.bootDrive not in self.selected_disks:
            self.data.bootloader.bootDrive = None
            self.storage.bootloader.stage1_disk = None
            self.storage.bootloader.stage1_device = None

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

    def execute(self):
        # Spawn storage execution as a separate thread so there's no big delay
        # going back from this spoke to the hub while StorageChecker.run runs.
        # Yes, this means there's a thread spawning another thread.  Sorry.
        threadMgr.add(AnacondaThread(name="AnaExecuteStorageThread",
                                     target=self._doExecute))

    def _doExecute(self):
        self._ready = False
        communication.send_not_ready(self.__class__.__name__)
        communication.send_message(self.__class__.__name__,
                               _("Saving storage configuration..."))
        try:
            doKickstartStorage(self.storage, self.data, self.instclass)
        except StorageError as e:
            log.error("storage configuration failed: %s" % e)
            StorageChecker.errors = str(e).split("\n")
            communication.send_message(self.__class__.__name__,
                                   _("Failed to save storage configuration..."))
            self.data.ignoredisk.drives = []
            self.data.ignoredisk.onlyuse = []
            self.storage.config.update(self.data)
            self.storage.reset()
            self.disks = getDisks(self.storage.devicetree)
            # now set ksdata back to the user's specified config
            self._applyDiskSelection(self.selected_disks)
        else:
            if self.autopart:
                # this was already run as part of doAutoPartition. dumb.
                StorageChecker.errors = []
                self.run()
        finally:
            self._ready = True
            communication.send_ready(self.__class__.__name__, justUpdate=True)

    @property
    def completed(self):
        return (threadMgr.get("AnaExecuteStorageThread") is None and
                threadMgr.get("AnaCheckStorageThread") is None and
                (self.data.ignoredisk.onlyuse != [] or
                 flags.automatedInstall) and
                self.storage.rootDevice is not None and
                not self.errors)

    @property
    def ready(self):
        # By default, the storage spoke is not ready.  We have to wait until
        # storageInitialize is done.
        return self._ready

    @property
    def status(self):
        """ A short string describing the current status of storage setup. """
        msg = _("No disks selected")
        if self.data.ignoredisk.onlyuse:
            msg = P_(("%d disk selected"),
                     ("%d disks selected"),
                     len(self.data.ignoredisk.onlyuse)) % len(self.data.ignoredisk.onlyuse)

            if self.errors:
                msg = _("Error checking storage configuration")
            elif self.data.autopart.autopart:
                msg = _("Automatic partitioning selected")
            else:
                msg = _("Custom partitioning selected")

        return msg

    def _on_disk_clicked(self, overview, event):
        # This handler only runs for these two kinds of events, and only for
        # activate-type keys (space, enter) in the latter event's case.
        if not event.type in [Gdk.EventType.BUTTON_PRESS, Gdk.EventType.KEY_RELEASE]:
            return

        if event.type == Gdk.EventType.KEY_RELEASE and \
           event.keyval not in [Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter, Gdk.KEY_KP_Space]:
              return

        self._update_disk_list()
        self._update_summary()

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

        encrypt_checkbutton = self.builder.get_object("encryption_checkbutton")
        encrypt_checkbutton.set_active(self.encrypted)

        # update the selections in the ui
        overviews = self.local_disks_box.get_children()
        for overview in overviews:
            name = overview.get_property("popup-info").partition("|")[0].strip()
            overview.set_chosen(name in self.selected_disks)

        self._update_summary()

        if self.errors:
            self.set_warning(_("Error checking storage configuration.  Click for details."))

    def initialize(self):
        from pyanaconda.ui.gui.utils import setViewportBackground

        NormalSpoke.initialize(self)

        label = self.builder.get_object("summary_button").get_children()[0]
        markup = "<span foreground='blue'><u>%s</u></span>" % label.get_text()
        label.set_use_markup(True)
        label.set_markup(markup)

        self.local_disks_box = self.builder.get_object("local_disks_box")
        #specialized_disks_box = self.builder.get_object("specialized_disks_box")

        threadMgr.add(AnacondaThread(name="AnaStorageWatcher", target=self._initialize))

    def _initialize(self):
        communication.send_message(self.__class__.__name__, _("Probing storage..."))

        storageThread = threadMgr.get("AnaStorageThread")
        if storageThread:
            storageThread.join()

        self.disks = getDisks(self.storage.devicetree)

        # if there's only one disk, select it by default
        if len(self.disks) == 1 and not self.selected_disks:
            self._applyDiskSelection([self.disks[0].name])

        # properties: kind, description, capacity, os, popup-info
        for disk in self.disks:
            if disk.removable:
                kind = "drive-removable-media"
            else:
                kind = "drive-harddisk"

            size = size_str(disk.size)
            popup_info = "%s | %s" % (disk.name, disk.serial)

            @gtk_thread_wait
            def gtk_action():
                overview = AnacondaWidgets.DiskOverview(disk.description,
                                                        kind,
                                                        size,
                                                        popup=popup_info)
                self.local_disks_box.pack_start(overview, False, False, 0)

                # FIXME: this will need to get smarter
                #
                # maybe a little function that resolves each item in onlyuse using
                # udev_resolve_devspec and compares that to the DiskDevice?
                overview.set_chosen(disk.name in self.selected_disks)
                overview.connect("button-press-event", self._on_disk_clicked)
                overview.connect("key-release-event", self._on_disk_clicked)
                overview.show_all()

                self._update_summary()

            gtk_action()
                
        self._ready = True
        communication.send_ready(self.__class__.__name__)

    def _update_summary(self):
        """ Update the summary based on the UI. """
        count = 0
        capacity = 0
        free = Size(bytes=0)

        # pass in our disk list so hidden disks' free space is available
        free_space = self.storage.getFreeSpace(disks=self.disks)
        selected = [d for d in self.disks if d.name in self.selected_disks]

        for disk in selected:
            capacity += disk.size
            free += free_space[disk.name][0]
            count += 1

        summary = (P_("%d disk selected; %s capacity; %s free",
                      "%d disks selected; %s capacity; %s free",
                      count) % (count, str(Size(spec="%s MB" % capacity)), free))
        summary_label = self.builder.get_object("summary_label")
        summary_label.set_text(summary)

        if len(self.disks) == 0:
            self.set_warning(_("No disks detected.  Please shut down the computer, connect at least one disk, and restart to complete installation."))
        elif count == 0:
            self.set_warning(_("No disks selected; please select at least one disk to install to."))
        else:
            self.clear_info()

        self.builder.get_object("continue_button").set_sensitive(count > 0)
        self.builder.get_object("summary_label").set_sensitive(count > 0)

    def _update_disk_list(self):
        """ Update self.selected_disks based on the UI. """
        overviews = self.local_disks_box.get_children()
        for overview in overviews:
            name = overview.get_property("popup-info").partition("|")[0].strip()

            selected = overview.get_chosen()
            if selected and name not in self.selected_disks:
                self.selected_disks.append(name)

            if not selected and name in self.selected_disks:
                self.selected_disks.remove(name)

    # signal handlers
    def on_summary_clicked(self, button):
        # show the selected disks dialog
        # pass in our disk list so hidden disks' free space is available
        free_space = self.storage.getFreeSpace(disks=self.disks)
        dialog = SelectedDisksDialog(self.data,)
        dialog.refresh([d for d in self.disks if d.name in self.selected_disks],
                       free_space)
        rc = self.run_lightbox_dialog(dialog)

        # update selected disks since some may have been removed
        self.selected_disks = [d.name for d in dialog.disks]

        # update the UI to reflect changes to self.selected_disks
        overviews = self.local_disks_box.get_children()
        for overview in overviews:
            name = overview.get_property("popup-info").partition("|")[0].strip()

            overview.set_chosen(name in self.selected_disks)

        self._update_summary()

        if self.data.bootloader.location == "none":
            self.set_warning(_("You have chosen to skip bootloader installation.  Your system may not be bootable."))
            self.window.show_all()
        else:
            self.clear_info()

    def run_lightbox_dialog(self, dialog):
        with enlightbox(self.window, dialog.window):
            rc = dialog.run()

        return rc

    def on_continue_clicked(self, button):
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
        disks_size = sum(Size(spec="%f MB" % d.size) for d in disks)

        # Figure out if the existing disk labels will work on this platform
        # you need to have at least one of the platform's labels in order for
        # any of the free space to be useful.
        disk_labels = set([disk.format.labelType for disk in disks \
                                                 if hasattr(disk.format, "labelType")])
        platform_labels = set(self.storage.platform.diskLabelTypes)
        if disk_labels and platform_labels.isdisjoint(disk_labels):
            disk_free = 0
            fs_free = 0
            log.debug("Need disklabel: %s have: %s" % (", ".join(platform_labels),
                                                       ", ".join(disk_labels)))
        else:
            free_space = self.storage.getFreeSpace(disks=disks,
                                                   clearPartType=CLEARPART_TYPE_NONE)
            disk_free = sum([f[0] for f in free_space.itervalues()])
            fs_free = sum([f[1] for f in free_space.itervalues()])

        required_space = self.payload.spaceRequired
        auto_swap = Size(bytes=0)
        for autoreq in self.storage.autoPartitionRequests:
            if autoreq.fstype == "swap":
                auto_swap += Size(spec="%d MB" % autoreq.size)

        log.debug("disk free: %s  fs free: %s  sw needs: %s  auto swap: %s"
                        % (disk_free, fs_free, required_space, auto_swap))
        if disk_free >= required_space + auto_swap:
            dialog = InstallOptions1Dialog(self.data)
        elif disks_size >= required_space:
            dialog = InstallOptions2Dialog(self.data, payload=self.payload)
        else:
            dialog = InstallOptions3Dialog(self.data, payload=self.payload)

        dialog.refresh(required_space, disks_size, disk_free, fs_free, self.autopart, self.autoPartType)
        rc = self.run_lightbox_dialog(dialog)
        if rc == dialog.RESPONSE_CONTINUE:
            # depending on custom/autopart, either set up autopart or show
            # custom partitioning ui
            self.autopart = not dialog.custom
            self.autoPartType = dialog.autoPartType

            # even if they're not doing autopart, setting autopart.encrypted
            # establishes a default of encrypting new devices
            encrypt_button = self.builder.get_object("encryption_checkbutton")
            self.encrypted = encrypt_button.get_active()

            if dialog.custom:
                self.skipTo = "CustomPartitioningSpoke"
            elif self.encrypted:
                dialog = PassphraseDialog(self.data)
                rc = self.run_lightbox_dialog(dialog)
                if rc == 0:
                    return

                self.passphrase = dialog.passphrase

            gtk_call_once(self.window.emit, "button-clicked")
        elif rc == dialog.RESPONSE_CANCEL:
            # stay on this spoke
            print "user chose to continue disk selection"
        elif rc == dialog.RESPONSE_MODIFY_SW:
            # go to software spoke
            self.skipTo = "SoftwareSelectionSpoke"
            gtk_call_once(self.window.emit, "button-clicked")
        elif rc == dialog.RESPONSE_RECLAIM:
            self.autopart = not dialog.custom
            self.autoPartType = dialog.autoPartType

            # even if they're not doing autopart, setting autopart.encrypted
            # establishes a default of encrypting new devices
            encrypt_button = self.builder.get_object("encryption_checkbutton")
            self.encrypted = encrypt_button.get_active()

            if dialog.custom:
                self.skipTo = "CustomPartitioningSpoke"
                gtk_call_once(self.window.emit, "button-clicked")
            else:
                if self.encrypted:
                    dialog = PassphraseDialog(self.data)
                    rc = self.run_lightbox_dialog(dialog)
                    if rc == 0:
                        return

                    self.passphrase = dialog.passphrase

                self.apply()
                gtk_call_once(self._show_resize_dialog, disks)
        elif rc == dialog.RESPONSE_QUIT:
            raise SystemExit("user-selected exit")

    def _show_resize_dialog(self, disks):
        resizeDialog = ResizeDialog(self.data, self.storage, self.payload)
        resizeDialog.refresh(disks)

        # resizeDialog handles okay/cancel on its own, so we can throw out the
        # return value.
        self.run_lightbox_dialog(resizeDialog)
        gtk_call_once(self.window.emit, "button-clicked")

    def on_add_disk_clicked(self, button):
        print "ADD DISK CLICKED"

    def on_info_bar_clicked(self, *args):
        if not self.errors:
            return

        label = _("The following errors were encountered when checking your storage "
                  "configuration.  You can modify your storage layout\nor quit the "
                  "installer.")
        dialog = DetailedErrorDialog(self.data, buttons=[_("_Quit"), _("_Modify Storage Layout")], label=label)
        with enlightbox(self.window, dialog.window):
            errors = "\n".join(self.errors)
            dialog.refresh(errors)
            rc = dialog.run()

        dialog.window.destroy()

        if rc == 0:
            # Quit.
            sys.exit(0)
        elif rc == 1:
            # Close the dialog so the user can change selections.
            pass
