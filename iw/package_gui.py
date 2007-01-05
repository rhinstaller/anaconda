#
# package_gui.py: package group selection screen
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

# FIXME: group selection isn't currently backend independent
from pirut.GroupSelector import GroupSelector

import gui
from iw_gui import *
from rhpl.translate import _, N_, textdomain
textdomain("pirut")

class GroupSelectionWindow (InstallWindow):
    def getScreen(self, anaconda):
        self.backend = anaconda.backend
        self.intf = anaconda.intf
        self.grpsel = GroupSelector(self.backend.ayum, gui.findGladeFile,
                                    gui.addFrame)
        self.grpsel.doRefresh()
        return self.grpsel.vbox
