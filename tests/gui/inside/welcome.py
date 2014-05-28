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

# This test case handles the basic case on the welcome language spoke where
# everything works as intended.  On this spoke, we are testing the following:
#
#   * The default language and locale are selected and displayed at the top
#     of their views.
#   * Clicking the Quit button brings up a dialog asking if you're sure, though
#     we're not going to test that confirming actually quits.
#   * Clicking the Continue button brings up the betanag dialog, though we're
#     not going to test the quit button there either.
#
# TODO:
#   * Entering text into the search box should result in narrowing down the
#     contents of the left hand view.

class BasicWelcomeTestCase(UITestCase):
    def check_lang_locale_views(self):
        # FIXME:  This encodes default information.
#        lang = "English"
#        locale = "English (United States)"

        return
#        self.assertEqual(ldtp.verifytablecell("frmWelcome", "tblLanguages", 0, 0, lang), 1,
#                         msg="Default language (%s) is not selected" % lang)
#        self.assertEqual(ldtp.verifytablecell("frmWelcome", "tblLocales", 0, 0, locale), 1,
#                         msg="Default locale (%s) is not selected")

    def check_quit_button(self):
        self.click_button("_Quit")
        self.check_dialog_displayed("Quit")
        self.click_button("No")

    def check_continue_button(self):
        self.click_button("_Continue")
        self.check_dialog_displayed("Beta Warn")
        self.click_button("I accept my fate.")

    def _run(self):
        # Before doing anything, verify we are on the right screen.
        self.check_window_displayed("WELCOME")

        # And now we can check everything else on the screen.
        self.check_keyboard_layout_indicator("us")
        self.check_lang_locale_views()
        self.check_quit_button()
        self.check_continue_button()
