#
# package_gui.py: package group selection screen
#
# Copyright (C) 2005  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Jeremy Katz <katzj@redhat.com>
#

# FIXME: group selection isn't currently backend independent
from GroupSelector import GroupSelector

import gui
from iw_gui import *

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class GroupSelectionWindow (InstallWindow):
    def getScreen(self, anaconda):
        self.backend = anaconda.backend
        self.intf = anaconda.intf
        self.grpsel = GroupSelector(self.backend.ayum, gui.findGladeFile,
                                    gui.addFrame)
        self.grpsel.doRefresh()
        return self.grpsel.vbox
