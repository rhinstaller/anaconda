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

class LiveCDNetworkTestCase(UITestCase):
    def check_hostname_entry(self, spoke):
        # Only the live install hint and hostname box should be visible.
        self.assertTrue(self.find("Please use the live desktop environment's tools for customizing your network configuration.  You can set the host name here.", node=spoke).showing)

        box = self.find("Network Config Box", node=spoke)
        self.assertIsNotNone(box, "Network Config box not found")
        self.assertFalse(box.showing, msg="Network Config box should not be displayed")

        box = self.find("More Network Config Box", node=spoke)
        self.assertIsNotNone(box, "More Network Config box not found")
        self.assertFalse(box.showing, msg="More Network Config box should not be displayed")

        entry = self.find("Host Name", "text", node=spoke)
        self.assertIsNotNone(entry , "Hostname entry not found")
        self.assertTrue(entry.showing, msg="Hostname entry should be displayed")

    def _run(self):
        # First, we need to click on the network spoke selector.
        self.enter_spoke("NETWORK & HOST NAME")

        # Now verify we are on the right screen.
        w = self.check_window_displayed("NETWORK & HOST NAME")

        # And now we can check everything else on the screen.
        self.check_help_button(w)
        self.check_hostname_entry(w)

        # And then we click the Done button to go back to the hub, verifying
        # that's where we ended up.
        self.exit_spoke(node=w)
