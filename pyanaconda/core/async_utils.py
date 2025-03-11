# Utilities for asynchronous calls.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from queue import Queue

from pyanaconda.core.glib import idle_add
from pyanaconda.core.threads import thread_manager


def run_in_loop(callback, *args, **kwargs):
    """Run callback in the main thread."""
    idle_add(callback, *args, **kwargs)


def async_action_wait(func):
    """Decorator method which ensures every call of the decorated function to be
       executed in the context of GLib main loop even if called from a non-main
       thread and returns the ret value after the decorated method finishes.
    """

    queue_instance = Queue()

    def _idle_method(queue_instance, args, kwargs):
        """This method contains the code for the main loop to execute.
        """
        ret = func(*args, **kwargs)
        queue_instance.put(ret)
        return False

    def _call_method(*args, **kwargs):
        """The new body for the decorated method. If needed, it uses closure
           bound queue_instance variable which is valid until the reference to this
           method is destroyed."""
        if thread_manager.in_main_thread():
            # nothing special has to be done in the main thread
            return func(*args, **kwargs)

        run_in_loop(_idle_method, queue_instance, args, kwargs)
        return queue_instance.get()

    return _call_method


def async_action_nowait(func):
    """Decorator method which ensures every call of the decorated function to be
       executed in the context of GLib main loop even if called from a non-main
       thread. The new method does not wait for the callback to finish.
    """

    def _idle_method(args, kwargs):
        """This method contains the code for the main loop to execute.
        """
        func(*args, **kwargs)
        return False

    def _call_method(*args, **kwargs):
        """The new body for the decorated method.
        """
        if thread_manager.in_main_thread():
            # nothing special has to be done in the main thread
            func(*args, **kwargs)
            return

        run_in_loop(_idle_method, args, kwargs)

    return _call_method
