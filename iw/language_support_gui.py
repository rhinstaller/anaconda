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
#        self.todo.language.setSupported (self.langs)
#        self.todo.language.setByAbbrev (self.defaultLang)

        self.langs = []
        support_all = TRUE

        for row in range(self.maxrows):
            (val, row_data, header) = self.language.get_row_data (row)

            
            if val == 1:
                print "selected"
                selected = self.language.get_text (row, 1)
                self.langs.append (self.languages[selected])
            else:
                print "not selected"
                support_all = FALSE

        if support_all == TRUE:
            print "Supporting all langs"
            self.langs = None


        self.defaultLang = self.languages[self.combo.entry.get_text()]        

        print "langs = ", self.langs
        print "self.defaultLang = ", self.defaultLang

        self.todo.language.setSupported (self.langs)
        self.todo.language.setByAbbrev (self.defaultLang)


        return None

    def support_select_row (self, clist, event):
        print "support_select_row"
        list = []
        try:
            row, col  = self.language.get_selection_info (event.x, event.y)
            selected = self.language.get_text (row, 1)
#            print "selected = ", selected
            self.toggle_row (row)

            for row in range(self.maxrows):
                (val, row_data, header) = self.language.get_row_data (row)
                if val == 1:
                    selected = self.language.get_text (row, 1)
                    list.append (selected)
            
#            print len(list)        
            if len(list) == 0:
                list = [""]
                self.ics.setNextEnabled (FALSE)
            else:
                self.ics.setNextEnabled (TRUE)

            self.combo.set_popdown_strings(list)      

            for row in range(self.maxrows):
                if self.languages[self.language.get_text (row, 1)] == self.defaultLang:
#                    print "self.defaultLang is ", self.defaultLang
                    default = self.language.get_text (row, 1)
                    index = list.index(default)
#                    print "self.defaultLang is at index ", index
                    self.combo.list.select_item(index)
        except:
            pass

    def toggle_row (self, row):
        (val, row_data, header) = self.language.get_row_data(row)
#        print val, row_data, header
        val = not val
        self.language.set_row_data(row, (val, row_data, header))
        self.language._update_row (row)
        
    def select_all (self, data):
        self.ics.setNextEnabled (TRUE)
        for row in range(self.maxrows):
            (val, row_data, header) = self.language.get_row_data (row)
            self.language.set_row_data (row, (TRUE, row_data, header)) 
            self.language._update_row (row)

        self.combo.set_popdown_strings (self.language_keys)

        for row in range(self.maxrows):
            if self.languages[self.language.get_text (row, 1)] == self.defaultLang:
#                print "self.defaultLang is ", self.defaultLang
                default = self.language.get_text (row, 1)
                index = self.language_keys.index(default)
#                print "self.defaultLang is at index ", index
                self.combo.list.select_item(index)

    def reset (self, data):
        self.ics.setNextEnabled (TRUE)
        for row in range(self.maxrows):
            selected = self.languages[self.language.get_text (row, 1)]
            (val, row_data, header) = self.language.get_row_data (row)

            if selected == self.defaultLang:
                self.language.set_row_data(row, (1, row_data, header))
                self.language._update_row (row)

                selected = self.language.get_text (row, 1)
                list = []
                list.append (selected)
                self.combo.set_popdown_strings(list)
#                index = list.index(selected)
#                print index
#                self.combo.list.select_item(index)
            else:
                self.language.set_row_data(row, (0, row_data, header))
                self.language._update_row (row)


    # LanguageSupportWindow tag="langsupport"
    def getScreen (self):
        self.langs = self.todo.language.getSupported()

        self.lastLangs = self.langs
        print "Supported Langs are: ", self.langs
        self.sensitiveList = []
        self.running = 0

        self.defaultLang = self.icw.getLanguage ()
        print "self.defaultLang", self.defaultLang
#        self.defaultPosition = 0

 	self.language_keys = self.languages.keys ()
        self.language_keys.sort ()

        vbox = GtkVBox (FALSE, 10)
        hbox = GtkHBox (FALSE)
        
        label = GtkLabel (_("Choose the default language:   "))
        hbox.pack_start (label, FALSE, 20)

        self.combo = GtkCombo ()
#        combo.set_popdown_strings (language_keys)


        hbox.pack_start (self.combo, FALSE, 20)
        vbox.pack_start (hbox, FALSE, 50)

        sep = GtkHSeparator ()
        vbox.pack_start (sep, FALSE, 15)

        label = GtkLabel (_("Choose the languages to install:"))
        label.set_alignment (0.0, 0.5)
        label.set_line_wrap (TRUE)
        vbox.pack_start (label, FALSE)
        
        hbox = GtkHBox (FALSE)

        # langs we want to support
        self.language = checklist.CheckList(1)
        self.language.connect ('button_press_event', self.support_select_row)

        self.maxrows = 0
        list = []
        comboCurr = 0
        for locale in self.language_keys:
            if self.languages[locale] == self.defaultLang or self.langs == None:
                self.language.append_row((locale, ""), TRUE)
                list.append(locale)
            else:
                try:
                    if self.langs.index(self.languages[locale]) >= 0:
                        self.language.append_row((locale, ""), TRUE)
                        list.append(locale)
                        comboCurr = comboCurr + 1
                except:
                    self.language.append_row((locale, ""), FALSE)
                    
            self.maxrows = self.maxrows + 1
            self.todo.langMaxRows = self.maxrows
            
        self.combo.set_popdown_strings (list)
        print comboCurr
        self.combo.list.select_item(comboCurr)






#        for locale in self.language_keys:
#            print locale
#            if self.langs == []:
#                print "ALL :", self.languages
#                self.language.append_row((locale, ""), TRUE)

#                for locale2 in self.language_keys:
#                    list.append(locale2)
#                list.append (locale)

#                self.combo.set_popdown_strings (list)

#                if self.languages[locale] == self.defaultLang:
#                    print "dddddddd", locale

#                    print self.language_keys.index(self.languages[locale])
#                    index = self.language_keys.index(locale)
#                    print self.language_keys
#                    print index
#                    self.combo.list.select_item(5)

#                    except:
#                        pass
                
#                index = self.languages[self.defaultLang]

#                self.combo.list.select_item(index)


#            elif self.languages[locale] == self.defaultLang:
#                print "B"
#                self.language.append_row((locale, ""), TRUE)
#                list.append (locale)
#                self.combo.set_popdown_strings (list)
#            else:
#                print "C"
#                try:
#                    print self.lastLangs.index(self.languages[locale])
#                    self.language.append_row((locale, ""), TRUE)
#                    list.append (locale)
#                    self.combo.set_popdown_strings (list)
#                except:
#                    self.language.append_row((locale, ""), FALSE)

#            self.combo.set_popdown_strings (list)
#            print self.defaultLang
            
#            if self.languages[locale] == self.defaultLang:
#                print "dddddddd", self.lastLangs
#                try:
#                    print self.lastLangs.index(self.languages[locale])
#                    index = self.lastLangs.index(self.languages[locale])
#                    self.combo.list.select_item(index)
#                except:
#                    pass
            
#            self.maxrows = self.maxrows + 1


        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        sw.add (self.language)

        vbox2 = GtkVBox (FALSE, 12)

        all_button = GtkButton (_("Select all"))
        all_button.set_usize(160, -1)
        all_button.connect ('clicked', self.select_all)
        a1 = GtkAlignment (0.5, 0.5)
        a1.add (all_button)

        reset_button = GtkButton (_("Reset"))
        reset_button.set_usize(160, -1)
        reset_button.connect ('clicked', self.reset)
        a2 = GtkAlignment (0.5, 0.5)
        a2.add (reset_button)

        vbox2.pack_start (a1, FALSE, 10)
        vbox2.pack_start (a2, FALSE)
        hbox.pack_start (sw, TRUE, 10)
        hbox.pack_start (vbox2, FALSE, 10)
        vbox.pack_start (hbox, TRUE)

        # default button
        alignment = GtkAlignment (0.0, 0.0)
        button = GtkButton (_("Select as default"))
        alignment.add (button)


        self.running = 1

        # set up initial state
#        self.allToggled (self.supportAll)

        return vbox
#        return table


