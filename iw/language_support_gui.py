from gtk import *
from iw_gui import *
from translate import _
from xpms_gui import CHECKBOX_ON_XPM
from xpms_gui import CHECKBOX_OFF_XPM
import GdkImlib
from GDK import _2BUTTON_PRESS
from gnome.ui import *
import checklist

class LanguageSupportWindow (InstallWindow):
    foo = GdkImlib.create_image_from_xpm (CHECKBOX_ON_XPM)
    foo.render()
    checkMark = foo.make_pixmap()
    del foo

    foo = GdkImlib.create_image_from_xpm (CHECKBOX_OFF_XPM)
    foo.render()
    checkMark_Off = foo.make_pixmap()
    del foo

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Language Selection"))

        ics.setNextEnabled (1)
        ics.readHTML ("langsupport")
        self.ics = ics
        self.icw = ics.getICW ()
        self.languages = self.todo.language.getAllSupported ()

    def getNext (self):
        self.langs = []

        for row in range(self.maxrows):
            (val, row_data, header) = self.language.get_row_data (row)
            
            if val == 1:
                selected = self.language.get_text (row, 1)
                self.langs.append (selected)

        self.defaultLang = self.combo.entry.get_text()
        self.todo.language.setSupported (self.langs)
        self.todo.language.setDefault (self.defaultLang)

        return None

    def support_select_row (self, clist, event):
	# ACK: we need exception handling around here
        
	row, col  = self.language.get_selection_info (event.x, event.y)
	selected = self.language.get_text (row, 1)
	self.toggle_row (row)

	self.rebuild_combo_box()

    def rebuild_combo_box(self):
        list = []

	for row in range(self.maxrows):
	    (val, row_data, header) = self.language.get_row_data (row)
	    if val == 1:
		selected = self.language.get_text (row, 1)
		list.append (selected)
	
	if len(list) == 0:
	    list = [""]
	    self.ics.setNextEnabled (FALSE)
	else:
	    self.ics.setNextEnabled (TRUE)

        self.defaultLang = self.combo.entry.get_text()
	self.combo.set_popdown_strings(list)

	if self.defaultLang in list:
	    index = list.index(self.defaultLang)
	    self.combo.list.select_item(index)
	else:
	    self.combo.list.select_item(0)
	    self.defaultLang = list[0]

    def toggle_row (self, row):
        (val, row_data, header) = self.language.get_row_data(row)
        val = not val
        self.language.set_row_data(row, (val, row_data, header))
        self.language._update_row (row)
        
    def select_all (self, data):
        self.ics.setNextEnabled (TRUE)
        for row in range(self.maxrows):
            (val, row_data, header) = self.language.get_row_data (row)
            self.language.set_row_data (row, (TRUE, row_data, header)) 
            self.language._update_row (row)

	self.rebuild_combo_box()

    def reset (self, data):
        self.ics.setNextEnabled (TRUE)
	list = []
        for row in range(self.maxrows):
	    (val, row_data, header) = self.language.get_row_data (row)
            item = self.language.get_text (row, 1)

	    if item in self.origLangs:
                self.language.set_row_data(row, (1, row_data, header))
                self.language._update_row (row)
                list.append (item)
            else:
                self.language.set_row_data(row, (0, row_data, header))
                self.language._update_row (row)

	self.defaultLang = self.oldDefaultLang
	self.combo.set_popdown_strings(list)

	self.combo.list.select_item(list.index(self.defaultLang))

    def language_key_press (self, list, event):
        if event.keyval == ord(" ") and self.language.focus_row != -1:
            self.toggle_row (self.language.focus_row)
	    self.rebuild_combo_box()

    # LanguageSupportWindow tag="langsupport"
    def getScreen (self):
	def moveto (widget, event, item):
            widget.moveto (item, 0, 0.5, 0.5)

        self.langs = self.todo.language.getSupported()
	self.origLangs = self.langs

	self.defaultLang = self.todo.language.getDefault()
	self.oldDefaultLang = self.defaultLang
            
        vbox = GtkVBox (FALSE, 10)
        hbox = GtkHBox (FALSE)
        
        label = GtkLabel (_("Choose the default language:   "))
        hbox.pack_start (label, FALSE, 20)

        self.combo = GtkCombo ()

        hbox.pack_start (self.combo, FALSE, 20)
        vbox.pack_start (hbox, FALSE, 50)

        sep = GtkHSeparator ()
        vbox.pack_start (sep, FALSE, 15)

        label = GtkLabel (_("Choose the languages to install:"))
        label.set_alignment (0.0, 0.5)
        label.set_line_wrap (TRUE)
        vbox.pack_start (label, FALSE)
        
        hbox = GtkHBox (FALSE)

        # langs we want to support
        self.language = checklist.CheckList(1)
        self.language.connect ("button_press_event", self.support_select_row)
        self.language.connect ("key_press_event", self.language_key_press)

        self.maxrows = 0
        list = []
        comboCurr = 0
	firstItem = 0
        sel = 0
        for locale in self.languages:
	    if locale == self.defaultLang or (locale in self.langs):
		self.language.append_row((locale, ""), TRUE)
		list.append(locale)

		if locale == self.defaultLang:
		    firstItem = self.maxrows
		    sel = comboCurr
		else:
		    comboCurr = comboCurr + 1
	    else:
		self.language.append_row((locale, ""), FALSE)

            self.maxrows = self.maxrows + 1

        self.language.connect_after ("draw", moveto, firstItem)
            
        self.combo.set_popdown_strings (list)
        self.combo.list.select_item(sel)
        self.combo.entry.set_editable(FALSE)

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        sw.add (self.language)

        vbox2 = GtkVBox (FALSE, 12)

        all_button = GtkButton (_("Select all"))
        all_button.set_usize(160, -1)
        all_button.connect ('clicked', self.select_all)
        a1 = GtkAlignment (0.5, 0.5)
        a1.add (all_button)

        reset_button = GtkButton (_("Reset"))
        reset_button.set_usize(160, -1)
        reset_button.connect ('clicked', self.reset)
        a2 = GtkAlignment (0.5, 0.5)
        a2.add (reset_button)

        vbox2.pack_start (a1, FALSE, 10)
        vbox2.pack_start (a2, FALSE)
        hbox.pack_start (sw, TRUE, 10)
        hbox.pack_start (vbox2, FALSE, 10)
        vbox.pack_start (hbox, TRUE)

        # default button
        alignment = GtkAlignment (0.0, 0.0)
        button = GtkButton (_("Select as default"))
        alignment.add (button)

        return vbox





