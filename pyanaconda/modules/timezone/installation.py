#
# Copyright (C) 2019 Red Hat, Inc.
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
import os
import os.path

from blivet import arch

from pyanaconda import ntp
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import service, util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.errors.installation import TimezoneConfigurationError
from pyanaconda.modules.common.task import Task
from pyanaconda.timezone import NTP_SERVICE, is_valid_timezone

__all__ = ["ConfigureHardwareClockTask", "ConfigureNTPTask", "ConfigureTimezoneTask"]

log = get_module_logger(__name__)


class ConfigureHardwareClockTask(Task):
    """Installation task for setting the Hardware Clock from the System Clock."""

    def __init__(self, is_utc):
        """Create a new task.

        :param bool is_utc: Indicate which timescale the Hardware Clock is set to
        """
        super().__init__()
        self._is_utc = is_utc

    @property
    def name(self):
        return "Set the Hardware Clock from the System Clock"

    def run(self):
        """Perform the actual work of setting the Hardware Clock from the System Clock."""
        if arch.is_s390():
            log.debug("There is not Hardware Clock on s390x.")
            return

        if conf.system.can_set_hardware_clock:
            cmd = "hwclock"
            args = ["--systohc"]
            if self._is_utc:
                args.append("--utc")
            else:
                args.append("--local")

            util.execWithRedirect(cmd, args)


class ConfigureTimezoneTask(Task):
    """Installation task for timezone configuration."""

    def __init__(self, sysroot, timezone, is_utc):
        """Create a new task.

        :param str sysroot: a path to the root of the installed system
        :param str timezone: time zone to set
        :param bool is_utc: whether time is UTC or local
        """
        super().__init__()
        self._sysroot = sysroot
        self._timezone = timezone
        self._is_utc = is_utc

    @property
    def name(self):
        return "Configure time zone"

    def run(self):
        """Perform the actual work of setting up timezone."""
        self._correct_timezone()
        self._make_timezone_symlink()
        self._write_etc_adjtime()

    def _correct_timezone(self):
        """Ensure the timezone is valid."""
        if not is_valid_timezone(self._timezone):
            # this should never happen, but for pity's sake
            log.warning("Timezone %s set in kickstart is not valid, "
                        "falling back to default (America/New_York).", self._timezone)
            self._timezone = "America/New_York"

    def _make_timezone_symlink(self):
        """Create the symlink that actually defines timezone."""

        # we want to create a relative symlink
        tz_file = "/usr/share/zoneinfo/" + self._timezone
        rooted_tz_file = os.path.normpath(self._sysroot + tz_file)
        relative_path = os.path.normpath("../" + tz_file)
        link_path = os.path.normpath(self._sysroot + "/etc/localtime")

        if not os.access(rooted_tz_file, os.R_OK):
            log.error("Timezone to be linked (%s) doesn't exist", rooted_tz_file)
            return

        try:
            # os.symlink fails if link_path exists, so try to remove it first
            os.remove(link_path)
        except OSError:
            pass

        try:
            os.symlink(relative_path, link_path)
        except OSError as oserr:
            log.error("Error when symlinking timezone (from %s): %s",
                      rooted_tz_file, oserr.strerror)

    def _write_etc_adjtime(self):
        """Write /etc/adjtime contents.

        :raise: TimezoneConfigurationError
        """
        if arch.is_s390():
            # there is no Hardware clock on s390(x)
            return

        try:
            with open(os.path.normpath(self._sysroot + "/etc/adjtime"), "r") as fobj:
                lines = fobj.readlines()
        except OSError:
            lines = ["0.0 0 0.0\n", "0\n"]

        try:
            with open(os.path.normpath(self._sysroot + "/etc/adjtime"), "w") as fobj:
                fobj.write(lines[0])
                fobj.write(lines[1])
                if self._is_utc:
                    fobj.write("UTC\n")
                else:
                    fobj.write("LOCAL\n")
        except OSError as e:
            msg = "Error while writing /etc/adjtime file: {}".format(e.strerror)
            raise TimezoneConfigurationError(msg) from e


class ConfigureNTPTask(Task):
    """Installation task for NTP configuration."""

    def __init__(self, sysroot, ntp_enabled, ntp_servers):
        """Create a new task.

        :param str sysroot: a path to the root of the installed system
        :param bool ntp_enabled: is NTP enabled or not
        :param ntp_servers: list of NTP servers and pools
        :type ntp_servers: list of str
        """
        super().__init__()
        self._sysroot = sysroot
        self._ntp_enabled = ntp_enabled
        self._ntp_servers = ntp_servers

    @property
    def name(self):
        return "Configure NTP"

    def run(self):
        """Perform the actual work of setting up NTP."""
        self._enable_service()
        self._write_configuration()

    def _enable_service(self):
        """Enable or disable the chrony service."""
        if not service.is_service_installed(NTP_SERVICE, root=self._sysroot):
            log.debug("The NTP service is not installed.")
            return

        if self._ntp_enabled:
            service.enable_service(NTP_SERVICE, root=self._sysroot)
        else:
            service.disable_service(NTP_SERVICE, root=self._sysroot)

    def _write_configuration(self):
        """Write the chrony configuration."""
        if not (self._ntp_enabled and self._ntp_servers):
            log.debug("The NTP service is not enabled or configured.")
            return

        chronyd_conf_path = os.path.normpath(self._sysroot + ntp.NTP_CONFIG_FILE)

        if os.path.exists(chronyd_conf_path):
            log.debug("Modifying installed chrony configuration")
            try:
                ntp.save_servers_to_config(
                    self._ntp_servers,
                    conf_file_path=chronyd_conf_path
                )
            except ntp.NTPconfigError as ntperr:
                log.warning("Failed to save NTP configuration: %s", ntperr)

        # use chrony conf file from installation environment when
        # chrony is not installed (chrony conf file is missing)
        else:
            log.debug("Creating chrony configuration based on the "
                      "configuration from installation environment")
            try:
                ntp.save_servers_to_config(
                    self._ntp_servers,
                    conf_file_path=ntp.NTP_CONFIG_FILE,
                    out_file_path=chronyd_conf_path
                )
            except ntp.NTPconfigError as ntperr:
                log.warning("Failed to save NTP configuration without chrony package: %s",
                            ntperr)
