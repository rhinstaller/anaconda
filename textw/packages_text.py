#
# packages_text.py: text mode package selection dialog
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

import rpm
from snack import *
from constants_text import *
from rhpl.translate import _
from hdrlist import orderPackageGroups
from hdrlist import ON_STATES, OFF_STATES

import logging
log = logging.getLogger("anaconda")

class PackageGroupWindow:

    # Unfortunately, the checkboxtree is callback-happy

    def size(self, comps):
	return _("Total install size: %s") % comps.sizeStr()
    
    def updateSize(self, args):
	(label, comps, ct ) = args

	comp = ct.getCurrent()
	list = ct.getSelection()

	try:
	    list.index(comp)
	    if comp.isSelected(justManual = 1): return
	    comp.select()
	except ValueError:
	    if not comp.isSelected(justManual = 1): return
	    comp.unselect()

	label.setText(self.size(comps))

    def __call__(self, screen, grpset, instLanguage, instClass, dispatch):
	origSelection = grpset.getSelectionState()

        ct = CheckboxTree(height = 8, scroll = 1)

        (parlist, pardict) = orderPackageGroups(grpset)
        for par in parlist:
            for grp in pardict[par]:
                if grp.hidden:
                    continue
                ct.append(grp.name, grp, grp.isSelected(justManual = 1))

        cb = Checkbox (_("Select individual packages"), 
			    not dispatch.stepInSkipList("indivpackage"))
        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
	la = Label(self.size(grpset))

	ct.setCallback(self.updateSize, (la, grpset, ct))

        g = GridFormHelp (screen, _("Package Group Selection"), 
			  "packagetree", 1, 4)

        g.add (la, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        g.add (ct, 0, 1, (0, 0, 0, 1))
#        g.add (cb, 0, 2, (0, 0, 0, 1))
        g.add (bb, 0, 3, growx = 1)

	g.addHotKey("F2")

	screen.pushHelpLine (_("<Space>,<+>,<-> selection   |   <F2> Group Details   |   <F12> next screen"))

	while 1:
	    result = g.run()
	    if result != "F2":
		break

	    # if current group is not selected then select it first
	    newSelection = 0
	    cur = ct.getCurrent()
	    lst = ct.getSelection()
	    if cur not in lst:
		newSelection = 1
		try:
		    if not cur.isSelected(justManual = 1):
			cur.select()
		except ValueError:
		    pass
		ct.setEntryValue(cur, 1)

	    # do group details
	    gct = CheckboxTree(height = 8, scroll = 1)

	    origpkgselection = {}
	    for (pkg, val) in cur.packageInfo().items():
		origpkgselection[pkg] = val

	    # make a copy
	    pkgselection = {}
	    for k in origpkgselection.keys():
		pkgselection[k] = origpkgselection[k]

            pkgs = origpkgselection.keys()
            pkgs.sort()
            for pkg in pkgs:
                if grpset.hdrlist.pkgs.has_key(pkg):
                    name = grpset.hdrlist.pkgs[pkg].name
                elif grpset.groups.has_key(pkg):
                    name = grpset.groups[pkg].name
                else:
                    log.warning("unknown package %s" %(pkg,))
                    continue
		gct.append(name, pkg, pkgselection[pkg][1])

	    bb2 = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON))

	    g2 = GridFormHelp (screen, _("Package Group Details"),  "", 1, 4)

	    g2.add (gct, 0, 1, (0, 0, 0, 1))
	    g2.add (bb2, 0, 3, growx = 1)

	    rc2 = g2.runOnce()
	    if bb2.buttonPressed(rc2) == TEXT_CANCEL_CHECK:
		# unselect group if necessary
		if newSelection:
		    try:
			cur.unselect()
		    except:
			pass
		    ct.setEntryValue(cur, 0)
	    else:
		# reflect new packages selected
		selectedlst = gct.getSelection()
		for pkg in origpkgselection.keys():
		    (otype, osel) = origpkgselection[pkg]
		    if pkg in selectedlst:
			if osel in ON_STATES:
			    continue
			cur.selectPackage(pkg)
		    else:
			if osel in OFF_STATES:
			    continue
			cur.unselectPackage(pkg)

        rc = bb.buttonPressed (result)

	screen.popWindow()
	screen.popHelpLine ()
	    
        if rc == TEXT_BACK_CHECK:
	    grpset.setSelectionState(origSelection)
            return INSTALL_BACK

	if cb.selected():
	    dispatch.skipStep("indivpackage", skip = 0)
	else:
	    dispatch.skipStep("indivpackage")

        return INSTALL_OK

class IndividualPackageWindow:
    def get_rpm_desc (self, header):
	desc = string.replace (header[rpm.RPMTAG_DESCRIPTION], "\n\n", "\x00")
	desc = string.replace (desc, "\n", " ")
	desc = string.replace (desc, "\x00", "\n\n")
	return desc

    def printHelp(self, screen, header):
	sg = Grid(2, 2)
	bb = ButtonBar (screen, (TEXT_OK_BUTTON,))

	sg.setField (Label (_("Package :")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
	sg.setField (Label ("%s-%s-%s" % (header[rpm.RPMTAG_NAME],
	                                  header[rpm.RPMTAG_VERSION],
	                                  header[rpm.RPMTAG_RELEASE])),
	             1, 0, anchorLeft = 1)
	sg.setField (Label (_("Size    :")), 0, 1, (0, 0, 1, 0), anchorLeft = 1)
	sg.setField (Label (_("%.1f KBytes") 
		% (header[rpm.RPMTAG_SIZE] / 1024.0)), 1, 1, anchorLeft= 1)

	txt = TextboxReflowed(60, self.get_rpm_desc(header), maxHeight = 10)

	g = GridForm (screen, header[rpm.RPMTAG_NAME], 1, 3)
	g.add (sg, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
	g.add (txt, 0, 1, (0, 0, 0, 1))
	g.add (bb, 0, 2, growx = 1)

	g.runOnce()

    def printSize(self, size):
	if not size:
	    return "      "
        return "%3d.%dM" % (size / 1024, (((size * 10) / 1024) % 10))

    def printTotal(self):
	size = self.total
	self.lbl.setText("%-*s   %4d.%dM" % (self.length, _("Total size"), size / 1024, (((size * 10) / 1024) % 10)))

    def printNum(self, group):
	if self.groupCount[group] == self.groupSelCount[group]:
	    return "*"
	elif self.groupSelCount[group]:
	    return "o"
	else:
	    return " "

    def ctSet(self, header, isOn):
	isSelected = header.isSelected()
	if isSelected and not isOn:
	    header.unselect()
	elif not isSelected and isOn:
	    header.select()

	key = header[rpm.RPMTAG_GROUP]
	if isOn:
	    self.groupSize[key] = self.groupSize[key] + (header[rpm.RPMTAG_SIZE] / 1024)
	    self.total = self.total + (header[rpm.RPMTAG_SIZE] / 1024)
	    self.groupSelCount[key] = self.groupSelCount[key] + 1
	    self.ct.setEntry(header, "%-*s %s" % (self.length,
						  header[rpm.RPMTAG_NAME],
						  self.printSize(header[rpm.RPMTAG_SIZE] / 1024)))
	else:
	    self.groupSize[key] = self.groupSize[key] - (header[rpm.RPMTAG_SIZE] / 1024)
	    self.total = self.total - (header[rpm.RPMTAG_SIZE] / 1024)
	    self.groupSelCount[key] = self.groupSelCount[key] - 1
	    self.ct.setEntry(header, "%-*s" % (self.length + 7, header[rpm.RPMTAG_NAME]))
	self.ct.setEntry(key, "[%s] %-*s %s" % (self.printNum(key),
						self.length - 1, key,
						self.printSize(self.groupSize[key])))
	self.printTotal()

    def ctCallback(self):
	data = self.ct.getCurrent()
	(branch, isOn) = self.ct.getEntryValue(data)
	if not branch:
	    if data.isSelected() and not isOn:
		self.ctSet(data, 0)
	    elif isOn and not data.isSelected():
		self.ctSet(data, 1)
	else:
	    for header in self.groups[data]:
		(branch, isOn) = self.ct.getEntryValue(header)
		if header.isSelected() and not isOn:
		    self.ctSet(header, 0)
		elif isOn and not header.isSelected():
		    self.ctSet(header, 1)

    def __call__(self, screen, comps, hdList):
	origSelection = comps.getSelectionState()

        ct = CheckboxTree(height = 10, scroll = 1)
	self.ct = ct
	self.groups = {}
	self.groupSize = {}
	self.groupCount = {}
	self.groupSelCount = {}
	self.length = 0
	self.total = 0

        # go through all the headers and grok out the group names, placing
        # packages in lists in the groups dictionary.
        
        for key in hdList.packages.keys():
            header = hdList.packages[key]
            # don't show this package if it is in the base group
            if not comps["Base"].includesPackage (header):
		group = header[rpm.RPMTAG_GROUP]
		if not self.groups.has_key (group):
		    self.groups[group] = []
		    self.groupSize[group] = 0
		    self.groupCount[group] = 0
		    self.groupSelCount[group] = 0
		self.groups[group].append (header)
		self.length = max((self.length, len(header[rpm.RPMTAG_NAME])))
		self.groupCount[group] = self.groupCount[group] + 1
		if header.isSelected():
		    self.groupSize[group] = self.groupSize[group] + (header[rpm.RPMTAG_SIZE] / 1024)
		    self.groupSelCount[group] = self.groupSelCount[group] + 1

        # now insert the groups into the list, then each group's packages
        # after sorting the list
        def cmpHdrName(first, second):
            if first[rpm.RPMTAG_NAME] < second[rpm.RPMTAG_NAME]:
                return -1
            elif first[rpm.RPMTAG_NAME] == second[rpm.RPMTAG_NAME]:
                return 0
            return 1
        
	keys = self.groups.keys ()
        keys.sort ()
	for key in keys:
	    self.length = max((self.length, 1+len(key)))

	# comps.size() is in meg, we found in k
	self.total = comps.size() * 1024

        index = 0
        for key in keys:
	    self.groups[key].sort (cmpHdrName)
	    name = "[%s] %-*s %s" % (self.printNum(key), self.length - 1, key, self.printSize(self.groupSize[key]))
	    ct.append (name, key)
	    for header in self.groups[key]:
		if header.isSelected():
		    name = "%-*s %s" % (self.length, header[rpm.RPMTAG_NAME], self.printSize(header[rpm.RPMTAG_SIZE] / 1024))
		else:
		    name = "%-*s" % (self.length + 7, header[rpm.RPMTAG_NAME])
		ct.addItem (name, (index, snackArgs["append"]),
                            header, header.isSelected())
            index = index + 1
                
	ct.setCallback(self.ctCallback)
		
        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

	self.lbl = Label ("")
	self.printTotal()

	g = GridFormHelp (screen, _("Individual Package Selection"),
                          "indvpackage", 1, 3)
	g.add (ct, 0, 0, (0, 0, 0, 0))
	g.add (self.lbl, 0, 1, (4, 0, 0, 1), anchorLeft = 1)
	g.add (bb, 0, 2, growx = 1)

	g.addHotKey("F2")

	screen.pushHelpLine (_("   <Space>,<+>,<-> selection   |   <F1> help   |   <F2> package description"))

	while 1:
	    result = g.run ()
	    if result != "F2":
		break
	    header = self.ct.getCurrent()
	    (branch, isOn) = self.ct.getEntryValue(header)
	    if not branch:
		self.printHelp(screen, header)

	screen.popWindow()

	screen.popHelpLine ()

        rc = bb.buttonPressed (result)
        
        if rc == TEXT_BACK_CHECK:
	    comps.setSelectionState(origSelection)
            return INSTALL_BACK

        return INSTALL_OK

class PackageDepWindow:
    def size(self, comps):
	return _("Total install size: %s") % comps.sizeStr()

    def radiocb (self, args):
        (label, comps, deps, widget) = args
        if widget == self.inst:
            comps.selectDeps (deps)
            comps.selectDepCause (deps)
        elif widget == self.cause:
            comps.unselectDeps (deps)
            comps.unselectDepCause (deps)
        elif widget == self.ignore:
            comps.unselectDeps (deps)
            comps.selectDepCause (deps)
        else:
            raise RuntimeError, "never reached"
        
	label.setText(self.size(comps))

    def __call__(self, screen, comps, deps):

	origSelection = comps.getSelectionState()
        comps.selectDeps (deps)

        g = GridFormHelp(screen, _("Package Dependencies"), 
			 "packagedeps", 1, 8)
        g.add (TextboxReflowed (50, _("Some of the packages you have "
                                      "selected to install require "
                                      "packages you have not selected. If "
                                      "you just select OK all of those "
                                      "required packages will be "
                                      "installed.")), 0, 0, (0, 0, 0, 1))
        g.add (Label ("%-20s %-20s" % (_("Package"), _("Requirement"))), 0, 1, anchorLeft = 1)
        text = ""
        for name, suggest in deps:
            text = text + "%-20s %-20s\n" % (name, suggest)
        
        if len (deps) > 4:
            scroll = 1
        else:
            scroll = 0
            
        g.add (Textbox (45, 4, text, scroll = scroll), 0, 2)

        la = Label(self.size(comps))
        g.add (la, 0, 3, anchorRight = 1)

        instt = _("Install packages to satisfy dependencies")
        causet = _("Do not install packages that have dependencies")
        ignt = _("Ignore package dependencies")
        maxlen = max ((len (instt), len (causet), len (ignt)))

        def pad (pad, text):
            return "%-*s" % (pad, text)
        
        self.inst = SingleRadioButton (pad (maxlen, instt), None, 1)
	self.inst.setCallback(self.radiocb, (la, comps, deps, self.inst))
        g.add (self.inst, 0, 4, (0, 1, 0, 0), anchorLeft = 1)

        self.cause = SingleRadioButton (pad (maxlen, causet), self.inst, 0)
	self.cause.setCallback(self.radiocb, (la, comps, deps, self.cause))
        g.add (self.cause, 0, 5, anchorLeft = 1)
        
        self.ignore = SingleRadioButton (pad (maxlen, ignt), self.cause, 0)
        g.add (self.ignore, 0, 6, (0, 0, 0, 1), anchorLeft = 1)
	self.ignore.setCallback(self.radiocb, (la, comps, deps, self.ignore))
        
        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        g.add (bb, 0, 7, growx = 1)

        result = g.runOnce ()

        rc = bb.buttonPressed (result)
        if rc == TEXT_BACK_CHECK:
            comps.setSelectionState(origSelection)
            return INSTALL_BACK

        if self.ignore.selected():
            return INSTALL_OK

        return INSTALL_OK

