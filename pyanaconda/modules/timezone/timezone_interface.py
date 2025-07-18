#
# DBus interface for the timezone module.
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
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import TIMEZONE
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.timezone import (
    GeolocationData,
    TimeSourceData,
)


@dbus_interface(TIMEZONE.interface_name)
class TimezoneInterface(KickstartModuleInterface):
    """DBus interface for Timezone module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Timezone", self.implementation.timezone_changed)
        self.watch_property("IsUTC", self.implementation.is_utc_changed)
        self.watch_property("NTPEnabled", self.implementation.ntp_enabled_changed)
        self.watch_property("TimeSources", self.implementation.time_sources_changed)
        self.watch_property("GeolocationResult", self.implementation.geolocation_result_changed)

    @property
    def Timezone(self) -> Str:
        """Timezone the system will use."""
        return self.implementation.timezone

    @Timezone.setter
    @emits_properties_changed
    def Timezone(self, timezone: Str):
        """Set the timezone with maximal priority.

        See SetTimezoneWithPriority for more details.

        :param timezone: a string with a timezone
        """
        self.implementation.set_timezone(timezone)

    @emits_properties_changed
    def SetTimezoneWithPriority(self, timezone: Str, priority: UInt16):
        """Set the timezone with a given priority.

        Sets the system time zone to timezone, if the already stored timezone does not have higher
        priority.

        To view a list of available time zones, use the `timedatectl list-timezones` command.

        Example: Europe/Prague

        The priority is a positive number. Use values defined in pyanaconda.core.constants
        as TIMEZONE_PRIORITY_* :
            TIMEZONE_PRIORITY_DEFAULT = 0
            TIMEZONE_PRIORITY_LANGUAGE = 30
            TIMEZONE_PRIORITY_GEOLOCATION = 50
            TIMEZONE_PRIORITY_KICKSTART = 70
            TIMEZONE_PRIORITY_USER = 90

        :param timezone: a string with a timezone specification in the Olson db aka tzdata format
        :param priority: priority for the timezone; see the respective constants
        """
        self.implementation.set_timezone_with_priority(timezone, priority)

    def GetAllValidTimezones(self) -> Dict[Str, List[Str]]:
        """Get valid timezones.

        Return a dictionary, where keys are region ids and values are lists
        of timezone names in the region.

        :return: a dictionary of timezone lists per region
        """
        return self.implementation.get_all_valid_timezones()

    @property
    def IsUTC(self) -> Bool:
        """Is the hardware clock set to UTC?

        The system assumes that the hardware clock is set to UTC
        (Greenwich Mean) time, if true.

        :return: True, if the hardware clock set to UTC, otherwise False
        """
        return self.implementation.is_utc

    @IsUTC.setter
    @emits_properties_changed
    def IsUTC(self, is_utc: Bool):
        """Set if the hardware clock set to UTC or not.

        :param is_utc: Is the hardware clock set to UTC?
        """
        self.implementation.set_is_utc(is_utc)

    @property
    def NTPEnabled(self) -> Bool:
        """Is automatic starting of NTP service enabled?

        :return: True, if the service is enabled, otherwise false.
        """
        return self.implementation.ntp_enabled

    @NTPEnabled.setter
    @emits_properties_changed
    def NTPEnabled(self, ntp_enabled: Bool):
        """Enable or disable automatic starting of NTP service.

        :param ntp_enabled: should be NTP service enabled?
        """
        self.implementation.set_ntp_enabled(ntp_enabled)

    @property
    def TimeSources(self) -> List[Structure]:
        """A list of time sources.

        :return: a list of time source data
        :rtype: a list of structures of the type TimeSourceData
        """
        return TimeSourceData.to_structure_list(
            self.implementation.time_sources
        )

    @TimeSources.setter
    @emits_properties_changed
    def TimeSources(self, sources: List[Structure]):
        """Set the time sources.

        :param sources: a list of time sources
        :type sources: a list of structures of the type TimeSourceData
        """
        self.implementation.set_time_sources(
            TimeSourceData.from_structure_list(sources)
        )

    @property
    def TimeServersFromConfig(self) -> List[Structure]:
        """A list of ntp servers found in the chronyd's configuration file.

        :return: a list of ntp server data
        :rtype: a list of structures of the type TimeSourceData
        """
        return TimeSourceData.to_structure_list(
            self.implementation.servers_from_config
        )

    def StartGeolocationWithTask(self) -> ObjPath:
        """Start geolocation with task.

        :return: a DBus path of the task
        """
        return TaskContainer.to_object_path(
            self.implementation.start_geolocation_with_task()
        )

    def CheckNTPServer(self, server_hostname: Str, nts_enabled: Bool) -> Bool:
        """Check if an NTP server is working.

        :param server_hostname: hostname or IP address of the NTP server
        :param nts_enabled: whether NTS (Network Time Security) is enabled
        :return: True if the server is working, False otherwise
        """
        return self.implementation.check_ntp_server(server_hostname, nts_enabled)

    @property
    def GeolocationResult(self) -> Structure:
        """Get geolocation result, if any.

        :return DBusData: geolocation result data
        """
        return GeolocationData.to_structure(
            self.implementation.geolocation_result
        )

    def GetSystemDateTime(self) -> Str:
        """Get the current local date and time of the system.

        The timezone set via the Timezone property affects the returned data.

        :return: a string representing the date and time in ISO 8601 format
        """
        return self.implementation.get_system_date_time()

    def SetSystemDateTime(self, date_time_spec: Str):
        """Set the current local date and time of the system.

        The timezone set via the Timezone property will be applied to the received data.

        :param date_time_spec: a string representing the date and time in ISO 8601 format
        """
        self.implementation.set_system_date_time(date_time_spec)
