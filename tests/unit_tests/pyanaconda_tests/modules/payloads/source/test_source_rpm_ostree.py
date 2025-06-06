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
import unittest

from dasbus.typing import Bool, Str, get_variant

from pyanaconda.core.constants import SOURCE_TYPE_RPM_OSTREE
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_RPM_OSTREE
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.rpm_ostree.rpm_ostree import (
    RPMOSTreeSourceModule,
)
from pyanaconda.modules.payloads.source.rpm_ostree.rpm_ostree_interface import (
    RPMOSTreeSourceInterface,
)
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class OSTreeSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the OSTree source."""

    def setUp(self):
        self.module = RPMOSTreeSourceModule()
        self.interface = RPMOSTreeSourceInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_RPM_OSTREE,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Test the Type property."""
        assert self.interface.Type == SOURCE_TYPE_RPM_OSTREE

    def test_description(self):
        """Test the Description property."""
        assert self.interface.Description == "RPM OSTree"

    def test_configuration(self):
        """Test the configuration property."""
        data = {
            "osname": get_variant(Str, "fedora-atomic"),
            "remote": get_variant(Str, "fedora-atomic-28"),
            "url": get_variant(Str, "https://kojipkgs.fedoraproject.org/atomic/repo"),
            "ref": get_variant(Str, "fedora/28/x86_64/atomic-host"),
            "gpg-verification-enabled": get_variant(Bool, False)
        }

        self._check_dbus_property(
            "Configuration",
            data
        )


class OSTreeSourceTestCase(unittest.TestCase):
    """Test the OSTree source module."""

    def setUp(self):
        self.module = RPMOSTreeSourceModule()

    def test_type(self):
        """Test the type property."""
        assert self.module.type == SourceType.RPM_OSTREE

    def test_network_required(self):
        """Test the network_required property."""
        assert self.module.network_required is False

        self.module.configuration.url = "file://my/path"
        assert self.module.network_required is False

        self.module.configuration.url = "http://my/path"
        assert self.module.network_required is True

        self.module.configuration.url = "https://my/path"
        assert self.module.network_required is True

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 500000000

    def test_get_state(self):
        """Test the source state."""
        assert self.module.get_state() == SourceState.NOT_APPLICABLE

    def test_set_up_with_tasks(self):
        """Test the set-up tasks."""
        assert self.module.set_up_with_tasks() == []

    def test_tear_down_with_tasks(self):
        """Test the tear-down tasks."""
        assert self.module.tear_down_with_tasks() == []

    def test_repr(self):
        """Test the string representation."""
        assert repr(self.module) == str(
            "Source("
            "type='RPM_OSTREE', "
            "osname='', "
            "url=''"
            ")"
        )

        self.module.configuration.osname = "fedora-atomic"
        self.module.configuration.url = "https://kojipkgs.fedoraproject.org/atomic/repo"

        assert repr(self.module) == str(
            "Source("
            "type='RPM_OSTREE', "
            "osname='fedora-atomic', "
            "url='https://kojipkgs.fedoraproject.org/atomic/repo'"
            ")"
        )
