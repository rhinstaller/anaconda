

import gi

from queue import Queue
from pyanaconda.threading import threadMgr

gi.require_version("GLib", "2.0")

from gi.repository import GLib


def async_action_wait(func):
    """Decorator method which ensures every call of the decorated function to be
       executed in the context of Gtk main loop even if called from a non-main
       thread and returns the ret value after the decorated method finishes.
    """

    queue_instance = Queue()

    def _idle_method(queue_instance, args, kwargs):
        """This method contains the code for the main loop to execute.
        """
        ret = func(*args)
        queue_instance.put(ret)
        return False

    def _call_method(*args, **kwargs):
        """The new body for the decorated method. If needed, it uses closure
           bound queue_instance variable which is valid until the reference to this
           method is destroyed."""
        if threadMgr.in_main_thread():
            # nothing special has to be done in the main thread
            return func(*args, **kwargs)

        GLib.idle_add(_idle_method, queue_instance, args, kwargs)
        return queue_instance.get()

    return _call_method


def async_action_nowait(func):
    """Decorator method which ensures every call of the decorated function to be
       executed in the context of Gtk main loop even if called from a non-main
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
        if threadMgr.in_main_thread():
            # nothing special has to be done in the main thread
            func(*args, **kwargs)
            return

        GLib.idle_add(_idle_method, args, kwargs)

    return _call_method