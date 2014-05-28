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

class BasicStorageTestCase(UITestCase):
    def check_select_disks(self):
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
                if child.name.startswith("10."):
                    return False

            return True

        # There should be some disks displayed on the screen.
        overviews = self.ana.findChildren(GenericPredicate(roleName="disk overview"))
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

    def check_shopping_cart(self):
        pass

    def check_storage_options(self):
        button = self.find("Automatically configure partitioning.", "radio button")
        self.assertIsNotNone(button, msg="Autopart button not found")
        self.assertTrue(button.checked, msg="Autopart should be selected")

        button = self.find("I would like to make additional space available.", "check box")
        self.assertIsNotNone(button, msg="Reclaim button not found")
        self.assertFalse(button.checked, msg="Reclaim button should not be selected")

        button = self.find("Encrypt my data.", "check box")
        self.assertIsNotNone(button, msg="Encrypt button not found")
        self.assertFalse(button.checked, msg="Encrypt button should not be selected")

    def _run(self):
        # First, we need to click on the network spoke selector.
        self.enter_spoke("INSTALLATION DESTINATION")

        # Now verify we are on the right screen.
        self.check_window_displayed("INSTALLATION DESTINATION")

        # Given that we attach a second disk to the system (for storing the test
        # suite and results), anaconda will not select disks by default.  Thus,
        # the storage options panel should currently be insensitive.
        area = self.find("Storage Options")
        self.assertIsNotNone(area, "Storage Options not found")
        self.assertFalse(area.sensitive, msg="Storage options should be insensitive")

        # Select disk overviews.  In the basic case, this means uninitialized
        # disks that we're going to do autopart on.
        self.check_select_disks()

        # And now with disks selected, the storage options should be sensitive.
        self.assertTrue(area.sensitive, msg="Storage options should be sensitive")

        self.check_shopping_cart()
        self.check_storage_options()

        # And then we click the Done button which should take the user right back to
        # the hub.  There's no need to display any other dialogs given that this is
        # an install against empty disks and no other options were checked.
        self.exit_spoke()
