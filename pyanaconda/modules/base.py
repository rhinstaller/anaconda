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

from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.constants import DBUS_MODULE_NAMESPACE

from pyanaconda import anaconda_logging
log = anaconda_logging.get_dbus_module_logger(__name__)


@dbus_interface(DBUS_MODULE_NAMESPACE)
class BaseModule(object):
    """A common base for Anaconda DBUS modules.

    This class also basically defines the common DBUS API
    of Anaconda DBUS modules.
    """

    def __init__(self):
        self._loop = GLib.MainLoop()

    def run(self):
        """Run the module's loop."""
        log.debug("Schedule publishing.")
        GLib.idle_add(self.publish)
        log.debug("Start the loop.")
        self._loop.run()

    def publish(self):
        """Publish DBus objects and register a DBus service.

        Nothing is published by default.
        """
        pass

    def Quit(self):
        """Shut the module down."""
        log.debug("Schedule quitting.")
        GLib.timeout_add_seconds(1, self._loop.quit)
