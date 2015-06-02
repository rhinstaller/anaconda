#
# timer.py: timer decorator for unittest functions
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: David Shea <dshea@redhat.com>

from contextlib import contextmanager
import signal

@contextmanager
def timer(seconds):
    """Return a timer context manager.

       If the code within the context does not finish within the given number
       of seconds, it will raise an AssertionError.
    """
    def _handle_sigalrm(signum, frame):
        raise AssertionError("Test failed to complete within %d seconds" % seconds)

    old_handler = signal.signal(signal.SIGALRM, _handle_sigalrm)
    try:
        signal.alarm(seconds)
        yield
    finally:
        # Put everything back
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
