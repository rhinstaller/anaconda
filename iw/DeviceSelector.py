#
# Filtering UI for the simple path through the storage code.
#
# Copyright (C) 2009  Red Hat, Inc.
# All rights reserved.
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

import gtk, gobject
import gtk.glade
import gui

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

# The column that holds a python object containing information about the
# device in each row.  This value really shouldn't be overridden.
OBJECT_COL = 0

# These columns can be overridden with the active= and visible= parameters to
# __init__.  active indicates which column tracks whether the row is checked
# by default, and visible indicates which column tracks whether the row is
# seen or not.
VISIBLE_COL = 1
ACTIVE_COL = 2

# This should not be overridden.  It controls whether or not a row may be
# deselected.  Rows with this column set will stay in selected or not
# (whichever they were initialized to) permanently.
IMMUTABLE_COL = 3

class DeviceDisplayer(object):
    def _column_toggled(self, menuItem, col):
        # This is called when a selection is made in the column visibility drop
        # down menu, and obviously makes a column visible (or not).
        col.set_visible(not col.get_visible())

    def __init__(self, store, model, view, active=ACTIVE_COL, visible=VISIBLE_COL):
        self.store = store
        self.model = model
        self.view = view

        self.menu = None

        self.active = active
        self.visible = visible

    def addColumn(self, title, num, displayed=True):
        cell = gtk.CellRendererText()
        cell.set_property("yalign", 0)

        col = gtk.TreeViewColumn(title, cell, text=num, active=self.active)
        col.set_visible(displayed)
        col.set_expand(True)
        col.set_resizable(True)
        self.view.append_column(col)

        # This needs to be set on all columns or it will be impossible to sort
        # by that column.
        col.set_sort_column_id(num)

        if self.menu:
            # Add a new entry to the drop-down menu.
            item = gtk.CheckMenuItem(title)
            item.set_active(displayed)
            item.connect("toggled", self._column_toggled, col)
            item.show()
            self.menu.append(item)

    def createMenu(self):
        self.menu = gtk.Menu()

        # Add a blank column at the (current) end of the view.  This column
        # exists only so we can have a header to click on and display the
        # drop down allowing column configuration.
        menuCol = gtk.TreeViewColumn("")
        menuCol.set_clickable(True)
        menuCol.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        menuCol.set_fixed_width(30)
        menuCol.connect("clicked", lambda col, menu: menu.popup(None, None, None, 0, 0),
                        self.menu)

        image = gui.readImageFromFile("filter-menu.png")
        image.show_all()
        menuCol.set_widget(image)

        # Make sure the menu column gets added after all other columns so it
        # will be on the far right edge.
        self.view.connect("show", lambda x: self.view.append_column(menuCol))

    def getStoreIter(self, row, model=None):
        """Get an iter on the underlying store that maps to a row on the
           provided model.  If model is None, use the default.
        """
        if not model:
            model = self.model

        iter = model.get_iter(row)
        if not iter:
            return None

        while not self.store.iter_is_valid(iter):
            if isinstance(model, gtk.TreeModelFilter):
                iter = model.convert_iter_to_child_iter(iter)
            elif isinstance(model, gtk.TreeModelSort):
                iter = model.convert_iter_to_child_iter(None, iter)

            model = model.get_model()

        return iter

    def getSelected(self):
        """Return a list of all the items currently checked in the UI, or
           an empty list if nothing is selected.
        """
        return filter(lambda row: row[self.active], self.store)

    def getNVisible(self):
        """Return the number of items currently visible in the UI."""
        return len(filter(lambda row: row[self.visible], self.store))

class DeviceSelector(DeviceDisplayer):
    def createSelectionCol(self, title="", radioButton=False, toggledCB=None,
                           membershipCB=None):
        # Add a column full of checkboxes/radiobuttons in the first column of the view.
        crt = gtk.CellRendererToggle()
        crt.set_property("activatable", True)
        crt.set_property("yalign", 0)
        crt.set_radio(radioButton)

        crt.connect("toggled", self._device_toggled, toggledCB, radioButton)

        col = gtk.TreeViewColumn(title, crt, active=self.active)
        col.set_alignment(0.75)

        if not radioButton:
            self.allButton = gtk.ToggleButton()
            col.connect("clicked", lambda *args: self.allButton.set_active(not self.allButton.get_active()))

            col.set_widget(self.allButton)
            self.allButton.show_all()

            self.allButton.connect("toggled", self._all_clicked, toggledCB, membershipCB)

        self.view.append_column(col)
        self.view.set_headers_clickable(True)
        self.view.connect("row-activated", self._row_activated, toggledCB, radioButton)

    def _all_clicked(self, button, toggledCB=None, membershipCB=None):
        # This is called when the Add/Remove all button is checked and does
        # the obvious.
        def _toggle_all(model, path, iter, set):
            # Don't check the boxes of rows that aren't visible or aren't part
            # of the currently displayed page.  We'd like the all button to
            # only operate on the current page, after all.
            if not model[path][self.visible] or model[path][IMMUTABLE_COL] or \
                (membershipCB and not membershipCB(model[path][OBJECT_COL])):
                return

            # Don't try to set a row to active if it's already been checked.
            # This prevents devices that have been checked before the all
            # button was checked from getting double counted.
            if model[path][self.active] == set:
                return

            model[path][self.active] = set

            if toggledCB:
                toggledCB(set, model[path][OBJECT_COL])

        set = button.get_active()
        self.store.foreach(_toggle_all, set)

    def _row_activated(self, view, row, col, cb, isRadio):
        # This is called when a row is double-clicked, or selected via space or
        # enter.  We just want to do the same as if the checkbox were clicked.
        self._device_toggled(None, row, cb, isRadio)

    def _device_toggled(self, button, row, cb, isRadio):
        # This is called when the checkbox for a device is clicked or unclicked.
        iter = self.getStoreIter(row)
        if not iter:
            return

        storeRow = self.store.get_path(iter)
        if self.store[storeRow][IMMUTABLE_COL]:
            return

        if isRadio:
            # This is lame, but there's no other way to do it.  First we have
            # to uncheck everything in the store, then we check the one that
            # was clicked on.
            for r in self.store:
                r[self.active] = False

            self.store[storeRow][self.active] = True

            if cb:
                cb(True, self.store[storeRow][OBJECT_COL])
        else:
            is_checked = self.store[storeRow][self.active]
            self.store[storeRow][self.active] = not is_checked

            if cb:
                cb(not is_checked, self.store[storeRow][OBJECT_COL])
