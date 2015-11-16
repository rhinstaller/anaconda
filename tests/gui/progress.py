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

import signal

from dogtail.predicate import GenericPredicate
from dogtail.utils import doDelay
from . import UITestCase

class LiveCDProgressTestCase(UITestCase):
    def check_begin_installation_button(self, hub):
        button = self.find("Begin Installation", "push button", node=hub)
        self.assertIsNotNone(button, msg="Begin Installation button does not exist")
        self.assertTrue(button.sensitive, msg="Begin Installation button should be sensitive")

    def check_shown_spoke_selectors(self, hub):
        # FIXME:  This forces English.
        validSelectors = ["ROOT PASSWORD", "USER CREATION"]
        selectors = hub.findChildren(GenericPredicate(roleName="spoke selector"))

        self.assertEqual(len(selectors), len(validSelectors), msg="Incorrect number of spoke selectors shown")

        # Validate that only the spoke selectors we expect are shown.  At the same time,
        # we can also validate the status of each selector.  This only validates the
        # initial state of everything.  Once we start clicking on spokes, things are
        # going to change.
        # FIXME:  This encodes default information.
        for selector in selectors:
            if selector.name == "ROOT PASSWORD":
                self.assertEqual(selector.description, "Root password is not set")
            elif selector.name == "USER CREATION":
                self.assertEqual(selector.description, "No user will be created")
            else:
                self.fail("Invalid spoke selector shown on livecd: %s" % selector.name)

    def _timer_expired(self, signum, frame):
        self.fail("anaconda did not finish in 30 minutes")

    def _run(self):
        # Before doing anything, verify we are still on the summary hub.
        w = self.check_window_displayed("INSTALLATION SUMMARY")
        # All spokes should have been visited and satisfied now.
        self.check_no_warning_bar(w)
        self.check_begin_installation_button(w)

        # Click the begin installation button, wait a moment, and now we should
        # be on the progress hub.
        self.click_button("Begin Installation", node=w)

        w = self.check_window_displayed("CONFIGURATION")
        self.check_shown_spoke_selectors(w)
        self.check_warning_bar(node=w)
        self.check_help_button(w)

        # Now we need to wait for installation to finish.  We're doing that two ways:
        # (1) Set a 30 minute timeout.  Should we hit that, anaconda's clearly not
        #     going to finish (or is hung or something) and we should fail.
        # (2) Poll the UI waiting for the "Complete!" message to pop up.  Once
        #     that happens, we know it's time to test the user settings stuff and
        #     the end of the UI.
        signal.signal(signal.SIGALRM, self._timer_expired)
        signal.alarm(30*60)

        while True:
            label = self.find("Complete!", node=w)
            if label:
                signal.alarm(0)
                break

            doDelay(20)

        # If we got here, installation completed successfully.  Since we've not
        # done a password or created a user yet, we still have to do that.  The
        # finish configuration button should still be insensitive.
        button = self.find("Finish configuration", "push button", node=w)
        self.assertIsNotNone(button, msg="Finish configuration button not found")
        self.assertFalse(button.sensitive, msg="Finish Configuration button should not be sensitive")

class LiveCDFinishTestCase(UITestCase):
    def check_finish_config_button(self, hub):
        # Click the Finish Configuration button.
        self.click_button("Finish configuration", node=hub)

    def _timer_expired(self, signum, frame):
        self.fail("anaconda did not finish in 5 minutes")

    def _run(self):
        # Before doing anything, verify we are still on the progress hub.
        w = self.check_window_displayed("CONFIGURATION")

        self.check_finish_config_button(w)
        # We've completed configuration, so the warning bar should be gone.
        self.check_no_warning_bar(node=w)

        # And now we wait for configuration to finish.  Then we check the
        # reboot button, but don't click it.  The end of the test case shuts
        # down the system for us.
        signal.signal(signal.SIGALRM, self._timer_expired)
        signal.alarm(5*60)

        while True:
            button = self.find("Quit", "push button", node=w)
            if button and button.showing:
                signal.alarm(0)
                break

            doDelay(20)

        self.click_button("Quit", node=w)
