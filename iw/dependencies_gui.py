#
# dependencies_gui.py: screen to allow resolution of unresolved dependencies.
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gobject
import gtk
from iw_gui import *
from rhpl.translate import _, N_

class UnresolvedDependenciesWindow (InstallWindow):

    windowTitle = N_("Unresolved Dependencies")
    htmlTag = "depend"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        self.dependRB = None
        self.causeRB = None
        self.ics = ics

    def getPrev (self):
	self.comps.setSelectionState(self.origSelection)
    
    def updateSize (self, *args):
        self.sizelabel.set_text (_("Total install size: %s") % self.comps.sizeStr())

    def installToggled (self, widget, *args):
        self.comps.selectDepCause (self.deps)
        if widget.get_active ():
            self.comps.selectDeps (self.deps)
        else:
            self.comps.unselectDeps (self.deps)
        self.updateSize ()

    def causeToggled (self, widget, *args):
        if widget.get_active ():
            self.comps.unselectDepCause (self.deps)
        else:
            self.comps.selectDepCause (self.deps)            
        self.updateSize ()

    def ignoreToggled (self, widget, *args):
        if widget.get_active ():
            self.comps.selectDepCause (self.deps)
            self.comps.unselectDeps (self.deps)            
        self.updateSize ()

    #UnresolvedDependenciesWindow tag="depend"
    def getScreen (self, comps, deps):
        self.ics.setHelpEnabled(True)
	self.deps = deps
	self.comps = comps

        sw = gtk.ScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

	store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        for (name, suggest) in self.deps:
	    iter = store.append()
	    store.set_value(iter, 0, name)
	    store.set_value(iter, 1, suggest)

	view = gtk.TreeView(store)
	col = gtk.TreeViewColumn(_("Package"), gtk.CellRendererText(), text=0)
	view.append_column(col)
	col = gtk.TreeViewColumn(_("Requirement"), gtk.CellRendererText(),
				 text=1)
	view.append_column(col)
        sw.add (view)

	# assume things will be selected -- that matches our default
	self.origSelection = self.comps.getSelectionState()
        self.comps.selectDeps (self.deps)

        self.sizelabel = gtk.Label("")
        self.sizelabel.set_alignment (1, .5)
        self.updateSize()

        rb = gtk.VBox (False)
        self.dependRB = gtk.RadioButton (None, _("_Install packages to "
                                                "satisfy dependencies"))
        
        self.causeRB  = gtk.RadioButton (self.dependRB, _("_Do not install "
                                                         "packages that "
                                                         "have dependencies"))
        
        self.ignoreRB = gtk.RadioButton (self.dependRB, _("I_gnore package "
                                                         "dependencies"))

        rb.pack_start (self.dependRB)
        rb.pack_start (self.causeRB)
        rb.pack_start (self.ignoreRB)
        rb.pack_start (self.sizelabel)

        self.dependRB.set_active (1)
        self.dependRB.connect('toggled', self.installToggled)
        self.causeRB.connect('toggled', self.causeToggled)
        self.ignoreRB.connect('toggled', self.ignoreToggled)

        box = gtk.VBox (False, 5)
        box.pack_start (sw, True)
        box.pack_start (rb, False)

        return box
