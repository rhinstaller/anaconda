#
# installpath_gui.py: screen for selecting which installclass to use.
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

import installclass
import gtk
from iw_gui import InstallWindow
from flags import flags
from translate import _, N_

UPGRADE = 0
INSTALL = 1

CUSTOM = 2
WORKSTATION_GNOME = 3
WORKSTATION_KDE = 4
SERVER = 5

def D_(x):
    return x

class InstallPathWindow (InstallWindow):		

    installTypes = installclass.availableClasses()
    htmlTag = "instpath"
    windowTitle = N_("Installation Type")

    def getNext(self):
	# Hack to let backing out of upgrades work properly
	#if self.flags.setupFilesystems() and self.id.fstab:
	    #self.id.fstab.turnOffSwap()

	for (button, box, buttons) in self.topLevelButtonList:
	    if not button.get_active(): continue

	    if buttons:
		for b in buttons:
		    if b.get_active(): selection = self.buttonToObject[b]
	    else:
		selection = self.buttonToObject[button]

	if not isinstance (self.id.instClass, selection):
	    c = selection(self.flags.expert)
	    c.setSteps(self.dispatch)
	    c.setInstallData(self.id)
	    needNewDruid = 1

    def toggled (self, widget):
        if not widget.get_active (): return

	for (button, box, buttons) in self.topLevelButtonList:
	    if not box: continue
	    sensitive = (button == widget)
	    box.set_sensitive(sensitive)

    def pixRadioButton (self, group, label, pixmap):
        pix = self.ics.readPixmap (pixmap)
        if pix:
            hbox = gtk.HBox (gtk.FALSE, 5)
            hbox.pack_start (pix, gtk.FALSE, gtk.FALSE, 0)
            label = gtk.Label (label)
            label.set_alignment (0.0, 0.5)
            hbox.pack_start (label, gtk.TRUE, gtk.TRUE, 15)
            button = gtk.RadioButton (group)
            button.add (hbox)
        else:
            button = gtk.RadioButton (group, label)
        return button

    # InstallPathWindow tag="instpath"
    def getScreen (self, dispatch, id, method, intf):
	self.dispatch = dispatch
	self.id = id
	self.flags = flags
	self.method = method
	self.intf = intf

	topButtons = {}

	defaultClass = None
	# this points to the class for the current install class object
	currentClass = None

        names = []
	for (name, object, pixmap) in self.installTypes:
	    (parentName, parentPixmap) = object.parentClass
	    if not topButtons.has_key(parentName):
		topButtons[parentName] = []
                names.append(parentName)

	    topButtons[parentName].append(object)

	    if isinstance(id.instClass, object):
		currentClass = object
	    if object.default:
		defaultClass = object

	if not currentClass:
	    currentClass = defaultClass

	topLevelGroup = None
	tableRows = 0
	# tuples of (button, box) (box may be None)
	self.topLevelButtonList = []
	self.buttonToObject = {}

	for item in names:
	    buttons = []
	    if len(topButtons[item]) == 1:
		name = topButtons[item][0].name
		pixmap = topButtons[item][0].pixmap
		topLevelGroup = self.pixRadioButton(topLevelGroup,
				    _(name), pixmap)
		self.buttonToObject[topLevelGroup] = topButtons[item][0]
		box = None

		if currentClass == topButtons[item][0]:
		    topLevelGroup.set_active(1)
	    else:
		(parentName, parentPixmap) = topButtons[item][0].parentClass

		topLevelGroup = self.pixRadioButton(topLevelGroup,
		    _(parentName), parentPixmap)

		box = gtk.VBox (gtk.FALSE, 0)
		box.set_usize(300, -1)
		group = None

		for obj in topButtons[item]:
		    name = obj.name
		    pixmap = obj.pixmap
		    group = self.pixRadioButton(group, _(name), pixmap)
		    self.buttonToObject[group] = obj
		    buttons.append(group)
		    box.pack_start (group, gtk.FALSE)

		    if currentClass == obj:
			group.set_active(1)
			topLevelGroup.set_active(1)

	    self.topLevelButtonList.append((topLevelGroup, box, buttons))
	    topLevelGroup.connect("toggled", self.toggled)

	    tableRows = tableRows + 1
	    if box:
		tableRows = tableRows + 1

	table = gtk.Table(2, tableRows + 1)
	row = 0

	for (button, box, buttons) in self.topLevelButtonList:
	    table.attach(button, 0, 3, row, row + 1,
                         xoptions = gtk.FILL | gtk.EXPAND)

	    #table.attach(align, 2, 3, row, row + 1, xoptions = gtk.FALSE)
	    row = row + 1

	    if box:
		table.attach(box, 1, 3, row, row + 1)
		row = row + 1

	box = gtk.VBox (gtk.FALSE, 5)
	box.pack_start(table, gtk.FALSE)
        box.set_border_width (5)

        return box
