from gtk import *
from gnome.ui import *
from iw_gui import *
from string import *
from thread import *
from examine_gui import *
import rpm
import GdkImlib
import GtkExtra
import string
import sys
import xpms_gui
from translate import _
import checklist
import time
from threading import *
import os

class IndividualPackageSelectionWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("Individual Package Selection"))
        ics.setNextEnabled (1)
        ics.readHTML ("sel-indiv")
        ics.setHelpEnabled (FALSE)
        self.DIR = 0
        self.DIR_UP = 1
        self.RPM = 2
        self.rownum = 0
        self.maxrows = 0

        self.updatingIcons = FALSE


    def getPrev (self):
        for x in self.ics.getICW ().stateList:
            if isinstance (x, PackageSelectionWindow):
                return PackageSelectionWindow
            elif isinstance (x, UpgradeExamineWindow):
                return UpgradeExamineWindow
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
        
        if (len (list) > 1 and isinstance (list[1], type (()))): leaf = FALSE
        else: leaf = TRUE
    
        if isinstance (list[0], type (())):
            self.build_ctree (list[0], prev_node, None, self.ctree.node_get_row_data (prev_node))
            self.build_ctree (list[1:], cur_parent, None, path)
        else:
            node = self.ctree.insert_node (cur_parent, None, (list[0],), 2,
                                           self.closed_p, self.closed_b, self.open_p, self.open_b, leaf)
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

        if col == 2:
            self.bubblesort(args, col)
            min = 0
            max = self.maxrows - 1
            self.sortType = "Size"

        elif col == 1:
            self.packageList.set_sort_column (col)
            self.packageList.sort ()
            self.sortType = "Package"

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
                
                curr = self.packageList.get_text(currow, col)
                curr = string.atoi(curr)
                next = self.packageList.get_text(nextrow, col)
                next = string.atoi(next)
                
                if curr < next:
                    self.packageList.swap_rows(currow, nextrow)
                    count = count + 1
                    self.packageList._update_row(currow)
                    self.packageList._update_row(nextrow)


    def select_all (self, rownum):
        self.packageDesc.freeze ()
        self.packageDesc.delete_text (0, -1)
        self.packageDesc.thaw ()
        
        for i in range(self.rownum + 1):
             (val, row_data, header) = self.packageList.get_row_data (i)
             header.select ()
             self.packageList.set_row_data (i, (TRUE, row_data, header)) 
             self.packageList._update_row (i)

        self.updateSize()

    def unselect_all (self, rownum):
        self.packageDesc.freeze ()
        self.packageDesc.delete_text (0, -1)
        self.packageDesc.thaw ()

        for i in range (self.rownum + 1):
             (val, row_data, header) = self.packageList.get_row_data(i)
             header.unselect()
             self.packageList.set_row_data(i, (FALSE, row_data, header)) 
             self.packageList._update_row (i)

        self.updateSize()

    def button_press (self, packageList, event):
        row, col  = self.packageList.get_selection_info (event.x, event.y)
        if row != None:
            if col == 0:   #--If click on checkbox, then toggle
                self.toggle_row (row)
            elif col == 1 or col == 2:  #--If click pkg name, show description

                packageName = self.packageList.get_text(row, col)

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


    def toggle_row (self, row):
        (val, row_data, header) = self.packageList.get_row_data(row)

        val = not val
        self.packageList.set_row_data(row, (val, row_data, header))
        self.packageList._update_row (row)

        packageName = self.packageList.get_text(row, 1)

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
#            self.emit_stop_by_name ("key_press_event")
#            return 1

#        return 0


    def select (self, ctree, node, *args):
#        print "select"
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
                    row = [ "", dirName, "%s" % dirSize]
                    self.rownum = self.packageList.append_row((dirName, "%s" % dirSize), TRUE, dirDesc)
                    
                else:
                    row = [ "", dirName, "1"]
                    self.rownum = self.packageList.append_row((dirName, "1"), TRUE, dirDesc)


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

            self.packageList.column_titles_active ()
            
            self.selectAllButton.set_sensitive (TRUE)
            self.unselectAllButton.set_sensitive (TRUE)
            
        except:
#            print "Except called"
            self.selectAllButton.set_sensitive (FALSE)
            self.unselectAllButton.set_sensitive (FALSE)
            pass

        self.packageList.thaw ()
        self.packageList.show_all ()

    def updateSize(self):
        self.totalSizeLabel.set_text(_("Total install size: ")+ str(self.todo.comps.sizeStr()))

    # IndividualPackageSelectionWindow tag="sel-indiv"
    def getScreen (self):
        threads_leave ()
        self.todo.getHeaderList()
        threads_enter ()

        self.path_mapping = {}
        self.ctree = GtkCTree ()
        self.ctree.set_selection_mode (SELECTION_BROWSE)
        self.ctree.set_expander_style(CTREE_EXPANDER_TRIANGLE)
        self.ctree.set_line_style(CTREE_LINES_NONE)

        # Kludge to get around CTree s extremely broken focus behavior
        self.ctree.unset_flags (CAN_FOCUS)

        if (not self.__dict__.has_key ("open_p")):
            self.open_p, self.open_b = create_pixmap_from_xpm_d (self.ctree,
                                                                 None, xpms_gui.DIRECTORY_OPEN_XPM)
            self.closed_p, self.closed_b = create_pixmap_from_xpm_d (self.ctree,
                                                                     None, xpms_gui.DIRECTORY_CLOSE_XPM)

        groups = {}

        # go through all the headers and grok out the group names, placing
        # packages in lists in the groups dictionary.        
        for key in self.todo.hdList.packages.keys():
            header = self.todo.hdList.packages[key]
            if not groups.has_key (header[rpm.RPMTAG_GROUP]):
                groups[header[rpm.RPMTAG_GROUP]] = []
            # don't display package if it is in the Base group
            if not self.todo.comps["Base"].includesPackage (header):
                groups[header[rpm.RPMTAG_GROUP]].append (header)

        keys = groups.keys ()
        keys.sort ()
        self.flat_groups = groups
        index = 0

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
        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)

        # Set the style for the tree
        self.ctree.set_expander_style(CTREE_EXPANDER_TRIANGLE)
        self.ctree.set_line_style(CTREE_LINES_NONE)

        sw.add (self.ctree)
        packageHBox = GtkHBox ()
        packageHBox.pack_start (sw, FALSE)

        self.packageList = checklist.CheckList(2)

        self.sortType = "Package"
        self.packageList.set_column_title (1, (_("Package")))
        self.packageList.set_column_auto_resize (1, TRUE)
        self.packageList.set_column_title (2, (_("Size (MB)")))
        self.packageList.set_column_auto_resize (2, TRUE)
        self.packageList.column_titles_show ()

        self.packageList.set_column_min_width(0, 16)
        self.packageList.column_title_active (1)
        self.packageList.column_title_active (2)
        self.packageList.connect ('click-column', self.sort_list)
        self.packageList.connect ('button_press_event', self.button_press)
        self.packageList.connect ("key_press_event", self.key_press_cb)

        self.packageListSW = GtkScrolledWindow ()
        self.packageListSW.set_border_width (5)
        self.packageListSW.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.packageListSW.add(self.packageList)

        self.packageListVAdj = self.packageListSW.get_vadjustment ()
        self.packageListSW.set_vadjustment(self.packageListVAdj)
        self.packageListHAdj = self.packageListSW.get_hadjustment () 
        self.packageListSW.set_hadjustment(self.packageListHAdj)

        packageHBox.pack_start (self.packageListSW)


        descVBox = GtkVBox ()        
        descVBox.pack_start (GtkHSeparator (), FALSE, padding=2)

        hbox = GtkHButtonBox ()

        self.totalSizeLabel = GtkLabel(_("Total size: "))
        hbox.pack_start(self.totalSizeLabel, FALSE, FALSE, 0)

        self.selectAllButton = GtkButton(_("Select all in group"))
        hbox.pack_start(self.selectAllButton, FALSE)
        self.selectAllButton.connect('clicked', self.select_all)

        self.unselectAllButton = GtkButton(_("Unselect all in group"))
        hbox.pack_start(self.unselectAllButton, FALSE)
        self.unselectAllButton.connect('clicked', self.unselect_all)        

        self.selectAllButton.set_sensitive (FALSE)
        self.unselectAllButton.set_sensitive (FALSE)

        descVBox.pack_start (hbox, FALSE)

        descSW = GtkScrolledWindow ()
        descSW.set_border_width (5)
        descSW.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        self.packageDesc = GtkText ()
        self.packageDesc.set_word_wrap (TRUE)
        self.packageDesc.set_line_wrap (TRUE)
        self.packageDesc.set_editable (FALSE)
        descSW.add (self.packageDesc)
        descSW.set_usize (-1, 100)

        descVBox.pack_start (descSW)

        vbox = GtkVBox ()
        vbox.pack_start (packageHBox)
        vbox.pack_start (descVBox, FALSE)

	self.updateSize()

        return vbox


class ErrorWindow:
    def __init__ (self, text):
        win = GnomeDialog (_("File not found"))
        win.connect ("clicked", self.exit)

        info = GtkLabel (text)
#        info = GtkLabel (_("An error has occurred while retreiving hdlist or comps files.  "
#                           "The installation media or image is probably corrupt.  Installer will exit now."))
        info.set_line_wrap (TRUE)

        hbox = GtkHBox (FALSE)
        hbox.pack_start (GnomePixmap ('/usr/share/pixmaps/gnome-warning.png'), FALSE)
        hbox.pack_start (info)

#        exit = GtkButton (_("Ok"))
#        exit.connect ("clicked", self.exit)
#        exit.set_border_width (20)
        win.append_button (_("Ok"))
        win.button_connect (0 , self.exit)

        win.vbox.pack_start (hbox, FALSE)
#        win.vbox.pack_start (exit, FALSE, FALSE, 10)

        win.set_usize (450, 180)
        win.set_position (WIN_POS_CENTER)
        win.show_all ()
        self.window = win
        
        thread = currentThread ()
        if thread.getName () == "gtk_main":
            self.mutex = None
            self.rc = self.window.run ()
            threads_leave()
        else:
            threads_leave ()
            self.mutex = Event ()
            self.mutex.wait ()
        
    def exit (self, args):
        os._exit(0)

class PackageSelectionWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Package Group Selection"))
        ics.setNextEnabled (1)
        ics.readHTML ("sel-group")
        self.selectIndividualPackages = FALSE

        self.files_found = "TRUE"
        
    def getPrev (self):
	self.todo.comps.setSelectionState(self.origSelection)

    def getNext (self):
	if not self.__dict__.has_key ("individualPackages"):
	    return None

        gotoIndividualPackages = self.individualPackages.get_active ()
        del self.individualPackages
        
        if gotoIndividualPackages:
            self.selectIndividualPackages = TRUE
            return IndividualPackageSelectionWindow
        else:
            self.selectIndividualPackages = FALSE
          
        return None

    def setSize(self):
        self.sizelabel.set_text (_("Total install size: %s") % self.todo.comps.sizeStr())

    def componentToggled(self, widget, comp):
        # turn on all the comps we selected
	if widget.get_active ():
	    comp.select ()
	else:
	    comp.unselect ()

	self.setSize()

    # PackageSelectionWindow tag="sel-group"
    def getScreen (self):
        #--If we can't retreive hdlist or comps files, raise an error
        try:
	    threads_leave ()
	    self.todo.getHeaderList ()
	    self.todo.getCompsList()
	    threads_enter ()
        except:
            self.files_found = "FALSE"

        if self.files_found == "FALSE":
            text = (_("An error has occurred while retreiving hdlist file.  The installation media or image is probably corrupt.  Installer will exit now."))
            win = ErrorWindow (text)
        else:
            self.origSelection = self.todo.comps.getSelectionState()

        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        box = GtkVBox (FALSE, 2)

        self.checkButtons = []
        klass = self.todo.getClass ()
	showList = klass.getOptionalGroups()
        for comp in self.todo.comps:
            show = 0
            if showList:
                try:
                    if klass.findOptionalGroup (comp.name):
			show = 1
                except ValueError:
                    # comp not in show list
                    pass
            else:
                show = not comp.hidden

            if show:
                pixname = string.replace (comp.name, ' ', '-')
                pixname = string.replace (pixname, '/', '-')
                pixname = string.replace (pixname, '.', '-')
                pixname = string.replace (pixname, '(', '-')
                pixname = string.replace (pixname, ')', '-')
                pixname = string.lower (pixname) + ".png"
                picture = None
                checkButton = None
                im = self.ics.readPixmap (pixname)
                if im:
                    im.render ()
                    pix = im.make_pixmap ()
                    hbox = GtkHBox (FALSE, 5)
                    hbox.pack_start (pix, FALSE, FALSE, 0)
                    label = GtkLabel (_(comp.name))
                    label.set_alignment (0.0, 0.5)
                    hbox.pack_start (label, TRUE, TRUE, 0)
                    checkButton = GtkCheckButton ()
                    checkButton.add (hbox)
                else:
                    checkButton = GtkCheckButton (comp.name)

                checkButton.set_active (comp.isSelected())
                checkButton.connect('toggled', self.componentToggled, comp)
                self.checkButtons.append ((checkButton, comp))
                box.pack_start (checkButton)

        wrapper = GtkVBox (FALSE, 0)
        wrapper.pack_start (box, FALSE)
        
        sw.add_with_viewport (wrapper)
        viewport = sw.children()[0]
        viewport.set_shadow_type (SHADOW_ETCHED_IN)
        box.set_focus_hadjustment(sw.get_hadjustment ())
        box.set_focus_vadjustment(sw.get_vadjustment ())

        hbox = GtkHBox (FALSE, 5)

        self.individualPackages = GtkCheckButton (_("Select individual packages"))
        self.individualPackages.set_active (self.selectIndividualPackages)
        hbox.pack_start (self.individualPackages, FALSE)

        self.sizelabel = GtkLabel ("")
        self.setSize()
        hbox.pack_start (self.sizelabel, TRUE)
        
        vbox = GtkVBox (FALSE, 5)
        vbox.pack_start (sw, TRUE)
        vbox.pack_start (hbox, FALSE)
        vbox.set_border_width (5)

        return vbox


        
#        else:
#            self.raiseDialog ()





































































