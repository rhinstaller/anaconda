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
from pixmapRadioButtonGroup_gui import pixmapRadioButtonGroup
from rhpl.translate import _, N_
from constants import *
from upgrade import *
from flags import flags

import upgradeclass
UpgradeClass = upgradeclass.InstallClass

UPGRADE_STR = "upgrade"
REINSTALL_STR = "reinstall"

class UpgradeExamineWindow (InstallWindow):		

    windowTitle = N_("Upgrade Examine")
    htmlTag = "upgrade"

    def getNext (self):
	if self.doupgrade:
            # set the install class to be an upgrade
            c = UpgradeClass(flags.expert)
            c.setSteps(self.dispatch)
            c.setInstallData(self.id)

	    rootfs = self.parts[self.upgradeoption.get_history()]
            self.id.upgradeRoot = [(rootfs[0], rootfs[1])]
            self.id.rootParts = self.parts

            if self.individualPackages.get_active():
                self.dispatch.skipStep("indivpackage", skip = 0)
            else:
                self.dispatch.skipStep("indivpackage")
            self.dispatch.skipStep("installtype", skip = 1)
        else:
            self.dispatch.skipStep("installtype", skip = 0)

        return None

    def createUpgradeOption(self):
	r = pixmapRadioButtonGroup()
	r.addEntry(UPGRADE_STR, N_("Upgrade an existing installation"),
		   pixmap=self.ics.readPixmap("upgrade.png"),
		   descr=_("Choose this option if you would like to upgrade your "
		   "existing Red Hat Linux system.  This option will preserve the "
		   "existing data on your drives."))

	r.addEntry(REINSTALL_STR, N_("Perform a fresh install of %s") % (productName,),
		   pixmap=self.ics.readPixmap("install.png"),
		   descr=_("Choose this option to install your system from scratch.  "
		   "Depending on how you choose to partition your system the existing data "
		   "on your drives may or may not be preserved."))

	return r

    def upgradeOptionsSetSensitivity(self, state):
	self.uplabel.set_sensitive(state)
	self.upgradeoption.set_sensitive(state)
	self.individualPackages.set_sensitive(state)

    def optionToggled(self, widget, name):
	if name == UPGRADE_STR:
	    self.upgradeOptionsSetSensitivity(widget.get_active())

	    self.doupgrade = widget.get_active()

    #UpgradeExamineWindow tag = "upgrade"
    def getScreen (self, dispatch, intf, id, chroot):
        self.dispatch = dispatch
        self.intf = intf
        self.id = id
        self.chroot = chroot

	self.doupgrade = dispatch.stepInSkipList("installtype")
        self.parts = self.id.rootParts 

        vbox = gtk.VBox (gtk.FALSE, 10)
	vbox.set_border_width (8)

	r = self.createUpgradeOption()
	b = r.render()
	if self.doupgrade:
	    r.setCurrent(UPGRADE_STR)
	else:
	    r.setCurrent(REINSTALL_STR)

	r.setToggleCallback(self.optionToggled)
	box = gtk.VBox (gtk.FALSE)
        box.pack_start(b, gtk.FALSE)

        vbox.pack_start (box, gtk.FALSE)
        self.root = self.parts[0]

        self.individualPackages = gtk.CheckButton (_("_Customize packages to be "
                                                    "upgraded"))
        self.individualPackages.set_active (not dispatch.stepInSkipList("indivpackage"))
	ipbox = gtk.HBox(gtk.FALSE)
	crackhbox = gtk.HBox(gtk.FALSE)
	crackhbox.set_size_request(70, -1)
	ipbox.pack_start(crackhbox, gtk.FALSE, gtk.FALSE)
	ipbox.pack_start(self.individualPackages, gtk.TRUE, gtk.TRUE)
	r.packWidgetInEntry(UPGRADE_STR, ipbox)


	# hack hack hackity hack
	upboxtmp = gtk.VBox(gtk.FALSE, 5)
	uplabelstr = _("The following Red Hat product will be upgraded:")
	self.uplabel = gtk.Label(uplabelstr)
	self.uplabel.set_alignment(0.0, 0.0)
	self.upgradeoption = gtk.OptionMenu()
	self.upgradeoptionmenu = gtk.Menu()
	for (part, filesystem, desc) in self.parts:
	    if (desc is None) or len(desc) < 1:
		desc = _("Unknown Linux system")
	    if part[:5] != "/dev/":
		devname = "/dev/" + part
	    else:
		devname = part
            item = gtk.MenuItem("")
	    itemlabel = item.get_children()[0]
	    itemlabel.set_markup("<small>%s (%s)</small>" %(desc, devname))
	    item.show()
	    self.upgradeoptionmenu.add(item)

	self.upgradeoption.set_menu(self.upgradeoptionmenu)
	upboxtmp.pack_start(self.uplabel)

	# more indentation
	box1 = gtk.HBox(gtk.FALSE)
	crackhbox = gtk.HBox(gtk.FALSE)
	crackhbox.set_size_request(35, -1)
	box1.pack_start(crackhbox, gtk.FALSE, gtk.FALSE)
	box1.pack_start(self.upgradeoption, gtk.FALSE, gtk.FALSE)
	upboxtmp.pack_start(box1, gtk.FALSE, gtk.FALSE)
#	upboxtmp.pack_start(self.upgradeoption, gtk.FALSE, gtk.FALSE)

	# hack indent it
	upbox = gtk.HBox(gtk.FALSE)

	crackhbox = gtk.HBox(gtk.FALSE)
	crackhbox.set_size_request(70, -1)

	upbox.pack_start(crackhbox, gtk.FALSE, gtk.FALSE)
#	upbox.pack_start(upboxtmp, gtk.TRUE, gtk.TRUE)
	upbox.pack_start(upboxtmp, gtk.FALSE, gtk.FALSE)

	# all done phew
	r.packWidgetInEntry(UPGRADE_STR, upbox)

	# set default
	if self.doupgrade:
	    idx = 0
	    for p in self.parts:
		if self.id.upgradeRoot[0][0] == p[0]:
		    self.upgradeoption.set_history(idx)
		    break
		idx = idx + 1

	self.upgradeOptionsSetSensitivity(self.doupgrade)

        return vbox
