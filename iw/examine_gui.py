#
# examine_gui.py: dialog to allow selection of a RHL installation to upgrade
#                 and if the user wishes to select individual packages.
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

import gtk
from iw_gui import *
from package_gui import *
from rhpl.translate import _, N_
from constants import *
from upgrade import *
from flags import flags

import upgradeclass
UpgradeClass = upgradeclass.InstallClass

class UpgradeExamineWindow (InstallWindow):		

    windowTitle = N_("Upgrade Examine")
    htmlTag = "upgrade"

    def toggled (self, widget, newPart):
        if widget.get_active ():
	    self.root = newPart
            if self.root is None:
                self.individualPackages.set_sensitive(gtk.FALSE)
            else:
                self.individualPackages.set_sensitive(gtk.TRUE)

    def getNext (self):
        if self.root is not None:
            # set the install class to be an upgrade
            c = UpgradeClass(flags.expert)
            c.setSteps(self.dispatch)
            c.setInstallData(self.id)

            self.id.upgradeRoot = [(self.root[0], self.root[1])]
            self.id.rootParts = self.parts
            if self.individualPackages.get_active():
                self.dispatch.skipStep("indivpackage", skip = 0)
            else:
                self.dispatch.skipStep("indivpackage")
            self.dispatch.skipStep("installtype", skip = 1)
        else:
            self.dispatch.skipStep("installtype", skip = 0)

        return None

    #UpgradeExamineWindow tag = "upgrade"
    def getScreen (self, dispatch, intf, id, chroot):
        self.dispatch = dispatch
        self.intf = intf
        self.id = id
        self.chroot = chroot

        self.parts = self.id.rootParts

	box = gtk.VBox (gtk.FALSE)

        vbox = gtk.VBox (gtk.FALSE, 10)
	vbox.set_border_width (8)

        label = gui.WrappingLabel (_("The following root partitions have been found "
                             "on your system.  FIXME: I NEED BETTER TEXT "
                             "HERE."))
        label.set_alignment(0.0, 0.5)
        box.pack_start(label, gtk.FALSE)

        group = None
        for (part, filesystem, desc) in self.parts:
            group = gtk.RadioButton (group, "/dev/%s (%s)" %(part, desc))
            group.connect ("toggled", self.toggled, part)
            box.pack_start(group, gtk.FALSE)

        group = gtk.RadioButton (group, "Don't upgrade")
        group.connect("toggled", self.toggled, None)
        box.pack_start(group, gtk.FALSE)

        vbox.pack_start (box, gtk.FALSE)
        self.root = self.parts[0]

        self.individualPackages = gtk.CheckButton (_("_Customize packages to be "
                                                    "upgraded"))
        self.individualPackages.set_active (not dispatch.stepInSkipList("indivpackage"))
            
        align = gtk.Alignment (0.0, 0.5)
        align.add (self.individualPackages)

        vbox.pack_end (align, gtk.FALSE)

        return vbox
