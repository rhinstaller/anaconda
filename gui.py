#
# gui.py - Graphical front end for anaconda
#
# Matt Wilson <msw@redhat.com>
# Michael Fulbright <msf@redhat.com>
#
# Copyright 1999-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
from flags import flags
os.environ["PYGTK_DISABLE_THREADS"] = "1"
os.environ["GNOME_DISABLE_CRASH_DIALOG"] = "1"

# we only want to enable the accessibility stuff if requested for now...
if flags.cmdline.has_key("dogtail"):
    os.environ["GTK_MODULES"] = "gail:atk-bridge"

import errno
import iutil
import string
import time
import isys
import sys
import parted
import gtk
import gtk.glade
import gobject
import htmlbuffer
import kudzu
import gettext
import warnings
from language import expandLangs
from constants import *
from network import hasActiveNetDev
import floppy
import rhpl
from threading import *

from rhpl.translate import _, N_

from release_notes import ReleaseNotesViewer

import logging
log = logging.getLogger("anaconda")

isys.bind_textdomain_codeset("redhat-dist", "UTF-8")

StayOnScreen = "stayOnScreen"
mainWindow = None

stepToClass = {
    "language" : ("language_gui", "LanguageWindow"),
    "keyboard" : ("kbd_gui", "KeyboardWindow"),
    "mouse" : ("mouse_gui", "MouseWindow"),
    "welcome" : ("welcome_gui", "WelcomeWindow"),
    "iscsi" : ("iscsi_gui", "iscsiWindow"),
    "zfcpconfig" : ("zfcp_gui", "ZFCPWindow"),
    "partitionmethod" : ("partmethod_gui", "PartitionMethodWindow"),
    "partition" : ("partition_gui", "PartitionWindow"),
    "parttype" : ("autopart_type", "PartitionTypeWindow"),
    "findinstall" : ("examine_gui", "UpgradeExamineWindow"),
    "addswap" : ("upgrade_swap_gui", "UpgradeSwapWindow"),
    "upgrademigratefs" : ("upgrade_migratefs_gui", "UpgradeMigrateFSWindow"),
    "bootloader": ("bootloader_main_gui", "MainBootloaderWindow"),
    "bootloaderadvanced": ("bootloader_advanced_gui", "AdvancedBootloaderWindow"),
    "upgbootloader": ("upgrade_bootloader_gui", "UpgradeBootloaderWindow"),
    "network" : ("network_gui", "NetworkWindow"),
    "timezone" : ("timezone_gui", "TimezoneWindow"),
    "accounts" : ("account_gui", "AccountWindow"),
    "tasksel": ("task_gui", "TaskWindow"),    
    "group-selection": ("package_gui", "GroupSelectionWindow"),
    "confirminstall" : ("confirm_gui", "InstallConfirmWindow"),
    "confirmupgrade" : ("confirm_gui", "UpgradeConfirmWindow"),
    "install" : ("progress_gui", "InstallProgressWindow"),
    "complete" : ("congrats_gui", "CongratulationWindow"),
}

if rhpl.getArch() == 's390':
    stepToClass["bootloader"] = ("zipl_gui", "ZiplWindow")

#
# Stuff for screenshots
#
screenshotDir = None
screenshotIndex = 0

def copyScreenshots():
    global screenshotIndex
    global screenshotDir
    
    # see if any screenshots taken
    if screenshotIndex == 0:
	return

    destDir = "/mnt/sysimage/root/anaconda-screenshots"
    if not os.access(destDir, os.R_OK):
	try:
	    os.mkdir(destDir, 0750)
	except:
	    window = MessageWindow("Error Saving Screenshot", 
				   _("An error occurred copying the "
				     "screenshots over."), type="warning")
	    return

    # copy all png's over
    for f in os.listdir(screenshotDir):
	(path, fname) = os.path.split(f)
	(b, ext) = os.path.splitext(f)
	if ext == ".png":
	    iutil.copyFile(screenshotDir + '/' + f,
			   destDir + '/' + fname)

    window = MessageWindow(_("Screenshots Copied"), 
			   _("The screenshots have been saved into the "
			     "directory:\n\n"
			     "\t/root/anaconda-screenshots/\n\n"
			     "You can access these when you reboot and "
			     "login as root."))



def takeScreenShot():
    global screenshotIndex
    global screenshotDir

    if screenshotDir is None:
	screenshotDir = "/tmp/ramfs/anaconda-screenshots"

	if  not os.access(screenshotDir, os.R_OK):
	    try:
		os.mkdir(screenshotDir)
	    except:
		screenshotDir = None
		return

    try:
	screenshot = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8,
				    gtk.gdk.screen_width(), gtk.gdk.screen_height())
	screenshot.get_from_drawable(gtk.gdk.get_default_root_window(),
				     gtk.gdk.colormap_get_system(),
				     0, 0, 0, 0,
				     gtk.gdk.screen_width(), gtk.gdk.screen_height())

	if screenshot:
	    while (1):
		sname = "screenshot-%04d.png" % ( screenshotIndex,)
		if not os.access(screenshotDir + '/' + sname, os.R_OK):
		    break

		screenshotIndex = screenshotIndex + 1
		if screenshotIndex > 9999:
		    log.error("Too many screenshots!")
		    return

	    screenshot.save (screenshotDir + '/' + sname, "png")
	    screenshotIndex = screenshotIndex + 1

	    window = MessageWindow(_("Saving Screenshot"), 
				   _("A screenshot named '%s' has been saved.") % (sname,) ,
				   type="ok")
    except:
	window = MessageWindow(_("Error Saving Screenshot"), 
			       _("An error occurred while saving "
				 "the screenshot.  If this occurred "
				 "during package installation, you may need "
				 "to try several times for it to succeed."),
			       type="warning")

		
def handleShiftPrintScrnRelease (window, event):
    if (event.keyval == gtk.keysyms.Print and event.state & gtk.gdk.SHIFT_MASK):
	takeScreenShot()
	    
	    
	

#
# HACK to make treeview work
# 
 
def setupTreeViewFixupIdleHandler(view, store):
    id = {}
    id["id"] = gobject.idle_add(scrollToIdleHandler, (view, store, id))

def scrollToIdleHandler((view, store, iddict)):
    if not view or not store or not iddict:
	return

    try:
	id = iddict["id"]
    except:
	return
    
    selection = view.get_selection()
    if not selection:
	return
    
    model, iter = selection.get_selected()
    if not iter:
	return

    path = store.get_path(iter)
    col = view.get_column(0)
    view.scroll_to_cell(path, col, True, 0.5, 0.5)

    if id:
	gobject.source_remove(id)

# setup globals
def processEvents():
    gtk.gdk.flush()
    while gtk.events_pending():
        gtk.main_iteration(False)

def partedExceptionWindow(exc):
    # if our only option is to cancel, let us handle the exception
    # in our code and avoid popping up the exception window here.
    if exc.options == parted.EXCEPTION_CANCEL:
        return parted.EXCEPTION_UNHANDLED
    log.critical("parted exception: %s: %s" %(exc.type_string,exc.message))
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

_busyCursor = 0

def setCursorToBusy(process=1):
    root = gtk.gdk.get_default_root_window()
    cursor = gtk.gdk.Cursor(gtk.gdk.WATCH)
    root.set_cursor(cursor)
    if process:
        processEvents()

def setCursorToNormal():
    root = gtk.gdk.get_default_root_window()
    cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
    root.set_cursor(cursor)

def rootPushBusyCursor(process=1):
    global _busyCursor
    _busyCursor += 1
    if _busyCursor > 0:
	setCursorToBusy(process)

def rootPopBusyCursor():
    global _busyCursor
    _busyCursor -= 1
    if _busyCursor <= 0:
	setCursorToNormal()

def getBusyCursorStatus():
    global _busyCursor
    
    return _busyCursor

class MnemonicLabel(gtk.Label):
    def __init__(self, text="", alignment = None):
        gtk.Label.__init__(self, "")
        self.set_text_with_mnemonic(text)
        if alignment is not None:
            apply(self.set_alignment, alignment)

class WrappingLabel(gtk.Label):
    def __init__(self, label=""):
        gtk.Label.__init__(self, label)
        self.set_line_wrap(True)
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

	data["window"].move(int(newx), int(newy))

def addFrame(dialog, title=None, showtitle = 1):
    # We don't add a Frame in rootpath mode, as we almost certainly have a window manager
    contents = dialog.get_children()[0]
    dialog.remove(contents)
    frame = gtk.Frame()
    frame.set_shadow_type(gtk.SHADOW_OUT)
    box = gtk.VBox()
    try:
	if title is None:
	    title = dialog.get_title()

	if title and not flags.rootpath:
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
	    titleBox = gtk.HBox(False, 5)
	    eventBox.add(titleBox)
	    eventBox.modify_bg(gtk.STATE_NORMAL,
                               eventBox.rc_get_style().bg[gtk.STATE_SELECTED])
            if showtitle:
                titlelbl = gtk.Label("")
                titlelbl.set_markup("<b>"+_(title)+"</b>")
                titlelbl.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse ("white"))
                titlelbl.set_property("ypad", 4)
                titleBox.pack_start(titlelbl)
            else:
                s = gtk.Label("")
                titleBox.pack_start(s)
	    box.pack_start(eventBox, False, False)
        elif flags.rootpath:
            dialog.set_title (title)
    except:
	pass
    
    frame2=gtk.Frame()
    frame2.set_shadow_type(gtk.SHADOW_NONE)
    frame2.set_border_width(4)
    frame2.add(contents)
    box.pack_start(frame2, True, True, padding=5)
    frame.add(box)
    frame.show()
    dialog.add(frame)

    # make screen shots work
    dialog.connect ("key-release-event", handleShiftPrintScrnRelease)


def findGladeFile(file):
    for dir in ("/mnt/source/RHupdates/", "/tmp/updates/",
                "ui/", "/usr/share/anaconda/ui/",
                "/usr/share/pirut/ui/"):
        fn = dir + file
        if os.access(fn, os.R_OK):
            return fn
    raise RuntimeError, "Unable to find glade file %s"  %(fn,)

def getGladeWidget(file, rootwidget, i18ndomain="anaconda"):
    f = findGladeFile(file)
    xml = gtk.glade.XML(f, root = rootwidget, domain = i18ndomain)
    w = xml.get_widget(rootwidget)
    if w is None:
        raise RuntimeError, "Unable to find root widget %s in %s" %(rootwidget, file)
    return (xml, w)

def findPixmap(file):
    for dir in ("/mnt/source/RHupdates/pixmaps/",
                 "/mnt/source/RHupdates/",
                 "/tmp/updates/pixmaps/", "/tmp/updates/",
                 "/tmp/product/pixmaps/", "/tmp/product/", "pixmaps/",
                 "/usr/share/anaconda/pixmaps/",
                 "/usr/share/pixmaps/",
                 "/usr/share/anaconda/", ""):
        fn = dir + file
        if os.access(fn, os.R_OK):
            return fn
    return None

def getPixbuf(file):
    fn = findPixmap(file)
    if not fn:
        log.error("unable to load %s" %(file,))
        return None
    
    try:
        pixbuf = gtk.gdk.pixbuf_new_from_file(fn)
    except RuntimeError, msg:
        log.error("unable to read %s: %s" %(file, msg))
        return None
    
    return pixbuf

def readImageFromFile(file, height = None, width = None, dither = None,
                      image = None):
    pixbuf = getPixbuf(file)
    if pixbuf is None:
        log.warning("can't find pixmap %s" %(file,))
        return None

    if (height is not None and width is not None
        and height != pixbuf.get_height()
        and width != pixbuf.get_width()):
        pixbuf = pixbuf.scale_simple(height, width,
                                     gtk.gdk.INTERP_BILINEAR)

    if image is None:
        p = gtk.Image()
    else:
        p = image
    if dither:
        (pixmap, mask) = pixbuf.render_pixmap_and_mask()
        pixmap.draw_pixbuf(gtk.gdk.GC(pixmap), pixbuf, 0, 0, 0, 0,
                           pixbuf.get_width(), pixbuf.get_height(),
                           gtk.gdk.RGB_DITHER_MAX, 0, 0)
        p = gtk.Image()
        p.set_from_pixmap(pixmap, mask)
    else:
        source = gtk.IconSource()
        source.set_pixbuf(pixbuf)
        source.set_size(gtk.ICON_SIZE_DIALOG)
        source.set_size_wildcarded(False)
        iconset = gtk.IconSet()
        iconset.add_source(source)
        p.set_from_icon_set(iconset, gtk.ICON_SIZE_DIALOG)

    return p
    

class WaitWindow:
    def __init__(self, title, text):
        if flags.rootpath:
            self.window = gtk.Window()
            self.window.set_decorated(False)
            # FIXME: we should really call set_transient_for
        else:
            self.window = gtk.Window(gtk.WINDOW_POPUP)
        self.window.set_title(title)
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.set_modal(True)
        label = WrappingLabel(text)
        box = gtk.Frame()
        box.set_border_width(10)
        box.add(label)
        box.set_shadow_type(gtk.SHADOW_NONE)
        self.window.add(box)
        addFrame(self.window, showtitle = 0)
	self.window.show_all()
        rootPushBusyCursor()
            
    def pop(self):
        self.window.destroy()
        rootPopBusyCursor()

class ProgressWindow:
    def __init__(self, title, text, total, updpct = 0.05):
        if flags.rootpath:
            self.window = gtk.Window()
            self.window.set_decorated(False)
            # FIXME: we should really call set_transient_for
            def no_delete (window, event):
                return True
            self.window.connect('delete-event', no_delete)
        else:
            self.window = gtk.Window(gtk.WINDOW_POPUP)
        self.window.set_title (title)
        self.window.set_position (gtk.WIN_POS_CENTER)
        self.window.set_modal (True)
        box = gtk.VBox (False, 5)
        box.set_border_width (10)

        label = WrappingLabel (text)
        label.set_alignment (0.0, 0.5)
        box.pack_start (label, False)
        
        self.total = total
        self.updpct = updpct
	self.progress = gtk.ProgressBar ()
        box.pack_start (self.progress, True)
        self.window.add(box)

        addFrame(self.window, showtitle = 0)
	self.window.show_all ()
        rootPushBusyCursor()

    def refresh(self):
        processEvents()

    def set (self, amount):
	# only update widget if we've changed by 5%
	curval = self.progress.get_fraction()
	newval = float (amount) / self.total
	if newval < 0.998:
	    if (newval - curval) < self.updpct and newval > curval:
		return
	self.progress.set_fraction (newval)
        processEvents ()        
    
    def pop(self):
        self.window.destroy ()
        rootPopBusyCursor()

class ScpWindow:
    def __init__(self, screen=None):
        self.scpxml = gtk.glade.XML(findGladeFile("scp.glade"),
                                    domain="anaconda")
        self.win = self.scpxml.get_widget("saveRemoteDlg")

        addFrame(self.win)
        self.win.show_all()
        self.window = self.win

    def getrc(self):
        if self.rc == 0:
            return None
        else:
            host = self.scpxml.get_widget("hostEntry")
            remotePath = self.scpxml.get_widget("remotePathEntry")
            userName = self.scpxml.get_widget("userNameEntry")
            password = self.scpxml.get_widget("passwordEntry")
            return (host.get_text(), remotePath.get_text(), userName.get_text(),
                    password.get_text())

    def run(self):
        self.rc = self.window.run()
    
    def pop(self):
        self.window.destroy()

class ExceptionWindow:
    def __init__ (self, shortTraceback, longTracebackFile=None, screen=None):
        # Get a bunch of widgets from the XML file.
        exnxml = gtk.glade.XML(findGladeFile("exn.glade"), domain="anaconda")
        self.win = exnxml.get_widget("exnDialog")
        vbox = exnxml.get_widget("mainVBox")
        exnView = exnxml.get_widget("exnView")
        expander = exnxml.get_widget("exnExpander")
        info = exnxml.get_widget("info")
        infoImage = exnxml.get_widget("infoImage")

        info.set_text(exceptionText)

        infoImage.clear()
        img = findPixmap("exception.png")
        if os.path.exists(img):
            infoImage.set_from_file(img)

        # Add the brief traceback message to the upper text view.
        textbuf = gtk.TextBuffer()
        textbuf.set_text(shortTraceback)

        # Remove the floppy button if we don't need it.
        if not floppy.hasFloppyDevice() and not flags.debug:
            buttonBox = exnxml.get_widget("buttonBox")
            floppyButton = exnxml.get_widget("floppyButton")
            buttonBox.remove(floppyButton)

        # Remove the remote button if there's no network.
        if not hasActiveNetDev() and not flags.debug:
            buttonBox = exnxml.get_widget("buttonBox")
            remoteButton = exnxml.get_widget("remoteButton")
            buttonBox.remove(remoteButton)

        # If there's an anacdump.txt file, add it to the lower view in the
        # expander.  If not, remove the expander.
        if longTracebackFile:
            try:
                f = open(longTracebackFile)
                lines = f.readlines()
                f.close()

                # Add text one line at a time to work around limits in
                # set_text.
                textbuf = gtk.TextBuffer()
                iter = textbuf.get_start_iter()

                for line in lines:
                    textbuf.insert(iter, line)

                exnView.set_buffer(textbuf)
            except IOError:
                log.error("Could not read %s, skipping" % longTraceback)
                vbox.remove(expander)
        else:
            vbox.remove(expander)

        addFrame(self.win)
        self.win.show_all ()
        self.window = self.win

    def run(self):
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
        # 1 is save to floppy
        if self.rc == 1:
            return 2
        # 2 is OK
        elif self.rc == 2:
            return 0
        # 3 is save to remote host
        elif self.rc == 3:
            return 3
    
    def pop(self):
        self.window.destroy()

class MessageWindow:
    def getrc (self):
        return self.rc
    
    def __init__ (self, title, text, type="ok", default=None, custom_buttons=None, custom_icon=None):
        if flags.autostep:
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

	# XXX - Messy - turn off busy cursor if necessary
	busycursor = getBusyCursorStatus()
	setCursorToNormal()
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

	# restore busy cursor
	if busycursor:
	    setCursorToBusy()
    
class InstallInterface:
    def __init__ (self):
        # figure out if we want to run interface at 800x600 or 640x480
        if gtk.gdk.screen_width() >= 800:
            self.runres = "800x600"
        else:
            self.runres = "640x480"
        root = gtk.gdk.get_default_root_window()
        cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
        root.set_cursor(cursor)

    def __del__ (self):
        pass

    def shutdown (self):
	pass

    def setPackageProgressWindow (self, ppw):
        self.ppw = ppw

    def waitWindow (self, title, text):
	return WaitWindow (title, text)

    def progressWindow (self, title, text, total, updpct = 0.05):
	return ProgressWindow (title, text, total, updpct)

    def packageProgressWindow (self, total, totalSize):
        self.ppw.setSizes (total, totalSize)
        return self.ppw

    def messageWindow(self, title, text, type="ok", default = None,
		     custom_buttons=None,  custom_icon=None):
        rc = MessageWindow (title, text, type, default,
			    custom_buttons, custom_icon).getrc()
        return rc

    def exceptionWindow(self, shortText, longTextFile):
        log.critical(shortText)
        win = ExceptionWindow (shortText, longTextFile)
        return win

    def scpWindow(self):
        return ScpWindow()

    def beep(self):
        gtk.gdk.beep()

    def kickstartErrorWindow(self, text):
        s = _("The following error was found while parsing your "
              "kickstart configuration:\n\n%s") %(text,)
        return self.messageWindow(_("Error Parsing Kickstart Config"),
                                  s,
                                  type = "custom",
                                  custom_buttons = [_("_Reboot")],
                                  custom_icon = "error")

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

    def run(self, id, dispatch):
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

        self.icw = InstallControlWindow (self, self.dispatch, id)
        self.icw.run (self.runres)

class TextViewBrowser(gtk.TextView):
    def __init__(self):
        self.hadj = None
        self.vadj = None

        gtk.TextView.__init__(self)
        self.set_property('editable', False)
        self.set_property('cursor_visible', False)
        self.set_left_margin(10)
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.connect('set-scroll-adjustments', self.cacheAdjustments)

    def swallowFocus(self, *args):
        self.emit_stop_by_name('focus-in-event')        
        
    def cacheAdjustments(self, view, hadj, vadj):
        self.hadj = hadj
        self.vadj = vadj

    def moveCursor(self, view, step, count, extend_selection):
        if step == gtk.MOVEMENT_DISPLAY_LINES:
            if count == -1 and self.vadj != None:
                self.vadj.value = max(self.vadj.value - self.vadj.step_increment,
                                      self.vadj.lower)
                self.vadj.value_changed()
            elif count == 1 and self.vadj != None:
                self.vadj.value = min(self.vadj.value + self.vadj.step_increment - 1,
                                      self.vadj.upper - self.vadj.page_increment - 1)
                self.vadj.value_changed()
        elif step == gtk.MOVEMENT_PAGES:
            if count == -1 and self.vadj != None:
                self.vadj.value = max(self.vadj.value - self.vadj.page_increment,
                                      self.vadj.lower)
                self.vadj.value_changed()
            elif count == 1 and self.vadj != None:
                self.vadj.value = min(self.vadj.value + self.vadj.page_increment - 1,
                                      self.vadj.upper - self.vadj.page_increment - 1)
                self.vadj.value_changed()

        self.emit_stop_by_name ('move-cursor')

    
class InstallControlWindow:
    def setLanguage (self):
	if not self.__dict__.has_key('window'): return

        self.reloadRcQueued = 1

        # need to reload our widgets
        self.setLtR()

        # reload the glade file, although we're going to keep our toplevel
        self.loadGlade()

	self.window.destroy()
	self.window = self.mainxml.get_widget("mainWindow")
        
        self.createWidgets()
        self.connectSignals()
	self.setScreen()
	self.window.show()

    def setLtR(self):
        ltrrtl = gettext.dgettext("gtk20", "default:LTR")
        if ltrrtl == "default:RTL":
            gtk.widget_set_default_direction (gtk.TEXT_DIR_RTL)
        elif ltrrtl == "default:LTR":
            gtk.widget_set_default_direction (gtk.TEXT_DIR_LTR)
        else:
            log.error("someone didn't translate the ltr bits right: %s" %(ltrrtl,))
            gtk.widget_set_default_direction (gtk.TEXT_DIR_LTR)            
        
    def prevClicked (self, *args):
	try:
	    self.currentWindow.getPrev ()
	except StayOnScreen:
	    return

	self.dispatch.gotoPrev()
	self.dir = DISPATCH_BACK

        self.setScreen ()

    def nextClicked (self, *args):
	try:
	    rc = self.currentWindow.getNext ()
	except StayOnScreen:
	    return

	self.dispatch.gotoNext()
	self.dir = DISPATCH_FORWARD

        self.setScreen ()

    def releaseNotesButtonClicked (self, widget):
	# we make cursor busy, on assumption when viewer app runs it will
	# make it normal
	setCursorToBusy()

	## this is the child executing the release notes viewer
	#child = os.fork()
	#if (child == 0):
	#    # close unneeded fd's
	#    for i in range(3,255):
	#        try:
	#            os.close(i)
	#        except:
	#            pass
        #
	#    win = ReleaseNotesViewer(self.id, self.dispatch)
	#    win.view()
	win = ReleaseNotesViewer(self.id, self.dispatch)

	## desensitize button bar at bottom of screen
        #self.mainxml.get_widget("buttonBar").set_sensitive(False)

	setCursorToNormal()

    def helpClicked (self, *args):
        self.displayHelp = not self.displayHelp
        self.refreshHelp()

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
        # make sure we're refreshing the help for an actual screen
        if self.currentWindow is None:
            return

        ics = self.currentWindow.getICS()

        # This became more complicated than I'd like.  The problem is that
        # displaying the help box and enabling the help buttons are
        # independent of each other.  The congrats screen has no help box
        # or button, while the progress screen has help but no buttons.
        # So it takes a couple variables to sort all this out.
        if ics.getHelpEnabled() and self.displayHelp:
            if ics.getHelpButtonEnabled():
                self.mainxml.get_widget("showHelpButton").hide()
                self.mainxml.get_widget("hideHelpButton").show()
                self.mainxml.get_widget("hideHelpButton").grab_focus()

            self.mainxml.get_widget("help").show_all()
            self.mainxml.get_widget("mainTable").set_homogeneous(True)
        else:
            if ics.getHelpButtonEnabled():
#                self.mainxml.get_widget("showHelpButton").show()
                self.mainxml.get_widget("hideHelpButton").hide()
#                self.mainxml.get_widget("showHelpButton").grab_focus()

            self.mainxml.get_widget("help").hide_all()
            self.mainxml.get_widget("mainTable").set_homogeneous(False)
        
        buffer = htmlbuffer.HTMLBuffer()
        buffer.feed(ics.getHTML(self.id.instLanguage.getCurrentLangSearchList()))
        textbuffer = buffer.get_buffer()
        self.help.set_buffer(textbuffer)
        # scroll to the top.  Do this with a mark so it's done in the idle loop
        iter = textbuffer.get_iter_at_offset(0)
        mark = textbuffer.create_mark("top", iter, False)
        self.help.scroll_to_mark(mark, 0.0, False, 0.0, 0.0)

    def handleRenderCallback(self):
        self.currentWindow.renderCallback()
        if flags.autostep:
	    if flags.autoscreenshot:
		# let things settle down graphically
		processEvents()
		time.sleep(1)
		takeScreenShot()
            self.nextClicked()
        else:
            gobject.source_remove(self.handle)

    def setScreen (self):
	(step, anaconda) = self.dispatch.currentStep()
	if step is None:
	    gtk.main_quit()
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
        while 1:
            try:
                exec s
                break
            except ImportError, e:
                print e
                win = MessageWindow(_("Error!"),
                                   _("An error occurred when attempting "
                                     "to load an installer interface "
                                     "component.\n\nclassName = %s") % (className,),
                                    type="custom", custom_icon="warning",
                                    custom_buttons=[_("_Exit"),
                                                    _("_Retry")])
                if not win.getrc():
                    if flags.rootpath:
                        msg =  _("The installer will now exit...")
                        buttons = [_("_Exit")]
                    else:
                        msg =  _("Your system will now be rebooted...")
                        buttons = [_("_Reboot")]

                    MessageWindow(_("Rebooting System"),
                                  msg,
                                  type="custom",
                                  custom_icon="warning",
                                  custom_buttons=buttons)
                    sys.exit(0)

	ics = InstallControlState (self)
	ics.setPrevEnabled(self.dispatch.canGoBack())
	self.destroyCurrentWindow()
        self.currentWindow = newScreenClass(ics)

        new_screen = self.currentWindow.getScreen(anaconda)
	if not new_screen:
            return

        self.update (ics)

        self.installFrame.add(new_screen)
        self.installFrame.show_all()

	self.handle = gobject.idle_add(self.handleRenderCallback)

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
        self.mainxml.get_widget("backButton").set_sensitive(ics.getPrevEnabled())
        self.mainxml.get_widget("nextButton").set_sensitive(ics.getNextEnabled())
        self.mainxml.get_widget("hideHelpButton").set_sensitive(ics.getHelpButtonEnabled())
        self.mainxml.get_widget("showHelpButton").set_sensitive(ics.getHelpButtonEnabled())

        if ics.getHelpEnabled() == False and self.displayHelp:
            self.refreshHelp()
        elif ics.getHelpEnabled() == True and not self.displayHelp:
            self.refreshHelp()
        if ics.getGrabNext():
            self.mainxml.get_widget("nextButton").grab_focus()

    def __init__ (self, ii, dispatch, id):
        self.reloadRcQueued = 0
        self.currentWindow = None
        self.ii = ii
        self.id = id
        self.dispatch = dispatch
        self.handle = None
        self.displayHelp = False

    def keyRelease (self, window, event):
        if ((event.keyval == gtk.keysyms.KP_Delete
             or event.keyval == gtk.keysyms.Delete)
            and (event.state & (gtk.gdk.CONTROL_MASK | gtk.gdk.MOD1_MASK))):
            gtk.main_quit()
            os._exit(0)
        # XXX hack: remove me when the accelerators work again.
        elif (event.keyval == gtk.keysyms.F12
              and self.currentWindow.getICS().getNextEnabled()):
            self.nextClicked()
	elif (event.keyval == gtk.keysyms.Print
	      and event.state & gtk.gdk.SHIFT_MASK):
	    takeScreenShot()

    def createWidgets (self):
        self.window.set_title(_("%s Installer") %(productName,))
        
        # FIXME: doesn't handle the lowres case
        i = self.mainxml.get_widget("headerImage")        
        p = readImageFromFile("anaconda_header.png", dither = False, image = i)
        if p is None:
            print _("Unable to load title bar")

        if flags.debug:
            self.mainxml.get_widget("debugButton").show_now()
        self.installFrame = self.mainxml.get_widget("installFrame")

        self.help = TextViewBrowser()
        self.mainxml.get_widget("helpView").add(self.help)
        self.help.show_all()

    def connectSignals(self):
        def noop (window, event):
            return True
        sigs = { "on_nextButton_clicked": self.nextClicked,
                 "on_rebootButton_clicked": self.nextClicked,                 
                 "on_backButton_clicked": self.prevClicked,
                 "on_hideHelpButton_clicked": self.helpClicked,
                 "on_showHelpButton_clicked": self.helpClicked,
                 "on_relnotesButton_clicked": self.releaseNotesButtonClicked,
                 "on_debugButton_clicked": self.debugClicked,
                 
                 "on_mainWindow_key_release_event": self.keyRelease,
                 "on_mainWindow_delete_event": noop,
                 }
        self.mainxml.signal_autoconnect(sigs)

    def loadGlade(self):
        self.mainxml = gtk.glade.XML(findGladeFile("anaconda.glade"),
                                     domain="anaconda")

    def setup_window (self, runres):
        self.setLtR()

        self.loadGlade()
        self.window = self.mainxml.get_widget("mainWindow")

        self.createWidgets()
        self.connectSignals()

        self.setScreen()
        self.window.show()
            
    def busyCursorPush(self):
        rootPushBusyCursor()
        
    def busyCursorPop(self):
        rootPopBusyCursor()
        
    def run (self, runres):
        self.setup_window(runres)
        gtk.main()
            
class InstallControlState:
    def __init__ (self, cw):
        self.searchPath = ("/mnt/source/RHupdates", "/tmp/updates",
                           "./", "/usr/share/anaconda/")
        self.cw = cw
        self.prevEnabled = True
        self.nextEnabled = True
        self.title = _("Install Window")
        self.html = ""
        self.htmlFile = None
        self.helpEnabled = True
        self.helpButtonEnabled = True
        self.grabNext = True

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
        self.helpButtonEnabled = value
        self.cw.update (self)

    def getHelpButtonEnabled (self):
        return self.helpButtonEnabled

    def findPixmap(self, file):
        warnings.warn("ics.findPixmap is deprecated, use gui.findPixmap instead", DeprecationWarning, stacklevel=2)
        return findPixmap(file)
        
    def readPixmap (self, file, height = None, width = None):
        warnings.warn("ics.readPixmap is deprecated, use gui.readImageFromFile instead", DeprecationWarning, stacklevel=2)        
        return readImageFromFile(file, height, width)

    def readPixmapDithered(self, file, height = None, width = None):
        warnings.warn("ics.readPixmapDithered is deprecated, use gui.readImageFromFile instead", DeprecationWarning, stacklevel=2)                
        return readImageFromFile(file, height, width, dither = 1)

    def readHTML (self, file):
        self.htmlFile = file

    def setHTML (self, text):
        self.html = text
        self.cw.update (self)

    def getHTML (self, langPath):
        text = None
        if self.htmlFile:
            file = self.htmlFile

            arch = "-%s" % (rhpl.getArch(),)
            tags = [ "%s" % (arch,), "" ]

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
                text = text.replace("@RHL@", productName)
                text = text.replace("@RHLVER@", productVersion)
                return text

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
