#
# iw_gui.py: install window base class
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

from rhpl.translate import _

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
