from gtk import *
from iw_gui import *
from translate import _
from xpms_gui import RADIOBUTTON_ON_XPM
from xpms_gui import RADIOBUTTON_OFF_XPM
import GdkImlib
from GDK import _2BUTTON_PRESS
from gnome.ui import *


class LanguageSupportWindow (InstallWindow):
    foo = GdkImlib.create_image_from_xpm (RADIOBUTTON_ON_XPM)
    foo.render()
    checkMark = foo.make_pixmap()
    del foo

    foo = GdkImlib.create_image_from_xpm (RADIOBUTTON_OFF_XPM)
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
                row = self.language.append (("", locale))
                if self.languages[locale] == self.defaultLang:
                    self.language.set_pixmap(i, 0, self.checkMark)
                else:
                    self.language.set_pixmap(i, 0, self.checkMark_Off)
                i = i + 1
        self.language.thaw ()

    def updateAvailable (self):
        self.languageAvailable.freeze ()
        for i in range(self.languageAvailable.rows):
            self.languageAvailable.remove (0)

        self.available.sort ()
        for locale in self.available:
            row = self.languageAvailable.append ((locale,))

        self.languageAvailable.thaw ()


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
        self.updateAvailable()

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

        table = GtkTable ()
        
        label = GtkLabel (_("Which languages should be supported on this "
                            "system?"))
        label.set_alignment (0.5, 0.5)
        label.set_line_wrap (TRUE)
        table.attach (label, 0, 3, 0, 1, FALSE, FALSE)
        
 	language_keys = self.languages.keys ()
        language_keys.sort ()

        # support everything?
        self.supportAll = GtkRadioButton(None,
                                         _("Install support for all languages"))
        self.supportAll.connect ("toggled", self.allToggled)
        self.selectLanguages = GtkRadioButton(self.supportAll,
                                              _("Select languages to support"))

        if self.langs:
            self.selectLanguages.set_active (TRUE)
        
        align = GtkAlignment (0.0, 0.5)
        vbox = GtkVBox (3, FALSE)
        vbox.pack_start (self.supportAll)
        vbox.pack_start (self.selectLanguages)
        align.add (vbox)
        table.attach (align, 0, 3, 1, 2, FILL|EXPAND, FALSE)

        # langs we can support
        self.languageAvailable = GtkCList (1, (_("Available"),))
        self.languageAvailable.set_selection_mode (SELECTION_MULTIPLE)
        self.languageAvailable.connect ("select_row",
                                        self.available_select_row)

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        sw.add (self.languageAvailable)

        vbox = GtkVBox(FALSE, 5)
        header = GtkLabel (_("Languages Available"))
#        vbox.pack_start (header, FALSE)
        vbox.pack_start (sw, TRUE)
        self.sensitiveList.append (sw)
        table.attach (vbox, 0, 1, 3, 4, EXPAND|FILL, EXPAND|FILL)

        # <- -> buttons
        vbox = GtkVBox (FALSE, 5)
        self.addbutton = GtkButton()
        self.addbutton.add (GnomeStock (STOCK_BUTTON_NEXT))
        self.addbutton.connect ("pressed", self.onAdd)
        self.removebutton = GtkButton()
        self.removebutton.add (GnomeStock (STOCK_BUTTON_PREV))
        self.removebutton.connect ("pressed", self.onRemove)
        vbox.pack_start (self.addbutton, FALSE)
        vbox.pack_start (self.removebutton, FALSE)
        self.sensitiveList.append (self.removebutton)
        self.sensitiveList.append (self.addbutton)

        alignment = GtkAlignment (.5, .5)
        alignment.add(vbox)

        table.attach(alignment, 1, 2, 3, 4, FALSE)

        # langs we want to support
        self.language = GtkCList (2, (_("Default"), _("Selected")))
        self.language.set_selection_mode (SELECTION_MULTIPLE)
        self.language.connect ("select_row", self.support_select_row)

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        sw.add (self.language)
        table.attach (sw, 2, 3, 3, 4, EXPAND|FILL, EXPAND|FILL)

        # default button
        alignment = GtkAlignment (0.5, 0.5)
        button = GtkButton (_("Select as default"))
        alignment.add (button)

#        table.attach (alignment, 2, 3, 4, 5,
#                      FALSE, FALSE, 5, 5)

        self.running = 1

        # set up initial state
        self.allToggled (self.supportAll)
        
        return table
