#
# Copyright (C) 2018  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest

from pyanaconda.modules.common.structures.requirement import Requirement


class ModuleRequirementsTestCase(unittest.TestCase):
    """Test the module requirements."""

    def test_package_requirement(self):
        requirement = Requirement.for_package("package-name", "reason")
        assert requirement.type == "package"
        assert requirement.name == "package-name"
        assert requirement.reason == "reason"

    def test_group_requirement(self):
        requirement = Requirement.for_group("group-name", "reason")
        assert requirement.type == "group"
        assert requirement.name == "group-name"
        assert requirement.reason == "reason"
