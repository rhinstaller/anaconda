#
# examine_gui.py: dialog to allow selection of a RHL installation to upgrade
#
# Copyright 2000-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gui
from iw_gui import *
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

    def getNext (self):
	if self.doupgrade:
            # set the install class to be an upgrade
            c = UpgradeClass(flags.expert)
            # hack, hack, hack...
            c.installkey = self.anaconda.id.instClass.installkey
            c.repopaths = self.anaconda.id.instClass.repopaths

            c.setSteps(self.anaconda.dispatch)
            c.setInstallData(self.anaconda)

	    rootfs = self.parts[self.upgradecombo.get_active()]
            self.anaconda.id.upgradeRoot = [(rootfs[0], rootfs[1])]
            self.anaconda.id.rootParts = self.parts

            self.anaconda.dispatch.skipStep("installtype", skip = 1)
            self.anaconda.id.upgrade = True
        else:
            self.anaconda.dispatch.skipStep("installtype", skip = 0)
            self.anaconda.id.upgrade = False
	
        return None

    def createUpgradeOption(self):
	r = pixmapRadioButtonGroup()
	r.addEntry(REINSTALL_STR,
                   _("_Install %s") %(productName,),
		   pixmap=gui.readImageFromFile("install.png"),
		   descr=_("Choose this option to freshly install your system. "                           "Existing software and data may be overwritten "
			   "depending on your configuration choices."))        
        
	r.addEntry(UPGRADE_STR,
                   _("_Upgrade an existing installation"),
		   pixmap=gui.readImageFromFile("upgrade.png"),
		   descr=_("Choose this option if you would like "
                           "to upgrade your existing %s system.  "
                           "This option will preserve the "
                           "existing data on your drives.") %(productName,))
        
	return r

    def upgradeOptionsSetSensitivity(self, state):
	self.uplabel.set_sensitive(state)
	self.upgradecombo.set_sensitive(state)

    def optionToggled(self, widget, name):
	if name == UPGRADE_STR:
	    self.upgradeOptionsSetSensitivity(widget.get_active())
	    self.doupgrade = widget.get_active()

    #UpgradeExamineWindow tag = "upgrade"
    def getScreen (self, anaconda):
        self.anaconda = anaconda

	if self.anaconda.id.upgrade == None:
	    # this is the first time we've entered this screen
	    self.doupgrade = self.anaconda.dispatch.stepInSkipList("installtype")
	else:
	    self.doupgrade = self.anaconda.id.upgrade

        self.parts = self.anaconda.id.rootParts 

        vbox = gtk.VBox (False, 10)
	vbox.set_border_width (8)

	r = self.createUpgradeOption()
	b = r.render()
	if self.doupgrade:
	    r.setCurrent(UPGRADE_STR)
	else:
	    r.setCurrent(REINSTALL_STR)

	r.setToggleCallback(self.optionToggled)
	box = gtk.VBox (False)
        box.pack_start(b, False)

        vbox.pack_start (box, False)
        self.root = self.parts[0]

	# hack hack hackity hack
	upboxtmp = gtk.VBox(False, 5)
	uplabelstr = _("The following installed system will be upgraded:")
	self.uplabel = gtk.Label(uplabelstr)
	self.uplabel.set_alignment(0.0, 0.0)
        model = gtk.ListStore(str)
	self.upgradecombo = gtk.ComboBox(model)

        cell = gtk.CellRendererText()
        self.upgradecombo.pack_start(cell, True)
        self.upgradecombo.set_attributes(cell, markup=0)

	for (part, filesystem, desc, label) in self.parts:
            iter = model.append()
	    if (desc is None) or len(desc) < 1:
		desc = _("Unknown Linux system")
	    if part[:5] != "/dev/":
		devname = "/dev/" + part
	    else:
		devname = part
            model[iter][0] = "<small>%s (%s)</small>" %(desc, devname)

	upboxtmp.pack_start(self.uplabel)

	# more indentation
	box1 = gtk.HBox(False)
	crackhbox = gtk.HBox(False)
	crackhbox.set_size_request(35, -1)
	box1.pack_start(crackhbox, False, False)
	box1.pack_start(self.upgradecombo, False, False)
	upboxtmp.pack_start(box1, False, False)

	# hack indent it
	upbox = gtk.HBox(False)

#	upbox.pack_start(upboxtmp, True, True)
	upbox.pack_start(upboxtmp, False, False)

	# all done phew
	r.packWidgetInEntry(UPGRADE_STR, upbox)

	# set default
	idx = 0
	for p in self.parts:
	    if self.anaconda.id.upgradeRoot[0][0] == p[0]:
	        self.upgradecombo.set_active(idx)
	        break
	    idx = idx + 1

	self.upgradeOptionsSetSensitivity(self.doupgrade)

        return vbox
