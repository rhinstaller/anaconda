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
import iutil
import string
import isys
import sys
import parted
import gtk
from translate import _, N_
from language import expandLangs
from splashscreen import splashScreenPop
from log import log
from flags import flags

StayOnScreen = "stayOnScreen"

stepToClass = {
    "language" : ("language_gui", "LanguageWindow"),
    "keyboard" : ("keyboard_gui", "KeyboardWindow"),
    "mouse" : ("mouse_gui", "MouseWindow"),
    "welcome" : ("welcome_gui", "WelcomeWindow"),
    "installtype" : ("installpath_gui", "InstallPathWindow"),
    "partitionmethod" : ("partmethod_gui", "PartitionMethodWindow"),
    "partition" : ("partition_gui", "PartitionWindow"),
    "autopartition" : ("partition_gui", "AutoPartitionWindow"),
    "findinstall" : ("examine_gui", "UpgradeExamineWindow"),
    "addswap" : ("upgrade_swap_gui", "UpgradeSwapWindow"),
    "upgrademigratefs" : ("upgrade_migratefs_gui", "UpgradeMigrateFSWindow"),
    "fdisk" : ("fdisk_gui", "FDiskWindow"),
    "format" : ("format_gui", "FormatWindow"),
    "bootloader": ("bootloader_gui", "BootloaderWindow"), 
    "bootloaderpassword" : ("bootloaderpassword_gui", "BootloaderPasswordWindow"),
    "network" : ("network_gui", "NetworkWindow"),
    "firewall" : ("firewall_gui", "FirewallWindow"),
    "languagesupport" : ("language_support_gui", "LanguageSupportWindow"),
    "timezone" : ("timezone_gui", "TimezoneWindow"),
    "accounts" : ("account_gui", "AccountWindow"),
    "authentication" : ("auth_gui", "AuthWindow"),
    "package-selection" : ("package_gui", "PackageSelectionWindow"),
    "indivpackage" : ("package_gui", "IndividualPackageSelectionWindow"),
    "dependencies" : ("dependencies_gui", "UnresolvedDependenciesWindow"),
    "videocard" : ("xconfig_gui", "XConfigWindow"),
    "monitor" : ("xconfig_gui", "MonitorWindow"),
    "xcustom" : ("xconfig_gui", "XCustomWindow"),
    "confirminstall" : ("confirm_gui", "InstallConfirmWindow"),
    "confirmupgrade" : ("confirm_gui", "UpgradeConfirmWindow"),
    "finishxconfig" : None,
    "install" : ("progress_gui", "InstallProgressWindow"),
    "bootdisk" : ("bootdisk_gui", "BootdiskWindow"),
    "complete" : ("congrats_gui", "CongratulationWindow"),
    "reconfigwelcome" : ("welcome_gui", "ReconfigWelcomeWindow"),
    "reconfigkeyboard" : ("keyboard_gui", "KeyboardWindow"),
    "reconfigcomplete" : ("congrats_gui", "ReconfigCongratulationWindow")
}

if iutil.getArch() == 'sparc':
    stepToClass["bootloader"] = ("silo_gui", "SiloWindow")
else:
    stepToClass["bootloader"] = ("bootloader_gui", "BootloaderWindow")

# setup globals

def processEvents():
    gtk.gdk.flush()
    while gtk.events_pending():
        gtk.main_iteration(gtk.FALSE)

def partedExceptionWindow(exc):
    # if our only option is to cancel, let us handle the exception
    # in our code and avoid popping up the exception window here.
    if exc.options == parted.EXCEPTION_CANCEL:
        return parted.EXCEPTION_UNHANDLED
    print exc.type_string
    print exc.message
    print exc.options
    win = gtk.Dialog (exc.type_string)
    win.set_position (gtk.WIN_POS_CENTER)
    label = WrappingLabel(exc.message)
    win.vbox.pack_start (label)
    numButtons = 0
    buttonToAction = {}
    
    flags = ((parted.EXCEPTION_FIX, N_("Fix")),
             (parted.EXCEPTION_YES, N_("Yes")),
             (parted.EXCEPTION_NO, N_("No")),
             (parted.EXCEPTION_OK, N_("OK")),
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
    return buttonToAction[rc]

def widgetExpander(widget, growTo=None):
    widget.connect("size-allocate", growToParent, growTo)

def growToParent(widget, rect, growTo=None):
    if not widget.parent:
        return
    ignore = widget.__dict__.get("ignoreEvents")
    if not ignore:
        if growTo:
            x, y, width, height = growTo.get_allocation()
            widget.set_usize(width, -1)
        else:
            widget.set_usize(rect.width, -1)
        widget.ignoreEvents = 1
    else:
        widget.ignoreEvents = 0

class WrappingLabel(gtk.Label):
    def __init__(self, label=""):
        gtk.Label.__init__(self, label)
        self.set_line_wrap(gtk.TRUE)
        self.ignoreEvents = 0
        self.set_usize(-1, 1)
        widgetExpander(self)

class WaitWindow:
    def __init__(self, title, text):
        self.window = gtk.Window(gtk.WINDOW_POPUP)
        self.window.set_title(_(title))
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.set_modal(gtk.TRUE)
        label = WrappingLabel(_(text))
        box = gtk.Frame()
        box.set_border_width(10)
        box.add(label)
        box.set_shadow_type(gtk.SHADOW_NONE)
        frame = gtk.Frame ()
        frame.set_shadow_type(gtk.SHADOW_OUT)
        frame.add (box)
	self.window.add(frame)
	self.window.show_all()
        processEvents()
            
    def pop(self):
        self.window.destroy()

class ProgressWindow:
    def __init__(self, title, text, total):
        self.window = gtk.Window (gtk.WINDOW_POPUP)
        self.window.set_title (_(title))
        self.window.set_position (gtk.WIN_POS_CENTER)
        self.window.set_modal (gtk.TRUE)
        box = gtk.VBox (gtk.FALSE, 5)
        box.set_border_width (10)

        label = WrappingLabel (_(text))
        label.set_alignment (0.0, 0.5)
        box.pack_start (label, gtk.FALSE)
        
        self.total = total
	self.progress = gtk.ProgressBar ()
        box.pack_start (self.progress, gtk.TRUE)
        
        frame = gtk.Frame ()
        frame.set_shadow_type (gtk.SHADOW_OUT)
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
        win = gtk.Dialog ("Exception Occured")
        win.add_button("Debug", 0)
        win.add_button("Save to floppy", 1)
        win.add_button('gtk-ok', 2)
        buffer = gtk.TextBuffer(None)
        buffer.set_text(text)
        textbox = gtk.TextView()
        textbox.set_buffer(buffer)
        textbox.set_property("editable", gtk.FALSE)
        textbox.set_property("cursor_visible", gtk.FALSE)
        sw = gtk.ScrolledWindow ()
        sw.add (textbox)
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        hbox = gtk.HBox (gtk.FALSE)
##         file = pixmap_file('gnome-warning.png')
##         if file:
##             hbox.pack_start (GnomePixmap (file), gtk.FALSE)

        info = WrappingLabel(_("An unhandled exception has occured.  This "
                               "is most likely a bug.  Please copy the "
                               "full text of this exception or save the crash "
                               "dump to a floppy then file a detailed bug "
                               "report against anaconda at "
                               "http://bugzilla.redhat.com/bugzilla/"))
        info.set_usize (400, -1)

        hbox.pack_start (sw, gtk.TRUE)
        win.vbox.pack_start (info, gtk.FALSE)            
        win.vbox.pack_start (hbox, gtk.TRUE)
        win.set_usize (500, 300)
        win.set_position (gtk.WIN_POS_CENTER)
        win.show_all ()
        self.window = win
        self.rc = self.window.run ()
        
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
    def getrc (self):
        return self.rc
    
    def __init__ (self, title, text, type="ok", default=None):
        if flags.autostep:
            print title, text, type
            self.rc = 1
            return
        self.rc = None
#        window = gtk.Dialog(flags=gtk.DIALOG_MODAL)
        window = gtk.Dialog("Foo", None, gtk.DIALOG_MODAL)
        window = gtk.Dialog()
        window.vbox.pack_start(WrappingLabel(_(text)), gtk.FALSE)
        if type == "ok":
            window.add_button('gtk-ok', 1)
        if type == "okcancel":
            window.add_button('gtk-ok', 1)
            window.add_button('gtk-cancel', 0)
        if type == "yesno":
            window.add_button('gtk-yes', 1)
            window.add_button('gtk-no', 0)
        if default == "no":
            window.set_default_response(0)
        elif default == "yes" or default == "ok":
            window.set_default_response(1)
        else:
            raise RuntimeError, "unhandled default"
        window.set_position (gtk.WIN_POS_CENTER)
        window.show_all ()
        self.rc = window.run ()
        window.destroy()
    
class InstallInterface:
    def __init__ (self):
        # figure out if we want to run interface at 800x600 or 640x480
        if gtk.gdk.screen_width() >= 800:
            self.runres = "800x600"
        else:
            self.runres = "640x480"

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

    def messageWindow(self, title, text, type="ok", default = None):
        rc = MessageWindow (title, text, type, default).getrc()
        return rc

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

    def run(self, id, dispatch, configFileData):
        from xkb import XKB
        kb = XKB()

	self.dispatch = dispatch

        if flags.setupFilesystems:
            try:
                kb.setMouseKeys (1)
            except SystemError:
                pass

        if id.keyboard:
	    info = id.keyboard.getXKB()
	    if info:
                (rules, model, layout, variant, options) = info
                kb.setRule (model, layout, variant, "complete")

        id.fsset.registerMessageWindow(self.messageWindow)
        id.fsset.registerProgressWindow(self.progressWindow)
        id.fsset.registerWaitWindow(self.waitWindow)
        parted.exception_set_handler(partedExceptionWindow)

	lang = id.instLanguage.getCurrent()
	lang = id.instLanguage.getLangNick(lang)
        self.icw = InstallControlWindow (self, self.dispatch, lang)
        self.icw.run (self.runres, configFileData)

class InstallControlWindow:
    def setLanguage (self, locale):
        #gtk_set_locale ()
        #gtk_rc_init ()
        #gtk_rc_reparse_all ()

	self.langSearchPath = expandLangs(locale) + ['C']
        
##         found = 0
##         for l in self.langSearchPath:
##             if os.access ("/etc/gtk/gtkrc." + l, os.R_OK):
##                 rc_parse("/etc/gtk/gtkrc." + l)
##                 found = 1
##         if not found:
##             rc_parse("/etc/gtk/gtkrc")

##         #_gtk_nuke_rc_mtimes ()
##         gtk_rc_reparse_all ()
        
	if not self.__dict__.has_key('window'): return

        self.reloadRcQueued = 1

##         self.html.set_font_charset (locale)
	self.updateStockButtons()
        self.helpFrame.set_label (_("Online Help"))
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

    def helpClicked (self, widget, simulated=0):
        self.hbox.remove (widget)
        if widget == self.hideHelpButton:
            self.bin.remove (self.table)
            self.installFrame.reparent (self.bin)
            self.showHelpButton.show ()
            self.showHelpButton.set_state (gtk.STATE_NORMAL)
            self.hbox.pack_start (self.showHelpButton, gtk.FALSE)
            self.hbox.reorder_child (self.showHelpButton, 0)
            self.showHelpButton.grab_focus()            
            self.displayHelp = gtk.FALSE
        else:
            self.bin.remove (self.installFrame)
            self.table.attach (self.installFrame, 1, 3, 0, 1,
                               gtk.FILL | gtk.EXPAND,
                               gtk.FILL | gtk.EXPAND)
            self.bin.add (self.table)
            # fix to set the bgcolor to white (xmhtml sucks)
##             self.html.source ("<HTML><BODY BGCOLOR=white></BODY></HTML>")
##             self.html.source (self.currentWindow.getICS().getHTML(self.langSearchPath))        
            self.hideHelpButton.show ()
            self.showHelpButton.set_state (gtk.STATE_NORMAL)
            self.hbox.pack_start (self.hideHelpButton, gtk.FALSE)
            self.hbox.reorder_child (self.hideHelpButton, 0)
            self.hideHelpButton.grab_focus()
            self.displayHelp = gtk.TRUE

    def close (self, *args):
        self.textWin.destroy()
        self.releaseButton.set_sensitive(gtk.TRUE)

    def releaseClicked (self, widget):
        self.textWin = gtk.Dialog ()
        self.releaseButton.set_sensitive(gtk.FALSE)

        table = gtk.Table(3, 3, gtk.FALSE)
        self.textWin.vbox.pack_start(table)
        self.textWin.add_button('gtk-close', gtk.RESPONSE_NONE)
        self.textWin.connect("response", self.close)
        vbox1 = gtk.VBox ()        
        vbox1.set_border_width (10)
        frame = gtk.Frame (_("Release Notes"))
        frame.add(vbox1)
        frame.set_label_align (0.5, 0.5)
        frame.set_shadow_type (gtk.SHADOW_NONE)
        
        self.textWin.set_position (gtk.WIN_POS_CENTER)

        if self.buff != "":
            buffer = gtk.TextBuffer(None)
            buffer.set_text(self.buff)
            text = gtk.TextView()
            text.set_buffer(buffer)
            text.set_property("editable", gtk.FALSE)
            text.set_property("cursor_visible", gtk.FALSE)
                
            sw = gtk.ScrolledWindow()
            sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
            sw.set_shadow_type(gtk.SHADOW_IN)
            sw.add(text)
            vbox1.pack_start(sw)

            a = gtk.Alignment (0, 0, 1.0, 1.0)
            a.add (frame)
            
            self.textWin.set_default_size (635, 393)
            self.textWin.set_usize (635, 393)
            self.textWin.set_position (gtk.WIN_POS_CENTER)

            table.attach (a, 1, 2, 1, 2,
                          gtk.FILL | gtk.EXPAND,
                          gtk.FILL | gtk.EXPAND, 5, 5)

            self.textWin.set_border_width(0)
            self.textWin.show_all()

        else:
            self.textWin.set_position (gtk.WIN_POS_CENTER)
            label = gtk.Label(_("Unable to load file!"))

            table.attach (label, 1, 2, 1, 2,
                          gtk.FILL | gtk.EXPAND, gtk.FILL | gtk.EXPAND, 5, 5)

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

    def handleRenderCallback(self):
        self.currentWindow.renderCallback()
        if flags.autostep:
            self.nextClicked()
        else:
            gtk.idle_remove(self.handle)

    def setScreen (self):
	(step, args) = self.dispatch.currentStep()
	if not step:
	    gtk.mainquit()
	    return

	if not stepToClass[step]:
	    if self.dir == 1:
		return self.nextClicked()
	    else:
		return self.prevClicked()
		
	(file, className) = stepToClass[step]
        newScreenClass = None
	s = "from %s import %s; newScreenClass = %s" % (file, className,
                                                        className)
	exec s

	ics = InstallControlState (self)
        ics.setPrevEnabled(self.dispatch.canGoBack())
        
	self.destroyCurrentWindow()
        self.currentWindow = newScreenClass(ics)

	new_screen = apply(self.currentWindow.getScreen, args)
	if not new_screen:
            return

        self.update (ics)

        self.installFrame.set_label (ics.getTitle ())
        self.installFrame.add (new_screen)
        self.installFrame.show_all ()

	self.handle = gtk.idle_add(self.handleRenderCallback)

        if self.reloadRcQueued:
            self.window.reset_rc_styles ()
            self.reloadRcQueued = 0

##         if self.displayHelp:
##             self.html.source ("<HTML><BODY BGCOLOR=white></BODY></HTML>")
##             self.html.source (ics.getHTML(self.langSearchPath))

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
	    nextButton = Button(stock=icon)
#            nextButton.set_property("label", _(text))
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
        self.hideHelpButton.set_sensitive (ics.getHelpButtonEnabled ())
        self.showHelpButton.set_sensitive (ics.getHelpButtonEnabled ())

        if ics.getHelpEnabled () == gtk.FALSE:
            if self.displayHelp:
                self.helpClicked (self.hideHelpButton, 1)
        elif ics.getHelpEnabled () == gtk.TRUE:
            if not self.displayHelp:
                self.helpClicked (self.showHelpButton, 1)
 
        if (ics.getGrabNext ()):
            nextButton.grab_focus ()

    def __init__ (self, ii, dispatch, locale):
        self.prevButtonStock = None
        self.nextButtonStock = None
        self.releaseButton = None
        self.showHelpButton = None
        self.hideHelpButton = None

	self.stockButtons = (('gtk-go-back', "prevButtonStock",
                              N_("_Back"), self.prevClicked),
                             ('gtk-go-forward', "nextButtonStock",
                              N_("_Next"), self.nextClicked),
                             ('gtk-new', "releaseButton",
                              N_("_Release Notes"), self.releaseClicked),
                             ('gtk-help', "showHelpButton",
                              N_("Show _Help"), self.helpClicked),
                             ('gtk-help', "hideHelpButton",
                              N_("Hide _Help"), self.helpClicked))

        self.reloadRcQueued = 0
        self.ii = ii
        self.dispatch = dispatch
	self.setLanguage(locale)
        self.handle = None

    def keyRelease (self, window, event):
        if ((event.keyval == gtk.keysyms.KP_Delete
             or event.keyval == gtk.keysyms.Delete)
            and (event.state & (gtk.gdk.CONTROL_MASK | gtk.gdk.MOD1_MASK))):
            gtk.mainquit()
            os._exit(0)

    def buildStockButtons(self):
	for (icon, item, text, action) in self.stockButtons:
            button = gtk.Button()
            box = gtk.HBox(gtk.FALSE, 0)
            image = gtk.Image()
            image.set_from_stock(icon, gtk.ICON_SIZE_BUTTON)
            box.pack_start(image, gtk.FALSE, gtk.FALSE)
            label = gtk.Label(_(text))
            label.set_property("use-underline", gtk.TRUE)
            box.pack_start(label, gtk.TRUE, gtk.TRUE)
            button.add(box)
	    button.connect("clicked", action)
	    button.show_all()
            button.label = label
	    self.__dict__[item] = button

    def updateStockButtons(self):
	for (icon, item, text, action) in self.stockButtons:
	    button = self.__dict__[item]
            button.label.set_text_with_mnemonic(_(text))
            button.queue_resize()

    def setup_window (self, runres):
        self.window = gtk.Window ()
        self.window.set_events (gtk.gdk.KEY_RELEASE_MASK)

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
	    # zvtwin = gtk.Window ()
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
        self.window.set_position (gtk.WIN_POS_CENTER)
        self.window.set_border_width(0)
        vbox = gtk.VBox (gtk.FALSE, 10)

        image = self.configFileData["TitleBar"]

        # Create header at the top of the installer
        if runres != '640x480':
            for dir in ("/usr/share/anaconda/",
                        "",
                        "/tmp/updates"):
                pixbuf = gtk.gdk.pixbuf_new_from_file(dir + image)
                if not pixbuf is None:
                    break
                
            if pixbuf:
                p = gtk.Image()
                p.set_from_pixbuf(pixbuf)
                a = gtk.Alignment()
                a.set(0.5, 0.5, 1.0, 1.0)
                a.add(p)
                vbox.pack_start(a, gtk.FALSE, gtk.TRUE, 0)
            else:
                print _("Unable to load title bar")


	self.loadReleaseNotes()

        vbox.set_spacing(0)

        self.buttonBox = gtk.HButtonBox ()
        self.buttonBox.set_layout (gtk.BUTTONBOX_END)
        self.buttonBox.set_spacing (30)

	self.buildStockButtons()

        group = gtk.AccelGroup()
        self.nextButtonStock.add_accelerator ("clicked", group, gtk.keysyms.F12,
                                              gtk.gdk.RELEASE_MASK, 0);
        self.window.add_accel_group (group)

        # set up ctrl+alt+delete handler
        self.window.connect ("key-release-event", self.keyRelease)

        self.buttonBox.add (self.prevButtonStock)
        self.buttonBox.add (self.nextButtonStock)

	self.hbox = gtk.HBox ()
        self.hbox.set_border_width(5)
	self.hbox.pack_start (self.hideHelpButton, gtk.FALSE)
        self.hbox.set_spacing (25)
        self.hbox.pack_start (self.releaseButton, gtk.FALSE)
	self.hbox.pack_start (self.buttonBox)

        vbox.pack_end (self.hbox, gtk.FALSE)

##         self.html = gtk.XmHTML()
##         self.html.set_allow_body_colors(gtk.TRUE)
##         self.html.source ("<HTML><BODY BGCOLOR=white></BODY></HTML>")
        self.displayHelp = gtk.TRUE
        self.helpState = gtk.TRUE

        self.helpFrame = gtk.Frame (_("Online Help"))
        self.box = gtk.VBox (gtk.FALSE, 0)
        self.box.set_spacing(0)

        self.box.pack_start (gtk.HSeparator (), gtk.FALSE)
##         self.box.pack_start (self.html, gtk.TRUE)
        
        self.helpFrame.add (self.box)

        table = gtk.Table (1, 3, gtk.TRUE)
        table.attach (self.helpFrame, 0, 1, 0, 1,
                      gtk.FILL | gtk.EXPAND,
                      gtk.FILL | gtk.EXPAND)

        self.installFrame = gtk.Frame ()

        self.windowList = []

        #self.setStateList (self.steps, 0)
        self.setScreen ()
                          
        table.attach (self.installFrame, 1, 3, 0, 1,
                      gtk.FILL | gtk.EXPAND,
                      gtk.FILL | gtk.EXPAND)
        table.set_col_spacing (0, 5)

        self.bin = gtk.Frame ()
        self.bin.set_shadow_type (gtk.SHADOW_NONE)
        self.bin.add (table)
        vbox.pack_end (self.bin, gtk.TRUE, gtk.TRUE)
        self.table = table

        self.window.add (vbox)

        # Popup the ICW and wait for it to wake us back up
        self.window.show_all ()

        splashScreenPop()

    def run (self, runres, configFileData):
        self.configFileData = configFileData
        self.setup_window(runres)
        gtk.main()
            
class InstallControlState:
    def __init__ (self, cw):
        self.searchPath = [ "./", "/usr/share/anaconda/", "./" ]
        self.cw = cw
        self.prevEnabled = 1
        self.nextEnabled = 1
	self.nextButtonInfo = None
        self.helpButtonEnabled = gtk.TRUE
        self.title = _("Install Window")
        self.html = ""
        self.htmlFile = None
        self.nextButton = 'gtk-next'
        self.prevButton = 'gtk-prev'
        self.nextButtonLabel = None
        self.prevButtonLabel = None
        # Values other than gtk.TRUE or gtk.FALSE don't change the help setting        
        self.helpEnabled = 3 
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

    def findPixmap(self, file):
        for path in ("/usr/share/anaconda/pixmaps/", "pixmaps/",
                     "/usr/share/anaconda/", "",
                     "/mnt/source/RHupdates/pixmaps/",
                     "/mnt/source/RHupdates/"):
            fn = path + file
            if os.access(fn, os.R_OK):
                return fn
        return None
        
    def readPixmap (self, file):
        fn = self.findPixmap(file)
        if not fn:
            log("unable to load %s", file)
            return None
        pixbuf = gtk.gdk.pixbuf_new_from_file(fn)
        if pixbuf is None:
            log("unable to read %s", file)
            return None
        p = gtk.Image()
        p.set_from_pixbuf(pixbuf)
        return p

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
