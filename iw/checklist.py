from gtk import *
import GTK

class CheckList (GtkCList):
    """A class (derived from GtkCList) that provides a list of
    checkbox / text string pairs"""
    CHECK_SIZE = 13

    def __init__ (self, columns = 1):
        GtkCList.__init__ (self, columns+1)

        self.set_column_auto_resize(0, 1)
        #for i in range(columns):
        #    self.set_column_auto_resize (i, 1)

        def debug_cb (widget):
            print widget
            
        self.connect ("realize", self._realize_cb)
#        self.connect ("button_press_event", self._button_press_cb)
#        self.connect ("key_press_event", self._key_press_cb)

        self.off_pixmap = None
        self.on_pixmap = None

        self.toggled_func = None

        self.n_rows = 0

    def append_row (self, textList, init_value, row_data=None):
        """Add a row to the list.
        text: text to display in the row
        init_value: initial state of the indicator
        row_data: data to pass to the toggled_func callback"""

        textList = ("",) + textList
        row = self.append (textList)
        self.set_row_data (row, (not not init_value, row_data, ""))
        self.n_rows = self.n_rows + 1

        if (self.flags() & GTK.REALIZED):
            self._update_row (row)

        return row

    def clear (self):
        "Remove all rows"
        GtkCList.clear(self)
        self.n_rows = 0

    def set_toggled_func (self, func):
        """Set a function to be called when the value of a row is toggled.
        The  function will be called with two arguments, the new state
        of the indicator (boolean) and the row_data for the row."""
        self.toggled_func = func
        
    def _update_row (self, row):
        (val, row_data, name) = self.get_row_data(row)
        if val:
            self.set_pixmap(row,0,self.on_pixmap,self.mask)
        else:
            self.set_pixmap(row,0,self.off_pixmap,self.mask)


    def _color_pixmaps(self):
        style = self.get_style()
        base_gc = self.on_pixmap.new_gc(foreground = style.base[GTK.STATE_NORMAL])
        text_gc = self.on_pixmap.new_gc(foreground = style.text[GTK.STATE_NORMAL])
        
        self.mask = create_pixmap(None,CheckList.CHECK_SIZE,CheckList.CHECK_SIZE,1)
        # HACK - we really want to just use a color with a pixel value of 1
        mask_gc = self.mask.new_gc (foreground = self.get_style().white)
        draw_rectangle(self.mask,mask_gc,1,0,0,CheckList.CHECK_SIZE,CheckList.CHECK_SIZE)

        draw_rectangle(self.on_pixmap,base_gc,1,0,0,CheckList.CHECK_SIZE,CheckList.CHECK_SIZE)
        draw_rectangle(self.on_pixmap,text_gc,0,0,0,CheckList.CHECK_SIZE-1,CheckList.CHECK_SIZE-1)

        draw_line(self.on_pixmap,text_gc,2, CheckList.CHECK_SIZE/2,CheckList.CHECK_SIZE/3,CheckList.CHECK_SIZE-5)
        draw_line(self.on_pixmap,text_gc,2, CheckList.CHECK_SIZE/2+1,CheckList.CHECK_SIZE/3,CheckList.CHECK_SIZE-4)
        
        draw_line(self.on_pixmap,text_gc,CheckList.CHECK_SIZE/3, CheckList.CHECK_SIZE-5, CheckList.CHECK_SIZE-3, 3)
        draw_line(self.on_pixmap,text_gc,CheckList.CHECK_SIZE/3, CheckList.CHECK_SIZE-4, CheckList.CHECK_SIZE-3, 2)

        draw_rectangle(self.off_pixmap,base_gc,1,0,0,CheckList.CHECK_SIZE,CheckList.CHECK_SIZE)
        draw_rectangle(self.off_pixmap,text_gc,0,0,0,CheckList.CHECK_SIZE-1,CheckList.CHECK_SIZE-1)










    def _realize_cb (self, clist):
        self.on_pixmap = create_pixmap(self.get_window(), CheckList.CHECK_SIZE,CheckList.CHECK_SIZE)
        self.off_pixmap = create_pixmap(self.get_window(), CheckList.CHECK_SIZE,CheckList.CHECK_SIZE)

        # We can't connect this callback before because of a bug in PyGtk where it doesn't
        # like style_set to be called with a NULL old_style
        self.connect ("style_set", lambda self, old_style: self._color_pixmaps)
        self._color_pixmaps()

        for i in range (self.n_rows):
            self._update_row (i)

    def _toggle_row (self, row):
        (val, row_data, name) = self.get_row_data(row)
        val = not val
        self.set_row_data(row, (val, row_data, name))
        
        self._update_row (row)

#        print "Val: ", val, "     Row data: ", row_data, "    Name ", name

        
        if self.toggled_func != None:
            self.toggled_func(val, row_data)


        
        















