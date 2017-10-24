# base.py
# Anaconda DBUS module base.
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
from pyanaconda.dbus import get_bus
from pyanaconda.dbus.interface import dbus_interface

from pyanaconda import anaconda_logging
log = anaconda_logging.get_dbus_module_logger(__name__)

@dbus_interface(dbus_constants.DBUS_MODULE_NAMESPACE)
class BaseModule(object):
    """A common base for Anaconda DBUS modules.

    This class also basically defines the common DBUS API
    of Anaconda DBUS modules.
    """

    def __init__(self):
        self._loop = GLib.MainLoop()
        self._bus = get_bus()
        self._dbus_name = None

    def run(self):
        # schedule publishing once loop is running
        GLib.idle_add(self.publish_module)
        # start mainloop
        log.debug("starting module mainloop: %s", self._dbus_name)
        self._loop.run()

    def publish_module(self):
        """Publish the module on DBUS and start its main loop."""
        self._bus.publish(self._dbus_name, self)
        log.debug("module %s has been published", self._dbus_name)

    def Quit(self):
        """Shut the module down."""
        log.debug("module quiting: %s", self._dbus_name)
        GLib.timeout_add_seconds(1, self._loop.quit)
