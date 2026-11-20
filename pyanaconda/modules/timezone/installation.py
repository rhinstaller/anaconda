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
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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

    def __init__(self, timezone_service):
        """Create a new task.

        :param TimezoneService timezone_service: The TimezoneService that knows the RTC mode
        """
        super().__init__()
        self._timezone_service = timezone_service

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
            if self._timezone_service.is_utc:
                args.append("--utc")
            else:
                args.append("--local")

            util.execWithRedirect(cmd, args)


class ConfigureTimezoneTask(Task):
    """Installation task for timezone configuration."""

    def __init__(self, sysroot, timezone_service):
        """Create a new task.

        :param str sysroot: a path to the root of the installed system
        :param TimezoneService timezone_service: The TimezoneService that knows the RTC mode and timezone
        """
        super().__init__()
        self._sysroot = sysroot
        self._timezone_service = timezone_service

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
        tz = self._timezone_service.timezone
        if not is_valid_timezone(tz):
            # this should never happen, but for pity's sake
            log.warning("Timezone %s set in kickstart is not valid, "
                        "falling back to default (America/New_York).", tz)
            self._timezone_service.set_timezone("America/New_York")

    def _make_timezone_symlink(self):
        """Create the symlink that actually defines timezone."""

        # we want to create a relative symlink
        tz_file = "/usr/share/zoneinfo/" + self._timezone_service.timezone
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
                if self._timezone_service.is_utc:
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


class ChronyUnavailable(Exception):
    pass


class RTCHeuristicTask(Task):
    """Installation task to heuristically determine the RTC mode."""

    # How close do two times have to be for us to consider them basically the same?
    TIME_NEAR_TOLERANCE = timedelta(minutes=2)

    def __init__(self, timezone_service):
        """Create a new task.

        :param TimezoneService timezone_service: The TimezoneService to set the RTC mode on.
        """
        super().__init__()
        self._timezone_service = timezone_service

    @property
    def name(self):
        return "Determine RTC mode"

    def run(self):
        """Perform the work of guessing the RTC mode."""
        if not self._timezone_service.rtc_heuristic:
            return

        ntp_utc = self._chrony_utc()
        rtc = self._read_rtc()
        if not ntp_utc or not rtc:
            return # Can't guess

        tz = self._timezone_service.timezone
        if tz:
            try:
                ntp_local = ntp_utc.astimezone(ZoneInfo(tz))
            except ZoneInfoNotFoundError:
                return

            utc_plausible = self._time_near(rtc, ntp_utc)
            local_plausible = self._time_near(rtc, ntp_local)

            # If one choice is clearly better, choose it and adjust
            # the system time to match.
            if utc_plausible and not local_plausible:
                self._timezone_service.set_is_utc(True)
                util.execProgram('hwclock', ['--hctosys', '--utc'])
            elif local_plausible and not utc_plausible:
                self._timezone_service.set_is_utc(False)
                util.execProgram('hwclock', ['--hctosys', '--local'])
            # Otherwise we can't choose, just keep the previous choice

    def _chrony_utc_once(self):
        """Read the UTC time from chrony, or None if unsynced."""
        status, out = util.execProgram('chronyc', ['-c', 'tracking'])
        if status != 0:
            raise ChronyUnavailable()

        fields = out.rstrip().split(',')
        status = fields[13]
        if status == "Not synchronised":
            return None

        offset = float(fields[4])
        return datetime.now(timezone.utc) + timedelta(seconds=offset)

    def _chrony_utc(self):
        """Read the UTC time from chrony, best-effort syncing if necessary."""
        try:
            utc = self._chrony_utc_once()
            if not utc:
                # In time_initialize, we may call `hwclock --hctosys`. Chrony detects
                # this external change, and unsyncs temporarily. It will generally
                # resync within 2-4 minutes on its own. It then will start adjusting
                # the sysclock, though usually very slowly.
                #
                # If we're in that gap, accelerate resync so we can measure UTC.
                # This could potentially bring forward chrony changing sysclock,
                # but since we already allow that to happen during installation,
                # it shouldn't be a problem.
                util.execProgram('chronyc', ['burst', '3/10'])
                util.execProgram('chronyc', ['waitsync', '10', '0', '0', '1'])
                utc = self._chrony_utc_once()
            return utc
        except ChronyUnavailable:
            return None

    def _read_rtc(self):
        """Read the RTC time."""
        status, out = util.execProgram("hwclock", ["--show", "--utc"], env_add={"TZ": "UTC0"})
        if status != 0:
            return None
        return datetime.fromisoformat(out.strip())

    def _time_near(self, t1, t2):
        return abs(t1.replace(tzinfo=None) - t2.replace(tzinfo=None)) < self.TIME_NEAR_TOLERANCE
