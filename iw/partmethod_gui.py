#
# partmethod_gui.py: allows the user to choose how to partition their disks
#
# Copyright (C) 2001, 2002  Red Hat, Inc.  All rights reserved.
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
# Author(s): Matt Wilson <msw@redhat.com>
#

import gtk
from gui import WrappingLabel
from iw_gui import *
from autopart import PARTMETHOD_TYPE_DESCR_TEXT

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class PartitionMethodWindow(InstallWindow):
    def __init__(self, ics):
	InstallWindow.__init__(self, ics)
        ics.setTitle (_("Disk Partitioning Setup"))

    def getNext(self):
        
        if self.useAuto.get_active():
            self.partitions.useAutopartitioning = 1
        else:
            self.partitions.useAutopartitioning = 0
            
	return None

    def getScreen (self, partitions, instclass):
        self.partitions = partitions
        
        box = gtk.VBox (False)
        box.set_border_width (5)

        label=WrappingLabel(_(PARTMETHOD_TYPE_DESCR_TEXT))
        label.set_alignment(0.0, 0.0)

        box.pack_start(label, True, True)

        radioBox = gtk.VBox (False)

        self.useAuto = gtk.RadioButton(
            None, _("_Automatically partition"))
	radioBox.pack_start(self.useAuto, False, False)
        self.useDS = gtk.RadioButton(
            self.useAuto, _("Manually partition with _Disk Druid"))
	radioBox.pack_start(self.useDS, False, False)

        if partitions.useAutopartitioning:
            self.useAuto.set_active(1)
        else:
            self.useDS.set_active(1)
            
	align = gtk.Alignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, False, False, 10)

	box.set_border_width (5)

        self.ics.setNextEnabled (True)

        align = gtk.Alignment()
        align.add(box)
        align.set(0.5, 0.5, 0.0, 0.0)

	return align
