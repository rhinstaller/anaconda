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
#

from gi.repository import Gtk

from pyanaconda.ui.gui import UIObject
from pyanaconda.storage.size import Size

import gettext

_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

__all__ = ["SelectedDisksDialog"]

def size_str(mb):
    if isinstance(mb, Size):
        spec = str(mb)
    else:
        spec = "%s mb" % mb

    return str(Size(spec=spec)).upper()

class SelectedDisksDialog(UIObject):
    builderObjects = ["selected_disks_dialog", "disk_store"]
    mainWidgetName = "selected_disks_dialog"
    uiFile = "spokes/lib/cart.ui"

    def initialize(self, disks, showRemove=True):
        for disk in disks:
            self._store.append([disk.description,
                                size_str(disk.size),
                                size_str(disk.format.free),
                                str(disks.index(disk))])
        self.disks = disks[:]
        self._update_summary()

        if not showRemove:
            self.builder.get_object("remove_button").hide()

    def refresh(self, disks, showRemove=True):
        print "REFRESH selected disks dialog"
        super(SelectedDisksDialog, self).refresh()

        self._view = self.builder.get_object("disk_view")
        self._store = self.builder.get_object("disk_store")
        self._selection = self.builder.get_object("disk_selection")
        self._summary_label = self.builder.get_object("summary_label")

        # clear out the store and repopulate it from the devicetree
        self._store.clear()
        self.initialize(disks, showRemove)

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
        for row in self._store:
            count += 1
            size += Size(spec=row[1])
            free += Size(spec=row[2])

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
            disk = self.disks[idx]
            print "removing %s" % disk.name
            self._store.remove(itr)
            self.disks.remove(disk)
            self._update_summary()

    def on_close_clicked(self, button):
        print "CLOSE CLICKED"

    def on_selection_changed(self, *args):
        print "SELECTION CHANGED"
        model, itr = self._selection.get_selected()
        if itr:
            print "new selection: %s" % model.get_value(itr, 3)
