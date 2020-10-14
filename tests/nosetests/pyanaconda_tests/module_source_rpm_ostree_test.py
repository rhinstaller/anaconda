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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest

from dasbus.typing import get_variant, Str, Bool

from pyanaconda.core.constants import SOURCE_TYPE_RPM_OSTREE
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_RPM_OSTREE
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.rpm_ostree.rpm_ostree import RPMOSTreeSourceModule
from pyanaconda.modules.payloads.source.rpm_ostree.rpm_ostree_interface import \
    RPMOSTreeSourceInterface

from tests.nosetests.pyanaconda_tests import check_dbus_property


class OSTreeSourceInterfaceTestCase(unittest.TestCase):
    """Test the DBus interface of the OSTree source."""

    def setUp(self):
        self.module = RPMOSTreeSourceModule()
        self.interface = RPMOSTreeSourceInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            PAYLOAD_SOURCE_RPM_OSTREE,
            self.interface,
            *args, **kwargs
        )

    def type_test(self):
        """Test the Type property."""
        self.assertEqual(SOURCE_TYPE_RPM_OSTREE, self.interface.Type)

    def description_test(self):
        """Test the Description property."""
        self.assertEqual("RPM OSTree", self.interface.Description)

    def configuration_test(self):
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

    def type_test(self):
        """Test the type property."""
        self.assertEqual(SourceType.RPM_OSTREE, self.module.type)

    def network_required_test(self):
        """Test the network_required property."""
        self.assertEqual(self.module.network_required, False)

        self.module.configuration.url = "file://my/path"
        self.assertEqual(self.module.network_required, False)

        self.module.configuration.url = "http://my/path"
        self.assertEqual(self.module.network_required, True)

        self.module.configuration.url = "https://my/path"
        self.assertEqual(self.module.network_required, True)

    def required_space_test(self):
        """Test the required_space property."""
        self.assertEqual(self.module.required_space, 0)

    def get_state_test(self):
        """Test the source state."""
        self.assertEqual(SourceState.NOT_APPLICABLE, self.module.get_state())

    def set_up_with_tasks_test(self):
        """Test the set-up tasks."""
        self.assertEqual(self.module.set_up_with_tasks(), [])

    def tear_down_with_tasks_test(self):
        """Test the tear-down tasks."""
        self.assertEqual(self.module.tear_down_with_tasks(), [])

    def repr_test(self):
        """Test the string representation."""
        self.assertEqual(repr(self.module), str(
            "Source("
            "type='RPM_OSTREE', "
            "osname='', "
            "url=''"
            ")"
        ))

        self.module.configuration.osname = "fedora-atomic"
        self.module.configuration.url = "https://kojipkgs.fedoraproject.org/atomic/repo"

        self.assertEqual(repr(self.module), str(
            "Source("
            "type='RPM_OSTREE', "
            "osname='fedora-atomic', "
            "url='https://kojipkgs.fedoraproject.org/atomic/repo'"
            ")"
        ))
