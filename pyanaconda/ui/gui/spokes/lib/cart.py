# Disk shopping cart
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
#                    Chris Lumens <clumens@redhat.com>
#

from gi.repository import Gtk

from pyanaconda.i18n import C_, P_
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import escape_markup
from blivet.size import Size

__all__ = ["SelectedDisksDialog"]

IS_BOOT_COL = 0
DESCRIPTION_COL = 1
SIZE_COL = 2
FREE_SPACE_COL = 3
NAME_COL = 4
ID_COL = 5

class SelectedDisksDialog(GUIObject):
    builderObjects = ["selected_disks_dialog", "disk_store", "disk_tree_view"]
    mainWidgetName = "selected_disks_dialog"
    uiFile = "spokes/lib/cart.glade"

    def __init__(self, data):
        GUIObject.__init__(self, data)

        self._view = self.builder.get_object("disk_tree_view")
        self._store = self.builder.get_object("disk_store")
        self._selection = self.builder.get_object("disk_selection")
        self._summary_label = self.builder.get_object("summary_label")

        self._set_button = self.builder.get_object("set_as_boot_button")
        self._remove_button = self.builder.get_object("remove_button")

    # pylint: disable=arguments-differ
    def initialize(self, disks, free, showRemove=True, setBoot=True):
        self._previousID = None

        for disk in disks:
            self._store.append([False,
                                "%s (%s)" % (disk.description, disk.serial),
                                str(disk.size),
                                str(free[disk.name][0]),
                                disk.name,
                                disk.id])
        self.disks = disks[:]
        self._update_summary()

        if not showRemove:
            self.builder.get_object("remove_button").hide()

        if not setBoot:
            self._set_button.hide()

        if not disks:
            return

        # Don't select a boot device if no boot device is asked for.
        if self.data.bootloader.location == "none":
            return

        # Set up the default boot device.  Use what's in the ksdata if anything,
        # then fall back to the first device.
        default_id = None
        if self.data.bootloader.bootDrive:
            for d in self.disks:
                if d.name == self.data.bootloader.bootDrive:
                    default_id = d.id

        if not default_id:
            default_id = self.disks[0].id

        # And then select it in the UI.
        for row in self._store:
            if row[ID_COL] == default_id:
                self._previousID = row[ID_COL]
                row[IS_BOOT_COL] = True
                break

    # pylint: disable=arguments-differ
    def refresh(self, disks, free, showRemove=True, setBoot=True):
        super(SelectedDisksDialog, self).refresh()

        # clear out the store and repopulate it from the devicetree
        self._store.clear()
        self.initialize(disks, free, showRemove=showRemove, setBoot=setBoot)

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    def _get_selection_refs(self):
        selected_refs = []
        if self._selection.count_selected_rows():
            selected_paths = self._selection.get_selected_rows()[1]
            selected_refs = [Gtk.TreeRowReference() for _p in selected_paths]

        return selected_refs

    def _update_summary(self):
        count = 0
        size = Size(0)
        free = Size(0)
        for row in self._store:
            count += 1
            size += Size(row[SIZE_COL])
            free += Size(row[FREE_SPACE_COL])

        # pylint: disable=unescaped-markup
        text = P_("<b>%(count)d disk; %(size)s capacity; %(free)s free space</b> "
                   "(unpartitioned and in file systems)",
                  "<b>%(count)d disks; %(size)s capacity; %(free)s free space</b> "
                   "(unpartitioned and in file systems)",
                   count) % {"count" : count,
                             "size" : escape_markup(size),
                             "free" : escape_markup(free)}
        self._summary_label.set_markup(text)

    # signal handlers
    def on_remove_clicked(self, button):
        itr = self._selection.get_selected()[1]
        if not itr:
            return

        disk = None
        for d in self.disks:
            if d.id == self._store[itr][ID_COL]:
                disk = d
                break

        if not disk:
            return

        # If this disk was marked as the boot device, just change to the first one
        # instead.
        resetBootDevice = self._store[itr][IS_BOOT_COL]

        # remove the selected disk(s) from the list and update the summary label
        self._store.remove(itr)
        self.disks.remove(disk)

        if resetBootDevice and len(self._store) > 0:
            self._store[0][IS_BOOT_COL] = True

        self._update_summary()

        # If no disks are available in the cart anymore, grey out the buttons.
        self._set_button.set_sensitive(len(self._store) > 0)
        self._remove_button.set_sensitive(len(self._store) > 0)

    def on_close_clicked(self, button):
        # Save the boot device setting, if something was selected.
        for row in self._store:
            if row[IS_BOOT_COL]:
                for disk in self.disks:
                    if disk.id == row[ID_COL]:
                        self.data.bootloader.bootDrive = disk.name
                        self.data.bootloader.location = "mbr"
                        return

        # No device was selected.  The user does not want to install
        # a bootloader.
        self.data.bootloader.bootDrive = ""
        self.data.bootloader.location = "none"

    def _toggle_button_text(self, row):
        if row[IS_BOOT_COL]:
            self._set_button.set_label(C_("GUI|Selected Disks Dialog",
                "_Do not install boot loader"))
        else:
            self._set_button.set_label(C_("GUI|Selected Disks Dialog",
                "_Set as Boot Device"))

    def on_selection_changed(self, *args):
        itr = self._selection.get_selected()[1]
        if not itr:
            return

        self._toggle_button_text(self._store[itr])

    def on_set_as_boot_clicked(self, button):
        itr = self._selection.get_selected()[1]
        if not itr:
            return

        # There's only two cases:
        if self._store[itr][ID_COL] == self._previousID:
            # Either the user clicked on the device they'd previously selected,
            # in which case we are just toggling here.
            self._store[itr][IS_BOOT_COL] = not self._store[itr][IS_BOOT_COL]
        else:
            # Or they clicked on a different device.  First we unselect the
            # previously selected device.
            for row in self._store:
                if row[ID_COL] == self._previousID:
                    row[IS_BOOT_COL] = False
                    break

            # Then we select the new row.
            self._store[itr][IS_BOOT_COL] = True
            self._previousID = self._store[itr][ID_COL]

        self._toggle_button_text(self._store[itr])
