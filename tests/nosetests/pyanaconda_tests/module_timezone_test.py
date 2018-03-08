#
# Copyright (C) 2018  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from mock import Mock

from pyanaconda.modules.common.constants.services import TIMEZONE
from pyanaconda.modules.timezone.timezone import TimezoneModule
from pyanaconda.modules.timezone.timezone_interface import TimezoneInterface
from tests.nosetests.pyanaconda_tests import check_kickstart_interface


class TimezoneInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the timezone module."""

    def setUp(self):
        """Set up the timezone module."""
        # Set up the timezone module.
        self.timezone_module = TimezoneModule()
        self.timezone_interface = TimezoneInterface(self.timezone_module)

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.timezone_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.timezone_interface.KickstartCommands, ["timezone"])
        self.assertEqual(self.timezone_interface.KickstartSections, [])
        self.assertEqual(self.timezone_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def timezone_property_test(self):
        """Test the Timezone property."""
        self.timezone_interface.SetTimezone("Europe/Prague")
        self.assertEqual(self.timezone_interface.Timezone, "Europe/Prague")
        self.callback.assert_called_once_with(TIMEZONE.interface_name, {'Timezone': 'Europe/Prague'}, [])

    def utc_property_test(self):
        """Test the IsUtc property."""
        self.timezone_interface.SetIsUTC(True)
        self.assertEqual(self.timezone_interface.IsUTC, True)
        self.callback.assert_called_once_with(TIMEZONE.interface_name, {'IsUTC': True}, [])

    def ntp_property_test(self):
        """Test the NTPEnabled property."""
        self.timezone_interface.SetNTPEnabled(False)
        self.assertEqual(self.timezone_interface.NTPEnabled, False)
        self.callback.assert_called_once_with(TIMEZONE.interface_name, {'NTPEnabled': False}, [])

    def ntp_servers_property_test(self):
        """Test the NTPServers property."""
        self.timezone_interface.SetNTPServers(["ntp.cesnet.cz"])
        self.assertEqual(self.timezone_interface.NTPServers, ["ntp.cesnet.cz"])
        self.callback.assert_called_once_with(TIMEZONE.interface_name, {'NTPServers': ["ntp.cesnet.cz"]}, [])

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.timezone_interface, ks_in, ks_out)

    def no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = """
        # System timezone
        timezone America/New_York
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_empty_test(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def kickstart_test(self):
        """Test the timezone command."""
        ks_in = """
        timezone Europe/Prague
        """
        ks_out = """
        # System timezone
        timezone Europe/Prague
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart2_test(self):
        """Test the timezone command with flags."""
        ks_in = """
        timezone --utc --nontp Europe/Prague
        """
        ks_out = """
        # System timezone
        timezone Europe/Prague --isUtc --nontp
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart3_test(self):
        """Test the timezone command with ntp servers.."""
        ks_in = """
        timezone --ntpservers ntp.cesnet.cz Europe/Prague
        """
        ks_out = """
        # System timezone
        timezone Europe/Prague --ntpservers=ntp.cesnet.cz
        """
        self._test_kickstart(ks_in, ks_out)
