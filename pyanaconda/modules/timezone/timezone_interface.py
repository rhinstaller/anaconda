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
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import
from dasbus.server.interface import dbus_interface

from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import TIMEZONE
from pyanaconda.modules.common.structures.timezone import TimeSourceData, GeolocationData


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

    @emits_properties_changed
    def SetTimezone(self, timezone: Str):
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

    @property
    def IsUTC(self) -> Bool:
        """Is the hardware clock set to UTC?

        The system assumes that the hardware clock is set to UTC
        (Greenwich Mean) time, if true.

        :return: True, if the hardware clock set to UTC, otherwise False
        """
        return self.implementation.is_utc

    @emits_properties_changed
    def SetIsUTC(self, is_utc: Bool):
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

    @emits_properties_changed
    def SetNTPEnabled(self, ntp_enabled: Bool):
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

    @emits_properties_changed
    def SetTimeSources(self, sources: List[Structure]):
        """Set the time sources.

        :param sources: a list of time sources
        :type sources: a list of structures of the type TimeSourceData
        """
        self.implementation.set_time_sources(
            TimeSourceData.from_structure_list(sources)
        )

    def StartGeolocationWithTask(self) -> ObjPath:
        """Start geolocation with task.

        :return: a DBus path of the task
        """
        return TaskContainer.to_object_path(
            self.implementation.start_geolocation_with_task()
        )

    @property
    def GeolocationResult(self) -> Structure:
        """Get geolocation result, if any.

        :return DBusData: geolocation result data
        """
        return GeolocationData.to_structure(
            self.implementation.geolocation_result
        )
