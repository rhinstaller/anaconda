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

import gtk
from gui import WrappingLabel
from iw_gui import *
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

        self.ics.readHTML("howpartition")

        self.partitions = partitions
        
        box = gtk.VBox (gtk.FALSE)
        box.set_border_width (5)

        label=WrappingLabel(_(PARTMETHOD_TYPE_DESCR_TEXT))
        label.set_alignment(0.0, 0.0)

        box.pack_start(label, gtk.TRUE, gtk.TRUE)

        radioBox = gtk.VBox (gtk.FALSE)

        self.useAuto = gtk.RadioButton(
            None, _("Have the installer automatically partition for you"))
	radioBox.pack_start(self.useAuto, gtk.FALSE, gtk.FALSE)
        self.useDS = gtk.RadioButton(
            self.useAuto, _("Manually partition with Disk Druid"))
	radioBox.pack_start(self.useDS, gtk.FALSE, gtk.FALSE)
        self.useFdisk = gtk.RadioButton(
            self.useAuto, _("Manually partition with fdisk [experts only]"))
	radioBox.pack_start(self.useFdisk, gtk.FALSE, gtk.FALSE)

        if partitions.useAutopartitioning:
            self.useAuto.set_active(1)
        elif partitions.useFdisk:
            self.useFdisk.set_active(1)
        else:
            self.useDS.set_active(1)
            
	align = gtk.Alignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, gtk.FALSE, gtk.FALSE, 10)

	box.set_border_width (5)

        self.ics.setNextEnabled (gtk.TRUE)

        align = gtk.Alignment()
        align.add(box)
        align.set(0.5, 0.5, 0.0, 0.0)

	return align
