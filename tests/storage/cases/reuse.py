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

__all__ = ["PartitionReuse_TestCase", "LVMReuse_TestCase", "BTRFSReuse_TestCase", "ThinpReuse_TestCase"]

from . import TestCase, ReusableTestCaseComponent, ReusingTestCaseComponent
from blivet.size import Size

class FirstPartitionAutopartComponent(ReusableTestCaseComponent):
    name = "FirstPartitionAutopart"

    def __init__(self, *args, **kwargs):
        ReusableTestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("part-autopart-disk1", Size("8GiB"))]

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
autopart --type=plain
"""

class SecondPartitionAutopartComponent(ReusingTestCaseComponent):
    name = "SecondPartitionAutopart"

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
autopart --type=plain
"""

class PartitionReuse_TestCase(TestCase):
    name = "PartitionReuse"
    desc = """Test that a disk with pre-existing partitioning as a
result of a previous installation with partition-based autopart works.
"""

    def __init__(self):
        TestCase.__init__(self)
        first = FirstPartitionAutopartComponent()
        second = SecondPartitionAutopartComponent(reusedComponents=[first])

        self.components = [first, second]

class FirstLVMAutopartComponent(ReusableTestCaseComponent):
    name = "FirstLVMAutopart"

    def __init__(self, *args, **kwargs):
        ReusableTestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("lvm-autopart-disk1", Size("8GiB"))]

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
autopart --type=lvm
"""

class SecondLVMAutopartComponent(ReusingTestCaseComponent):
    name = "SecondLVMAutopart"

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
autopart --type=lvm
"""

class LVMReuse_TestCase(TestCase):
    name = "LVMReuse"
    desc = """Test that a disk with pre-existing LVM partitioning as a
result of a previous installation with LVM-based autopart works.
"""

    def __init__(self):
        TestCase.__init__(self)
        first = FirstLVMAutopartComponent()
        second = SecondLVMAutopartComponent(reusedComponents=[first])

        self.components = [first, second]

class FirstBTRFSAutopartComponent(ReusableTestCaseComponent):
    name = "FirstBTRFSAutopart"

    def __init__(self, *args, **kwargs):
        ReusableTestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("btrfs-autopart-disk1", Size("8GiB"))]

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
autopart --type=btrfs
"""

class SecondBTRFSAutopartComponent(ReusingTestCaseComponent):
    name = "SecondBTRFSAutopart"

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
autopart --type=btrfs
"""

class BTRFSReuse_TestCase(TestCase):
    name = "BTRFSReuse"
    desc = """Test that a disk with pre-existing BTRFS partitioning as a
result of a previous installation with BTRFS-based autopart works.
"""

    def __init__(self):
        TestCase.__init__(self)
        first = FirstBTRFSAutopartComponent()
        second = SecondBTRFSAutopartComponent(reusedComponents=[first])

        self.components = [first, second]

class FirstThinpAutopartComponent(ReusableTestCaseComponent):
    name = "FirstThinpAutopart"

    def __init__(self, *args, **kwargs):
        ReusableTestCaseComponent.__init__(self, *args, **kwargs)
        self.disksToCreate = [("thinp-autopart-disk1", Size("8GiB"))]

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
autopart --type=thinp
"""

class SecondThinpAutopartComponent(ReusingTestCaseComponent):
    name = "SecondThinpAutopart"

    @property
    def ks(self):
        return """
bootloader --location=none
zerombr
clearpart --all --initlabel
autopart --type=thinp
"""

class ThinpReuse_TestCase(TestCase):
    name = "ThinpReuse"
    desc = """Test that a disk with pre-existing thinp partitioning as a
result of a previous installation with thinp autopart works.
"""

    def __init__(self):
        TestCase.__init__(self)
        first = FirstThinpAutopartComponent()
        second = SecondThinpAutopartComponent(reusedComponents=[first])

        self.components = [first, second]
