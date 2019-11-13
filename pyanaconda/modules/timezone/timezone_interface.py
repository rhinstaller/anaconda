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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.modules.common.constants.services import TIMEZONE
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterface
from dasbus.server.interface import dbus_interface


@dbus_interface(TIMEZONE.interface_name)
class TimezoneInterface(KickstartModuleInterface):
    """DBus interface for Timezone module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Timezone", self.implementation.timezone_changed)
        self.watch_property("IsUTC", self.implementation.is_utc_changed)
        self.watch_property("NTPEnabled", self.implementation.ntp_enabled_changed)
        self.watch_property("NTPServers", self.implementation.ntp_servers_changed)

    @property
    def Timezone(self) -> Str:
        """Timezone the system will use."""
        return self.implementation.timezone

    @emits_properties_changed
    def SetTimezone(self, timezone: Str):
        """Set the timezone.

        Sets the system time zone to timezone. To view a list of
        available time zones, use the timedatectl list-timezones
        command.

        Example: Europe/Prague

        :param timezone: a string with a timezone
        """
        self.implementation.set_timezone(timezone)

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
    def NTPServers(self) -> List[Str]:
        """A list of NTP servers.

        :return: a list of servers
        """
        return self.implementation.ntp_servers

    @emits_properties_changed
    def SetNTPServers(self, servers: List[Str]):
        """Set the NTP servers.

        Example: [ntp.cesnet.cz]

        :param servers: a list of servers
        """
        self.implementation.set_ntp_servers(servers)
