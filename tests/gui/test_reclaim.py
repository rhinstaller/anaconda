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

from tests.gui import base, welcome, summary, storage, progress, rootpassword
import subprocess

from blivet.size import Size

class BasicReclaimTestCase(base.DogtailTestCase):
    drives = [("one", Size("8 GiB"))]
    name = "basicreclaim"

    # This does not test every spoke, as we only need to do enough to satisfy anaconda
    # and get us onto the progress hub.
    tests = [welcome.BasicWelcomeTestCase,
             summary.SummaryTestCase,
             storage.BasicReclaimTestCase,
             progress.ProgressTestCase,
             rootpassword.BasicRootPasswordTestCase,
             progress.FinishTestCase]

    def makeDrives(self):
        base.DogtailTestCase.makeDrives(self)

        # Put a partition and filesystem across the whole disk, which will
        # force anaconda to display the reclaim dialog.
        for (drive, size) in self.drives:
            subprocess.call(["/sbin/parted", "-s", self._drivePaths[drive], "mklabel", "msdos"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            subprocess.call(["/sbin/parted", "-s", self._drivePaths[drive], "mkpart", "p", "ext2", "0", str(size)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            subprocess.call(["/sbin/mkfs.ext4", "-F", self._drivePaths[drive]],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

class CantReclaimTestCase(base.DogtailTestCase):
    drives = [("one", Size("1 GiB"))]
    name = "cantreclaim"

    # We don't get to test much here, since the reclaim test shuts down anaconda.
    tests = [welcome.BasicWelcomeTestCase,
             summary.SummaryTestCase,
             storage.CantReclaimTestCase]
