#
# langauge_support_gui.py: dialog for selection of which languages to support.
#
# Copyright 2001-2002 Red Hat, Inc.
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
from rhpl.translate import _, N_

class LanguageSupportWindow (InstallWindow):
    windowTitle = _("Additional Language Support")
    htmlTag = "langsupport"
    
    def getNext (self):
        self.supportedLangs = []

        for row in range(self.maxrows):
            if self.languageList.get_active(row) == 1:
                selected = self.languageList.get_text (row, 1)
                self.supportedLangs.append (selected)

        self.defaultLang = self.combo.entry.get_text()
        self.langs.setSupported (self.supportedLangs)
        self.langs.setDefault (self.defaultLang)

        return None

    def toggled_language(self, data, row):
#        row = int(row)
#        lang = self.languageList.get_text(row, 1)
# 	 val = self.languageList.get_active(row)
#
	# may be too slow to redo everytime they select/deselect a lang
	# but worth trying since its simple
	self.rebuild_combo_box()
	

    def rebuild_combo_box(self):
        list = []

	for row in range(self.maxrows):
	    if self.languageList.get_active(row) == 1:
		selected = self.languageList.get_text (row, 1)
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

    def select_all (self, data):
        self.ics.setNextEnabled (gtk.TRUE)
        for row in range(self.maxrows):
            self.languageList.set_active(row, gtk.TRUE)

	self.rebuild_combo_box()

    def reset (self, data):
        self.ics.setNextEnabled (gtk.TRUE)
	list = []

        for row in range(self.maxrows):
            item = self.languageList.get_text (row, 1)

	    if item in self.origLangs:
                self.languageList.set_active(row, gtk.TRUE)
                list.append (item)
            else:
                self.languageList.set_active(row, gtk.FALSE)                

	self.defaultLang = self.oldDefaultLang
	self.combo.set_popdown_strings(list)

	self.combo.list.select_item(list.index(self.defaultLang))

    def setCurrent(self, currentDefault, recenter=1):
        parent = None

        store = self.languageList.get_model()
        row = 0

        # iterate over the list looking for the default locale
        while (row < self.languageList.num_rows):
            if self.languageList.get_text(row, 1) == currentDefault:
                path = store.get_path(store.get_iter((row,)))
                col = self.languageList.get_column(0)
                self.languageList.set_cursor(path, col, gtk.FALSE)
                self.languageList.scroll_to_cell(path, col, gtk.TRUE, 0.5, 0.5)
                break
            row = row + 1

    # LanguageSupportWindow tag="langsupport"
    def getScreen (self, langs):
	self.langs = langs

        self.languages = self.langs.getAllSupported ()

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

	label = gtk.Label (_("Choose additional languages you would "
			     "like to use on this system:"))

        label.set_alignment (0.0, 0.5)
        label.set_line_wrap (gtk.TRUE)
        label.set_size_request(400, -1)
        vbox.pack_start (label, gtk.FALSE)
        
        hbox = gtk.HBox (gtk.FALSE)

        # langs we want to support
        self.languageList = checklist.CheckList(1)

        self.maxrows = 0
        list = []
        comboCurr = 0
	firstItem = 0
        sel = 0

        for locale in self.languages:
	    if locale == self.defaultLang or (locale in self.supportedLangs):
		self.languageList.append_row((locale, ""), gtk.TRUE)
		list.append(locale)

		if locale == self.defaultLang:
		    firstItem = self.maxrows
		    sel = comboCurr
		else:
		    comboCurr = comboCurr + 1
	    else:
		self.languageList.append_row((locale, ""), gtk.FALSE)

            self.maxrows = self.maxrows + 1

        self.setCurrent(self.defaultLang)
            
        self.combo.set_popdown_strings (list)
        self.combo.list.select_item(sel)
        self.combo.entry.set_property("editable", gtk.FALSE)

        sw = gtk.ScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.add (self.languageList)
        sw.set_shadow_type(gtk.SHADOW_IN)

        vbox2 = gtk.VBox (gtk.FALSE, 12)

        all_button = gtk.Button (_("Select all"))
        all_button.set_size_request(160, -1)
        all_button.connect ('clicked', self.select_all)
        a1 = gtk.Alignment (0.5, 0.5)
        a1.add (all_button)

        reset_button = gtk.Button (_("Reset"))
        reset_button.set_size_request(160, -1)
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

	# connect CB for when they change selected langs
        self.languageList.checkboxrenderer.connect("toggled",
					       self.toggled_language)

        return vbox
