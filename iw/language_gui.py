from gtk import *
from iw_gui import *
from translate import _

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
        self.languages = self.todo.instTimeLanguage.available()
        self.running = 0
        self.lang = None

    def getNext (self):
        if self.lang:
            self.icw.setLanguage (self.lang)

            #--Go ahead and pull the release notes into memory.  This allows them to be viewed
            #--during package installation
            self.icw.buff = ""
            try:
                filename = "/mnt/source/RELEASE-NOTES." + self.languages[self.lang]
                file = open(filename, "r")
                for line in file.readlines():
                    self.icw.buff = self.icw.buff + line
                file.close()

            except:
                try:
                    filename = "/RELEASE-NOTES." + self.languages[self.lang]
                    file = open(filename, "r")
                    for line in file.readlines():
                        self.icw.buff = self.icw.buff + line
                    file.close()
                except:
                    try:
                        filename = "/RELEASE-NOTES"
                        file = open(filename, "r")
                        for line in file.readlines():
                            self.icw.buff = self.icw.buff + line
                        file.close()
                    except:
                        pass

        return None

    def select_row (self, clist, row, col, event):
        if self.running:
            lang = clist.get_text (clist.selection[0], 0)
            self.lang = lang

    # LanguageWindow tag="lang"
    def getScreen (self):
        self.running = 0
        mainBox = GtkVBox (FALSE, 10)
        label = GtkLabel (_("What language should be used during the "
                         "installation process?"))
        label.set_alignment (0.5, 0.5)
        label.set_line_wrap (TRUE)
        
        self.language = GtkCList ()
        self.language.set_selection_mode (SELECTION_BROWSE)
        self.language.connect ("select_row", self.select_row)

        default = -1
        n = 0
        for locale in self.languages:
            row = self.language.append ((locale,))
            if locale == self.todo.instTimeLanguage.getCurrent():
                self.lang = locale
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
