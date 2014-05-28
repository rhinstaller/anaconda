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

from . import UITestCase

class BasicKeyboardTestCase(UITestCase):
    def _get_enabled_layouts(self, view):
        return [child.text for child in view.findChildren(GenericPredicate(roleName="table cell"))]

    def check_options_dialog(self):
        # Click the options button.
        self.click_button("Options")
        self.check_dialog_displayed("Layout Options")
        self.click_button("Cancel")

    def check_num_layouts(self):
        # There ought to be only one layout enabled right now.
        # FIXME:  This encodes default information.
        view = self.find("Selected Layouts")
        self.assertIsNotNone(view, "Selected Layouts view not found")
        self.assertEqual(len(self._get_enabled_layouts(view)), 1, msg="An unexpected number of keyboard layouts are enabled")

    def check_layout_buttons_initial(self):
        button = self.find("Add layout", "push button")
        self.assertIsNotNone(button, msg="Add layout button not found")
        self.assertTrue(button.sensitive, msg="Add layout button should be sensitive")

        # When no layouts are selected in the view, none of these buttons mean anything.
        button = self.find("Remove layout", "push button")
        self.assertIsNotNone(button, msg="Remove layout button not found")
        self.assertFalse(button.sensitive, msg="Remove layout button should not be sensitive")

        button = self.find("Move selected layout up", "push button")
        self.assertIsNotNone(button, msg="Move layout up button not found")
        self.assertFalse(button.sensitive, msg="Move layout up button should not be sensitive")

        button = self.find("Move selected layout down", "push button")
        self.assertIsNotNone(button, msg="Move layout down button not found")
        self.assertFalse(button.sensitive, msg="Move layout down button should not be sensitive")

        button = self.find("Preview layout", "push button")
        self.assertIsNotNone(button, msg="Preview layout button not found")
        self.assertFalse(button.sensitive, msg="Preview layout button should not be sensitive")

    def check_add_layout_dialog(self):
        self.click_button("Add layout")
        self.check_dialog_displayed("Add Layout")
        self.click_button("Cancel")

    def check_layout_buttons_after_click(self):
        # Click on the first (and only) layout shown in the view.  This
        # ensures buttons change sensitivity.
        # FIXME:  This encodes default information.
        view = self.find("Selected Layouts")
        self.assertIsNotNone(view, msg="Selected Layouts view not found")
        view.children[1].click()

        button = self.find("Add layout", "push button")
        self.assertIsNotNone(button, msg="Add layout button not found")
        self.assertTrue(button.sensitive, msg="Add layout button should be sensitive")

        button = self.find("Remove layout", "push button")
        self.assertIsNotNone(button, msg="Remove layout button not found")
        self.assertTrue(button.sensitive, msg="Remove layout button should be sensitive")

        # These two should still not be sensitive - we've only got one layout.
        # We ensured that with check_num_layouts.
        # FIXME:  This encodes default information.
        button = self.find("Move selected layout up", "push button")
        self.assertIsNotNone(button, msg="Move layout up button not found")
        self.assertFalse(button.sensitive, msg="Move layout up button should not be sensitive")

        button = self.find("Move selected layout down", "push button")
        self.assertIsNotNone(button, msg="Move layout down button not found")
        self.assertFalse(button.sensitive, msg="Move layout down button should not be sensitive")

        button = self.find("Preview layout", "push button")
        self.assertIsNotNone(button, msg="Preview layout button not found")
        self.assertTrue(button.sensitive, msg="Preview layout button should be sensitive")

    def check_preview_dialog(self):
        self.click_button("Preview layout")

        # Verify the preview dialog is displayed.  The dialog out to be titled
        # with the name of the current layout.  We happen to know that - it's
        # the default.
        # FIXME:  This encodes default information.
        self.check_dialog_displayed("English (US)")

        self.click_button("Close")

    def _run(self):
        # First, we need to click on the network spoke selector.
        self.enter_spoke("KEYBOARD")

        # Now verify we are on the right screen.
        self.check_window_displayed("KEYBOARD")

        # And now we can check everything else on the screen.
        self.check_options_dialog()
        self.check_num_layouts()
        self.check_layout_buttons_initial()
        self.check_add_layout_dialog()

        # Once a layout has been selected in the view, we can test these other buttons.
        self.check_layout_buttons_after_click()
        self.check_preview_dialog()

        # And then we click the Done button to go back to the hub, verifying
        # that's where we ended up.
        self.exit_spoke()
