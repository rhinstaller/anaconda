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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import unittest

import gi

from pyanaconda.ui.gui.spokes.lib.network_secret_agent import SecretAgent

gi.require_version("NM", "1.0")
gi.require_version("GLib", "2.0")
from gi.repository import NM, GLib


class SecretAgentTestCase(unittest.TestCase):
    """Test DBus interface of SecretAgent."""

    def setUp(self):
        """Set up the secret agent."""
        self.agent = SecretAgent(lambda x: True)

    def test_save_secrets(self):
        """Test SaveSecrets method."""
        self.agent.SaveSecrets(None, None)

    def test_validate_staticwep(self):
        """Test validate_staticwep method."""
        secret = {}

        secret['wep_key_type'] = NM.WepKeyType.KEY
        valid_keys = [
            # ascii, len 5
            "aaZZZ",
            # ascii, len 13
            "a"*12+"z",
            # hex, len 10
            "01234ABCDE",
            # hex, len 26
            "0"*20+"ABCDEF",
        ]
        invalid_keys = [
            "abc",
            "a"*6,
            "012345ABCDE",
            "0123XABCDE",
            "0"*20+"ABCDEX",
            "0"*15,
        ]
        for key in valid_keys:
            secret['value'] = key
            assert self.agent._validate_staticwep(secret)
        for key in invalid_keys:
            secret['value'] = key
            assert not self.agent._validate_staticwep(secret)

        secret['wep_key_type'] = NM.WepKeyType.PASSPHRASE
        valid_keys = [
            "passphrase",
            "",
            "a"*64,
        ]
        invalid_keys = [
            "a"*65,
        ]
        for key in valid_keys:
            secret['value'] = key
            assert self.agent._validate_staticwep(secret)
        for key in invalid_keys:
            secret['value'] = key
            assert not self.agent._validate_staticwep(secret)

    def test_validate_wpapsk(self):
        """Test validate_wpapsk method."""
        secret = {}

        valid_keys = [
            "x"*8,
            "x"*40,
            "x"*63,
            # hex, len 64
            "0"*58+"ABCDEF",
        ]
        invalid_keys = [
            # non-hex, len 64
            "0"*58+"ABCDEx",
            # too long
            "a"*65,
            # too short
            "a"*7,
        ]
        for key in valid_keys:
            secret['value'] = key
            assert self.agent._validate_wpapsk(secret)
        for key in invalid_keys:
            secret['value'] = key
            assert not self.agent._validate_wpapsk(secret)

    def _mock_secret_agent_dialog_ui_callback(self, entered_value):
        def ui_callback(content):
            if 'secrets' not in content:
                content['secrets'] = []
            for secret in content['secrets']:
                if secret['key']:
                    secret['value'] = entered_value
            return True
        return ui_callback

    def test_get_secrets(self):
        """Test GetSecrets method."""
        connection_hash = {
            'ipv4': {
                'address-data': GLib.Variant('aa{sv}', []),
                'addresses': GLib.Variant('aau', []),
                'dns': GLib.Variant('au', []),
                'dns-search': GLib.Variant('as', []),
                'method': GLib.Variant('s', 'auto'),
                'route-data': GLib.Variant('aa{sv}', []),
                'routes': GLib.Variant('aau', [])
            },
            'proxy': {},
            'ipv6': {
                'address-data': GLib.Variant('aa{sv}', []),
                'addresses': GLib.Variant('a(ayuay)', []),
                'dns': GLib.Variant('aay', []),
                'dns-search': GLib.Variant('as', []),
                'method': GLib.Variant('s', 'auto'),
                'route-data': GLib.Variant('aa{sv}', []),
                'routes': GLib.Variant('a(ayuayu)', [])
            },
            'connection': {
                'id': GLib.Variant('s', 'UPC1379222'),
                'interface-name': GLib.Variant('s', 'wlp3s0'),
                'permissions': GLib.Variant('as', []),
                'type': GLib.Variant('s', '802-11-wireless'),
                'uuid': GLib.Variant('s', '6b4ebdf4-942e-4750-a0d5-7b23cffa99be')
            },
            '802-11-wireless': {
                'mac-address-blacklist': GLib.Variant('as', []),
                'mode': GLib.Variant('s', 'infrastructure'),
                'security': GLib.Variant('s', '802-11-wireless-security'),
                'ssid': GLib.Variant('ay',
                                     [0x55, 0x50, 0x43, 0x31, 0x33, 0x37, 0x39, 0x32, 0x32, 0x32])
            },
            '802-11-wireless-security': {
                'auth-alg': GLib.Variant('s', 'open'),
                'key-mgmt': GLib.Variant('s', 'wpa-psk')
            }
        }
        connection_path = '/org/freedesktop/NetworkManager/Settings/6'
        setting_name = '802-11-wireless-security'
        hints = []
        no_interaction_flags = 0
        allowed_interaction_flags = 5

        # NM_SECRET_AGENT_GET_SECRETS_FLAG_ALLOW_INTERACTION not set
        result = self.agent.GetSecrets(
            connection_hash,
            connection_path,
            setting_name,
            hints,
            no_interaction_flags
        )
        assert result is None

        # UI cancelled
        self.agent.set_ui_callback(lambda x: False)
        result = self.agent.GetSecrets(
            connection_hash,
            connection_path,
            setting_name,
            hints,
            allowed_interaction_flags
        )
        assert result == {setting_name: {}}

        # Mock what SecretAgentDialog does in the iu callback
        secret_value = GLib.Variant('s', "mypassword")
        self.agent.set_ui_callback(
            self._mock_secret_agent_dialog_ui_callback(entered_value=secret_value.unpack())
        )

        # unsupported connection type
        orig_type = connection_hash['connection']['type']
        connection_hash['connection']['type'] = 'unsupported-type'
        result = self.agent.GetSecrets(
            connection_hash,
            connection_path,
            setting_name,
            hints,
            allowed_interaction_flags
        )
        assert result == {setting_name: {}}
        connection_hash['connection']['type'] = orig_type

        # WPA key management
        orig_key_mgmt = connection_hash['802-11-wireless-security']['key-mgmt']
        connection_hash['802-11-wireless-security']['key-mgmt'] = 'wpa-none'
        result = self.agent.GetSecrets(
            connection_hash,
            connection_path,
            setting_name,
            hints,
            allowed_interaction_flags
        )
        assert result == {setting_name: {'psk': secret_value}}
        connection_hash['802-11-wireless-security']['key-mgmt'] = 'wpa-psk'
        result = self.agent.GetSecrets(
            connection_hash,
            connection_path,
            setting_name,
            hints,
            allowed_interaction_flags
        )
        assert result == {setting_name: {'psk': secret_value}}
        connection_hash['802-11-wireless-security']['key-mgmt'] = orig_key_mgmt

        # WEP key management
        orig_key_mgmt = connection_hash['802-11-wireless-security']['key-mgmt']
        connection_hash['802-11-wireless-security']['key-mgmt'] = 'none'
        result = self.agent.GetSecrets(
            connection_hash,
            connection_path,
            setting_name,
            hints,
            allowed_interaction_flags
        )
        assert result == {setting_name: {'wep-key0': secret_value}}
        connection_hash['802-11-wireless-security']['key-mgmt'] = orig_key_mgmt

        # WPA-Enterprise
        # TODO: get more realistic connection_hash for WPA enterprise
        orig_key_mgmt = connection_hash['802-11-wireless-security']['key-mgmt']
        connection_hash['802-11-wireless-security']['key-mgmt'] = 'wpa-eap'
        connection_hash['802-11-wireless-security']['eap'] = ['peap']
        result = self.agent.GetSecrets(
            connection_hash,
            connection_path,
            setting_name,
            hints,
            allowed_interaction_flags
        )
        assert result == {setting_name: {'password': secret_value}}
        connection_hash['802-11-wireless-security']['eap'] = ['tls']
        result = self.agent.GetSecrets(
            connection_hash,
            connection_path,
            setting_name,
            hints,
            allowed_interaction_flags
        )
        assert result == {setting_name: {'private-key-password': secret_value}}
        connection_hash['802-11-wireless-security'].pop('eap')
        connection_hash['802-11-wireless-security']['key-mgmt'] = orig_key_mgmt
