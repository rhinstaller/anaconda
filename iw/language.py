from gtk import *
from iw import *
from gui import _

class LanguageWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Language Selection"))
        ics.setPrevEnabled (0)
        ics.setNextEnabled (1)
        ics.setHTML ("<HTML><BODY>Select which language you would like"
                     "to use for the system default.</BODY></HTML>")
        
        self.question = (_("What language should be used during the "
                         "installation process?"))

    def languageSelected (self, button, locale):
        self.todo.language.set (locale)
        
    def getScreen (self):
        mainBox = GtkVBox (FALSE, 10)
        label = GtkLabel (self.question)
        label.set_alignment (0.5, 0.5)
        
        box = GtkVBox (FALSE, 10)
	language_keys = self.todo.language.available ().keys ()
        language1 = GtkRadioButton (None, language_keys[0])
        language1.connect ("clicked", self.languageSelected, language_keys[0])
        self.todo.language.set (language_keys[0])
        box.pack_start (language1, FALSE)
        for locale in language_keys[1:]:
            language = GtkRadioButton (language1, locale)
            language.connect ("clicked", self.languageSelected, locale)
            box.pack_start (language, FALSE)

        align = GtkAlignment (0.5, 0.5)
        align.add (box)

        mainBox.pack_start (label, FALSE, FALSE, 10)
        mainBox.pack_start (align)
        
        return mainBox
