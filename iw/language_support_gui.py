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
import gui
from iw_gui import *
from flags import flags
from rhpl.translate import _, N_

from gui import setupTreeViewFixupIdleHandler

class LanguageSupportWindow (InstallWindow):
    windowTitle = _("Additional Language Support")
    htmlTag = "langsupport"
    
    def getNext (self):
        self.supportedLangs = []

        for row in range(self.maxrows):
            if self.languageList.get_active(row) == 1:
                selected = self.languageList.get_text (row, 1)
                self.supportedLangs.append (selected)

	curidx = self.deflang_optionmenu.get_history()
	self.defaultLang = self.deflang_values[curidx]
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
	olddef = self.defaultLang
	oldidx = None
	for row in range(self.maxrows):
	    selected = self.languageList.get_text (row, 1)
	    if selected == olddef:
		oldidx = row
		break

	self.rebuild_optionmenu()

	# if no default lang now restore
	# this can happen if they clicked on the only remaining selected
	# language.  If we dont reset to previous default lang selected
	# the UI is confusing because there is no default lang and no
	# langauges supported
	if self.defaultLang is None or self.defaultLang == "":
            self.languageList.set_active(oldidx, gtk.TRUE)
	    self.rebuild_optionmenu()
	    
    def rebuild_optionmenu(self):
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

	curidx = self.deflang_optionmenu.get_history()
	if curidx >= 0:
	    self.defaultLang = self.deflang_values[curidx]
	else:
	    self.defaultLang = None

	if self.defaultLang is not None and self.defaultLang in list:
	    index = list.index(self.defaultLang)
	else:
	    index = 0
	    self.defaultLang = list[0]

	self.createDefaultLangMenu(list)
	self.deflang_optionmenu.set_history(index)

    def select_all (self, data):
        self.ics.setNextEnabled (gtk.TRUE)
        for row in range(self.maxrows):
            self.languageList.set_active(row, gtk.TRUE)

	self.rebuild_optionmenu()

    def select_default (self, data):
        self.ics.setNextEnabled (gtk.TRUE)

	curidx = self.deflang_optionmenu.get_history()
	if curidx >= 0:
	    deflang = self.deflang_values[curidx]

	    for row in range(self.maxrows):
		if self.languageList.get_text(row, 1) == deflang:
		    self.languageList.set_active(row, gtk.TRUE)
		else:
		    self.languageList.set_active(row, gtk.FALSE)

	    self.rebuild_optionmenu()

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
	self.createDefaultLangMenu(list)
	self.deflang_optionmenu.set_history(self.deflang_values.index(self.defaultLang))

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

    def createDefaultLangMenu(self, supported):
	if self.deflang_optionmenu is None:
	    self.deflang_optionmenu = gtk.OptionMenu()

	if self.deflang_menu is not None:
	    self.deflang_optionmenu.remove_menu()
	    
	self.deflang_menu = gtk.Menu()

	sel = None
        curidx = 0
	values = []
        for locale in self.languages:
	    if locale == self.defaultLang or (locale in supported):
		item = gtk.MenuItem(locale)
		item.show()
		self.deflang_menu.add(item)

		if locale == self.defaultLang:
		    sel = curidx
		else:
		    curidx = curidx + 1

		values.append(locale)

	self.deflang_optionmenu.set_menu(self.deflang_menu)

	if sel is not None:
	    self.deflang_optionmenu.set_history(sel)

	self.deflang_values = values

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
        vbox.set_border_width(5)
        hbox = gtk.HBox (gtk.FALSE)
        
	# create option menu of default langs
        label = gui.MnemonicLabel(_("Select the _default language for the system:   "))
	self.deflang_optionmenu = None
	self.deflang_menu = None
	self.deflang_values = None
	self.createDefaultLangMenu(self.supportedLangs)
        label.set_mnemonic_widget(self.deflang_optionmenu)

        hbox.pack_start (label, gtk.FALSE, 20)
        hbox.pack_start (self.deflang_optionmenu, gtk.FALSE, 20)
        vbox.pack_start (hbox, gtk.FALSE, 50)

        sep = gtk.HSeparator ()
        vbox.pack_start (sep, gtk.FALSE, 15)

	label = gui.MnemonicLabel(_("Select _additional languages to install "
				    "on the system:"))
        
        label.set_alignment (0.0, 0.5)
        label.set_line_wrap (gtk.TRUE)
        label.set_size_request(400, -1)
        vbox.pack_start (label, gtk.FALSE)
        
        hbox = gtk.HBox (gtk.FALSE, 5)

        # langs we want to support
        self.languageList = checklist.CheckList(1)
        label.set_mnemonic_widget(self.languageList)

        self.maxrows = 0
        list = []

        for locale in self.languages:
	    if locale == self.defaultLang or (locale in self.supportedLangs):
		self.languageList.append_row((locale, ""), gtk.TRUE)
		list.append(locale)
	    else:
		self.languageList.append_row((locale, ""), gtk.FALSE)

            self.maxrows = self.maxrows + 1

        self.setCurrent(self.defaultLang)
            
        sw = gtk.ScrolledWindow ()
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.add (self.languageList)
        sw.set_shadow_type(gtk.SHADOW_IN)

        vbox2 = gtk.VBox (gtk.FALSE, 12)

        all_button = gtk.Button (_("_Select All"))
        all_button.set_size_request(160, -1)
        all_button.connect ('clicked', self.select_all)
        a1 = gtk.Alignment (0.5, 0.5)
        a1.add (all_button)

        default_button = gtk.Button (_("Select Default _Only"))
        default_button.set_size_request(160, -1)
        default_button.connect ('clicked', self.select_default)
        a2 = gtk.Alignment (0.5, 0.5)
        a2.add (default_button)

        reset_button = gtk.Button (_("Rese_t"))
        reset_button.set_size_request(160, -1)
        reset_button.connect ('clicked', self.reset)
        a3 = gtk.Alignment (0.5, 0.5)
        a3.add (reset_button)

        vbox2.pack_start (a1, gtk.FALSE, 10)
        vbox2.pack_start (a2, gtk.FALSE)
        vbox2.pack_start (a3, gtk.FALSE)
        hbox.pack_start (sw, gtk.TRUE, 10)
        hbox.pack_start (vbox2, gtk.FALSE, 10)
        vbox.pack_start (hbox, gtk.TRUE)

        # default button
#        alignment = gtk.Alignment (0.0, 0.0)
#        button = gtk.Button (_("Select as default"))
#        alignment.add (button)

	# connect CB for when they change selected langs
        self.languageList.checkboxrenderer.connect("toggled",
					       self.toggled_language)

	store = self.languageList.get_model()

	setupTreeViewFixupIdleHandler(self.languageList, store)


        return vbox
