#
# gui.py - Graphical front end for anaconda
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
os.environ["PYGTK_FATAL_EXCEPTIONS"] = "1"
os.environ["GNOME_DISABLE_CRASH_DIALOG"] = "1"
# msw says this is a good idea
os.environ["LC_ALL"] = "C"

import GDK
import GdkImlib
import iutil
import string
import isys
import sys
import parted
from translate import cat, _, N_
from gnome.ui import *
from gnome.xmhtml import *
from gtk import *
from _gtk import gtk_set_locale, gtk_rc_init, gtk_rc_reparse_all
from _gtk import _gtk_nuke_rc_files, _gtk_nuke_rc_mtimes
from language import expandLangs
from splashscreen import splashScreenPop
from log import log

StayOnScreen = "stayOnScreen"

stepToClass = {
    "language" : ( "language_gui", "LanguageWindow" ),
    "keyboard" : ( "keyboard_gui", "KeyboardWindow" ),
    "mouse" : ( "mouse_gui", "MouseWindow" ),
    "welcome" : ("welcome_gui", "WelcomeWindow" ),
    "installtype" : ( "installpath_gui", "InstallPathWindow" ),
    "partitionmethod" : ( "partmethod_gui", "PartitionMethodWindow" ),
    "partition" : ( "partition_gui", "PartitionWindow" ),
    "autopartition" : ("partition_gui", "AutoPartitionWindow" ),
    "findinstall" : ( "examine_gui", "UpgradeExamineWindow" ),
    "addswap" : ( "upgrade_swap_gui", "UpgradeSwapWindow" ),
    "fdisk" : ( "fdisk_gui", "FDiskWindow" ),
    "format" : ( "format_gui", "FormatWindow" ),
    "bootloader": ("lilo_gui", "LiloWindow" ), 
    "network" : ( "network_gui", "NetworkWindow" ),
    "firewall" : ( "firewall_gui", "FirewallWindow" ),
    "languagesupport" : ( "language_support_gui", "LanguageSupportWindow" ),
    "timezone" : ( "timezone_gui", "TimezoneWindow" ),
    "accounts" : ( "account_gui", "AccountWindow" ),
    "authentication" : ( "auth_gui", "AuthWindow" ),
    "package-selection" : ( "package_gui", "PackageSelectionWindow" ),
    "indivpackage" : ( "package_gui", "IndividualPackageSelectionWindow" ),
    "dependencies" : ( "dependencies_gui", "UnresolvedDependenciesWindow" ),
    "videocard" : ( "xconfig_gui", "XConfigWindow" ),
    "monitor" : ( "xconfig_gui", "MonitorWindow" ),
    "xcustom" : ( "xconfig_gui", "XCustomWindow" ),
    "confirminstall" : ( "confirm_gui", "InstallConfirmWindow" ),
    "confirmupgrade" : ( "confirm_gui", "UpgradeConfirmWindow" ),
    "finishxconfig" : None,
    "install" : ( "progress_gui", "InstallProgressWindow" ),
    "bootdisk" : ( "bootdisk_gui", "BootdiskWindow" ),
    "complete" : ( "congrats_gui", "CongratulationWindow" )
}

if iutil.getArch() == 'sparc':
    stepToClass["bootloader"] = ( "silo_gui", "SiloWindow" )
else:
    stepToClass["bootloader"] = ( "lilo_gui", "LiloWindow" )

# setup globals

def processEvents():
    gdk_flush()
    while events_pending ():
        mainiteration (FALSE)

def partedExceptionWindow(exc):
    print exc.type_string
    print exc.message
    print exc.options
    win = GnomeDialog (exc.type_string)
    win.vbox.pack_start (GtkLabel(exc.message))
    numButtons = 0
    buttonToAction = {}
    
    flags = ((parted.EXCEPTION_YES, N_("Yes")),
             (parted.EXCEPTION_NO, N_("No")),
             (parted.EXCEPTION_OK, N_("Ok")),
             (parted.EXCEPTION_RETRY, N_("Retry")),
             (parted.EXCEPTION_IGNORE, N_("Ignore")),
             (parted.EXCEPTION_CANCEL, N_("Cancel")))
    for flag, string in flags:
        if exc.options & flag:
            win.append_button (_(string))
            buttonToAction[numButtons] = flag
            numButtons = numButtons + 1
    win.show_all()
    rc = win.run()
    print rc, buttonToAction
    return buttonToAction[rc]

class WaitWindow:
    def __init__(self, title, text):
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
        processEvents ()
            
    def pop(self):
        self.window.destroy ()

class ProgressWindow:
    def __init__(self, title, text, total):
        self.window = GtkWindow (WINDOW_POPUP)
        self.window.set_title (_(title))
        self.window.set_position (WIN_POS_CENTER)
        self.window.set_modal (TRUE)
        box = GtkVBox (FALSE, 5)
        box.set_border_width (10)

        label = GtkLabel (_(text))
        label.set_line_wrap (TRUE)
        label.set_alignment (0.0, 0.5)
        box.pack_start (label, FALSE)
        
        self.total = total
	self.progress = GtkProgressBar ()
        box.pack_start (self.progress, TRUE)
        
        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_OUT)
        frame.add (box)
	self.window.add (frame)
	self.window.show_all ()
        processEvents ()

    def set (self, amount):
	self.progress.update (float (amount) / self.total)
        processEvents ()        
    
    def pop(self):
        self.window.destroy ()

class ExceptionWindow:
    def __init__ (self, text):
        win = GnomeDialog ("Exception Occured")
        win.connect ("clicked", self.quit)
        win.append_button ("Debug")
        win.append_button ("Save to floppy")
        win.append_button_with_pixmap ("OK", STOCK_BUTTON_OK)
        textbox = GtkText()
        textbox.insert_defaults (text)
        sw = GtkScrolledWindow ()
        sw.add (textbox)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        hbox = GtkHBox (FALSE)
        # XXX fix me, use util function when we upgrade pygnome
        # s = unconditional_pixmap_file ("gnome-error.png")
        # use this for now
        s = None
        if s:
            hbox.pack_start (GnomePixmap ('/usr/share/pixmaps/gnome-warning.png'),
                             FALSE)

        info = GtkLabel (_("An exceptional condition has occured.  This "
                           "is most likely a bug.  Please copy the "
                           "full text of this exception and file a bug "
                           "report against anaconda at "
                           "http://bugzilla.redhat.com/bugzilla"))
        info.set_line_wrap (TRUE)
        info.set_usize (400, -1)

        hbox.pack_start (sw, TRUE)
        win.vbox.pack_start (info, FALSE)            
        win.vbox.pack_start (hbox, TRUE)
        win.set_usize (500, 300)
        win.set_position (WIN_POS_CENTER)
        win.show_all ()
        self.window = win
        self.rc = self.window.run ()
        
    def quit (self, dialog, button):
        self.rc = button

    def getrc (self):
        # I did it this way for future expantion
        # 0 is debug
        if self.rc == 0:
            try:
                # switch to VC1 so we can debug
                isys.vtActivate (1)
            except SystemError:
                pass
            return 1
        # 1 is save
        if self.rc == 1:
            return 2
        # 2 is OK
        elif self.rc == 2:
            return 0

class MessageWindow:
    def quit (self, dialog, button=None):
        if button != None:
            self.rc = button

    def okcancelquit (self, button):
        self.rc = button

    def questionquit (self, button):
        self.rc = button

    def getrc (self):
        return self.rc
    
    def __init__ (self, title, text, type = "ok"):
        self.rc = None
        if type == "ok":
            self.window = GnomeOkDialog (_(text))
            self.window.connect ("clicked", self.quit)
            self.window.connect ("close", self.quit)
        if type == "okcancel":
            self.window = GnomeOkCancelDialog (_(text), self.okcancelquit)
        if type == "yesno":
            self.window = GnomeQuestionDialog (_(text), self.questionquit)

        # this is the pixmap + the label
        hbox = self.window.vbox.children ()[0]
        label = hbox.children ()[1]
        label.set_line_wrap (TRUE)
        self.window.set_position (WIN_POS_CENTER)
        win = self.window.get_window()
        win.keyboard_grab(0)
        self.window.show_all ()
        self.rc = self.window.run ()
        win.keyboard_ungrab()
    
class InstallInterface:
    def __init__ (self, runres, nofbmode):
        self.runres = runres
        self.nofbmode = nofbmode

    def __del__ (self):
        pass

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

    def messageWindow(self, title, text, type = "ok"):
        return MessageWindow (title, text, type)

    def exceptionWindow(self, title, text):
        print text
        win = ExceptionWindow (text)
        return win.getrc ()

    def dumpWindow(self):
        window = MessageWindow("Save Crash Dump", 
                               _("Please insert a floppy now. All contents "
                                 "of the disk will be erased, so please "
                                 "choose your diskette carefully."),
                               "okcancel")
        rc = window.getrc()
	return rc

    def getBootdisk (self):
        return None

    def run(self, id, dispatch):
        from xkb import XKB
        kb = XKB()

	self.dispatch = dispatch

	# XXX
        #if todo.installSystem:
            #try:
                #kb.setMouseKeys (1)
            #except SystemError:
                #pass
        #if todo.instClass.keyboard:
	    #info = todo.keyboard.getXKB()
	    #if info:
                #(rules, model, layout, variant, options) = info
                #kb.setRule (model, layout, variant, "complete")

        id.fsset.registerMessageWindow(self.messageWindow)
        id.fsset.registerProgressWindow(self.progressWindow)
        parted.exception_set_handler(partedExceptionWindow)

	lang = id.instLanguage.getCurrent()
	lang = id.instLanguage.getLangNick(lang)
        self.icw = InstallControlWindow (self, self.dispatch, lang)
        self.icw.run (self.runres)

class InstallControlWindow:
    def setLanguage (self, locale):
        gtk_set_locale ()
        _gtk_nuke_rc_files ()
        gtk_rc_init ()
        gtk_rc_reparse_all ()

	self.langSearchPath = expandLangs(locale) + ['C']
        
        found = 0
        for l in self.langSearchPath:
            if os.access ("/etc/gtk/gtkrc." + l, os.R_OK):
                rc_parse("/etc/gtk/gtkrc." + l)
                found = 1
        if not found:
            rc_parse("/etc/gtk/gtkrc")

        _gtk_nuke_rc_mtimes ()
        gtk_rc_reparse_all ()
        
	if not self.__dict__.has_key('window'): return

        self.reloadRcQueued = 1

#        self.html.set_font_charset (locale)
	self.updateStockButtons()
        self.navFrame.set_label (_("Navigation"))
        self.installFrame.set_label (_("Language Selection"))
	self.loadReleaseNotes()

    def prevClicked (self, *args):
	try:
	    self.currentWindow.getPrev ()
	except StayOnScreen:
	    return

	self.dispatch.gotoPrev()
	self.dir = -1

        self.setScreen ()

    def nextClicked (self, *args):
	try:
	    rc = self.currentWindow.getNext ()
	except StayOnScreen:
	    return

	self.dispatch.gotoNext()
	self.dir = 1

        self.setScreen ()
        if self.helpWin:
            self.html.source (self.currentWindow.getICS().getHTML(self.langSearchPath))

        self.html.source (self.currentWindow.getICS().getHTML(self.langSearchPath))
#        self.html.source ("<HTML><BODY BGCOLOR=white></BODY></HTML>")
#        self.html.source ("<HTML><BODY BGCOLOR=white><H1>Flight of the Navigator</h1><br>&nbsp;<br>&nbsp;<br><p>Coming soon to an anaconda near you</BODY></HTML>")



    def helpClicked (self, widget, simulated = 0):
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
            self.html.source (self.currentWindow.getICS().getHTML(self.langSearchPath))        
            self.hideHelpButton.show ()
            self.showHelpButton.set_state (STATE_NORMAL)
            self.hbox.pack_start (self.hideHelpButton, FALSE)
            self.hbox.reorder_child (self.hideHelpButton, 0)
            self.displayHelp = TRUE

    def closeHelp(self, args):
        self.helpWin.destroy()
        self.html.destroy()
        self.helpWin = None
        self.showHelpButton.set_sensitive(TRUE)

    def close (self, args):
        self.textWin.destroy()
        self.releaseButton.set_sensitive(TRUE)

    def releaseClicked (self, widget):
        self.textWin = GnomeDialog ()
        self.releaseButton.set_sensitive(FALSE)

        table = GtkTable(3, 3, FALSE)
        self.textWin.vbox.pack_start(table)
        self.textWin.append_button(_("Close"))
        self.textWin.button_connect (0, self.close)

        vbox1 = GtkVBox ()        
        vbox1.set_border_width (10)
        frame = GtkFrame (_("Release Notes"))
        frame.add(vbox1)
        frame.set_label_align (0.5, 0.5)
        frame.set_shadow_type (SHADOW_NONE)
        
        self.textWin.set_position (WIN_POS_CENTER)

        if self.buff != "":
            text = GtkText()
            text.insert (None, None, None, self.buff)
                
            sw = GtkScrolledWindow()
            sw.set_policy(POLICY_NEVER, POLICY_ALWAYS)
            sw.add(text)
            vbox1.pack_start(sw)

            a = GtkAlignment ()
            a.add (frame)
            a.set (0, 0, 1.0, 1.0)
            
            self.textWin.set_default_size (590, 393)
            self.textWin.set_usize (590, 393)
            self.textWin.set_position (WIN_POS_CENTER)

            table.attach (a, 1, 2, 1, 2, FILL|EXPAND, FILL|EXPAND, 5, 5)

            self.textWin.set_border_width(0)
            self.textWin.show_all()

        else:
            self.textWin.set_position (WIN_POS_CENTER)
            label = GtkLabel(_("Unable to load file!"))

            table.attach (label, 1, 2, 1, 2, FILL|EXPAND, FILL|EXPAND, 5, 5)

            self.textWin.set_border_width(0)
            self.textWin.show_all()

    def loadReleaseNotes(self):
        self.buff = ""
	langList = self.langSearchPath + [ "" ]
	for lang in langList:
	    fn = "/mnt/source/RELEASE-NOTES"
	    if len(lang):
		fn = fn + "." + lang

	    if os.access(fn, os.R_OK):
		file = open(fn, "r")
		self.buff = string.join(file.readlines(), '')
		file.close()
		return

	self.buff = _("Release notes are missing.\n")

    def setScreen (self):
	(step, args) = self.dispatch.currentStep()
	if not step:
	    mainquit()
	    return

	if not stepToClass[step]:
	    if self.dir == 1:
		return self.nextClicked()
	    else:
		return self.prevClicked()
		
	(file, className) = stepToClass[step]
        newScreenClass = None
	s = "from %s import %s; newScreenClass = %s" % (file, className, className)
	exec s

	ics = InstallControlState (self)

	self.destroyCurrentWindow()
        self.currentWindow = newScreenClass(ics)

	new_screen = apply(self.currentWindow.getScreen, args)
	if not new_screen:
            return

        self.update (ics)

        self.installFrame.set_label (ics.getTitle ())
        self.installFrame.add (new_screen)
        self.installFrame.show_all ()
	self.currentWindow.renderCallback()

        if self.reloadRcQueued:
            self.window.reset_rc_styles ()
            self.reloadRcQueued = 0

    def destroyCurrentWindow(self):
        children = self.installFrame.children ()
        if children:
            child = children[0]
            self.installFrame.remove (child)
            child.destroy ()
	self.currentWindow = None

    def update (self, ics):
        self.installFrame.set_label (_(ics.getTitle ()))

	prevButton = self.prevButtonStock
	nextButton = self.nextButtonStock

	if ics.getNextButton():
	    (icon, text) = ics.getNextButton()
	    nextButton = GnomePixmapButton (GnomeStock (icon), text)
	    nextButton.connect ("clicked", self.nextClicked)
	    nextButton.show_all()

        children = self.buttonBox.children ()

        if not prevButton in children:
            self.buttonBox.remove (children[0])
            self.buttonBox.pack_start (prevButton)

        if not nextButton in children:
            self.buttonBox.remove (children[1])
            self.buttonBox.pack_end (nextButton)

        prevButton.set_sensitive (ics.getPrevEnabled ())
        nextButton.set_sensitive (ics.getNextEnabled ())
 
        self.html.source (ics.getHTML(self.langSearchPath))


        if (ics.getGrabNext ()):
            nextButton.grab_focus ()

    def __init__ (self, ii, dispatch, locale):
	self.stockButtons = [ 
	    ( STOCK_BUTTON_PREV, "prevButtonStock",
		    _("Back"), self.prevClicked ),
	    ( STOCK_BUTTON_NEXT, "nextButtonStock",
		    _("Next"), self.nextClicked ),
	    ( STOCK_BUTTON_HELP, "releaseButton",
		    _("Release Notes"), self.releaseClicked ),
	    ( STOCK_BUTTON_HELP, "showHelpButton",
		    _("Show Help"), self.helpClicked ),
	    ( STOCK_BUTTON_HELP, "hideHelpButton",
		    _("Hide Help"), self.helpClicked ),
	    ]

        self.reloadRcQueued = 0
        self.ii = ii
        self.dispatch = dispatch
	self.setLanguage(locale)
        self.helpWin = None

    def keyRelease (self, window, event):
        if ((event.keyval == GDK.KP_Delete or event.keyval == GDK.Delete)
            and (event.state & (GDK.CONTROL_MASK | GDK.MOD1_MASK))):
            mainquit ()
            os._exit (0)

    def buildStockButtons(self):
	for (icon, item, text, action) in self.stockButtons:
	    button = GnomePixmapButton(GnomeStock(icon), text)
	    button.connect("clicked", action)
	    button.show_all()
	    self.__dict__[item] = button

    def updateStockButtons(self):
	for (icon, item, text, action) in self.stockButtons:
	    button = self.__dict__[item]
            label = button.children ()[0].children ()[0].children()[1]
            label.set_text (text)
            button.queue_resize()

    def setup_window (self, runres):
        self.window = GtkWindow ()
        self.window.set_events (GDK.KEY_RELEASE_MASK)

        if runres == '640x480':
            self.window.set_default_size (640, 480)
            self.window.set_usize (640, 480)
        else:
            self.window.set_default_size (800, 600)
            self.window.set_usize (800, 600)

        self.window.set_border_width (10)

	title = _("Red Hat Linux Installer")
	if os.environ["DISPLAY"][:1] != ':':
	    # from gnome.zvt import *
	    # zvtwin = GtkWindow ()
#	    shtitle = _("Red Hat Linux Install Shell")
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
#			shtitle = _("Red Hat Linux Install Shell on %s") % string.strip (netinf[1])
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
        self.window.set_border_width(0)
        vbox = GtkVBox (FALSE, 10)

        # Create header at the top of the installer
        if runres != '640x480':
            for dir in ["/usr/share/anaconda/pixmaps/",
                      "pixmaps/",
                      "/tmp/updates"]:
                try:
                    im = GdkImlib.Image (dir + "anaconda_header.png")
                except:
                    im = None
                else:
                    break
                
            if im:
                im.render ()
                pix = im.make_pixmap ()
                a = GtkAlignment ()
                a.add (pix)
                a.set (0.5, 0.5, 1.0, 1.0)
                vbox.pack_start (a, FALSE, TRUE, 0)
            else:
                print _("Unable to load anaconda_header.png")

	self.loadReleaseNotes()

        vbox.set_spacing(0)

        self.buttonBox = GtkHButtonBox ()
        self.buttonBox.set_layout (BUTTONBOX_END)
        self.buttonBox.set_spacing (30)

	self.buildStockButtons()

        group = GtkAccelGroup()
        self.nextButtonStock.add_accelerator ("clicked", group, GDK.F12, GDK.RELEASE_MASK, 0);
        self.window.add_accel_group (group)
        self.window.connect ("key-release-event", self.keyRelease)

        self.buttonBox.add (self.prevButtonStock)
        self.buttonBox.add (self.nextButtonStock)

	self.hbox = GtkHBox ()
        self.hbox.set_border_width(5)
#	self.hbox.pack_start (self.showHelpButton, FALSE)
	self.hbox.pack_start (self.hideHelpButton, FALSE)
        self.hbox.set_spacing (25)
        self.hbox.pack_start (self.releaseButton, FALSE)
	self.hbox.pack_start (self.buttonBox)

        vbox.pack_end (self.hbox, FALSE)

        self.html = GtkXmHTML()
        self.html.set_allow_body_colors(TRUE)
        self.html.source ("<HTML><BODY BGCOLOR=white></BODY></HTML>")
        self.html.source ("<HTML><BODY BGCOLOR=white><H1>Flight of the Navigator</h1><br>&nbsp;<br>&nbsp;<br><p>Coming soon to an anaconda near you</BODY></HTML>")

        self.navFrame = GtkFrame (_("Navigation"))
        self.box = GtkVBox (FALSE, 0)
        self.box.set_spacing(0)

        self.box.pack_start (GtkHSeparator (), FALSE)
        self.box.pack_start (self.html, TRUE)
        
        self.navFrame. add (self.box)

        table = GtkTable (1, 3, TRUE)
        table.attach (self.navFrame, 0, 1, 0, 1)

        self.installFrame = GtkFrame ()

        self.windowList = []

        #self.setStateList (self.steps, 0)
        self.setScreen ()
                          
        table.attach (self.installFrame, 1, 3, 0, 1)
        table.set_col_spacing (0, 5)

        self.bin = GtkFrame ()
        self.bin.set_shadow_type (SHADOW_NONE)
        self.bin.add (table)
        vbox.pack_end (self.bin, TRUE, TRUE)
        self.table = table

        self.window.add (vbox)

        # Popup the ICW and wait for it to wake us back up
        self.window.show_all ()

        splashScreenPop()

    def run (self, runres):
        self.setup_window (runres)
        mainloop ()
            
class InstallControlState:
    def __init__ (self, cw):
        self.searchPath = [ "./", "/usr/share/anaconda/", "./" ]
        self.cw = cw
        self.prevEnabled = 1
        self.nextEnabled = 0
	self.nextButtonInfo = None
        self.helpButtonEnabled = TRUE
        self.title = _("Install Window")
        self.html = ""
        self.htmlFile = None
        self.nextButton = STOCK_BUTTON_NEXT
        self.prevButton = STOCK_BUTTON_PREV
        self.nextButtonLabel = None
        self.prevButtonLabel = None
        self.helpEnabled = 3 # Values other than TRUE or FALSE don't change the help setting
        self.grabNext = 0

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
        if value != self.nextEnabled:
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

    def getHTML (self, langPath):
        text = None
        if self.htmlFile:
            file = self.htmlFile
            
            for path in self.searchPath:
                for lang in langPath:
                    try:
                        text = open("%s/help/%s/s1-help-screens-%s.html" %
                                    (path, lang, file)).read ()
                    except IOError:
                        continue
                    else:
                        break
                if text:
                    break
                try:
                    text = open("%s/help/C/s1-help-screens-%s.html" %
                                (path, file)).read ()
                except IOError:
                        continue

            if text:
                return text

            print "Unable to read %s help text" % (file,)

        return self.html
    
    def setScreenPrev (self):
        self.cw.prevClicked ()

    def setScreenNext (self):
        self.cw.nextClicked ()

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

    def setNextButton(self, icon, text):
	self.nextButtonInfo = (icon, text)

    def getNextButton(self):
	return self.nextButtonInfo
