#
# checklist.py: A class (derived from GtkTreeView) that provides a list of
#               checkbox / text string pairs
#
# Brent Fox <bfox@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2000-2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gobject

class CheckList (gtk.TreeView):
    """A class (derived from gtk.TreeView) that provides a list of
    checkbox / text string pairs"""

    # override this to make your own columns if necessary
    def create_columns(self, columns):
        # add the string columns to the tree view widget
        for i in range(1, columns + 1):
            renderer = gtk.CellRendererText()
            column = gtk.TreeViewColumn('Text', renderer, text=i)
            column.set_clickable(False)
            self.append_column(column)

    # XXX need to handle the multicolumn case better still....
    def __init__ (self, columns = 1, custom_store=None):
	if custom_store is None:
	    self.store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
				       gobject.TYPE_STRING,
				       gobject.TYPE_STRING)
	else:
	    self.store = custom_store
	    
        gtk.TreeView.__init__ (self, self.store)
        
        # XXX we only handle two text columns right now
        if custom_store is None and columns > 2:
            raise RuntimeError, "CheckList supports a maximum of 2 columns"
	
        self.columns = columns
	
        self.checkboxrenderer = gtk.CellRendererToggle()
        column = gtk.TreeViewColumn('', self.checkboxrenderer, active=0)
#        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
#        column.set_fixed_width(40)
        column.set_clickable(True)
        self.checkboxrenderer.connect ("toggled", self.toggled_item)        
        self.append_column(column)

	self.create_columns(columns)

        self.set_rules_hint(False)
        self.set_headers_visible(False)
        self.columns_autosize()
        self.set_enable_search(False)

        # keep track of the number of rows we have so we can
        # iterate over them all
        self.num_rows = 0

    def append_row (self, textList, init_value):
        """Add a row to the list.
        text: text to display in the row
        init_value: initial state of the indicator"""

        iter = self.store.append(None)
        self.store.set_value(iter, 0, init_value)

        # add the text for the number of columns we have
        i = 1
        for text in textList[:self.columns]:
            self.store.set_value(iter, i, textList[i - 1])
            i = i + 1

        self.num_rows = self.num_rows + 1


    def toggled_item(self, data, row):
        """Set a function to be called when the value of a row is toggled.
        The  function will be called with two arguments, the clicked item
        in the row and a string for which row was clicked."""
        
        iter = self.store.get_iter((int(row),))
        val = self.store.get_value(iter, 0)
        self.store.set_value(iter, 0, not val)


    def clear (self):
        "Remove all rows"
        self.store.clear()
        self.num_rows = 0


    def get_active(self, row):
        """Return FALSE or TRUE as to whether or not the row is toggled
        similar to GtkToggleButtons"""

        iter = self.store.get_iter((row,))
        return self.store.get_value(iter, 0)


    def set_active(self, row, is_active):
        "Set row to be is_active, similar to GtkToggleButton"

        iter = self.store.get_iter((row,))
        self.store.set_value(iter, 0, is_active)


    def get_text(self, row, column):
        "Get the text from row and column"

        iter = self.store.get_iter((row,))
        return self.store.get_value(iter, column)


    def set_column_title(self, column, title):
        "Set the title of column to title"

        col = self.get_column(column)
        if col:
            col.set_title(title)


    def set_column_min_width(self, column, min):
        "Set the minimum width of column to min"

        col = self.get_column(column)
        if col:
            col.set_min_width(min)


    def set_column_clickable(self, column, clickable):
        "Set the column to be clickable"

        col = self.get_column(column)
        if col:
            col.set_clickable(clickable)
            

    def set_column_sizing(self, column, sizing):
        "Set the column to use the given sizing method"

        col = self.get_column(column)
        if col:
            col.set_sizing(sizing)

    def set_column_sort_id(self, column, id):
        "Set the sort id of column to id"

        col = self.get_column(column)
        if col:
            col.set_sort_column_id(id)

def main():
    win = gtk.Window()
    cl = CheckList(1)
    for i in range(1, 10):
        cl.append_row("%s" %(i,), False)

    sw = gtk.ScrolledWindow()
    sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    sw.add (cl)
    sw.set_shadow_type(gtk.SHADOW_IN)

    win.add(sw)
    win.set_size_request(250, 250)
    win.show_all()

    gtk.main()

if __name__ == "__main__":
    main()
