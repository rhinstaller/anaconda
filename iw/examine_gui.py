#
# examine_gui.py: dialog to allow selection of a RHL installation to upgrade
#                 and if the user wishes to select individual packages.
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

import gtk
from iw_gui import *
from package_gui import *
from translate import _, N_
from upgrade import *

class UpgradeExamineWindow (InstallWindow):		

    windowTitle = N_("Upgrade Examine")
    htmlTag = "upgrade"

    def toggled (self, widget, newPart):
        if widget.get_active ():
	    self.root = newPart

    def getNext (self):
        self.id.upgradeRoot = [self.root]
	if self.individualPackages.get_active():
	    self.dispatch.skipStep("indivpackage", skip = 0)
	else:
	    self.dispatch.skipStep("indivpackage")

        return None

    #UpgradeExamineWindow tag = "upgrade"
    def getScreen (self, dispatch, intf, id, chroot):
        self.dispatch = dispatch
        self.intf = intf
        self.id = id
        self.chroot = chroot

        self.parts = self.id.upgradeRoot
        
	box = gtk.VBox (gtk.FALSE)
        if not self.parts:
            box.pack_start (gtk.Label (_("You don't have any Linux partitions."
                                        "\nYou can't upgrade this sytem!")),
                            gtk.FALSE)
            self.ics.setNextEnabled (gtk.FALSE)
            return box

        vbox = gtk.VBox (gtk.FALSE, 10)
	vbox.set_border_width (8)

        if self.parts and len (self.parts) > 1:
	    label = gtk.Label (_("Please select the device containing the root "
                                "filesystem: "))
	    label.set_alignment(0.0, 0.5)
	    box.pack_start(label, gtk.FALSE)

	    table = gtk.Table(2, 6)
	    table.set_border_width (10)
            box.pack_start (table, gtk.FALSE)
	    box.pack_start (gtk.HSeparator ())
	    spacer = gtk.Label("")
	    spacer.set_size_request(15, 1)
	    table.attach(spacer, 0, 1, 2, 4, gtk.FALSE)

            self.ics.setNextEnabled (gtk.TRUE)
            self.root = self.parts[0]
            group = None
	    row = 1
            for (part, filesystem) in self.parts:
                group = gtk.RadioButton (group, part)
                group.connect ("toggled", self.toggled, (part, filesystem))
		table.attach(group, 1, 2, row, row+1)
		row = row + 1

	    vbox.pack_start (box, gtk.FALSE)
        else:
            # if there is only one partition, go on.
            self.ics.setNextEnabled (gtk.TRUE)
            self.root = self.parts[0]
	    label = gtk.Label (_("Upgrading the Red Hat Linux installation "
                                "on partition /dev/%s")
                              % (self.root[0] + "\n\n",))
	    label.set_alignment(0.0, 0.5)
	    vbox.pack_start(label, gtk.FALSE)
            
        self.individualPackages = gtk.CheckButton (_("Customize packages to be "
                                                    "upgraded"))
        self.individualPackages.set_active (not dispatch.stepInSkipList("indivpackage"))
            
        align = gtk.Alignment (0.0, 0.5)
        align.add (self.individualPackages)

        vbox.pack_start (align, gtk.FALSE)

        return vbox
