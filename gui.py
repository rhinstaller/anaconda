import gettext_rh
import os
os.environ["PYGTK_FATAL_EXCEPTIONS"] = "1"
from gtk import *
from gtk import _root_window
from _gtk import gtk_set_locale
import GdkImlib
from GDK import *
from translate import cat, _

im = None
splashwindow = None
try:
    im = GdkImlib.Image ("/usr/share/anaconda/pixmaps/first.png")
except:
    try:
        im = GdkImlib.Image ("pixmaps/first.png")
    except:
        print "Unable to load", file
if im:
    root = _root_window ()
    cursor = cursor_new (LEFT_PTR)
    root.set_cursor (cursor)
    threads_enter ()
    im.render ()
    splashwindow = GtkWindow ()
    splashwindow.set_position (WIN_POS_CENTER)
    box = GtkEventBox ()
    pix = im.make_pixmap ()
    style = box.get_style ().copy ()
    style.bg[STATE_NORMAL] = style.white
    box.set_style (style)
    box.add (pix)
    splashwindow.add (box)
    splashwindow.show_all ()
    while events_pending ():
        mainiteration (FALSE)
    threads_leave ()        

from gnome.ui import *
from gnome.xmhtml import *
#don't want to do this now because it makes update disk hard
#from iw.language import *
#from iw.welcome import *
#from iw.mouse import *
#from iw.keyboard import *
#from iw.installpath import *
#
# instead we do (assuming pythonpath set correctly)
#
from language_gui import *
from welcome_gui import *
from mouse_gui import *

from keyboard_gui import *
from installpath_gui import *

import isys
import sys

import rpm
from thread import *
from threading import *

class WaitWindow:
    def __init__(self, title, text):
	threads_enter ()
        self.window = GtkWindow (WINDOW_POPUP)
        self.window.set_title (_(title))
        self.window.set_position (WIN_POS_CENTER)
        self.window.set_modal (TRUE)
        label = GtkLabel (_(text))
        label.set_line_wrap (TRUE)
        box = GtkFrame ()
        box.set_border_width (10)
        box.add (label)
        box.set_shadow_type (SHADOW_NONE)
        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_OUT)
        frame.add (box)
	self.window.add (frame)
	self.window.show_all ()
        thread = currentThread ()
        if thread.getName () == "gtk_main":
            while events_pending ():
                mainiteration (FALSE)
        threads_leave ()
            
    def pop(self):
	threads_enter ()
        self.window.destroy ()
	threads_leave ()

class ProgressWindow:
    def __init__(self, title, text, total):
	threads_enter ()
        self.window = GtkWindow (WINDOW_POPUP)
        self.window.set_title (_(title))
        self.window.set_position (WIN_POS_CENTER)
        self.window.set_modal (TRUE)
        box = GtkVBox (5)
        box.set_border_width (10)

        label = GtkLabel (_(text))
        label.set_line_wrap (TRUE)
        label.set_alignment (0.0, 0.5)
        box.pack_start (label)
        
        self.total = total
	self.progress = GtkProgressBar ()
        box.pack_start (self.progress)
        
        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_OUT)
        frame.add (box)
	self.window.add (frame)
	self.window.show_all ()
        threads_leave ()

    def set (self, amount):
        threads_enter ()
	self.progress.update (float (amount) / self.total)
        threads_leave ()
    
    def pop(self):
	threads_enter ()
        self.window.destroy ()
	threads_leave ()

def ExceptionWindow():
    import sys, traceback
    (type, value, tb) = sys.exc_info()
    from string import joinfields
    list = traceback.format_exception (type, value, tb)
    text = joinfields (list, "")
    print text

    win = GnomeDialog ("Exception Occured", STOCK_BUTTON_OK)
    textbox = GtkText()
    textbox.insert_defaults (text)
    sw = GtkScrolledWindow ()
    sw.add (textbox)
    sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

    hbox = GtkHBox (FALSE)
    # XXX fix me, use util function when we upgrade pygnome
    # s = unconditional_pixmap_file ("gnome-error.png")
    if s:
        hbox.pack_start (GnomePixmap ('/usr/share/pixmaps/gnome-error.png'),
                         FALSE)

    info = GtkLabel (_("An exceptional condition has occured.  This "
                       "is most likely a bug.  Please copy the "
                       "full text of this exception and file a bug "
                       "report at "
                       "http://bugzilla.redhat.com/bugzilla"))
    info.set_line_wrap (TRUE)
    info.set_usize (350, -1)

    hbox.pack_start (sw, TRUE)
    win.vbox.pack_start (info, FALSE)            
    win.vbox.pack_start (hbox, TRUE)
    win.set_usize (500, 300)
    win.set_position (WIN_POS_CENTER)
    win.show_all ()
    win.run ()

    # welcome to the land of threads where sys.exit() doesn't.
    os.kill (os.getpid(), 9)    

class GtkMainThread (Thread):
    def run (self):
        self.setName ("gtk_main")
        threads_enter ()
        try:
            mainloop ()
        except SystemExit:
            pass
        except:
            ExceptionWindow ()
        threads_leave ()

class MessageWindow:
    def quit (self, dialog, button):
        self.rc = button
        if self.mutex:
            self.mutex.set ()

    def okcancelquit (self, button):
        self.rc = button
        if self.mutex:
            self.mutex.set ()

    def getrc (self):
        return self.rc
    
    def __init__ (self, title, text, type = "ok"):
        threads_enter ()
        if type == "ok":
            self.window = GnomeOkDialog (_(text))
            self.window.connect ("clicked", self.quit)
        if type == "okcancel":
            self.window = GnomeOkCancelDialog (_(text), self.okcancelquit)
        # this is the pixmap + the label
        hbox = self.window.vbox.children ()[0]
        label = hbox.children ()[1]
        label.set_line_wrap (TRUE)
        self.window.set_position (WIN_POS_CENTER)
        
        self.window.show_all ()

        threads_leave ()

        # there are two cases to cover here in order to be
        # modal:
        # 1) the MessageWindow is being created by the gtk_main
        #    thread, in which case we must call the mainloop recursively.
        # 2) the MessageWindow is created by some other thread, in
        #    which case we must _not_ call the mainloop (currently,
        #    you can not call the mainloop from a second thread).
        #    Instead, create an Event mutex and wait for it to get set.
        #    by the clicked signal handler
        thread = currentThread ()
        if thread.getName () == "gtk_main":
            self.mutex = None
            threads_enter ()
            self.rc = self.window.run ()
            threads_leave ()
        else:
            self.mutex = Event ()
            self.mutex.wait ()
    
class InstallInterface:
    def shutdown (self):
	pass

    def setPackageProgressWindow (self, ppw):
        self.ppw = ppw

    def waitWindow (self, title, text):
	return WaitWindow (title, text)

    def progressWindow (self, title, text, total):
	return ProgressWindow (title, text, total)

    def packageProgressWindow (self, total, totalSize):
        self.ppw.setSizes (total, totalSize)
        return self.ppw

    def messageWindow(self, title, text):
        return MessageWindow (title, text)

    def exceptionWindow(self, title, text):
        print text
        return 1

    def getBootdisk ():
        return None

    def getCongratulation ():
        return CongratulationWindow

    def run (self, todo, test = 0):
        gtkThread = GtkMainThread ()
        gtkThread.start ()

        # This is the same as the file
        if todo.reconfigOnly:
            if todo.serial:
                commonSteps = [ ( LanguageWindow, "language" ), 
                                ]
            else:
                commonSteps = [ ( ReconfigWelcomeWindow, "reconfig"),
                                ( LanguageWindow, "language" ), 
                                ( KeyboardWindow, "keyboard" ),
                                ]

            commonSteps = commonSteps + [
		     ( NetworkWindow, "network" ),
		     ( TimezoneWindow, "timezone" ),
		     ( AccountWindow, "accounts" ),
		     ( AuthWindow, "authentication" ),
		     ( ReconfigCongratulationWindow, "complete" )
		   ]

        else:
            if todo.serial:
                commonSteps = [ ( LanguageWindow, "language" ), 
                                ( WelcomeWindow, "welcome" ),
                                ( InstallPathWindow, "installtype" ),
                                ]
            else:
                commonSteps = [ ( LanguageWindow, "language" ), 
                                ( KeyboardWindow, "keyboard" ),
                                ( MouseWindow, "mouse" ),
                                ( WelcomeWindow, "welcome" ),
                                ( InstallPathWindow, "installtype" ),
                                ]

        self.finishedTODO = Event ()

        from xkb import XKB
        kb = XKB()
        try:
            kb.setMouseKeys (1)
        except SystemError:
            pass
        if todo.instClass.keyboard:
	    info = todo.keyboard.getXKB()
	    if info:
                (rules, model, layout, variant, options) = info
                kb.setRule (model, layout, variant, "complete")
        self.icw = InstallControlWindow (self, commonSteps, todo)
        self.icw.start ()
        self.finishedTODO.wait ()

class InstallControlWindow (Thread):
    def setLanguage (self, lang):
        newlangs = [lang]
        
        if len(lang) > 2:
            newlangs.append(lang[:2])
        self.locale = lang[:2]

        cat.setlangs (newlangs)

        for l in newlangs:
            if os.access ("/etc/gtk/gtkrc." + l, os.R_OK):
                rc_parse("/etc/gtk/gtkrc." + l)

        gtk_set_locale ()
        self.window.reset_rc_styles ()
        # XXX recreate html widget to set new locale
        # there has to be a better way to do this, but I
        # can't find it.  I try html.set_font_charset, but
        # it screws everything up.
        self.box.remove(self.html)
        self.html = GtkXmHTML()
        self.box.add (self.html)
        self.html.show ()
        self.html.source (self.currentScreen.getICS ().getHTML ())

        # get the labels
        for (button, text) in [ (self.nextButtonStock, _("Next")),
                                (self.prevButtonStock, _("Back")),
                                (self.showHelpButton, _("Show Help")),
                                (self.hideHelpButton, _("Hide Help")),
                                (self.finishButton, _("Finish")) ]:
            label = button.children ()[0].children ()[0].children()[1]
            label.set_text (text)
        self.helpFrame.set_label (_("Online Help"))
        self.installFrame.set_label (_("Language Selection"))

    def instantiateWindow (self, windowClass):
        ics = InstallControlState (self, self.ii, self.todo)
        self.buildingWindows = 1
        window = windowClass (ics)
        self.buildingWindows = 0
        self.windowList.append (window)
        return window

    def setStateList (self, list, pos):
        self.stateList = []
	self.stateTagByWindow = {}
        for x in list:
	    if type(x) == type((1,)):
		(x, tag) = x
	    else:
		tag = None
            instantiated = 0
            for y in self.windowList:
                if isinstance (y, x):
                    self.stateList.append (y)
		    self.stateTagByWindow[y] = tag
                    instantiated = 1
                    break
            if not instantiated:
		instance = self.instantiateWindow (x)
                self.stateList.append (instance)
		self.stateTagByWindow[instance] = tag

        self.stateListIndex = pos
        
    def prevClicked (self, *args):
        self.currentScreen.getPrev ()
#          if prev:
#              instantiated = 0
#              for x in self.windowList:
#                  if isinstance (x, prev):
#                      self.currentScreen = x
#                      instantiated = 1
#                      break
#              if not instantiated:
#                  self.currentScreen = self.instantiateWindow (prev)
            
#          else:
#              self.stateListIndex = self.stateListIndex - 1
#              self.currentScreen = self.stateList[self.stateListIndex]

        self.prevList.pop ()
        (self.currentScreen, self.stateListIndex) = self.prevList[-1]
        self.setScreen (self.currentScreen, self.prevClicked)

    def nextClicked (self, *args):
        next = self.currentScreen.getNext ()
        if next:
            instantiated = 0
            for x in self.windowList:
                if isinstance (x, next):
                    self.currentScreen = x
                    instantiated = 1
                    break
            if not instantiated:
                self.currentScreen = self.instantiateWindow (next)
        else:
            self.stateListIndex = self.stateListIndex + 1
            if self.stateListIndex < len (self.stateList):
                self.currentScreen = self.stateList[self.stateListIndex]
            else:
                self.ii.finishedTODO.set ()
                sys.exit (0)
        self.setScreen (self.currentScreen, self.nextClicked)

    def helpClicked (self, widget, simulated = 0):
	if not simulated:
            self.helpState = (widget == self.showHelpButton)
            
        self.hbox.remove (widget)
        if widget == self.hideHelpButton:
            self.bin.remove (self.table)
            self.installFrame.reparent (self.bin)

            self.showHelpButton.show ()
            self.showHelpButton.set_state (STATE_NORMAL)

            self.hbox.pack_start (self.showHelpButton, FALSE)
            self.hbox.reorder_child (self.showHelpButton, 0)
            self.displayHelp = FALSE
        else:
            self.bin.remove (self.installFrame)
            self.table.attach (self.installFrame, 1, 3, 0, 1)
            self.bin.add (self.table)
            # fix to set the bgcolor to white (xmhtml sucks)
            self.html.source ("<HTML><BODY BGCOLOR=white></BODY></HTML>")
            self.html.source (self.currentScreen.getICS ().getHTML ())
            self.hideHelpButton.show ()
            self.showHelpButton.set_state (STATE_NORMAL)
            self.hbox.pack_start (self.hideHelpButton, FALSE)
            self.hbox.reorder_child (self.hideHelpButton, 0)
            self.displayHelp = TRUE

    def setScreen (self, screen, direction):
        # if getScreen returns None, or we're supposed to skip this screen
	# entirely, we continue advancing in direction given
	if (self.stateTagByWindow.has_key(screen) and
	        self.todo.instClass.skipStep(self.stateTagByWindow[screen])):
            direction ()
            return

	new_screen = screen.getScreen ()
	if not new_screen:
            direction ()
            return

        # if we're the initial screen (because of kickstart), make sure we can't go back.
        if not self.initialScreenShown:
            self.initialScreenShown = 1
            screen.getICS ().setPrevEnabled (FALSE)
            self.prevList = []

        if not direction == self.prevClicked:
            self.prevList.append ((screen, self.stateListIndex))

        if self.helpState != self.displayHelp:
            if self.displayHelp:
                self.helpClicked (self.hideHelpButton, 1)
            else:
                self.helpClicked (self.showHelpButton, 1)
        
        self.update (screen.getICS ())

        children = self.installFrame.children ()
        if children:
            child = children[0]
            self.installFrame.remove (child)
            child.destroy ()

        self.installFrame.add (new_screen)
        self.installFrame.show_all ()

    def update (self, ics):
        if self.buildingWindows or ics != self.currentScreen.getICS ():
            return

        self.installFrame.set_label (_(ics.getTitle ()))

        buttons = { "prev" : ics.getPrevButton (),
                    "next" : ics.getNextButton () }

	for (name, button) in buttons.items ():
            if button["pixmap"] == STOCK_BUTTON_PREV and not button["label"]:
                buttons[name] = self.prevButtonStock
            elif button["pixmap"] == STOCK_BUTTON_NEXT and not button["label"]:
                buttons[name] = self.nextButtonStock
            else:
                buttons[name] = GnomePixmapButton (GnomeStock (button["pixmap"]), _(button["label"]))
                if   name == "prev": buttons[name].connect ("clicked", self.prevClicked)
                elif name == "next": buttons[name].connect ("clicked", self.nextClicked)
                buttons[name].show ()

        children = self.buttonBox.children ()
        if not buttons["prev"] in children:
            self.buttonBox.remove (children[0])
            self.buttonBox.pack_start (buttons["prev"])
        if not buttons["next"] in children:
            self.buttonBox.remove (children[1])
            self.buttonBox.pack_end (buttons["next"])

        buttons["prev"].set_sensitive (ics.getPrevEnabled ())
        buttons["next"].set_sensitive (ics.getNextEnabled ())
        self.hideHelpButton.set_sensitive (ics.getHelpButtonEnabled ())
        self.showHelpButton.set_sensitive (ics.getHelpButtonEnabled ())
 
        if ics.getHelpEnabled () == FALSE:
            if self.displayHelp:
                self.helpClicked (self.hideHelpButton, 1)
        elif ics.getHelpEnabled () == TRUE:
            if not self.displayHelp:
                self.helpClicked (self.showHelpButton, 1)
        
        if self.displayHelp:
            self.html.source (ics.getHTML ())

        if (ics.getGrabNext ()):
            buttons["next"].grab_focus ()

    def __init__ (self, ii, steps, todo):
        Thread.__init__ (self)
        self.ii = ii
        self.todo = todo
        self.steps = steps
        if os.environ.has_key ("LC_ALL"):
            self.locale = os.environ["LC_ALL"][:2]
        else:
            self.locale = "C"

    def keyRelease (self, window, event):
        if ((event.keyval == KP_Delete or event.keyval == Delete)
            and (event.state & (CONTROL_MASK | MOD1_MASK))):
            os.kill (os.getpid(), 9)

    def main (self):
        self.window = GtkWindow ()
        self.window.set_events (KEY_RELEASE_MASK)

        self.window.set_default_size (640, 480)
        self.window.set_usize (640, 480)
        cursor = cursor_new (LEFT_PTR)
        _root_window ().set_cursor (cursor)

        self.window.set_border_width (10)

	title = _("Red Hat Linux Installer")
	if os.environ["DISPLAY"][:1] != ':':
	    # from gnome.zvt import *
	    # zvtwin = GtkWindow ()
	    shtitle = _("Red Hat Linux Install Shell")
	    try:
		f = open ("/tmp/netinfo", "r")
	    except:
		pass
	    else:
		lines = f.readlines ()
		f.close ()
		for line in lines:
		    netinf = string.splitfields (line, '=')
		    if netinf[0] == "HOSTNAME":
			title = _("Red Hat Linux Installer on %s") % string.strip (netinf[1])
			shtitle = _("Red Hat Linux Install Shell on %s") % string.strip (netinf[1])
			break

	    # zvtwin.set_title (shtitle)
	    # zvt = ZvtTerm (80, 24)
	    # if zvt.forkpty() == 0:
	    #     os.execv ("/bin/sh", [ "/bin/sh" ])
	    # zvt.show ()
	    # zvtwin.add (zvt)
	    # zvtwin.show_all ()

	self.window.set_title (title)
        self.window.set_position (WIN_POS_CENTER)
        vbox = GtkVBox (FALSE, 10)

        self.buttonBox = GtkHButtonBox ()
        self.buttonBox.set_layout (BUTTONBOX_END)
        self.prevButtonStock = GnomePixmapButton (GnomeStock (STOCK_BUTTON_PREV), _("Back"))
        self.nextButtonStock = GnomePixmapButton (GnomeStock (STOCK_BUTTON_NEXT), _("Next"))
        
        self.finishButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_APPLY), _("Finish"))
	self.hideHelpButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_HELP), _("Hide Help"))
        self.showHelpButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_HELP), _("Show Help"))
        self.hideHelpButton.connect ("clicked", self.helpClicked)
        self.showHelpButton.connect ("clicked", self.helpClicked)
        self.prevButtonStock.connect ("clicked", self.prevClicked)
        self.nextButtonStock.connect ("clicked", self.nextClicked)

        group = GtkAccelGroup()
        self.nextButtonStock.add_accelerator ("clicked", group, F12, RELEASE_MASK, 0);
        self.window.add_accel_group (group)
        self.window.connect ("key-release-event", self.keyRelease)

        self.buttonBox.add (self.prevButtonStock)
        self.buttonBox.add (self.nextButtonStock)

	self.hbox = GtkHBox ()
	self.hbox.pack_start (self.hideHelpButton, FALSE)
	self.hbox.pack_start (self.buttonBox)

        vbox.pack_end (self.hbox, FALSE)

        self.html = GtkXmHTML()
        self.html.set_allow_body_colors(TRUE)
        self.html.source ("<HTML><BODY>HTML Help Window</BODY></HTML>")
        self.displayHelp = TRUE
        self.helpState = TRUE

        self.helpFrame = GtkFrame (_("Online Help"))
        self.box = GtkVBox (FALSE, 0)
        
        self.box.pack_start (GtkHSeparator (), FALSE)
        self.box.pack_start (self.html, TRUE)
        self.helpFrame.add (self.box)

        table = GtkTable (1, 3, TRUE)
        table.attach (self.helpFrame, 0, 1, 0, 1)

        self.installFrame = GtkFrame ()
#        self.installFrame.set_shadow_type (SHADOW_NONE)

        self.windowList = []

        self.setStateList (self.steps, 0)
        self.currentScreen = self.stateList[self.stateListIndex]
        self.initialScreenShown = 0
        self.setScreen (self.currentScreen, self.nextClicked)
                          
        table.attach (self.installFrame, 1, 3, 0, 1)
        table.set_col_spacing (0, 5)

        self.bin = GtkFrame ()
        self.bin.set_shadow_type (SHADOW_NONE)
        self.bin.add (table)
        vbox.pack_end (self.bin, TRUE, TRUE)
        self.table = table

        self.window.add (vbox)
        threads_leave ()

        # let her rip...
	self.mutex = allocate_lock ()
        self.mutex.acquire ()

        # Popup the ICW and wait for it to wake us back up
        threads_enter ()
        self.window.show_all ()
        global splashwindow
        if splashwindow:
            splashwindow.destroy ()
        threads_leave ()

        self.mutex.acquire ()

    def run (self):
        threads_enter ()
        try:
            self.main ()
        except SystemExit:
            pass
        except:
            threads_leave()
            mainquit()
            ExceptionWindow ()
            
class InstallControlState:
    def __init__ (self, cw, ii, todo, title = _("Install Window"),
                  prevEnabled = 1, nextEnabled = 0, html = ""):
        self.searchPath = [ "/usr/share/anaconda/", "./" ]
        self.ii = ii
        self.cw = cw
        self.todo = todo
        self.prevEnabled = prevEnabled
        self.nextEnabled = nextEnabled
        self.helpButtonEnabled = TRUE
        self.title = title
        self.html = html
        self.htmlFile = None
        self.nextButton = STOCK_BUTTON_NEXT
        self.prevButton = STOCK_BUTTON_PREV
        self.nextButtonLabel = None
        self.prevButtonLabel = None
        self.helpEnabled = 3 # Values other than TRUE or FALSE don't change the help setting
        self.grabNext = 0

    def getState (self):
        return (self.title, prevEnabled, nextEnabled, prevText, nextTest)

    def setTitle (self, title):
        self.title = title
        self.cw.update (self)
        
    def getTitle (self):
        return self.title

    def setPrevEnabled (self, value):
        if value == self.prevEnabled: return
        self.prevEnabled = value
        self.cw.update (self)

    def getPrevEnabled (self):
        return self.prevEnabled
    
    def setNextEnabled (self, value):
        if value == self.nextEnabled: return
        self.nextEnabled = value
        self.cw.update (self)

    def getNextEnabled (self):
        return self.nextEnabled

    def setHelpButtonEnabled (self, value):
        if value == self.helpButtonEnabled: return
        self.helpButtonEnabled = value
        self.cw.update (self)

    def getHelpButtonEnabled (self):
        return self.helpButtonEnabled

    def readPixmap (self, file):
        try:
            im = GdkImlib.Image ("/usr/share/anaconda/pixmaps/" + file)
        except:
            try:
                im = GdkImlib.Image ("pixmaps/" + file)
            except:
                print "Unable to load", file
                return None
        return im

    def readHTML (self, file):
        self.htmlFile = file

    def setHTML (self, text):
        self.html = text
        self.cw.update (self)

    def getHTML (self):
        text = None
        if self.htmlFile:
            file = self.htmlFile
            for path in self.searchPath:
                try:
                    text = open("%s/help/%s/s1-help-screens-%s.html" %
                                (path, self.cw.locale, file)).read ()
                except IOError:
                    try:
                        text = open("%s/help/C/s1-help-screens-%s.html" %
                                    (path, file)).read ()
                    except IOError:
                        continue

                if text:
                    break

            if text:
                return text
            else:
                print "Unable to read %s help text" % (file,)

        return self.html
    
    def getToDo (self):
        return self.todo

    def setNextButton (self, button, label=None):
        self.nextButton = button
        self.nextButtonLabel = label

    def getNextButton (self):
        return { "pixmap" : self.nextButton, "label" : self.nextButtonLabel }

    def setPrevButton (self, button, label=None):
        self.prevButton = button
        self.prevButtonLabel = label

    def getPrevButton (self):
        return { "pixmap" : self.prevButton, "label" : self.prevButtonLabel }

    def setScreenPrev (self):
        self.cw.prevClicked ()

    def setScreenNext (self):
        self.cw.nextClicked ()

    def getInstallInterface (self):
        return self.ii

    def setHelpEnabled (self, value):
        self.helpEnabled = value
        self.cw.update (self)

    def getHelpEnabled (self):
        return self.helpEnabled

    def setGrabNext (self, value):
        self.grabNext = value
        self.cw.update (self)

    def getGrabNext (self):
        return self.grabNext

    def getICW (self):
        return self.cw
