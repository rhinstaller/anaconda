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
            self.id.useAutopartitioning = 0
            self.id.useFdisk = 1
        elif self.useAuto.get_active():
            self.id.useAutopartitioning = 1
            self.id.useFdisk = 0
        else:
            self.id.useAutopartitioning = 0
            self.id.useFdisk = 0
            
	return None

    def getScreen (self, id):

        # XXX Change to not use id in (use more specific components of id)
        self.id = id
        
        box = GtkVBox (FALSE)
        box.set_border_width (5)

        label = GtkLabel(
             _("Autopartitioning sets up your partitioning in a reasonable "
               "way depending on your installation type and then gives you a "
               "chance to customize this setup.\n"
               "\n"
               "Disk Druid is a tool designed for partitioning and setting "
               "up mount points.  It is designed to be easier to use than "
               "Linux's traditional disk partitioning software, fdisk, as "
               "well as more powerful.  However, there are some cases where "
               "fdisk may be preferred.\n"
               "\n"
               "Which tool would you like to use?"))

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

        if id.useAutopartitioning:
            self.useAuto.set_active(1)
        elif id.useFdisk:
            self.useFdisk.set_active(1)
        else:
            self.useDS.set_active(1)
            
	align = GtkAlignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, FALSE, FALSE, 10)
	box.set_border_width (5)

        self.ics.setNextEnabled (TRUE)

	return box
