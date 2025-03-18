# Implementation of GUI Secret Agent for wireless configuration
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

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("NM", "1.0")

from gi.repository import Gtk, NM

from dasbus.typing import *  # pylint: disable=wildcard-import
from dasbus.identifier import DBusObjectIdentifier
from dasbus.server.interface import dbus_interface
from string import hexdigits, ascii_letters   # pylint: disable=deprecated-module

from pyanaconda.core.i18n import _, C_
from pyanaconda.core.dbus import SystemBus
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.constants.services import NETWORK_MANAGER
from pyanaconda.modules.common.constants.namespaces import NETWORK_MANAGER_NAMESPACE
from pyanaconda.ui.gui import GUIObject

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

NM_SECRET_AGENT_GET_SECRETS_FLAG_ALLOW_INTERACTION = 0x1

AGENT_MANAGER = DBusObjectIdentifier(
    namespace=NETWORK_MANAGER_NAMESPACE,
    basename="AgentManager"
)
SECRET_AGENT = DBusObjectIdentifier(
    namespace=NETWORK_MANAGER_NAMESPACE,
    basename="SecretAgent"
)

secret_agent = None


class SecretAgentDialog(GUIObject):
    builderObjects = ["secret_agent_dialog"]
    mainWidgetName = "secret_agent_dialog"
    uiFile = "spokes/lib/network_secret_agent.glade"

    def __init__(self, *args, **kwargs):
        self._content = kwargs.pop('content', {})
        if 'message' not in self._content:
            self._content['message'] = ""
        if 'secrets' not in self._content:
            self._content['secrets'] = []
        super().__init__(*args, **kwargs)
        self.builder.get_object("label_message").set_text(self._content['message'])
        self._connect_button = self.builder.get_object("connect_button")

    def initialize(self):
        self._entries = {}
        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(6)

        for row, secret in enumerate(self._content['secrets']):
            label = Gtk.Label(label=secret['label'], halign=Gtk.Align.START)
            entry = Gtk.Entry(hexpand=True)
            entry.set_text(secret['value'])
            if secret['key']:
                self._entries[secret['key']] = entry
            else:
                entry.set_sensitive(False)
            if secret['password']:
                entry.set_visibility(False)
            self._validate(entry, secret)
            entry.connect("changed", self._validate, secret)
            entry.connect("activate", self._password_entered_cb)
            label.set_use_underline(True)
            label.set_mnemonic_widget(entry)
            grid.attach(label, 0, row, 1, 1)
            grid.attach(entry, 1, row, 1, 1)

        self.builder.get_object("password_box").add(grid)

    def run(self):
        self.initialize()
        self.window.show_all()
        rc = self.window.run()
        for secret in self._content['secrets']:
            if secret['key']:
                secret['value'] = self._entries[secret['key']].get_text()
        self.window.destroy()
        return rc

    @property
    def valid(self):
        return all(secret.get('valid', False) for secret in self._content['secrets'])

    def _validate(self, entry, secret):
        secret['value'] = entry.get_text()
        if secret['validate']:
            secret['valid'] = secret['validate'](secret)
        else:
            secret['valid'] = len(secret['value']) > 0
        self._update_connect_button()

    def _password_entered_cb(self, entry):
        if self._connect_button.get_sensitive() and self.valid:
            self.window.response(1)

    def _update_connect_button(self):
        self._connect_button.set_sensitive(self.valid)


@dbus_interface(SECRET_AGENT.interface_name)
class SecretAgent(object):
    def __init__(self, ui_callback):
        """Create a SecretAgent instance.

        :param ui_callback: A callable that runs UI dialog to get secrets.
                            Takes one in/out argument - a dictionary holding the content
                            of the dialog.
                            Returns True if the secrets in the content were set and
                            should be applied, False otherwise (eg when cancelled).
        :type ui_callback: callable(dialog_content)
        """
        self._ui_callback = ui_callback

    def set_ui_callback(self, ui_callback):
        self._ui_callback = ui_callback

    def GetSecrets(
        self,
        connection_hash: Dict[Str, Structure],
        connection_path: ObjPath,
        setting_name: Str,
        hints: List[Str],
        flags: UInt32
    ) -> Dict[Str, Structure]:
        """Get secrets for wireless configuration interactively via GUI dialog.

        Implemantation of SecretAgent NetworkManager interface.
        Supports WEP and WPA key management.
        For WPA Enterprise returns empty secrets for further configuration in nm-c-e.
        """
        log.debug("GetSecrets: secrets requested path '%s' setting '%s' hints '%s' new %d",
                  connection_path, setting_name, str(hints), flags)
        if not (flags & NM_SECRET_AGENT_GET_SECRETS_FLAG_ALLOW_INTERACTION):
            return

        unpacked_connection_hash = get_native(connection_hash)

        content = self._get_content(setting_name, unpacked_connection_hash)

        secrets = dict()
        if self._ui_callback(content):
            for secret in content['secrets']:
                if secret['key']:
                    secrets[secret['key']] = get_variant(Str, secret['value'])

        settings = {setting_name: secrets}

        return settings

    def _get_content(self, setting_name, connection_hash):
        content = {}
        connection_type = connection_hash['connection']['type']
        if connection_type == "802-11-wireless":
            content['title'] = _("Authentication required by wireless network")
            content['message'] = _("Passwords or encryption keys are required to access\n"
                                   "the wireless network '%(network_id)s'.") \
                % {'network_id': str(connection_hash['connection']['id'])}
            content['secrets'] = self._get_wireless_secrets(setting_name, connection_hash)
        else:
            log.info("Connection type %s not supported by secret agent", connection_type)

        return content

    def _get_wireless_secrets(self, setting_name, connection_hash):
        key_mgmt = connection_hash['802-11-wireless-security']['key-mgmt']
        original_secrets = connection_hash[setting_name]
        secrets = []
        if key_mgmt in ['wpa-none', 'wpa-psk']:
            secrets.append({
                'label': C_('GUI|Network|Secrets Dialog', '_Password:'),
                'key': 'psk',
                'value': original_secrets.get('psk', ''),
                'validate': self._validate_wpapsk,
                'password': True
            })
        # static WEP
        elif key_mgmt == 'none':
            key_idx = str(original_secrets.get('wep_tx_keyidx', '0'))
            secrets.append({
                'label': C_('GUI|Network|Secrets Dialog', '_Key:'),
                'key': 'wep-key%s' % key_idx,
                'value': original_secrets.get('wep-key%s' % key_idx, ''),
                'wep_key_type': original_secrets.get('wep-key-type', ''),
                'validate': self._validate_staticwep,
                'password': True
            })
        # WPA-Enterprise
        elif key_mgmt == 'wpa-eap':
            eap = original_secrets['eap'][0]
            if eap in ('md5', 'leap', 'ttls', 'peap'):
                secrets.append({
                    'label': _('User name: '),
                    'key': None,
                    'value': original_secrets.get('identity', ''),
                    'validate': None,
                    'password': False
                })
                secrets.append({
                    'label': _('Password: '),
                    'key': 'password',
                    'value': original_secrets.get('password', ''),
                    'validate': None,
                    'password': True
                })
            elif eap == 'tls':
                secrets.append({
                    'label': _('Identity: '),
                    'key': None,
                    'value': original_secrets.get('identity', ''),
                    'validate': None,
                    'password': False
                })
                secrets.append({
                    'label': _('Private key password: '),
                    'key': 'private-key-password',
                    'value': original_secrets.get('private-key-password', ''),
                    'validate': None,
                    'password': True
                })
        else:
            log.info("Unsupported wireless key management: %s", key_mgmt)

        return secrets

    def _validate_wpapsk(self, secret):
        value = secret['value']
        if len(value) == 64:
            # must be composed of hexadecimal digits only
            return all(c in hexdigits for c in value)
        else:
            return 8 <= len(value) <= 63

    def _validate_staticwep(self, secret):
        value = secret['value']
        if secret['wep_key_type'] == NM.WepKeyType.KEY:
            if len(value) in (10, 26):
                return all(c in hexdigits for c in value)
            elif len(value) in (5, 13):
                return all(c in ascii_letters for c in value)
            else:
                return False
        elif secret['wep_key_type'] == NM.WepKeyType.PASSPHRASE:
            return 0 <= len(value) <= 64
        else:
            return True

    def SaveSecrets(self, connection_hash: Dict[Str, Structure], connection_path: ObjPath):
        """Noop implementation of NetworkManager SecretAgent interface SaveSecrets method"""
        log.debug("SaveSecrets called for %s", connection_path)


def register_secret_agent(spoke):
    if not conf.system.can_configure_network:
        return False

    def spoke_ui_callback(dialog_content):
        dialog = SecretAgentDialog(spoke.data, content=dialog_content)
        with spoke.main_window.enlightbox(dialog.window):
            rc = dialog.run()
        return rc == 1

    global secret_agent
    if not secret_agent:
        secret_agent = SecretAgent(spoke_ui_callback)
        bus = SystemBus
        bus.publish_object(SECRET_AGENT.object_path, secret_agent)
        proxy = NETWORK_MANAGER.get_proxy(AGENT_MANAGER.object_path)
        proxy.Register("anaconda")
    else:
        secret_agent.set_ui_callback(spoke_ui_callback)

    return True
