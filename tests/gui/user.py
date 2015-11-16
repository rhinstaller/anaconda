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

class BasicUserTestCase(UITestCase):
    def check_enter_name(self, spoke):
        entry = self.find("Full Name", "text", node=spoke)
        self.assertIsNotNone(entry, msg="Full name entry not found")
        entry.grabFocus()
        entry.text = "Bobby Good User"

        # We base the username on the full name entered
        entry = self.find("Username", "text", node=spoke)
        self.assertIsNotNone(entry, msg="Username entry not found")
        self.assertEqual(entry.text, "buser", msg="Generated username does not match expectation")

    def check_enter_password(self, spoke):
        # The warning bar starts off telling us there's no password set.
        self.check_warning_bar("The password is empty", node=spoke)

        entry = self.find("Password", "password text", node=spoke)
        self.assertIsNotNone(entry, msg="Password entry should be displayed")
        entry.grabFocus()
        entry.text = "asdfasdf"

        # That wasn't a very good password and we haven't confirmed it, so the
        # bar is still displayed at the bottom.
        self.check_warning_bar("The password you have provided is weak.", node=spoke)

        # Let's confirm that terrible password.
        entry = self.find("Confirm Password", "password text", node=spoke)
        self.assertIsNotNone(entry, msg="Confirm password should be displayed")
        entry.grabFocus()
        entry.text = "asdfasdf"

        # But of course it's still a terrible password, so the bar is still
        # displayed at the bottom.
        self.check_warning_bar("The password you have provided is weak.", node=spoke)

    def check_click_done(self, spoke):
        # Press the Done button once, which won't take us anywhere but will change the
        # warning label at the bottom.
        self.click_button("_Done", node=spoke)
        self.check_warning_bar("Press Done again", node=spoke)

        # Pressing Done again should take us back to the progress hub.
        self.exit_spoke(hubName="CONFIGURATION", node=spoke)

    def _run(self):
        # First, we need to click on the spoke selector.
        self.enter_spoke("USER CREATION")

        # Now, verify we are on the right screen.
        w = self.check_window_displayed("CREATE USER")

        # And now we can check everything else on the screen.
        self.check_help_button(w)
        self.check_enter_name(w)
        self.check_enter_password(w)
        self.check_click_done(w)
