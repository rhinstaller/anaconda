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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

from pyanaconda import timezone
import unittest
import mock

class TimezonesListings(unittest.TestCase):
    def string_timezones_test(self):
        """Check if returned timezones are plain strings, not unicode objects."""
        for (region, zones) in timezone.get_all_regions_and_timezones().items():
            self.assertIsInstance(region, str)

            for zone in zones:
                self.assertIsInstance(zone, str)

    def all_timezones_valid_test(self):
        """Check if all returned timezones are considered valid timezones."""

        for (region, zones) in timezone.get_all_regions_and_timezones().items():
            for zone in zones:
                self.assertTrue(timezone.is_valid_timezone(region + "/" + zone))

class TerritoryTimezones(unittest.TestCase):
    def string_valid_territory_zone_test(self):
        """Check if the returned value is string for a valid territory."""

        zone = timezone.get_preferred_timezone("CZ")
        self.assertIsInstance(zone, str)

    def invalid_territory_zones_test(self):
        """Check if None is return for an invalid territory."""

        self.assertIsNone(timezone.get_preferred_timezone("nonexistent"))

class s390HWclock(unittest.TestCase):
    def setUp(self):
        self.arch_mock = mock.Mock()
        self.arch_mock.isS390.return_value = True
        self.iutil_mock = mock.Mock()

        # pylint: disable=no-member
        timezone.save_hw_clock.func_globals["arch"] = self.arch_mock
        # pylint: disable=no-member
        timezone.save_hw_clock.func_globals["iutil"] = self.iutil_mock

    def s390_save_hw_clock_test(self):
        """Check that save_hw_clock does nothing on s390."""

        timezone.save_hw_clock(mock.Mock())
        self.assertFalse(self.iutil_mock.execWithRedirect.called)

    def s390_time_initialize_test(self):
        """Check that time_initialize doesn't call hwclock on s390."""

        timezone.time_initialize(mock.Mock(), mock.Mock(), mock.Mock())
        self.assertFalse(self.iutil_mock.execWithRedirect.called)
