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

from pyanaconda.modules.common.base import KickstartModuleInterface, KickstartService
from pyanaconda.modules.common.base.base import KickstartBaseModule
from pyanaconda.modules.common.constants.completeness import IncompletenessKind
from pyanaconda.modules.common.constants.interfaces import KICKSTART_MODULE
from pyanaconda.modules.common.structures.completeness import (
    IncompletenessReason,
    ModuleCompleteness,
)
from tests.unit_tests.pyanaconda_tests import PropertiesChangedCallback


class IncompletenessReasonTestCase(unittest.TestCase):
    """Test the IncompletenessReason structure."""

    def test_default_values(self):
        """Test the default values of a reason."""
        reason = IncompletenessReason()
        assert reason.kind == ""
        assert reason.id == ""
        assert reason.message == ""
        assert reason.context == ""
        assert reason.module_name == ""

    def test_factories(self):
        """Test the factory methods for the three kinds."""
        busy = IncompletenessReason.for_busy("a.busy", "Working.")
        assert busy.kind == IncompletenessKind.BUSY
        assert busy.id == "a.busy"
        assert busy.message == "Working."

        unconfigured = IncompletenessReason.for_unconfigured("a.unset", "Unset.")
        assert unconfigured.kind == IncompletenessKind.UNCONFIGURED

        invalid = IncompletenessReason.for_invalid("a.wrong", "Wrong.", "a-screen")
        assert invalid.kind == IncompletenessKind.INVALID
        assert invalid.context == "a-screen"

    def test_structure_round_trip(self):
        """Test that a reason survives a conversion to a DBus structure."""
        reason = IncompletenessReason.for_busy("a.busy", "Working.", "a-screen")
        reason.module_name = "org.example.Module"

        result = IncompletenessReason.from_structure(
            IncompletenessReason.to_structure(reason)
        )

        assert result.kind == IncompletenessKind.BUSY
        assert result.id == "a.busy"
        assert result.message == "Working."
        assert result.context == "a-screen"
        assert result.module_name == "org.example.Module"


class ModuleCompletenessTestCase(unittest.TestCase):
    """Test the ModuleCompleteness structure."""

    def test_default_values(self):
        """Test the default values of a report."""
        report = ModuleCompleteness()
        assert report.service_name == ""
        assert report.complete is True
        assert report.mandatory is True
        assert report.reasons == []

    def test_structure_round_trip(self):
        """Test that nested reasons survive a conversion to a structure."""
        report = ModuleCompleteness()
        report.service_name = "org.example.Module"
        report.complete = False
        report.mandatory = False
        report.reasons = [IncompletenessReason.for_invalid("a.wrong", "Wrong.")]

        result = ModuleCompleteness.from_structure(
            ModuleCompleteness.to_structure(report)
        )

        assert result.service_name == "org.example.Module"
        assert result.complete is False
        assert result.mandatory is False
        assert len(result.reasons) == 1
        assert result.reasons[0].id == "a.wrong"


class ModuleWithReasons(KickstartBaseModule):
    """A module whose completeness is driven by the test."""

    def __init__(self):
        super().__init__()
        self.reasons = []

    @property
    def incompleteness(self):
        return self.reasons


class CompletenessDefaultsTestCase(unittest.TestCase):
    """Test the completeness defaults of a kickstart module."""

    def test_defaults(self):
        """Test that a module is complete and mandatory by default."""
        module = KickstartBaseModule()
        assert module.complete is True
        assert module.mandatory is True
        assert module.incompleteness == []

    def test_complete_follows_the_reasons(self):
        """Test that Complete is derived from the reasons."""
        module = ModuleWithReasons()
        assert module.complete is True

        module.reasons = [IncompletenessReason.for_busy("a.busy", "Working.")]
        assert module.complete is False


class CompletenessNotificationTestCase(unittest.TestCase):
    """Test the re-publishing of the completeness."""

    def setUp(self):
        self.module = ModuleWithReasons()
        self.emitted = 0
        self.module.completeness_changed.connect(self._on_change)

    def _on_change(self):
        self.emitted += 1

    def test_notify_on_a_real_change(self):
        """Test that a changed completeness is published."""
        self.module.seed_completeness()

        self.module.reasons = [IncompletenessReason.for_busy("a.busy", "Working.")]
        self.module.notify_completeness_changed()
        assert self.emitted == 1

    def test_no_notify_without_a_change(self):
        """Test that an unchanged completeness is not published."""
        self.module.seed_completeness()

        self.module.notify_completeness_changed()
        assert self.emitted == 0

    def test_no_notify_for_an_equivalent_reason(self):
        """Test that an equal but distinct reason is not published."""
        self.module.reasons = [IncompletenessReason.for_busy("a.busy", "Working.")]
        self.module.seed_completeness()

        self.module.reasons = [IncompletenessReason.for_busy("a.busy", "Working.")]
        self.module.notify_completeness_changed()
        assert self.emitted == 0


class ServiceWithReasons(KickstartService):
    """A service whose completeness is driven by the test."""

    def __init__(self):
        super().__init__()
        self.reasons = []

    @property
    def incompleteness(self):
        return self.reasons


class CompletenessInterfaceTestCase(unittest.TestCase):
    """Test the completeness on the DBus interface of a module."""

    def setUp(self):
        self.service = ServiceWithReasons()
        self.interface = KickstartModuleInterface(self.service)

        self.callback = PropertiesChangedCallback()
        self.interface.PropertiesChanged.connect(self.callback)

    def test_default_properties(self):
        """Test the properties of a complete module."""
        assert self.interface.Complete is True
        assert self.interface.Mandatory is True
        assert self.interface.Incompleteness == []

    def test_reported_reasons(self):
        """Test the properties of an incomplete module."""
        self.service.reasons = [
            IncompletenessReason.for_invalid("a.wrong", "Wrong.", "a-screen")
        ]

        assert self.interface.Complete is False
        assert IncompletenessReason.from_structure_list(
            self.interface.Incompleteness
        )[0].id == "a.wrong"

    def test_changed_properties_are_published(self):
        """Test that a changed completeness is published on the bus."""
        self.service.seed_completeness()
        self.service.reasons = [IncompletenessReason.for_busy("a.busy", "Working.")]
        self.service.notify_completeness_changed()

        self.callback.assert_called_once_with(
            KICKSTART_MODULE.interface_name,
            {
                "Complete": False,
                "Mandatory": True,
                "Incompleteness": [{
                    "kind": "busy",
                    "id": "a.busy",
                    "message": "Working.",
                    "context": "",
                    "module-name": "",
                }],
            },
            []
        )

    def test_unchanged_properties_are_not_published(self):
        """Test that nothing is published without a change."""
        self.service.seed_completeness()
        self.service.notify_completeness_changed()

        self.callback.assert_not_called()
