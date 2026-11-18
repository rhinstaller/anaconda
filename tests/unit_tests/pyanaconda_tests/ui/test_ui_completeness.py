#
# Copyright (C) 2026  Red Hat, Inc.
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
from unittest.mock import Mock

from pyanaconda.modules.common.structures.completeness import IncompletenessReason
from pyanaconda.ui.lib.completeness import (
    get_incompleteness,
    get_incompleteness_message,
    is_module_busy,
)


def create_module_proxy(reasons=()):
    """Create a module proxy that reports the given reasons.

    The proxy is an unconstrained mock on purpose: a dasbus proxy is
    generated from the remote interface, so there is no class to spec it
    against.

    :param reasons: a list of IncompletenessReason
    :return: a mocked DBus proxy of a module
    """
    proxy = Mock()
    proxy.Complete = not reasons
    proxy.Incompleteness = IncompletenessReason.to_structure_list(list(reasons))
    return proxy


class CompletenessUITestCase(unittest.TestCase):
    """Test the UI functions for the completeness of a module."""

    def test_get_incompleteness_of_a_complete_module(self):
        """Test the reasons of a module that is ready to install."""
        proxy = create_module_proxy()
        assert get_incompleteness(proxy) == []

    def test_get_incompleteness(self):
        """Test the reasons of a module that is not ready to install."""
        proxy = create_module_proxy([
            IncompletenessReason.for_unconfigured("a.unset", "Unset."),
        ])

        reasons = get_incompleteness(proxy)
        assert len(reasons) == 1
        assert reasons[0].id == "a.unset"
        assert reasons[0].message == "Unset."

    def test_a_complete_module_is_not_busy(self):
        """Test that a module with nothing to report is not busy."""
        assert is_module_busy(create_module_proxy()) is False

    def test_a_working_module_is_busy(self):
        """Test that a module with only transient reasons is busy."""
        proxy = create_module_proxy([
            IncompletenessReason.for_busy("a.busy", "Working."),
        ])

        assert is_module_busy(proxy) is True

    def test_a_misconfigured_module_is_not_busy(self):
        """Test that waiting cannot resolve a non-transient reason."""
        proxy = create_module_proxy([
            IncompletenessReason.for_busy("a.busy", "Working."),
            IncompletenessReason.for_invalid("a.wrong", "Wrong."),
        ])

        assert is_module_busy(proxy) is False

    def test_message_of_a_complete_module(self):
        """Test that a complete module has nothing to say."""
        assert get_incompleteness_message(create_module_proxy()) == ""

    def test_message_of_an_incomplete_module(self):
        """Test the message of a module that is not ready to install."""
        proxy = create_module_proxy([
            IncompletenessReason.for_unconfigured("a.unset", "Unset."),
            IncompletenessReason.for_invalid("a.wrong", "Wrong."),
        ])

        assert get_incompleteness_message(proxy) == "Unset."
