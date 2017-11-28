# boss.py
# Anaconda main DBUS module & module manager.
#
# Copyright (C) 2017 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

from pyanaconda.dbus import dbus_constants
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.modules.base import BaseModule

from pyanaconda.modules.boss.module_manager import ModuleManager  # pylint: disable=relative-beyond-top-level

from pyanaconda import anaconda_logging
log = anaconda_logging.get_dbus_module_logger(__name__)

@dbus_interface(dbus_constants.DBUS_BOSS_NAME)
class Boss(BaseModule):

    def __init__(self, module_manager=None):
        super().__init__()
        self._dbus_name = dbus_constants.DBUS_BOSS_NAME
        if module_manager is None:
            self._module_manager = ModuleManager()

    def run(self):
        log.info("looking for addons")
        self._module_manager.find_addons()
        # schedule publishing
        GLib.idle_add(self.publish_module)
        # then schedule module startup
        GLib.idle_add(self._module_manager.start_modules)
        # start the mainloop
        log.info("starting mainloop")
        self._loop.run()

    def Quit(self):
        """Stop all modules and then stops Boss."""
        self._module_manager.stop_modules()
        super().Quit()
