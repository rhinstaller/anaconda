#
# upgrade_bootloader_gui.py: gui bootloader dialog for upgrades
#
# Copyright (C) 2002, 2007  Red Hat, Inc.  All rights reserved.
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

# must replace with explcit form so update disks will work
from iw_gui import *

import gtk
from pyanaconda.storage.devices import devicePathToName

from pyanaconda.constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class UpgradeBootloaderWindow (InstallWindow):
    windowTitle = N_("Upgrade Boot Loader Configuration")

    def getPrev(self):
        pass

    def getNext(self):
        if self.nobl_radio.get_active():
            self.dispatch.skip_steps("bootloader")
            self.dispatch.skip_steps("instbootloader")
            self.anaconda.bootloader.skip_bootloader = True
        else:
            self.dispatch.request_steps_gently("bootloader")
            self.anaconda.bootloader.skip_bootloader = False

    def getScreen(self, anaconda):
        self.dispatch = anaconda.dispatch
        self.bl = anaconda.bootloader
        self.anaconda = anaconda

        self.newbl_radio = gtk.RadioButton(None,
                                          _("_Create new boot loader "
                                            "configuration"))
        self.newbl_label = gtk.Label(_("This option creates a "
                                      "new boot loader configuration.  If "
                                      "you wish to switch boot loaders, you "
                                      "should choose this."))

        self.newbl_radio.set_active(False)
        self.nobl_radio = gtk.RadioButton(self.newbl_radio,
                                         _("_Skip boot loader updating"))
        self.nobl_label = gtk.Label(_("This option makes no changes to boot "
                                     "loader configuration.  If you are "
                                     "using a third party boot loader, you "
                                     "should choose this."))
        self.nobl_radio.set_active(False)

        for label in [self.nobl_label, self.newbl_label]:
            label.set_alignment(0.8, 0)
            label.set_size_request(275, -1)
            label.set_line_wrap(True)

        default = self.newbl_radio

        if self.dispatch.step_enabled("bootloader"):
            self.newbl_radio.set_active(True)
        elif self.dispatch.step_disabled("instbootloader"):
            self.nobl_radio.set_active(True)
        else:
            default.set_active(True)

        box = gtk.VBox(False, 5)

        label = gtk.Label(_("What would you like to do?"))
        label.set_line_wrap(True)
        label.set_alignment(0.5, 0.0)
        label.set_size_request(300, -1)

        box.pack_start(label, False, padding = 10)

        box.pack_start(self.nobl_radio, False)
        box.pack_start(self.nobl_label, False)
        box.pack_start(self.newbl_radio, False)
        box.pack_start(self.newbl_label, False)

        a = gtk.Alignment(0.2, 0.1)
        a.add(box)

        return a
