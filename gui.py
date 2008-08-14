#
# gui.py - Graphical front end for anaconda
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Matt Wilson <msw@redhat.com>
#            Michael Fulbright <msf@redhat.com>
#

import os
from flags import flags
os.environ["GNOME_DISABLE_CRASH_DIALOG"] = "1"

# we only want to enable the accessibility stuff if requested for now...
if flags.cmdline.has_key("dogtail"):
    os.environ["GTK_MODULES"] = "gail:atk-bridge"

import string
import time
import isys
import iutil
import sys
import parted
import shutil
import gtk
import gtk.glade
import gobject
import gettext
from language import expandLangs
from constants import *
from product import *
from network import hasActiveNetDev
import xutils
import imputil

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

isys.bind_textdomain_codeset("redhat-dist", "UTF-8")

class StayOnScreen(Exception):
    pass

mainWindow = None

stepToClass = {
    "language" : ("language_gui", "LanguageWindow"),
    "keyboard" : ("kbd_gui", "KeyboardWindow"),
    "welcome" : ("welcome_gui", "WelcomeWindow"),
    "zfcpconfig" : ("zfcp_gui", "ZFCPWindow"),
    "partitionmethod" : ("partmethod_gui", "PartitionMethodWindow"),
    "partition" : ("partition_gui", "PartitionWindow"),
    "parttype" : ("autopart_type", "PartitionTypeWindow"),
    "findinstall" : ("examine_gui", "UpgradeExamineWindow"),
    "addswap" : ("upgrade_swap_gui", "UpgradeSwapWindow"),
    "upgrademigratefs" : ("upgrade_migratefs_gui", "UpgradeMigrateFSWindow"),
    "bootloader": ("bootloader_main_gui", "MainBootloaderWindow"),
    "upgbootloader": ("upgrade_bootloader_gui", "UpgradeBootloaderWindow"),
    "network" : ("network_gui", "NetworkWindow"),
    "timezone" : ("timezone_gui", "TimezoneWindow"),
    "accounts" : ("account_gui", "AccountWindow"),
    "tasksel": ("task_gui", "TaskWindow"),    
    "group-selection": ("package_gui", "GroupSelectionWindow"),
    "install" : ("progress_gui", "InstallProgressWindow"),
    "complete" : ("congrats_gui", "CongratulationWindow"),
}

if iutil.isS390():
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
            shutil.copyfile(screenshotDir + '/' + f, destDir + '/' + fname)

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
        screenshotDir = "/tmp/anaconda-screenshots"

    if not os.access(screenshotDir, os.R_OK):
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
                                     gtk.gdk.screen_width(),
                                     gtk.gdk.screen_height())

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

def runningMiniWm():
    return xutils.getXatom("_ANACONDA_MINI_WM_RUNNING")

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
        widgetExpander(self)

def titleBarMousePressCB(widget, event, data):
    if event.type & gtk.gdk.BUTTON_PRESS:
        (x, y) = data["window"].get_position()
        data["state"] = 1
        data["button"] = event.button
        data["deltax"] = event.x_root - x
        data["deltay"] = event.y_root - y
    
def titleBarMouseReleaseCB(widget, event, data):
    if data["state"] and event.button == data["button"]:
        data["state"] = 0
        data["button"] = 0
        data["deltax"] = 0
        data["deltay"] = 0

def titleBarMotionEventCB(widget, event, data):
    if data["state"]:
        newx = event.x_root - data["deltax"]
        newy = event.y_root - data["deltay"]
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
    # We don't add a Frame in rootpath mode, as we almost certainly
    # have a window manager
    contents = dialog.get_children()[0]
    dialog.remove(contents)
    frame = gtk.Frame()
    if not flags.rootpath and runningMiniWm():
        frame.set_shadow_type(gtk.SHADOW_OUT)
    else:
        frame.set_shadow_type(gtk.SHADOW_NONE)
    box = gtk.VBox()
    try:
        if title is None:
            title = dialog.get_title()

        if title and not flags.rootpath and runningMiniWm():
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
            eventBox.modify_bg(gtk.STATE_NORMAL, eventBox.rc_get_style().bg[gtk.STATE_SELECTED])

            if showtitle:
                titlelbl = gtk.Label("")
                titlelbl.set_markup("<b>"+_(title)+"</b>")
                titlelbl.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse ("white"))
                titlelbl.set_property("ypad", 4)
                titleBox.pack_start(titlelbl)
            else:
                s = gtk.Label("")
                titleBox.pack_start(s)
            eventBox.show_all()
            box.pack_start(eventBox, False, False)
        else:
            dialog.set_title (title)
    except:
        pass

    frame2=gtk.Frame()
    frame2.set_shadow_type(gtk.SHADOW_NONE)
    frame2.set_border_width(4)
    frame2.add(contents)
    contents.show()
    frame2.show()
    box.pack_start(frame2, True, True, padding=5)
    box.show()
    frame.add(box)
    frame.show()
    dialog.add(frame)

    # make screen shots work
    dialog.connect ("key-release-event", handleShiftPrintScrnRelease)

def findGladeFile(file):
    for dir in ("/tmp/updates/", "ui/", "/usr/share/anaconda/ui/",
                "/usr/share/pirut/ui/"):
        fn = dir + file
        if os.access(fn, os.R_OK):
            return fn
    raise RuntimeError, "Unable to find glade file %s" % file

def getGladeWidget(file, rootwidget, i18ndomain="anaconda"):
    f = findGladeFile(file)
    xml = gtk.glade.XML(f, root = rootwidget, domain = i18ndomain)
    w = xml.get_widget(rootwidget)
    if w is None:
        raise RuntimeError, "Unable to find root widget %s in %s" %(rootwidget, file)

    return (xml, w)

def findPixmap(file):
    for dir in ( "/tmp/updates/pixmaps/", "/tmp/updates/",
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
        pixbuf = None
    
    return pixbuf

def readImageFromFile(file, width = None, height = None, dither = None,
                      image = None):
    pixbuf = getPixbuf(file)
    if pixbuf is None:
        log.warning("can't find pixmap %s" %(file,))
        return None

    if (width is not None and height is not None
        and height != pixbuf.get_height()
        and width != pixbuf.get_width()):
        pixbuf = pixbuf.scale_simple(width, height,
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
    def __init__(self, title, text, parent = None):
        if flags.rootpath or not runningMiniWm():
            self.window = gtk.Window()
            if parent:
                self.window.set_transient_for(parent)
        else:
            self.window = gtk.Window(gtk.WINDOW_POPUP)
            self.window.set_modal(True)
            
        self.window.set_title(title)
        self.window.set_position(gtk.WIN_POS_CENTER)
        label = WrappingLabel(text)
        box = gtk.Frame()
        box.set_border_width(10)
        box.add(label)
        box.set_shadow_type(gtk.SHADOW_NONE)
        self.window.add(box)
        addFrame(self.window, showtitle = 0)
        self.window.show_all()
        rootPushBusyCursor()

    def refresh(self):
        processEvents()
            
    def pop(self):
        self.window.destroy()
        rootPopBusyCursor()

class ProgressWindow:
    def __init__(self, title, text, total, updpct = 0.05, updsecs=10,
                 parent = None, pulse = False):
        if flags.rootpath or not runningMiniWm():
            self.window = gtk.Window()
            if parent:
                self.window.set_transient_for(parent)
        else:
            self.window = gtk.Window(gtk.WINDOW_POPUP)
            self.window.set_modal(True)            
        self.window.set_title (title)
        self.window.set_position (gtk.WIN_POS_CENTER)
        self.lastUpdate = int(time.time())
        self.updsecs = updsecs
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

    def pulse(self):
        self.progress.set_pulse_step(self.updpct)
        self.progress.pulse()
        processEvents()

    def set (self, amount):
        # only update widget if we've changed by 5% or our timeout has
        # expired
        curval = self.progress.get_fraction()
        newval = float (amount) / self.total
        then = self.lastUpdate
        now = int(time.time())
        if newval < 0.998:
            if ((newval - curval) < self.updpct and (now-then) < self.updsecs):
                return
        self.lastUpdate = now
        self.progress.set_fraction (newval)
        processEvents ()

    def pop(self):
        self.window.destroy ()
        rootPopBusyCursor()

class InstallKeyWindow:
    def __init__(self, anaconda, key):
        (keyxml, self.win) = getGladeWidget("instkey.glade", "instkeyDialog")
        if anaconda.id.instClass.instkeydesc is not None:
            w = keyxml.get_widget("instkeyLabel")
            w.set_text(_(anaconda.id.instClass.instkeydesc))

        if not anaconda.id.instClass.allowinstkeyskip:
            keyxml.get_widget("skipRadio").hide()

        keyName = _(anaconda.id.instClass.instkeyname)
        if anaconda.id.instClass.instkeyname is None:
            keyName = _("Installation Key")

        # set the install key name based on the installclass
        for l in ("instkeyLabel", "keyEntryLabel", "skipLabel"):
            w = keyxml.get_widget(l)
            t = w.get_text()
            w.set_text(t % {"instkey": keyName})

        self.entry = keyxml.get_widget("keyEntry")
        self.entry.set_text(key)
        self.entry.set_sensitive(True)

        self.keyradio = keyxml.get_widget("keyRadio")
        self.skipradio = keyxml.get_widget("skipRadio")
        self.rc = 0

        if anaconda.id.instClass.skipkey:
            self.skipradio.set_active(True)
        else:
            self.entry.grab_focus()

        self.win.connect("key-release-event", self.keyRelease)
        addFrame(self.win, title=keyName)        

    def keyRelease(self, window, event):
        # XXX hack: remove this, too, when the accelerators work again
        if event.keyval == gtk.keysyms.F12:
            window.response(1)

    def run(self):
        self.win.show()
        self.rc = self.win.run()
        return self.rc

    def get_key(self):
        if self.skipradio.get_active():
            return SKIP_KEY
        key = self.entry.get_text()
        key.strip()
        return key

    def destroy(self):
        self.win.destroy()

class luksPassphraseWindow:
    def __init__(self, passphrase=None, device = "", parent = None):
        luksxml = gtk.glade.XML(findGladeFile("lukspassphrase.glade"),
                                domain="anaconda",
                                root="luksPassphraseDialog")
        self.passphraseEntry = luksxml.get_widget("passphraseEntry")
        self.passphraseEntry.set_visibility(False)
        self.confirmEntry = luksxml.get_widget("confirmEntry")
        self.confirmEntry.set_visibility(False)
        self.win = luksxml.get_widget("luksPassphraseDialog")
        self.okButton = luksxml.get_widget("okbutton1")
        self.minimumLength = 8  # arbitrary; should probably be much larger
        if passphrase:
            self.initialPassphrase = passphrase
            self.passphraseEntry.set_text(passphrase)
            self.confirmEntry.set_text(passphrase)
        else:
            self.initialPassphrase = ""

        if device:
            deviceStr = " (%s)" % (device,)
        else:
            deviceStr = ""
        txt = _("Choose a passphrase for this encrypted device%s. "
                "You will be prompted for the passphrase during system "
                "boot.") % (deviceStr,)
        luksxml.get_widget("mainLabel").set_text(txt)

        if parent:
            self.win.set_transient_for(parent)

        addFrame(self.win)

    def run(self):
        self.win.show()
        while True:
            self.passphraseEntry.grab_focus()
            self.rc = self.win.run()
            if self.rc == gtk.RESPONSE_OK:
                passphrase = self.passphraseEntry.get_text()
                confirm = self.confirmEntry.get_text()
                if passphrase != confirm:
                    MessageWindow(_("Error with passphrase"),
                                  _("The passphrases you entered were "
                                    "different.  Please try again."),
                                  type = "ok", custom_icon = "error")
                    self.confirmEntry.set_text("")
                    continue

                if len(passphrase) < self.minimumLength:
                    MessageWindow(_("Error with passphrase"),
                                    _("The passphrase must be at least "
                                      "eight characters long."),
                                  type = "ok", custom_icon = "error")
                    self.passphraseEntry.set_text("")
                    self.confirmEntry.set_text("")
                    continue
            else:
                self.passphraseEntry.set_text(self.initialPassphrase)
                self.confirmEntry.set_text(self.initialPassphrase)

            return self.rc

    def getPassphrase(self):
        return self.passphraseEntry.get_text()

    def getrc(self):
        return self.rc

    def destroy(self):
        self.win.destroy()

class PassphraseEntryWindow:
    def __init__(self, device, parent = None):
        def ok(*args):
            self.win.response(gtk.RESPONSE_OK)
        xml = gtk.glade.XML(findGladeFile("lukspassphrase.glade"),
                            domain="anaconda",
                            root="passphraseEntryDialog")
        self.txt = _("Device %s is encrypted. In order to "
                     "access the device's contents during "
                     "installation you must enter the device's "
                     "passphrase below.") % (device,)
        self.win = xml.get_widget("passphraseEntryDialog")
        self.passphraseLabel = xml.get_widget("passphraseLabel")
        self.passphraseEntry = xml.get_widget("passphraseEntry2")
        self.globalcheckbutton = xml.get_widget("globalcheckbutton")

        if parent:
            self.win.set_transient_for(parent)

        self.passphraseEntry.connect('activate', ok)
        addFrame(self.win)

    def run(self):
        self.win.show()
        self.passphraseLabel.set_text(self.txt)
        self.passphraseEntry.grab_focus()
        rc = self.win.run()
        passphrase = None
        isglobal = False
        if rc == gtk.RESPONSE_OK:
            passphrase = self.passphraseEntry.get_text()
            isglobal = self.globalcheckbutton.get_active()

        self.rc = (passphrase, isglobal)
        return self.rc

    def getrc(self):
        return self.rc

    def destroy(self):
        self.win.destroy()

class SaveExceptionWindow:
    def __init__(self, anaconda, longTracebackFile=None, screen=None):
        exnxml = gtk.glade.XML(findGladeFile("exnSave.glade"), domain="anaconda")

        self.bugzillaNameEntry = exnxml.get_widget("bugzillaNameEntry")
        self.bugzillaPasswordEntry = exnxml.get_widget("bugzillaPasswordEntry")
        self.bugDesc = exnxml.get_widget("bugDesc")

        self.scpNameEntry = exnxml.get_widget("scpNameEntry")
        self.scpPasswordEntry = exnxml.get_widget("scpPasswordEntry")
        self.scpHostEntry = exnxml.get_widget("scpHostEntry")
        self.scpDestEntry = exnxml.get_widget("scpDestEntry")

        self.notebook = exnxml.get_widget("destNotebook")
        self.destCombo = exnxml.get_widget("destCombo")

        self.diskCombo = exnxml.get_widget("diskCombo")
        self.localChooser = exnxml.get_widget("localChooser")
        self.win = exnxml.get_widget("saveDialog")

        self.destCombo.connect("changed", self.combo_changed)

        self.destCombo.insert_text(2, _("Bugzilla (%s)") % bugUrl)

        cell = gtk.CellRendererText()
        self.diskCombo.pack_start(cell, True)
        self.diskCombo.set_attributes(cell, text=1)

        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)

        dests = anaconda.id.diskset.exceptionDisks(anaconda)

        if flags.livecdInstall:
            exnxml.get_widget("diskBox").hide()
            exnxml.get_widget("localBox").show()
            self.destCombo.set_active(0)
            self.notebook.remove_page(0)
            self.notebook.set_current_page(0)
        elif len(dests) > 0:
            for d in dests:
                iter = store.append(None)
                store[iter] = ("/dev/%s" % d[0], "/dev/%s - %s" % (d[0], d[1]))

            self.diskCombo.set_model(store)
            self.diskCombo.set_active(0)
            self.diskCombo.set_sensitive(True)

            self.destCombo.set_active(0)
            self.notebook.remove_page(1)
            self.notebook.set_current_page(0)
        else:
            self.destCombo.remove_text(1)
            self.destCombo.set_active(1)
            self.notebook.remove_page(1)
            self.notebook.set_current_page(1)

        addFrame(self.win)
        self.win.show()
        self.window = self.win

    def combo_changed(self, args):
        self.notebook.set_current_page(self.destCombo.get_active())

    def getrc(self):
        if self.rc == gtk.RESPONSE_OK:
            return EXN_OK
        elif self.rc == gtk.RESPONSE_CANCEL:
            return EXN_CANCEL

    def getDest(self):
        if self.saveToDisk():
            active = self.diskCombo.get_active()
            if active < 0:
                return None

            return self.diskCombo.get_model()[active][0]
        elif self.saveToLocal():
            return self.localChooser.get_filename()
        elif self.saveToRemote():
            return map(lambda e: e.get_text(), [self.scpNameEntry,
                                                self.scpPasswordEntry,
                                                self.scpHostEntry,
                                                self.scpDestEntry])
        else:
            return map(lambda e: e.get_text(), [self.bugzillaNameEntry,
                                                self.bugzillaPasswordEntry,
                                                self.bugDesc])

    def pop(self):
        self.window.destroy()

    def run(self):
        self.rc = self.window.run ()

    def saveToDisk(self):
        return self.destCombo.get_active() == 0

    def saveToLocal(self):
        return self.destCombo.get_active() == 0

    def saveToRemote(self):
        return self.destCombo.get_active() == 2

class MessageWindow:
    def getrc (self):
        return self.rc

    def __init__ (self, title, text, type="ok", default=None, custom_buttons=None, custom_icon=None, run = True, parent = None, destroyAfterRun = True):
        self.debugRid = None
        self.title = title
        if flags.autostep:
            self.rc = 1
            return
        self.rc = None
        self.framed = False
        self.doCustom = False

        style = 0
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
            self.doCustom = True
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

        self.dialog = gtk.MessageDialog(mainWindow, 0, style, buttons, str(text))

        if parent:
            self.dialog.set_transient_for(parent)

        if self.doCustom:
            rid=0
            for button in custom_buttons:
                if button == _("Cancel"):
                    tbutton = "gtk-cancel"
                else:
                    tbutton = button

                widget = self.dialog.add_button(tbutton, rid)
                rid = rid + 1

            if default is not None:
                defaultchoice = default
            else:
                defaultchoice = rid - 1
            if flags.debug and not _("_Debug") in custom_buttons:
                widget = self.dialog.add_button(_("_Debug"), rid)
                self.debugRid = rid
                rid += 1

        else:
            if default == "no":
                defaultchoice = 0
            elif default == "yes" or default == "ok":
                defaultchoice = 1
            else:
                defaultchoice = 0

        self.dialog.set_position (gtk.WIN_POS_CENTER)
        self.dialog.set_default_response(defaultchoice)
        if run:
            self.run(destroyAfterRun)

    def run(self, destroy = False):
        if not self.framed:
            addFrame(self.dialog, title=self.title)
            self.framed = True
        self.dialog.show_all ()

        # XXX - Messy - turn off busy cursor if necessary
        busycursor = getBusyCursorStatus()
        setCursorToNormal()
        self.rc = self.dialog.run()

        if not self.doCustom:
            if self.rc in [gtk.RESPONSE_OK, gtk.RESPONSE_YES]:
                self.rc = 1
            elif self.rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_NO,
                             gtk.RESPONSE_CLOSE, gtk.RESPONSE_DELETE_EVENT]:
                self.rc = 0

        if not self.debugRid is None and self.rc == self.debugRid:
            self.debugClicked(self)
            return self.run(destroy)

        if destroy:
            self.dialog.destroy()

        # restore busy cursor
        if busycursor:
            setCursorToBusy()

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
            isys.vtActivate (6)
        except SystemError:
            pass

class DetailedMessageWindow(MessageWindow):
    def __init__(self, title, text, longText=None, type="ok", default=None, custom_buttons=None, custom_icon=None, run=True, parent=None, destroyAfterRun=True):
        self.title = title

        if flags.autostep:
            self.rc = 1
            return

        self.debugRid = None
        self.rc = None
        self.framed = False
        self.doCustom = False

        if type == 'ok':
            buttons = ["gtk-ok"]
        elif type == 'warning':
            buttons = ["gtk-ok"]
        elif type == 'okcancel':
            buttons = ["gtk-ok", "gtk-cancel"]
        elif type == 'yesno':
            buttons = ["gtk-yes", "gtk-no"]
        elif type == 'custom':
            self.doCustom = True
            buttons = custom_buttons

        xml = gtk.glade.XML(findGladeFile("detailed-dialog.glade"), domain="anaconda")
        self.dialog = xml.get_widget("detailedDialog")
        self.mainVBox = xml.get_widget("mainVBox")
        self.hbox = xml.get_widget("hbox1")
        self.info = xml.get_widget("info")
        self.detailedExpander = xml.get_widget("detailedExpander")
        self.detailedView = xml.get_widget("detailedView")

        if parent:
            self.dialog.set_transient_for(parent)

        if custom_icon:
            img = gtk.Image()
            img.set_from_file(custom_icon)
            self.hbox.pack_start(img)
            self.hbox.reorder_child(img, 0)

        rid = 0
        for button in buttons:
            self.dialog.add_button(button, rid)
            rid += 1

        if self.doCustom:
            defaultchoice = rid-1
            if flags.debug and not _("_Debug") in buttons:
                self.dialog.add_button(_("_Debug"), rid)
                self.debugRid = rid
                rid += 1
        else:
            if default == "no":
                defaultchoice = 0
            elif default == "yes" or default == "ok":
                defaultchoice = 1
            else:
                defaultchoice = 0

        self.info.set_text(text)

        if longText:
            textbuf = gtk.TextBuffer()
            iter = textbuf.get_start_iter()

            for line in longText:
                textbuf.insert(iter, line)

            self.detailedView.set_buffer(textbuf)
        else:
            self.mainVBox.remove(self.detailedExpander)

        self.dialog.set_position (gtk.WIN_POS_CENTER)
        self.dialog.set_default_response(defaultchoice)

        if run:
            self.run(destroyAfterRun)

class MainExceptionWindow(DetailedMessageWindow):
    def __init__ (self, shortTraceback, longTracebackFile=None, screen=None):
        longText=None

        if longTracebackFile:
            try:
                f = open(longTracebackFile)
                longText = f.readlines()
                f.close()
            except:
                pass

        if flags.livecdInstall:
            custom_buttons = ["gtk-save", _("Exit installer")]
        else:
            custom_buttons = [_("Debug"), "gtk-save", _("Exit installer")]

        DetailedMessageWindow.__init__(self, _("Exception Occurred"),
                                       exceptionText, longText=longText,
                                       type="custom", run=False,
                                       custom_buttons=custom_buttons,
                                       custom_icon=findPixmap("exception.png"))

    def getrc (self):
        if flags.livecdInstall:
            if self.rc == 0:
                return EXN_SAVE
            elif self.rc == 1:
                return EXN_OK
        else:
            if self.rc == 0:
                try:
                    # switch to VC1 so we can debug
                    isys.vtActivate (1)
                except SystemError:
                    pass
                return EXN_DEBUG
            elif self.rc == 1:
                return EXN_SAVE
            elif self.rc == 2:
                return EXN_OK

class EntryWindow(MessageWindow):
    def __init__ (self, title, text, prompt, entrylength = None):
        mainWindow = None
        MessageWindow.__init__(self, title, text, type = "okcancel", custom_icon="question", run = False)
        self.entry = gtk.Entry()
        if entrylength:
            self.entry.set_width_chars(entrylength)
            self.entry.set_max_length(entrylength)

        # eww, eww, eww... but if we pack in the vbox, it goes to the right
        # place!
        self.dialog.child.pack_start(self.entry)

    def run(self):
        MessageWindow.run(self)
        if self.rc == 0:
            return None
        t = self.entry.get_text()
        t.strip()
        if len(t) == 0:
            return None
        return t

    def destroy(self):
        self.dialog.destroy()

class InstallInterface:
    def __init__ (self):
        self.icw = None

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

    def suspend(self):
        pass
    
    def resume(self):
        pass

    def enableNetwork(self, anaconda):
        from netconfig_dialog import NetworkConfigurator
        net = NetworkConfigurator(anaconda.id.network)
        ret = net.run()
        net.destroy()

        return ret != gtk.RESPONSE_CANCEL

    def setPackageProgressWindow (self, ppw):
        self.ppw = ppw

    def waitWindow (self, title, text):
        if self.icw:
            return WaitWindow (title, text, self.icw.window)
        else:
            return WaitWindow (title, text)

    def progressWindow (self, title, text, total, updpct = 0.05, pulse = False):
        if self.icw:
            return ProgressWindow (title, text, total, updpct,
                                   parent = self.icw.window, pulse = pulse)
        else:
            return ProgressWindow (title, text, total, updpct, pulse = pulse)

    def messageWindow(self, title, text, type="ok", default = None,
             custom_buttons=None,  custom_icon=None):
        if self.icw:
            parent = self.icw.window
        else:
            parent = None

        rc = MessageWindow (title, text, type, default,
                custom_buttons, custom_icon, run=True, parent=parent).getrc()
        return rc

    def createRepoWindow(self, anaconda):
        from task_gui import RepoCreator
        dialog = RepoCreator(anaconda)
        dialog.createDialog()
        dialog.run()

    def editRepoWindow(self, anaconda, repoObj):
        from task_gui import RepoEditor
        dialog = RepoEditor(anaconda, repoObj)
        dialog.createDialog()
        dialog.run()

    def methodstrRepoWindow(self, anaconda):
        from task_gui import RepoMethodstrEditor
        dialog = RepoMethodstrEditor(anaconda)
        dialog.createDialog()
        return dialog.run()

    def entryWindow(self, title, text, type="ok", entrylength = None):
        d = EntryWindow(title, text, type, entrylength)
        rc = d.run()
        d.destroy()
        return rc

    def detailedMessageWindow(self, title, text, longText=None, type="ok",
                              default=None, custom_buttons=None,
                              custom_icon=None):
        if self.icw:
            parent = self.icw.window
        else:
            parent = None

        rc = DetailedMessageWindow (title, text, longText, type, default,
                                    custom_buttons, custom_icon, run=True,
                                    parent=parent).getrc()
        return rc

    def mainExceptionWindow(self, shortText, longTextFile):
        log.critical(shortText)
        win = MainExceptionWindow (shortText, longTextFile)
        return win

    def saveExceptionWindow(self, anaconda, longTextFile):
        win = SaveExceptionWindow (anaconda, longTextFile)
        return win

    def getInstallKey(self, anaconda, key = ""):
        d = InstallKeyWindow(anaconda, key)
        rc = d.run()
        if rc == gtk.RESPONSE_CANCEL:
            ret = None
        else:
            ret = d.get_key()
        d.destroy()
        return ret

    def getLuksPassphrase(self, passphrase = "", device = ""):
        if self.icw:
            parent = self.icw.window
        else:
            parent = None

        d = luksPassphraseWindow(passphrase, device = device, parent = parent)
        rc = d.run()
        passphrase = d.getPassphrase()
        d.destroy()
        return passphrase

    def passphraseEntryWindow(self, device):
        if self.icw:
            parent = self.icw.window
        else:
            parent = None

        d = PassphraseEntryWindow(device, parent = parent)
        rc = d.run()
        d.destroy()
        return rc

    def beep(self):
        gtk.gdk.beep()

    def kickstartErrorWindow(self, text):
        s = _("The following error was found while parsing your "
              "kickstart configuration:\n\n%s") %(text,)
        return self.messageWindow(_("Error Parsing Kickstart Config"),
                                  s,
                                  type = "custom",
                                  custom_buttons = [_("_Exit installer")],
                                  custom_icon = "error")

    def getBootdisk (self):
        return None

    def run(self, anaconda):
        self.anaconda = anaconda

        # XXX x_already_set is a hack
        if anaconda.id.keyboard and not anaconda.id.x_already_set:
            anaconda.id.keyboard.activate()

        anaconda.id.fsset.registerMessageWindow(self.messageWindow)
        anaconda.id.fsset.registerProgressWindow(self.progressWindow)
        anaconda.id.fsset.registerWaitWindow(self.waitWindow)

        parted.exception_set_handler(partedExceptionWindow)

        self.icw = InstallControlWindow (self.anaconda)
        self.icw.run (self.runres)

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

        self.anaconda.dispatch.gotoPrev()
        self.setScreen ()

    def nextClicked (self, *args):
        try:
            rc = self.currentWindow.getNext ()
        except StayOnScreen:
            return

        self.anaconda.dispatch.gotoNext()
        self.setScreen ()

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
            isys.vtActivate (6)
        except SystemError:
            pass

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
        (step, anaconda) = self.anaconda.dispatch.currentStep()
        if step is None:
            gtk.main_quit()
            return

        if not stepToClass[step]:
            if self.anaconda.dispatch.dir == DISPATCH_FORWARD:
                return self.nextClicked()
            else:
                return self.prevClicked()

        (file, className) = stepToClass[step]
        newScreenClass = None

        while 1:
            try:
                found = imputil.imp.find_module(file)
                loaded = imputil.imp.load_module(className, found[0], found[1],
                                                 found[2])
                newScreenClass = loaded.__dict__[className]
                break
            except ImportError, e:
                print e
                win = MessageWindow(_("Error!"),
                                    _("An error occurred when attempting "
                                      "to load an installer interface "
                                      "component.\n\nclassName = %s")
                                    % (className,),
                                    type="custom", custom_icon="warning",
                                    custom_buttons=[_("_Exit"),
                                                    _("_Retry")])
                if not win.getrc():
                    if flags.rootpath:
                        msg =  _("The installer will now exit...")
                        buttons = [_("_Exit installer")]
                    else:
                        msg =  _("Your system will now be rebooted...")
                        buttons = [_("_Reboot")]

                    MessageWindow(_("Exiting"),
                                  msg,
                                  type="custom",
                                  custom_icon="warning",
                                  custom_buttons=buttons)
                    sys.exit(0)

        ics = InstallControlState (self)
        ics.setPrevEnabled(self.anaconda.dispatch.canGoBack())
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

        if ics.getGrabNext():
            self.mainxml.get_widget("nextButton").grab_focus()

        self.mainxml.get_widget("nextButton").set_flags(gtk.HAS_DEFAULT)

    def __init__ (self, anaconda):
        self.reloadRcQueued = 0
        self.currentWindow = None
        self.anaconda = anaconda
        self.handle = None

    def keyRelease (self, window, event):
        if ((event.keyval == gtk.keysyms.KP_Delete
             or event.keyval == gtk.keysyms.Delete)
            and (event.state & (gtk.gdk.CONTROL_MASK | gtk.gdk.MOD1_MASK))):
            self._doExit()
        # XXX hack: remove me when the accelerators work again.
        elif (event.keyval == gtk.keysyms.F12
              and self.currentWindow.getICS().getNextEnabled()):
            self.nextClicked()
        elif (event.keyval == gtk.keysyms.Print
              and event.state & gtk.gdk.SHIFT_MASK):
            takeScreenShot()

    def _doExit (self, *args):
        gtk.main_quit()
        os._exit(0)

    def _doExitConfirm (self, win = None, *args):
        # FIXME: translate the string
        win = MessageWindow(_("Exit installer"),
                            _("Are you sure you wish to exit the installation?"),
                            type="custom", custom_icon="question",
                            custom_buttons = [_("Cancel"), _("_Exit installer")],
                            parent = win)
        if win.getrc() == 0:
            return True
        self._doExit()

    def createWidgets (self):
        self.window.set_title(_("%s Installer") %(productName,))
        
        # FIXME: doesn't handle the lowres case
        i = self.mainxml.get_widget("headerImage")        
        p = readImageFromFile("anaconda_header.png",
                              dither = False, image = i)
        if p is None:
            print _("Unable to load title bar")
        if (gtk.gdk.screen_height() < 600) or \
           (gtk.gdk.screen_height() <= 675 and not runningMiniWm()):
            i.hide()
        else:
            self.window.set_size_request(800, 600)
            self.window.set_position(gtk.WIN_POS_CENTER_ALWAYS)

        if flags.debug:
            self.mainxml.get_widget("debugButton").show_now()
        self.installFrame = self.mainxml.get_widget("installFrame")

    def connectSignals(self):
        sigs = { "on_nextButton_clicked": self.nextClicked,
            "on_rebootButton_clicked": self._doExit,
            "on_closeButton_clicked": self._doExit,                 
            "on_backButton_clicked": self.prevClicked,
            "on_debugButton_clicked": self.debugClicked,
            "on_mainWindow_key_release_event": self.keyRelease,
            "on_mainWindow_delete_event": self._doExitConfirm, }
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
        self.cw = cw
        self.prevEnabled = True
        self.nextEnabled = True
        self.title = _("Install Window")
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

    def setScreenPrev (self):
        self.cw.prevClicked ()

    def setScreenNext (self):
        self.cw.nextClicked ()

    def setGrabNext (self, value):
        self.grabNext = value
        self.cw.update (self)

    def getGrabNext (self):
        return self.grabNext

    def getICW (self):
        return self.cw
