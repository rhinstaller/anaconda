import rpm
import gettext
from snack import *
from textw.constants import *
from text import _

class PackageGroupWindow:
    def __call__(self, screen, todo, individual):
        # be sure that the headers and comps files have been read.
	todo.getHeaderList()
        todo.getCompsList()

        ct = CheckboxTree(height = 10, scroll = 1)
        for comp in todo.comps:
            if not comp.hidden:
                ct.append(comp.name, comp, comp.selected)

        cb = Checkbox (_("Select individual packages"), individual.get ())

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        g = GridForm (screen, _("Package Group Selection"), 1, 3)
        g.add (ct, 0, 0, (0, 0, 0, 1))
        g.add (cb, 0, 1, (0, 0, 0, 1))
        g.add (bb, 0, 2, growx = 1)

        result = g.runOnce()

        individual.set (cb.selected())
        # turn off all the comps
        for comp in todo.comps:
            if not comp.hidden: comp.unselect(0)

        # turn on all the comps we selected
        for comp in ct.getSelection():
            comp.select (1)

        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

class IndividualPackageWindow:
    def __call__(self, screen, todo, individual):
        if not individual.get():
            return
	todo.getHeaderList()
        todo.getCompsList()

        ct = CheckboxTree(height = 10, scroll = 1)
        groups = {}

        # go through all the headers and grok out the group names, placing
        # packages in lists in the groups dictionary.
        
        for key in todo.hdList.packages.keys():
            header = todo.hdList.packages[key]
            # don't show this package if it is in the base group
            if not todo.comps["Base"].items.has_key (header):
                if not groups.has_key (header[rpm.RPMTAG_GROUP]):
                    groups[header[rpm.RPMTAG_GROUP]] = []
                groups[header[rpm.RPMTAG_GROUP]].append (header)

        # now insert the groups into the list, then each group's packages
        # after sorting the list
        def cmpHdrName(first, second):
            if first[rpm.RPMTAG_NAME] < second[rpm.RPMTAG_NAME]:
                return -1
            elif first[rpm.RPMTAG_NAME] == second[rpm.RPMTAG_NAME]:
                return 0
            return 1
        
        keys = groups.keys ()
        keys.sort ()
        index = 0
        for key in keys:
            groups[key].sort (cmpHdrName)
            ct.append (key)
            for header in groups[key]:
                ct.addItem (header[rpm.RPMTAG_NAME], (index, snackArgs["append"]),
                            header, header.selected)
            index = index + 1
                
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        g = GridForm (screen, _("Package Group Selection"), 1, 2)
        g.add (ct, 0, 0, (0, 0, 0, 1))
        g.add (bb, 0, 1, growx = 1)

        result = g.runOnce ()
 
        # turn off all the packages
        for key in todo.hdList.packages.keys ():
            todo.hdList.packages[key].selected = 0

        # turn on all the packages we selected
        for package in ct.getSelection ():
            package.selected = 1

        rc = bb.buttonPressed (result)
        
        if rc == "back":
            return INSTALL_BACK

        return INSTALL_OK

class PackageDepWindow:
    def __call__(self, screen, todo):
        deps = todo.verifyDeps ()
        if not deps:
            return INSTALL_NOOP

        g = GridForm(screen, _("Package Dependencies"), 1, 5)
        g.add (TextboxReflowed (45, _("Some of the packages you have "
                                      "selected to install require "
                                      "packages you have not selected. If "
                                      "you just select Ok all of those "
                                      "required packages will be "
                                      "installed.")), 0, 0, (0, 0, 0, 1))
        g.add (Label ("%-20s %-20s" % (_("Package"), _("Requirement"))), 0, 1, anchorLeft = 1)
        text = ""
        for name, suggest in deps:
            text = text + "%-20s %-20s\n" % (name, suggest)
        
        if len (deps) > 5:
            scroll = 1
        else:
            scroll = 0
            
        g.add (Textbox (45, 5, text, scroll = scroll), 0, 2, anchorLeft = 1)
        
        cb = Checkbox (_("Install packages to satisfy dependencies"), 1)
        g.add (cb, 0, 3, (0, 1, 0, 1), growx = 1)
        
        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))
        g.add (bb, 0, 4, growx = 1)

        result = g.runOnce ()

        if cb.selected ():
            todo.selectDeps (deps)
        
        rc = bb.buttonPressed (result)
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK

