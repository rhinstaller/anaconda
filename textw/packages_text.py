import rpm
#import gettext
from snack import *
from constants_text import *
from translate import _

class PackageGroupWindow:

    # Unfortunately, the checkboxtree is callback-happy

    def size(self, comps):
	return _("Total install size: %s") % comps.sizeStr()
    
    def updateSize(self, args):
	(label, todo, ct ) = args

	comp = ct.getCurrent()
	list = ct.getSelection()

	try:
	    list.index(comp)
	    if comp.isSelected(justManual = 1): return
	    comp.select()
	except ValueError:
	    if not comp.isSelected(justManual = 1): return
	    comp.unselect()

	label.setText(self.size(todo.comps))

    def __call__(self, screen, todo, individual):
        # be sure that the headers and comps files have been read.
	todo.getHeaderList()
        todo.getCompsList()

	origSelection = todo.comps.getSelectionState()

        ct = CheckboxTree(height = 8, scroll = 1)
        klass = todo.getClass ()
        showgroups = klass.getOptionalGroups()
        for comp in todo.comps:
            show = 0
            if showgroups:
                try:
                    showgroups.index (comp.name)
                    show = 1
                except ValueError:
                    # comp not in show list
                    pass
            else:
                show = not comp.hidden
            if show:
                ct.append(_(comp.name), comp, comp.isSelected(justManual = 1))

        cb = Checkbox (_("Select individual packages"), individual.get ())
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))
	la = Label(self.size(todo.comps))

	ct.setCallback(self.updateSize, (la, todo, ct))

        g = GridFormHelp (screen, _("Package Group Selection"), 
			  "components", 1, 4)

        g.add (la, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        g.add (ct, 0, 1, (0, 0, 0, 1))
        g.add (cb, 0, 2, (0, 0, 0, 1))
        g.add (bb, 0, 3, growx = 1)

        result = g.runOnce()

        rc = bb.buttonPressed (result)

        if rc == "back":
	    todo.comps.setSelectionState(origSelection)
            return INSTALL_BACK

	individual.set (cb.selected())

        return INSTALL_OK

class IndividualPackageWindow:
    def get_rpm_desc (self, header):
	desc = string.replace (header[rpm.RPMTAG_DESCRIPTION], "\n\n", "\x00")
	desc = string.replace (desc, "\n", " ")
	desc = string.replace (desc, "\x00", "\n\n")
	return desc

    def printHelp(self, screen, header):
	sg = Grid(2, 2)
	bb = ButtonBar (screen, ((_("OK"), "ok"),))

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

    def __call__(self, screen, todo, individual):
        if not individual.get():
            return
	todo.getHeaderList()
        todo.getCompsList()
	origSelection = todo.comps.getSelectionState()

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
        
        for key in todo.hdList.packages.keys():
            header = todo.hdList.packages[key]
            # don't show this package if it is in the base group
            if not todo.comps["Base"].includesPackage (header):
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
	self.total = todo.comps.size() * 1024

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
		
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

	self.lbl = Label ("")
	self.printTotal()

	g = GridFormHelp (screen, _("Package Group Selection"), "packagetree", 
			    1, 3)
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
        
        if rc == "back":
	    todo.comps.setSelectionState(origSelection)
            return INSTALL_BACK

        return INSTALL_OK

class PackageDepWindow:
    moredeps = None
    def size(self, comps):
	return _("Total install size: %s") % comps.sizeStr()

    def radiocb (self, args):
        (label, todo, widget) = args
        if widget == self.inst:
            todo.selectDeps (self.deps)
            todo.selectDepCause (self.deps)
        elif widget == self.cause:
            todo.unselectDeps (self.deps)
            todo.unselectDepCause (self.deps)
        elif widget == self.ignore:
            todo.unselectDeps (self.deps)
            todo.selectDepCause (self.deps)
        else:
            raise RuntimeError, "never reached"
        
	label.setText(self.size(todo.comps))

    def __call__(self, screen, todo):
        if not PackageDepWindow.moredeps:
            self.deps = todo.verifyDeps ()
        else:
            self.deps = PackageDepWindow.moredeps
        if not self.deps:
            return INSTALL_NOOP

	origSelection = todo.comps.getSelectionState()
        todo.selectDeps (self.deps)

        g = GridFormHelp(screen, _("Package Dependencies"), 
			 "pacakgedeps", 1, 8)
        g.add (TextboxReflowed (45, _("Some of the packages you have "
                                      "selected to install require "
                                      "packages you have not selected. If "
                                      "you just select Ok all of those "
                                      "required packages will be "
                                      "installed.")), 0, 0, (0, 0, 0, 1))
        g.add (Label ("%-20s %-20s" % (_("Package"), _("Requirement"))), 0, 1, anchorLeft = 1)
        text = ""
        for name, suggest in self.deps:
            text = text + "%-20s %-20s\n" % (name, suggest)
        
        if len (self.deps) > 4:
            scroll = 1
        else:
            scroll = 0
            
        g.add (Textbox (45, 4, text, scroll = scroll), 0, 2, anchorLeft = 1)

        la = Label(self.size(todo.comps))
        g.add (la, 0, 3, anchorRight = 1)

        instt = _("Install packages to satisfy dependencies")
        causet = _("Do not install packages that have dependencies")
        ignt = _("Ignore package dependencies")
        maxlen = max ((len (instt), len (causet), len (ignt)))

        def pad (pad, text):
            return "%-*s" % (pad, text)
        
        self.inst = SingleRadioButton (pad (maxlen, instt), None, 1)
	self.inst.setCallback(self.radiocb, (la, todo, self.inst))
        g.add (self.inst, 0, 4, (0, 1, 0, 0), anchorLeft = 1)

        self.cause = SingleRadioButton (pad (maxlen, causet), self.inst, 0)
	self.cause.setCallback(self.radiocb, (la, todo, self.cause))
        g.add (self.cause, 0, 5, anchorLeft = 1)
        
        self.ignore = SingleRadioButton (pad (maxlen, ignt), self.cause, 0)
        g.add (self.ignore, 0, 6, (0, 0, 0, 1), anchorLeft = 1)
	self.ignore.setCallback(self.radiocb, (la, todo, self.ignore))
        
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))
        g.add (bb, 0, 7, growx = 1)

        result = g.runOnce ()

        rc = bb.buttonPressed (result)
        if rc == string.lower (_("Back")):
            todo.comps.setSelectionState(origSelection)
            return INSTALL_BACK

        if self.ignore.selected():
            return INSTALL_OK
        
        moredeps = todo.verifyDeps ()
        if moredeps and todo.canResolveDeps (moredeps):
            PackageDepWindow.moredeps = moredeps
            return self(screen, todo)
        return INSTALL_OK

