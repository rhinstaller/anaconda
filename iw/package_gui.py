#
# package_gui.py: package group and individual package selection screens
#
# Brent Fox <bfox@redhat.com>
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2000-2003 Red Hat, Inc.
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
import gtk
import gobject
import checklist
from iw_gui import *
from string import *
from thread import *
from examine_gui import *
from rhpl.translate import _, N_
from hdrlist import orderPackageGroups, getGroupDescription
from hdrlist import PKGTYPE_MANDATORY, PKGTYPE_DEFAULT, PKGTYPE_OPTIONAL
from hdrlist import ON, MANUAL_ON, OFF, MANUAL_OFF, MANUAL_NONE
from hdrlist import ON_STATES, OFF_STATES
from hdrlist import Package, Group
from rhpl.log import log
import packages


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
        SHOW_WATCH_MIN = 200
        if len(packages) > SHOW_WATCH_MIN:
            cw = self.ics.getICW()
            cw.busyCursorPush()
        
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
        if len(packages) > SHOW_WATCH_MIN:
            cw.busyCursorPop()

    def select_group(self, selection):
        (model, iter) = selection.get_selected()
        if iter:
            currentGroup = model.get_value(iter, 1)

            self.packageList.clear()

            if not self.flat_groups.has_key(currentGroup):
                self.selectAllButton.set_sensitive(False)
                self.unselectAllButton.set_sensitive(False)
                return

            self.selectAllButton.set_sensitive(True)
            self.unselectAllButton.set_sensitive(True)
            
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
        desc = replace (desc, "&", "&amp;")
        desc = replace (desc, "\x00", "\n\n")
        return desc

    def make_group_list(self, grpset, displayBase = 0):
        """Go through all of the headers and get group names, placing
           packages in the dictionary.  Also have in the upper level group"""
        
        groups = {}

        # special group for listing all of the packages (aka old flat view)
        groups["allpkgs"] = []
        
        for key in grpset.hdrlist.pkgs.keys():
            header = grpset.hdrlist.pkgs[key]

            group = header[rpm.RPMTAG_GROUP]
	    hier = string.split(group, '/')
            toplevel = hier[0]

            # make sure the dictionary item exists for group and toplevel
            # note that if group already exists, toplevel must also exist
            if not groups.has_key (group):
                groups[group] = []

                if not groups.has_key(toplevel):
                    groups[toplevel] = []

            # don't display package if it is in the Base group
            if not grpset.groups["core"].includesPackage(header) or displayBase:
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
        text = _("Total install size: %s") % (self.grpset.sizeStr(),)
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
                for pkg in self.pkgs.values():
                    if not self.grpset.groups["core"].includesPackage(pkg):
                        self.allPkgs.append(pkg)
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
			return True
		    else:
			# didnt match for some reason, lets plow ahead
			self.ignoreKeypress = None
		
		self.packageList.store.set_value(iter, 0, not val)

		if not val:
		    self.pkgs[package].select()
		else:
		    self.pkgs[package].unselect()

		self.updateSize()
                return True

	return False
	    
		
    # IndividualPackageSelectionWindow tag="sel-indiv"
    def getScreen (self, grpset):
        self.grpset = grpset
        self.pkgs = self.grpset.hdrlist
        self.allPkgs = None
        
        self.packageTreeView = gtk.TreeView()

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Groups', renderer, text=0)
        column.set_clickable(True)
        self.packageTreeView.append_column(column)
        self.packageTreeView.set_headers_visible(False)
        self.packageTreeView.set_rules_hint(False)
        self.packageTreeView.set_enable_search(False)
        
        self.flat_groups = self.make_group_list(grpset)
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

        self.leftVBox = gtk.VBox(False)

        # FIXME should these stay or go?
        # tree/flat radio buttons... 
        optionHBox = gtk.HBox()
        self.treeRadio = gtk.RadioButton(None, (_("_Tree View")))
        self.treeRadio.connect("clicked", self.changePkgView)
        self.flatRadio = gtk.RadioButton(self.treeRadio, (_("_Flat View")))
        optionHBox.pack_start(self.treeRadio)
        optionHBox.pack_start(self.flatRadio)
        self.leftVBox.pack_start(optionHBox, False)
        
        self.leftVBox.pack_start(self.sw, True)
        packageHBox.pack_start(self.leftVBox, False)

        self.packageList = PackageCheckList(2)
        self.packageList.checkboxrenderer.connect("toggled",
						  self.toggled_package)

        self.packageList.set_enable_search(True)

        self.sortType = "Package"
        self.packageList.set_column_title (1, (_("_Package")))
        self.packageList.set_column_sizing (1, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
        self.packageList.set_column_title (2, (_("_Size (MB)")))
        self.packageList.set_column_sizing (2, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
        self.packageList.set_headers_visible(True)

        self.packageList.set_column_min_width(0, 16)
        self.packageList.set_column_clickable(0, False)
        
        self.packageList.set_column_clickable(1, True)
        self.packageList.set_column_sort_id(1, 1)
        self.packageList.set_column_clickable(2, True)
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
        descVBox.pack_start (gtk.HSeparator (), False, padding=2)

        hbox = gtk.HBox ()
        bb = gtk.HButtonBox ()
        bb.set_layout (gtk.BUTTONBOX_END)

        self.totalSizeLabel = gtk.Label (_("Total size: "))
        hbox.pack_start (self.totalSizeLabel, False, False, 0)

        self.selectAllButton = gtk.Button (_("Select _all in group"))
        bb.pack_start (self.selectAllButton, False)
        self.selectAllButton.connect ('clicked', self.select_all, 1)

        self.unselectAllButton = gtk.Button(_("_Unselect all in group"))
        bb.pack_start(self.unselectAllButton, False)
        self.unselectAllButton.connect ('clicked', self.select_all, 0)
        
        hbox.pack_start (bb)

        self.selectAllButton.set_sensitive (False)
        self.unselectAllButton.set_sensitive (False)

        descVBox.pack_start (hbox, False)

        descSW = gtk.ScrolledWindow ()
        descSW.set_border_width (5)
        descSW.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        descSW.set_shadow_type(gtk.SHADOW_IN)

        self.packageDesc = gtk.TextView()

        buffer = gtk.TextBuffer(None)
        self.packageDesc.set_buffer(buffer)
        self.packageDesc.set_editable(False)
        self.packageDesc.set_cursor_visible(False)
        self.packageDesc.set_wrap_mode(gtk.WRAP_WORD)
        descSW.add (self.packageDesc)
        descSW.set_size_request (-1, 100)

        descVBox.pack_start (descSW)

        vbox = gtk.VBox ()
        vbox.pack_start (packageHBox)
        vbox.pack_start (descVBox, False)

	self.updateSize()

        return vbox

class PackageSelectionWindow (InstallWindow):
    windowTitle = N_("Package Group Selection")
    htmlTag = "sel-group"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        self.ics = ics
        self.ics.setNextEnabled (1)
        self.files_found = "False"
        
    def getPrev (self):
	self.grpset.setSelectionState(self.origSelection)

    def getNext (self):
	if self.individualPackages.get_active():
	    self.dispatch.skipStep("indivpackage", skip = 0)
	else:
	    self.dispatch.skipStep("indivpackage")

	# jsut to be sure if we come back
	self.savedStateDict = {}
	self.savedStateFlag = 0

        return None

    def setSize(self):
        self.sizelabel.set_text (_("Total install size: %s") % 
					self.grpset.sizeStr())

    # given a value, set all components except Everything and Base to
    # that value.  Handles restoring state if it exists
    def setComponentsSensitive(self, comp, value):
	tmpval = self.ignoreComponentToggleEvents
	self.ignoreComponentToggleEvents = 1
	for (cb, lbl, al, ebutton, cbox, cbox2, cbcomp) in self.checkButtons:
	    if cbcomp.id == comp.id:
		continue

	    if value:
		if cbcomp.id not in ["everything", "base"]:
#		    print "restoring checkbutton for ",cbcomp.name," at state ",self.savedStateDict[cbcomp.name]
		    if self.savedStateFlag and self.savedStateDict[cbcomp.id]:
			cb.set_active(1)
		    else:
			cb.set_active(0)
		else:
		    cb.set_active(0)
	    else:
		cb.set_active(0)

	    if cb.get_active():
		if ebutton:
		    al.add(ebutton)
		    al.show_all()
	    else:
		if ebutton:
		    if ebutton in al.get_children():
			al.remove(ebutton)

	    if lbl:
		self.setCompCountLabel(cbcomp, lbl)
	    if cbox:
		cbox.set_sensitive(value)
	    if cbox2:
		cbox2.set_sensitive(value)

	self.ignoreComponentToggleEvents = tmpval

    def componentToggled(self, widget, data):
        cw = self.ics.getICW()
	(comp, lbl, count, al, ebutton) = data
	newstate = widget.get_active()
	if self.ignoreComponentToggleEvents:
	    return

        cw.busyCursorPush()
        # turn on all the comps we selected
	if newstate:
            if ebutton:
                al.add(ebutton)
                al.show_all()
	    comp.select ()
	else:
            if ebutton in al.get_children():
                al.remove(ebutton)

	    # dont turn off Base, and if we're turning off everything
	    # we need to be sure language support stuff is on
	    if comp.id != "base":
		comp.unselect ()
		if comp.id == "everything":
		    packages.selectLanguageSupportGroups(self.grpset, self.langSupport)

        if count:
            self.setCompCountLabel(comp, count)

        if comp.id == "everything" or comp.id == "base":
	    
	    self.ignoreComponentToggleEvents = 1
	    # save state of buttons if they hit everything or minimal
#	    print "entered, savedstateflag = ",self.savedStateFlag
	    if not self.savedStateFlag and newstate:
		self.savedStateDict = {}
		self.savedStateFlag = 1
		savestate = 1
	    else:
		savestate = 0

	    for c in self.grpset.groups.values():
		if c.id in ["everything", "base"]:
		    continue
		
		if newstate:
			sel = c.isSelected(justManual = 1)
#			print "saving ",c.name," at state ",sel
			if savestate:
			    self.savedStateDict[c.id] = sel
			if sel:
			    c.unselect()
		else:
#		    print "restoring ",c.name," at state ",self.savedStateDict[c.name]
		    if self.savedStateFlag and self.savedStateDict[c.id]:
			c.select()

	    # turn on lang support if we're minimal and enabling
	    if comp.id == "base" and newstate:
		packages.selectLanguageSupportGroups(self.grpset, self.langSupport)

	    self.setComponentsSensitive(comp, not newstate)

	    self.ignoreComponentToggleEvents = 0
	else:
	    self.savedStateDict = {}
	    self.savedStateFlag = 0

	# after all this we need to recompute total size
	self.setSize()
        cw.busyCursorPop()

    def pkgGroupMemberToggled(self, widget, data):
	(comp, sizeLabel, pkg) = data
	(ptype, sel) = comp.packageInfo()[pkg]

	# dont select or unselect if its already in that state
	if widget.get_active():
            if sel not in ON_STATES:
                comp.selectPackage(pkg)
	    else:
		log("%s already selected, not selecting!" %(pkg,))
	else:
            if sel in ON_STATES:
                comp.unselectPackage(pkg)
	    else:
		log("%s already unselected, not unselecting!" %(pkg,))

	if sizeLabel:
	    self.setDetailSizeLabel(comp, sizeLabel)

    # have to do magic to handle 'Minimal'
    def setCheckButtonState(self, cb, comp):
	state = 0
	if comp.id != "base":
	    state = comp.isSelected(justManual = 1)	    
	    cb.set_active (state)
	else:
	    state = 1
	    for c in self.grpset.groups.values():
		# ignore base and langsupport files pulled in by 'minimal'
		if c.id == "base" or self.grpset.groups[c.id].langonly is not None:
		    continue
		
		if c.isSelected(justManual = 1):
		    state = 0
		    break

	    cb.set_active (state)

	return state
	
    def getStats(self, comp):
        # FIXME: metapkgs
#	allpkgs = comp.packageInfo().keys() + comp.metapackagesFullInfo().keys()
	allpkgs = comp.packageInfo()
	
	if comp.id == "everything":
	    total = len(allpkgs.keys())
	    if comp.isSelected(justManual = 1):
		selected = total
	    else:
		selected = 0
	    return (selected, total)
	
	total = 0
	selected = 0
	for pkg in allpkgs.values():
	    total = total + 1
	    (ptype, sel) = pkg
            if sel in ON_STATES:
		selected = selected + 1

        return (selected, total)

    def setDetailSizeLabel(self, comp, sizeLabel):
        text = _("Total install size: %s") % (self.grpset.sizeStr(),)
	sizeLabel.set_text(text)

    def setCompLabel(self, comp, label):
        if comp.id == "base":
	    nm = _("Minimal")
	else:
	    nm = comp.name
	label.set_markup("<b>%s</b>" % (nm,))

    def setCompCountLabel(self, comp, label):
	(selpkg, totpkg) = self.getStats(comp)
        if not comp.isSelected(justManual = 1):
            selpkg = 0

	if comp.id == "everything" or comp.id == "base":
	    txt = ""
	else:
	    txt = "<b>[%d/%d]</b>" % (selpkg, totpkg)
	    
	label.set_markup(txt)

    def editDetails(self, button, data):
	# do all magic for packages and metapackages
	def getDescription(obj, comp):
            if self.grpset.hdrlist.pkgs.has_key(obj):
                obj = self.grpset.hdrlist.pkgs[obj]
            elif self.grpset.groups.has_key(obj):
                obj = self.grpset.groups[obj]
            basedesc = obj.getDescription()

	    if basedesc is not None:
		desc = replace (basedesc, "\n\n", "\x00")
		desc = replace (desc, "\n", " ")
		desc = replace (desc, "\x00", "\n\n")
	    else:
		desc = ""
	    return "%s - %s" % (obj.name, desc)

	# pull out member sorted by name
	def getNextMember(goodpkgs, comp, domandatory = 0):
	    curpkg = None
	    for pkg in goodpkgs:
		if domandatory:
		    (ptype, sel) = comp.packageInfo()[pkg]
		    if ptype != PKGTYPE_MANDATORY:
			continue

		foundone = 1
		if curpkg is not None:
		    if pkg < curpkg:
			curpkg = pkg
		else:
		    curpkg = pkg

	    return curpkg


	#
	# START OF editDetails
	#
	# backup state
	(comp, hdrlbl, countlbl, compcb) = data
	origpkgselection = {}
	for (pkg, val) in comp.packageInfo().items():
	    origpkgselection[pkg] = val
	    
        self.dialog = gtk.Dialog(_("Details for '%s'") % (comp.name,))
        gui.addFrame(self.dialog)
        self.dialog.add_button('gtk-cancel', 2)
        self.dialog.add_button('gtk-ok', 1)
        self.dialog.set_position(gtk.WIN_POS_CENTER)

        mainvbox = self.dialog.vbox

	lblhbox = gtk.HBox(False)
        lbl = gtk.Label(_("A package group can have both Base and "
                          "Optional package members.  Base packages "
                          "are always selected as long as the package group "
			  "is selected.\n\nSelect the optional packages "
			  "to be installed:"))
        lbl.set_line_wrap(True)
	lbl.set_size_request(475, -1)
	lbl.set_alignment(0.0, 0.5)
	lblhbox.pack_start(lbl, True, True)

        pix = gui.readImageFromFile("package-selection.png")

	if pix is not None:
	    al = gtk.Alignment(0.0, 0.0)
	    al.add(pix)
	    lblhbox.pack_start(al, False, False)
	    
        mainvbox.pack_start(lblhbox, False, False)

        cbvbox = gtk.VBox(False)
	cbvbox.set_border_width(5)
	
	# will pack this last, need to create it for toggle callback below
        sizeLabel = gtk.Label("")
	self.setDetailSizeLabel(comp, sizeLabel)

        goodpkgs = comp.packageInfo().keys()
        # FIXME
#        goodpkgs = comp.packagesFullInfo().keys() + comp.metapackagesFullInfo().keys()


	# first show default members, if any
	haveBase = 0
	next = getNextMember(goodpkgs, comp, domandatory = 1)
	if next is not None:
	    haveBase = 1
	    lbl = gtk.Label("")
	    lbl.set_markup("<b>%s</b>" % (_("Base Packages"),))
	    lbl.set_alignment(0.0, 0.0)
	    cbvbox.pack_start(lbl, False, False);
	    while 1:
		next = getNextMember(goodpkgs, comp, domandatory = 1)
		if next is None:
		    break

		goodpkgs.remove(next)
		desc = getDescription(next, comp)
		lbl = gtk.Label(desc)
		lbl.set_alignment(0.0, 0.0)
		lbl.set_property("use-underline", False)

		thbox = gtk.HBox(False)
		chbox = gtk.HBox(False)
		chbox.set_size_request(10,-1)
		thbox.pack_start(chbox, False, False)
		thbox.pack_start(lbl, True, True)

		cbvbox.pack_start(thbox, False, False)

	# now the optional parts, if any
	next = getNextMember(goodpkgs, comp, domandatory = 0)
	if next is not None:
	    spacer = gtk.Fixed()
	    spacer.set_size_request(-1, 10)
	    cbvbox.pack_start(spacer, False, False)
	    
	    lbl = gtk.Label("")
	    lbl.set_markup("<b>%s</b>" % (_("Optional Packages"),))
	    lbl.set_alignment(0.0, 0.0)
	    cbvbox.pack_start(lbl, False, False)
	    while 1:
		next = getNextMember(goodpkgs, comp, domandatory = 0)
		if next is None:
		    break

		goodpkgs.remove(next)

		desc = getDescription(next, comp)
		lbl = gtk.Label(desc)
		lbl.set_alignment(0.0, 0.0)
		lbl.set_property("use-underline", False)
		cb = gtk.CheckButton()
		cb.add(lbl)
		(ptype, sel) = comp.packageInfo()[next]
		cb.set_active((sel in ON_STATES))
		cb.connect("toggled", self.pkgGroupMemberToggled,
			   (comp, sizeLabel, next))

		thbox = gtk.HBox(False)
		chbox = gtk.HBox(False)
		chbox.set_size_request(10,-1)
		thbox.pack_start(chbox, False, False)
		thbox.pack_start(cb, True, True)

		cbvbox.pack_start(thbox, False, False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        wrapper = gtk.VBox (False, 0)
        wrapper.pack_start (cbvbox, False)
        
        sw.add_with_viewport (wrapper)
        viewport = sw.get_children()[0]
        viewport.set_shadow_type (gtk.SHADOW_IN)
	viewport.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse ("white"))
        cbvbox.set_focus_hadjustment(sw.get_hadjustment ())
        cbvbox.set_focus_vadjustment(sw.get_vadjustment ())
        
        mainvbox.pack_start(sw, True, True, 10)

        mainvbox.pack_start(sizeLabel, False, False)
                            
        self.dialog.set_size_request(550, 420)
        self.dialog.show_all()

	while 1:
	    rc = self.dialog.run()

	    # they hit cancel, restore original state and quit
	    if rc == 2:
		allpkgs = comp.packageInfo().keys()
		for pkg in allpkgs:
		    (ptype, sel) = comp.packageInfo()[pkg]
		    (optype, osel) = origpkgselection[pkg]

                    if (osel == sel):
                        pass
                    elif (osel not in OFF_STATES) and (sel not in ON_STATES):
                        comp.selectPackage(pkg)
                    elif (osel not in ON_STATES) and (sel not in OFF_STATES):
                        comp.unselectPackage(pkg)
	    break
	
        self.dialog.destroy()
	self.setSize()

	if countlbl:
	    self.setCompCountLabel(comp, countlbl)

	(selpkg, totpkg) = self.getStats(comp)
	if selpkg < 1:
	    if compcb:
		compcb.set_active(0)
        return

    def focusIdleHandler(self, data):
	if not self.needToFocus:
	    return

	if self.scrolledWindow is None:
	    return

	vadj = self.scrolledWindow.get_vadjustment()
	swmin = vadj.lower
	swmax = vadj.upper
	pagesize = vadj.page_size
	curval = vadj.get_value()

	self.scrolledWindow.get_vadjustment().set_value(swmax-pagesize)

	if self.idleid is not None:
	    gobject.source_remove(self.idleid)

	self.idleid = None
	self.needToFocus = 0
	
	

    def getScreen(self, grpset, langSupport, instClass, dispatch):

    # PackageSelectionWindow tag="sel-group"
        ICON_SIZE = 32
        
	self.grpset = grpset
	self.langSupport = langSupport
	self.dispatch = dispatch

	self.origSelection = self.grpset.getSelectionState()

        self.checkButtons = []

	# used to save buttons state if they hit everything or minimal
	self.savedStateDict = {}
	self.savedStateFlag = 0
	self.ignoreComponentToggleEvents = 0

	(parlist, pardict) = orderPackageGroups(self.grpset)

        topbox = gtk.VBox(False, 3)
        topbox.set_border_width(3)
        
        checkGroup = gtk.SizeGroup(gtk.SIZE_GROUP_BOTH)
        countGroup = gtk.SizeGroup(gtk.SIZE_GROUP_BOTH)
        detailGroup = gtk.SizeGroup(gtk.SIZE_GROUP_BOTH)

        minimalActive = 0
	minimalComp = None
	minimalCB = None
	everythingActive = 0
	everythingComp = None
	everythingCB = None
	for par in parlist:
            # don't show the top-level if there aren't any groups in it
            if len(pardict[par]) == 0:
                continue
            
            # set the background to our selection color
	    eventBox = gtk.EventBox()
	    eventBox.modify_bg(gtk.STATE_NORMAL,
                               gtk.gdk.color_parse("#727fb2"))
	    lbl = gtk.Label("")
	    lbl.set_markup("<span foreground='white'><big><b>"
                           "%s</b></big></span>" % (par,))
	    lbl.set_alignment(0.0, 0.0)
            pad = gtk.Alignment(0.0, 0.0)
            pad.add(lbl)
            pad.set_border_width(3)
            eventBox.add(pad)
            topbox.pack_start(eventBox)

	    for comp in pardict[par]:
		if comp.hidden:
                    if comp.id != "base":
			continue
		    else:
			if not instClass.showMinimal:
			    continue
			
		pixname = string.lower(comp.id) + ".png"
                pix = gui.readImageFromFile("comps/"+pixname,
                                            height = ICON_SIZE,
                                            width = ICON_SIZE)

                compbox = gtk.HBox(False, 5)                

                spacer = gtk.Fixed()
                spacer.set_size_request(30, -1)
                compbox.pack_start(spacer, False, False)

		# create check button and edit button
		# make the comps title + edit button
		hdrlabel=gtk.Label("")
		hdrlabel.set_alignment (0.0, 0.5)
		self.setCompLabel(comp, hdrlabel)

		checkButton = gtk.CheckButton()
		checkButton.add(hdrlabel)
                checkGroup.add_widget(checkButton)
                compbox.pack_start(checkButton)

		count=gtk.Label("")
		count.set_alignment (1.0, 0.5)
		self.setCompCountLabel(comp, count)
                countGroup.add_widget(count)
                compbox.pack_start(count, False, False)

                spacer = gtk.Fixed()
                spacer.set_size_request(15, -1)
                compbox.pack_start(spacer, False, False)
                
                buttonal = gtk.Alignment(0.5, 0.5)
                detailGroup.add_widget(buttonal)
                compbox.pack_start(buttonal, False, False)

		# now make the url looking button for details
		if comp.id != "everything" and comp.id != "base":
		    nlbl = gtk.Label("")
                    selected = comp.isSelected(justManual = 1)
                    nlbl.set_markup('<span foreground="#3030c0"><u>'
                                    '%s</u></span>' % (_('Details'),))
		    editbutton = gtk.Button()
		    editbutton.add(nlbl)
		    editbutton.set_relief(gtk.RELIEF_NONE)
		    editbutton.connect("clicked", self.editDetails,
				       (comp, hdrlabel, count, checkButton))
                    if comp.isSelected(justManual = 1):
                        buttonal.add(editbutton)
		else:
		    editbutton = None

                topbox.pack_start(compbox)

                detailbox = gtk.HBox(False)

                spacer = gtk.Fixed()
                spacer.set_size_request(45, -1)
                detailbox.pack_start(spacer, False, False)
                
		# icon
		if pix is not None:
		    al = gtk.Alignment(0.5, 0.5)
		    al.add(pix)
                    detailbox.pack_start(al, False, False, 10)
                    
		# add description if it exists
		descr = getGroupDescription(comp)
		if descr is not None:
		    label=gtk.Label("")
		    label.set_alignment (0.0, 0.0)
		    label.set_line_wrap(True)

                    if  gtk.gdk.screen_width() > 640:
                        wraplen = 350
                    else:
                        wraplen = 250

		    label.set_size_request(wraplen, -1)
		    label.set_markup("%s" % (_(descr),))
                    detailbox.pack_start(label, True)
                topbox.pack_start(detailbox)

		state = self.setCheckButtonState(checkButton, comp)
                if comp.id == "base":
		    minimalActive = state
		    minimalComp = comp
		    minimalCB = checkButton
		elif comp.id == "everything":
		    everythingActive = state
		    everythingComp = comp
		    everythingCB = checkButton
		    
		checkButton.connect('toggled', self.componentToggled,
				    (comp, hdrlabel, count, buttonal,
                                     editbutton))
		self.checkButtons.append ((checkButton, count, buttonal, editbutton, compbox, detailbox, comp))

            # add some extra space to the end of each group
            spacer = gtk.Fixed()
            spacer.set_size_request(-1, 3)
            topbox.pack_start(spacer, False, False)

	# hack to make everything and minimal act right
        sw = gtk.ScrolledWindow()
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        viewport = gtk.Viewport(sw.get_hadjustment(), sw.get_vadjustment())
        sw.add(viewport)
        viewport.add(topbox)
        viewport.set_property('shadow-type', gtk.SHADOW_IN)
	viewport.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))
        topbox.set_focus_hadjustment(sw.get_hadjustment())
        topbox.set_focus_vadjustment(sw.get_vadjustment())

	# save so we can scrfoll if needed
	self.scrolledWindow = sw
	self.needToFocus = 0

	# if special case we do things a little differently
	if minimalActive:
	    self.setComponentsSensitive(minimalComp, 0)
	    sw.set_focus_child(minimalCB)
	    self.needToFocus = 1
	elif everythingActive:
	    self.setComponentsSensitive(everythingComp, 0)
	    sw.set_focus_child(everythingCB)
	    self.needToFocus = 1

	if self.needToFocus:
	    self.idleid = gobject.idle_add(self.focusIdleHandler, None)

	# pack rest of screen
        hbox = gtk.HBox (False, 5)

        self.individualPackages = gtk.CheckButton (
		_("_Select individual packages"))
        self.individualPackages.set_active (
		not dispatch.stepInSkipList("indivpackage"))
#        hbox.pack_start (self.individualPackages, False)

        self.sizelabel = gtk.Label ("")
        self.setSize()
        hbox.pack_start (self.sizelabel, True)
        
        vbox = gtk.VBox (False, 5)
        vbox.pack_start (sw, True)
        vbox.pack_start (hbox, False)
        vbox.set_border_width (5)

        return vbox


class PackageCheckList(checklist.CheckList):

    def create_columns(self, columns):
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Text', renderer, text = 1)
        column.set_clickable(False)
        self.append_column(column)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Size', renderer, text = 2)
        column.set_clickable(False)
        self.append_column(column)
    
    def __init__(self, columns = 2):
        store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
                              gobject.TYPE_STRING, gobject.TYPE_INT)

	checklist.CheckList.__init__(self, columns=columns,
				     custom_store = store)

	
