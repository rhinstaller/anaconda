#
# installpath_gui.py: screen for selecting which installclass to use.
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

import installclass
import gtk
import gui
import iutil
from iw_gui import InstallWindow
from flags import flags
from rhpl.translate import _, N_

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
    if iutil.getArch() == "s390":
        htmlTag = "instpath-s390"
    else:
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

    def pixRadioButton (self, group, labelstr, pixmap, description=None):
	if pixmap:
	    pix = self.ics.readPixmap (pixmap)
	    xpad = 15
	else:
	    pix = None
	    xpad = 0

	hbox = gtk.HBox (gtk.FALSE, 18)
	if pix != None:
	    hbox.pack_start (pix, gtk.FALSE, gtk.FALSE, 0)
	label = gtk.Label("")
	label.set_line_wrap(gtk.TRUE)
	label.set_markup("<b>"+labelstr+"</b>")
	label.set_alignment (0.0, 0.5)
	if description is not None:
	    label.set_markup ("<b>%s</b>\n<small>%s</small>" %(labelstr,
                                                               description))
	    label.set_line_wrap(gtk.TRUE)
	    if  gtk.gdk.screen_width() > 640:
		wraplen = 350
	    else:
		wraplen = 250
		
	    label.set_size_request(wraplen, -1)
	label.set_use_markup (gtk.TRUE)
	hbox.pack_start (label, gtk.TRUE, gtk.TRUE, 0)
	button = gtk.RadioButton (group)
	button.add (hbox)
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

		box = gtk.VBox (gtk.FALSE, 9)
		group = None

		for obj in topButtons[item]:
		    name = obj.name
		    pixmap = obj.pixmap
		    descr = obj.description
		    group = self.pixRadioButton(group, _(name), pixmap,
						description=_(descr))
		    self.buttonToObject[group] = obj
		    buttons.append(group)
		    box.pack_start (group, gtk.FALSE)

		    if currentClass == obj:
			group.set_active(1)
			topLevelGroup.set_active(1)

	    self.topLevelButtonList.append((topLevelGroup, box, buttons))
	    topLevelGroup.connect("toggled", self.toggled)

	finalVBox = gtk.VBox(gtk.FALSE, 18)
	finalVBox.set_border_width (5)

	for (button, box, buttons) in self.topLevelButtonList:
	    vbox = gtk.VBox (gtk.FALSE, 9)
	    finalVBox.pack_start(vbox, gtk.FALSE, gtk.FALSE)
	    vbox.pack_start (button, gtk.FALSE, gtk.FALSE)
	    
	    if box:
		tmphbox = gtk.HBox(gtk.FALSE)

		crackhbox = gtk.HBox(gtk.FALSE)
		crackhbox.set_size_request(50, -1)

		tmphbox.pack_start(crackhbox, gtk.FALSE, gtk.FALSE)
		tmphbox.pack_start(box, gtk.TRUE, gtk.TRUE)
		vbox.pack_start(tmphbox, gtk.FALSE, gtk.FALSE)
		
                self.toggled(button)

	# make sure we get sensitivity setup right
	for (button, box, buttons) in self.topLevelButtonList:
	    if not box:
		continue
	    sensitive = button.get_active()
	    box.set_sensitive(sensitive)

        return finalVBox
