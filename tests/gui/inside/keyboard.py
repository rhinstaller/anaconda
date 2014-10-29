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

class BasicKeyboardTestCase(UITestCase):
    def check_options_dialog(self, spoke):
        # No layout switching should be configured yet.
        self.assertTrue(self.find("Layout switching not configured.", node=spoke).showing)

        # Click the options button.
        self.click_button("Options", node=spoke)
        dlg = self.check_dialog_displayed("Layout Options")

        # Enable a layout switching combo by just clicking on the first checkbox.
        view = self.find("Layout Options", node=dlg)
        self.assertIsNotNone(view, "Layout Switching Options view not found")

        children = self.view_children(view)
        self.assertTrue(len(children) > 0, msg="No layouts found in view")
        children[0].click()

        # Leave the dialog and make sure the layout switching hint on the spoke has changed.
        self.click_button("OK", node=dlg)
        self.assertTrue(self.find("Alt+Caps Lock to switch layouts.", node=spoke).showing)

    def check_num_layouts(self, spoke, n):
        # FIXME:  This encodes default information.
        view = self.find("Selected Layouts", node=spoke)
        self.assertIsNotNone(view, "Selected Layouts view not found")
        self.assertEqual(len(self.view_children(view)), n, msg="An unexpected number of keyboard layouts are enabled")

    def check_layout_buttons_initial(self, spoke):
        button = self.find("Add layout", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Add layout button not found")
        self.assertTrue(button.sensitive, msg="Add layout button should be sensitive")

        # When no layouts are selected in the view, none of these buttons mean anything.
        button = self.find("Remove layout", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Remove layout button not found")
        self.assertFalse(button.sensitive, msg="Remove layout button should not be sensitive")

        button = self.find("Move selected layout up", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Move layout up button not found")
        self.assertFalse(button.sensitive, msg="Move layout up button should not be sensitive")

        button = self.find("Move selected layout down", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Move layout down button not found")
        self.assertFalse(button.sensitive, msg="Move layout down button should not be sensitive")

        button = self.find("Preview layout", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Preview layout button not found")
        self.assertFalse(button.sensitive, msg="Preview layout button should not be sensitive")

    def check_add_layout_dialog(self, spoke):
        # Click the Add button to bring up the dialog.
        self.click_button("Add layout", node=spoke)
        dlg = self.check_dialog_displayed("Add Layout")

        # Now on the dialog, the Add button should be insensitive initially.
        button = self.find("Add", node=dlg)
        self.assertIsNotNone(button, msg="Add button not found")
        self.assertFalse(button.sensitive, msg="Add button should not be sensitive")

        # Select the first layout in the dialog - 'af'.
        view = self.find("Available Layouts", node=dlg)
        self.assertIsNotNone(view, "Available Layouts view not found")

        children = self.view_children(view)
        self.assertTrue(len(children) > 0, msg="No layouts found in view")
        children[0].click()

        self.assertTrue(button.sensitive, msg="Add button should be sensitive")

        # Leave the dialog and make sure the new layout is visible on the spoke.
        # There are now two layouts available - 'us' (default), and 'af'.
        self.click_button("Add", node=dlg)
        self.check_num_layouts(spoke, 2)

    def check_layout_indicator(self, spoke):
        # First, the layout indicator should still show 'us' as the active layout.
        self.check_keyboard_layout_indicator("us", node=spoke)

        # Now if we click on it, the layout indicator should change to show 'af'.
        self.find("Keyboard Layout", node=spoke).click()
        self.check_keyboard_layout_indicator("af", node=spoke)

        # FIXME: The order of keyboard layouts in the view should also change
        # to match what happened in the layout indicator.  This is an anaconda
        # bug.

        # Click on it again, and it should go back to 'us'.
        self.find("Keyboard Layout", node=spoke).click()
        self.check_keyboard_layout_indicator("us", node=spoke)

    def check_layout_buttons_after_click(self, spoke):
        # Click on the first layout shown in the view.  This ensures buttons
        # change sensitivity.
        view = self.find("Selected Layouts", node=spoke)
        self.assertIsNotNone(view, msg="Selected Layouts view not found")
        view.children[1].click()

        button = self.find("Add layout", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Add layout button not found")
        self.assertTrue(button.sensitive, msg="Add layout button should be sensitive")

        button = self.find("Remove layout", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Remove layout button not found")
        self.assertTrue(button.sensitive, msg="Remove layout button should be sensitive")

        button = self.find("Move selected layout down", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Move layout down button not found")
        self.assertTrue(button.sensitive, msg="Move layout down button should be sensitive")

        # This should still not be sensitive - we selected the first layout, so
        # it's impossible to move up.
        button = self.find("Move selected layout up", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Move layout up button not found")
        self.assertFalse(button.sensitive, msg="Move layout up button should not be sensitive")

        button = self.find("Preview layout", "push button", node=spoke)
        self.assertIsNotNone(button, msg="Preview layout button not found")
        self.assertTrue(button.sensitive, msg="Preview layout button should be sensitive")

        # Now that we've just checked the sensitivity of everything, do something
        # with the buttons.  First, move the default 'us' layout down and then back
        # up to verify those two buttons work.
        self.click_button("Move selected layout down", node=spoke)
        self.click_button("Move selected layout up", node=spoke)

        # Click on the second layout and remove it.  This should leave only the initial
        # layout in the view.
        view = self.find("Selected Layouts", node=spoke)
        self.assertIsNotNone(view, "Selected Layouts view not found")

        children = self.view_children(view)
        children[1].click()
        self.click_button("Remove layout", node=spoke)
        self.check_num_layouts(spoke, 1)

    def check_preview_dialog(self, spoke):
        self.click_button("Preview layout", node=spoke)

        # Verify the preview dialog is displayed.  The dialog out to be titled
        # with the name of the current layout.  We happen to know that - it's
        # the default.
        # FIXME:  This encodes default information.
        dlg = self.check_dialog_displayed("English (US)")

        self.click_button("Close", node=dlg)

    def _run(self):
        # First, we need to click on the network spoke selector.
        self.enter_spoke("KEYBOARD")

        # Now verify we are on the right screen.
        w = self.check_window_displayed("KEYBOARD LAYOUT")

        # And now we can check everything else on the screen.
        self.check_help_button(w)
        self.check_options_dialog(w)
        self.check_num_layouts(w, 1)
        self.check_layout_buttons_initial(w)

        # Once a layout has been added, we can test the keyboard layout indicator.
        self.check_add_layout_dialog(w)
        self.check_layout_indicator(w)

        # Once a layout has been selected in the view, we can test these other buttons.
        self.check_layout_buttons_after_click(w)
        self.check_preview_dialog(w)

        # And then we click the Done button to go back to the hub, verifying
        # that's where we ended up.
        self.exit_spoke(node=w)
