#
# grpselect_text - Text mode group/package selection UI
#
# Jeremy Katz <katzj@redhat.com>
# Copyright 2005-2006   Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import yum.Errors
from snack import *
from constants_text import *
from rhpl.translate import _, N_, getDefaultLangs

import logging
log = logging.getLogger("anaconda")

# kind of lame caching of translations so we don't always have
# to do all the looping
strs = {}
def _xmltrans(base, thedict):
    if strs.has_key(base):
        return strs[base]
    
    langs = getDefaultLangs()
    for l in langs:
        if thedict.has_key(l):
            strs[base] = thedict[l]
            return strs[base]
    strs[base] = base
    return base

def _ui_comps_sort(one, two):
    if one.display_order > two.display_order:
        return 1
    elif one.display_order < two.display_order:
        return -1
    elif _xmltrans(one.name, one.translated_name) > \
         _xmltrans(two.name, two.translated_name):
        return 1
    elif _xmltrans(one.name, one.translated_name) < \
         _xmltrans(two.name, two.translated_name):
        return -1
    return 0

class GroupSelectionWindow:
    def __deselectPackage(self, grp, pkg):
        grpid = grp.groupid
        try:
            pkgs = self.ayum.pkgSack.returnNewestByName(pkg)
        except yum.Errors.PackageSackError:
            log.debug("no such package %s from group %s" %
                      (pkg, grpid))
        if pkgs:
            pkgs = self.ayum.bestPackagesFromList(pkgs)
        for po in pkgs:
            txmbrs = self.ayum.tsInfo.getMembers(pkgtup = po.pkgtup)
            for txmbr in txmbrs:
                try:
                    txmbr.groups.remove(grpid)
                except ValueError:
                    log.debug("package %s was not marked in group %s" %(po, grpid))
                if len(txmbr.groups) == 0:
                    self.ayum.tsInfo.remove(po.pkgtup)

    def __selectPackage(self, grp, pkg):
        grpid = grp.groupid
        try:
            txmbrs = self.ayum.install(name = pkg)
        except yum.Errors.InstallError, e:
            log.debug("No package named %s available to be installed: %s"
                      %(pkg, e))
        else:
            map(lambda x: x.groups.append(grpid), txmbrs)
    
    def __call__(self, screen, anaconda):
        self.ayum = anaconda.backend.ayum
        
        g = GridFormHelp(screen, "Package Group Selection",
                         "packagetree", 1, 5)

        t = TextboxReflowed(50, _("Please select the package groups you "
                                  "would like to have installed."))
        g.add(t, 0, 0, (0, 0, 0, 1), anchorLeft = 1)

        # FIXME: this is very yum backend specific...
        groups = filter(lambda x: x.user_visible,
                        anaconda.backend.ayum.comps.groups)
        groups.sort(_ui_comps_sort)
        ct = CheckboxTree(height = 6, scroll = (len(groups) > 6))
        for grp in groups:
            ct.append(_xmltrans(grp.name, grp.translated_name),
                      grp, grp.selected)
        g.add(ct, 0, 2, (0, 0, 0, 1))

        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        g.add(bb, 0, 3, growx = 1)

	g.addHotKey("F2")
	screen.pushHelpLine (_("<Space>,<+>,<-> selection   |   <F2> Group Details   |   <F12> next screen"))

        while 1:
            result = g.run()

            if result != "F2":
                break

	    grp = ct.getCurrent()
            pkgs = grp.default_packages.keys() + grp.optional_packages.keys()
            if len(pkgs) == 0:
                ButtonChoiceWindow(screen, _("Error"),
                                   _("No optional packages to select"))
                continue

	    # if current group is not selected then select it first
	    newSelection = 0
	    lst = ct.getSelection()
	    if grp not in lst:
		newSelection = 1
                self.ayum.selectGroup(grp.groupid)
		ct.setEntryValue(grp, True)

	    # do group details
	    gct = CheckboxTree(height = 8, scroll = 1)

            orig = {}
            pkgs.sort()
            for pkg in pkgs:
                orig[pkg] = self.ayum.isPackageInstalled(pkg)
                gct.append("%s" %(pkg,), pkg, orig[pkg])

	    bb2 = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON))

	    g2 = GridFormHelp (screen, _("Package Group Details"),  "", 1, 4)

	    g2.add (gct, 0, 1, (0, 0, 0, 1))
	    g2.add (bb2, 0, 3, growx = 1)

	    rc2 = g2.runOnce()
	    if bb2.buttonPressed(rc2) == TEXT_CANCEL_CHECK:
		# unselect group if necessary
		if newSelection:
		    ct.setEntryValue(grp, False)
                    self.ayum.deselectGroup(grp.groupid)                    

	    else:
		# reflect new packages selected
		selected = gct.getSelection()
                for (opkg, osel) in orig.items():
                    if opkg in selected and not osel:
                        self.__selectPackage(grp, opkg)
                    elif opkg not in selected and osel:
                        self.__deselectPackage(grp, opkg)

        rc = bb.buttonPressed(result)
        screen.popWindow()
        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK

        sel = ct.getSelection()
        for g in groups:
            if g in sel and not g.selected:
                anaconda.backend.selectGroup(g.groupid)
            elif g not in sel and g.selected:
                anaconda.backend.deselectGroup(g.groupid)

        return INSTALL_OK
