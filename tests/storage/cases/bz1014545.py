#!/usr/bin/python
#
# Copyright (C) 2013-2014  Red Hat, Inc.
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

from . import TestCase, TestCaseComponent

from blivet.size import Size
from pykickstart.errors import KickstartValueError

class BTRFSOnNonBTRFSComponent(TestCaseComponent):
    name = "BTRFSOnNonBTRFS"

    def __init__(self, *args, **kwargs):
        TestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("anatest-disk1", Size("1GiB"))]

    @property
    def ks(self):
        return """
zerombr
clearpart --all --initlabel
btrfs none --data=0 --metadata=1 anatest-disk1
"""

    @property
    def expectedExceptionType(self):
        return KickstartValueError

    @property
    def expectedExceptionText(self):
        return "BTRFS partition .* has incorrect format"

class VolGroupOnNonPVsComponent(TestCaseComponent):
    name = "VolGroupOnNonPVs"

    def __init__(self, *args, **kwargs):
        TestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("anatest-disk1", Size("1GiB"))]

    @property
    def ks(self):
        return """
zerombr
clearpart --all --initlabel
volgroup myvg anatest-disk1
"""

    @property
    def expectedExceptionType(self):
        return KickstartValueError

    @property
    def expectedExceptionText(self):
        return "Physical Volume .* has incorrect format"

class RaidOnNonRaidMembersComponent(TestCaseComponent):
    name = "RaidOnNonRaidMembers"

    def __init__(self, *args, **kwargs):
        TestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("anatest-disk1", Size("1GiB")),
                              ("anatest-disk2", Size("1GiB"))]

    @property
    def ks(self):
        return """
zerombr
clearpart --all --initlabel
raid / --level=1 --device=md0 anatest-disk1 anatest-disk2
"""

    @property
    def expectedExceptionType(self):
        return KickstartValueError

    @property
    def expectedExceptionText(self):
        return "RAID member .* has incorrect format"

class BZ1014545_TestCase(TestCase):
    components = [BTRFSOnNonBTRFSComponent,
                  RaidOnNonRaidMembersComponent,
                  VolGroupOnNonPVsComponent]
    name = "1014545"
    desc = """The members of various commands must have the correct format.
For instance, raid members must have mdmember, and volgroup members must have
lvmpv.  If they do not have this format, a KickstartValueError should be raised
during storage execution time.

Note that this is different from the error condition described in the bug.
There, anaconda was letting the invalid format go and then hitting errors
much further in installation - during bootloader installation.  The real
bug is that this condition should be detected when the kickstart storage
commands are being converted to actions.
"""
