#!/usr/bin/python2
#
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
from dogtail.config import config
from dogtail.predicate import GenericPredicate
from dogtail.tree import SearchError, root
from dogtail.utils import doDelay, screenshot

import glob
import unittest

class UITestCase(unittest.TestCase):
    """A UITestCase is a class that incorporates all the test functions for a
       single anaconda Hub or Spoke window.  Moving to the window, and dealing
       with what happens after we move away is left up to whatever wraps up
       all the test cases.  A single Hub or Spoke may have multiple instances
       of this class - one may test the assumption that everything works as it
       should, while another may test that a specific initial setup fails in
       an expected way, and another may attempt fuzz testing on all entries on
       the screen.  However, a single TestSuite will only have one instance
       for each anaconda window.

       Some basic assumptions about the existence of UI elements are made in
       UITestCase subclasses.  If an element is required to be there (for
       instance, a button we are going to click) we simply grab the element
       with the exception-raising dogtail functions and call click on it.
       If the element does not exist, the exception will be propagated up and
       fail the test.  If we are testing for the existence of some element
       (for instance, that a dialog was displayed after a button was clicked)
       then we use UITestCase.find and the unittest.assert* functions.

       This is kind of subtle, but look at existing test cases for examples.

       Due to the unusual nature of running such a large program as anaconda
       in a test suite, combined with the special environment, tests are
       organized inside a UITestCase as follows:

       * Testing one little piece of the window is handled by a check_*
         function.  These are explicitly not named test_* as that is special
         to unittest.

       * Multiple check_* functions are called linearly in the _run method,
         which is used instead of runTest for error handling purposes.
    """

    ###
    ### OVERRIDES OF THINGS FROM TestCase
    ###

    def runTest(self):
        """A version of TestCase.runTest that attempts to take a screenshot of
           anaconda should a test fail.  Subclasses should not override this.
           See the documentation for _run.
        """
        config.load({"scratchDir": "/mnt/anactest/result/"})

        try:
            self._run()
        except (AssertionError, SearchError):
            # Try to take a screenshot of whatever screen anaconda's on, so
            # we can attempt to figure out what went wrong.
            screenshot()
            raise

    def _run(self):
        """Do all the tests for this test case.  This is like the TestCase.runTest
           method, but we've overridden that to do more specialized error handling.
           Thus, all testing should be done in this method.
        """
        pass

    def setUp(self):
        self.ana = root.application("anaconda")

    ###
    ### METHODS FOR FINDING WIDGETS
    ###

    def find(self, name, roleName=None, node=None):
        """Wrap findChild, returning None if no widget is found instead of
           raising an exception.  This method also allows for checking if
           anaconda has hit a traceback and if so, fails the test
           immediately.
        """
        if len(glob.glob("/tmp/anaconda-tb-*")) > 0:
            self.fail("anaconda encountered a traceback")

        if not node:
            node = self.ana

        try:
            return node.child(name=name, roleName=roleName)
        except SearchError:
            return None

    def view_children(self, view):
        return [child for child in view.findChildren(GenericPredicate(roleName="table cell"))]

    def selected_view_children(self, view):
        return [child for child in self.view_children(view) if child.selected]

    ###
    ### METHODS FOR CHECKING A SINGLE WIDGET
    ###

    def check_window_displayed(self, name):
        """Verify that a window (such as a hub or spoke) given by the
           provided name is currently displayed on the screen.  If not,
           the current test case will be failed.
        """
        w = self.find(name, roleName="panel")
        self.assertIsNotNone(w, msg="%s not found" % name)
        self.assertTrue(w.showing, msg="%s is not displayed" % name)
        return w

    def check_dialog_displayed(self, name):
        """Verify that a dialog given by the provided name is currently
           displayed on the screen.  If not, the current test case will
           be failed.
        """
        w = self.find(name, "dialog")
        self.assertIsNotNone(w, msg="%s not found" % name)
        self.assertTrue(w.showing, msg="%s is not displayed" % name)
        return w

    def check_keyboard_layout_indicator(self, layout, node=None):
        """Verify that the keyboard layout indicator is present and that
           the currently enabled layout is what we expect.  If not, the
           current test case will be failed.
        """
        indicator = self.find("Keyboard Layout", node=node)
        self.assertIsNotNone(indicator, msg="keyboard layout indicator not found")
        self.assertEqual(indicator.description, layout,
                         msg="keyboard layout indicator not set to %s" % layout)

    def check_help_button(self, node=None):
        self.click_button("Help!", node=node)

        try:
            yelp = root.application("yelp")
        except SearchError:
            self.fail("Help view is not displayed.")

        doDelay(2)
        yelp.keyCombo("<Alt>F4")

    def check_no_warning_bar(self, node=None):
        """Verify that the warning bar is not currently displayed."""
        self.assertIsNone(self.find("Warning", node=node), msg="Warning bar should not be displayed")

    def check_warning_bar(self, msg=None, node=None):
        """Verify that the warning bar is currently displayed.  If msg is given,
           verify that it is contained in whatever message the warning bar is
           showing.
        """
        bar = self.find("Warning", node=node)
        self.assertTrue(bar.showing, msg="Warning bar should be displayed")
        if msg:
            self.assertIn(msg, bar.child(roleName="label").text)

    def click_button(self, name, node=None):
        """Verify that a button with the given name exists and is sensitive,
           and then click it.
        """
        b = self.find(name, "push button", node=node)
        self.assertIsNotNone(b, msg="%s button not found" % name)
        self.assertTrue(b.sensitive, msg="%s button should be sensitive" % name)
        b.click()

    def enter_spoke(self, spokeSelectorName):
        """Click on the spoke selector for the given spoke, then wait a moment
           to make sure it has appeared.
        """
        selector = self.find(spokeSelectorName, "spoke selector")
        self.assertIsNotNone(selector, msg="Selector %s not found" % spokeSelectorName)
        selector.click()

    def exit_spoke(self, hubName="INSTALLATION SUMMARY", node=None):
        """Leave a spoke by clicking the Done button in the upper left corner,
           then verify we have returned to the proper hub.  Since most spokes
           are off the summary hub, that's the default.  If we are not back
           on the hub, the current test case will be failed.
        """
        button = self.find("_Done", "push button", node=node)
        self.assertIsNotNone(button, msg="Done button not found")
        button.click()
        doDelay(5)
        self.check_window_displayed(hubName)
