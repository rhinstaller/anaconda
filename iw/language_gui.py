from gtk import *
from iw_gui import *
from translate import _, N_

class LanguageWindow (InstallWindow):

    windowTitle = N_("Language Selection")
    htmlTag = "lang"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

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

        hbox = GtkHBox(FALSE, 5)
        im = self.ics.readPixmap ("gnome-globe.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            hbox.pack_start (a, FALSE)
            
        label = GtkLabel (_("What language would you like to use during the "
                         "installation process?"))
        label.set_line_wrap (TRUE)
        label.set_usize(350, -1)
        hbox.pack_start(label, FALSE)
        
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
        
        mainBox.pack_start (hbox, FALSE, FALSE, 10)
        mainBox.pack_start (sw, TRUE)

        self.running = 1
        
        return mainBox
