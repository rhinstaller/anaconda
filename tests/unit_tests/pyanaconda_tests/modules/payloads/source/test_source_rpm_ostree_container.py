#
# Copyright (C) 2023  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest

from pyanaconda.core.constants import SOURCE_TYPE_RPM_OSTREE_CONTAINER
from pyanaconda.modules.common.constants.interfaces import (
    PAYLOAD_SOURCE_RPM_OSTREE_CONTAINER,
)
from pyanaconda.modules.common.structures.rpm_ostree import (
    RPMOSTreeContainerConfigurationData,
)
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.rpm_ostree_container.rpm_ostree_container import (
    RPMOSTreeContainerSourceModule,
)
from pyanaconda.modules.payloads.source.rpm_ostree_container.rpm_ostree_container_interface import (
    RPMOSTreeContainerSourceInterface,
)
from tests.unit_tests.pyanaconda_tests import check_dbus_property


class OSTreeContainerSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the OSTree source."""

    def setUp(self):
        self.module = RPMOSTreeContainerSourceModule()
        self.interface = RPMOSTreeContainerSourceInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            PAYLOAD_SOURCE_RPM_OSTREE_CONTAINER,
            self.interface,
            *args, **kwargs
        )

    def test_type(self):
        """Test the Type property."""
        assert SOURCE_TYPE_RPM_OSTREE_CONTAINER == self.interface.Type

    def test_description(self):
        """Test the Description property."""
        assert "RPM OSTree Container" == self.interface.Description

    def test_configuration(self):
        """Test the configuration property."""
        data = RPMOSTreeContainerConfigurationData()
        data.stateroot = "fedora-coreos"
        data.remote = "fcos-28"
        data.transport = "registry"
        data.url = "quay.io/fedora/coreos:stable"
        data._signature_verification_enabled = False

        self._check_dbus_property(
            "Configuration",
            RPMOSTreeContainerConfigurationData.to_structure(data)
            )


class OSTreeContainerSourceTestCase(unittest.TestCase):
    """Test the OSTree source module."""

    def setUp(self):
        self.module = RPMOSTreeContainerSourceModule()

    def test_type(self):
        """Test the type property."""
        assert SourceType.RPM_OSTREE_CONTAINER == self.module.type

    def test_network_required(self):
        """Test the network_required property."""
        assert self.module.network_required is False

        data = RPMOSTreeContainerConfigurationData()

        data.transport = "oci"
        self.module.set_configuration(data)
        assert self.module.network_required is False

        data.transport = "oci-archive"
        self.module.set_configuration(data)
        assert self.module.network_required is False

        data.transport = "registry"
        self.module.set_configuration(data)
        assert self.module.network_required is True

    def test_required_space(self):
        """Test the required_space property."""
        assert self.module.required_space == 500000000

    def test_get_state(self):
        """Test the source state."""
        assert SourceState.NOT_APPLICABLE == self.module.get_state()

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
            "type='RPM_OSTREE_CONTAINER', "
            "stateroot='', "
            "transport='', "
            "url=''"
            ")"
        )

        self.module.configuration.stateroot = "fcos"
        self.module.configuration.transport = "registry"
        self.module.configuration.url = "quay.io/fedora/coreos:stable"

        assert repr(self.module) == str(
            "Source("
            "type='RPM_OSTREE_CONTAINER', "
            "stateroot='fcos', "
            "transport='registry', "
            "url='quay.io/fedora/coreos:stable'"
            ")"
        )
