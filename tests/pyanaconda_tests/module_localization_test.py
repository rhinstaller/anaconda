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
from textwrap import dedent
from mock import Mock

from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.modules.localization.localization import LocalizationModule
from pyanaconda.modules.localization.localization_interface import LocalizationInterface
from tests.pyanaconda_tests import check_kickstart_interface


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
        self.assertEqual(self.localization_interface.KickstartCommands, ["keyboard", "lang"])
        self.assertEqual(self.localization_interface.KickstartSections, [])
        self.assertEqual(self.localization_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def language_property_test(self):
        """Test the Language property."""
        self.localization_interface.SetLanguage("cs_CZ.UTF-8")
        self.assertEqual(self.localization_interface.Language, "cs_CZ.UTF-8")
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'Language': 'cs_CZ.UTF-8'}, [])

    def language_support_property_test(self):
        """Test the LanguageSupport property."""
        self.localization_interface.SetLanguageSupport(["fr_FR"])
        self.assertEqual(self.localization_interface.LanguageSupport, ["fr_FR"])
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'LanguageSupport': ["fr_FR"]}, [])

    def keyboard_property_test(self):
        """Test the Keyboard property."""
        self.localization_interface.SetKeyboard("cz")
        self.assertEqual(self.localization_interface.Keyboard, "cz")
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'Keyboard': 'cz'}, [])

    def vc_keymap_property_test(self):
        """Test the VirtualConsoleKeymap property."""
        self.localization_interface.SetVirtualConsoleKeymap("cz")
        self.assertEqual(self.localization_interface.VirtualConsoleKeymap, "cz")
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'VirtualConsoleKeymap': 'cz'}, [])

    def x_layouts_property_test(self):
        """Test the XLayouts property."""
        self.localization_interface.SetXLayouts(["en", "cz(querty)"])
        self.assertEqual(self.localization_interface.XLayouts, ["en", "cz(querty)"])
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'XLayouts': ["en", "cz(querty)"]}, [])

    def switch_options_property_test(self):
        """Test the LayoutSwitchOptions property."""
        self.localization_interface.SetLayoutSwitchOptions(["grp:alt_shift_toggle"])
        self.assertEqual(self.localization_interface.LayoutSwitchOptions, ["grp:alt_shift_toggle"])
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'LayoutSwitchOptions': ["grp:alt_shift_toggle"]}, [])

    def keyboard_seen_test(self):
        """Test the KeyboardKickstarted property."""
        self.assertEqual(self.localization_interface.KeyboardKickstarted, False)
        ks_in = """
        lang cs_CZ.UTF-8
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        self.assertEqual(self.localization_interface.KeyboardKickstarted, False)
        ks_in = """
        lang cs_CZ.UTF-8
        keyboard cz
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        self.assertEqual(self.localization_interface.KeyboardKickstarted, True)

    def language_seen_test(self):
        """Test the LanguageKickstarted property."""
        self.assertEqual(self.localization_interface.LanguageKickstarted, False)
        ks_in = """
        keyboard cz
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        self.assertEqual(self.localization_interface.LanguageKickstarted, False)
        ks_in = """
        keyboard cz
        lang cs_CZ.UTF-8
        """
        ks_in = dedent(ks_in).strip()
        self.localization_interface.ReadKickstart(ks_in)
        self.assertEqual(self.localization_interface.LanguageKickstarted, True)

    def set_language_kickstarted_test(self):
        """Test SetLanguageKickstart."""
        self.localization_interface.SetLanguageKickstarted(True)
        self.assertEqual(self.localization_interface.LanguageKickstarted, True)
        self.callback.assert_called_once_with(LOCALIZATION.interface_name, {'LanguageKickstarted': True}, [])

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.localization_interface, ks_in, ks_out)

    def no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def kickstart_empty_test(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def lang_kickstart_test(self):
        """Test the lang command."""
        ks_in = """
        lang cs_CZ.UTF-8
        """
        ks_out = """
        # System language
        lang cs_CZ.UTF-8
        """
        self._test_kickstart(ks_in, ks_out)

    def lang_kickstart2_test(self):
        """Test the lang command with added language support.."""
        ks_in = """
        lang en_US.UTF-8 --addsupport=cs_CZ.UTF-8
        """
        ks_out = """
        # System language
        lang en_US.UTF-8 --addsupport=cs_CZ.UTF-8
        """
        self._test_kickstart(ks_in, ks_out)

    def keyboard_kickstart1_test(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard --vckeymap=us --xlayouts='us','cz (qwerty)'
        """
        ks_out = """
        # Keyboard layouts
        keyboard --vckeymap=us --xlayouts='us','cz (qwerty)'
        """
        self._test_kickstart(ks_in, ks_out)

    def keyboard_kickstart2_test(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard us
        """
        ks_out = """
        # Keyboard layouts
        keyboard 'us'
        """
        self._test_kickstart(ks_in, ks_out)

    def keyboard_kickstart3_test(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard --xlayouts=cz,'cz (qwerty)' --switch=grp:alt_shift_toggle
        """
        ks_out = """
        # Keyboard layouts
        keyboard --xlayouts='cz','cz (qwerty)' --switch='grp:alt_shift_toggle'
        """
        self._test_kickstart(ks_in, ks_out)

    def keyboard_kickstart4_test(self):
        """Test the keyboard command."""
        ks_in = """
        keyboard --xlayouts='cz (qwerty)','en' en
        """
        ks_out = """
        # Keyboard layouts
        # old format: keyboard en
        # new format:
        keyboard --xlayouts='cz (qwerty)','en'
        """
        self._test_kickstart(ks_in, ks_out)
