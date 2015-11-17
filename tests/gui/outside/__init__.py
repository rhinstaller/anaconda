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
#
# Author: Chris Lumens <clumens@redhat.com>

# Ignore any interruptible calls
# pylint: disable=interruptible-system-call
# pylint: disable=ignorable-system-call

__all__ = ["Creator", "OutsideMixin"]

from blivet.size import MiB

from contextlib import contextmanager
from nose.plugins.multiprocess import TimedOutException
import os
import time
import shutil
import subprocess
import tempfile
import unittest

class DogtailTestCase(unittest.TestCase):
    """A Creator subclass defines all the parameters for starting a local
       copy of anaconda, inspecting results, and managing temporary data.

       Most Creator subclasses will only need to define the following four
       attributes:

       drives       -- A list of tuples describing disk images to create.  Each
                       tuple is the name of the drive and its size as a blivet.Size.
       environ      -- A dictionary of environment variables that should be added
                       to the environment the test suite will run under.
       name         -- A unique string that names a Creator.  This name will
                       be used in creating the results directory (and perhaps
                       other places in the future) so make sure it doesn't
                       conflict with another object.
       tests        -- A list of tuples describing which test cases make up
                       this test.  Each tuple is the name of the module
                       containing the test case (minus the leading "inside."
                       and the name of the test case class.  Tests will be
                       run in the order provided.
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

        # add tests for each spoke
        self.suite = unittest.TestSuite()
        for test in self.tests:
            self.suite.addTest(test())
        self.test_result = None

    def setUp(self):
        # pylint: disable=not-callable
        self.makeDrives()


    def tearDown(self):
        self.collect_logs()
        self.die()
        self.cleanup()

    def collect_logs(self):
        try:
            NOSE_RESULTS_DIR = os.environ.get("NOSE_RESULTS_DIR", "./")
            if self.test_result and (not self.test_result.wasSuccessful()):
                with open(NOSE_RESULTS_DIR + "/unittest-failures.log", "w") as f:
                    for (where, what) in result.errors + result.failures:
                        f.write(str(where) + "\n" + str(what) + "\n")
                    f.close()

            for log in glob.glob("/tmp/*.log"):
                shutil.copy(log, NOSE_RESULTS_DIR)

            if os.path.exists("/tmp/memory.dat"):
                shutil.copy("/tmp/memory.dat", NOSE_RESULTS_DIR)
#todo: maybe clean everything in /tmp before running anaconda b/c it looks like
# logs are appended to, not overwritten

            # anaconda writes out traceback files with restricted permissions, so
            # we have to go out of our way to grab them.
            for tb in glob.glob("/tmp/anaconda-tb-*"):
                os.system("sudo cp " + tb + " " + NOSE_RESULTS_DIR)
        except:
            # If anything went wrong with the above, log it and quit
            with open(NOSE_RESULTS_DIR + "/unittest-failures.log", "w+") as f:
                traceback.print_exc(file=f)
                f.close()

    def cleanup(self):
        """Remove all disk images used during this test case and the temporary
           directory they were stored in.
        """
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def die(self):
        """Kill any running qemu process previously started by this test."""
        if self._proc:
            self._proc.kill()
            self._proc = None

    def makeDrives(self):
        """Create all hard drive images associated with this test.  Images
           must be listed in self.drives and will be stored in a temporary
           directory this method creates.  It is up to the caller to remove
           everything later by calling self.cleanup().
        """
        for (drive, size) in self.drives:
            (fd, diskimage) = tempfile.mkstemp(dir=self.tempdir, prefix="%s_" % drive, suffix=".img")
            os.close(fd)

            # For now we are using qemu-img to create these files but specifying
            # sizes in blivet Size objects.  Unfortunately, qemu-img wants sizes
            # as xM or xG, not xMB or xGB.  That's what the conversion here is for.
            subprocess.call(["/usr/bin/qemu-img", "create", "-f", "raw", diskimage, "%sM" % size.convertTo(MiB)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                            )
            self._drivePaths[drive] = diskimage

    def runTest(self):
        from testconfig import config

        args = ["%s/anaconda" % os.environ.get("top_srcdir", ""), "-G"]
        for drive in self._drivePaths.values():
        args += ["--image", drive]
        args += config.get("anacondaArgs", "").strip('"')

        print("***** args", args, self.__class__)

        # Save a reference to the running anaconda process so we can later kill
        # it if necessary.  For now, the only reason we'd want to kill it is
        # an expired timer.
        self._proc = subprocess.Popen(args) # starts anaconda
        time.sleep(10) # wait for anaconda to initialize

        try:
            self.test_result = unittest.TextTestRunner(verbosity=2, failfast=True).run(self.suite)
            self._proc.wait() # wait for anaconda
        except TimedOutException:
            self.die()
            self.cleanup()
            raise
        finally:
            self._proc = None

    @property
    def tempdir(self):
        """The temporary directory used to store disk images and other data
           this test requires.  This directory will be removed by self.cleanup().
           It is up to the caller to call that method, though.
        """
        if not self._tempdir:
            self._tempdir = tempfile.mkdtemp(prefix="%s-" % self.name, dir="/var/tmp")

        return self._tempdir
