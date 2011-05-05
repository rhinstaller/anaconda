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
            self.dispatch.skipStep("bootloader")
            self.dispatch.skipStep("instbootloader")
        elif self.newbl_radio.get_active():
            self.dispatch.skipStep("bootloader", skip = 0)
            self.dispatch.skipStep("instbootloader", skip = 0)
            self.bl.update_only = False
        else:
            self.dispatch.skipStep("bootloader")
            self.dispatch.skipStep("instbootloader", skip = 0)
            self.bl.update_only = self.bl.can_update

            self.bl.stage1_device = self.bootDev

    def getScreen(self, anaconda):
        self.dispatch = anaconda.dispatch
        self.bl = anaconda.bootloader

        # TODO: implement bootloader detection
        self.type = None
        self.bootDev = None

        self.update_radio = gtk.RadioButton(None, _("_Update boot loader configuration"))
        updatestr = _("This will update your current boot loader.")

        if (not self.bl.can_update) or \
           (self.type is None or self.bootDev is None):
            current = _("The installer is unable to detect the boot loader "
                        "currently in use on your system.")
            self.update_label = gtk.Label("%s" % (updatestr,))
            self.update_radio.set_sensitive(False)
            self.update_label.set_sensitive(False)
            update = False
        else:
            current = _("The installer has detected the %(type)s boot loader "
                        "currently installed on %(bootDev)s.") \
                      % {'type': self.type, 'bootDev': self.bootDev}
            self.update_label = gtk.Label("%s  %s" % (updatestr,
                                         _("This is the recommended option.")))
            self.update_radio.set_active(False)
            update = True

        self.newbl_radio = gtk.RadioButton(self.update_radio,
                                          _("_Create new boot loader "
                                            "configuration"))
        self.newbl_label = gtk.Label(_("This option creates a "
                                      "new boot loader configuration.  If "
                                      "you wish to switch boot loaders, you "
                                      "should choose this."))

        self.newbl_radio.set_active(False)
        self.nobl_radio = gtk.RadioButton(self.update_radio,
                                         _("_Skip boot loader updating"))
        self.nobl_label = gtk.Label(_("This option makes no changes to boot "
                                     "loader configuration.  If you are "
                                     "using a third party boot loader, you "
                                     "should choose this."))
        self.nobl_radio.set_active(False)

        for label in [self.update_label, self.nobl_label, self.newbl_label]:
            label.set_alignment(0.8, 0)
            label.set_size_request(275, -1)
            label.set_line_wrap(True)

        str = _("What would you like to do?")
        # if they have one, the default is to update, otherwise the
        # default is to not touch anything
        if update:
            default = self.update_radio
        else:
            default = self.nobl_radio

        if not self.dispatch.stepInSkipList("bootloader"):
            self.newbl_radio.set_active(True)
        elif self.dispatch.stepInSkipList("instbootloader"):
            self.nobl_radio.set_active(True)
        else:
            default.set_active(True)

        box = gtk.VBox(False, 5)

        label = gtk.Label(current)
        label.set_line_wrap(True)
        label.set_alignment(0.5, 0.0)
        label.set_size_request(300, -1)
        label2 = gtk.Label(str)
        label2.set_line_wrap(True)
        label2.set_alignment(0.5, 0.0)
        label2.set_size_request(300, -1)

        box.pack_start(label, False)
        box.pack_start(label2, False, padding = 10)

        box.pack_start(self.update_radio, False)
        box.pack_start(self.update_label, False)
        box.pack_start(self.nobl_radio, False)
        box.pack_start(self.nobl_label, False)
        box.pack_start(self.newbl_radio, False)
        box.pack_start(self.newbl_label, False)

        a = gtk.Alignment(0.2, 0.1)
        a.add(box)

        return a
