from gtk import *
from iw import *
from gui import _

class LanguageWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Language Selection"))

        if self.todo.reconfigOnly:
            ics.setPrevEnabled (1)
        else:
            ics.setPrevEnabled (0)

        ics.setNextEnabled (1)
        ics.readHTML ("lang")
        self.ics = ics
        self.icw = ics.getICW ()
        self.question = (_("What language should be used during the "
                         "installation process?"))
        self.languages = self.todo.language.available ()
        self.running = 0
        self.lang = None

    def getNext (self):
        if self.lang:
            self.todo.language.set (self.lang)
            self.icw.setLanguage (self.languages[self.lang])
        return None

        
    def select_row (self, clist, row, col, event):
        if self.running:
            lang = clist.get_text (clist.selection[0], 0)
            self.lang = lang
        
    def getScreen (self):
        self.running = 0
        mainBox = GtkVBox (FALSE, 10)
        label = GtkLabel (self.question)
        label.set_alignment (0.5, 0.5)
        label.set_line_wrap (TRUE)
        
 	language_keys = self.languages.keys ()
        language_keys.sort ()

        self.language = GtkCList ()
        self.language.set_selection_mode (SELECTION_BROWSE)
        self.language.connect ("select_row", self.select_row)

        default = -1
        n = 0
        for locale in language_keys:
            row = self.language.append ((locale,))
            if self.languages[locale] == self.todo.language.get ():
                default = n
            n = n + 1

        if default > 0:
            self.language.select_row (default, 0)

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_NEVER, POLICY_NEVER)
        sw.add (self.language)
        
        mainBox.pack_start (label, FALSE, FALSE, 10)
        mainBox.pack_start (sw, TRUE)

        self.running = 1
        
        return mainBox
