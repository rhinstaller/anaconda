from gtk import *
from gnome.ui import *
from iw import *
from string import *
from xpms import *
from thread import *
import rpm
import GdkImlib

class IndividualPackageSelectionWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle ("Individual Package Selection")
        ics.setNextEnabled (1)
        ics.setHTML ("<HTML><BODY>Next you must select which packages to install."
                     "</BODY></HTML>")
        ics.setHelpEnabled (FALSE)
        self.DIR = 0
        self.DIR_UP = 1
        self.RPM = 2

        self.updatingIcons = FALSE

	self.idirImage = GdkImlib.create_image_from_xpm (I_DIRECTORY_XPM)
	self.idirUpImage = GdkImlib.create_image_from_xpm (I_DIRECTORY_UP_XPM)
	self.packageImage = GdkImlib.create_image_from_xpm (PACKAGE_XPM)
	self.packageSelectedImage = GdkImlib.create_image_from_xpm (PACKAGE_SELECTED_XPM)

    def getPrev (self):
        return PackageSelectionWindow

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

    def draw_root_icons (self):
        self.iconList.freeze ()
        self.iconList.clear ()
        for x in self.ctree.base_nodes ():
            dirName = self.ctree.get_node_info (x)[0]
            pos = self.iconList.append_imlib (self.idirImage, dirName)
            self.iconList.set_icon_data (pos, (self.DIR, x))
        self.iconList.thaw ()


    def get_rpm_desc (self, header):
        desc = replace (header[rpm.RPMTAG_DESCRIPTION], "\n\n", "\x00")
        desc = replace (desc, "\n", " ")
        desc = replace (desc, "\x00", "\n\n")
        return desc

    def clear_package_desc (self):
        self.currentPackage = None
        self.packageName.set_text ("")
        self.packageSize.set_text ("")                 
        self.packageDesc.freeze ()
        self.packageDesc.delete_text (0, -1)
        self.packageDesc.thaw ()
        self.cbutton.set_active (FALSE)
        self.cbutton.set_sensitive (FALSE)

    
    def select_icon (self, iconList, arg1, event, *args):
        if event and event.type != GDK._2BUTTON_PRESS and event.type != GDK.BUTTON_PRESS:
            return
        icon_data = iconList.get_icon_data (arg1)
        if not icon_data: return

        if event and iconList.icon_is_visible (arg1) != VISIBILITY_FULL:
            allocation = iconList.get_allocation ()
            if (event.y - self.iconListAdj.value) < (allocation[3]/2):
                self.iconList.moveto (arg1, 0.0)
            else:
                self.iconList.moveto (arg1, 1.0)

        if event == None or event.type == GDK.BUTTON_PRESS:
            if icon_data[0] == self.RPM:
                header = icon_data[1]
                # if we're already displaying the current package, don't redraw
                if self.packageName.get () == "%s-%s-%s" % (header[rpm.RPMTAG_NAME],
                                                            header[rpm.RPMTAG_VERSION],
                                                            header[rpm.RPMTAG_RELEASE]):
                    return
                
                self.currentPackage = header
                self.currentPackagePos = arg1
                self.cbutton.set_sensitive (TRUE)
                if header.selected:
                    self.cbutton.set_active (TRUE)
                else:
                    self.cbutton.set_active (FALSE)
                    
                self.packageName.set_text ("%s-%s-%s" % (header[rpm.RPMTAG_NAME],
                                                         header[rpm.RPMTAG_VERSION],
                                                         header[rpm.RPMTAG_RELEASE]))
                self.packageSize.set_text ("%.1f KBytes" % (header[rpm.RPMTAG_SIZE] / 1024.0))
                self.packageDesc.freeze ()
                self.packageDesc.delete_text (0, -1)
                self.packageDesc.insert_defaults (self.get_rpm_desc (header))
                self.packageDesc.thaw ()
            else:
                self.clear_package_desc ()
            return

        if icon_data[0] == self.RPM:
            active = self.cbutton.get_active ()
            if active == TRUE:
                self.cbutton.set_active (FALSE)
            else:
                self.cbutton.set_active (TRUE)

        if icon_data[0] == self.DIR_UP:
            current_node = icon_data[1].parent
            if current_node:
                self.ctree.select (current_node)
            else:
                # handle the imaginary root node
                current_node = self.ctree.base_nodes ()[0]
                self.ctree.unselect (icon_data[1])
                self.draw_root_icons ()
                
        elif icon_data[0] == self.DIR:
            current_node = icon_data[1]
            self.ctree.select (current_node)
            if (current_node.parent):
                self.ctree.expand_to_depth (current_node.parent, 1)
	else: return

        if self.ctree.node_is_visible (current_node) != VISIBILITY_FULL:
            self.ctree.node_moveto (current_node, 0, 0.5, 0.0)

    def select (self, ctree, node, *args):
        self.clear_package_desc ()
        self.iconList.freeze ()
        self.iconList.clear ()
        self.iconList.append_imlib (self.idirUpImage, "Up")
        self.iconList.set_icon_data (0, (self.DIR_UP, node))
        for x in node.children:
            dirName = ctree.get_node_info (x)[0]
            pos = self.iconList.append_imlib (self.idirImage, dirName)
            self.iconList.set_icon_data (pos, (self.DIR, x))

        try:
            # this code is wrapped in a generic exception handler since we don't
            # care if we access a namespace that lacks rpms
            
            # drop the leading slash off the package namespace
            for header in self.flat_groups[ctree.node_get_row_data (node)[1:]]:
                if header.selected:
                    packageIcon = self.packageSelectedImage
                    self.cbutton.set_active (TRUE)
                else:
                    packageIcon = self.packageImage
                    self.cbutton.set_active (FALSE)
                
                pos = self.iconList.append_imlib (packageIcon, header[rpm.RPMTAG_NAME])
                self.iconList.set_icon_data (pos, (self.RPM, header))
        except:
            pass

	# make sure that the iconList is reset to show the initial files in a dir,
        # unless we're rebuilding the icons because one has been selected for install
        if not self.updatingIcons:
            self.iconListSW.get_vadjustment ().set_value (0.0)
        self.iconList.thaw ()
        self.iconList.show_all ()


    def installButtonToggled (self, cbutton, *args):
        if not self.currentPackage: return
        oldSelectedStatus = self.currentPackage.selected
        
        if cbutton.get_active ():
            self.currentPackage.selected = 1
        else:
            self.currentPackage.selected = 0

        
        if oldSelectedStatus != self.currentPackage.selected:
            self.updatingIcons = TRUE
            self.ctree.select (self.ctree.selection[0])
            self.iconList.select_icon (self.currentPackagePos)
            self.updatingIcons = FALSE
            
#            self.iconList.freeze ()
#            if self.currentPackage.selected:
#                packageIcon = "/home/devel/pnfisher/gnome-package-checked.png"
#            else:
#                packageIcon = "/usr/src/gnorpm/gnome-package.xpm"

#            print self.currentPackagePos
#            self.iconList.remove (self.currentPackagePos)
#            print "got here"
#            self.iconList.insert (self.currentPackagePos, packageIcon,
#                                  self.currentPackage[rpm.RPMTAG_NAME])
#            self.iconList.set_icon_data (self.currentPackagePos, (self.RPM, self.currentPackage))
            
#            self.iconList.thaw ()


    def getScreen (self):
        threads_leave ()
        self.todo.getHeaderList()
        threads_enter ()

        self.path_mapping = {}
        self.ctree = GtkCTree ()
        self.ctree.set_selection_mode (SELECTION_BROWSE)
        # Kludge to get around CTree's extremely broken focus behavior
        self.ctree.unset_flags (CAN_FOCUS)

        if (not self.__dict__.has_key ("open_p")):
            self.open_p, self.open_b = create_pixmap_from_xpm_d (self.ctree,
                                                                 None, DIRECTORY_OPEN_XPM)
            self.closed_p, self.closed_b = create_pixmap_from_xpm_d (self.ctree,
                                                                     None, DIRECTORY_CLOSE_XPM)

        groups = {}

        # go through all the headers and grok out the group names, placing
        # packages in lists in the groups dictionary.
        
        for key in self.todo.hdList.packages.keys():
            header = self.todo.hdList.packages[key]
            if not groups.has_key (header[rpm.RPMTAG_GROUP]):
                groups[header[rpm.RPMTAG_GROUP]] = []
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
        sw.set_border_width (5)
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        sw.add (self.ctree)
        iconHBox = GtkHBox ()
        iconHBox.pack_start (sw, FALSE)

        self.iconList = GnomeIconList (90)
        self.iconList.set_selection_mode (SELECTION_MULTIPLE)
	self.iconList.connect ("select_icon", self.select_icon)
        self.draw_root_icons ()

        self.iconListSW = GtkScrolledWindow ()
        self.iconListSW.set_border_width (5)
        self.iconListSW.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        self.iconListSW.add (self.iconList)
        self.iconListAdj = self.iconListSW.get_vadjustment ()
        iconHBox.pack_start (self.iconListSW)

        descVBox = GtkVBox ()        
        descVBox.pack_start (GtkHSeparator (), FALSE, padding=3)


        hbox = GtkHBox ()
        label = GtkLabel ("Name: ")
        self.packageName = GtkLabel ()
        self.packageName.set_alignment (0.0, 0.0)
        hbox.pack_start (label, FALSE, padding=5)
        hbox.pack_start (self.packageName, FALSE)
        label = GtkLabel ("Package Details")
        label.set_alignment (1.0, 1.0)
        hbox.pack_start (label, padding=5)
        descVBox.pack_start (hbox, FALSE)

        hbox = GtkHBox ()
        label = GtkLabel ("Size: ")
        self.packageSize = GtkLabel ()
        self.packageSize.set_alignment (0.0, 0.5)
        hbox.pack_start (label, FALSE, padding=5)
        hbox.pack_start (self.packageSize, FALSE)
        align = GtkAlignment (1.0, 0.0)
        self.cbutton = GtkCheckButton ("Select Package For Installation")
        self.cbutton.set_sensitive (FALSE)
        self.cbutton.connect ("toggled", self.installButtonToggled)
        self.cbutton.children()[0].set_alignment (1.0, 0.5)
        align.add (self.cbutton)
        hbox.pack_start (align, padding=5)
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

#        descFrame = GtkFrame ("Package Details")
#        descFrame.set_border_width (5)
#        descFrame.add (descVBox)
        
        vbox = GtkVBox ()
        vbox.pack_start (iconHBox)
        vbox.pack_start (descVBox, FALSE)

        return vbox

class PackageSelectionWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle ("Package Group Selection")
        ics.setNextEnabled (1)
        ics.setHTML ("<HTML><BODY>Next you must select which package groups to install."
                     "</BODY></HTML>")

    def getNext (self):
        if self.individualPackages.get_active ():
            return IndividualPackageSelectionWindow
        else:
            return None

    def getScreen (self):
        threads_leave ()
        self.todo.getHeaderList ()
        self.todo.getCompsList()
        threads_enter ()

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)

        box = GtkVBox (FALSE, 10)
        for comp in self.todo.comps:
            if not comp.hidden:
                checkButton = GtkCheckButton (comp.name)
                checkButton.set_active (comp.selected)

                def toggled (widget, comp):
                  if widget.get_active ():
                    comp.select (0)
                  else:
                    comp.unselect (0)
                    
                checkButton.connect ("toggled", toggled, comp)

                box.pack_start (checkButton)

        sw.add_with_viewport (box)

        vbox = GtkVBox (FALSE, 5)
        self.individualPackages = GtkCheckButton ("Select individual packages")
        self.individualPackages.set_active (FALSE)
        align = GtkAlignment (0.5, 0.5)
        align.add (self.individualPackages)

        vbox.pack_start (sw, TRUE)
        vbox.pack_start (align, FALSE)
        
        return vbox

