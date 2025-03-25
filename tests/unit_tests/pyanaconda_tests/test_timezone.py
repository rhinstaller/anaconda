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

from pyanaconda import timezone
import unittest
from unittest.mock import patch, Mock


class TimezonesListings(unittest.TestCase):
    def test_string_timezones(self):
        """Check if returned timezones are plain strings, not unicode objects."""
        for (region, zones) in timezone.get_all_regions_and_timezones().items():
            assert isinstance(region, str)

            for zone in zones:
                assert isinstance(zone, str)

    def test_all_timezones_valid(self):
        """Check if all returned timezones are considered valid timezones."""

        for (region, zones) in timezone.get_all_regions_and_timezones().items():
            for zone in zones:
                assert timezone.is_valid_timezone(region + "/" + zone)


class TerritoryTimezones(unittest.TestCase):
    def test_string_valid_territory_zone(self):
        """Check if the returned value is string for a valid territory."""

        zone = timezone.get_preferred_timezone("CZ")
        assert isinstance(zone, str)

    def test_invalid_territory_zones(self):
        """Check if None is return for an invalid territory."""

        assert timezone.get_preferred_timezone("nonexistent") is None


class s390HWclock(unittest.TestCase):

    @patch('pyanaconda.timezone.arch.is_s390', return_value=True)
    @patch('pyanaconda.timezone.util.execWithRedirect')
    def test_s390_save_hw_clock(self, exec_mock, s390_mock):
        """Check that save_hw_clock does nothing on s390."""
        timezone.save_hw_clock(Mock())
        assert not exec_mock.called

    @patch('pyanaconda.timezone.arch.is_s390', return_value=True)
    @patch('pyanaconda.timezone.util.execWithRedirect')
    def test_s390_time_initialize(self, exec_mock, s390_mock):
        """Check that time_initialize doesn't call hwclock on s390."""
        timezone.time_initialize(Mock())
        assert exec_mock.called is False
