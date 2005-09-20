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
from rhpl.translate import _, N_

import copy

class GroupSelectionWindow:
    def __call__(self, screen, backend, intf):
        self.instgrps = copy.copy(backend.anaconda_grouplist)

        g = GridFormHelp(screen, "Package Group Selection",
                     "packagetree", 1, 5)

        t = TextboxReflowed(50, "Please select the package groups you "
                                "would like to have installed.\n\n"
                                "Note that this is a temporary interface "
                                "as we work on hooking things up, so please "
                                "don't file bugs related directly to it.")
        g.add(t, 0, 0, (0, 0, 0, 1), anchorLeft = 1)

        # FIXME: this is very yum backend specific...
        groups = backend.ayum.groupInfo.visible_groups
        groups.sort()
        ct = CheckboxTree(height = 6, scroll = (len(groups) > 6))
        for grp in groups:
            ct.append(grp, grp, grp in backend.anaconda_grouplist)
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
            if g in sel and g not in self.instgrps:
                backend.selectGroup(g)
            elif g not in sel and g in self.instgrps:
                backend.deselectGroup(g)

        return INSTALL_OK
