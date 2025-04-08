#
# Copyright (C) 2021  Red Hat, Inc.
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
import pytest

from dasbus.typing import get_variant, Int
from pyanaconda.modules.common.structures.policy import PasswordPolicy


class PasswordPolicyTestCase(unittest.TestCase):
    """Test the module requirements."""

    def test_default_known_policy(self):
        """Test the default policy data."""
        policy = PasswordPolicy.from_defaults("root")
        assert policy.min_quality == 1
        assert policy.min_length == 6
        assert policy.allow_empty is False
        assert policy.is_strict is False

    def test_default_unknown_policy(self):
        """Test the default policy data for unknown policy."""
        policy = PasswordPolicy.from_defaults("test")
        assert policy.min_quality == 0
        assert policy.min_length == 0
        assert policy.allow_empty is True
        assert policy.is_strict is False

    def test_to_structure_dict(self):
        """Test the to_structure_dict method."""
        p1 = PasswordPolicy()
        p1.quality = 1

        p2 = PasswordPolicy()
        p2.quality = 2

        p3 = PasswordPolicy()
        p3.quality = 3

        # Test an invalid argument.
        with pytest.raises(TypeError):
            PasswordPolicy.to_structure_dict([])

        # Test a valid argument.
        structures = PasswordPolicy.to_structure_dict({
            "p1": p1, "p2": p2, "p3": p3
        })

        assert structures == {
            "p1": PasswordPolicy.to_structure(p1),
            "p2": PasswordPolicy.to_structure(p2),
            "p3": PasswordPolicy.to_structure(p3),
        }

    def test_from_structure_dict(self):
        """Test the from_structure_dict method."""
        s1 = {"min-quality": get_variant(Int, 1)}
        s2 = {"min-quality": get_variant(Int, 2)}
        s3 = {"min-quality": get_variant(Int, 3)}

        # Test an invalid argument.
        with pytest.raises(TypeError):
            PasswordPolicy.from_structure_dict([])

        # Test a valid argument.
        objects = PasswordPolicy.from_structure_dict({
            "s1": s1, "s2": s2, "s3": s3
        })

        assert objects.keys() == {"s1", "s2", "s3"}
        assert objects["s1"].min_quality == 1
        assert objects["s2"].min_quality == 2
        assert objects["s3"].min_quality == 3
