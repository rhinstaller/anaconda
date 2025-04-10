#
# Copyright (C) 2020  Red Hat, Inc.
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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#

import unittest

from pyanaconda.ui.gui.spokes.lib.subscription import handle_user_provided_value


class SubscriptionSpokeHelpersTestCase(unittest.TestCase):
    """Test the helper functions of the Subscription spoke."""

    def test_handle_user_provided_value(self):
        """Test the handle_user_provided_value() helper function."""
        valid_values = ["Self Support", "Standard", "Premium"]
        # user provided value matches one of the valid values
        expected_output = [("Self Support", "Self Support", False),
                           ("Standard", "Standard", True),
                           ("Premium", "Premium", False)]
        output = handle_user_provided_value("Standard", valid_values)
        assert output == expected_output
        # user provided value does not match one of the valid values
        expected_output = [("Self Support", "Self Support", False),
                           ("Standard", "Standard", False),
                           ("Premium", "Premium", False),
                           ("Custom", "Other (Custom)", True)]
        output = handle_user_provided_value("Custom", valid_values)
        assert output == expected_output
        # user provided empty string
        expected_output = [("Self Support", "Self Support", False),
                           ("Standard", "Standard", False),
                           ("Premium", "Premium", False)]
        output = handle_user_provided_value("", valid_values)
        assert output == expected_output
