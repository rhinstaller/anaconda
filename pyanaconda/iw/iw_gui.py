#
# iw_gui.py: install window base class
#
# Copyright (C) 2000, 2001, 2002  Red Hat, Inc.  All rights reserved.
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

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class InstallWindow:

    windowTitle = None

    def __init__ (self,ics):
        self.ics = ics

	if self.windowTitle:
	    ics.setTitle (_(self.windowTitle))

    def getNext (self):
	return None

    def renderCallback(self):
	return None

    def getPrev (self):
	return None

    def getScreen (self):
        pass

    def getICS (self):
        return self.ics

    def fixUp (self):
        pass

    def focus(self):
        pass
