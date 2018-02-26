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

from pyanaconda.dbus.constants import DBUS_SESSION_ADDRESS
from pyanaconda.core.util import execWithCapture
from pyanaconda.core.constants import ANACONDA_BUS_ADDR_FILE

__all__ = ["is_dbus_session_running", "start_dbus_session", "write_bus_address",
           "get_anaconda_dbus_address", "clean_bus_address_file"]

DBUS_LAUNCH_BIN = "dbus-daemon"


def is_dbus_session_running():
    """Check if dbus session is running.

    :returns: True if DBus is running, False otherwise
    """
    if os.environ.get(DBUS_SESSION_ADDRESS):
        return True

    return False


def get_anaconda_dbus_address():
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


def start_dbus_session():
    """Start dbus session if not running already.

    :returns: True if session was started, False otherwise
    """
    if is_dbus_session_running():
        return False

    address = execWithCapture(DBUS_LAUNCH_BIN,
                              ["--session", "--print-address", "--fork", "--syslog"],
                              filter_stderr=True)

    if not address:
        raise IOError("Unable to start DBus session!")

    # pylint: disable=environment-modify
    os.environ[DBUS_SESSION_ADDRESS] = address.rstrip('\n')
    return True


def write_bus_address():
    address = os.environ[DBUS_SESSION_ADDRESS]
    file_name = ANACONDA_BUS_ADDR_FILE
    run_dir = os.path.dirname(file_name)

    if not os.path.exists(run_dir):
        os.mkdir(run_dir)

    with open(file_name, 'wt') as f:
        f.write(address)


def clean_bus_address_file():
    """Delete bus address file in /var/run/anaconda/ ."""
    f = ANACONDA_BUS_ADDR_FILE
    if os.path.exists(f):
        os.unlink(f)
