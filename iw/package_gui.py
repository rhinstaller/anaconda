#
# package_gui.py: package group and individual package selection screens
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

import rpm
import gui
import string
import sys
import checklist
import gtk
from iw_gui import *
from string import *
from thread import *
from examine_gui import *
from translate import _, N_


def queryUpgradeContinue(intf):
    rc = intf.messageWindow(_("Proceed with upgrade?"),
                       _("The filesystems of the Linux installation "
                         "you have chosen to upgrade have already been "
                         "mounted. You cannot go back past this point. "
                         "\n\n") + 
                     _( "Would you like to continue with the upgrade?"),
                                      type = "yesno")
    return rc

class IndividualPackageSelectionWindow (InstallWindow):

    windowTitle = N_("Individual Package Selection")
    htmlTag = "sel-indiv"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        self.ics = ics
        self.ics.setHelpEnabled (gtk.FALSE)
        self.DIR = 0
        self.DIR_UP = 1
        self.RPM = 2
        self.rownum = 0
        self.maxrows = 0
        self.updatingIcons = gtk.FALSE

    def getPrev (self):
        self.ics.setHelpEnabled (gtk.TRUE)
        return None
    
    def build_tree (self, x):
        if (x == ()): return ()
        if (len (x) == 1): return (x[0],)
        else: return (x[0], self.build_tree (x[1:]))

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

    def build_ctree (self, list, cur_parent = None, prev_node = None, path = ""):
        if (list == ()): return
        
        if (len (list) > 1 and isinstance (list[1], type (()))): leaf = gtk.FALSE
        else: leaf = gtk.TRUE
    
        if isinstance (list[0], type (())):
            self.build_ctree (list[0], prev_node, None, self.ctree.node_get_row_data (prev_node))
            self.build_ctree (list[1:], cur_parent, None, path)
        else:
##             node = self.ctree.insert_node (cur_parent, None, (list[0],), 2,
##                                            self.closed_p, self.closed_b, self.open_p, self.open_b, leaf)
            node = self.ctree.insert_node (cur_parent, None, (list[0],), 2,
                                           is_leaf=leaf)
            cur_path = path + "/" + list[0]
            self.ctree.node_set_row_data (node, cur_path)
            self.build_ctree (list[1:], cur_parent, node, path)

    def get_rpm_desc (self, header):
        desc = replace (header[rpm.RPMTAG_DESCRIPTION], "\n\n", "\x00")
        desc = replace (desc, "\n", " ")
        desc = replace (desc, "\x00", "\n\n")
        return desc

    def clear_package_desc (self):
        self.currentPackage = None
        self.packageDesc.freeze ()
        self.packageDesc.delete_text (0, -1)
        self.packageDesc.thaw ()
    
    def sort_list (self, args, col):
        self.packageList.freeze ()
        if col == 2:         #sort by column #2
            self.bubblesort(args, col)
            self.sortType = "Size"
        elif col == 1:       #sort by column #1
            self.packageList.set_sort_column (col)
            self.packageList.sort ()
            self.sortType = "Package"
        elif col == 0:       #sort by column #0
            self.bubblesort(args, col)
            self.sortType = "Selected"            
        self.packageList.thaw () 

    def bubblesort (self, args, col):
        count = 0

        #--For empty groups, don't sort.  Just return.
        if self.rownum == 0:
            return

        for i in range(self.rownum):
            for j in range(self.rownum-i):
                currow = j
                nextrow = j + 1

                #--depending on which column we're sorting by, we extract different data to compare
                if col == 0:                
                    (curr, row_data, header) = self.packageList.get_row_data (currow)
                    (next, row_data, header) = self.packageList.get_row_data (nextrow)

                elif col == 2:
                    curr = self.packageList.get_text(currow, col)
                    curr = string.atoi(curr)
                    next = self.packageList.get_text(nextrow, col)
                    next = string.atoi(next)

                if curr < next:
                    self.packageList.swap_rows(currow, nextrow)
                    count = count + 1
                    self.packageList._update_row(currow)
                    self.packageList._update_row(nextrow)


    def select_all (self, rownum, select_all):
        self.packageDesc.freeze ()
        self.packageDesc.delete_text (0, -1)
        self.packageDesc.thaw ()
        
        for i in range(self.rownum + 1):
             (val, row_data, header) = self.packageList.get_row_data (i)
             if select_all == 1:
                 header.select ()
                 self.packageList.set_row_data (i, (gtk.TRUE, row_data, header)) 
             elif select_all == 0:
                 header.unselect()
                 self.packageList.set_row_data (i, (gtk.FALSE, row_data, header)) 
             self.packageList._update_row (i)

        self.updateSize()

    def button_press (self, packageList, event):
        try:
            row, col  = self.packageList.get_selection_info (event.x, event.y)
            if row != None:
                if col == 0:   #--If click on checkbox, then toggle
                    self.toggle_row (row)
                elif col == 1 or col == 2:  #--If click pkg name, show description

                    (val, row_data, header) = self.packageList.get_row_data(row)
                    description = header[rpm.RPMTAG_DESCRIPTION]
                
                    self.packageDesc.freeze ()
                    self.packageDesc.delete_text (0, -1)

                    #-- Remove various end of line characters
                    description = string.replace (description, "\n\n", "\x00")
                    description = string.replace (description, "\n", " ")
                    description = string.replace (description, "\x00", "\n\n")
                    
                    self.packageDesc.insert_defaults (description)
                    self.packageDesc.thaw ()
        except:
            pass

    def toggle_row (self, row):
        (val, row_data, header) = self.packageList.get_row_data(row)

        val = not val
        self.packageList.set_row_data(row, (val, row_data, header))
        self.packageList._update_row (row)

        description = header[rpm.RPMTAG_DESCRIPTION]

        self.packageDesc.freeze ()
        self.packageDesc.delete_text (0, -1)

        #-- Remove various end of line characters
        description = string.replace (description, "\n\n", "\x00")
        description = string.replace (description, "\n", " ")
        description = string.replace (description, "\x00", "\n\n")

        self.packageDesc.insert_defaults (description)
        self.packageDesc.thaw ()

        if val == 0:
            header.unselect()
        else:
            header.select()
        
        if self.packageList.toggled_func != None:
            self.packageList.toggled_func(val, row_data)

        self.updateSize()

    def key_press_cb (self, clist, event):
        if event.keyval == ord(" ") and self.packageList.focus_row != -1:
            self.toggle_row (self.packageList.focus_row)

    def select (self, ctree, node, *args):
        self.pkgTreeNode = node
        self.clear_package_desc ()
        self.packageList.freeze ()
        self.packageList.clear ()

        self.maxrows = 0
        self.rownum = 0

        for x in node.children:
            dirName = ctree.get_node_info (x)[0]
            self.packageList.column_titles_passive ()
                
        try:
            # drop the leading slash off the package namespace
            for header in self.flat_groups[ctree.node_get_row_data (node)[1:]]:
                dirName = header[rpm.RPMTAG_NAME] 
                dirSize = header[rpm.RPMTAG_SIZE]
                dirDesc = header[rpm.RPMTAG_DESCRIPTION]

                dirSize = dirSize/1000000
                if dirSize > 1:
                    self.rownum = self.packageList.append_row((dirName, "%s" % dirSize), gtk.TRUE, dirDesc)
                else:
                    row = [ "", dirName, "1"]
                    self.rownum = self.packageList.append_row((dirName, "1"), gtk.TRUE, dirDesc)

                if header.isSelected():
                    self.packageList.set_row_data(self.rownum, (1, dirDesc, header))
                    self.maxrows = self.maxrows + 1
                else:
                    self.packageList._toggle_row(self.rownum)
                    self.packageList.set_row_data(self.rownum, (0, dirDesc, header))
                    self.maxrows = self.maxrows + 1

            if self.sortType == "Package":
                pass
            elif self.sortType == "Size":
                self.sort_list (args, 2)
            elif self.sortType == "Selected":
                self.sort_list (args, 0)

            self.packageList.column_titles_active ()
            self.selectAllButton.set_sensitive (gtk.TRUE)
            self.unselectAllButton.set_sensitive (gtk.TRUE)
            
        except:
            self.selectAllButton.set_sensitive (gtk.FALSE)
            self.unselectAllButton.set_sensitive (gtk.FALSE)
            pass

        self.packageList.thaw ()
        self.packageList.show_all ()

    def updateSize(self):
        self.totalSizeLabel.set_text(_("Total install size: ")+ str(self.comps.sizeStr()))

    def changePkgView(self, widget):
        if self.treeRadio.get_active():
            self.packageList.clear()
            self.packageList.column_title_active (0)
            self.packageList.column_title_active (1)
            self.packageList.column_title_active (2)
            list = self.sw.children()
            if list != []:
                self.sw.remove(self.ctreeAllPkgs)
                self.sw.add(self.ctree)
                try:   #If there was already a selected node in the self.ctree, we want to select it again
                    self.ctree.select(self.pkgTreeNode)
                except:  #If the self.ctree has no selected nodes, do nothing
                    pass
                
        elif self.flatRadio.get_active():
            list = self.sw.children()
            self.packageList.column_titles_passive ()
            
            if list != []:
                self.sw.remove(self.ctree)
                self.sw.add(self.ctreeAllPkgs)
                self.ctreeAllPkgs.show()

                self.packageList.clear()
                self.packageList.freeze()
                pkgList = self.pkgs.packages.keys()
                pkgList.sort()

                for key in pkgList:
                    header = self.pkgs.packages[key]
                    name = header[rpm.RPMTAG_NAME]
                    size = header[rpm.RPMTAG_SIZE]
                    size = size/1000000
                    if size < 1:   #We don't want packages with > 1MB to appear as 0 MB in the list
                        size = 1

                    desc = header[rpm.RPMTAG_DESCRIPTION]
                    
                    if header.isSelected():
                        self.rownum = self.packageList.append_row((name, "%s" %size), gtk.TRUE, desc)
                        self.packageList.set_row_data(self.rownum, (1, desc, header))
                    else:
                        self.rownum = self.packageList.append_row((name, "%s" %size), gtk.FALSE, desc)
                        self.packageList.set_row_data(self.rownum, (0, desc, header))
            self.packageList.thaw()
            
    # IndividualPackageSelectionWindow tag="sel-indiv"
    def getScreen (self, comps, hdList):
	self.comps = comps

        self.pkgs = hdList
        
        self.path_mapping = {}
        self.ctree = gtk.CTree()
        self.ctree.set_selection_mode (gtk.SELECTION_BROWSE)

        self.ctreeAllPkgs = gtk.CTree()
        self.ctreeAllPkgs.set_selection_mode (gtk.SELECTION_BROWSE)

        # Kludge to get around CTree s extremely broken focus behavior
        # self.ctree.unset_flags (CAN_FOCUS)     

##         if (not self.__dict__.has_key ("open_p")):
##             fn = self.ics.findPixmap("directory-open.png")
##             p = gdkpixbuf.new_from_file (fn)
##             if p:
##                 self.open_p, self.open_b = p.render_pixmap_and_mask()
##             fn = self.ics.findPixmap("directory-closed.png")
##             p = gdkpixbuf.new_from_file (fn)
##             if p:
##                 self.closed_p, self.closed_b = p.render_pixmap_and_mask()
            
        groups = {}

        # go through all the headers and grok out the group names, placing
        # packages in lists in the groups dictionary.        
        for key in hdList.packages.keys():
            header = hdList.packages[key]
            if not groups.has_key (header[rpm.RPMTAG_GROUP]):
                groups[header[rpm.RPMTAG_GROUP]] = []
            # don't display package if it is in the Base group
            if not comps["Base"].includesPackage (header):
                groups[header[rpm.RPMTAG_GROUP]].append (header)

        keys = groups.keys ()
        keys.sort ()
        self.flat_groups = groups

        # now insert the groups into the list, then each group's packages
        # after sorting the list
        def cmpHdrName(first, second):
            if first[rpm.RPMTAG_NAME] < second[rpm.RPMTAG_NAME]:
                return -1
            elif first[rpm.RPMTAG_NAME] == second[rpm.RPMTAG_NAME]:
                return 0
            return 1

        groups = ()
        for key in keys:
            self.flat_groups[key].sort (cmpHdrName)
            groups = self.merge (groups, split (key, "/"))
        self.ctree.freeze ()
        self.build_ctree (groups)

        for base_node in self.ctree.base_nodes ():
            self.ctree.expand_recursive (base_node)
        self.ctree.columns_autosize ()
        for base_node in self.ctree.base_nodes ():
            self.ctree.collapse_recursive (base_node)
        self.ctree.thaw ()

        self.ctree.connect ("tree_select_row", self.select)
        self.sw = gtk.ScrolledWindow ()
        self.sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)

        self.sw.add(self.ctree)
        packageHBox = gtk.HBox()

        self.leftVBox = gtk.VBox(gtk.FALSE)
        optionHBox = gtk.HBox()

        self.treeRadio = gtk.RadioButton(None, (_("Tree View")))
        self.treeRadio.connect("clicked", self.changePkgView)
        self.flatRadio = gtk.RadioButton(self.treeRadio, (_("Flat View")))

        optionHBox.pack_start(self.treeRadio)
        optionHBox.pack_start(self.flatRadio)
        
        self.leftVBox.pack_start(optionHBox, gtk.FALSE)
        self.leftVBox.pack_start(self.sw, gtk.TRUE)
        packageHBox.pack_start(self.leftVBox, gtk.FALSE)

        self.packageList = checklist.CheckList(2)

        self.sortType = "Package"
        self.packageList.set_column_title (1, (_("Package")))
        self.packageList.set_column_auto_resize (1, gtk.TRUE)
        self.packageList.set_column_title (2, (_("Size (MB)")))
        self.packageList.set_column_auto_resize (2, gtk.TRUE)
        self.packageList.column_titles_show ()

        self.packageList.set_column_min_width(0, 16)
        self.packageList.column_title_active (0)
        self.packageList.column_title_active (1)
        self.packageList.column_title_active (2)
        self.packageList.connect ('click-column', self.sort_list)
        self.packageList.connect ('button_press_event', self.button_press)
        self.packageList.connect ("key_press_event", self.key_press_cb)

        self.packageListSW = gtk.ScrolledWindow ()
        self.packageListSW.set_border_width (5)
        self.packageListSW.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.packageListSW.add(self.packageList)

        self.packageListVAdj = self.packageListSW.get_vadjustment ()
        self.packageListSW.set_vadjustment(self.packageListVAdj)
        self.packageListHAdj = self.packageListSW.get_hadjustment () 
        self.packageListSW.set_hadjustment(self.packageListHAdj)

        packageHBox.pack_start (self.packageListSW)

        descVBox = gtk.VBox ()        
        descVBox.pack_start (gtk.HSeparator (), gtk.FALSE, padding=2)

        hbox = gtk.HBox ()
        bb = gtk.HButtonBox ()
        bb.set_layout (BUTTONBOX_END)

        self.totalSizeLabel = gtk.Label (_("Total size: "))
        hbox.pack_start (self.totalSizeLabel, gtk.FALSE, gtk.FALSE, 0)

        self.selectAllButton = gtk.Button (_("Select all in group"))
        bb.pack_start (self.selectAllButton, gtk.FALSE)
        self.selectAllButton.connect ('clicked', self.select_all, 1)

        self.unselectAllButton = gtk.Button(_("Unselect all in group"))
        bb.pack_start(self.unselectAllButton, gtk.FALSE)
        self.unselectAllButton.connect ('clicked', self.select_all, 0)
        
        hbox.pack_start (bb)

        self.selectAllButton.set_sensitive (gtk.FALSE)
        self.unselectAllButton.set_sensitive (gtk.FALSE)

        descVBox.pack_start (hbox, gtk.FALSE)

        descSW = gtk.ScrolledWindow ()
        descSW.set_border_width (5)
        descSW.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.packageDesc = gtk.Text ()
        self.packageDesc.set_word_wrap (gtk.TRUE)
        self.packageDesc.set_line_wrap (gtk.TRUE)
        self.packageDesc.set_editable (gtk.FALSE)
        descSW.add (self.packageDesc)
        descSW.set_usize (-1, 100)

        descVBox.pack_start (descSW)

        vbox = gtk.VBox ()
        vbox.pack_start (packageHBox)
        vbox.pack_start (descVBox, gtk.FALSE)

	self.updateSize()

        return vbox

class PackageSelectionWindow (InstallWindow):
    windowTitle = N_("Package Group Selection")
    htmlTag = "sel-group"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        self.ics = ics
        self.ics.setNextEnabled (1)
        self.files_found = "gtk.FALSE"
        
    def getPrev (self):
	self.comps.setSelectionState(self.origSelection)

    def getNext (self):
	if self.individualPackages.get_active():
	    self.dispatch.skipStep("indivpackage", skip = 0)
	else:
	    self.dispatch.skipStep("indivpackage")

        return None

    def setSize(self):
        self.sizelabel.set_text (_("Total install size: %s") % 
					self.comps.sizeStr())

    def componentToggled(self, widget, comp):
        # turn on all the comps we selected
	if widget.get_active ():
	    comp.select ()
	else:
	    comp.unselect ()

	self.setSize()

    def getScreen(self, comps, dispatch):
    # PackageSelectionWindow tag="sel-group"
	self.comps = comps
	self.dispatch = dispatch

	self.origSelection = self.comps.getSelectionState()
            
        sw = gtk.ScrolledWindow ()
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        box = gtk.VBox (gtk.FALSE, 2)

        self.checkButtons = []
        for comp in self.comps:
            if not comp.hidden:
                pixname = string.replace (comp.name, ' ', '-')
                pixname = string.replace (pixname, '/', '-')
                pixname = string.replace (pixname, '.', '-')
                pixname = string.replace (pixname, '(', '-')
                pixname = string.replace (pixname, ')', '-')
                pixname = string.lower (pixname) + ".png"
                checkButton = None
                pix = self.ics.readPixmap (pixname)
                if pix:
                    hbox = gtk.HBox (gtk.FALSE, 5)
                    hbox.pack_start (pix, gtk.FALSE, gtk.FALSE, 0)
                    label = gtk.Label (_(comp.name))
                    label.set_alignment (0.0, 0.5)
                    hbox.pack_start (label, gtk.TRUE, gtk.TRUE, 0)
                    checkButton = gtk.CheckButton ()
                    checkButton.add (hbox)
                else:
                    checkButton = gtk.CheckButton (comp.name)

                checkButton.set_active (comp.isSelected(justManual = 1))
                checkButton.connect('toggled', self.componentToggled, comp)
                self.checkButtons.append ((checkButton, comp))
                box.pack_start (checkButton)

        wrapper = gtk.VBox (gtk.FALSE, 0)
        wrapper.pack_start (box, gtk.FALSE)
        
        sw.add_with_viewport (wrapper)
        viewport = sw.children()[0]
        viewport.set_shadow_type (SHADOW_ETCHED_IN)
        box.set_focus_hadjustment(sw.get_hadjustment ())
        box.set_focus_vadjustment(sw.get_vadjustment ())

        hbox = gtk.HBox (gtk.FALSE, 5)

        self.individualPackages = gtk.CheckButton (
		_("Select individual packages"))
        self.individualPackages.set_active (
		not dispatch.stepInSkipList("indivpackage"))
        hbox.pack_start (self.individualPackages, gtk.FALSE)

        self.sizelabel = gtk.Label ("")
        self.setSize()
        hbox.pack_start (self.sizelabel, gtk.TRUE)
        
        vbox = gtk.VBox (gtk.FALSE, 5)
        vbox.pack_start (sw, gtk.TRUE)
        vbox.pack_start (hbox, gtk.FALSE)
        vbox.set_border_width (5)

        return vbox

