#
# Copyright (C) 2025  Red Hat, Inc.
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

from dasbus.typing import Str, get_variant

from pyanaconda.core.constants import SOURCE_TYPE_BOOTC
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_BOOTC
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.bootc.bootc import (
    BootcSourceModule,
)
from pyanaconda.modules.payloads.source.bootc.bootc_interface import (
    BootcSourceInterface,
)
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class BootcInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the Bootc source."""

    def setUp(self):
        self.module = BootcSourceModule()
        self.interface = BootcSourceInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_BOOTC,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Test the Type property."""
        assert self.interface.Type == SOURCE_TYPE_BOOTC

    def test_description(self):
        """Test the Description property."""
        assert self.interface.Description == "Bootc"

    def test_configuration(self):
        """Test the configuration property."""
        data = {
            "stateroot": get_variant(Str, "default"),
            "sourceImgRef": get_variant(Str, "registry:quay.io/fedora-testing/fedora-bootc:rawhide-standard"),
            "targetImgRef": get_variant(Str, "registry:quay.io/fedora-testing/fedora-bootc:rawhide-standard")
        }

        self._check_dbus_property(
            "Configuration",
            data
        )


class BootcSourceTestCase(unittest.TestCase):
    """Test the Bootc source module."""

    def setUp(self):
        self.module = BootcSourceModule()

    def test_type(self):
        """Test the type property."""
        assert self.module.type == SourceType.BOOTC

    def test_network_required(self):
        """Test the network_required property."""
        assert self.module.network_required is True

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
            "type='BOOTC', "
            "stateroot='', "
            "sourceImgRef='', "
            "targetImgRef=''"
            ")"
        )

        self.module.configuration.stateroot = "default"
        self.module.configuration.sourceImgRef = "registry:quay.io/fedora-testing/fedora-bootc:rawhide-standard"
        self.module.configuration.targetImgRef = "registry:quay.io/fedora-testing/fedora-bootc:rawhide-newest"

        assert repr(self.module) == str(
            "Source("
            "type='BOOTC', "
            "stateroot='default', "
            "sourceImgRef='registry:quay.io/fedora-testing/fedora-bootc:rawhide-standard', "
            "targetImgRef='registry:quay.io/fedora-testing/fedora-bootc:rawhide-newest'"
            ")"
        )
