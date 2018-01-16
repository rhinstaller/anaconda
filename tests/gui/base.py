#!/usr/bin/python3
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

from blivet.size import MiB

import os
import copy
import glob
import shutil
import selinux
import subprocess
import tempfile
import traceback
import unittest

import testconfig
from dogtail.config import config as dogtail_config
from dogtail.predicate import GenericPredicate
from dogtail.tree import SearchError, root
from dogtail.utils import doDelay, isA11yEnabled, screenshot
from nose.plugins.multiprocess import TimedOutException

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

    suite_name = None

    def update_scratch_dir(self, name=""):
        """ Update the directory where Dogtail saves screenshots. """
        path = os.path.join(testconfig.config.get("resultsdir", ""), name)
        if not path.endswith("/"):
            path += "/"

        if not os.path.isdir(path):
            os.makedirs(path)

        dogtail_config.load({"scratchDir": path})

    ###
    ### OVERRIDES OF THINGS FROM TestCase
    ###

    def runTest(self):
        """A version of TestCase.runTest that attempts to take a screenshot of
           anaconda should a test fail.  Subclasses should not override this.
           See the documentation for _run.
        """
        self.update_scratch_dir(self.suite_name)

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
        self.ana = root.application("anaconda.py")

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
        return [child for child in self.view_children(view) if child.parent == view and child.selected]

    ###
    ### METHODS FOR CHECKING A SINGLE WIDGET
    ###
    def wait_for_configuration_to_settle(self, spoke):
        """ Wait for some of the configuration to settle down
            before continuing further.
        """
        selectors = spoke.findChildren(GenericPredicate(roleName="spoke selector"))

        for wait_for in ["INSTALLATION SOURCE", "SOFTWARE SELECTION", "INSTALLATION DESTINATION"]:
            retry = 0
            while retry < 5:
                for selector in selectors:
                    if (selector.name == wait_for):
                        if not selector.sensitive:
                            retry += 1
                            doDelay(10)
                        else:
                            retry = 5 # break while
                            break

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
        return # temporary, see https://bugzilla.redhat.com/show_bug.cgi?id=1282432
        # self.click_button("Help!", node=node)

        # try:
        #     yelp = root.application("yelp")
        # except SearchError:
        #     self.fail("Help view is not displayed.")

        # doDelay(2)
        # yelp.keyCombo("<Alt>F4")

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


@unittest.skipIf(os.geteuid() != 0, "GUI tests must be run as root")
@unittest.skipIf(os.environ.get("DISPLAY", "") == "", "DISPLAY must be defined")
@unittest.skipIf(selinux.is_selinux_enabled() and selinux.security_getenforce() == 1, "SELinux must be disabled or in Permissive mode, see rhbz#1276376")
@unittest.skipIf(not isA11yEnabled(), "Assistive Technologies are disabled")
class DogtailTestCase(unittest.TestCase):
    """A subclass that defines all the parameters for starting a local
       copy of anaconda, inspecting results, and managing temporary data!

       Most subclasses will only need to define the following four attributes:

       drives       -- A list of tuples describing disk images to create.  Each
                       tuple is the name of the drive and its size as a blivet.Size.
       environ      -- A dictionary of environment variables that should be added
                       to the environment the test suite will run under.
       name         -- A unique string that names the test.  This name will
                       be used in creating the results directory (and perhaps
                       other places in the future) so make sure it doesn't
                       conflict with another object.
       tests        -- A list describing which test cases make up this test.
                       Each item is the class name containing the test case.
                       Items *must* be descendants of UITestCase().
                       Tests will be run in the order provided.
    """
    drives = []
    environ = {}
    name = "DogtailTestCase"
    tests = []

    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        self._drivePaths = {}
        self._proc = None
        self._tempdir = None
        self._orig_environ = {}

        # add tests for each spoke
        self.suite = unittest.TestSuite()
        for test in self.tests:
            T = test()
            T.suite_name = self.name
            self.suite.addTest(T)
        self.test_result = None

    def setUp(self):
        # pylint: disable=not-callable
        self._tempdir = tempfile.mkdtemp(prefix="%s-" % self.name, dir="/var/tmp")
        self.makeDrives()
        self.remove_anaconda_logs()

        if self.environ:
            self._orig_environ = copy.deepcopy(os.environ)
            os.environ.update(self.environ)     # pylint: disable=environment-modify


    def tearDown(self):
        if self._orig_environ:
            os.environ = copy.deepcopy(self._orig_environ)
            self._orig_environ = {}

        self.die()
        self.collect_logs()
        self.cleanup()

    def collect_logs(self):
        try:
            NOSE_RESULTS_DIR = os.path.join(testconfig.config.get("resultsdir", "./"), self.name)
            if not os.path.isdir(NOSE_RESULTS_DIR):
                os.makedirs(NOSE_RESULTS_DIR)

            if self.test_result and (not self.test_result.wasSuccessful()):
                with open(NOSE_RESULTS_DIR + "/unittest-failures.log", "w") as f:
                    for (where, what) in self.test_result.errors + self.test_result.failures:
                        f.write(str(where) + "\n" + str(what) + "\n")
                    f.close()

            for log in glob.glob("/tmp/*.log"):
                shutil.copy(log, NOSE_RESULTS_DIR)

            if os.path.exists("/tmp/memory.dat"):
                shutil.copy("/tmp/memory.dat", NOSE_RESULTS_DIR)

            # anaconda writes out traceback files with restricted permissions, so
            # we have to go out of our way to grab them.
            for tb in glob.glob("/tmp/anaconda-tb-*"):
                os.system("sudo cp " + tb + " " + NOSE_RESULTS_DIR)
        except:     # pylint: disable=bare-except
            # If anything went wrong with the above, log it and quit
            with open(NOSE_RESULTS_DIR + "/unittest-failures.log", "w+") as f:
                traceback.print_exc(file=f)
                f.close()

    def cleanup(self):
        """Remove all disk images used during this test case and the temporary
           directory they were stored in.
        """
        shutil.rmtree(self._tempdir, ignore_errors=True)
        self.remove_anaconda_logs()

    def remove_anaconda_logs(self):
        try:
            for f in glob.glob("/tmp/*.log"):
                os.remove(f)
            for f in glob.glob("/tmp/anaconda-tb-*"):
                os.remove(f)
            os.remove("/tmp/memory.dat")
        except OSError:
            pass


    def die(self, terminate=False):
        """Kill any running process previously started by this test."""
        if self._proc:
            if terminate:
                self._proc.terminate()

            # Tests will click the Reboot or Quit button which will shutdown anaconda.
            # We need to make sure /mnt/sysimage/* are unmounted and device mapper devices
            # are removed before starting the next test.
            subprocess.call(["%s/scripts/anaconda-cleanup" % os.environ.get("top_srcdir", ".")],
                            stderr=subprocess.STDOUT)

            self._proc.kill()
            self._proc = None
            try:
                os.remove('/var/run/anaconda.pid')
            except OSError:
                pass

    def makeDrives(self):
        """Create all hard drive images associated with this test.  Images
           must be listed in self.drives and will be stored in a temporary
           directory this method creates.  It is up to the caller to remove
           everything later by calling self.cleanup().
        """
        for (drive, size) in self.drives:
            (fd, diskimage) = tempfile.mkstemp(dir=self._tempdir, prefix="%s_" % drive, suffix=".img")
            os.close(fd)

            # For now we are using qemu-img to create these files but specifying
            # sizes in blivet Size objects.  Unfortunately, qemu-img wants sizes
            # as xM or xG, not xMB or xGB.  That's what the conversion here is for.
            subprocess.call(["/usr/bin/qemu-img", "create", "-f", "raw", diskimage, "%sM" % size.convert_to(MiB)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                            )
            self._drivePaths[drive] = diskimage

    def runTest(self):
        if not self.tests:
            return

        args = ["%s/anaconda.py" % os.environ.get("top_srcdir", ""), "-G"]
        for drive in self._drivePaths.values():
            args += ["--image", drive]

        # Save a reference to the running anaconda process so we can later kill
        # it if necessary.  For now, the only reason we'd want to kill it is
        # an expired timer.
        self._proc = subprocess.Popen(args) # starts anaconda
        doDelay(10) # wait for anaconda to initialize

        try:
            self.test_result = unittest.TextTestRunner(verbosity=2, failfast=True).run(self.suite)
            if not self.test_result.wasSuccessful():
                raise AssertionError('Dogtail tests failed')
        except (TimedOutException, AssertionError):
            self.die(True)
            self.collect_logs()
            self.cleanup()
            raise
        finally:
            self.die()
