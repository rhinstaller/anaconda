#
# langauge_support_gui.py: dialog for selection of which languages to support.
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import checklist
import gtk
from iw_gui import *
from flags import flags
from translate import _, N_

class LanguageSupportWindow (InstallWindow):
    windowTitle = _("Additional Language Support")
    htmlTag = "langsupport"
    
    def getNext (self):
        self.supportedLangs = []

        for row in range(self.maxrows):
            (val, row_data, header) = self.language.get_row_data (row)
            
            if val == 1:
                selected = self.language.get_text (row, 1)
                self.supportedLangs.append (selected)

        self.defaultLang = self.combo.entry.get_text()
        self.langs.setSupported (self.supportedLangs)
        self.langs.setDefault (self.defaultLang)

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
	    self.ics.setNextEnabled (gtk.FALSE)
	else:
	    self.ics.setNextEnabled (gtk.TRUE)

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
        self.ics.setNextEnabled (gtk.TRUE)
        for row in range(self.maxrows):
            (val, row_data, header) = self.language.get_row_data (row)
            self.language.set_row_data (row, (gtk.TRUE, row_data, header)) 
            self.language._update_row (row)

	self.rebuild_combo_box()

    def reset (self, data):
        self.ics.setNextEnabled (gtk.TRUE)
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
    def getScreen (self, langs):
	self.langs = langs

        self.languages = self.langs.getAllSupported ()

	def moveto (widget, event, item):
            widget.moveto (item, 0, 0.5, 0.5)

        self.supportedLangs = self.langs.getSupported()
	self.origLangs = []
        for i in self.supportedLangs:
            self.origLangs.append(i)
            
	self.defaultLang = self.langs.getDefault()
	self.oldDefaultLang = self.defaultLang

        # first time we hit this point in install this is not initialized
        if self.origLangs == []:
            self.origLangs.append(self.defaultLang)
        
        vbox = gtk.VBox (gtk.FALSE, 10)
        hbox = gtk.HBox (gtk.FALSE)
        
        label = gtk.Label (_("Choose the default language for this system:   "))
        hbox.pack_start (label, gtk.FALSE, 20)

        self.combo = gtk.Combo ()

        hbox.pack_start (self.combo, gtk.FALSE, 20)
        vbox.pack_start (hbox, gtk.FALSE, 50)

        sep = gtk.HSeparator ()
        vbox.pack_start (sep, gtk.FALSE, 15)

        if flags.reconfig:
            label = gtk.Label (_("Currently installed languages:"))
        else:
            label = gtk.Label (_("Choose additional languages you would "
                                "like to use on this system:"))

        label.set_alignment (0.0, 0.5)
        label.set_line_wrap (gtk.TRUE)
        label.set_usize(400, -1)
        vbox.pack_start (label, gtk.FALSE)
        
        hbox = gtk.HBox (gtk.FALSE)

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
	    if locale == self.defaultLang or (locale in self.supportedLangs):
		self.language.append_row((locale, ""), gtk.TRUE)
		list.append(locale)

		if locale == self.defaultLang:
		    firstItem = self.maxrows
		    sel = comboCurr
		else:
		    comboCurr = comboCurr + 1
	    else:
		self.language.append_row((locale, ""), gtk.FALSE)

            self.maxrows = self.maxrows + 1

        self.language.connect_after ("expose-event", moveto, firstItem)
            
        self.combo.set_popdown_strings (list)
        self.combo.list.select_item(sel)
        self.combo.entry.set_editable(gtk.FALSE)

        sw = gtk.ScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.add (self.language)

        vbox2 = gtk.VBox (gtk.FALSE, 12)

        all_button = gtk.Button (_("Select all"))
        all_button.set_usize(160, -1)
        all_button.connect ('clicked', self.select_all)
        a1 = gtk.Alignment (0.5, 0.5)
        a1.add (all_button)

        reset_button = gtk.Button (_("Reset"))
        reset_button.set_usize(160, -1)
        reset_button.connect ('clicked', self.reset)
        a2 = gtk.Alignment (0.5, 0.5)
        a2.add (reset_button)

        vbox2.pack_start (a1, gtk.FALSE, 10)
        vbox2.pack_start (a2, gtk.FALSE)
        hbox.pack_start (sw, gtk.TRUE, 10)
        hbox.pack_start (vbox2, gtk.FALSE, 10)
        vbox.pack_start (hbox, gtk.TRUE)

        # default button
        alignment = gtk.Alignment (0.0, 0.0)
        button = gtk.Button (_("Select as default"))
        alignment.add (button)

        # in reconfig mode make some widgets unchangable
        if flags.reconfig:
            self.language.set_sensitive(gtk.FALSE)
            all_button.set_sensitive(gtk.FALSE)

        return vbox
