#
# gui.py - Graphical front end for anaconda
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 1999-2002 Red Hat, Inc.
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
import htmlbuffer
from language import expandLangs
from splashscreen import splashScreenPop
from flags import flags
from constants import *

from rhpl.log import log
from rhpl.translate import _, N_, utf8

StayOnScreen = "stayOnScreen"
mainWindow = None

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
    "fdasd" : ("fdasd_gui", "FDasdWindow"),
    "bootloader": ("bootloader_main_gui", "MainBootloaderWindow"),
    "bootloaderadvanced": ("bootloader_advanced_gui", "AdvancedBootloaderWindow"),
    "upgbootloader": ("upgrade_bootloader_gui", "UpgradeBootloaderWindow"),
    "network" : ("network_gui", "NetworkWindow"),
    "firewall" : ("firewall_gui", "FirewallWindow"),
    "languagesupport" : ("language_support_gui", "LanguageSupportWindow"),
    "timezone" : ("timezone_gui", "TimezoneWindow"),
    "accounts" : ("account_gui", "AccountWindow"),
    "authentication" : ("auth_gui", "AuthWindow"),
    "desktopchoice": ("desktop_choice_gui", "DesktopChoiceWindow"),
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
}

if iutil.getArch() == 'sparc':
    stepToClass["bootloader"] = ("silo_gui", "SiloWindow")
elif iutil.getArch() == 's390':
    stepToClass["bootloader"] = ("zipl_gui", "ZiplWindow")

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
    win = gtk.Dialog(exc.type_string, mainWindow, gtk.DIALOG_MODAL)
    addFrame(win)
    win.set_position(gtk.WIN_POS_CENTER)
    label = WrappingLabel(exc.message)
    win.vbox.pack_start (label)
    numButtons = 0
    buttonToAction = {}
    
    exflags = ((parted.EXCEPTION_FIX, N_("Fix")),
             (parted.EXCEPTION_YES, N_("Yes")),
             (parted.EXCEPTION_NO, N_("No")),
             (parted.EXCEPTION_OK, N_("OK")),
             (parted.EXCEPTION_RETRY, N_("Retry")),
             (parted.EXCEPTION_IGNORE, N_("Ignore")),
             (parted.EXCEPTION_CANCEL, N_("Cancel")))
    for flag, string in exflags:
        if exc.options & flag:
            win.add_button(_(string), flag)
    win.show_all()
    rc = win.run()
    win.destroy()
    return rc

def widgetExpander(widget, growTo=None):
    widget.connect("size-allocate", growToParent, growTo)

def growToParent(widget, rect, growTo=None):
    return
    if not widget.parent:
        return
    ignore = widget.__dict__.get("ignoreEvents")
    if not ignore:
        if growTo:
            x, y, width, height = growTo.get_allocation()
            widget.set_size_request(width, -1)
        else:
            widget.set_size_request(rect.width, -1)
        widget.ignoreEvents = 1
    else:
        widget.ignoreEvents = 0

class MnemonicLabel(gtk.Label):
    def __init__(self, text=""):
        gtk.Label.__init__(self, "")
        self.set_text_with_mnemonic(text)

class WrappingLabel(gtk.Label):
    def __init__(self, label=""):
        gtk.Label.__init__(self, label)
        self.set_line_wrap(gtk.TRUE)
        self.ignoreEvents = 0
#        self.set_size_request(-1, 1)
        widgetExpander(self)

def titleBarMousePressCB(widget, event, data):
    if event.type & gtk.gdk.BUTTON_PRESS:
	data["state"] = 1
	data["button"] = event.button
	data["deltax"] = event.x
	data["deltay"] = event.y
	
def titleBarMouseReleaseCB(widget, event, data):
    if data["state"] and event.button == data["button"]:
	data["state"] = 0
	data["button"] = 0
	data["deltax"] = 0
	data["deltay"] = 0

def titleBarMotionEventCB(widget, event, data):
    if data["state"]:
	newx = event.x_root-data["deltax"]
	newy = event.y_root-data["deltay"]
	if newx < 0:
	    newx = 0
	if newy < 0:
	    newy = 0
	(w, h) = data["window"].get_size()
	if (newx+w) > gtk.gdk.screen_width():
	    newx = gtk.gdk.screen_width() - w
	if (newy+20) > (gtk.gdk.screen_height()):
	    newy = gtk.gdk.screen_height() - 20
	
	data["window"].move(newx, newy)

def addFrame(dialog, title=None):
    contents = dialog.get_children()[0]
    dialog.remove(contents)
    frame = gtk.Frame()
    frame.set_shadow_type(gtk.SHADOW_OUT)
    box = gtk.VBox()
    try:
	if title is None:
	    title = dialog.get_title()

	if title:
	    data = {}
	    data["state"] = 0
	    data["button"] = 0
	    data["deltax"] = 0
	    data["deltay"] = 0
	    data["window"] = dialog
	    eventBox = gtk.EventBox()
	    eventBox.connect("button-press-event", titleBarMousePressCB, data)
	    eventBox.connect("button-release-event", titleBarMouseReleaseCB, data)
	    eventBox.connect("motion-notify-event", titleBarMotionEventCB,data)
	    titleBox = gtk.HBox(gtk.FALSE, 5)
	    eventBox.add(titleBox)
	    eventBox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse ("#4C57a6"))
	    titlelbl = gtk.Label("")
	    titlelbl.set_markup("<b>"+_(title)+"</b>")
	    titlelbl.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse ("white"))
	    titlelbl.set_property("ypad", 4)
	    titleBox.pack_start(titlelbl)
	    box.pack_start(eventBox, gtk.FALSE, gtk.FALSE)
    except:
	pass
    
    frame2=gtk.Frame()
    frame2.set_shadow_type(gtk.SHADOW_NONE)
    frame2.set_border_width(4)
    frame2.add(contents)
    box.pack_start(frame2, gtk.TRUE, gtk.TRUE, padding=5)
    frame.add(box)
    frame.show()
    dialog.add(frame)

class WaitWindow:
    def __init__(self, title, text):
        self.window = gtk.Window(gtk.WINDOW_POPUP)
        self.window.set_title(title)
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.set_modal(gtk.TRUE)
        label = WrappingLabel(text)
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
        self.window.set_title (title)
        self.window.set_position (gtk.WIN_POS_CENTER)
        self.window.set_modal (gtk.TRUE)
        box = gtk.VBox (gtk.FALSE, 5)
        box.set_border_width (10)

        label = WrappingLabel (text)
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
	self.progress.set_fraction (float (amount) / self.total)
        processEvents ()        
    
    def pop(self):
        self.window.destroy ()

class ExceptionWindow:
    def __init__ (self, text):
        win = gtk.Dialog("Exception Occured", mainWindow, gtk.DIALOG_MODAL)
        win.add_button("_Debug", 0)
        win.add_button("_Save to floppy", 1)
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
        info.set_size_request (400, -1)

        hbox.pack_start (sw, gtk.TRUE)
        win.vbox.pack_start (info, gtk.FALSE)            
        win.vbox.pack_start (hbox, gtk.TRUE)
        win.set_size_request (500, 300)
        win.set_position (gtk.WIN_POS_CENTER)
        addFrame(win)
        win.show_all ()
        self.window = win
        self.rc = self.window.run ()
#        self.window.destroy()
        
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
    
    def __init__ (self, title, text, type="ok", default=None, custom_buttons=None, custom_icon=None):
        if flags.autostep:
            print title, text, type
            self.rc = 1
            return
        self.rc = None
	docustom = 0
        if type == 'ok':
            buttons = gtk.BUTTONS_OK
            style = gtk.MESSAGE_INFO
        elif type == 'warning':
            buttons = gtk.BUTTONS_OK
            style = gtk.MESSAGE_WARNING
        elif type == 'okcancel':
            buttons = gtk.BUTTONS_OK_CANCEL
            style = gtk.MESSAGE_WARNING
        elif type == 'yesno':
            buttons = gtk.BUTTONS_YES_NO
            style = gtk.MESSAGE_QUESTION
	elif type == 'custom':
	    docustom = 1
	    buttons = gtk.BUTTONS_NONE
	    style = gtk.MESSAGE_QUESTION

	if custom_icon == "warning":
	    style = gtk.MESSAGE_WARNING
	elif custom_icon == "question":
	    style = gtk.MESSAGE_QUESTION
	elif custom_icon == "error":
	    style = gtk.MESSAGE_ERROR
	elif custom_icon == "info":
	    style = gtk.MESSAGE_INFO

	dialog = gtk.MessageDialog(mainWindow, 0, style, buttons, text)

	if docustom:
	    rid=0
	    for button in custom_buttons:
		if button == _("Cancel"):
		    tbutton = "gtk-cancel"
		else:
		    tbutton = button
		widget = dialog.add_button(tbutton, rid)
		rid = rid + 1

            defaultchoice = rid - 1
	else:
	    if default == "no":
                defaultchoice = 0
	    elif default == "yes" or default == "ok":
                defaultchoice = 1
	    else:
                defaultchoice = 0

        addFrame(dialog, title=title)
        dialog.set_position (gtk.WIN_POS_CENTER)
        dialog.set_default_response(defaultchoice)
        dialog.show_all ()
        rc = dialog.run()

        if rc == gtk.RESPONSE_OK or rc == gtk.RESPONSE_YES:
            self.rc = 1
        elif (rc == gtk.RESPONSE_CANCEL or rc == gtk.RESPONSE_NO
            or rc == gtk.RESPONSE_CLOSE):
            self.rc = 0
	elif rc == gtk.RESPONSE_DELETE_EVENT:
	    self.rc = 0
	else:
	    self.rc = rc
        dialog.destroy()
    
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

    def messageWindow(self, title, text, type="ok", default = None,
		     custom_buttons=None,  custom_icon=None):
        rc = MessageWindow (title, text, type, default,
			    custom_buttons, custom_icon).getrc()
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
	return not rc

    def getBootdisk (self):
        return None

    def run(self, id, dispatch, configFileData):
##         from xkb import XKB
##         kb = XKB()

	self.dispatch = dispatch

        # XXX users complain when the keypad doesn't work for input.
##         if 0 and flags.setupFilesystems:
##             try:
##                 kb.setMouseKeys (1)
##             except SystemError:
##                 pass

        # XXX x_already_set is a hack
        if id.keyboard and not id.x_already_set:
            id.keyboard.activate()
## 	    info = id.keyboard.getXKB()
## 	    if info:
##                 (rules, model, layout, variant, options) = info
##                 kb.setRule (model, layout, variant, "complete")

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
            self.refreshHelp()
            self.hideHelpButton.show ()
            self.showHelpButton.set_state (gtk.STATE_NORMAL)
            self.hbox.pack_start (self.hideHelpButton, gtk.FALSE)
            self.hbox.reorder_child (self.hideHelpButton, 0)
            self.hideHelpButton.grab_focus()
            self.displayHelp = gtk.TRUE

    def debugClicked (self, *args):
        try:
            # switch to VC1 so we can debug
            isys.vtActivate (1)
        except SystemError:
            pass
        import pdb
        try:
            pdb.set_trace()
        except:
            sys.exit(-1)
        try:
            # switch back
            isys.vtActivate (7)
        except SystemError:
            pass
        
    def refreshHelp(self):
        buffer = htmlbuffer.HTMLBuffer()
        ics = self.currentWindow.getICS()
        buffer.feed(utf8(ics.getHTML(self.langSearchPath)))
        textbuffer = buffer.get_buffer()
        self.help.set_buffer(textbuffer)
        # scroll to the top.  Do this with a mark so it's done in the idle loop
        iter = textbuffer.get_iter_at_offset(0)
        mark = textbuffer.create_mark("top", iter, gtk.FALSE)
        self.help.scroll_to_mark(mark, 0.0, gtk.FALSE, 0.0, 0.0)

    def close (self, *args):
        self.textWin.destroy()
        self.releaseButton.set_sensitive(gtk.TRUE)

    def releaseClicked (self, widget):
        self.textWin = gtk.Dialog(parent=mainWindow, flags=gtk.DIALOG_MODAL)
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

        if self.releaseNotesBuffer:
            text = gtk.TextView()
            text.set_buffer(self.releaseNotesBuffer)
            text.set_property("editable", gtk.FALSE)
            text.set_property("cursor_visible", gtk.FALSE)
            text.set_wrap_mode(gtk.WRAP_WORD)
            
            sw = gtk.ScrolledWindow()
            sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
            sw.set_shadow_type(gtk.SHADOW_IN)
            sw.add(text)
            vbox1.pack_start(sw)

            a = gtk.Alignment (0, 0, 1.0, 1.0)
            a.add (frame)
            
            self.textWin.set_default_size (635, 393)
            self.textWin.set_size_request (635, 393)
            self.textWin.set_position (gtk.WIN_POS_CENTER)

            table.attach (a, 1, 2, 1, 2,
                          gtk.FILL | gtk.EXPAND,
                          gtk.FILL | gtk.EXPAND, 5, 5)

            self.textWin.set_border_width(0)
            addFrame(self.textWin)
            self.textWin.show_all()

        else:
            self.textWin.set_position (gtk.WIN_POS_CENTER)
            label = gtk.Label(_("Unable to load file!"))

            table.attach (label, 1, 2, 1, 2,
                          gtk.FILL | gtk.EXPAND, gtk.FILL | gtk.EXPAND, 5, 5)

            self.textWin.set_border_width(0)
            addFrame(self.textWin)
            self.textWin.show_all()

    def loadReleaseNotes(self):
	langList = self.langSearchPath + [ "" ]
        sourcepath = self.dispatch.method.getSourcePath()
        suffixList = []        
	for lang in langList:
	    if lang:
                suffixList.append("-%s.html" % (lang,))
                suffixList.append(".%s" % (lang,))
            else:
                suffixList.append(".html")
                suffixList.append("")
                
            for suffix in suffixList:
                fn = "%s/RELEASE-NOTES%s" % (sourcepath, suffix)
                if os.access(fn, os.R_OK):
                    file = open(fn, "r")
                    if suffix.endswith('.html'):
                        buffer = htmlbuffer.HTMLBuffer()
                        buffer.feed(utf8(file.read()))
                        self.releaseNotesBuffer = buffer.get_buffer()
                    else:
                        buffer = gtk.TextBuffer(None)
                        buffer.set_text(utf8(file.read()))
                        self.releaseNotesBuffer = buffer
                    file.close()
                    return
            
        buffer = gtk.TextBuffer(None)
        buffer.set_text(_("Release notes are missing.\n"))
        self.releaseNotesBuffer = buffer

    def handleRenderCallback(self):
        self.currentWindow.renderCallback()
        if flags.autostep:
            self.nextClicked()
        else:
            gtk.idle_remove(self.handle)

    def setScreen (self):
	(step, args) = self.dispatch.currentStep()
	if step is None:
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

        self.installFrame.set_label(ics.getTitle ())
        self.installFrame.add(new_screen)
        self.installFrame.show_all()

	self.handle = gtk.idle_add(self.handleRenderCallback)

        if self.reloadRcQueued:
            self.window.reset_rc_styles()
            self.reloadRcQueued = 0

        if self.displayHelp:
            self.refreshHelp()
            
    def destroyCurrentWindow(self):
        children = self.installFrame.get_children ()
        if children:
            child = children[0]
            self.installFrame.remove (child)
            child.destroy ()
	self.currentWindow = None

    def update (self, ics):
        self.installFrame.set_label (ics.getTitle ())

	prevButton = self.prevButtonStock
	nextButton = self.nextButtonStock

	if ics.getNextButton():
	    (icon, text) = ics.getNextButton()
            button = gtk.Button()
            box = gtk.HBox(gtk.FALSE, 0)
            image = gtk.Image()
            image.set_from_stock(icon, gtk.ICON_SIZE_BUTTON)
            box.pack_start(image, gtk.FALSE, gtk.FALSE)
            label = gtk.Label(_(text))
            label.set_property("use-underline", gtk.TRUE)
            box.pack_start(label, gtk.TRUE, gtk.TRUE)
            button.add(box)
	    button.connect("clicked", self.nextClicked)
	    button.show_all()
            button.label = label
            nextButton = button

        children = self.buttonBox.get_children()

        if not nextButton in children and self.nextButtonStock in children:
            pos = children.index(self.nextButtonStock)
            self.buttonBox.remove(self.nextButtonStock)
            self.buttonBox.pack_end(nextButton)
            self.buttonBox.reorder_child(nextButton, pos)
            self.nextButtonStock = nextButton

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
        self.debugButton = None

	self.stockButtons = (('gtk-go-back', "prevButtonStock",
                              N_("_Back"), self.prevClicked),
                             ('gtk-go-forward', "nextButtonStock",
                              N_("_Next"), self.nextClicked),
                             ('gtk-new', "releaseButton",
			       N_("_Release Notes"), self.releaseClicked),
                             ('gtk-help', "showHelpButton",
                              N_("Show _Help"), self.helpClicked),
                             ('gtk-help', "hideHelpButton",
                              N_("Hide _Help"), self.helpClicked),
                             ('gtk-execute', 'debugButton',
                              N_("_Debug"), self.debugClicked))

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
        # XXX hack: remove me when the accelerators work again.
        elif (event.keyval == gtk.keysyms.F12
              and self.currentWindow.getICS().getNextEnabled()):
            self.nextClicked()

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
        global mainWindow
        mainWindow = self.window
        self.window.set_events (gtk.gdk.KEY_RELEASE_MASK)

        if runres == '640x480':
            self.window.set_default_size (640, 480)
            self.window.set_size_request (640, 480)
        else:
            self.window.set_default_size (800, 600)
            self.window.set_size_request (800, 600)

        self.window.set_border_width (10)

	title = _("%s Installer") % (productName,)
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
			title = _("%s Installer on %s") % (productName, string.strip (netinf[1]))
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

        pixbuf = None
        # Create header at the top of the installer
        if runres != '640x480':
            for dir in ("/usr/share/anaconda/",
                        "",
                        "/tmp/updates"):
                try:
                    pixbuf = gtk.gdk.pixbuf_new_from_file(dir + image)
                    break
                except RuntimeError:
                    pass
                
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
        self.window.add_accel_group(group)
        self.nextButtonStock.add_accelerator('clicked', group,
                                             gtk.keysyms.F12,
                                             gtk.gdk.RELEASE_MASK, 0);

        # set up ctrl+alt+delete handler
        self.window.connect ("key-release-event", self.keyRelease)

        if DEBUG:
            self.buttonBox.add (self.debugButton)
            
        self.buttonBox.add (self.prevButtonStock)
        self.buttonBox.add (self.nextButtonStock)

	self.hbox = gtk.HBox ()
        self.hbox.set_border_width(5)
	self.hbox.pack_start (self.hideHelpButton, gtk.FALSE)
        self.hbox.set_spacing (25)
        self.hbox.pack_start (self.releaseButton, gtk.FALSE)
	self.hbox.pack_start (self.buttonBox)

        vbox.pack_end (self.hbox, gtk.FALSE)

        self.help = gtk.TextView()
        self.help.set_property("editable", gtk.FALSE)
        self.help.set_property("cursor_visible", gtk.FALSE)
        self.help.set_left_margin(10)
        self.help.set_wrap_mode(gtk.WRAP_WORD)

        self.displayHelp = gtk.TRUE
        self.helpState = gtk.TRUE

        self.helpFrame = gtk.Frame (_("Online Help"))
        self.box = gtk.VBox (gtk.FALSE, 0)
        self.box.set_spacing(0)

        self.box.pack_start (gtk.HSeparator (), gtk.FALSE)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.help)
        self.box.pack_start(sw, gtk.TRUE)
        
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
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(fn)
        except RuntimeError, msg:
            log("unable to read %s: %s", file, msg)
            return None
        source = gtk.IconSource()
        source.set_pixbuf(pixbuf)
        source.set_size(gtk.ICON_SIZE_DIALOG)
        source.set_size_wildcarded(gtk.FALSE)
        iconset = gtk.IconSet()
        iconset.add_source(source)
        p = gtk.image_new_from_icon_set(iconset, gtk.ICON_SIZE_DIALOG)
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

            if self.cw.configFileData.has_key("helptag"):
                helpTag = "-%s" % (self.cw.configFileData["helptag"],)
            else:
                helpTag = ""

            arch = "-%s" % (iutil.getArch(),)
            tags = [ "%s%s" % (helpTag, arch), "%s" % (helpTag,),
                     "%s" % (arch,), "" ]

            found = 0
            for path in self.searchPath:
                if found:
                    break
                for lang in langPath + ['C']:
                    if found:
                        break
                    for tag in tags:
                        try:
                            text = open("%s/help/%s/s1-help-screens-%s%s.html"
                                        % (path, lang, file, tag)).read ()
                            found = 1
                            break
                        except IOError:
                            continue
                if text:
                    break

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
