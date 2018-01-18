# Event loop object abstraction above GLib loop.
#
# Copyright (C) 2018 Red Hat, Inc.
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
#  Author(s):  Jiri Konecny <jkonecny@redhat.com>
#

from pyanaconda.core.glib import create_main_loop


class EventLoop(object):
    """Abstraction for GLib.MainLoop object.

    This abstraction has everything important and can be easily extended.
    """

    def __init__(self):
        self._loop = create_main_loop()

    @property
    def loop(self):
        """Get GLib.MainLoop object.

        :returns: GLib.MainLoop object.
        """
        return self._loop

    @property
    def is_running(self):
        """Is the main loop running?

        :returns: bool
        """
        return self._loop.is_running()

    def run(self):
        """Start the GLib main loop."""
        self._loop.run()

    def quit(self):
        """Quit the GLib main loop."""
        self._loop.quit()
