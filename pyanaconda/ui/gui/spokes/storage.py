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

from gi.repository import Gtk
from gi.repository import AnacondaWidgets

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.storage import StorageCategory

from pyanaconda.storage.size import Size
from pyanaconda.product import productName

import gettext

_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

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
        disks = [d for d in devicetree.devices if d.isDisk and
                                                  not d.format.hidden and
                                                  d.partitioned]
    else:
        disks = []
        disks.append(FakeDisk("sda", size=300000, free=10000, serial="00001",
                              vendor="Seagate", model="Monster"))
        disks.append(FakeDisk("sdb", size=300000, free=300000, serial="00002",
                              vendor="Seagate", model="Monster"))
        disks.append(FakeDisk("sdc", size=8000, free=2100, removable=True,
                              vendor="SanDisk", model="Cruzer", serial="00003"))

    return disks

def get_free_space_info(disks, devicetree):
    disk_free = 0
    fs_free = 0
    for disk in disks:
        if not disk.partitioned:
            continue

        disk_free += disk.format.free

        for partition in devicetree.getChildren(disk):
            # only check actual filesystems since lvm &c require a bunch of
            # operations to translate free filesystem space into free disk space
            if hasattr(partition.format, "free"):
                fs_free += partition.format.free

    print("disks %s have %d free, plus %s in filesystems"
          % ([d.name for d in disks], disk_free, fs_free))
    return (disk_free, fs_free)

def size_str(mb):
    return str(Size(spec="%s mb" % mb)).upper()

class SelectedDisksDialog(UIObject):
    builderObjects = ["selected_disks_dialog", "disk_store"]
    mainWidgetName = "selected_disks_dialog"
    uiFile = "spokes/storage.ui"

    def populate(self, disks):
        for disk in disks:
            if disk.name not in self.data.ignoredisk.onlyuse:
                continue

            self._store.append([disk.description,
                                size_str(disk.size),
                                size_str(disk.format.free),
                                str(disks.index(disk))])
        self.disks = disks[:]
        self._update_summary()

    def setup(self, disks):
        print "SETUP selected disks dialog"
        super(SelectedDisksDialog, self).setup()

        self._view = self.builder.get_object("disk_view")
        self._store = self.builder.get_object("disk_store")
        self._selection = self.builder.get_object("disk_selection")
        self._summary_label = self.builder.get_object("summary_label")

        # clear out the store and repopulate it from the devicetree
        self._store.clear()
        self.populate(disks)

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    def _get_selection_refs(self):
        selected_refs = []
        if self._selection.count_selected_rows():
            model, selected_paths = self._selection.get_selected_rows()
            selected_refs = [Gtk.TreeRowReference() for p in selected_paths]

        return selected_refs

    def _update_summary(self):
        count = 0
        size = 0
        free = 0
        itr = self._store.get_iter_first()
        while itr:
            count += 1
            size += Size(spec=self._store.get_value(itr, 1))
            free += Size(spec=self._store.get_value(itr, 2))
            itr = self._store.iter_next(itr)

        size = str(Size(bytes=long(size))).upper()
        free = str(Size(bytes=long(free))).upper()

        text = P_(("<b>%d disk; %s capacity; %s free space</b> "
                   "(unpartitioned and in filesystems)"),
                  ("<b>%d disks; %s capacity; %s free space</b> "
                   "(unpartitioned and in filesystems)"),
                  count) % (count, size, free)
        self._summary_label.set_markup(text)

    # signal handlers
    def on_remove_clicked(self, button):
        print "REMOVE CLICKED"#: %s" % self._selection.get_selected().get_value(3)
        # remove the selected disk(s) from the list and update the summary label
        #selected_refs = self._get_selection_refs()
        #for ref in selected_refs:
        #    path = ref.get_path()
        #    itr = model.get_iter_from_string(path)
        #    self._store.remove(itr)
        model, itr = self._selection.get_selected()
        if itr:
            idx = int(model.get_value(itr, 3))
            name = self.disks[idx].name
            print "removing %s" % name
            self._store.remove(itr)
            self.data.ignoredisk.onlyuse.remove(name)
            self._update_summary()

    def on_close_clicked(self, button):
        print "CLOSE CLICKED"

    def on_selection_changed(self, *args):
        print "SELECTION CHANGED"
        model, itr = self._selection.get_selected()
        if itr:
            print "new selection: %s" % model.get_value(itr, 3)


class InstallOptions1Dialog(UIObject):
    builderObjects = ["options1_dialog"]
    mainWidgetName = "options1_dialog"
    uiFile = "spokes/storage.ui"

    RESPONSE_CANCEL = 0
    RESPONSE_CONTINUE = 1
    RESPONSE_MODIFY_SW = 2
    RESPONSE_RECLAIM = 3
    RESPONSE_QUIT = 4

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    def setup(self, required_space, disk_free, fs_free):
        custom = not self.data.autopart.autopart
        self.custom_checkbutton = self.builder.get_object("options1_custom_check")
        self.custom_checkbutton.set_active(custom)

        options_label = self.builder.get_object("options1_label")

        options_text = (_("You have plenty of space to install <b>%s</b>, so "
                          "we can automatically\n"
                          "configure the rest of the installation for you.\n\n"
                          "You're all set!")
                        % productName)
        options_label.set_markup(options_text)

    def _set_free_space_labels(self, disk_free, fs_free):
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

    @property
    def customize_state(self):
        if hasattr(self, "custom_checkbutton"):
            return self.custom_checkbutton.get_active()

        return False

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
        # TODO: handle custom checkbutton
        print "CONTINUE CLICKED"

class InstallOptions2Dialog(InstallOptions1Dialog):
    builderObjects = ["options2_dialog"]
    mainWidgetName = "options2_dialog"

    def setup(self, required_space, disk_free, fs_free):
        custom = not self.data.autopart.autopart
        self.custom_checkbutton = self.builder.get_object("options2_custom_check")
        self.custom_checkbutton.set_active(custom)

        sw_text = self._get_sw_needs_text(required_space)
        label_text = _("%s\nThe disks you've selected have the following "
                       "amounts of free space:") % sw_text
        self.builder.get_object("options2_label1").set_markup(label_text)

        self.disk_free_label = self.builder.get_object("options2_disk_free_label")
        self.fs_free_label = self.builder.get_object("options2_fs_free_label")
        self._set_free_space_labels(disk_free, fs_free)

        label_text = (_("<b>You don't have enough space available to install "
                        "%s</b>, but we can help you\n"
                        "reclaim space by shrinking or removing existing partitions.")
                      % productName)
        self.builder.get_object("options2_label2").set_markup(label_text)

    def on_custom_toggled(self, checkbutton):
        custom = checkbutton.get_active()
        self.builder.get_object("options2_cancel_button").set_sensitive(not custom)
        self.builder.get_object("options2_modify_sw_button").set_sensitive(not custom)

class InstallOptions3Dialog(InstallOptions1Dialog):
    builderObjects = ["options3_dialog"]
    mainWidgetName = "options3_dialog"

    def setup(self, required_space, disk_free, fs_free):
        sw_text = self._get_sw_needs_text(required_space)
        label_text = (_("%s\nYou don't have enough space available to install "
                        "<b>%s</b>, even if you used all of the free space\n"
                        "available on the selected disks.")
                      % (sw_text, productName))
        self.builder.get_object("options3_label1").set_markup(label_text)

        self.disk_free_label = self.builder.get_object("options3_disk_free_label")
        self.fs_free_label = self.builder.get_object("options3_fs_free_label")
        self._set_free_space_labels(disk_free, fs_free)

        label_text = _("<b>You don't have enough space available to install "
                       "%s</b>, even if you used all of the free space\n"
                       "available on the selected disks.  You could add more "
                       "disks for additional space,\n"
                       "modify your software selection to install a smaller "
                       "version of <b>%s</b>, or quit the installer.") % (productName, productName)
        self.builder.get_object("options3_label2").set_markup(label_text)

class StorageSpoke(NormalSpoke):
    builderObjects = ["storageWindow"]
    mainWidgetName = "storageWindow"
    uiFile = "spokes/storage.ui"

    category = StorageCategory

    # other candidates: computer-symbolic, folder-symbolic
    icon = "drive-harddisk-symbolic"
    title = N_("STORAGE CONFIGURATION")

    def apply(self):
        pass

    @property
    def completed(self):
        return False

    @property
    def status(self):
        """ A short string describing the current status of storage setup. """
        msg = _("No disks selected")
        if self.data.ignoredisk.onlyuse:
            msg = _("%d disks selected") % len(self.data.ignoredisk.onlyuse)

            if self.data.autopart.autopart:
                msg = _("Automatic partitioning selected")

                # if we had a storage instance we could check for a defined root

        return msg

    def _on_disk_clicked(self, overview, *args):
        print "DISK CLICKED: %s" % overview.get_property("popup-info").partition("|")[0].strip()

        self._update_disk_list()
        self._update_summary()

    def populate(self):
        NormalSpoke.populate(self)

        local_disks_box = self.builder.get_object("local_disks_box")
        #specialized_disks_box = self.builder.get_object("specialized_disks_box")

        print self.data.ignoredisk.onlyuse
        self.disks = getDisks(self.devicetree)

        # properties: kind, description, capacity, os, popup-info
        for disk in self.disks:
            if disk.removable:
                kind = "drive-removable-media"
            else:
                kind = "drive-harddisk"

            size = size_str(disk.size)
            popup_info = "%s | %s" % (disk.name, disk.serial)
            overview = AnacondaWidgets.DiskOverview(disk.description,
                                                    kind,
                                                    size,
                                                    popup=popup_info)
            local_disks_box.pack_start(overview, False, False, 0)

            # FIXME: this will need to get smarter
            #
            # maybe a little function that resolves each item in onlyuse using
            # udev_resolve_devspec and compares that to the DiskDevice?
            overview.set_selected(disk.name in self.data.ignoredisk.onlyuse)
            overview.connect("button-press-event", self._on_disk_clicked)

        self._update_summary()

    def setup(self):
        # XXX this is called every time we switch to this spoke
        NormalSpoke.setup(self)

    def _update_summary(self):
        """ Update the summary based on the UI. """
        print "UPDATING SUMMARY"
        count = 0
        capacity = 0
        free = 0

        overviews = self.builder.get_object("local_disks_box").get_children()
        for overview in overviews:
            name = overview.get_property("popup-info").partition("|")[0].strip()
            selected = overview.get_selected()
            if selected:
                disk = None
                for _disk in self.disks:
                    if _disk.name == name:
                        disk = _disk
                        break

                capacity += disk.size
                free += disk.format.free
                count += 1

        summary = (P_(("%d disk selected; %s capacity; %s free ..."),
                      ("%d disks selected; %s capacity; %s free ..."),
                      count) % (count, size_str(capacity), size_str(free)))
        self.builder.get_object("summary_button").set_label(summary)

        if count == 0:
            self.window.set_info(Gtk.MessageType.WARNING, _("No disks selected; please select at least one disk to install to."))
        else:
            self.window.clear_info()

        self.builder.get_object("summary_button").set_sensitive(count > 0)

    def _update_disk_list(self):
        """ Update ignoredisk.onlyuse based on the UI. """
        print "UPDATING DISK LIST"
        overviews = self.builder.get_object("local_disks_box").get_children()
        for overview in overviews:
            name = overview.get_property("popup-info").partition("|")[0].strip()

            selected = overview.get_selected()
            if selected and name not in self.data.ignoredisk.onlyuse:
                self.data.ignoredisk.onlyuse.append(name)

            if not selected and name in self.data.ignoredisk.onlyuse:
                self.data.ignoredisk.onlyuse.remove(name)

    # signal handlers
    def on_summary_clicked(self, button):
        # show the selected disks dialog
        dialog = SelectedDisksDialog(self.data)
        dialog.setup(self.disks)
        rc = self.run_lightbox_dialog(dialog)

        # update the UI to reflect changes to self.data.ignoredisk.onlyuse
        overviews = self.builder.get_object("local_disks_box").get_children()
        for overview in overviews:
            name = overview.get_property("popup-info").partition("|")[0].strip()

            overview.set_selected(name in self.data.ignoredisk.onlyuse)
        self._update_summary()

    def run_lightbox_dialog(self, dialog):
        lightbox = AnacondaWidgets.lb_show_over(self.window)
        dialog.window.set_transient_for(lightbox)
        rc = dialog.run()
        lightbox.destroy()
        return rc

    def on_continue_clicked(self, button):
        # show the installation options dialog
        disks = [d for d in self.disks if d.name in self.data.ignoredisk.onlyuse]
        (disk_free, fs_free) = get_free_space_info(disks, self.devicetree)
        required_space = 12000      # TODO: find out where to get this
        if disk_free >= required_space:
            dialog = InstallOptions1Dialog(self.data)
        elif sum([d.size for d in disks]) >= required_space:
            dialog = InstallOptions2Dialog(self.data)
        else:
            dialog = InstallOptions3Dialog(self.data)

        dialog.setup(required_space, disk_free, fs_free)
        rc = self.run_lightbox_dialog(dialog)
        if rc == dialog.RESPONSE_CONTINUE:
            # depending on custom/autopart, either set up autopart or show
            # custom partitioning ui
            print "user chose to continue to partitioning (custom is %s)" % dialog.customize_state
            Gtk.main_quit()
        elif rc == dialog.RESPONSE_CANCEL:
            # stay on this spoke
            print "user chose to continue disk selection"
            pass
        elif rc == dialog.RESPONSE_MODIFY_SW:
            # go to software spoke
            print "user chose to modify software selection"
            Gtk.main_quit()
            pass
        elif rc == dialog.RESPONSE_RECLAIM:
            # go to tug-of-war
            print "user chose to reclaim space"
            Gtk.main_quit()
            pass
        elif rc == dialog.RESPONSE_QUIT:
            raise SystemExit("user-selected exit")

    def on_add_disk_clicked(self, button):
        print "ADD DISK CLICKED"

    def on_back_clicked(self, window):
        self.window.hide()
        Gtk.main_quit()
