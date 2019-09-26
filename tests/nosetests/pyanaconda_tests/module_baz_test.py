#
# Copyright (C) 2019  Red Hat, Inc.
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

from pyanaconda.dbus_addons.baz.baz import Baz
from pyanaconda.dbus_addons.baz.baz_interface import BazInterface
from tests.nosetests.pyanaconda_tests import check_kickstart_interface


class BazInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the Baz module."""

    def setUp(self):
        """Set up the localization module."""
        self.module = Baz()
        self.interface = BazInterface(self.module)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.interface.KickstartCommands, [])
        self.assertEqual(self.interface.KickstartSections, [])
        self.assertEqual(self.interface.KickstartAddons, ["my_example_baz"])

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.interface, ks_in, ks_out)

    def no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def kickstart_test(self):
        """Test with kickstart."""
        ks_in = """
        %addon my_example_baz --foo=1 --bar
        The content of the baz section.
        %end
        """
        ks_out = """
        %addon my_example_baz --foo=1 --bar
        The content of the baz section.
        %end
        """
        self._test_kickstart(ks_in, ks_out)
