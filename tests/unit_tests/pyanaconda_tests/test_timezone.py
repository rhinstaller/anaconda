#
# Copyright (C) 2013  Red Hat, Inc.
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
import unittest
from collections import OrderedDict
from unittest.mock import patch

from freezegun import freeze_time

from pyanaconda import timezone


class TimezonesListings(unittest.TestCase):

    def test_get_all_regions_and_timezones(self):
        """Test the get_all_regions_and_timezones function."""
        regions_and_timezones = timezone.get_all_regions_and_timezones()
        assert regions_and_timezones

        for (region, zones) in regions_and_timezones.items():
            assert region and isinstance(region, str)
            assert zones and isinstance(zones, set)

            for zone in zones:
                assert zone and isinstance(zone, str)
                assert timezone.is_valid_timezone(region + "/" + zone)

    def test_get_all_regions_and_timezones_compare(self):
        """Compare the previous implementation with the current one."""
        result = OrderedDict()

        for tz in sorted(timezone.all_timezones()):
            parts = tz.split("/", 1)

            if len(parts) > 1:
                if parts[0] not in result:
                    result[parts[0]] = set()
                result[parts[0]].add(parts[1])

        assert result == timezone.get_all_regions_and_timezones()

    def test_parse_timezone(self):
        """Test the parse_timezone function."""
        regions_and_timezones = timezone.get_all_regions_and_timezones()

        # Cover some of the invalid and valid use cases.
        assert timezone.parse_timezone("") == ("", "")
        assert timezone.parse_timezone("/") == ("", "")
        assert timezone.parse_timezone("Europe") == ("", "")
        assert timezone.parse_timezone("Europe/") == ("", "")
        assert timezone.parse_timezone("Europe/") == ("", "")
        assert timezone.parse_timezone("/Prague") == ("", "")
        assert timezone.parse_timezone("Europe/Prague") == ("Europe", "Prague")

        # Parse all valid timezones.
        for (region, zones) in regions_and_timezones.items():
            for zone in zones:
                assert timezone.parse_timezone(region + "/" + zone) == (region, zone)

class TerritoryTimezones(unittest.TestCase):
    def test_string_valid_territory_zone(self):
        """Check if the returned value is string for a valid territory."""

        zone = timezone.get_preferred_timezone("CZ")
        assert isinstance(zone, str)

    def test_invalid_territory_zones(self):
        """Check if None is return for an invalid territory."""

        assert timezone.get_preferred_timezone("nonexistent") is None


class SystemTime(unittest.TestCase):
    @freeze_time("2021-01-01")
    @patch('pyanaconda.timezone.execWithRedirect')
    def test_system_time_now(self, exec_mock):
        """Test we do timezone math properly when setting system time
        to "now". 1609459200 is 00:00:00 on 2021-01-01; with time
        frozen to that point, whatever timezone we call the function
        with, it should end up with that number. We also test
        2021-06-01 (with the appropriate expected result) for zones
        which do DST, as that date is during daylight savings.
        """
        # default tz (UTC)
        timezone.set_system_date_time()
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1609459200"])
        timezone.set_system_date_time(tz="US/Eastern")
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1609459200"])
        with freeze_time("2021-06-01"):
            timezone.set_system_date_time(tz="US/Eastern")
            exec_mock.assert_called_with("/usr/bin/date", ["--set=@1622505600"])
        timezone.set_system_date_time(tz="Asia/Kolkata")
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1609459200"])
        timezone.set_system_date_time(tz="Asia/Aden")
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1609459200"])

    @freeze_time("2021-01-01 12:00:00")
    @patch('pyanaconda.timezone.execWithRedirect')
    def test_system_time_explicit(self, exec_mock):
        """Test we do timezone math properly when setting system time
        to explicit values, in and out of daylight savings.
        """
        timezone.set_system_date_time(2020, 1, 1, 0, 0)
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1577836800"])
        timezone.set_system_date_time(2020, 1, 1, 0, 0,  "US/Eastern")
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1577854800"])
        timezone.set_system_date_time(2020, 6, 1, 0, 0, "US/Eastern")
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1590984000"])
        timezone.set_system_date_time(2020, 1, 1, 0, 0, "Asia/Kolkata")
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1577817000"])
        timezone.set_system_date_time(2020, 1, 1, 0, 0, "Asia/Aden")
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1577826000"])

    @freeze_time("2021-01-01 12:00:00")
    @patch('pyanaconda.timezone.execWithRedirect')
    def test_system_time_hybrid(self, exec_mock):
        """Test we do timezone math properly when setting system time
        to a mix of "now" and explicit values, in and out of daylight
        savings. We use 12pm as 12pm UTC is on the same date in each
        tested timezone.
        """
        timezone.set_system_date_time(None, None, None, 19, 15)
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1609528500"])
        timezone.set_system_date_time(
            None, None, None, 19, 15, "US/Eastern"
        )
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1609546500"])
        with freeze_time("2021-06-01 12:00:00"):
            timezone.set_system_date_time(
                None, None, None, 19, 15, "US/Eastern"
            )
            exec_mock.assert_called_with("/usr/bin/date", ["--set=@1622589300"])
        timezone.set_system_date_time(
            None, None, None, 19, 15, "Asia/Kolkata"
        )
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1609508700"])
        timezone.set_system_date_time(
            None, None, None, 19, 15, "Asia/Aden"
        )
        exec_mock.assert_called_with("/usr/bin/date", ["--set=@1609517700"])
