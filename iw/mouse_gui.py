from gtk import *

# must replace with explcit form so update disks will work
from iw_gui import *
from string import *
from re import *
import tree
from translate import _

class MouseWindow (InstallWindow):

    def reduce_leafs (self, a):
        if a == (): return a
        if len (a) > 1 and isinstance (a[1], type (())) and len (a[1]) == 1:
            return ("%s - %s" % (a[0], a[1][0]),) + self.reduce_leafs (a[2:])
        return (a[0],) + self.reduce_leafs (a[1:])

    def build_ctree (self, list, cur_parent = None, prev_node = None):
        if (list == ()): return
        
        if (len (list) > 1 and isinstance (list[1], type (()))): 
	    leaf = FALSE
        else:
	    leaf = TRUE
    
        if isinstance (list[0], type (())):
            self.build_ctree (list[0], prev_node, None)
            self.build_ctree (list[1:], cur_parent, None)
        else:
            index = find (list[0], " - ")
            if index != -1:
                list_item = list[0][0:index] + list[0][index+2:]
            else:
                list_item = list[0]
            node = self.ctree.insert_node (cur_parent, None, (list_item,), 2, is_leaf=leaf)
            self.ctree.node_set_row_data (node, list[0])
            self.build_ctree (list[1:], cur_parent, node)

    def selectMouse (self, ctreeNode, mouseNode):
        if len (ctreeNode) == 0 or len (mouseNode) == 0: return
        
        nodeLabel = self.ctree.get_node_info (ctreeNode[0])[0]
        if nodeLabel == mouseNode[0]:
            if len (mouseNode) == 1:
                self.ctree.select (ctreeNode[0])
                return
            else:
                self.ctree.expand (ctreeNode[0])
                self.selectMouse (ctreeNode[0].children, mouseNode[1:])
        else:
            self.selectMouse (ctreeNode[1:], mouseNode)

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Mouse Configuration"))
        ics.readHTML ("mouse")
        ics.setNextEnabled (TRUE)

    def getCurrentKey (self):
        if not len (self.ctree.selection): return
        name = ""
        node = self.ctree.selection[0]
        while node:
            name = self.ctree.node_get_row_data (node) + name
            node = node.parent
            if node:
                name = " - " + name

	if self.locList.selection:
	    self.serialDevice = self.locList.get_text (self.locList.selection[0], 0)
	# otherwise, just leave the old selection in place

        return name

    def getNext (self):
	if not self.__dict__.has_key("availableMice"): return
	cur = self.getCurrentKey()
	(gpm, xdev, device, emulate) = self.availableMice[cur]
        self.todo.mouse.set (cur, self.emulate3.get_active ())
	if (device == "ttyS"):
	    self.todo.mouse.setDevice(self.serialDevice)
	else:
	    self.todo.mouse.setDevice(device)

        self.todo.mouse.setXProtocol ()

        return None
    
    def selectDeviceType(self, *args):
	self.ics.setNextEnabled (TRUE)

    def selectMouseType (self, widget, node, *args):
        if not node.is_leaf:
	    self.locList.unselect_all ()
	    self.locList.set_sensitive (FALSE)
            self.emulate3.set_sensitive (FALSE)
            self.ics.setNextEnabled (FALSE)
	    return

	cur = self.getCurrentKey()
	if (not self.availableMice.has_key(cur)):
            self.ics.setNextEnabled (FALSE)
	    return

        self.emulate3.set_sensitive (TRUE)
	(gpm, xdev, device, emulate) = self.availableMice[cur]
        self.emulate3.set_active (emulate)
	if device == "ttyS":
	    if (self.serialDevice):
		self.locList.select_row(int(self.serialDevice[4]), 1)
		self.ics.setNextEnabled (TRUE)
	    else:
		self.locList.unselect_all()
		self.ics.setNextEnabled (FALSE)

	    self.locList.set_sensitive (TRUE)
	else:
	    self.locList.unselect_all()
	    self.locList.set_sensitive(FALSE)
	    self.ics.setNextEnabled (TRUE)

    def getScreen (self):
	self.availableMice = self.todo.mouse.available()
        sorted_mice_keys = self.availableMice.keys()
        sorted_mice_keys.sort ()

        currentDev = self.todo.mouse.getDevice ()
	(currentMouse, emulate3) = self.todo.mouse.get ()

	deviceList = [ (_("/dev/ttyS0 (COM1 under DOS)"), "ttyS0" ),
    		       (_("/dev/ttyS1 (COM2 under DOS)"), "ttyS1" ),
		       (_("/dev/ttyS2 (COM3 under DOS)"), "ttyS2" ),
		       (_("/dev/ttyS3 (COM4 under DOS)"), "ttyS3" ) ]

        self.emulate3 = GtkCheckButton (_("Emulate 3 Buttons"))
        box = GtkVBox (FALSE)
        
        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.locList = GtkCList (2, (_("Port"), _("Device")))
        self.locList.set_selection_mode (SELECTION_SINGLE)

	for (descrip, dev) in deviceList:
	    self.locList.append((dev, descrip))

        self.locList.columns_autosize ()
        self.locList.set_column_resizeable (0, FALSE)
        self.locList.column_title_passive (0)
        self.locList.column_title_passive (1)
        self.locList.set_border_width (5)

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.ctree = GtkCTree (1)

        groups = ()
        for x in sorted_mice_keys:
            groups = tree.merge (groups, string.split (x, " - ", 1))
        groups = self.reduce_leafs (groups)

        self.build_ctree (groups)
        self.ctree.set_selection_mode (SELECTION_BROWSE)
        self.ctree.columns_autosize ()
        self.ctree.connect ("tree_select_row", self.selectMouseType)
        self.locList.connect ("select_row", self.selectDeviceType)
	self.locList.set_sensitive(FALSE)

        sw.add (self.ctree)
	
	if (currentDev and currentDev[0:4] == "ttyS"):
	    self.serialDevice = currentDev
	    self.locList.select_row(int(self.serialDevice[4]), 1)
	else:
	    self.locList.unselect_all();
	    self.serialDevice = None

	splitv = string.split (currentMouse, " - ", 1)
	nodes = self.ctree.base_nodes ()
        # do a simple search on the root nodes, since leaf reduction creates
        # a special case
        found = 0
	for x in nodes:
            if self.ctree.get_node_info (x)[0] == "%s %s" % tuple (splitv):
                found = 1
                self.ctree.select (x)
                break
        if not found:
            self.selectMouse (nodes, splitv)

        self.emulate3.set_active (emulate3)

        align = GtkAlignment ()
        align.add (self.emulate3)
        align.set_border_width (5)

        im = self.ics.readPixmap ("gnome-mouse.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            box.pack_start (a, FALSE)
            
        box.pack_start (sw)
        box.pack_start (self.locList, FALSE)
        box.pack_start (align, FALSE)

        return box

