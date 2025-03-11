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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
#  Author(s):  Jiri Konecny <jkonecny@redhat.com>
#
import os
import signal

from pyanaconda.core.glib import child_watch_add, source_remove
from pyanaconda.errors import ExitError

__all__ = ["PidWatcher", "WatchProcesses"]


class PidWatcher:
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


class WatchProcesses:
    """Static class for watching external processes."""

    # Dictionary of processes to watch in the form {pid: [name, GLib event source id], ...}
    _forever_pids = {}
    # Set to True if process watching is handled by GLib
    _watch_process_glib = False
    _watch_process_handler_set = False

    @classmethod
    def _raise_exit_error(cls, statuses):
        """Raise an error on process exit. The argument is a list of tuples
       of the form [(name, status), ...] with statuses in the subprocess
       format (>=0 is return codes, <0 is signal)
        """
        exn_message = []

        for proc_name, status in statuses:
            if status >= 0:
                status_str = "with status %s" % status
            else:
                status_str = "on signal %s" % -status

            exn_message.append("%s exited %s" % (proc_name, status_str))

        raise ExitError(", ".join(exn_message))

    @classmethod
    def _sigchld_handler(cls, num=None, frame=None):
        """Signal handler used with watchProcess"""
        # Check whether anything in the list of processes being watched has
        # exited. We don't want to call waitpid(-1), since that would break
        # anything else using wait/waitpid (like the subprocess module).
        exited_pids = []
        exit_statuses = []

        for child_pid, proc in cls._forever_pids.items():
            try:
                pid_result, status = os.waitpid(child_pid, os.WNOHANG)
            except ChildProcessError:
                continue

            if pid_result:
                proc_name = proc[0]
                exited_pids.append(child_pid)

                # Convert the wait-encoded status to the format used by subprocess
                if os.WIFEXITED(status):
                    sub_status = os.WEXITSTATUS(status)
                else:
                    # subprocess uses negative return codes to indicate signal exit
                    sub_status = -os.WTERMSIG(status)

                exit_statuses.append((proc_name, sub_status))

        for child_pid in exited_pids:
            if cls._forever_pids[child_pid][1]:
                source_remove(cls._forever_pids[child_pid][1])
            del cls._forever_pids[child_pid]

        if exit_statuses:
            cls._raise_exit_error(exit_statuses)

    @classmethod
    def _watch_process_cb(cls, pid, status, proc_name):
        """GLib callback used with watchProcess."""
        # Convert the wait-encoded status to the format used by subprocess
        if os.WIFEXITED(status):
            sub_status = os.WEXITSTATUS(status)
        else:
            # subprocess uses negative return codes to indicate signal exit
            sub_status = -os.WTERMSIG(status)

        cls._raise_exit_error([(proc_name, sub_status)])

    @classmethod
    def watch_process(cls, proc, name):
        """Watch for a process exit, and raise a ExitError when it does.

       This method installs a SIGCHLD signal handler and thus interferes
       the child_watch_add methods in GLib. Use watchProcessGLib to convert
       to GLib mode if using a GLib main loop.

       Since the SIGCHLD handler calls wait() on the watched process, this call
       cannot be combined with Popen.wait() or Popen.communicate, and also
       doing so wouldn't make a whole lot of sense.

       :param proc: The Popen object for the process
       :param name: The name of the process
        """
        if not cls._watch_process_glib and not cls._watch_process_handler_set:
            signal.signal(signal.SIGCHLD, cls._sigchld_handler)
            cls._watch_process_handler_set = True

        # Add the PID to the dictionary
        # The second item in the list is for the GLib event source id and will be
        # replaced with the id once we have one.
        cls._forever_pids[proc.pid] = [name, None]

        # If GLib is watching processes, add a watcher. child_watch_add checks if
        # the process has already exited.
        if cls._watch_process_glib:
            cls._forever_pids[proc.id][1] = child_watch_add(proc.pid, cls._watch_process_cb, name)
        else:
            # Check that the process didn't already exit
            if proc.poll() is not None:
                del cls._forever_pids[proc.pid]
                cls._raise_exit_error([(name, proc.returncode)])

    @classmethod
    def unwatch_process(cls, proc):
        """Unwatch a process watched by watchProcess.

        :param proc: The Popen object for the process.
        """
        if cls._forever_pids[proc.pid][1]:
            source_remove(cls._forever_pids[proc.pid][1])
        del cls._forever_pids[proc.pid]

    @classmethod
    def unwatch_all_processes(cls):
        """Clear the watched process list."""
        for proc in cls._forever_pids.values():
            if proc[1]:
                source_remove(proc[1])
        cls._forever_pids = {}
