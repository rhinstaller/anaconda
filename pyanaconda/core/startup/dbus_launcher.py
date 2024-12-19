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
import signal
from subprocess import TimeoutExpired

from dasbus.constants import DBUS_FLAG_NONE

from pyanaconda.anaconda_loggers import get_anaconda_root_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    ANACONDA_BUS_ADDR_FILE,
    ANACONDA_BUS_CONF_FILE,
    ANACONDA_CONFIG_TMP,
    DBUS_ANACONDA_SESSION_ADDRESS,
)
from pyanaconda.core.dbus import DBus
from pyanaconda.core.path import open_with_perm
from pyanaconda.core.util import startProgram
from pyanaconda.modules.common.constants.services import BOSS
from pyanaconda.modules.common.task import sync_run_task

log = get_anaconda_root_logger()

__all__ = ["AnacondaDBusLauncher"]


class AnacondaDBusLauncher:
    """Class for launching the Anaconda DBus modules."""

    DBUS_LAUNCH_BIN = "dbus-daemon"

    def __init__(self):
        self._dbus_daemon_process = None
        self._log_file = None
        self._bus_address = None

    @property
    def bus_address(self):
        """The address of the Anaconda DBus session."""
        return self._bus_address

    def start(self):
        """Start DBus modules.

        Start the DBus session, the boss and the kickstart modules.
        """
        self._write_temporary_config()

        self._start_dbus_session()
        self._set_environment()
        self._write_bus_address()

        self._start_boss()
        self._start_modules()

    def stop(self, timeout=20):
        """Stop the DBus modules.

        Stop the DBus session, the boss and the kickstart modules.

        :param timeout: seconds to the launcher timeout
        """
        self._stop_boss_and_modules()

        self._stop_dbus_session(timeout)
        self._remove_bus_address_file()

        self._remove_temporary_config()

    def _write_temporary_config(self):
        """Create the temporary config file."""
        dirname = os.path.dirname(ANACONDA_CONFIG_TMP)

        if not os.path.exists(dirname):
            os.makedirs(dirname)

        log.info("Configuration loaded from: %s", conf.get_sources())
        log.info("Writing the runtime configuration to: %s", ANACONDA_CONFIG_TMP)
        conf.write(ANACONDA_CONFIG_TMP)

    def _remove_temporary_config(self):
        """Remove the temporary config file."""
        if os.path.exists(ANACONDA_CONFIG_TMP):
            os.unlink(ANACONDA_CONFIG_TMP)

    def _start_dbus_session(self):
        """Start dbus session if not running already."""
        command = [
            self.DBUS_LAUNCH_BIN,
            '--print-address',
            "--syslog",
            "--config-file={}".format(ANACONDA_BUS_CONF_FILE)
        ]

        def dbus_preexec():
            # to set dbus subprocess SIGINT handler
            signal.signal(signal.SIGINT, signal.SIG_IGN)

        self._log_file = open_with_perm('/tmp/dbus.log', 'a', 0o600)
        self._dbus_daemon_process = startProgram(command, stderr=self._log_file, reset_lang=False,
                                                 preexec_fn=dbus_preexec)

        if self._dbus_daemon_process.poll() is not None:
            raise RuntimeError("DBus wasn't properly started!")

        address = self._dbus_daemon_process.stdout.readline().decode('utf-8').strip()

        if not address:
            raise RuntimeError("Unable to start DBus session!")

        self._bus_address = address

    def _stop_dbus_session(self, timeout):
        """Stop DBus service and clean bus address file."""
        if self._log_file:
            self._log_file.close()

        if not self._dbus_daemon_process:
            return

        self._dbus_daemon_process.terminate()

        try:
            self._dbus_daemon_process.wait(timeout)
        except TimeoutExpired:
            log.error("DBus daemon wasn't terminated kill it now")
            self._dbus_daemon_process.kill()

        ret_code = self._dbus_daemon_process.poll()

        if ret_code is None:
            log.error("DBus daemon can't be killed!")
        elif ret_code != 0:
            log.error("DBus daemon exited with error %s", ret_code)

    def _set_environment(self):
        """Set the environment variables."""
        # pylint: disable=environment-modify
        os.environ[DBUS_ANACONDA_SESSION_ADDRESS] = self._bus_address

    def _write_bus_address(self):
        """Write the bus address to a file."""
        file_name = ANACONDA_BUS_ADDR_FILE
        run_dir = os.path.dirname(file_name)

        if not os.path.exists(run_dir):
            os.mkdir(run_dir)

        with open(file_name, 'wt') as f:
            f.write(self._bus_address)

    def _remove_bus_address_file(self):
        """Remove the file with the bus address."""
        f = ANACONDA_BUS_ADDR_FILE
        if os.path.exists(f):
            os.unlink(f)

    def _start_boss(self):
        """Start the boss."""
        bus_proxy = DBus.proxy
        bus_proxy.StartServiceByName(BOSS.service_name, DBUS_FLAG_NONE)

    def _start_modules(self):
        """Start the kickstart modules."""
        boss_proxy = BOSS.get_proxy()
        task_path = boss_proxy.StartModulesWithTask()
        task_proxy = BOSS.get_proxy(task_path)
        sync_run_task(task_proxy)

    def _stop_boss_and_modules(self):
        """Stop the boss and the kickstart modules."""
        boss_proxy = BOSS.get_proxy()
        boss_proxy.Quit()
