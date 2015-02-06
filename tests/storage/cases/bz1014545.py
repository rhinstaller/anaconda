#!/usr/bin/python2
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

__all__ = ["BZ1014545_TestCase"]

from . import TestCase, TestCaseComponent

from blivet.size import Size
from pykickstart.errors import KickstartValueError

class BTRFSOnNonBTRFSComponent(TestCaseComponent):
    name = "BTRFSOnNonBTRFS"

    def __init__(self, *args, **kwargs):
        TestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("btrfs-on-non-btrfs-disk1", Size("1GiB"))]

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
btrfs none --data=0 --metadata=1 btrfs-on-non-btrfs-disk1
"""

    @property
    def expectedExceptionType(self):
        return KickstartValueError

    @property
    def expectedExceptionText(self):
        return "Btrfs partition .* has a format of \"disklabel\", but should have a format of \"btrfs\""

class VolGroupOnNonPVsComponent(TestCaseComponent):
    name = "VolGroupOnNonPVs"

    def __init__(self, *args, **kwargs):
        TestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("volgroup-on-non-pv-disk1", Size("1GiB"))]

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
volgroup myvg volgroup-on-non-pv-disk1
"""

    @property
    def expectedExceptionType(self):
        return KickstartValueError

    @property
    def expectedExceptionText(self):
        return "Physical volume .* has a format of \"disklabel\", but should have a format of \"lvmpv\""

class RaidOnNonRaidMembersComponent(TestCaseComponent):
    name = "RaidOnNonRaidMembers"

    def __init__(self, *args, **kwargs):
        TestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("raid-on-non-raid-disk1", Size("1GiB")),
                              ("raid-on-non-raid-disk2", Size("1GiB"))]

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
raid / --level=1 --device=md0 raid-on-non-raid-disk1 raid-on-non-raid-disk2
"""

    @property
    def expectedExceptionType(self):
        return KickstartValueError

    @property
    def expectedExceptionText(self):
        return "RAID device .* has a format of \"disklabel\", but should have a format of \"mdmember\""

class BZ1014545_TestCase(TestCase):
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

    def __init__(self):
        TestCase.__init__(self)
        self.components = [BTRFSOnNonBTRFSComponent(),
                           RaidOnNonRaidMembersComponent(),
                           VolGroupOnNonPVsComponent()]
