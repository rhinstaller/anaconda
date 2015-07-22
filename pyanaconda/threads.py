#
# threads.py:  anaconda thread management
#
# Copyright (C) 2012
# Red Hat, Inc.  All rights reserved.
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
# Author(s):  Chris Lumens <clumens@redhat.com>
#
import logging
log = logging.getLogger("anaconda")

import threading

_WORKER_THREAD_PREFIX = "AnaWorkerThread"

class ThreadManager(object):
    """A singleton class for managing threads and processes.

       Notes:
       THE INSTANCE HAS TO BE CREATED IN THE MAIN THREAD!

       This manager makes one assumption that contradicts python's
       threading module documentation.  In this class, we assume that thread
       names are unique and meaningful.  This is an okay assumption for us
       to make given that anaconda is only ever going to have a handful of
       special purpose threads.
    """
    def __init__(self):
        self._objs = {}
        self._objs_lock = threading.RLock()
        self._errors = {}
        self._errors_lock = threading.RLock()
        self._main_thread = threading.current_thread()

    def __call__(self):
        return self

    def add(self, obj):
        """Given a Thread or Process object, add it to the list of known objects
           and start it.  It is assumed that obj.name is unique and descriptive.
        """

        # we need to lock the thread dictionary when adding a new thread,
        # so that callers can't get & join threads that are not yet started
        with self._objs_lock:
            if obj.name in self._objs:
                raise KeyError("Cannot add thread '%s', a thread with the same name already running" % obj.name)

            self._objs[obj.name] = obj
            obj.start()

        return obj.name

    def remove(self, name):
        """Removes a thread from the list of known objects.  This should only
           be called when a thread exits, or there will be no way to get a
           handle on it.
        """
        with self._objs_lock:
            self._objs.pop(name)

    def exists(self, name):
        """Determine if a thread or process exists with the given name."""

        # thread in the ThreadManager only officially exists once started
        with self._objs_lock:
            return name in self._objs

    def get(self, name):
        """Given an object name, see if it exists and return the object.
           Return None if no such object exists.  Additionally, this method
           will re-raise any uncaught exception in the thread.
        """

        # without the lock it would be possible to get & join
        # a thread that was not yet started
        with self._objs_lock:
            obj = self._objs.get(name)
            if obj:
                self.raise_if_error(name)

            return obj

    def wait(self, name):
        """Wait for the thread to exit and if the thread exited with an error
           re-raise it here.
        """

        ret_val = True

        # we don't need a lock here,
        # because get() acquires it itself
        try:
            self.get(name).join()
        except AttributeError:
            ret_val = False
        # - if there is a thread object for the given name,
        #   we join it
        # - if there is not a thread object for the given name,
        #   we get None, try to join it, suppress the AttributeError
        #   and return immediately

        self.raise_if_error(name)

        # return True if we waited for the thread, False otherwise
        return ret_val

    def wait_all(self):
        """Wait for all threads to exit and if there was an error re-raise it.
        """
        with self._objs_lock:
            names = list(self._objs.keys())

        for name in names:
            if self.get(name) == threading.current_thread():
                continue
            log.debug("Waiting for thread %s to exit", name)
            self.wait(name)

        if self.any_errors:
            with self._errors_lock:
                thread_names = ", ".join(thread_name for thread_name in self._errors.keys()
                                         if self._errors[thread_name])
            msg = "Unhandled errors from the following threads detected: %s" % thread_names
            raise RuntimeError(msg)

    def set_error(self, name, *exc_info):
        """Set the error data for a thread

           The exception data is expected to be the tuple from sys.exc_info()
        """
        with self._errors_lock:
            self._errors[name] = exc_info

    def get_error(self, name):
        """Get the error data for a thread using its name
        """
        return self._errors.get(name)

    @property
    def any_errors(self):
        """Return True of there have been any errors in any threads
        """
        with self._errors_lock:
            return any(self._errors.values())

    def raise_if_error(self, name):
        """If a thread has failed due to an exception, raise it into the main
           thread and remove it from errors.
        """
        if name not in self._errors:
            # no errors found for the thread
            return

        with self._errors_lock:
            exc_info = self._errors.pop(name)
        if exc_info:
            raise exc_info[0](exc_info[1]).with_traceback(exc_info[2])

    def in_main_thread(self):
        """Return True if it is run in the main thread."""

        cur_thread = threading.current_thread()
        return cur_thread is self._main_thread

    @property
    def running(self):
        """ Return the number of running threads.

            :returns: number of running threads
            :rtype:   int
        """
        with self._objs_lock:
            return len(self._objs)

    @property
    def names(self):
        """ Return the names of the running threads.

            :returns: list of thread names
            :rtype:   list of strings
        """
        with self._objs_lock:
            return list(self._objs.keys())

    def wait_for_error_threads(self):
        """
        Waits for all threads that caused exceptions. In other words, waits for
        exception handling (possibly interactive) to be finished.

        """

        with self._errors_lock:
            for thread_name in self._errors.keys():
                thread = self._objs[thread_name]
                thread.join()

class AnacondaThread(threading.Thread):
    """A threading.Thread subclass that exists only for a couple purposes:

       (1) Make exceptions that happen in a thread invoke our exception handling
           code as well.  Otherwise, threads will silently die and we are doing
           a lot of complicated code in them now.

       (2) Remove themselves from the thread manager when completed.

       (3) All created threads are made daemonic, which means anaconda will quit
           when the main process is killed.
    """

    # class-wide dictionary ensuring unique thread names
    _prefix_thread_counts = dict()

    def __init__(self, *args, **kwargs):
        # if neither name nor prefix is given, use the worker prefix
        if "name" not in kwargs and "prefix" not in kwargs:
            kwargs["prefix"] = _WORKER_THREAD_PREFIX

        # if prefix is specified, use it to construct new thread name
        prefix = kwargs.pop("prefix", None)
        if prefix:
            thread_num = self._prefix_thread_counts.get(prefix, 0) + 1
            self._prefix_thread_counts[prefix] = thread_num
            kwargs["name"] = prefix + str(thread_num)

        if "fatal" in kwargs:
            self._fatal = kwargs.pop("fatal")
        else:
            self._fatal = True

        threading.Thread.__init__(self, *args, **kwargs)
        self.daemon = True

    def run(self, *args, **kwargs):
        # http://bugs.python.org/issue1230540#msg25696
        import sys

        log.info("Running Thread: %s (%s)", self.name, self.ident)
        try:
            threading.Thread.run(self, *args, **kwargs)
        # pylint: disable=bare-except
        except:
            threadMgr.set_error(self.name, *sys.exc_info())
            if self._fatal:
                sys.excepthook(*sys.exc_info())
        finally:
            threadMgr.remove(self.name)
            log.info("Thread Done: %s (%s)", self.name, self.ident)

def initThreading():
    """Set up threading for anaconda's use. This method must be called before
       any GTK or threading code is called, or else threads will only run when
       an event is triggered in the GTK main loop. And IT HAS TO BE CALLED IN
       THE MAIN THREAD.
    """
    global threadMgr
    threadMgr = ThreadManager()

threadMgr = None
