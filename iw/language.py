from gtk import *
from iw import *
from gui import _, setLanguage

class LanguageWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Language Selection"))
        ics.setPrevEnabled (0)
        ics.setNextEnabled (1)
        ics.readHTML ("lang")
        self.question = (_("What language should be used during the "
                         "installation process?"))
        self.languages = self.todo.language.available ()
        self.running = 0
        
    def select_row (self, clist, row, col, event):
        if self.running:
            lang = clist.get_text (clist.selection[0], 0)
            self.todo.language.set (lang)
            setLanguage (self.languages[lang])
        
    def getScreen (self):
        mainBox = GtkVBox (FALSE, 10)
        label = GtkLabel (self.question)
        label.set_alignment (0.5, 0.5)
        
 	language_keys = self.languages.keys ()

        self.language = GtkCList ()
        self.language.set_selection_mode (SELECTION_BROWSE)
        self.language.connect ("select_row", self.select_row)

        for locale in language_keys[1:]:
            row = self.language.append ((locale,))

        print self.todo.language.get ()
        default = self.languages.values ().index (self.todo.language.get ())
        if default > 0:
            self.language.select_row (default - 1, 0)

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_NEVER, POLICY_NEVER)
        sw.add (self.language)
        
        mainBox.pack_start (label, FALSE, FALSE, 10)
        mainBox.pack_start (sw, TRUE)

        self.running = 1
        
        return mainBox
