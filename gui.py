import gettext

cat = gettext.Catalog ("anaconda", "/usr/share/locale")

def _(string):
    return cat.gettext(string)

def setLanguage (lang):
    global cat
    newlangs = [lang]
    if len(lang) > 2:
        newlangs.append(lang[:2])
    gettext.setlangs (newlangs)
    cat = gettext.Catalog ("anaconda", "/usr/share/locale")

from gtk import *
from gtk import _root_window
from GDK import *
from gnome.ui import *
from gnome.xmhtml import *
from iw.language import *
from iw.welcome import *
from iw.progress import *
from iw.package import *
from iw.network import *
from iw.account import *
from iw.rootpartition import *
from iw.auth import *
from iw.mouse import *
from iw.keyboard import *
from iw.format import *
from iw.congrats import *
from iw.dependencies import *
from iw.lilo import *
from iw.installpath import *

import sys
import GdkImlib

import isys
import sys

import thread
import rpm
from thread import *
from threading import *
import time

class WaitWindow:
    def __init__(self, title, text):
	threads_enter ()
        self.window = GtkWindow (WINDOW_POPUP)
        self.window.set_title (title)
        self.window.set_position (WIN_POS_CENTER)
        self.window.set_modal (TRUE)
        label = GtkLabel (text)
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
	gdk_flush ()
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
        self.window.set_title (title)
        self.window.set_position (WIN_POS_CENTER)
        self.window.set_modal (TRUE)
        box = GtkVBox (5)
        box.set_border_width (10)

        label = GtkLabel (text)
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
	gdk_flush ()
        threads_leave ()

    def set (self, amount):
        threads_enter ()
	self.progress.update (float (amount) / self.total)
        threads_leave ()
    
    def pop(self):
	threads_enter ()
        self.window.destroy ()
	threads_leave ()

class GtkMainThread (Thread):
    def run (self):
        self.setName ("gtk_main")
        threads_enter ()
        mainloop ()
        threads_leave ()

class MessageWindow:
    def quit (self, *args):
        if self.quitmain:
            mainquit ()
        else:
            self.window.destroy ()
            self.mutex.set ()
    
    def __init__ (self, title, text):
        threads_enter ()
        self.window = GtkWindow (WINDOW_POPUP)
        self.window.set_title (title)
        self.window.set_position (WIN_POS_CENTER)
        self.window.set_modal (TRUE)
        box = GtkVBox (5, FALSE)
        box.set_border_width (10)

        label = GtkLabel (text)
        label.set_line_wrap (TRUE)
        label.set_alignment (0.0, 0.5)
        box.pack_start (label)

        bb = GtkHButtonBox ()
        ok = GnomeStockButton (STOCK_BUTTON_OK)
        bb.pack_start (ok)
        box.pack_end (bb, FALSE, TRUE)
        ok.connect ("clicked", self.quit)

        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_OUT)
        frame.add (box)
        self.window.add (frame)
        self.window.show_all ()
        gdk_flush ()
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
            self.quitmain = 1
            threads_enter ()
            mainloop ()
            threads_leave ()
        else:
            self.quitmain = 0
            self.mutex = Event ()
            self.mutex.wait ()
    
class InstallInterface:
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
	commonSteps = [ ( LanguageWindow, "language" ), 
			( KeyboardWindow, "keyboard" ),
			( MouseWindow, "mouse" ),
			( WelcomeWindow, "welcome" ),
			( InstallPathWindow, "installtype" ),
		      ]

        self.finishedTODO = Event ()
        self.icw = InstallControlWindow (self, commonSteps, todo)
        self.icw.start ()
        self.finishedTODO.wait ()

class InstallControlWindow (Thread):

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
#          prev = self.currentScreen.getPrev ()
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

        self.installFrame.set_label (ics.getTitle ())

        buttons = { "prev" : ics.getPrevButton (),
                    "next" : ics.getNextButton () }

	for (name, button) in buttons.items ():
            if button["pixmap"] == STOCK_BUTTON_PREV and not button["label"]:
                buttons[name] = self.prevButtonStock
            elif button["pixmap"] == STOCK_BUTTON_NEXT and not button["label"]:
                buttons[name] = self.nextButtonStock
            else:
                buttons[name] = GnomePixmapButton (GnomeStock (button["pixmap"]), button["label"])
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
 
        if ics.getHelpEnabled () == FALSE:
            if self.displayHelp:
                self.helpClicked (self.hideHelpButton, 1)
        elif ics.getHelpEnabled () == TRUE:
            if not self.displayHelp:
                self.helpClicked (self.showHelpButton, 1)
        
        if self.displayHelp:
            self.html.source (ics.getHTML ())

    def __init__ (self, ii, steps, todo):
        Thread.__init__ (self)
        self.ii = ii
        self.todo = todo
        self.steps = steps

    def run (self):
        threads_enter ()
        self.window = GtkWindow ()

        self.window.set_default_size (640, 480)
        self.window.set_usize (640, 480)
        cursor = cursor_new (LEFT_PTR)
        _root_window ().set_cursor (cursor)

        self.window.set_border_width (10)
        self.window.set_title (_("Red Hat Linux Installer"))
        self.window.set_position (WIN_POS_CENTER)
        vbox = GtkVBox (FALSE, 10)

        self.buttonBox = GtkHButtonBox ()
        self.buttonBox.set_layout (BUTTONBOX_END)
        self.prevButtonStock = GnomePixmapButton (GnomeStock (STOCK_BUTTON_PREV), _("Back"))
        self.nextButtonStock = GnomeStockButton (STOCK_BUTTON_NEXT)
        
        self.finishButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_APPLY), _("Finish"))
	self.hideHelpButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_HELP), _("Hide Help"))
        self.showHelpButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_HELP), _("Show Help"))
        self.hideHelpButton.connect ("clicked", self.helpClicked)
        self.showHelpButton.connect ("clicked", self.helpClicked)
        self.prevButtonStock.connect ("clicked", self.prevClicked)
        self.nextButtonStock.connect ("clicked", self.nextClicked)

        self.buttonBox.add (self.prevButtonStock)
        self.buttonBox.add (self.nextButtonStock)

	self.hbox = GtkHBox ()
	self.hbox.pack_start (self.hideHelpButton, FALSE)
	self.hbox.pack_start (self.buttonBox)

        vbox.pack_end (self.hbox, FALSE)

        self.html = GtkXmHTML()
#        html.set_dithering(FALSE)  # this forces creation of CC
        self.html.set_allow_body_colors(TRUE)
        self.html.source ("<HTML><BODY>HTML Help Window</BODY></HTML>")
        self.displayHelp = TRUE
        self.helpState = TRUE

        self.helpFrame = GtkFrame (_("Online Help"))
        box = GtkVBox (FALSE, 0)
        
        box.pack_start (GtkHSeparator (), FALSE)
        box.pack_start (self.html, TRUE)
        self.helpFrame.add (box)

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
        threads_leave ()

        self.mutex.acquire ()
        

class InstallControlState:
    def __init__ (self, cw, ii, todo, title = "Install Window",
                  prevEnabled = 1, nextEnabled = 0, html = ""):
        self.searchPath = [ "/usr/share/anaconda/", "./" ]
        self.locale = 'C'
        self.ii = ii
        self.cw = cw
        self.todo = todo
        self.prevEnabled = prevEnabled
        self.nextEnabled = nextEnabled
        self.title = title
        self.html = html
        self.nextButton = STOCK_BUTTON_NEXT
        self.prevButton = STOCK_BUTTON_PREV
        self.nextButtonLabel = None
        self.prevButtonLabel = None
        self.helpEnabled = 3 # Values other than TRUE or FALSE don't change the help setting

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
        if (self.prevEnabled != 0):
            return TRUE
        return FALSE
    
    def setNextEnabled (self, value):
        if value == self.nextEnabled: return
        self.nextEnabled = value
        self.cw.update (self)

    def getNextEnabled (self):
        if (self.nextEnabled != 0):
            return TRUE
        return FALSE

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
        text = None
        for path in self.searchPath:
            try:
                text = open("%s/help/%s/s1-help-screens-%s.html" %
                            (path, self.locale, file)).read ()
            except IOError:
                try:
                    text = open("%s/help/C/s1-help-screens-%s.html" %
                                (path, file)).read ()
                except IOError:
                    continue
                
            if text:
                break

        if text:
            self.html = text
            self.cw.update (self)
        else:
            print "Unable to read %s help text" % (file,)

    def setHTML (self, text):
        self.html = text
        self.cw.update (self)

    def getHTML (self):
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

    def getICW (self):
        return self.cw
