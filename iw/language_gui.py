from gtk import *
from iw_gui import *
from translate import _, N_

class LanguageWindow (InstallWindow):

    windowTitle = N_("Language Selection")
    htmlTag = "lang"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setPrevEnabled(FALSE)

    def getNext (self):
	self.instLang.setRuntimeLanguage(self.lang)
	self.ics.getICW().setLanguage (self.instLang.getLangNick(self.lang))

        return None

    def select_row (self, clist, row, col, event):
        if self.running:
            self.lang = clist.get_row_data (clist.selection[0])

    # LanguageWindow tag="lang"
    def getScreen (self, intf, instLang):
        self.running = 0
        mainBox = GtkVBox (FALSE, 10)
        label = GtkLabel (_("What language should be used during the "
                         "installation process?"))
        label.set_alignment (0.5, 0.5)
        label.set_line_wrap (TRUE)
        
        self.language = GtkCList ()
        self.language.set_selection_mode (SELECTION_BROWSE)
        self.language.connect ("select_row", self.select_row)
	self.instLang = instLang

        default = -1
        n = 0
        for locale in instLang.available():
            row = self.language.append ((_(locale),))
            self.language.set_row_data (row, locale)

            if locale == instLang.getCurrent():
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
