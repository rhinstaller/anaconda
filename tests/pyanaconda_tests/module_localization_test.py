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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import unittest
from mock import Mock

from pyanaconda.dbus.constants import MODULE_LOCALIZATION_NAME, DBUS_MODULE_NAMESPACE
from pyanaconda.modules.localization.localization import LocalizationModule
from pyanaconda.modules.localization.localization_interface import LocalizationInterface


class LocalizationInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the localization module."""

    def setUp(self):
        """Set up the localization module."""
        # Set up the localization module.
        self.localization_module = LocalizationModule()
        self.localization_interface = LocalizationInterface(self.localization_module)

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.localization_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.localization_interface.KickstartCommands, ["lang"])
        self.assertEqual(self.localization_interface.KickstartSections, [])
        self.assertEqual(self.localization_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def language_property_test(self):
        """Test the Language property."""
        self.localization_interface.SetLanguage("cs_CZ.UTF-8")
        self.assertEqual(self.localization_interface.Language, "cs_CZ.UTF-8")
        self.callback.assert_called_once_with(MODULE_LOCALIZATION_NAME, {'Language': 'cs_CZ.UTF-8'}, [])

    def language_support_property_test(self):
        """Test the LanguageSupport property."""
        self.localization_interface.SetLanguageSupport(["fr_FR"])
        self.assertEqual(self.localization_interface.LanguageSupport, ["fr_FR"])
        self.callback.assert_called_once_with(MODULE_LOCALIZATION_NAME, {'LanguageSupport': ["fr_FR"]}, [])

    def _test_kickstart(self, ks_in, ks_out):
        """Test the kickstart string."""
        # Remove extra spaces from the expected output.
        ks_output = "\n".join("".join(line.strip()) for line in ks_out.strip("\n").splitlines())

        # Read a kickstart,
        result = self.localization_interface.ReadKickstart(ks_in)
        self.assertEqual({k: v.unpack() for k, v in result.items()}, {"success": True})

        # Generate a kickstart.
        self.assertEqual(ks_output, self.localization_interface.GenerateKickstart())

        # Test the properties changed callback.
        self.callback.assert_any_call(DBUS_MODULE_NAMESPACE, {'Kickstarted': True}, [])

    def kickstart_test(self):
        """Test the lang command."""
        ks_in = """
        lang cs_CZ.UTF-8
        """
        ks_out = """
        # System language
        lang cs_CZ.UTF-8
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart2_test(self):
        """Test the lang command with added language support.."""
        ks_in = """
        lang en_US.UTF-8 --addsupport=cs_CZ.UTF-8
        """
        ks_out = """
        # System language
        lang en_US.UTF-8 --addsupport=cs_CZ.UTF-8
        """
        self._test_kickstart(ks_in, ks_out)
