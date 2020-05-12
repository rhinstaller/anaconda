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

from dogtail.utils import doDelay

from tests.gui.base import UITestCase

class BasicRootPasswordTestCase(UITestCase):
    def check_enter_password(self, spoke):
        # The warning bar starts off telling us there's no password set.
        self.check_warning_bar("The password is empty", node=spoke)

        entry = self.find("Password", "password text", node=spoke)
        self.assertIsNotNone(entry, msg="Password entry should be displayed")
        entry.grabFocus()
        entry.text = "JustaTestPassword"

        # That is a strong password but we haven't confirmed it, so the
        # bar is still displayed at the bottom.
        doDelay(1)
        self.check_warning_bar("The passwords do not match", node=spoke)

        # Let's confirm the password.
        entry = self.find("Confirm Password", "password text", node=spoke)
        self.assertIsNotNone(entry, msg="Confirm password should be displayed")
        entry.grabFocus()
        entry.text = "JustaTestPassword"

        # the warning bar should not be displayed at the bottom.
        doDelay(1)
        self.check_no_warning_bar(node=spoke)

    def check_click_done(self, spoke):
        # Pressing Done should take us back to the progress hub.
        self.exit_spoke(hubName="CONFIGURATION", node=spoke)

    def _run(self):
        # First, we need to click on the spoke selector.
        self.enter_spoke("ROOT PASSWORD")

        # Now, verify we are on the right screen.
        w = self.check_window_displayed("ROOT PASSWORD")

        # And now we can check everything else on the screen.
        self.check_help_button(w)
        self.check_enter_password(w)
        self.check_click_done(w)
