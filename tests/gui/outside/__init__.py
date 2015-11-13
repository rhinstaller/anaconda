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
import shutil
import subprocess
import tempfile

class Creator(object):
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
    name = "Creator"
    tests = []

    def __init__(self):
        self._drivePaths = {}
        self._proc = None
        self._tempdir = None

        self._reqMemory = 1536

    def _call(self, args):
        subprocess.call(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def archive(self):
        """Copy all log files and other test results to a subdirectory of the
           given resultsdir.  If logs are no longer available, this method
           does nothing.  It is up to the caller to make sure logs are available
           beforehand and clean up afterwards.
        """
        from testconfig import config

        if not os.path.isdir(self.tempdir):
            return
#todo: fix this, use virsh copy-out to transfer files from the disk images
        shutil.copytree(self.mountpoint + "/result", config["resultsdir"] + "/" + self.name)

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
           must be listed in Creator.drives and will be stored in a temporary
           directory this method creates.  It is up to the caller to remove
           everything later by calling Creator.cleanup.
        """
        for (drive, size) in self.drives:
            (fd, diskimage) = tempfile.mkstemp(dir=self.tempdir)
            os.close(fd)

            # For now we are using qemu-img to create these files but specifying
            # sizes in blivet Size objects.  Unfortunately, qemu-img wants sizes
            # as xM or xG, not xMB or xGB.  That's what the conversion here is for.
            self._call(["/usr/bin/qemu-img", "create", "-f", "raw", diskimage, "%sM" % size.convertTo(MiB)])
            self._drivePaths[drive] = diskimage

    @property
    def template(self):
        with open("outside/template.py", "r") as f:
            return f.read()

    def makeSuite(self):
        """The suite is a special suite.py file that actually runs the test
           and a directory structure for reporting results.
        """
        from testconfig import config

        anacondaArgs = "%s/anaconda -G" % os.environ.get("top_srcdir", "")
        for drive in self._drivePaths.values():
            anacondaArgs += " --image %s " % drive
        anacondaArgs += config.get("anacondaArgs", "").strip('"')

        with open(self.suitepath, "w") as f:
            imports = map(lambda path_cls: "    from inside.%s import %s" % (path_cls[0], path_cls[1]), self.tests)
            addtests = map(lambda path_cls1: "    s.addTest(%s())" % path_cls1[1], self.tests)

            f.write(self.template % {"environ": "    os.environ.update(%s)" % self.environ,
                                     "imports": "\n".join(imports),
                                     "addtests": "\n".join(addtests),
                                     "anacondaArgs": anacondaArgs})
    def run(self):
        """Given disk images previously created by Creator.makeDrives
           start anaconda and wait for it to terminate!
        """
        from testconfig import config

#        args = ["%s/anaconda" % os.environ.get("top_srcdir", ""), "-G"]

#        for drive in self._drivePaths.values():
#            args += ["--image", drive]

        # Save a reference to the running qemu process so we can later kill
        # it if necessary.  For now, the only reason we'd want to kill it is
        # an expired timer.
#        self._proc = subprocess.Popen(args) # starts anaconda
#        time.sleep(5) # wait 5 seconds for anaconda to initialize
#todo: the test suite needs to kill anaconda if it fails prematurely

        self._proc = subprocess.Popen(["python3", self.suitepath]) # start the test suite

        try:
            self._proc.wait()
        except TimedOutException:
            self.die()
            self.cleanup()
            raise
        finally:
            self._proc = None

    @property
    def tempdir(self):
        """The temporary directory used to store disk images and other data
           this test requires.  This directory will be removed by Creator.cleanup.
           It is up to the caller to call that method, though.
        """
        if not self._tempdir:
            self._tempdir = tempfile.mkdtemp(prefix="%s-" % self.name, dir="/var/tmp")

        return self._tempdir

    @property
    def suitename(self):
        return self.name + "_suite"

    @property
    def suitepath(self):
        return self.tempdir + "/" + "suite.py"

class OutsideMixin(object):
    """A BaseOutsideTestCase subclass is the interface between the unittest framework
       and a running VM.  It interfaces with an associated Creator object to create
       devices and fire up a VM, and also handles actually reporting a result that
       unittest knows how to process.

       Each subclass will likely only want to define a single attribute:

       creatorClass -- A Creator subclass that goes with this test.
    """
    creatorClass = None

    def archive(self):
        self.creator.archive()

    def runTest(self):
        self.creator.run()

#todo: fix me
#        with self.creator.suiteMounted():
#            self.assertTrue(os.path.exists(self.creator.mountpoint + "/result"),
#                            msg="results directory does not exist")
#            self.archive()
#            self.assertFalse(os.path.exists(self.creator.mountpoint + "/result/unittest-failures"),
#                             msg="automated UI test %s failed" % self.creator.name)

    def setUp(self):
        # pylint: disable=not-callable
        self.creator = self.creatorClass()
        self.creator.makeDrives()
        self.creator.makeSuite()

    def tearDown(self):
        self.creator.cleanup()
