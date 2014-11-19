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

class BasicStorageTestCase(UITestCase):
    def check_select_disks(self, spoke):
        # FIXME:  This is a really roundabout way of determining whether a disk is
        # selected or not.  For some reason when a DiskOverview is selected, its icon
        # loses the name "Hard Disk".  For now, we can use this to check.
        def _selected(do):
            return len(do.findChildren(GenericPredicate(name="Hard Disk"))) == 0

        # A real disk is any disk attached to the VM that's not the special 10 MB
        # one used for communicating in and out of the VM.  Therefore, scan all
        # children of the DiskOverview looking for one whose name contains that
        # size.
        def _real_disk(do):
            for child in do.findChildren(GenericPredicate()):
                if child.name == "10 MiB":
                    return False

            return True

        # There should be some disks displayed on the screen.
        overviews = spoke.findChildren(GenericPredicate(roleName="disk overview"))
        self.assertGreater(len(overviews), 0, msg="No disks are displayed")

        if len(overviews) == 1:
            # Only one disk was given to this test case, so anaconda selected it
            # by default.  Verify.  Not sure how this would happen with how
            # testing is currently done, but it's good to be prepared.
            self.assertTrue(_selected(overviews[0]))
        else:
            # More than one disk was provided, so anaconda did not select any.
            # Let's select all disks and proceed.
            for overview in filter(_real_disk, overviews):
                self.assertFalse(_selected(overview))
                overview.click()
                self.assertTrue(_selected(overview))

    def check_shopping_cart(self, spoke):
        pass

    def check_storage_options(self, spoke):
        button = self.find("Automatically configure partitioning.", "radio button", node=spoke)
        self.assertIsNotNone(button, msg="Autopart button not found")
        self.assertTrue(button.checked, msg="Autopart should be selected")

        button = self.find("I would like to make additional space available.", "check box", node=spoke)
        self.assertIsNotNone(button, msg="Reclaim button not found")
        self.assertFalse(button.checked, msg="Reclaim button should not be selected")

        button = self.find("Encrypt my data.", "check box", node=spoke)
        self.assertIsNotNone(button, msg="Encrypt button not found")
        self.assertFalse(button.checked, msg="Encrypt button should not be selected")

    def _common_run(self):
        # First, we need to click on the storage spoke selector.
        self.enter_spoke("INSTALLATION DESTINATION")

        # Now verify we are on the right screen.
        w = self.check_window_displayed("INSTALLATION DESTINATION")
        self.check_help_button(w)

        # Given that we attach a second disk to the system (for storing the test
        # suite and results), anaconda will not select disks by default.  Thus,
        # the storage options panel should currently be insensitive.
        area = self.find("Storage Options", node=w)
        self.assertIsNotNone(area, "Storage Options not found")
        self.assertFalse(area.sensitive, msg="Storage options should be insensitive")

        # Select disk overviews.  In the basic case, this means uninitialized
        # disks that we're going to do autopart on.
        self.check_select_disks(w)

        # And now with disks selected, the storage options should be sensitive.
        self.assertTrue(area.sensitive, msg="Storage options should be sensitive")

        self.check_shopping_cart(w)
        self.check_storage_options(w)
        return w

    def _run(self):
        w = self._common_run()

        # And then we click the Done button which should take the user right back to
        # the hub.  There's no need to display any other dialogs given that this is
        # an install against empty disks and no other options were checked.
        self.exit_spoke(node=w)

class BasicReclaimTestCase(BasicStorageTestCase):
    def check_reclaim_buttons_before(self, dlg):
        # Test initial sensitivity of widgets upon entering the reclaim dialog.  A
        # partition should be selected in the view, the only way out should be via
        # the Cancel button, and the only operation available on the selected partition
        # should be deleting.
        button = self.find("Preserve", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Preserve button not found")
        self.assertFalse(button.sensitive, msg="Preserve button should be insensitive")

        button = self.find("Delete", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Delete button not found")
        self.assertTrue(button.sensitive, msg="Delete button should be sensitive")

        button = self.find("Shrink", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Shrink button not found")
        self.assertFalse(button.sensitive, msg="Shrink button should be insensitive")

        button = self.find("Delete all", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Delete all button not found")
        self.assertTrue(button.sensitive, msg="Delete all button should be sensitive")

        button = self.find("Cancel", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Cancel button not found")
        self.assertTrue(button.sensitive, msg="Cancel button should be sensitive")

        button = self.find("Reclaim space", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Reclaim button not found")
        self.assertFalse(button.sensitive, msg="Reclaim button should be insensitive")

    def check_reclaim_buttons_after(self, dlg):
        # Test sensitivity of widgets now that enough space has been freed up on disks
        # to continue.  The Preserve buttons should be the only available operations,
        # Delete all should have been renamed to Preserve All, and there should now be
        # two ways out of the dialog.
        button = self.find("Preserve", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Preserve button not found")
        self.assertTrue(button.sensitive, msg="Preserve button should be sensitive")

        button = self.find("Delete", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Delete button not found")
        self.assertFalse(button.sensitive, msg="Delete button should be insensitive")

        button = self.find("Shrink", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Shrink button not found")
        self.assertFalse(button.sensitive, msg="Shrink button should be insensitive")

        button = self.find("Preserve all", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Preserve all button not found")
        self.assertTrue(button.sensitive, msg="Preserve all button should be sensitive")

        button = self.find("Cancel", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Cancel button not found")
        self.assertTrue(button.sensitive, msg="Cancel button should be sensitive")

        button = self.find("Reclaim space", "push button", node=dlg)
        self.assertIsNotNone(button, msg="Reclaim button not found")
        self.assertTrue(button.sensitive, msg="Reclaim button should be sensitive")

    def check_reclaim(self, optionsDlg):
        self.click_button("Reclaim space", node=optionsDlg)

        # Verify we are on the reclaim dialog.
        reclaimDlg = self.check_dialog_displayed("Reclaim")
        self.check_reclaim_buttons_before(reclaimDlg)

        # Click the Delete all button to free up enough space.
        self.click_button("Delete all", node=reclaimDlg)
        self.check_reclaim_buttons_after(reclaimDlg)

        # Click on Reclaim space, which should take us all the way back to the hub.
        self.click_button("Reclaim space", node=reclaimDlg)
        doDelay(5)
        self.check_window_displayed("INSTALLATION SUMMARY")

    def _run(self):
        w = self._common_run()

        # Clicking the Done button should bring up the installation options dialog
        # indicating there's not currently enough space to install, but more space
        # can be made by going to the reclaim dialog.
        self.click_button("_Done", node=w)
        optionsDlg = self.check_dialog_displayed("Need Space")
        self.check_reclaim(optionsDlg)

class CantReclaimTestCase(BasicStorageTestCase):
    def _run(self):
        w = self._common_run()

        # Clicking the Done button should bring up the installation options dialog
        # indicating there's never going to be enough space to install.  There's nothing
        # to do now but quit.
        self.click_button("_Done", node=w)
        doDelay(5)
        optionsDlg = self.check_dialog_displayed("No Space")
        self.click_button("Quit installer", node=optionsDlg)
