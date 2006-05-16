#
# mouse_gui.py: gui mouse configuration.
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
import string
import gobject
import gui
from iw_gui import *
from re import *
from rhpl.translate import _, N_
from flags import flags

class MouseWindow(InstallWindow):
    windowTitle = N_("Mouse Configuration")

    def getNext(self):
        self.mouse.setMouse(self.currentMouse,self.emulate3.get_active())

        mouse = self.mice[self.currentMouse]
        (make, model, gpmproto, xproto, device, emulate3) = mouse        

        if device == "ttyS":
            self.mouse.setDevice(self.serialDevice)
        else:
            self.mouse.setDevice(device)

	if self.flags.setupFilesystems:
	    self.mouse.setXProtocol()

        return None
    
    def selectDeviceType(self, selection, *args):
        if self.ignoreEvents:
            return
        (model, iter) = selection.get_selected()
        if iter:
            self.serialDevice = model.get_value(iter, 1)
            self.ics.setNextEnabled(True)
        else:
            self.serialDevice = None

    def selectMouseType(self, selection, *args):
        if self.ignoreEvents:
            return
        (model, iter) = selection.get_selected()
        if iter is None:
            return

        if model.iter_has_child(iter):
	    self.devview.get_selection().unselect_all()
	    self.devview.set_sensitive(False)
            self.emulate3.set_sensitive(False)
            self.ics.setNextEnabled(False)
	    return

	cur = model.get_value(iter, 1)

	self.emulate3.set_sensitive(True)
        (make, model, gpmproto, xproto, device, emulate) = self.mice[cur]

	if device == "ttyS":
	    self.setCurrent(self.serialDevice, cur, emulate, recenter=0)
	else:
	    self.setCurrent(device, cur, emulate, recenter=0)

    def setupDeviceList(self):
	deviceList = ((_("/dev/ttyS0 (COM1 under DOS)"), "ttyS0" ),
                      (_("/dev/ttyS1 (COM2 under DOS)"), "ttyS1" ),
                      (_("/dev/ttyS2 (COM3 under DOS)"), "ttyS2" ),
                      (_("/dev/ttyS3 (COM4 under DOS)"), "ttyS3" ))
        
        self.devstore = gtk.ListStore(gobject.TYPE_STRING,
                                      gobject.TYPE_STRING)
	for descrip, dev in deviceList:
            iter = self.devstore.append()
            self.devstore.set_value(iter, 0, descrip)
            self.devstore.set_value(iter, 1, dev)
        self.devstore.set_sort_column_id(0, gtk.SORT_ASCENDING)
        self.devview = gtk.TreeView(self.devstore)
        col = gtk.TreeViewColumn(_("_Device"), gtk.CellRendererText(), text=0)
        self.devview.append_column(col)
        selection = self.devview.get_selection()
        selection.connect("changed", self.selectDeviceType)

    def setupMice(self):
        self.mousestore = gtk.TreeStore(gobject.TYPE_STRING,
                                        gobject.TYPE_STRING)
        # go though and find all the makes that have more than 1 mouse
        toplevels = {}
        for key, value in self.mice.items():
            (make, model, gpmproto, xproto, device, emulate3) = value
            make = _(make)
            if toplevels.has_key(make):
                toplevels[make] = toplevels[make] + 1
            else:
                toplevels[make] = 1

        # for each toplevel that has more than one mouse, make a parent
        # node for it.
        for make, count in toplevels.items():
            if count > 1:
                parent = self.mousestore.append(None)
                self.mousestore.set_value(parent, 0, make)
                toplevels[make] = parent
            else:
                del toplevels[make]
                
        # now go and add each child node
        for key, value in self.mice.items():
            (make, model, gpmproto, xproto, device, emulate3) = value
            make = _(make)
            model = _(model)
            parent = toplevels.get(make)
            iter = self.mousestore.append(parent)
            # if there is a parent, put only the model in the tree
            if parent:
                self.mousestore.set_value(iter, 0, model)
            else:
                # otherwise, put the full device there.
                self.mousestore.set_value(iter, 0, "%s %s" % (make, model))
            self.mousestore.set_value(iter, 1, key)

        self.mousestore.set_sort_column_id(0, gtk.SORT_ASCENDING)
        self.mouseview = gtk.TreeView(self.mousestore)
        self.mouseview.set_property("headers-visible", True)
        col = gtk.TreeViewColumn(_("_Model"), gtk.CellRendererText(), text=0)
        self.mouseview.append_column(col)
        selection = self.mouseview.get_selection()
        selection.connect("changed", self.selectMouseType)

    def setCurrent(self, currentDev, currentMouse, emulate3, recenter=1):
        self.ignoreEvents = 1
        self.currentMouse = currentMouse

        parent = None
        iter = self.mousestore.get_iter_first()
	fndmouse = 0
        # iterate over the list, looking for the current mouse selection
        while iter:
            # if this is a parent node, get the first child and iter over them
            if self.mousestore.iter_has_child(iter):
                parent = iter
                iter = self.mousestore.iter_children(parent)
                continue
            # if it's not a parent node and the mouse matches, select it.
            elif self.mousestore.get_value(iter, 1) == currentMouse:
		if parent:
		    path = self.mousestore.get_path(parent)
		    self.mouseview.expand_row(path, True)
                selection = self.mouseview.get_selection()
                selection.unselect_all()
                selection.select_iter(iter)
                path = self.mousestore.get_path(iter)
                col = self.mouseview.get_column(0)
                self.mouseview.set_cursor(path, col, False)
                if recenter:
                    self.mouseview.scroll_to_cell(path, col, True,
                                                  0.5, 0.5)
		fndmouse = 1
                break
            # get the next row.
            iter = self.mousestore.iter_next(iter)
            # if there isn't a next row and we had a parent, go to the node
            # after the parent we've just gotten the children of.
            if not iter and parent:
                parent = self.mousestore.iter_next(parent)
                iter = parent

        # set up the device list if we have a serial port
	if currentDev and currentDev.startswith('ttyS'):
	    self.serialDevice = currentDev
            selection = self.devview.get_selection()
            path = (int(self.serialDevice[4]),)
            selection.select_path(path)
            col = self.devview.get_column(0)
            self.devview.set_cursor(path, col, False)
            if recenter:
                self.devview.scroll_to_cell(path, col, True, 0.5, 0.5)
            self.ics.setNextEnabled(True)
            self.devview.set_sensitive(True)
	elif currentDev:
	    self.devview.get_selection().unselect_all();
            self.devview.set_sensitive(False)
            self.ics.setNextEnabled(True)
        else:
	    # XXX - see if this is the 'No - mouse' case
	    if fndmouse:
		cur = self.mousestore.get_value(iter, 1)
                (make, model, gpmproto, xdev, device, emulate3) = self.mice[cur]                        
	    else:
		xdev = None

	    if xdev == "none":
		self.devview.get_selection().unselect_all();
		self.devview.set_sensitive(False)
		self.ics.setNextEnabled(True)
		    
	    else:
		# otherwise disable the list
		self.devview.get_selection().unselect_all();
		self.serialDevice = None
		self.ics.setNextEnabled(False)
		self.devview.set_sensitive(True)
            
        self.emulate3.set_active(emulate3)
        self.ignoreEvents = 0
        
    # MouseWindow tag="mouse"
    def getScreen(self, mouse):
	self.mouse = mouse
	self.flags = flags

        self.ignoreEvents = 0

	self.mice = mouse.mouseModels
        self.serialDevice = None

        currentDev = mouse.getDevice()
	currentMouse, emulate3 = mouse.getMouse()
        
        # populate the big widgets with the available selections
        self.setupMice()
        self.setupDeviceList()
        self.emulate3 = gtk.CheckButton(_("_Emulate 3 buttons"))
        self.setCurrent(currentDev, currentMouse, emulate3)

        # set up the box for this screen
        box = gtk.VBox(False, 5)
        box.set_border_width(5)

        # top header, includes graphic and instructions
        hbox = gtk.HBox(False, 5)
        pix = gui.readImageFromFile ("gnome-mouse.png")
        if pix:
            a = gtk.Alignment()
            a.add(pix)
            a.set(0.0, 0.0, 0.0, 0.0)
            hbox.pack_start(a, False)
        label = gui.MnemonicLabel(_("Select the appropriate mouse for the system."))
        label.set_line_wrap(True)
        label.set_size_request(350, -1)
        hbox.pack_start(label, False)
        box.pack_start(hbox, False)

        # next is the mouse tree
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.add(self.mouseview)
        box.pack_start(sw)
        label.set_mnemonic_widget(self.mouseview)

	gui.setupTreeViewFixupIdleHandler(self.mouseview, self.mousestore)

        # then the port list
        serial_sw = gtk.ScrolledWindow()
        serial_sw.set_shadow_type(gtk.SHADOW_IN)
        serial_sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
        serial_sw.add(self.devview)
        box.pack_start(serial_sw, False)

        # finally the emulate 3 buttons
        box.pack_start(self.emulate3, False)
        return box

