#
# Copyright (C) 2026  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import unittest
from unittest.mock import Mock, PropertyMock, create_autospec

from pyanaconda.modules.boss.completeness_manager import CompletenessManager
from pyanaconda.modules.boss.module_manager.module_observer import ModuleObserver
from pyanaconda.modules.common.constants.completeness import IncompletenessKind
from pyanaconda.modules.common.structures.completeness import IncompletenessReason


def create_observer(service_name, available=True, complete=True, mandatory=True,
                    reasons=(), failing=False):
    """Create a module observer that reports the given completeness.

    The proxy is an unconstrained mock on purpose: a dasbus proxy is
    generated from the remote interface, so there is no class to spec it
    against.

    :param service_name: a service name of the module
    :param available: is the service running?
    :param complete: the Complete property of the module
    :param mandatory: the Mandatory property of the module
    :param reasons: a list of IncompletenessReason
    :param failing: should the proxy raise when it is asked?
    :return: a mocked module observer
    """
    observer = create_autospec(ModuleObserver, instance=True)
    observer.service_name = service_name
    observer.is_service_available = available

    proxy = Mock()

    if failing:
        type(proxy).Complete = PropertyMock(side_effect=ConnectionError("No answer."))
    else:
        proxy.Complete = complete
        proxy.Mandatory = mandatory
        proxy.Incompleteness = IncompletenessReason.to_structure_list(list(reasons))

    observer.proxy = proxy
    return observer


class CompletenessManagerTestCase(unittest.TestCase):
    """Test the collection of the completeness of the modules."""

    def setUp(self):
        self.manager = CompletenessManager()

    def test_no_modules(self):
        """Test the completeness with no modules at all."""
        assert self.manager.collect_completeness() == []
        assert self.manager.collect_blocking_reasons() == []
        assert self.manager.is_ready_to_install() is True

    def test_complete_module(self):
        """Test a module that is ready to install."""
        self.manager.on_module_observers_changed([
            create_observer("org.example.A")
        ])

        reports = self.manager.collect_completeness()
        assert len(reports) == 1
        assert reports[0].service_name == "org.example.A"
        assert reports[0].complete is True
        assert reports[0].reasons == []

        assert self.manager.collect_blocking_reasons() == []
        assert self.manager.is_ready_to_install() is True

    def test_unavailable_module_is_excluded(self):
        """Test that a module that is not running cannot block anything."""
        self.manager.on_module_observers_changed([
            create_observer("org.example.A", available=False, complete=False)
        ])

        assert self.manager.collect_completeness() == []
        assert self.manager.collect_blocking_reasons() == []
        assert self.manager.is_ready_to_install() is True

    def test_incomplete_mandatory_module_blocks(self):
        """Test that an incomplete mandatory module blocks the installation."""
        reason = IncompletenessReason.for_busy("a.busy", "Working.")
        self.manager.on_module_observers_changed([
            create_observer("org.example.A", complete=False, reasons=[reason])
        ])

        assert self.manager.is_ready_to_install() is False

        blocking = self.manager.collect_blocking_reasons()
        assert len(blocking) == 1
        assert blocking[0].id == "a.busy"
        assert blocking[0].kind == IncompletenessKind.BUSY
        assert blocking[0].module_name == "org.example.A"

    def test_incomplete_optional_module_does_not_block(self):
        """Test that an incomplete optional module does not block anything."""
        reason = IncompletenessReason.for_unconfigured("a.unset", "Unset.")
        self.manager.on_module_observers_changed([
            create_observer(
                "org.example.A", complete=False, mandatory=False, reasons=[reason]
            )
        ])

        reports = self.manager.collect_completeness()
        assert len(reports) == 1
        assert reports[0].complete is False

        assert self.manager.collect_blocking_reasons() == []
        assert self.manager.is_ready_to_install() is True

    def test_unresponsive_module_fails_closed(self):
        """Test that a module that cannot answer blocks with a reason."""
        self.manager.on_module_observers_changed([
            create_observer("org.example.A", failing=True)
        ])

        reports = self.manager.collect_completeness()
        assert len(reports) == 1
        assert reports[0].complete is False
        assert reports[0].mandatory is True

        blocking = self.manager.collect_blocking_reasons()
        assert len(blocking) == 1
        assert blocking[0].kind == IncompletenessKind.INVALID
        assert blocking[0].id == "boss.module-unresponsive"
        assert blocking[0].module_name == "org.example.A"
        assert "org.example.A" in blocking[0].message

    def test_reasons_are_aggregated_from_all_modules(self):
        """Test that the blocking reasons name the module that reported them."""
        self.manager.on_module_observers_changed([
            create_observer("org.example.A", complete=True),
            create_observer(
                "org.example.B",
                complete=False,
                reasons=[IncompletenessReason.for_busy("b.busy", "Working.")],
            ),
            create_observer(
                "org.example.C",
                complete=False,
                reasons=[
                    IncompletenessReason.for_unconfigured("c.unset", "Unset."),
                    IncompletenessReason.for_invalid("c.wrong", "Wrong."),
                ],
            ),
        ])

        assert self.manager.is_ready_to_install() is False

        blocking = self.manager.collect_blocking_reasons()
        assert [(r.module_name, r.id) for r in blocking] == [
            ("org.example.B", "b.busy"),
            ("org.example.C", "c.unset"),
            ("org.example.C", "c.wrong"),
        ]
