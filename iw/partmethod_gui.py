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
from autopart import PARTMETHOD_TYPE_DESCR_TEXT

class PartitionMethodWindow(InstallWindow):
    def __init__(self, ics):
	InstallWindow.__init__(self, ics)
        ics.setTitle (_("Disk Partitioning Setup"))

    def getNext(self):
        
        if self.useFdisk.get_active():
            self.partitions.useAutopartitioning = 0
            self.partitions.useFdisk = 1
        elif self.useAuto.get_active():
            self.partitions.useAutopartitioning = 1
            self.partitions.useFdisk = 0
        else:
            self.partitions.useAutopartitioning = 0
            self.partitions.useFdisk = 0
            
	return None

    def getScreen (self, partitions, instclass):

        # XXX messy - set help based on installclass
        helpfile = None
        if instclass.name == _("Workstation"):
            helpfile = "wkst"
        elif instclass.name == _("Server"):
            helpfile = "svr"
        elif instclass.name == _("Custom"):
            helpfile = "cust"
        elif instclass.name == _("Laptop"):
            helpfile = "laptop"

        if helpfile:
            self.ics.readHTML(helpfile)

        self.partitions = partitions
        
        box = GtkVBox (FALSE)
        box.set_border_width (5)

        label=GtkLabel(PARTMETHOD_TYPE_DESCR_TEXT)
        label.set_line_wrap(1)
        label.set_alignment(0.0, 0.0)
        label.set_usize(400, -1)

        box.pack_start(label, FALSE, FALSE)

        radioBox = GtkVBox (FALSE)

        self.useAuto = GtkRadioButton(
            None, _("Have the installer autopartition for you"))
	radioBox.pack_start(self.useAuto, FALSE, FALSE)
        self.useDS = GtkRadioButton(
            self.useAuto, _("Manually partition with Disk Druid"))
	radioBox.pack_start(self.useDS, FALSE, FALSE)
        self.useFdisk = GtkRadioButton(
            self.useAuto, _("Manually partition with fdisk [experts only]"))
	radioBox.pack_start(self.useFdisk, FALSE, FALSE)

        if partitions.useAutopartitioning:
            self.useAuto.set_active(1)
        elif partitions.useFdisk:
            self.useFdisk.set_active(1)
        else:
            self.useDS.set_active(1)
            
	align = GtkAlignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, FALSE, FALSE, 10)
	box.set_border_width (5)

        self.ics.setNextEnabled (TRUE)

        align = GtkAlignment()
        align.add(box)
        align.set(0.5, 0.5, 0.0, 0.0)

	return align
