#
# zipl_text.py: text mode z/IPL setup dialog
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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

from snack import *
from constants_text import *

from pyanaconda.constants import *
from pyanaconda.storage.dasd import getDasdPorts

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class ZiplWindow:
    def __call__(self, screen, anaconda):
        self.bl = anaconda.bootloader

        t = TextboxReflowed(53,
                         _("The z/IPL Boot Loader will be installed "
                           "on your system after installation is complete. "
                           "You can now enter any additional kernel parameters "
                           "required by your machine or setup."))

        kernelentry = Entry(48, scroll = 1, returnExit = 1)
        kernelparms = str(self.bl.boot_args)
        dasd_ports = "dasd=%s" % getDasdPorts()
        if dasd_ports and "dasd" not in self.bl.boot_args:
            kernelparms += " dasd=%s" % getDasdPorts()
        kernelentry.set(kernelparms)

        buttons = ButtonBar(screen, [TEXT_OK_BUTTON,
                            TEXT_BACK_BUTTON ] )

        grid = GridFormHelp(screen, _("z/IPL Configuration"), 
                            "zipl-s390", 1, 5)
        grid.add(t, 0, 0)
        sg = Grid(2, 1)
        sg.setField(Label(_("Kernel Parameters") + ": "), 0, 0, anchorLeft=1)
        sg.setField(kernelentry, 1, 0, anchorLeft=1)
        grid.add(sg, 0, 1, padding = (0, 1, 0, 1))
        grid.add(buttons, 0, 2, growx = 1)

        result = grid.runOnce ()
        button = buttons.buttonPressed(result)
        
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        self.bl.boot_args.update(kernelentry.value().split())
        return INSTALL_OK
