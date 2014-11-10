#!/usr/bin/python
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

__all__ = ["BasicReclaimLiveCDCreator", "BasicReclaimLiveCD_OutsideTest"]

from . import Creator, OutsideMixin
import subprocess
import unittest

class BasicReclaimLiveCDCreator(Creator):
    drives = [("one", 8)]
    name = "basicreclaimlivecd"

    # This does not test every spoke, as we only need to do enough to satisfy anaconda
    # and get us onto the progress hub.
    tests = [("welcome", "BasicWelcomeTestCase"),
             ("summary", "LiveCDSummaryTestCase"),
             ("storage", "BasicReclaimTestCase"),
             ("progress", "LiveCDProgressTestCase"),
             ("rootpassword", "BasicRootPasswordTestCase"),
             ("progress", "LiveCDFinishTestCase")]

    def makeDrives(self):
        Creator.makeDrives(self)

        # Put a partition and filesystem across the whole disk, which will
        # force anaconda to display the reclaim dialog.
        for (drive, size) in self.drives:
            subprocess.call(["/sbin/parted", "-s", self._drivePaths[drive], "mklabel", "msdos"],
                            stdout=open("/dev/null", "w"),
                            stderr=open("/dev/null", "w"))
            subprocess.call(["/sbin/parted", "-s", self._drivePaths[drive], "mkpart", "p", "ext2", "0", str(size) + "G"],
                            stdout=open("/dev/null", "w"),
                            stderr=open("/dev/null", "w"))
            subprocess.call(["/sbin/mkfs.ext4", "-F", self._drivePaths[drive]],
                            stdout=open("/dev/null", "w"),
                            stderr=open("/dev/null", "w"))

class BasicReclaimLiveCD_OutsideTest(OutsideMixin, unittest.TestCase):
    creatorClass = BasicReclaimLiveCDCreator
