#
# datacombo.py: A class (derived from GtkComboBox) that provides
#               the ability to store data and show text in a GtkComboBox easily
#
# Copyright (C) 2004  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import gtk
import gobject

class DataComboBox(gtk.ComboBox):
    """A class derived from gtk.ComboBox to allow setting a user visible
    string and (not-visible) data string"""

    def __init__(self, store = None):
        if store is None:
            self.store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        else:
            self.store = store
        gtk.ComboBox.__init__(self, self.store)

        cell = gtk.CellRendererText()
        self.pack_start(cell, True)
        self.set_attributes(cell, text = 0)

    def append(self, text, data):
        iter = self.store.append(None)
        self.store[iter] = (text, data)

    def get_active_value(self, col = 1):
        row = self.get_active()
        return self.get_stored_data(row, col)

    def get_stored_data(self, row, col = 1):
        if row < 0:
            return None
        iter = self.store.get_iter(row)
        val = self.store.get_value(iter, col)
        return val

    def get_text(self, row):
        return self.get_stored_data(row, col = 0)

    def set_active_text(self, t):
        """set_active_text(string) ->  Sets the active row to whereever t is.
           returns True if set_active is run, False otherwise.
        """
        retval = False
        n = 0
        i = self.store.get_iter(n)
        while i is not None:
            if self.store.get_value(i, 0) == t:
                self.set_active(n)
                retval = True
                break
            i = self.store.iter_next(i)
            n += 1

        return retval

    def clear(self):
        self.store.clear()

if __name__ == "__main__":
    def mycb(widget, *args):
        idx = widget.get_active()
        print(idx, widget.get_stored_data(idx), widget.get_text(idx))
        
    win = gtk.Window()

    cb = DataComboBox()
    cb.append("/dev/hda5", "hda5")
    cb.append("/dev/hda6", "hda6")
    cb.append("/dev/hda7", "hda7")
    cb.append("/dev/hda8", "hda8")
    cb.set_active_text("/dev/hda7")

    cb.connect('changed', mycb)
    
    win.add(cb)
    win.show_all()

    gtk.main()

