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


import gtk
import gobject
import gui
import copy
from iw_gui import *
from rhpl.translate import _, N_

import checklist


class GroupSelectionWindow (InstallWindow):
    def getNext(self):
        for row in self.cl.store:
            (on, grp) = (row[0], row[1])
            if on and grp not in self.instgrps:
                self.backend.selectGroup(grp)
            elif not on and grp in self.instgrps:
                self.backend.deselectGroup(grp)
    
    def getScreen(self, backend, intf):
        self.backend = backend
        self.intf = intf
        self.instgrps = copy.copy(backend.anaconda_grouplist)
        
        box = gtk.VBox(False)
        box.set_border_width(6)

        txt = gui.WrappingLabel("Please select the package groups you "
                                "would like to have installed.\n\n"
                                "Note that this is a temporary interface "
                                "as we work on hooking things up, so please "
                                "don't file bugs related directly to it.")
        box.pack_start(txt, False)
                                

        sw = gtk.ScrolledWindow()
        sw.set_border_width(6)
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        box.pack_start(sw)

        self.cl = checklist.CheckList(columns = 1)

        # FIXME: this is very yum backend specific...
        groups = backend.ayum.groupInfo.visible_groups
        groups.sort()
    
        for g in groups:
            self.cl.append_row([g], g in backend.anaconda_grouplist)

        sw.add(self.cl)

        return box

        
