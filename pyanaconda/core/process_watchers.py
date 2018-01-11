# Classes to watch for an external application.
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

from pyanaconda.core.glib import child_watch_add, source_remove

__all__ = ["PidWatcher"]


class PidWatcher(object):
    """Watch for process and call callback when the process ends."""

    def __init__(self):
        self._id = 0

    def watch_process(self, pid, callback, *args, **kwargs):
        """Watch for process with given pid to exit then call `callback`.

        :param pid: Process ID.
        :type pid: int

        :param callback: Callback to call when process ends.
        :type callback: A function.

        :param args: Arguments passed to the callback.
        :param kwargs: Keyword arguments passed to the callback.
        """
        self._id = child_watch_add(pid, callback, *args, **kwargs)

    def cancel(self):
        """Cancel watching."""
        source_remove(self._id)
        self._id = 0
