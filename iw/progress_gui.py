#
# progress_gui.py: install/upgrade progress window setup.
#
# Copyright 2000-2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, sys, string
import glob

import gtk
import pango

import gui
from flags import flags
from iw_gui import *
from rhpl.translate import _, N_
from constants import *
import language

import logging
log = logging.getLogger("anaconda")

class InstallProgressWindow (InstallWindow):
    windowTitle = N_("Installing Packages")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setPrevEnabled (False)
        ics.setNextEnabled (False)

        self._updateChange = 0.01

    def processEvents(self):
        gui.processEvents()

    def get_fraction(self):
        return self.progress.get_fraction()
    def set_fraction(self, pct):
        cur = self.get_fraction()
        if pct - cur > self._updateChange:
            self.progress.set_fraction(pct)
            self.processEvents()

    def set_label(self, txt):
        self.infolabel.set_markup(txt)
        self.infolabel.set_ellipsize(pango.ELLIPSIZE_END)
        self.processEvents()

    def set_text(self, txt):
        self.progress.set_text(txt)
        self.processEvents()

    def renderCallback(self):
        self.intf.icw.nextClicked()

    def _getRnotes(self):
        langs = []
        pixmaps = []
        if (os.environ.has_key('LANG')):
            langs = language.expandLangs(os.environ['LANG'])
        langs.append('')

        pixmaps = []
        paths = ("/tmp/product/pixmaps/rnotes/%s/*.png",
                 "/usr/share/anaconda/pixmaps/rnotes/%s/*.png")
        for p in paths:
            for lang in langs:
                path = p % lang
                pixmaps = glob.glob(path)
                if len(pixmaps) > 0:
                    break

        if len(pixmaps) > 0:
            files = pixmaps
        else:
            files = ["progress_first.png"]

        if self.intf.runres != '800x600':
            files = ["progress_first-lowres.png"]

        return files
        

    def getScreen (self, anaconda):
	self.intf = anaconda.intf
	if anaconda.dir == DISPATCH_BACK:
	    self.intf.icw.prevClicked()
	    return

        self.pixmaps = self._getRnotes()

	# Create vbox to contain components of UI
        vbox = gtk.VBox (False, 12)

        # Create rnote area
        self.adpix = None
        self.adbox = None
        pix = gui.readImageFromFile ("progress_first.png")
        if pix:
            frame = gtk.Frame()
            frame.set_shadow_type(gtk.SHADOW_NONE)
            box = gtk.EventBox()
            self.adpix = pix
            box.add(self.adpix)
            self.adbox = box
            frame.add(box)
            vbox.pack_start(frame);


	self.progress = gtk.ProgressBar()
        vbox.pack_start(self.progress, False)

        self.infolabel = gui.WrappingLabel("")
        vbox.pack_start(self.infolabel)

	# All done with creating components of UI
	self.intf.setPackageProgressWindow(self)
	anaconda.id.setInstallProgressClass(self)

	vbox.set_border_width(6)

	return vbox
