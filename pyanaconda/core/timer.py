# Timer class for scheduling methods after some time.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
#  Author(s):  Jiri Konecny <jkonecny@redhat.com>
#

from pyanaconda.core.glib import source_remove, timeout_add, timeout_add_seconds


class Timer:
    """Object to schedule functions and methods to the GLib event loop.

    Everything scheduled by Timer is ran on the main thread!
    """

    def __init__(self):
        self._id = 0

    def timeout_sec(self, seconds, callback, *args, **kwargs):
        """Schedule method to be run after given amount of seconds.

        .. NOTE::
            The callback will be repeatedly called until the callback will return False or
            `cancel()` is called.

        :param seconds: Number of seconds after which the callback will be called.
        :type seconds: int

        :param callback: Callback which will be called.
        :type callback: Function.

        :param args: Arguments passed to the callback.
        :param kwargs: Keyword arguments passed to the callback.
        """
        self._id = timeout_add_seconds(seconds, callback, *args, **kwargs)

    def timeout_msec(self, miliseconds, callback, *args, **kwargs):
        """Schedule method to be run after given amount of miliseconds.

        .. NOTE::
            The callback will be repeatedly called until the callback will return False or
            `cancel()` is called.

        :param miliseconds: Number of miliseconds after which the callback will be called.
        :type miliseconds: int

        :param callback: Callback which will be called.
        :type callback: Function.

        :param args: Arguments passed to the callback.
        :param kwargs: Keyword arguments passed to the callback.
        """
        self._id = timeout_add(miliseconds, callback, *args, **kwargs)

    def cancel(self):
        """Cancel scheduled callback.

        This way the schedule_sec and schedule_msec repetition can be canceled.
        """
        source_remove(self._id)
        self._id = 0
