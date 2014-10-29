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
from dogtail.predicate import GenericPredicate
from dogtail.utils import doDelay

from . import UITestCase

# This test case handles the livecd case on the summary hub where everything
# works as intended.  On this spoke, we are testing the following:
#
# * Clicking the Quit button brings up a dialog asking if you're sure, though
#   we're not going to test that confirming actually quits.
# * The Begin Installation button is insensitive, since no disks have yet
#   been selected.
# * Only the Date & Time, Keyboard, Installation Destination, and Network Config
#   spoke selectors are visible.

class LiveCDSummaryTestCase(UITestCase):
    def check_quit_button(self, spoke):
        self.click_button("Quit", node=spoke)
        dlg = self.check_dialog_displayed("Quit")
        self.click_button("No", node=dlg)

    def check_begin_installation_button(self, spoke):
        button = self.find("Begin Installation", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Begin Installation button not found")
        self.assertTrue(button.showing, msg="Begin Installation button should be displayed")
        self.assertFalse(button.sensitive, msg="Begin Installation button should not be sensitive")

    def check_shown_spoke_selectors(self, spoke):
        # FIXME:  This forces English.
        validSelectors = ["TIME & DATE", "KEYBOARD", "INSTALLATION DESTINATION", "NETWORK & HOST NAME"]
        selectors = spoke.findChildren(GenericPredicate(roleName="spoke selector"))

        self.assertEqual(len(selectors), len(validSelectors), msg="Incorrect number of spoke selectors shown")

        # Validate that only the spoke selectors we expect are shown.  At the same time,
        # we can also validate the status of each selector.  This only validates the
        # initial state of everything.  Once we start clicking on spokes, things are
        # going to change.
        # FIXME:  This encodes default information.
        for selector in selectors:
            if selector.name == "TIME & DATE":
                self.assertEqual(selector.description, "Americas/New York timezone")
            elif selector.name == "KEYBOARD":
                self.assertEqual(selector.description, "English (US)")
            elif selector.name == "INSTALLATION DESTINATION":
                # We don't know how many disks are going to be involved - if there's
                # just one, anaconda selects it by default.  If there's more than
                # one, it selects none.
                self.assertIn(selector.description, ["Automatic partitioning selected",
                                                     "No disks selected"])
            elif selector.name == "NETWORK & HOST NAME":
                self.assertTrue(selector.description.startswith("Connected:"))
            else:
                self.fail("Invalid spoke selector shown on livecd: %s" % selector.name)

    def _run(self):
        # Before doing anything, verify we are on the right screen.
        doDelay(5)
        w = self.check_window_displayed("INSTALLATION SUMMARY")

        # And now we can check everything else on the screen.
        self.check_help_button(w)
        self.check_quit_button(w)
        self.check_begin_installation_button(w)
        self.check_shown_spoke_selectors(w)
        self.check_warning_bar(node=w)
