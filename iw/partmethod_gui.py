#
# partmethod_gui.py: allows the user to choose how to partition their disks
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from iw_gui import *
from gtk import *
from translate import _

class PartitionMethodWindow(InstallWindow):
    def __init__(self, ics):
	InstallWindow.__init__(self, ics)
        ics.setTitle (_("Automatic Partitioning"))

    def getNext(self):
        if self.useFdisk.get_active():
	    self.dispatch.skipStep("fdisk", skip = 0)
	else:
	    self.dispatch.skipStep("fdisk")
	return None

    def getScreen (self, dispatch):
        self.dispatch = dispatch
        
        box = GtkVBox (FALSE)
        box.set_border_width (5)

        radioBox = GtkVBox (FALSE)

        self.useFdisk = GtkRadioButton(
            None, _("Manually partition with fdisk [experts only]"))
	radioBox.pack_start(self.useFdisk, FALSE)
        self.useFdisk.set_active (not dispatch.stepInSkipList("fdisk"))
            
	align = GtkAlignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, TRUE, TRUE)
	box.set_border_width (5)

        self.ics.setNextEnabled (TRUE)

	return box
