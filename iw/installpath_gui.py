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
from pixmapRadioButtonGroup_gui import pixmapRadioButtonGroup
from iw_gui import InstallWindow
from flags import flags
from rhpl.translate import _, N_

UPGRADE = 0
INSTALL = 1

CUSTOM = 2
WORKSTATION_GNOME = 3
WORKSTATION_KDE = 4
SERVER = 5

class InstallPathWindow (InstallWindow):		

    installTypes = installclass.availableClasses()
    htmlTag = "instpath"
    windowTitle = N_("Installation Type")

    def getNext(self):
	# Hack to let backing out of upgrades work properly
	#if self.flags.setupFilesystems() and self.id.fstab:
	    #self.id.fstab.turnOffSwap()

        selection = None
	for (name, object, pixmap) in self.installTypes:
	    if name == self.currentClassName:
		selection = object

	if not isinstance (self.id.instClass, selection):
	    c = selection(self.flags.expert)
	    c.setSteps(self.dispatch)
	    c.setInstallData(self.id)
	    needNewDruid = 1

    def optionToggled(self, widget, name):
	if widget.get_active():
	    self.currentClassName = name

    def createInstallTypeOption(self):
	r = pixmapRadioButtonGroup()

	for (name, object, pixmap) in self.installTypes:
	    descr = object.description
	    r.addEntry(name, _(name), pixmap=self.ics.readPixmap(pixmap),
		       descr=_(descr))

	return r



    # InstallPathWindow tag="instpath"
    def getScreen(self, dispatch, id, method, intf): 
        self.id = id
        self.intf = intf
	self.flags = flags
	self.method = method
	self.dispatch = dispatch
	
        vbox = gtk.VBox (gtk.FALSE, 10)
	vbox.set_border_width (8)

	r = self.createInstallTypeOption()
	b = r.render()

	r.setToggleCallback(self.optionToggled)

	# figure out current class as well as default
	defaultClass = None
	currentClass = None
	firstClass = None
	for (name, object, pixmap) in self.installTypes:
	    if firstClass is None:
		firstClass = object

	    if isinstance(id.instClass, object):
		currentClass = object

	    if object.default:
		defaultClass = object

	if currentClass is None:
	    if defaultClass is not None:
		self.currentClassName = defaultClass.name
	    else:
		self.currentClassName = firstClass.name
	else:
	    self.currentClassName = currentClass.name

	r.setCurrent(self.currentClassName)
	
	box = gtk.VBox (gtk.FALSE)
        box.pack_start(b, gtk.FALSE)

        vbox.pack_start (box, gtk.FALSE)
        return vbox


