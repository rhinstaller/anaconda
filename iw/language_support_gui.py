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
        self.languages = self.todo.language.available ()
        self.running = 0

    def getNext (self):
        self.todo.language.setSupported (self.langs)
        self.todo.language.setByAbbrev (self.defaultLang)
        return None

    def available_select_row (self, clist, row, col, event):
        if event and event.type == _2BUTTON_PRESS:
            lang = clist.get_text (row, 0)
            clist.remove (row)
            self.langs.append (self.languages[lang])
            self.updateSelected ()

    def support_select_row (self, clist, row, col, event):
        if event and (col == 0 or col == -1):
            newDefault = clist.get_text (row, 1)
            self.defaultLang = self.languages[newDefault]
            self.updateSelected ()
            clist.select_row (row, col)
            
    def updateSelected (self):
        self.language.freeze ()
        for i in range(self.language.rows):
            self.language.remove (0)

        i = 0
        
        language_keys = self.languages.keys ()
        language_keys.sort ()
        for locale in language_keys:
            if not self.langs or (self.languages[locale] in self.langs):
                row = self.language.append_row ((locale, "1"), TRUE, None)
#                if self.languages[locale] == self.defaultLang:
#                    self.language.set_pixmap(i, 0, self.checkMark)
#                else:
#                    self.language.set_pixmap(i, 0, self.checkMark_Off)
                i = i + 1
        self.language.thaw ()


    def allToggled (self, button):
        if not self.running:
            return
        language_keys = self.languages.keys ()
        language_keys.sort ()
        if button.get_active ():
            state = FALSE
        else:
            state = TRUE

        for widget in self.sensitiveList:
            widget.set_sensitive (state)

        if state == TRUE:
            # clear the current selection
            # set up for picking which lang we want.
            self.langs = self.lastLangs
            if not self.langs:
                self.langs.append (self.defaultLang)
            self.available = []
            for lang in language_keys:
                if not self.langs or (self.languages[lang] not in self.langs):
                    self.available.append (lang)
        else:
            self.available = []
            # speicfy no languages.
            self.lastLangs = self.langs
            self.langs = []
            
        self.updateSelected()


    def onAdd (self, button):
        for i in self.languageAvailable.selection:
            lang = self.languageAvailable.get_text (i, 0)
            self.langs.append (self.languages[lang])
            self.available.remove (lang)
        self.updateSelected()
        self.updateAvailable()
        
    def onRemove (self, button):
        for i in self.language.selection:
            lang = self.language.get_text (i, 1)
            self.langs.remove (self.languages[lang])
            self.available.append (lang)
        self.updateSelected()
        self.updateAvailable()

    # LanguageSupportWindow tag="langsupport"
    def getScreen (self):
        self.langs = self.todo.language.getSupported()
        self.lastLangs = self.langs
        self.sensitiveList = []
        self.running = 0
        self.defaultLang = self.todo.language.get()


 	language_keys = self.languages.keys ()
        language_keys.sort ()

#        table = GtkTable ()

        vbox = GtkVBox (FALSE, 10)

        hbox = GtkHBox (FALSE)
        
        label = GtkLabel (_("Choose the default language:   "))
#        label.set_alignment (0.01, 0.5)
#        label.set_line_wrap (TRUE)
        hbox.pack_start (label, FALSE, 20)

        combo = GtkCombo ()
        combo.set_popdown_strings (language_keys)
#        alignment = GtkAlignment (1.0, 0.0)
#        alignment.add (combo)

        hbox.pack_start (combo, FALSE, 20)

        vbox.pack_start (hbox, FALSE, 50)


        sep = GtkHSeparator ()
        vbox.pack_start (sep, FALSE, 15)

        label = GtkLabel (_("Choose the languages to install:"))
        label.set_alignment (0.0, 0.5)
        label.set_line_wrap (TRUE)
        vbox.pack_start (label, FALSE)
        
#        bb = GtkHButtonBox ()


        hbox = GtkHBox (FALSE)


        # langs we want to support
        self.language = checklist.CheckList(1)
#        self.language.set_column_title (0, (_("Default")))
#        self.language.set_column_title (1, (_("Selected")))
#        self.language.column_titles_show ()
#        self.language.set_selection_mode (SELECTION_MULTIPLE)
#        self.language.connect ("select_row", self.support_select_row)

#        i = 0
        for locale in language_keys:

            if self.languages[locale] == self.defaultLang:
                self.language.append_row((locale, ""), TRUE)
#                self.language.set_pixmap(i, 0, self.checkMark)
            else:
                self.language.append_row((locale, ""), FALSE)
#                self.language.set_pixmap(i, 0, self.checkMark_Off)
#            i = i + 1

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        sw.add (self.language)
#        table.attach (sw, 2, 3, 3, 4, EXPAND|FILL, EXPAND|FILL)
#        vbox.pack_start (sw, TRUE)

        vbox2 = GtkVBox (FALSE, 12)

        all_button = GtkButton (_("Select all"))
        all_button.set_usize(160, -1)
        a1 = GtkAlignment (0.5, 0.5)
        a1.add (all_button)

        reset_button = GtkButton (_("Reset"))
        reset_button.set_usize(160, -1)
        a2 = GtkAlignment (0.5, 0.5)
        a2.add (reset_button)

        vbox2.pack_start (a1, FALSE, 10)
        vbox2.pack_start (a2, FALSE)
        
#        vbox.pack_start (alignment, FALSE, 25)







        hbox.pack_start (sw, TRUE, 10)
        hbox.pack_start (vbox2, FALSE, 10)
        vbox.pack_start (hbox, TRUE)

        # default button
        alignment = GtkAlignment (0.0, 0.0)
        button = GtkButton (_("Select as default"))
        alignment.add (button)

#        table.attach (alignment, 2, 3, 4, 5,
#                      FALSE, FALSE, 5, 5)

        self.running = 1

        # set up initial state
#        self.allToggled (self.supportAll)

        return vbox
#        return table
