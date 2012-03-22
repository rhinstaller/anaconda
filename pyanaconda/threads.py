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
import threading

class ThreadManager(object):
    """A singleton class for managing threads and processes.

       Note:  This manager makes one assumption that contradicts python's
       threading module documentation.  In this class, we assume that thread
       names are unique and meaningful.  This is an okay assumption for us
       to make given that anaconda is only ever going to have a handful of
       special purpose threads.
    """
    def __init__(self):
        self._objs = {}

    def __call__(self):
        return self

    def add(self, obj):
        """Given a Thread or Process object, add it to the list of known objects
           and start it.  It is assumed that obj.name is unique and descriptive.
        """
        if obj.name in self._objs:
            return KeyError

        self._objs[obj.name] = obj
        obj.start()

    def exists(self, name):
        """Determine if a thread or process exists with the given name."""
        return name in self._objs

    def get(self, name):
        """Given an object name, see if it exists and return the object.
           Return None if no such object exists.
        """
        return self._objs.get(name)

def initThreading():
    from gi.repository import GObject
    GObject.threads_init()

    # http://bugs.python.org/issue1230540#msg25696
    import sys
    run_old = threading.Thread.run

    def run(*args, **kwargs):
        try:
            run_old(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            sys.excepthook(*sys.exc_info())

    threading.Thread.run = run

threadMgr = ThreadManager()
