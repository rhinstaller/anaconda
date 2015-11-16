# Copyright (C) 2014  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Chris Lumens <clumens@redhat.com>

from . import UITestCase

class LiveCDDateTimeTestCase(UITestCase):
    def check_region_city(self, spoke):
        # FIXME:  This encodes default information.
        entry = self.find("Region", "text", node=spoke)
        self.assertIsNotNone(entry, "Region entry does not exist")
        self.assertEqual(entry.text, "Americas", msg="Region should be set to default")

        entry = self.find("City", "text")
        self.assertIsNotNone(entry, "City entry does not exist")
        self.assertEqual(entry.text, "New York", msg="City should be set to default")

    def check_ntp(self, spoke):
        # NTP should be enabled given that we started up with networking.
        # FIXME:  This encodes default information.
        button = self.find("Use Network Time", "toggle button", node=spoke)
        self.assertIsNotNone(button, msg="Use Network Time button not found")
        self.assertTrue(button.checked, msg="NTP should be enabled")

        button = self.find("Configure NTP", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Configure NTP button not found")
        self.assertTrue(button.sensitive, msg="Configure NTP button should be sensitive")

        area = self.find("Set Date & Time", node=spoke)
        self.assertIsNotNone(area, msg="Set Date & Time not found")
        self.assertFalse(area.sensitive, msg="Date & Time region should not be sensitive")

    def _run(self):
        # First, we need to click on the network spoke selector.
        self.enter_spoke("TIME & DATE")

        # Now verify we are on the right screen.
        w = self.check_window_displayed("TIME & DATE")

        # And now we can check everything else on the screen.
        self.check_help_button(w)
        self.check_region_city(w)
        self.check_ntp(w)

        # And then we click the Done button to go back to the hub, verifying
        # that's where we ended up.
        self.exit_spoke(node=w)
