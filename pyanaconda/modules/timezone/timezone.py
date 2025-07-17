#
# Kickstart module for date and time settings.
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

import datetime

from pykickstart.errors import KickstartParseError

from pyanaconda import ntp
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    TIME_SOURCE_POOL,
    TIME_SOURCE_SERVER,
    TIMEZONE_PRIORITY_DEFAULT,
    TIMEZONE_PRIORITY_KICKSTART,
    TIMEZONE_PRIORITY_USER,
)
from pyanaconda.core.dbus import DBus
from pyanaconda.core.i18n import _
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import TIMEZONE
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.common.structures.timezone import (
    GeolocationData,
    TimeSourceData,
)
from pyanaconda.modules.timezone.initialization import GeolocationTask
from pyanaconda.modules.timezone.installation import (
    ConfigureHardwareClockTask,
    ConfigureNTPTask,
    ConfigureTimezoneTask,
)
from pyanaconda.modules.timezone.kickstart import TimezoneKickstartSpecification
from pyanaconda.modules.timezone.timezone_interface import TimezoneInterface
from pyanaconda.timezone import (
    NTP_PACKAGE,
    get_all_regions_and_timezones,
    get_timezone,
    set_system_date_time,
)

log = get_module_logger(__name__)


class TimezoneService(KickstartService):
    """The Timezone service."""

    def __init__(self):
        super().__init__()
        self.timezone_changed = Signal()
        self._timezone = "America/New_York"
        self._priority = TIMEZONE_PRIORITY_DEFAULT

        self.geolocation_result_changed = Signal()
        self._geoloc_result = GeolocationData()

        self.is_utc_changed = Signal()
        self._is_utc = False

        self.ntp_enabled_changed = Signal()
        self._ntp_enabled = True

        self.time_sources_changed = Signal()
        self._time_sources = []

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(TIMEZONE.namespace)
        DBus.publish_object(TIMEZONE.object_path, TimezoneInterface(self))
        DBus.register_service(TIMEZONE.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return TimezoneKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_timezone_with_priority(data.timezone.timezone, TIMEZONE_PRIORITY_KICKSTART)
        self.set_is_utc(data.timezone.isUtc)
        sources = []

        for source_data in data.timesource.dataList():
            if source_data.ntp_disable:
                self.set_ntp_enabled(False)
                continue

            source = TimeSourceData()
            source.options = ["iburst"]

            if source_data.ntp_server:
                source.type = TIME_SOURCE_SERVER
                source.hostname = source_data.ntp_server
            elif source_data.ntp_pool:
                source.type = TIME_SOURCE_POOL
                source.hostname = source_data.ntp_pool
            else:
                raise KickstartParseError(
                    _("Invalid time source."),
                    lineno=source_data.lineno
                )

            if source_data.nts:
                source.options.append("nts")

            sources.append(source)

        self.set_time_sources(sources)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        data.timezone.timezone = self.timezone
        data.timezone.isUtc = self.is_utc
        source_data_list = data.timesource.dataList()

        if not self.ntp_enabled:
            source_data = data.TimesourceData()
            source_data.ntp_disable = True
            source_data_list.append(source_data)
            return

        for source in self.time_sources:
            source_data = data.TimesourceData()

            if source.type == TIME_SOURCE_SERVER:
                source_data.ntp_server = source.hostname
            elif source.type == TIME_SOURCE_POOL:
                source_data.ntp_pool = source.hostname
            else:
                log.warning("Skipping %s.", source)
                continue

            if "nts" in source.options:
                source_data.nts = True

            source_data_list.append(source_data)

    @property
    def timezone(self):
        """Return the timezone."""
        return self._timezone

    def set_timezone(self, timezone):
        """Set the timezone."""
        self.set_timezone_with_priority(timezone, TIMEZONE_PRIORITY_USER)

    def set_timezone_with_priority(self, timezone, priority):
        """Set the timezone with priority.

        Sets the timezone only if the priority is higher than the previous priority.
        """
        if priority < self._priority:
            log.debug("Timezone did not change %s -> %s due to too low priority: %d > %d.",
                      self._timezone, timezone, self._priority, priority)
            return

        self._timezone = timezone
        self._priority = priority
        self.timezone_changed.emit()
        log.debug("Timezone is set to %s.", timezone)

    def get_all_valid_timezones(self):
        """Get all valid timezones.

        :return: list of valid timezones
        :rtype: list of str
        """
        timezone_dict = get_all_regions_and_timezones()
        # convert to a dict of lists for easier transfer over DBus
        # - change the nested sets to lists
        new_timezone_dict = {}
        for region in timezone_dict:
            new_timezone_dict[region] = list(timezone_dict[region])
        return new_timezone_dict

    @property
    def is_utc(self):
        """Is the hardware clock set to UTC?"""
        return self._is_utc

    def set_is_utc(self, is_utc):
        """Set if the hardware clock is set to UTC."""
        self._is_utc = is_utc
        self.is_utc_changed.emit()
        log.debug("UTC is set to %s.", is_utc)

    @property
    def ntp_enabled(self):
        """Enable automatic starting of NTP service."""
        return self._ntp_enabled

    def set_ntp_enabled(self, ntp_enabled):
        """Enable or disable automatic starting of NTP service."""
        self._ntp_enabled = ntp_enabled
        self.ntp_enabled_changed.emit()
        log.debug("NTP is set to %s.", ntp_enabled)

    @property
    def time_sources(self):
        """Return a list of time sources."""
        return self._time_sources

    def set_time_sources(self, servers):
        """Set time sources."""
        self._time_sources = list(servers)
        self.time_sources_changed.emit()
        log.debug("Time sources are set to: %s", servers)

    @property
    def servers_from_config(self):
        """Return up-to-date list of ntp servers found in the chronyd's configuration file."""
        return ntp.get_servers_from_config()

    def collect_requirements(self):
        """Return installation requirements for this module.

        :return: a list of requirements
        """
        requirements = []

        # Add ntp service requirements.
        if self._ntp_enabled:
            requirements.append(
                Requirement.for_package(NTP_PACKAGE, reason="Needed to run NTP service.")
            )

        return requirements

    def install_with_tasks(self):
        """Return the installation tasks of this module.

        :return: list of installation tasks
        """
        return [
            ConfigureHardwareClockTask(
                is_utc=self.is_utc
            ),
            ConfigureTimezoneTask(
                sysroot=conf.target.system_root,
                timezone=self.timezone,
                is_utc=self.is_utc
            ),
            ConfigureNTPTask(
                sysroot=conf.target.system_root,
                ntp_enabled=self.ntp_enabled,
                ntp_servers=self.time_sources
            )
        ]

    def _set_geolocation_result(self, result):
        """Set geolocation result when the task finished."""
        self._geoloc_result = result
        self.geolocation_result_changed.emit()
        log.debug("Geolocation result is set, valid=%s", not self._geoloc_result.is_empty())

    def start_geolocation_with_task(self):
        """Start geolocation.

        :return: task to run for geolocation
        :rtype: Task
        """
        task = GeolocationTask()
        task.succeeded_signal.connect(lambda: self._set_geolocation_result(task.get_result()))
        return task

    def check_ntp_server(self, server_hostname, nts_enabled):
        """Check if an NTP server is working.

        :param server_hostname: hostname or IP address of the NTP server
        :param nts_enabled: whether NTS (Network Time Security) is enabled
        :return: True if the server is working, False otherwise
        :rtype: bool
        """
        return ntp.ntp_server_working(server_hostname, nts_enabled)

    @property
    def geolocation_result(self):
        """Get geolocation result.

        :return GeolocationData: result of the lookup, empty if not ready yet
        """
        return self._geoloc_result

    def get_system_date_time(self):
        """Get system time as a ISO 8601 formatted string.

        :return: system time as ISO 8601 formatted string
        :rtype: str
        """
        # convert to the expected tzinfo format via get_timezone()
        return datetime.datetime.now(get_timezone(self._timezone)).isoformat()

    def set_system_date_time(self, date_time_spec):
        """Set system time based on a ISO 8601 formatted string.

        :param str date_time_spec: ISO 8601 time specification to use
        """
        log.debug("Setting system time to: %s, with timezone: %s", date_time_spec, self._timezone)
        # first convert the ISO 8601 time string to a Python date object
        date = datetime.datetime.fromisoformat(date_time_spec)
        # set the date to the system
        set_system_date_time(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=date.hour,
            minute=date.minute,
            tz=self._timezone
        )
