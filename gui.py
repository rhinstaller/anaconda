from gtk import *
from gnome.ui import *
from gnome.xmhtml import *
from iw.language import *
from iw.welcome import *
from iw.progress import *
from iw.package import *
from iw.network import *
import sys
import GdkImlib

import isys
import sys
import _balkan
import thread
import rpm
from thread import *
from threading import *
import time

class NetworkConfigWindow:
    def __init__ (self, ics):
        self.ics = ics
        ics.setTitle ("Network Configuration")

    def getScreen (self):
        devices = ["Ethernet Device 0 (eth0)",
                   "Ethernet Device 1 (eth1)",
                   "Ethernet Device 2 (eth2)"]
        vbox = GtkVBox (FALSE, 10)
        optionmenu = GtkOptionMenu ()
        menu = GtkMenu ()
        for i in devices:
            menuitem = GtkMenuItem (i)
            menu.append (menuitem)

        optionmenu.set_menu (menu)

        hbox = GtkHBox (FALSE, 10)
        devLabel = GtkLabel ("Device: ")
        hbox.pack_start (devLabel, FALSE)
        hbox.pack_start (optionmenu, TRUE)
        vbox.pack_start (hbox, FALSE, padding=10)
        return vbox

class PartitionWindow:
    def back(self, win):
        self.rc = -1
	mainquit()

    def next(self, win):
	self.rc = 0
        mainquit()

    def __init__(self):
        self.rc = 0

    def run(self, todo):
	if (not todo.setupFilesystems): return -2

        window = GtkWindow()
        window.set_border_width(10)
        window.set_title("Choose a partition")

        label = GtkLabel("What partition would you like to use for your root "
                         "partition?")
        label.set_line_wrap (TRUE)

        hbox = GtkHBox (FALSE, 10)

        device = 'hda'

        buttons = {}
        buttons[0] = None;
	numext2 = 0

        try:
    	    isys.makeDevInode(device, '/tmp/' + device)
            table = _balkan.readTable('/tmp/' + device)
    	    if len(table) - 1 > 0:
        	partbox = GtkVBox (FALSE, 5)
                for i in range(0, len(table) - 1):
                    (type, start, size) = table[i]
                    if (type == 0x83 and size):
                        buttons[numext2] = GtkRadioButton(buttons[0],
                                        '/dev/%s%d' % (device, i + 1))
                        partbox.pack_start(buttons[numext2], FALSE, FALSE, 0)
                        numext2 = numext2 + 1
            hbox.pack_start(partbox, FALSE, FALSE, 0)
            hbox.pack_start(label, FALSE, FALSE, 0)
        except:
            label = GtkLabel("Unable to read partition information")
            hbox.pack_start(label, TRUE, TRUE, 0)
            print "unable to read partitions"
 
        buttonbox = GtkHButtonBox()
        buttonbox.set_spacing(5)
        buttonbox.set_layout(BUTTONBOX_END)
        button = GtkButton("<- Back")
        button.connect("clicked", self.back)
        buttonbox.add(button)
        button = GtkButton("Next ->")
        button.connect("clicked", self.next)
        buttonbox.add(button)

        vbox = GtkVBox (FALSE, 10)
        vbox.pack_start(hbox, TRUE, TRUE, 0)
        vbox.pack_start(buttonbox, FALSE, FALSE, 0)

        window.add(vbox)
        window.set_position(WIN_POS_CENTER)
        window.show_all()

        sleep (20);


	rootpart = ""
        for i in range(0, numext2):
            if buttons[i].active:
                rootpart = "%s%d" % (device, i + 1)

	todo.addMount(rootpart, '/')

        window.destroy()

        return self.rc

class WaitWindow:
    def __init__(self, title, text):
	threads_enter ()
        self.window = GtkWindow ()
        self.window.set_border_width (10)
        self.window.set_title (title)
        self.window.set_position (WIN_POS_CENTER)
        self.window.set_modal (TRUE)
        label = GtkLabel (text)
        label.set_line_wrap (TRUE)
	self.window.add (label)
	self.window.show_all ()
	gdk_flush ()
	while events_pending ():
            mainiteration ()
        threads_leave ()
            
    def pop(self):
	threads_enter ()
        self.window.destroy ()
	threads_leave ()

class GtkMainThread:
    def run (self):
        threads_enter ()
        mainloop ()
        threads_leave ()
    
class InstallInterface:

    def setPackageProgressWindow (self, ppw):
        self.ppw = ppw
        self.mutex.release ()
        
    def waitWindow (self, title, text):
	return WaitWindow (title, text)

    def packageProgressWindow (self, total, totalSize):
        self.ppw.setSizes (total, totalSize)
        return self.ppw

    def exceptionWindow(self, (type, value, tb)):
        import traceback
        traceback.print_exception (type, value, tb)

    def run (self, todo):
        sys.setcheckinterval (0)
        start_new_thread (GtkMainThread ().run, ())
        
        steps = [
            ["Welcome", WelcomeWindow, ()],
            ["Partition", PartitionWindow, (todo,)]
        ]

        steps = [WelcomeWindow, LanguageWindow, NetworkWindow,
                 PackageSelectionWindow, InstallProgressWindow]

        windows = [WelcomeWindow, LanguageWindow, NetworkWindow,
                   PackageSelectionWindow, IndividualPackageSelectionWindow,
                   InstallProgressWindow]
                 
        icw = InstallControlWindow (self, steps, windows, todo)
	
	self.mutex = allocate_lock ()
	self.mutex.acquire ()
	start_new_thread (icw.run, ())
	self.mutex.acquire ()

	todo.setLiloLocation("hda")


class InstallControlWindow:

    def prevClicked (self, widget, *args):
        prev = self.currentScreen.getPrev ()
        if prev:
            for x in self.windowList:
                if isinstance (x, prev):
                    self.currentScreen = x
                    break
        else:
            self.stateListIndex = self.stateListIndex - 1
            self.currentScreen = self.stateList[self.stateListIndex]
        self.setScreen (self.currentScreen)

    def nextClicked (self, widget, *args):
        next = self.currentScreen.getNext ()
        if next:
            for x in self.windowList:
                if isinstance (x, next):
                    self.currentScreen = x
                    break
        else:
            self.stateListIndex = self.stateListIndex + 1
            self.currentScreen = self.stateList[self.stateListIndex]
        self.setScreen (self.currentScreen)

    def helpClicked (self, widget, *args):
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

            self.hideHelpButton.show ()
            self.showHelpButton.set_state (STATE_NORMAL)
            self.hbox.pack_start (self.hideHelpButton, FALSE)
            self.hbox.reorder_child (self.hideHelpButton, 0)
            self.displayHelp = TRUE

    def setScreen (self, screen):
#        if screen == len (self.stateList):
#            self.mutex.release ()
#            return

        self.update (screen.getICS ())

        child = self.installFrame.children ()[0]
        self.installFrame.remove (child)
        child.destroy ()
        
        self.installFrame.add (screen.getScreen ())
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
                buttons[name] = GnomePixmapButton (GnomeStock (button["pixmap"], button["label"]))
                if   name == "prev": buttons[name].connect ("clicked", self.prevClicked)
                elif name == "next": buttons[name].connect ("clicked", self.nextClicked)
                buttons[name].show ()

        self.buttonBox.foreach (lambda x, b=self.buttonBox: b.remove (x))
        self.buttonBox.pack_start (buttons["prev"])
        self.buttonBox.pack_start (buttons["next"])
        buttons["prev"].set_sensitive (ics.getPrevEnabled ())
        buttons["next"].set_sensitive (ics.getNextEnabled ())

        if ics.getHelpEnabled () == FALSE:
            if self.displayHelp:
                self.helpClicked (self.hideHelpButton)
        elif ics.getHelpEnabled () == TRUE:
            if not self.displayHelp:
                self.helpClicked (self.showHelpButton)
        
        if self.displayHelp:
            self.html.source (ics.getHTML ())

    def __init__ (self, ii, steps, windows, todo):
        self.ii = ii
        self.steps = steps

        threads_enter ()
        self.window = GtkWindow ()
        self.window.set_border_width (10)
        self.window.set_title ("Install Control Window")
        self.window.set_position (WIN_POS_CENTER)
        self.window.set_default_size (640, 480)
        vbox = GtkVBox (FALSE, 10)

        self.buttonBox = GtkHButtonBox ()
        self.buttonBox.set_layout (BUTTONBOX_END)
        self.prevButtonStock = GnomeStockButton (STOCK_BUTTON_PREV)
        self.nextButtonStock = GnomeStockButton (STOCK_BUTTON_NEXT)
        
        self.finishButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_APPLY), "Finish")
	self.hideHelpButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_HELP), "Hide Help")
        self.showHelpButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_HELP), "Show Help")
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

        self.helpFrame = GtkFrame ("Help Window")
        self.helpFrame.add (self.html)

        table = GtkTable (1, 3, TRUE)
        table.attach (self.helpFrame, 0, 1, 0, 1)

        self.installFrame = GtkFrame ()

        self.stateList = []
        self.windowList = []

        self.buildingWindows = 1
        for x in windows:
            ics = InstallControlState (self, ii, todo)
            window = x (ics)
            if x in steps: self.stateList.append (window)
            self.windowList.append (window)
        self.buildingWindows = 0

        self.stateListIndex = 0
        self.currentScreen = self.stateList[self.stateListIndex]
        self.update (self.currentScreen.getICS ())
        self.installFrame.add (self.currentScreen.getScreen ())
                          
        table.attach (self.installFrame, 1, 3, 0, 1)
        table.set_col_spacing (0, 15)

        self.bin = GtkFrame ()
        self.bin.set_shadow_type (SHADOW_NONE)
        self.bin.add (table)
        vbox.pack_end (self.bin, TRUE, TRUE)
        self.table = table

        self.window.add (vbox)
        threads_leave ()

    def run (self):
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
        self.prevEnabled = value
        self.cw.update (self)

    def getPrevEnabled (self):
        if (self.prevEnabled != 0):
            return TRUE
        return FALSE
    
    def setNextEnabled (self, value):
        self.nextEnabled = value
        self.cw.update (self)

    def getNextEnabled (self):
        if (self.nextEnabled != 0):
            return TRUE
        return FALSE

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
