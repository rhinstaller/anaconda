#
# Functions to launch and test DBus session.
#
# Functions here are NOT RECOMMENDED to be called in modules. These functions
# could have unexpected behavior when called in modules and not in main
# anaconda application.
#
# Copyright (C) 2018
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
# Author(s):  Jiri Konecny <jkonecny@redhat.com>
#

import os
from subprocess import TimeoutExpired

from pyanaconda.dbus.constants import DBUS_SESSION_ADDRESS
from pyanaconda.core.util import startProgram
from pyanaconda.core.constants import ANACONDA_BUS_ADDR_FILE
from pyanaconda.anaconda_loggers import get_anaconda_root_logger

log = get_anaconda_root_logger()

__all__ = ["DBusLauncher"]


class DBusLauncher(object):

    DBUS_LAUNCH_BIN = "dbus-daemon"
    TERMINATE_WAITING_TIME = 20

    def __init__(self):
        self._dbus_daemon_process = None
        self._log_file = None

    @classmethod
    def is_dbus_session_running(cls):
        """Check if dbus session is running.

        :returns: True if DBus is running, False otherwise
        """
        if os.environ.get(DBUS_SESSION_ADDRESS):
            return True

        return False

    @classmethod
    def get_anaconda_dbus_address(cls):
        """Return name of the dbus session where Anaconda lives.

        :returns: dbus session name
        :rtype: str
        """
        bus_addr_file = ANACONDA_BUS_ADDR_FILE
        if os.path.exists(bus_addr_file):
            with open(bus_addr_file, 'rt') as f:
                return f.readline().rstrip('\n')
        else:
            return ""

    def start_dbus_session(self):
        """Start dbus session if not running already.

        :returns: True if session was started, False otherwise
        """
        if self.is_dbus_session_running():
            return False

        self._log_file = open('/tmp/dbus.log', 'a')
        command = [DBusLauncher.DBUS_LAUNCH_BIN, "--session", '--print-address', "--syslog"]
        self._dbus_daemon_process = startProgram(command, stderr=self._log_file)

        if self._dbus_daemon_process.poll() is not None:
            raise IOError("DBus wasn't properly started!")

        address = self._dbus_daemon_process.stdout.readline().decode('utf-8')

        if not address:
            raise IOError("Unable to start DBus session!")

        # pylint: disable=environment-modify
        os.environ[DBUS_SESSION_ADDRESS] = address.rstrip('\n')
        return True

    def write_bus_address(self):
        address = os.environ[DBUS_SESSION_ADDRESS]
        file_name = ANACONDA_BUS_ADDR_FILE
        run_dir = os.path.dirname(file_name)

        if not os.path.exists(run_dir):
            os.mkdir(run_dir)

        with open(file_name, 'wt') as f:
            f.write(address)

    def stop(self):
        """Stop DBus service and clean bus address file."""
        f = ANACONDA_BUS_ADDR_FILE
        if os.path.exists(f):
            os.unlink(f)

        if self._log_file:
            self._log_file.close()

        if not self._dbus_daemon_process:
            return

        self._dbus_daemon_process.terminate()

        try:
            self._dbus_daemon_process.wait(DBusLauncher.TERMINATE_WAITING_TIME)
        except TimeoutExpired:
            log.error("DBus daemon wasn't terminated kill it now")
            self._dbus_daemon_process.kill()

        if self._dbus_daemon_process.poll() is not None:
            log.error("DBus daemon can't be killed!")
