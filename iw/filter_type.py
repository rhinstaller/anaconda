#
# Copyright (C) 2009  Red Hat, Inc.  All rights reserved.
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
# Author(s): Chris Lumens <clumens@redhat.com>
#

import gtk
import gobject
import math

from constants import *
import gui
from partition_ui_helpers_gui import *
from pixmapRadioButtonGroup_gui import pixmapRadioButtonGroup

from iw_gui import *
from flags import flags
from storage.deviceaction import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class FilterTypeWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        ics.setTitle("Filter Type")
        ics.setNextEnabled(True)

    def getNext(self):
        if self.buttonGroup.getCurrent() == "simple":
            self.anaconda.simpleFilter = True
        else:
            self.anaconda.simpleFilter = False

        return None

    def getScreen(self, anaconda):
        self.anaconda = anaconda
        self.intf = anaconda.intf

        vbox = gtk.VBox()
        label = gtk.Label(_("What type of devices will your installation "
                            "involve?"))
        label.set_alignment(0.0, 0.0)
        vbox.pack_start(label, expand=False, fill=False)

        self.buttonGroup = pixmapRadioButtonGroup()
        self.buttonGroup.addEntry("simple", _("Basic Storage Devices"),
                                  descr=_("Installs or upgrades to typical types "
                                          "of storage devices.  If you're not sure "
                                          "which option is right for you, this is "
                                          "probably it."))
        self.buttonGroup.addEntry("complex", _("Specialized Storage Devices"),
                                  descr=_("Installs or upgrades to devices such as "
                                          "Storage Area Networks (SANs) or mainframe "
                                          "attached disks (DASD), usually in an "
                                          "enterprise environment"))

        widget = self.buttonGroup.render()
        vbox.pack_start(widget, expand=True, fill=True)

        if self.anaconda.simpleFilter == True:
            self.buttonGroup.setCurrent("simple")
        else:
            self.buttonGroup.setCurrent("complex")

        return vbox
