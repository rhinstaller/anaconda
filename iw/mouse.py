from gtk import *
from iw import *
from string import *
from re import *

class MouseWindow (InstallWindow):

    def build_tree (self, x):
        if (x == ()): return ()
        if (len (x) == 1): return (x[0],)
        else: return (x[0], self.build_tree (x[1:]))

    def reduce_leafs (self, a):
        if a == (): return a
        if len (a) > 1 and isinstance (a[1], type (())) and len (a[1]) == 1:
            return ("%s - %s" % (a[0], a[1][0]),) + self.reduce_leafs (a[2:])
        return (a[0],) + self.reduce_leafs (a[1:])

    def merge (self, a, b):
        if a == (): return self.build_tree (b)
        if b == (): return a
        if b[0] == a[0]:
            if len (a) > 1 and isinstance (a[1], type (())):
                return (a[0],) + (self.merge (a[1], b[1:]),) + a[2:]
            elif b[1:] == (): return a
            else: return (a[0],) + (self.build_tree (b[1:]),) + a[1:]
        else:
            return (a[0],) + self.merge (a[1:], b)

    def build_ctree (self, list, cur_parent = None, prev_node = None):
        if (list == ()): return
        
        if (len (list) > 1 and isinstance (list[1], type (()))): leaf = FALSE
        else: leaf = TRUE
    
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

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Mouse Configuration")
        ics.setHTML ("<HTML><BODY>Select your mouse."
                     "</BODY></HTML>")
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

        dev = self.locList.get_text (self.locList.selection[0], 1)
        if not find (dev, "psaux"):
            name = name + " (PS/2)"
        elif not find (dev, "ttyS"):
            name = name + " (serial)"

        return name

    def getNext (self):
        self.todo.mouse.set (self.getCurrentKey ())
        return None

    def locSelect (self, widget, row, *args):
        if self.todo.mouse.available ().has_key (self.getCurrentKey ()):
            self.ics.setNextEnabled (TRUE)
        else:
            self.ics.setNextEnabled (FALSE)

    def select (self, widget, node, *args):
        if node.is_leaf and self.todo.mouse.available ().has_key (self.getCurrentKey ()):
            self.ics.setNextEnabled (TRUE)
        else:
            self.ics.setNextEnabled (FALSE)

    def getScreen (self):
        sorted_mice_keys = self.todo.mouse.available ().keys ()
        sorted_mice_keys.sort ()

        # build a dictionary of device : device name
        devs = {}
	for x in map (lambda x, dict=self.todo.mouse.available (): (dict[x][2], x),
                      self.todo.mouse.available ().keys ()):
            if not devs.has_key (x[0]):
                devs[x[0]] = x[1]
        
        devNames = { "psaux"    : (0, "PS/2"),
                     "ttyS"     : (1, "COM"),
                     "atibm"    : (2, "ATI Bus"),
                     "logibm"   : (2, "Logitech Bus"),
                     "inportbm" : (2, "Microsoft Bus") }

        devList = []
        for x in devs.keys ():
            # handle the special case of COM ports
            if x == "ttyS":
                for i in range (0, 4):
                    devList.append ((devNames[x][0], "%s %i" % (devNames[x][1], i+1), "%s%i" % (x, i)))
                continue

            if devNames.has_key (x):
                devList.append ((devNames[x][0], devNames[x][1], x))
            else:
                devList.append ((999, "Unknown Port", x))

	devList.sort ()

        box = GtkVBox (FALSE, 5)
        
        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.locList = GtkCList (2, ("Port", "Device"))
        self.locList.set_selection_mode (SELECTION_BROWSE)

        map (lambda x, self=self: self.locList.append (x[1:]), devList)

        self.locList.columns_autosize ()
        self.locList.set_column_resizeable (0, FALSE)
        self.locList.column_title_passive (0)
        self.locList.column_title_passive (1)
        self.locList.set_border_width (5)

        box.pack_start (self.locList, FALSE)

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.ctree = GtkCTree (1)
        self.typeList = GtkList ()
        self.typeList.set_selection_mode (SELECTION_BROWSE)

        mice = []
        for x in sorted_mice_keys:
            value = strip (sub ("\(.*\)", "", x))
            if not value in mice:
                mice.append (value)

        groups = ()
        for x in mice:
            groups = self.merge (groups, string.split (x, " - ", 1))
        groups = self.reduce_leafs (groups)

        self.build_ctree (groups)
        self.ctree.set_selection_mode (SELECTION_BROWSE)
        self.ctree.columns_autosize ()
        self.ctree.connect ("tree_select_row", self.select)
        self.locList.connect ("select_row", self.locSelect)
        sw.add (self.ctree)
        box.pack_start (sw)

        return box


   
