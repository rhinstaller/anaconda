from gtk import *
from gnome.ui import *
from gnome.xmhtml import *
import GdkImlib

import isys
import sys
import _balkan
import thread
import rpm
from thread import *
from threading import *
import time

class LanguageWindow:
    def __init__ (self, ics):
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
        label.set_alignment (1.0, 1.0)
        
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

class NetworkConfigWindow:
    def __init__ (self, ics):
        self.ics = ics
        ics.setTitle ("Network Configuration")

    def getScreen (self):
        devices = ["eth0", "eth1", "eth2" ]
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

class PackageSelectionWindow:
    def __init__ (self, ics):
        self.ics = ics
        self.todo = ics.getToDo ()
        ics.setTitle ("Package Group Selection")
        ics.setNextEnabled (1)
        ics.setHTML ("<HTML><BODY>Next you must select which package groups to install."
                     "</BODY></HTML>")

    def getScreen (self):
        threads_leave ()
        self.todo.headerList ()
        self.todo.compsList()
	threads_enter ()

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        box = GtkVBox (FALSE, 10)
        for comp in self.todo.comps:
            if not comp.hidden:
                checkButton = GtkCheckButton (comp.name)
                checkButton.set_active (comp.selected)

                def toggled (widget, comp):
                  if widget.get_active ():
                    comp.select (0)
                  else:
                    comp.unselect (0)
                    
                checkButton.connect ("toggled", toggled, comp)

                box.pack_start (checkButton)

        sw.add_with_viewport (box)

        vbox = GtkVBox (FALSE, 5)
        indivPackages = GtkCheckButton ("Select individual packages")
        indivPackages.set_active (FALSE)
        align = GtkAlignment (0.5, 0.5)
        align.add (indivPackages)

        vbox.pack_start (sw, TRUE)
        vbox.pack_start (align, FALSE)
        
        return vbox

class WelcomeWindow:		
    def __init__ (self, ics):
        ics.setTitle ("Welcome to Red Hat Linux!")
        ics.setPrevEnabled (0)
        ics.setNextEnabled (1)
        ics.setHTML("<HTML><BODY><CENTER><H2>Welcome to<br>Red Hat Linux!</H2></CENTER><br><br>"
	    "This installation process is outlined in detail in the "
    	    "Official Red Hat Linux Installation Guide available from "
	    "Red Hat Software. If you have access to this manual, you "
	    "should read the installation section before continuing.<br><br>"
	    "If you have purchased Official Red Hat Linux, be sure to "
	    "register your purchase through our web site, "
	    "http://www.redhat.com/.</BODY></HTML>")

    def getScreen (self):
        label = GtkLabel("(insert neat logo graphic here)")
        label.set_line_wrap (TRUE)

        box = GtkVBox (FALSE, 10)
        box.pack_start (label, TRUE, TRUE, 0)

        try:
            im = GdkImlib.Image ("shadowman-200.png")
            im.render ()
            pix = im.make_pixmap ()
            box.pack_start (pix, TRUE, TRUE, 0)

        except:
            print "Unable to load shadowman-200.png"

        return box

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


class InstallProgressWindow:
    def setPackageScale (self, amount, total):
        threads_enter ()
	self.progress.update (float (amount) / total)
        threads_leave ()

    def completePackage(self, header):
	pass

    def setPackage(self, header):
        threads_enter ()
        self.name.set_text (header[rpm.RPMTAG_NAME])
        self.size.set_text ("%d k" % (header[rpm.RPMTAG_SIZE] / 1024))
        self.summary.set_text (header[rpm.RPMTAG_SUMMARY])
        threads_leave ()

    def __del__(self):
        threads_enter ()
        self.window.destroy()
        threads_leave ()

    def setSizes (self, total, totalSize):
        self.total = total
        self.totalSize = totalSize

    def __init__ (self, ics):
        ics.setTitle ("Installing Packages")
        ics.setPrevEnabled (0)

    def getScreen (self):
	table = GtkTable()
	# x1, x2, y1, y2
	label = GtkLabel("Package Name:")
	label.set_alignment(1.0, 0.0)
	table.attach(label, 0, 1, 0, 1)
        label = GtkLabel("Package Size:")
	label.set_alignment(1.0, 0.0)
	table.attach(label, 0, 1, 1, 2)
        label = GtkLabel("Package Summary:")
	label.set_alignment(1.0, 0.0)
	table.attach(label, 0, 1, 2, 3, yoptions = FILL)

	self.name = GtkLabel();
	self.name.set_alignment(0, 0.0)
	self.size = GtkLabel();
	self.size.set_alignment(0, 0.0)
	self.summary = GtkLabel();
	self.summary.set_alignment(0, 0.0)
        self.summary.set_line_wrap (TRUE)
	table.attach(self.name, 1, 2, 0, 1, xoptions = FILL | EXPAND)
	table.attach(self.size, 1, 2, 1, 2, xoptions = FILL | EXPAND)
	table.attach(self.summary, 1, 2, 2, 3, xoptions = FILL | EXPAND)

	self.progress = GtkProgressBar()
	table.attach(self.progress, 0, 2, 3, 4)

	return table

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

    def filledToDo (self):
        self.mutex.release ()
        
    def waitWindow (self, title, text):
	return WaitWindow (title, text)

    def packageProgressWindow (self, total, totalSize):
	return InstallProgressWindow (total, totalSize)

    def run (self, todo):
        start_new_thread (GtkMainThread ().run, ())
        
        steps = [
            ["Welcome", WelcomeWindow, ()],
            ["Partition", PartitionWindow, (todo,)]
        ]

        steps = [WelcomeWindow, LanguageWindow, PackageSelectionWindow]
                 
        icw = InstallControlWindow (steps, todo)
	
	self.mutex = allocate_lock ()
	self.mutex.acquire ()
	start_new_thread (icw.run, ())
	self.mutex.acquire ()

	todo.liloLocation("hda")


class InstallControlWindow:

    def prevClicked (self, *args):
        self.setScreen (self.currentScreen - 1)

    def nextClicked (self, *args):
        self.setScreen (self.currentScreen + 1)

    def setScreen (self, screen):
        if screen == len (self.stateList):
            self.mutex.release ()
            return
        
        self.currentScreen = screen
        newScreen = self.stateList[self.currentScreen][0].getScreen ()
        self.update (self.stateList[self.currentScreen][1])

        child = self.installFrame.children ()[0]
        self.installFrame.remove (child)
        child.destroy ()
        
        self.installFrame.add (newScreen)
        self.installFrame.show_all ()

    def update (self, ics):
        if self.buildingWindows or ics != self.stateList[self.currentScreen][1]:
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
            buttons[name].set_state (STATE_NORMAL)
            buttons[name].show ()

        self.buttonBox.foreach (lambda x, b=self.buttonBox: b.remove (x))
        self.buttonBox.pack_start (buttons["prev"])
        self.buttonBox.pack_start (buttons["next"])
        buttons["prev"].set_sensitive (ics.getPrevEnabled ())
        buttons["next"].set_sensitive (ics.getNextEnabled ())
        self.html.source (ics.getHTML ())

    def __init__ (self, steps, todo):
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
        
        self.finishButton = GnomePixmapButton (GnomeStock (STOCK_BUTTON_APPLY),
                                               "Finish")
        self.prevButtonStock.connect ("clicked", self.prevClicked)
        self.nextButtonStock.connect ("clicked", self.nextClicked)

        self.buttonBox.add (self.prevButtonStock)
        self.buttonBox.add (self.nextButtonStock)

        vbox.pack_end (self.buttonBox, FALSE)

        self.html = GtkXmHTML()
#        html.set_dithering(FALSE)  # this forces creation of CC
        self.html.set_allow_body_colors(TRUE)
        self.html.source ("<HTML><BODY>HTML Help Window</BODY></HTML>")

        helpFrame = GtkFrame ("Help Window")
        helpFrame.add (self.html)

        table = GtkTable (1, 3, TRUE)
        table.attach (helpFrame, 0, 1, 0, 1)

        self.installFrame = GtkFrame ()

	self.currentScreen = 0
        self.stateList = []

        self.buildingWindows = 1
        for x in steps:
            ics = InstallControlState (self, todo)
            self.stateList.append ((x (ics), ics))
        self.buildingWindows = 0

        currentScreen = self.stateList[self.currentScreen][0].getScreen ()
        self.update (self.stateList[self.currentScreen][1])
        self.installFrame.add (currentScreen)
                          
        table.attach (self.installFrame, 1, 3, 0, 1)
        table.set_col_spacing (0, 15)

        vbox.pack_end (table, TRUE, TRUE)

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

    def __init__ (self, cw, todo, title = "Install Window",
                  prevEnabled = 1, nextEnabled = 0, html = ""):
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


