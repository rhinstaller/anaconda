#
# Representation of a signal
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
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

__all__ = ["Signal"]


class Signal(object):
    """Default representation of a signal."""

    __slots__ = ["_callbacks", "__weakref__"]

    def __init__(self):
        """Create a new signal."""
        self._callbacks = []

    def connect(self, callback):
        """Connect to a signal.

        :param callback: a function to register
        """
        self._callbacks.append(callback)

    def __call__(self, *args, **kwargs):
        """Emit a signal with the given arguments."""
        self.emit(*args, **kwargs)

    def emit(self, *args, **kwargs):
        """Emit a signal with the given arguments."""
        for callback in self._callbacks:
            callback(*args, **kwargs)

    def disconnect(self, callback=None):
        """Disconnect from a signal.

        If no callback is specified, then all functions will
        be unregistered from the signal.

        If the specified callback isn't registered, do nothing.

        :param callback: a function to unregister or None
        """
        if callback is None:
            self._callbacks.clear()
            return

        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

