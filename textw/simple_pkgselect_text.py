#
# simple_pkgselect - Simple package selection UI
#
# Jeremy Katz <katzj@redhat.com>
# Copyright 2005   Red Hat, Inc.
#
# Only shows groups and allows selecting them.  None of the real
# "interesting" pieces of package selection are present
# Mostly here as a placeholder until we write the real code
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
from constants_text import *
from rhpl.translate import _, N_, getDefaultLangs

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
    def __call__(self, screen, backend, intf):
        g = GridFormHelp(screen, "Package Group Selection",
                         "packagetree", 1, 5)

        t = TextboxReflowed(50, "Please select the package groups you "
                                "would like to have installed.\n\n"
                                "Note that this is a temporary interface "
                                "as we work on hooking things up, so please "
                                "don't file bugs related directly to it.")
        g.add(t, 0, 0, (0, 0, 0, 1), anchorLeft = 1)

        # FIXME: this is very yum backend specific...
        groups = filter(lambda x: x.user_visible,
                        backend.ayum.comps.groups)
        groups.sort(_ui_comps_sort)
        ct = CheckboxTree(height = 6, scroll = (len(groups) > 6))
        for grp in groups:
            ct.append(_xmltrans(grp.name, grp.translated_name),
                      grp, grp.selected)
        g.add(ct, 0, 2, (0, 0, 0, 1))

        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        g.add(bb, 0, 3, growx = 1)

        while 1:
            result = g.run()
            rc = bb.buttonPressed(result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK
            break

        screen.popWindow()
        sel = ct.getSelection()
        for g in groups:
            if g in sel and not g.selected:
                backend.selectGroup(g.groupid)
            elif g not in sel and g.selected:
                backend.deselectGroup(g.groupid)

        return INSTALL_OK
