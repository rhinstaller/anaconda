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
import gtk
import gobject
import checklist
from iw_gui import *
from string import *
from thread import *
from examine_gui import *
from rhpl.translate import _, N_, utf8
from comps import orderPackageGroups, getCompGroupDescription
from comps import PKGTYPE_MANDATORY, PKGTYPE_DEFAULT, PKGTYPE_OPTIONAL
from comps import Package, Component


def queryUpgradeContinue(intf):
    rc = intf.messageWindow(_("Proceed with upgrade?"),
                       _("The file systems of the Linux installation "
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
        

	### XXX Hack to get around fact treeview doesn't seem to resort
	###     when data is store is changed. By jostling it we can make it
	self.packageList.store.set_sort_column_id(self.sort_id, not self.sort_order)
	self.packageList.store.set_sort_column_id(self.sort_id, self.sort_order)	

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

	# if they hit space bar stop that event from happening
	self.ignoreKeypress = (package, val)
	

    def select_package(self, selection):
        (model, iter) = selection.get_selected()
        if iter:
            package = model.get_value(iter, 1)

            if not self.pkgs.has_key(package):
                raise RuntimeError, "Selected a non-existent package %s" % (package)

            buffer = self.packageDesc.get_buffer()
            description = self.get_rpm_desc(self.pkgs[package])
	    try:
		version = self.pkgs[package][rpm.RPMTAG_VERSION]
	    except:
		version = None

	    if version:
		outtext = _("Package: %s\nVersion: %s\n") % (package, version ) + description
	    else:
		outtext =description
		
            buffer.set_text(outtext)
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
	    hier = string.split(group, '/')
            toplevel = hier[0]

            # make sure the dictionary item exists for group and toplevel
            # note that if group already exists, toplevel must also exist
            if not groups.has_key (group):
                groups[group] = []

                if not groups.has_key(toplevel):
                    groups[toplevel] = []

            # don't display package if it is in the Base group
            if not comps["Base"].includesPackage(header) or displayBase:
                groups[group].append(header)
		if len(hier) > 1:
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

    ### XXX Hack to get around fact treeview doesn't seem to resort
    ###     Have to keep up with sort state when user changes it
    def colClickedCB(self, widget, val):
	self.sort_id = widget.get_sort_column_id()
	self.sort_order = widget.get_sort_order()

    def keypressCB(self, widget, val):
	if val.keyval == gtk.keysyms.space:
	    selection = self.packageList.get_selection()
	    (model, iter) = selection.get_selected()
	    if iter:
		self.select_package(selection)
		package = self.packageList.store.get_value(iter, 1)
		val = self.packageList.store.get_value(iter, 0)

		# see if we just got this because of focus being on
		# checkbox toggle and they hit space bar
		if self.ignoreKeypress:
		    if (package, val) == self.ignoreKeypress:
			self.ignoreKeypress = None
			return gtk.TRUE
		    else:
			# didnt match for some reason, lets plow ahead
			self.ignoreKeypress = None
		
		self.packageList.store.set_value(iter, 0, not val)

		if not val:
		    self.pkgs[package].select()
		else:
		    self.pkgs[package].unselect()

		self.updateSize()
                return gtk.TRUE

	return gtk.FALSE
	    
		
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
        self.treeRadio = gtk.RadioButton(None, (_("_Tree View")))
        self.treeRadio.connect("clicked", self.changePkgView)
        self.flatRadio = gtk.RadioButton(self.treeRadio, (_("_Flat View")))
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
        self.packageList.set_column_title (1, (_("_Package")))
        self.packageList.set_column_sizing (1, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
        self.packageList.set_column_title (2, (_("_Size (MB)")))
        self.packageList.set_column_sizing (2, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
        self.packageList.set_headers_visible(gtk.TRUE)

        self.packageList.set_column_min_width(0, 16)
        self.packageList.set_column_clickable(0, gtk.FALSE)
        
        self.packageList.set_column_clickable(1, gtk.TRUE)
        self.packageList.set_column_sort_id(1, 1)
        self.packageList.set_column_clickable(2, gtk.TRUE)
        self.packageList.set_column_sort_id(2, 2)

	sort_id = 1
	sort_order = 0
	self.packageList.store.set_sort_column_id(sort_id, sort_order)

	### XXX Hack to keep up with state of sorting
	###     Remove when treeview is fixed
	self.sort_id = sort_id
	self.sort_order = sort_order
	col = self.packageList.get_column(1)
	col.connect("clicked", self.colClickedCB, None)
	col = self.packageList.get_column(2)
	col.connect("clicked", self.colClickedCB, None)

        selection = self.packageList.get_selection()
        selection.connect("changed", self.select_package)

	self.packageList.connect("key-release-event", self.keypressCB)
	self.ignoreKeypress = None

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

        self.selectAllButton = gtk.Button (_("Select _all in group"))
        bb.pack_start (self.selectAllButton, gtk.FALSE)
        self.selectAllButton.connect ('clicked', self.select_all, 1)

        self.unselectAllButton = gtk.Button(_("_Unselect all in group"))
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

    def componentToggled(self, widget, data):
        # turn on all the comps we selected
	(comp, lbl, ebutton) = data
	if widget.get_active ():
	    comp.select ()
	else:
	    comp.unselect ()

	self.setSize()
	
	if lbl:
	    self.setCompLabel(comp, lbl)

        if ebutton:
            ebutton.set_sensitive(widget.get_active())

        ### XXX - need to i18n??
        if comp.name == "Everything":
            for (cb, cb2, cbcomp) in self.checkButtons:
                if cbcomp.name == 'Everything':
                    continue
		if cb:
		    cb.set_sensitive(not widget.get_active())
		if cb2:
		    cb2.set_sensitive(not widget.get_active())


    def pkgGroupMemberToggled(self, widget, data):
	(comp, sizeLabel, pkg) = data
	(ptype, sel) = self.getFullInfo(pkg, comp)

	# DONT handle metapackages write yet!
	if pkg in comp.metapackagesFullInfo().keys():
	    log("cant toggle metapackage yet!")
	    return

	# dont select or unselect if its already in that state
	if widget.get_active():
	    if not sel:
		if ptype == PKGTYPE_OPTIONAL:
		    comp.selectOptionalPackage(pkg)
		else:
		    log("Got callback with mandatory pkg %s!!", pkg.name)
	    else:
		log("already selected, not selecting!")
	else:
	    if sel:
		if ptype == PKGTYPE_OPTIONAL:
		    comp.unselectOptionalPackage(pkg)
		else:
		    log("Got callback with mandatory pkg %s!!", pkg.name)
	    else:
		log("already unselected, not unselecting!")

	if sizeLabel:
	    self.setDetailSizeLabel(comp, sizeLabel)

    def getFullInfo(self, obj, comp):
	if isinstance(obj, Package):
	    return comp.packagesFullInfo()[obj]
	elif isinstance(obj, Component):
	    return comp.metapackagesFullInfo()[obj]
	else:
	    return None
	
    def getStats(self, comp):
	allpkgs = comp.packagesFullInfo().keys() + comp.metapackagesFullInfo().keys()
	
	if comp.name == u"Everything":
	    total = len(allpkgs)
	    if comp.isSelected(justManual = 1):
		selected = total
	    else:
		selected = 0
	    return (selected, total)
	
	total = 0
	selected = 0
	for pkg in allpkgs:
	    total = total + 1
	    (ptype, sel) = self.getFullInfo(pkg, comp)
	    if sel:
		selected = selected + 1

        return (selected, total)

    def setDetailSizeLabel(self, comp, sizeLabel):
        text = _("Total install size: %s") % (self.comps.sizeStr(),)
	sizeLabel.set_text(text)

    def setCompLabel(self, comp, label):
	(selpkg, totpkg) = self.getStats(comp)
        if not comp.isSelected(justManual = 1):
            selpkg = 0
		    
	txt = "<b>%s [%d/%d]</b>" % (_(comp.name), selpkg, totpkg)
	label.set_markup(txt)

    def editDetails(self, button, data):

	# do all magic for packages and metapackages
	def getDescription(obj, comp):
	    if isinstance(obj, Package):
		basedesc = obj.h[rpm.RPMTAG_SUMMARY]
	    elif isinstance(obj, Component):
		basedesc = getCompGroupDescription(obj)
	    else:
		return None

	    if basedesc is not None:
		desc = replace (basedesc, "\n\n", "\x00")
		desc = replace (desc, "\n", " ")
		desc = replace (desc, "\x00", "\n\n")
		desc = utf8(desc)
	    else:
		desc = ""
	    return "%s - %s" % (obj.name, desc)

	# pull out member sorted by name
	def getNextMember(goodpkgs, comp, domandatory = 0):
	    curpkg = None
	    for pkg in goodpkgs:
		pkgname = pkg.name

		if domandatory:
		    (ptype, sel) = self.getFullInfo(pkg, comp)
		    if ptype != PKGTYPE_MANDATORY:
			continue

		foundone = 1
		if curpkg is not None:
		    if pkgname < curpkg.name:
			curpkg = pkg
		else:
		    curpkg = pkg

	    return curpkg


	#
	# START OF editDetails
	#
	# backup state
	(comp, hdrlbl) = data
	origpkgselection = {}
	for pkg in comp.packagesFullInfo().keys():
	    val = comp.packagesFullInfo()[pkg]
	    origpkgselection[pkg] = val
	    
	origmetapkgselection = {}
	for pkg in comp.metapackagesFullInfo().keys():
	    val = comp.metapackagesFullInfo()[pkg]
	    origmetapkgselection[pkg] = val
	
        self.dialog = gtk.Dialog(_("Details for '%s'") % (_(comp.name),))
        gui.addFrame(self.dialog)
        self.dialog.add_button('gtk-cancel', 2)
        self.dialog.add_button('gtk-ok', 1)
        self.dialog.set_position(gtk.WIN_POS_CENTER)

        mainvbox = self.dialog.vbox

        lbl = gtk.Label(_("A package group can have both Base and "
                          "Optional package members.  Base packages "
                          "are always selected as long as the package group "
			  "is selected.\n\nSelect the optional packages "
			  "to be installed:"))
        lbl.set_line_wrap(gtk.TRUE)
	lbl.set_size_request(450, -1)
	lbl.set_alignment(0.0, 0.5)
        mainvbox.pack_start(lbl, gtk.FALSE, gtk.FALSE)

        cbvbox = gtk.VBox(gtk.FALSE)
	cbvbox.set_border_width(5)

	# will pack this last, need to create it for toggle callback below
        sizeLabel = gtk.Label("")
	self.setDetailSizeLabel(comp, sizeLabel)
	
        goodpkgs = comp.packagesFullInfo().keys() + comp.metapackagesFullInfo().keys()

	# first show default members, if any
	haveBase = 0
	next = getNextMember(goodpkgs, comp, domandatory = 1)
	if next:
	    haveBase = 1
	    lbl = gtk.Label("")
	    lbl.set_markup("<b>%s</b>" % (_("Base Packages"),))
	    lbl.set_alignment(0.0, 0.0)
	    cbvbox.pack_start(lbl, gtk.FALSE, gtk.FALSE);
	    while 1:
		next = getNextMember(goodpkgs, comp, domandatory = 1)
		if not next:
		    break

		goodpkgs.remove(next)
		desc = getDescription(next, comp)
		lbl = gtk.Label(desc)
		lbl.set_alignment(0.0, 0.0)

		thbox = gtk.HBox(gtk.FALSE)
		chbox = gtk.HBox(gtk.FALSE)
		chbox.set_size_request(10,-1)
		thbox.pack_start(chbox, gtk.FALSE, gtk.FALSE)
		thbox.pack_start(lbl, gtk.TRUE, gtk.TRUE)

		cbvbox.pack_start(thbox, gtk.TRUE, gtk.TRUE)

	# now the optional parts, if any
	next = getNextMember(goodpkgs, comp, domandatory = 0)
	if next:
	    optvbox = gtk.VBox(gtk.FALSE)
	    cbvbox.pack_start(optvbox, gtk.FALSE, gtk.FALSE, haveBase*10)
	    
	    lbl = gtk.Label("")
	    lbl.set_markup("<b>%s</b>" % (_("Optional Packages"),))
	    lbl.set_alignment(0.0, 0.0)
	    optvbox.pack_start(lbl, gtk.FALSE, gtk.FALSE)
	    while 1:
		next = getNextMember(goodpkgs, comp, domandatory = 0)
		if not next:
		    break

		goodpkgs.remove(next)

		desc = getDescription(next, comp)
		cb = gtk.CheckButton(desc)
		(ptype, sel) = self.getFullInfo(next, comp)
		cb.set_active(sel)
		cb.connect("toggled", self.pkgGroupMemberToggled,
			   (comp, sizeLabel, next))

		thbox = gtk.HBox(gtk.FALSE)
		chbox = gtk.HBox(gtk.FALSE)
		chbox.set_size_request(10,-1)
		thbox.pack_start(chbox, gtk.FALSE, gtk.FALSE)
		thbox.pack_start(cb, gtk.TRUE, gtk.TRUE)

		optvbox.pack_start(thbox, gtk.FALSE, gtk.FALSE)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        wrapper = gtk.VBox (gtk.FALSE, 0)
        wrapper.pack_start (cbvbox, gtk.FALSE)
        
        sw.add_with_viewport (wrapper)
        viewport = sw.get_children()[0]
        viewport.set_shadow_type (gtk.SHADOW_IN)
	viewport.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse ("white"))
        cbvbox.set_focus_hadjustment(sw.get_hadjustment ())
        cbvbox.set_focus_vadjustment(sw.get_vadjustment ())
        
        mainvbox.pack_start(sw, gtk.TRUE, gtk.TRUE, 10)

        mainvbox.pack_start(sizeLabel, gtk.FALSE, gtk.FALSE)
                            
        self.dialog.set_size_request(500, 420)
        self.dialog.show_all()

	while 1:
	    rc = self.dialog.run()

	    # they hit cancel, restore original state and quit
	    if rc == 2:
		allpkgs = comp.packagesFullInfo().keys()
		for pkg in allpkgs:
		    (ptype, sel) = comp.packagesFullInfo()[pkg]
		    (optype, osel) = origpkgselection[pkg]

		    if ptype == PKGTYPE_OPTIONAL:
			if osel:
			    if not sel:
				comp.selectOptionalPackage(pkg)
			else:
			    if sel:
				comp.unselectOptionalPackage(pkg)
		allpkgs = comp.metapackagesFullInfo().keys()
		for pkg in allpkgs:
		    (ptype, sel) = comp.metapackagesFullInfo()[pkg]
		    (optype, osel) = origmetapkgselection[pkg]

		    if ptype == PKGTYPE_OPTIONAL:
			if osel:
			    if not sel:
				comp.selectOptionalPackage(pkg)
			else:
			    if sel:
				comp.unselectOptionalPackage(pkg)

	    break
	
        self.dialog.destroy()
	self.setSize()

	if hdrlbl:
	    self.setCompLabel(comp, hdrlbl)
	    
        return
    

    def getScreen(self, comps, dispatch):
    # PackageSelectionWindow tag="sel-group"
	self.comps = comps
	self.dispatch = dispatch

	self.origSelection = self.comps.getSelectionState()

        sw = gtk.ScrolledWindow ()
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)

        box = gtk.VBox (gtk.FALSE, 10)
	box.set_border_width(5)

        self.checkButtons = []
	(parlist, pardict) = orderPackageGroups(self.comps)

	for par in parlist:
	    vbox = gtk.VBox (gtk.FALSE, 2)
	    box.pack_start(vbox, gtk.FALSE, gtk.FALSE)
	    
	    lbl = gtk.Label("")
	    lbl.set_markup("<big><b>%s</b></big>" % (par,))
	    lbl.set_alignment(0.0, 0.0)
	    vbox.pack_start(lbl)

	    for comp in pardict[par]:
		if comp.hidden:
		    continue
		
		pixname = string.lower(comp.id) + ".png"
		fn = self.ics.findPixmap("comps/"+pixname)
		if not fn:
		    print "could not load pix ",pixname
		    pix = None
		else:
		    rawpix = gtk.gdk.pixbuf_new_from_file(fn)
		    sclpix = rawpix.scale_simple(32, 32,
						 gtk.gdk.INTERP_BILINEAR)
		    pix = gtk.Image()
		    pix.set_from_pixbuf(sclpix)

		# vbox for everything
		cvbox = gtk.VBox(gtk.FALSE)

		# create check button and edit button
		# make the comps title + edit button
		hdrhbox=gtk.HBox(gtk.FALSE)
		hdrlabel=gtk.Label("")
		hdrlabel.set_alignment (0.0, 0.5)
		self.setCompLabel(comp, hdrlabel)

		checkButton = gtk.CheckButton()
		checkButton.add(hdrlabel)
		hdrhbox.pack_start(checkButton, gtk.FALSE, gtk.FALSE, 10)

		# now make the url looking button for details
		if comp.name != u"Everything":
		    nlbl = gtk.Label("")
		    nlbl.set_markup('<span foreground="#3030c0"><u>%s</u></span>' % (_('Details'),))
		    editbutton = gtk.Button()
		    editbutton.add(nlbl)
		    editbutton.set_relief(gtk.RELIEF_NONE)
		    al = gtk.Alignment(1.0, 0.0)
		    al.add(editbutton)
		    hdrhbox.pack_start(al, gtk.TRUE, gtk.TRUE, 50)
		    editbutton.connect("clicked", self.editDetails,
				       (comp, hdrlabel))
		    editbutton.set_sensitive(comp.isSelected(justManual = 1))
		else:
		    editbutton = None

		cvbox.pack_start(hdrhbox, gtk.FALSE, gtk.FALSE)

		# now create the description
		dhbox = gtk.HBox(gtk.FALSE)
		dcrackhbox = gtk.HBox(gtk.FALSE)
		dcrackhbox.set_size_request(15, -1)
		dhbox.pack_start(dcrackhbox, gtk.FALSE, gtk.FALSE)
		packed_dhbox = 0
		if pix is not None:
		    al = gtk.Alignment(0.5, 0.5)
		    al.add(pix)
		    packed_dhbox = 1
		    dhbox.pack_start(al, gtk.FALSE, gtk.FALSE)

		# add description if it exists
		descr = getCompGroupDescription(comp)
		if descr is not None:
		    label=gtk.Label("")
		    label.set_alignment (0.0, 0.0)
		    label.set_line_wrap(gtk.TRUE)
		    label.set_size_request(350, -1)
		    label.set_markup("%s" % (_(descr),))
		    packed_dhbox = 1
		    dhbox.pack_start(label, gtk.TRUE, gtk.TRUE,10)

		if packed_dhbox:
		    cvbox.pack_start(dhbox, gtk.FALSE, gtk.FALSE)
		else:
		    dhbox = None

		checkButton.set_active (comp.isSelected(justManual = 1))
		checkButton.connect('toggled', self.componentToggled,
				    (comp, hdrlabel, editbutton))
		self.checkButtons.append ((hdrhbox, dhbox, comp))

		tmphbox = gtk.HBox(gtk.FALSE)
		crackhbox = gtk.HBox(gtk.FALSE)
		crackhbox.set_size_request(30, -1)
		tmphbox.pack_start(crackhbox, gtk.FALSE, gtk.FALSE)
		tmphbox.pack_start(cvbox, gtk.TRUE, gtk.TRUE)
		vbox.pack_start (tmphbox)

        wrapper = gtk.VBox (gtk.FALSE, 0)
        wrapper.pack_start (box, gtk.FALSE)
        
        sw.add_with_viewport (wrapper)
        viewport = sw.get_children()[0]
        viewport.set_shadow_type (gtk.SHADOW_IN)
	viewport.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse ("white"))
        box.set_focus_hadjustment(sw.get_hadjustment ())
        box.set_focus_vadjustment(sw.get_vadjustment ())

        hbox = gtk.HBox (gtk.FALSE, 5)

        self.individualPackages = gtk.CheckButton (
		_("_Select individual packages"))
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

	
