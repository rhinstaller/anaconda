#
# package_gui.py: package group and individual package selection screens
#
# Brent Fox <bfox@redhat.com>
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
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

import rpm404 as rpm
import gui
import string
import sys
import checklist
import gtk
import gobject
from iw_gui import *
from string import *
from thread import *
from examine_gui import *
from rhpl.translate import _, N_, utf8


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
        self.DIR = 0
        self.DIR_UP = 1
        self.RPM = 2
        self.rownum = 0
        self.maxrows = 0
        self.updatingIcons = gtk.FALSE

    def getPrev (self):
        return None
    

    def build_packagelists(self, groups):
        toplevels = {}
        self.packageGroupStore = gtk.TreeStore(gobject.TYPE_STRING,
                                               gobject.TYPE_STRING)

        keys = groups.keys()
        keys.sort()

        # allpkgs is the special toplevel group
        keys.remove("allpkgs")
        allpkg = self.packageGroupStore.append(None)
        self.packageGroupStore.set_value(allpkg, 0, _("All Packages"))
        self.packageGroupStore.set_value(allpkg, 1, "allpkgs")

        # go through and make parent nodes for all of the groups
        for key in keys:
            fields = string.split(key, '/')
            main = fields[0]
            if len(fields) > 1:
                subgroup = fields[1]
            
            if toplevels.has_key(main):
                continue

            iter = self.packageGroupStore.append(allpkg)
            self.packageGroupStore.set_value(iter, 0, main)
            self.packageGroupStore.set_value(iter, 1, main)
            toplevels[main] = iter

        # now make the children
        for key in keys:
            fields = string.split(key, '/')
            main = fields[0]
            if len(fields) > 1:
                subgroup = fields[1]
            else:
                continue
            
            if not toplevels.has_key(main):
                raise RuntimeError, "Got unexpected key building tree"

            parent = toplevels[main]
            iter = self.packageGroupStore.append(parent)
            self.packageGroupStore.set_value(iter, 0, subgroup)
            self.packageGroupStore.set_value(iter, 1,
                                             "%s/%s" % (main, subgroup))


    def add_packages(self, packages):
        """Adds the packages provided (list of headers) to the package
           list"""
        
        for header in packages:
            name = header[rpm.RPMTAG_NAME]
            size = header[rpm.RPMTAG_SIZE]

            # get size in MB
            size = size / (1024 * 1024)

            # don't show as < 1 MB
            if size < 1:
                size = 1
                    
            self.packageList.append_row((name, size), header.isSelected())
        

    def select_group(self, selection):
        (model, iter) = selection.get_selected()
        if iter:
            currentGroup = model.get_value(iter, 1)

            self.packageList.clear()

            if not self.flat_groups.has_key(currentGroup):
                self.selectAllButton.set_sensitive(gtk.FALSE)
                self.unselectAllButton.set_sensitive(gtk.FALSE)
                return

            self.selectAllButton.set_sensitive(gtk.TRUE)
            self.unselectAllButton.set_sensitive(gtk.TRUE)
            
            packages = self.flat_groups[currentGroup]
            self.add_packages(packages)
            

    def toggled_package(self, data, row):
        row = int(row)
        package = self.packageList.get_text(row, 1)

        if not self.pkgs.has_key(package):
            raise RuntimeError, "Toggled a non-existent package %s" % (package)

        val = self.packageList.get_active(row)
        if val:
            self.pkgs[package].select()
        else:
            self.pkgs[package].unselect()

        self.updateSize()

    def select_package(self, selection):
        (model, iter) = selection.get_selected()
        if iter:
            package = model.get_value(iter, 1)

            if not self.pkgs.has_key(package):
                raise RuntimeError, "Selected a non-existent package %s" % (package)

            buffer = self.packageDesc.get_buffer()
            description = self.get_rpm_desc(self.pkgs[package])
            buffer.set_text(description)

        else:
            buffer = self.packageDesc.get_buffer()
            buffer.set_text("")
        

    def get_rpm_desc (self, header):
        desc = replace (header[rpm.RPMTAG_DESCRIPTION], "\n\n", "\x00")
        desc = replace (desc, "\n", " ")
        desc = replace (desc, "\x00", "\n\n")
        desc = utf8(desc)
        return desc

    def make_group_list(self, hdList, comps, displayBase = 0):
        """Go through all of the headers and get group names, placing
           packages in the dictionary.  Also have in the upper level group"""
        
        groups = {}

        # special group for listing all of the packages (aka old flat view)
        groups["allpkgs"] = []
        
        for key in hdList.packages.keys():
            header = hdList.packages[key]

            group = utf8(header[rpm.RPMTAG_GROUP])
            toplevel = string.split(group, '/')[0]

            # make sure the dictionary item exists for group and toplevel
            # note that if group already exists, toplevel must also exist
            if not groups.has_key (group):
                groups[group] = []

                if not groups.has_key(toplevel):
                    groups[toplevel] = []

            # don't display package if it is in the Base group
            if not comps["Base"].includesPackage(header) or displayBase:
#                print "adding %s to %s and %s" % (header, group, toplevel)
                groups[group].append(header)
                groups[toplevel].append(header)
                groups["allpkgs"].append(header)

        return groups
        

    def select_all (self, rownum, select_all):
        for row in range(self.packageList.num_rows):
            package = self.packageList.get_text(row, 1)
            if not self.pkgs.has_key(package):
                raise RuntimeError, "Attempt to toggle non-existent package"

            if select_all:
                self.pkgs[package].select()
            else:
                self.pkgs[package].unselect()
            self.packageList.set_active(row, select_all)

        self.updateSize()


    def updateSize(self):
        text = _("Total install size: %s") % (self.comps.sizeStr(),)
        self.totalSizeLabel.set_text(text)


    # FIXME -- if this is kept instead of the All Packages in the tree
    # it needs to properly handle keeping the tree expanded to the same
    # state as opposed to having it default back to collapsed and no
    # selection; I personally like the All Packages in the tree better
    # but that seems to look weird with gtk 1.3.11
    def changePkgView(self, widget):
        if self.treeRadio.get_active():
            packages = []

            self.packageTreeView.set_model(self.packageGroupStore)
            self.packageTreeView.expand_all()            
        else:
            # cache the full package list
            if not self.allPkgs:
                self.allPkgs = []
                for key in self.pkgs.keys():
                    self.allPkgs.append(self.pkgs[key])
            packages = self.allPkgs

            self.packageTreeView.set_model(gtk.ListStore(gobject.TYPE_STRING))


        self.packageList.clear()
        self.add_packages(packages)

            
    # IndividualPackageSelectionWindow tag="sel-indiv"
    def getScreen (self, comps, hdList):
	self.comps = comps
        self.pkgs = hdList
        self.allPkgs = None
        
        self.packageTreeView = gtk.TreeView()

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Groups', renderer, text=0)
        column.set_clickable(gtk.TRUE)
        self.packageTreeView.append_column(column)
        self.packageTreeView.set_headers_visible(gtk.FALSE)
        self.packageTreeView.set_rules_hint(gtk.FALSE)
        self.packageTreeView.set_enable_search(gtk.FALSE)
        
        self.flat_groups = self.make_group_list(hdList, comps)
        self.build_packagelists(self.flat_groups)

        selection = self.packageTreeView.get_selection()
        selection.connect("changed", self.select_group)

        self.packageTreeView.set_model(self.packageGroupStore)
        self.packageTreeView.expand_all()
        
        self.sw = gtk.ScrolledWindow ()
        self.sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.sw.set_shadow_type(gtk.SHADOW_IN)
        self.sw.add(self.packageTreeView)
        
        packageHBox = gtk.HBox()

        self.leftVBox = gtk.VBox(gtk.FALSE)

        # FIXME should these stay or go?
        # tree/flat radio buttons... 
        optionHBox = gtk.HBox()
        self.treeRadio = gtk.RadioButton(None, (_("Tree View")))
        self.treeRadio.connect("clicked", self.changePkgView)
        self.flatRadio = gtk.RadioButton(self.treeRadio, (_("Flat View")))
        optionHBox.pack_start(self.treeRadio)
        optionHBox.pack_start(self.flatRadio)
        self.leftVBox.pack_start(optionHBox, gtk.FALSE)
        
        self.leftVBox.pack_start(self.sw, gtk.TRUE)
        packageHBox.pack_start(self.leftVBox, gtk.FALSE)

        self.packageList = PackageCheckList(2)
        self.packageList.checkboxrenderer.connect("toggled",
                                                  self.toggled_package)

        self.packageList.set_enable_search(gtk.TRUE)

        self.sortType = "Package"
        self.packageList.set_column_title (1, (_("Package")))
        self.packageList.set_column_sizing (1, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
        self.packageList.set_column_title (2, (_("Size (MB)")))
        self.packageList.set_column_sizing (2, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
        self.packageList.set_headers_visible(gtk.TRUE)

        self.packageList.set_column_min_width(0, 16)
        self.packageList.set_column_clickable(0, gtk.FALSE)
        
        self.packageList.set_column_clickable(1, gtk.TRUE)
        self.packageList.set_column_sort_id(1, 1)
        self.packageList.set_column_clickable(2, gtk.TRUE)
        self.packageList.set_column_sort_id(2, 2)

        selection = self.packageList.get_selection()
        selection.connect("changed", self.select_package)

        self.packageListSW = gtk.ScrolledWindow ()
        self.packageListSW.set_border_width (5)
        self.packageListSW.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.packageListSW.set_shadow_type(gtk.SHADOW_IN)
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
        bb.set_layout (gtk.BUTTONBOX_END)

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
        descSW.set_shadow_type(gtk.SHADOW_IN)

        self.packageDesc = gtk.TextView()

        buffer = gtk.TextBuffer(None)
        self.packageDesc.set_buffer(buffer)
        self.packageDesc.set_editable(gtk.FALSE)
        self.packageDesc.set_cursor_visible(gtk.FALSE)
        self.packageDesc.set_wrap_mode(gtk.WRAP_WORD)
        descSW.add (self.packageDesc)
        descSW.set_size_request (-1, 100)

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
        viewport = sw.get_children()[0]
        viewport.set_shadow_type (gtk.SHADOW_IN)
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


class PackageCheckList(checklist.CheckList):

    def create_columns(self, columns):
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Text', renderer, text = 1)
        column.set_clickable(gtk.FALSE)
        self.append_column(column)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Size', renderer, text = 2)
        column.set_clickable(gtk.FALSE)
        self.append_column(column)
    
    def __init__(self, columns = 2):
        store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
                              gobject.TYPE_STRING, gobject.TYPE_INT)

	checklist.CheckList.__init__(self, columns=columns,
				     custom_store = store)

	
