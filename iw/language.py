from gtk import *
from iw import *
from gui import _

class LanguageWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Language Selection"))
        ics.setPrevEnabled (0)
        ics.setNextEnabled (1)
        ics.readHTML ("lang")
        self.question = (_("What language should be used during the "
                         "installation process?"))

    def languageSelected (self, button, locale):
        self.todo.language.set (locale)
        
    def getScreen (self):
        mainBox = GtkVBox (FALSE, 10)
        label = GtkLabel (self.question)
        label.set_alignment (0.5, 0.5)
        
##         box = GtkVBox (FALSE, 5)
## 	language_keys = self.todo.language.available ().keys ()
##         language1 = GtkRadioButton (None, language_keys[0])
##         language1.connect ("clicked", self.languageSelected, language_keys[0])
##         self.todo.language.set (language_keys[0])

##         box.pack_start (language1, FALSE)
##         for locale in language_keys[1:]:
##             language = GtkRadioButton (language1, locale)
##             language.connect ("clicked", self.languageSelected, locale)
##             box.pack_start (language, FALSE)

 	language_keys = self.todo.language.available ().keys ()

        self.language = GtkCList ()
        self.language.set_selection_mode (SELECTION_BROWSE)
        for locale in language_keys[1:]:
            self.language.append ((locale,))

        print self.todo.language.available ().values ()
        self.language.select_row (self.todo.language.available ().values ().index ((self.todo.language.get ())) - 1, 0)

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_NEVER, POLICY_NEVER)
        sw.add (self.language)
        
        mainBox.pack_start (label, FALSE, FALSE, 10)
        mainBox.pack_start (sw, TRUE)
        
        return mainBox
