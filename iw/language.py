from gtk import *
from iw import *

class LanguageWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Language Selection")
        ics.setNextEnabled (1)
        ics.setHTML ("<HTML><BODY>Select which language you would like"
                     "to use for the system default.</BODY></HTML>")
        
        self.languages = ["English", "German", "French", "Spanish",
                          "Hungarian", "Japanese", "Chinese", "Korean"]
        self.question = ("What language should be used during the "
                         "installation process?")
        
    def getScreen (self):
        mainBox = GtkVBox (FALSE, 10)
        label = GtkLabel (self.question)
        label.set_alignment (0.5, 0.5)
        
        box = GtkVBox (FALSE, 10)
        language1 = GtkRadioButton (None, self.languages[0])
        box.pack_start (language1, FALSE)
        for locale in self.languages[1:]:
            language = GtkRadioButton (language1, locale)
            box.pack_start (language, FALSE)

        align = GtkAlignment (0.5, 0.5)
        align.add (box)

        mainBox.pack_start (label, FALSE, FALSE, 10)
        mainBox.pack_start (align)
        
        return mainBox
