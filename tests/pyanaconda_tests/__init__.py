#
# Copyright (C) 2017  Red Hat, Inc.
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


class run_in_glib(object):
    """Run the test methods in GLib.

    :param timeout: Timeout in seconds when the loop will be killed.
    """

    def __init__(self, timeout):
        self._timeout = timeout
        self._result = None

    def __call__(self, func):

        def kill_loop(loop):
            loop.quit()
            return False

        def run_in_loop(*args, **kwargs):
            self._result = func(*args, **kwargs)

        def create_loop(*args, **kwargs):
            loop = GLib.MainLoop()

            GLib.idle_add(run_in_loop, *args, **kwargs)
            GLib.timeout_add_seconds(self._timeout, kill_loop, loop)

            loop.run()

            return self._result

        return create_loop
