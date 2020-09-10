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

from pyanaconda.core.constants import SOURCE_TYPE_RPM_OSTREE
from pyanaconda.modules.payloads.constants import PayloadType
from pyanaconda.modules.payloads.payload.rpm_ostree.rpm_ostree import RPMOSTreeModule
from pyanaconda.modules.payloads.payload.rpm_ostree.rpm_ostree_interface import RPMOSTreeInterface

from tests.nosetests.pyanaconda_tests.module_payload_shared import PayloadSharedTest


class RPMOSTreeInterfaceTestCase(unittest.TestCase):
    """Test the RPM OSTree DBus module."""

    def setUp(self):
        self.module = RPMOSTreeModule()
        self.interface = RPMOSTreeInterface(self.module)

        self.shared_tests = PayloadSharedTest(
            test=self,
            payload=self.module,
            payload_intf=self.interface
        )

    def type_test(self):
        """Test the Type property."""
        self.shared_tests.check_type(PayloadType.RPM_OSTREE)

    def supported_sources_test(self):
        """Test the SupportedSourceTypes property."""
        self.assertEqual(self.interface.SupportedSourceTypes, [
            SOURCE_TYPE_RPM_OSTREE
        ])
