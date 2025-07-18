# Network configuration spoke classes
#
# Copyright (C) 2011  Red Hat, Inc.
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
gi.require_version("GObject", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("Gio", "2.0")
gi.require_version("NM", "1.0")

from uuid import uuid4

from gi.repository import NM, Gio, GObject, Gtk, Pango

from pyanaconda import network
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import glib
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import ANACONDA_ENVIRON, NETWORK_CAPABILITY_TEAM
from pyanaconda.core.i18n import CN_, N_, _
from pyanaconda.core.process_watchers import PidWatcher
from pyanaconda.core.util import startProgram
from pyanaconda.flags import flags as anaconda_flags
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.structures.network import NetworkDeviceConfiguration
from pyanaconda.modules.network.constants import (
    NM_CONNECTION_TYPE_WIFI,
)
from pyanaconda.modules.network.utils import get_default_connection
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import NormalSpoke, StandaloneSpoke
from pyanaconda.ui.gui.spokes.lib.network_secret_agent import register_secret_agent
from pyanaconda.ui.gui.utils import (
    escape_markup,
    gtk_call_once,
    really_hide,
    really_show,
)

log = get_module_logger(__name__)

NM._80211ApFlags = getattr(NM, "80211ApFlags")
NM._80211ApSecurityFlags = getattr(NM, "80211ApSecurityFlags")
NM._80211Mode = getattr(NM, "80211Mode")

IPV4_CONFIG = "IPv4"
IPV6_CONFIG = "IPv6"

DEVICES_COLUMN_ICON_NAME = 0
DEVICES_COLUMN_SORT = 1
DEVICES_COLUMN_TITLE = 2
DEVICES_COLUMN_OBJECT = 3

SELECT_WIRELESS_COLUMN_SSID = 0
SELECT_WIRELESS_COLUMN_SSID_STR = 1
SELECT_WIRELESS_COLUMN_STRENGTH = 3
SELECT_WIRELESS_COLUMN_SECURITY = 5
SELECT_WIRELESS_COLUMN_ACTIVE = 6

CONFIGURE_WIRELESS_COLUMN_SSID = 0
CONFIGURE_WIRELESS_COLUMN_SSID_STR = 1
CONFIGURE_WIRELESS_COLUMN_CON_ID = 2
CONFIGURE_WIRELESS_COLUMN_CON_UUID = 3


def localized_string_of_device_state(device, state):
    s = _("Status unknown (missing)")

    if state == NM.DeviceState.UNKNOWN:
        s = _("Status unknown")
    elif state == NM.DeviceState.UNMANAGED:
        s = _("Unmanaged")
    elif state == NM.DeviceState.UNAVAILABLE:
        if not device:
            s = _("Unavailable")
        elif device.get_firmware_missing():
            s = _("Firmware missing")
        else:
            s = _("Unavailable")
    elif state == NM.DeviceState.DISCONNECTED:
        if (device and device.get_device_type() == NM.DeviceType.ETHERNET
              and not device.get_carrier()):
            s = _("Cable unplugged")
        else:
            s = _("Disconnected")
    elif state in (NM.DeviceState.PREPARE,
                   NM.DeviceState.CONFIG,
                   NM.DeviceState.IP_CONFIG,
                   NM.DeviceState.IP_CHECK):
        s = _("Connecting")
    elif state == NM.DeviceState.NEED_AUTH:
        s = _("Authentication required")
    elif state == NM.DeviceState.ACTIVATED:
        s = _("Connected")
    elif state == NM.DeviceState.DEACTIVATING:
        s = _("Disconnecting")
    elif state == NM.DeviceState.FAILED:
        s = _("Connection failed")

    return s


__all__ = ["NetworkSpoke", "NetworkStandaloneSpoke"]


class CellRendererSignalStrength(Gtk.CellRendererPixbuf):

    __gtype_name__ = "CellRendererSignalStrength"
    __gproperties__ = {
        "signal": (GObject.TYPE_UINT,
                   "Signal", "Signal",
                   0, glib.MAXUINT, 0,
                   GObject.ParamFlags.READWRITE),
    }

    def __init__(self):
        super().__init__()
        self.signal = 0

    def do_get_property(self, prop):
        if prop.name == 'signal':
            return self.signal
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def do_set_property(self, prop, value):
        if prop.name == 'signal':
            self.signal = value
            self._set_icon_name(value)
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def _set_icon_name(self, value):

        if value == 0:
            self.set_property("gicon", None)

        if value < 20:
            icon_name = "network-wireless-signal-none-symbolic"
        elif value < 40:
            icon_name = "network-wireless-signal-weak-symbolic"
        elif value < 50:
            icon_name = "network-wireless-signal-ok-symbolic"
        elif value < 80:
            icon_name = "network-wireless-signal-good-symbolic"
        else:
            icon_name = "network-wireless-signal-excellent-symbolic"

        icon = Gio.ThemedIcon.new_with_default_fallbacks(icon_name)
        self.set_property("gicon", icon)


NM_AP_SEC_UNKNOWN = 0
NM_AP_SEC_NONE = 1
NM_AP_SEC_WEP = 2
NM_AP_SEC_WPA = 3
NM_AP_SEC_WPA2 = 4


class CellRendererSecurity(Gtk.CellRendererPixbuf):

    __gtype_name__ = "CellRendererSecurity"
    __gproperties__ = {"security": (GObject.TYPE_UINT,
                                    "Security", "Security",
                                    0, glib.MAXUINT, 0,
                                    GObject.ParamFlags.READWRITE),
                       }

    def __init__(self):
        super().__init__()
        self.security = NM_AP_SEC_UNKNOWN
        self.icon_name = ""

    def do_get_property(self, prop):
        if prop.name == 'security':
            return self.security
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def do_set_property(self, prop, value):
        if prop.name == 'security':
            self.security = value
            self._set_icon_name(value)
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def _set_icon_name(self, security):
        self.icon_name = ""
        if security not in (NM_AP_SEC_NONE, NM_AP_SEC_UNKNOWN):
            self.icon_name = "network-wireless-encrypted-symbolic"

        self.set_property("icon-name", self.icon_name)


class CellRendererSelected(Gtk.CellRendererPixbuf):

    __gtype_name__ = "CellRendererSelected"
    __gproperties__ = {"selected": (GObject.TYPE_BOOLEAN,
                                    "Selected", "Selected",
                                    False,
                                    GObject.ParamFlags.READWRITE),
                       }

    def __init__(self):
        super().__init__()
        self.selected = False
        self.icon_name = ""

    def do_get_property(self, prop):
        if prop.name == 'selected':
            return self.selected
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def do_set_property(self, prop, value):
        if prop.name == 'selected':
            self.selected = value
            self._set_icon_name(value)
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def _set_icon_name(self, selected):
        self.icon_name = ""
        if selected:
            self.icon_name = "object-select-symbolic"

        self.set_property("icon-name", self.icon_name)


class NetworkControlBox(GObject.GObject):

    __gsignals__ = {
        "nm-state-changed": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, []),
        "device-state-changed": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, [str, int, int, int]),
        "apply-hostname": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, []),
    }

    supported_device_types = [
        NM.DeviceType.ETHERNET,
        NM.DeviceType.WIFI,
        NM.DeviceType.TEAM,
        NM.DeviceType.BOND,
        NM.DeviceType.VLAN,
        NM.DeviceType.BRIDGE,
    ]

    virtual_device_types = [
        NM.DeviceType.TEAM,
        NM.DeviceType.BOND,
        NM.DeviceType.VLAN,
        NM.DeviceType.BRIDGE,
    ]

    wired_ui_device_types = [
        NM.DeviceType.ETHERNET,
        NM.DeviceType.TEAM,
        NM.DeviceType.BOND,
        NM.DeviceType.VLAN,
        NM.DeviceType.BRIDGE,
    ]

    device_type_sort_value = {
        NM.DeviceType.ETHERNET : "1",
        NM.DeviceType.WIFI : "2",
    }

    device_type_name = {
        NM.DeviceType.UNKNOWN: N_("Unknown"),
        NM.DeviceType.ETHERNET: N_("Ethernet"),
        NM.DeviceType.WIFI: N_("Wireless"),
        NM.DeviceType.BOND: N_("Bond"),
        NM.DeviceType.VLAN: N_("VLAN"),
        NM.DeviceType.TEAM: N_("Team"),
        NM.DeviceType.BRIDGE: N_("Bridge"),
    }

    def __init__(self, builder, client, network_module, spoke=None):

        super().__init__()

        self.builder = builder
        self._running_nmce = None
        self.spoke = spoke
        self.client = client
        self._network_module = network_module

        # button for creating of virtual bond and vlan devices
        self.builder.get_object("add_toolbutton").set_sensitive(True)
        self.builder.get_object("add_toolbutton").connect("clicked",
                                                           self.on_add_device_clicked)
        self.builder.get_object("remove_toolbutton").set_sensitive(False)
        self.builder.get_object("remove_toolbutton").connect("clicked",
                                                           self.on_remove_device_clicked)

        not_supported = ["start_hotspot_button",
                         "stop_hotspot_button",
                         "heading_hotspot_network_name",
                         "heading_hotspot_security_key",
                         "label_hotspot_network_name",
                         "label_hotspot_security_key",
                         "hbox54",
                        ]

        do_not_show_in_refresh = ["heading_wireless_network_name",
                                  "label_wireless_network_name"]
        do_not_show_in_refresh += ["%s_%s_%s" % (widget, ty, value)
                                   for widget in ["heading", "label"]
                                   for ty in ["wired", "wireless"]
                                   for value in ["ipv4", "ipv6", "dns", "route"]]
        do_not_show_in_refresh += ["%s_wired_%s" % (widget, value)
                                   for widget in ["heading", "label"]
                                   for value in ["ports", "vlanid", "parent"]]

        for ident in not_supported + do_not_show_in_refresh:
            self.builder.get_object(ident).set_no_show_all(True)
            self.builder.get_object(ident).hide()

        self.builder.get_object("notebook_types").set_show_tabs(False)

        # to prevent UI update signals races
        self._updating_device = False

        # devices list
        # limited to wired and wireless
        treeview = self.builder.get_object("treeview_devices")
        self._add_device_columns(treeview)
        self.dev_cfg_store = self.builder.get_object("liststore_devices")
        self.dev_cfg_store.set_sort_column_id(2, Gtk.SortType.ASCENDING)
        selection = treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.BROWSE)
        selection.connect("changed", self.on_device_selection_changed)

        self.builder.get_object("select_wireless_network_button").connect(
            "clicked",
            self.on_select_wireless_clicked
        )

        self.builder.get_object("device_wired_off_switch").connect("notify::active",
                                                             self.on_device_off_toggled)
        self.builder.get_object("device_wireless_off_switch").connect("notify::active",
                                                             self.on_device_off_toggled)
        self.builder.get_object("button_wired_options").connect("clicked",
                                                           self.on_edit_connection)
        self.builder.get_object("button_wireless_options").connect("clicked",
                                                              self.on_edit_connection)
        self.entry_hostname = self.builder.get_object("entry_hostname")
        self.label_current_hostname = self.builder.get_object("label_current_hostname")
        self.button_apply_hostname = self.builder.get_object("button_apply_hostname")
        self.button_apply_hostname.connect("clicked", self.on_apply_hostname)

        if NETWORK_CAPABILITY_TEAM not in self._network_module.Capabilities:
            self._remove_team_selection()

    def _remove_team_selection(self):
        log.debug("team functionality is not supported")
        model = self.builder.get_object("liststore_add_device")
        for row in model:
            if row[1] == "team":
                model.remove(row.iter)
                return True
        return False

    @property
    def vbox(self):
        return self.builder.get_object("networkControlBox_vbox")

    def _add_device_columns(self, treeview):
        rnd = Gtk.CellRendererPixbuf()
        rnd.set_property("stock-size", Gtk.IconSize.MENU)
        # TODO Gtk3 icon-name? (also at other places)
        col = Gtk.TreeViewColumn("Icon", rnd, **{"icon-name":0})
        col.set_min_width(27)
        treeview.append_column(col)

        rnd = Gtk.CellRendererText()
        rnd.set_property("wrap-mode", Pango.WrapMode.WORD)
        col = Gtk.TreeViewColumn("Text", rnd, markup=2)
        col.set_sort_column_id(2)
        col.set_expand(True)
        treeview.append_column(col)

    def initialize(self):
        if not self.client:
            return

        self.client.connect("notify::%s" % NM.CLIENT_WIRELESS_ENABLED,
                            self.on_wireless_enabled)
        self.client.connect("notify::%s" % NM.CLIENT_STATE,
                            self.on_nm_state_changed)

        self.client.connect("connection-added", self.on_connection_added_or_removed)
        self.client.connect("connection-removed", self.on_connection_added_or_removed)

        self._load_device_configurations()
        self._network_module.DeviceConfigurationChanged.connect(
            self.on_device_configurations_changed
        )

        # select the first device
        treeview = self.builder.get_object("treeview_devices")
        selection = treeview.get_selection()
        itr = self.dev_cfg_store.get_iter_first()
        if itr:
            selection.select_iter(itr)

    def on_device_configurations_changed(self, changes):
        log.debug("device configurations changed: %s", changes)
        self._update_device_configurations(changes)
        self.refresh_ui()

    def _update_device_configurations(self, changes):
        for old_values, new_values in changes:
            old_cfg = NetworkDeviceConfiguration.from_structure(old_values)
            new_cfg = NetworkDeviceConfiguration.from_structure(new_values)

            device_type = old_cfg.device_type or new_cfg.device_type
            # physical devices - devices persist in store
            if device_type not in self.virtual_device_types:
                # device added
                if not old_cfg.device_name and new_cfg.device_name:
                    self.add_dev_cfg(new_cfg)
                    self.watch_dev_cfg_device(new_cfg)
                # device removed
                elif old_cfg.device_name and not new_cfg.device_name:
                    self.remove_dev_cfg(old_cfg)
                # connection modified
                else:
                    self.update_dev_cfg(old_cfg, new_cfg)

            # virtual devices - connections persist in store
            else:
                # connection added
                if not old_cfg.connection_uuid and new_cfg.connection_uuid:
                    self.add_dev_cfg(new_cfg)
                # connection removed
                elif old_cfg.connection_uuid and not new_cfg.connection_uuid:
                    self.remove_dev_cfg(old_cfg)
                # virtual device added or removed
                elif old_cfg.connection_uuid:
                    self.update_dev_cfg(old_cfg, new_cfg)
                    # added
                    if not old_cfg.device_name and new_cfg.device_name:
                        self.watch_dev_cfg_device(new_cfg)

    def _load_device_configurations(self):
        device_configurations = self._network_module.GetDeviceConfigurations()
        self.dev_cfg_store.clear()
        for device_configuration in device_configurations:
            dev_cfg = NetworkDeviceConfiguration.from_structure(device_configuration)
            self.add_dev_cfg(dev_cfg)
            self.watch_dev_cfg_device(dev_cfg)

    def refresh(self):
        self.refresh_ui()

    # Signal handlers.
    def on_nm_state_changed(self, *args):
        self.emit("nm-state-changed")

    def on_device_selection_changed(self, *args):
        self.refresh_ui()

    def on_device_state_changed(self, device, new_state, *args):
        self.emit("device-state-changed", device.get_iface(), new_state, *args)
        if new_state == NM.DeviceState.SECONDARIES:
            return
        self._refresh_carrier_info()
        dev_cfg = self.selected_dev_cfg()
        if dev_cfg and dev_cfg.device_name == device.get_iface():
            self.refresh_ui(state=new_state)

    def on_device_config_changed(self, device, *args):
        dev_cfg = self.selected_dev_cfg()
        if dev_cfg and dev_cfg.device_name == device.get_iface():
            self.refresh_ui()

    def on_connection_added_or_removed(self, client, connection):
        dev_cfg = self.selected_dev_cfg()
        if not dev_cfg or not dev_cfg.device_name:
            return
        if connection.get_connection_type() == NM_CONNECTION_TYPE_WIFI \
                and connection.get_interface_name() == dev_cfg.device_name:
            self._refresh_configure_wireless_button(dev_cfg.device_name)

    def on_select_wireless_clicked(self, *args):
        # Get list of aps
        dev_cfg = self.selected_dev_cfg()
        if not dev_cfg:
            return

        device_name = dev_cfg.device_name

        # Run dialog
        dialog = SelectWirelessNetworksDialog(self.spoke.data, self.client)
        with self.spoke.main_window.enlightbox(dialog.window):
            dialog.refresh(device_name)
            dialog.run()

    def _get_wireless_connections_of_device(self, device):
        cons_ssids = []
        if device:
            for connection in _safe_device_filter_connections(device,
                                                              self.client.get_connections()):
                con_uuid = connection.get_setting_connection().get_uuid()
                con_ssid = b""
                wireless_setting = connection.get_setting_wireless()
                if wireless_setting:
                    ssid_variant = wireless_setting.get_ssid()
                    if ssid_variant:
                        con_ssid = ssid_variant.get_data()
                cons_ssids.append((con_uuid, con_ssid))
        return cons_ssids

    def on_edit_connection(self, *args):
        dev_cfg = self.selected_dev_cfg()
        if not dev_cfg:
            return

        device = self.client.get_device_by_iface(dev_cfg.device_name)
        con = self.client.get_connection_by_uuid(dev_cfg.connection_uuid)
        device_type = dev_cfg.device_type
        iface = dev_cfg.device_name
        activate = None
        selected_ssid = b""

        if device_type == NM.DeviceType.WIFI:

            con_uuid = ""
            cons_ssids = self._get_wireless_connections_of_device(device)
            if len(cons_ssids) == 1:
                con_uuid, selected_ssid = cons_ssids[0]

            if not con_uuid:
                # Run dialog
                dialog = ConfigureWirelessNetworksDialog(self.spoke.data, self.client)
                with self.spoke.main_window.enlightbox(dialog.window):
                    dialog.refresh(iface)
                    rc = dialog.run()
                    if rc != 1:
                        return

                    con_uuid = dialog.selected_uuid
                    selected_ssid = dialog.selected_ssid

            if not con_uuid:
                return

            con = self.client.get_connection_by_uuid(con_uuid)
            if not con:
                log.debug("on_edit_connection: connection %s for ap %s not found",
                          con_uuid, selected_ssid)
                return

            # 871132 auto activate wireless connection after editing if it is not
            # already activated (assume entering secrets)
            def restart_device_condition():
                ap = device.get_active_access_point()
                return not ap or ap.get_ssid().get_data() != selected_ssid

            activate = (con, device, restart_device_condition)
        else:
            if not con:
                log.debug("on_edit_connection: connection for device %s not found", iface)
                if device_type == NM.DeviceType.ETHERNET:
                    # Create default connection for the device and run nm-c-e on it
                    default_con = get_default_connection(iface, device_type, autoconnect=False)
                    persistent = False
                    log.info("creating new connection for %s device", iface)
                    self.client.add_connection_async(default_con, persistent, None,
                            self._default_connection_added_cb, activate)
                elif device_type in self.virtual_device_types:
                    # For virtual devices without connections, run nm-c-e to create one
                    log.info("no connection found for virtual device %s, launching nm-c-e to create one", iface)
                    # Get the connection type string for nm-connection-editor
                    type_map = {
                        NM.DeviceType.TEAM: "team",
                        NM.DeviceType.BOND: "bond",
                        NM.DeviceType.VLAN: "vlan",
                        NM.DeviceType.BRIDGE: "bridge"
                    }
                    connection_type = type_map.get(device_type)
                    if connection_type:
                        self._run_nmce_create(connection_type, activate)
                    return
                return

            if device and device.get_state() == NM.DeviceState.ACTIVATED:
                # Reactivate the connection after configuring it (if it changed)
                settings = con.to_dbus(NM.ConnectionSerializationFlags.ALL)
                settings_changed = lambda: settings != con.to_dbus(NM.ConnectionSerializationFlags.ALL)
                activate = (con, device, settings_changed)

        log.info("configuring connection %s device %s ssid %s",
                 con.get_uuid(), iface, selected_ssid)
        self._run_nmce(con.get_uuid(), activate)

    def _default_connection_added_cb(self, client, result, activate):
        con = client.add_connection_finish(result)
        uuid = con.get_setting_connection().get_uuid()
        log.info("configuring new connection %s", uuid)
        self._run_nmce(uuid, activate)

    def _run_nmce(self, uuid, activate):
        self.kill_nmce(msg="Configure button clicked")
        proc = startProgram(["nm-connection-editor", "--keep-above", "--edit", "%s" % uuid], reset_lang=False)
        self._running_nmce = proc

        PidWatcher().watch_process(proc.pid, self.on_nmce_exited, activate)

    def _run_nmce_create(self, connection_type, activate):
        self.kill_nmce(msg="Configure button clicked")
        proc = startProgram(["nm-connection-editor", "--keep-above", "--create", "--type=%s" % connection_type], reset_lang=False)
        self._running_nmce = proc

        PidWatcher().watch_process(proc.pid, self.on_nmce_exited, activate)



    def kill_nmce(self, msg=""):
        if not self._running_nmce:
            return False

        log.debug("killing running nm-c-e %s: %s", self._running_nmce.pid, msg)
        self._running_nmce.kill()
        self._running_nmce = None
        return True

    def on_nmce_exited(self, pid, condition, activate=None):
        # waitpid() has been called, make sure we don't do anything else with the proc
        self._running_nmce = None
        log.debug("nm-c-e exited with status %s", condition)

        # nm-c-e was closed normally, not killed by anaconda
        if condition == 0:
            if activate:
                # The default of None confuses pylint
                con, device, activate_condition = activate # pylint: disable=unpacking-non-sequence
                if activate_condition():
                    gtk_call_once(self._activate_connection_cb, con, device)
            self._network_module.LogConfigurationState("Connection Editor was run.")

    def _activate_connection_cb(self, con, device):
        self.client.activate_connection_async(con, device, None, None)
        if self.spoke:
            self.spoke.networking_changed = True

    def on_wireless_enabled(self, *args):
        switch = self.builder.get_object("device_wireless_off_switch")
        self._updating_device = True
        switch.set_active(self.client.wireless_get_enabled())
        self._updating_device = False

    def on_device_off_toggled(self, switch, *args):
        if self._updating_device:
            return

        active = switch.get_active()
        dev_cfg = self.selected_dev_cfg()
        if not dev_cfg:
            return
        device = self.client.get_device_by_iface(dev_cfg.device_name)
        con = self.client.get_connection_by_uuid(dev_cfg.connection_uuid)
        iface = dev_cfg.device_name

        log.info("device %s switched %s", iface, "on" if active else "off")

        if dev_cfg.device_type == NM.DeviceType.WIFI:
            self.client.wireless_set_enabled(active)
        else:
            if active:
                if not con:
                    log.debug("on_device_off_toggled: no connection for %s", iface)
                    return

                self.client.activate_connection_async(con, device, None, None)
            else:
                if not device:
                    log.debug("on_device_off_toggled: no device for %s", iface)
                    return
                device.disconnect(None)

        if self.spoke:
            self.spoke.networking_changed = True

    def on_add_device_clicked(self, *args):
        dialog = self.builder.get_object("add_device_dialog")
        with self.spoke.main_window.enlightbox(dialog):
            rc = dialog.run()
        dialog.hide()
        if rc == 1:
            ai = self.builder.get_object("combobox_add_device").get_active_iter()
            model = self.builder.get_object("liststore_add_device")
            dev_type = model[ai][1]
            self.add_device(dev_type)

    def on_remove_device_clicked(self, *args):
        selection = self.builder.get_object("treeview_devices").get_selection()
        model, itr = selection.get_selected()
        if not itr:
            return None
        dev_cfg = model[itr][DEVICES_COLUMN_OBJECT]
        con = self.client.get_connection_by_uuid(dev_cfg.connection_uuid)
        if con:
            con.delete()

    def on_apply_hostname(self, *args):
        self.emit("apply-hostname")

    def add_device(self, ty):
        log.info("adding device of type %s", ty)
        self._run_nmce_create(ty, activate=None)

    def selected_dev_cfg(self):
        selection = self.builder.get_object("treeview_devices").get_selection()
        model, itr = selection.get_selected()
        if not itr:
            return None
        return model[itr][DEVICES_COLUMN_OBJECT]

    def add_dev_cfg(self, dev_cfg):
        log.debug("adding device configuration: %s", dev_cfg)
        row = [None, None, None, dev_cfg]
        self._update_row_from_object(row)
        self.dev_cfg_store.append(row)

    def _update_row_from_object(self, row):
        dev_cfg = row[DEVICES_COLUMN_OBJECT]
        row[DEVICES_COLUMN_ICON_NAME] = self._dev_icon_name(dev_cfg)
        row[DEVICES_COLUMN_SORT] = self.device_type_sort_value.get(dev_cfg.device_type, "100")
        row[DEVICES_COLUMN_TITLE] = self._dev_title(dev_cfg)

    def watch_dev_cfg_device(self, dev_cfg):
        device = self.client.get_device_by_iface(dev_cfg.device_name)
        if device:
            device.connect("notify::ip4-config", self.on_ip_obj_changed, IPV4_CONFIG)
            device.connect("notify::ip6-config", self.on_ip_obj_changed, IPV6_CONFIG)
            device.connect("state-changed", self.on_device_state_changed)

    def remove_dev_cfg(self, dev_cfg):
        log.debug("removing device configuration: %s", dev_cfg)
        for row in self.dev_cfg_store:
            stored_cfg = row[DEVICES_COLUMN_OBJECT]
            if stored_cfg == dev_cfg:
                self.dev_cfg_store.remove(row.iter)
                return
        log.debug("configuration to be removed not found")

    def update_dev_cfg(self, old_cfg, new_cfg):
        log.debug("updating device configuration: %s -> %s", old_cfg, new_cfg)
        for row in self.dev_cfg_store:
            stored_cfg = row[DEVICES_COLUMN_OBJECT]
            if stored_cfg == old_cfg:
                row[DEVICES_COLUMN_OBJECT] = new_cfg
                self._update_row_from_object(row)
                return
        log.debug("configuration to be updated not found")

    def on_ip_obj_changed(self, device, *args):
        """Callback when ipX-config objects will be changed.

        Register callback on properties (IP address, gateway...) of these ipX-config
        objects when they are created.
        """
        log.debug("%s object changed", args[1])
        self.on_device_config_changed(device)
        if args[1] == IPV4_CONFIG:
            config = device.props.ip4_config
        else:
            config = device.props.ip6_config

        if config:
            # register callback when inner NMIP[4,6]Config object changed
            config.connect("notify::addresses", self.on_config_changed, device)
            config.connect("notify::gateway", self.on_config_changed, device)
            config.connect("notify::nameservers", self.on_config_changed, device)

    def on_config_changed(self, config, *args):
        """Callback on property change of ipX-config objects.

        Call method which show changed properties (IP, gateway...) to an user.
        """
        self.on_device_config_changed(args[1])

    def _dev_icon_name(self, dev_cfg):
        icon_name = ""
        if dev_cfg.device_type in self.wired_ui_device_types:
            device = self.client.get_device_by_iface(dev_cfg.device_name)
            if device:
                if device.get_state() == NM.DeviceState.UNAVAILABLE:
                    icon_name = "network-wired-disconnected-symbolic"
                else:
                    icon_name = "network-wired-symbolic"
            else:
                icon_name = "network-wired-disconnected-symbolic"
        elif dev_cfg.device_type == NM.DeviceType.WIFI:
            icon_name = "network-wireless-symbolic"

        return icon_name

    def _dev_title(self, dev_cfg):
        unplugged = ''
        device = self.client.get_device_by_iface(dev_cfg.device_name)

        if device:
            if (device.get_state() == NM.DeviceState.UNAVAILABLE
                and device.get_device_type() == NM.DeviceType.ETHERNET
                and not device.get_carrier()):
                # TRANSLATORS: ethernet cable is unplugged
                unplugged = ', <i>%s</i>' % escape_markup(_("unplugged"))
        connection_name = ""
        if dev_cfg.device_type in self.virtual_device_types:
            con = self.client.get_connection_by_uuid(dev_cfg.connection_uuid)
            if con:
                con_id = con.get_setting_connection().get_id()
                if con_id:
                    connection_name = " - {}".format(con_id)
        # pylint: disable=unescaped-markup
        title = '<span size="large">%s%s (%s%s)</span>' % \
                 (escape_markup(_(self.device_type_name.get(dev_cfg.device_type, ""))),
                  escape_markup(connection_name),
                  escape_markup(dev_cfg.device_name),
                  unplugged)

        if device:
            title += '\n<span size="small">%s %s</span>' % \
                    (escape_markup(device.get_vendor() or ""),
                     escape_markup(device.get_product() or ""))
        return title

    def refresh_ui(self, state=None):

        dev_cfg = self.selected_dev_cfg()
        if not dev_cfg:
            # the list is empty (no supported devices)
            notebook = self.builder.get_object("notebook_types")
            notebook.set_current_page(5)
            return

        self._refresh_device_type_page(dev_cfg)
        self._refresh_header_ui(dev_cfg, state)
        self._refresh_ports(dev_cfg)
        self._refresh_parent_vlanid(dev_cfg)
        self._refresh_speed_hwaddr(dev_cfg, state)
        self._refresh_ap(dev_cfg, state)
        self._refresh_device_cfg(dev_cfg)

    def _refresh_device_cfg(self, dev_cfg):

        if dev_cfg.device_type in self.wired_ui_device_types:
            dt = "wired"
        elif dev_cfg.device_type  == NM.DeviceType.WIFI:
            dt = "wireless"
        else:
            return

        device = self.client.get_device_by_iface(dev_cfg.device_name)
        if device:
            ipv4cfg = device.get_ip4_config()
            ipv6cfg = device.get_ip6_config()
        else:
            ipv4cfg = ipv6cfg = None

        if ipv4cfg:
            addr_str = " ".join("%s/%d" % (a.get_address(), a.get_prefix())
                                           for a in ipv4cfg.get_addresses())
            gateway_str = ipv4cfg.get_gateway()
            dnss_str = " ".join(ipv4cfg.get_nameservers())
        else:
            addr_str = dnss_str = gateway_str = None
        self._set_device_info_value(dt, "ipv4", addr_str)
        self._set_device_info_value(dt, "dns", dnss_str)
        self._set_device_info_value(dt, "route", gateway_str)

        addr6_str = ""
        if ipv6cfg:
            addr6_str = " ".join("%s/%d" % (a.get_address(), a.get_prefix())
                                            for a in ipv6cfg.get_addresses()
                                            # Do not display link-local addresses
                                            if not a.get_address().startswith("fe80:"))
        self._set_device_info_value(dt, "ipv6", addr6_str.strip() or None)

        if ipv4cfg and addr6_str:
            self.builder.get_object("heading_%s_ipv4" % dt).set_label(_("IPv4 Address"))
            self.builder.get_object("heading_%s_ipv6" % dt).set_label(_("IPv6 Address"))
        elif ipv4cfg:
            self.builder.get_object("heading_%s_ipv4" % dt).set_label(_("IP Address"))
        elif addr6_str:
            self.builder.get_object("heading_%s_ipv6" % dt).set_label(_("IP Address"))

        return False

    def _refresh_ap(self, dev_cfg, state=None):
        if dev_cfg.device_type != NM.DeviceType.WIFI:
            return

        device = self.client.get_device_by_iface(dev_cfg.device_name)
        if state is None:
            state = device.get_state()
        active_ssid = b""
        if state == NM.DeviceState.UNAVAILABLE:
            ap_str = None
        else:
            active_ap = device.get_active_access_point()
            if active_ap:
                ap_str = self._ap_security_string(active_ap)
                active_ssid = active_ap.get_ssid().get_data()
            else:
                ap_str = ""

        self._set_device_info_value("wireless", "security", ap_str)

        if state == NM.DeviceState.UNAVAILABLE:
            self.builder.get_object("heading_wireless_network_name").hide()
            self.builder.get_object("label_wireless_network_name").hide()
        else:
            self.builder.get_object("heading_wireless_network_name").show()
            self.builder.get_object("label_wireless_network_name").show()
        selected_network_label = self.builder.get_object("label_wireless_network_name")
        ssid_str = NM.utils_ssid_to_utf8(active_ssid)
        selected_network_label.set_label(ssid_str)

    def _refresh_ports(self, dev_cfg):
        if dev_cfg.device_type in [NM.DeviceType.BOND,
                                   NM.DeviceType.TEAM,
                                   NM.DeviceType.BRIDGE]:
            ports = ""
            device = self.client.get_device_by_iface(dev_cfg.device_name)
            if device:
                ports = ",".join(s.get_iface() for s in device.get_slaves())
            self._set_device_info_value("wired", "ports", ports)

    def _refresh_parent_vlanid(self, dev_cfg):
        if dev_cfg.device_type == NM.DeviceType.VLAN:
            parent = ""
            vlanid = ""
            device = self.client.get_device_by_iface(dev_cfg.device_name)
            if device:
                vlanid = device.get_vlan_id()
                parent = device.get_parent() or ""
                if parent:
                    parent = parent.get_iface()
            else:
                con = self.client.get_connection_by_uuid(dev_cfg.connection_uuid)
                if con:
                    vlanid = con.get_setting_vlan().get_id()
                    parent = con.get_setting_vlan().get_parent()
            self._set_device_info_value("wired", "vlanid", str(vlanid))
            self._set_device_info_value("wired", "parent", parent)

    def _refresh_speed_hwaddr(self, dev_cfg, state=None):
        dev_type = dev_cfg.device_type
        if dev_type in self.wired_ui_device_types:
            dt = "wired"
        elif dev_type == NM.DeviceType.WIFI:
            dt = "wireless"
        else:
            return

        device = self.client.get_device_by_iface(dev_cfg.device_name)

        # Speed
        speed = None
        if device:
            if dev_type == NM.DeviceType.ETHERNET:
                speed = device.get_speed()
            elif dev_type == NM.DeviceType.WIFI:
                speed = device.get_bitrate() / 1000

        if state is None and device:
            state = device.get_state()

        if not device or state == NM.DeviceState.UNAVAILABLE:
            speed_str = None
        elif speed:
            speed_str = _("%d Mb/s") % speed
        else:
            speed_str = ""
        self._set_device_info_value(dt, "speed", speed_str)

        # Hardware address
        hwaddr = device and device.get_hw_address()
        self._set_device_info_value(dt, "mac", hwaddr)

    def _refresh_device_type_page(self, dev_cfg):
        dev_type = dev_cfg.device_type
        notebook = self.builder.get_object("notebook_types")
        if dev_type == NM.DeviceType.ETHERNET:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_ports").hide()
            self.builder.get_object("label_wired_ports").hide()
            self.builder.get_object("heading_wired_vlanid").hide()
            self.builder.get_object("label_wired_vlanid").hide()
            self.builder.get_object("heading_wired_parent").hide()
            self.builder.get_object("label_wired_parent").hide()
            self.builder.get_object("remove_toolbutton").set_sensitive(False)
        elif dev_type in [NM.DeviceType.BOND,
                          NM.DeviceType.TEAM,
                          NM.DeviceType.BRIDGE]:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_ports").show()
            self.builder.get_object("label_wired_ports").show()
            self.builder.get_object("heading_wired_vlanid").hide()
            self.builder.get_object("label_wired_vlanid").hide()
            self.builder.get_object("heading_wired_parent").hide()
            self.builder.get_object("label_wired_parent").hide()
            self.builder.get_object("remove_toolbutton").set_sensitive(True)
        elif dev_type == NM.DeviceType.VLAN:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_ports").hide()
            self.builder.get_object("label_wired_ports").hide()
            self.builder.get_object("heading_wired_vlanid").show()
            self.builder.get_object("label_wired_vlanid").show()
            self.builder.get_object("heading_wired_parent").show()
            self.builder.get_object("label_wired_parent").show()
            self.builder.get_object("remove_toolbutton").set_sensitive(True)
        elif dev_type == NM.DeviceType.WIFI:
            notebook.set_current_page(1)
            self._refresh_configure_wireless_button(dev_cfg.device_name)

    def _refresh_configure_wireless_button(self, device_name):
        device = self.client.get_device_by_iface(device_name)
        connection_exists = bool(self._get_wireless_connections_of_device(device))
        self.builder.get_object("button_wireless_options").set_sensitive(connection_exists)

    def _refresh_carrier_info(self):
        for row in self.dev_cfg_store:
            row[DEVICES_COLUMN_TITLE] = self._dev_title(row[DEVICES_COLUMN_OBJECT])

    def _refresh_header_ui(self, dev_cfg, state=None):
        if dev_cfg.device_type in self.wired_ui_device_types:
            dev_type_str = "wired"
        elif dev_cfg.device_type == NM.DeviceType.WIFI:
            dev_type_str = "wireless"
        else:
            return

        if dev_type_str == "wired":
            # update icon according to device status
            img = self.builder.get_object("image_wired_device")
            img.set_from_icon_name(self._dev_icon_name(dev_cfg), Gtk.IconSize.LARGE_TOOLBAR)

        # TODO: is this necessary? Isn't it static from glade?
        device_type_label = _(self.device_type_name.get(dev_cfg.device_type, ""))
        self.builder.get_object("label_%s_device" % dev_type_str).set_label(
            "%s (%s)" % (device_type_label, dev_cfg.device_name))

        device = self.client.get_device_by_iface(dev_cfg.device_name)
        if state is None:
            if not device:
                state = NM.DeviceState.DISCONNECTED
            else:
                state = device.get_state()

        self.builder.get_object("label_%s_status" % dev_type_str).set_label(
            localized_string_of_device_state(device, state))

        switch = self.builder.get_object("device_%s_off_switch" % dev_type_str)
        if dev_type_str == "wired":
            visible = state not in (NM.DeviceState.UNAVAILABLE, NM.DeviceState.UNMANAGED)
            switch.set_visible(visible)
            switch.set_no_show_all(not visible)
            self._updating_device = True
            switch.set_active(state not in (NM.DeviceState.UNMANAGED,
                                            NM.DeviceState.UNAVAILABLE,
                                            NM.DeviceState.DISCONNECTED,
                                            NM.DeviceState.DEACTIVATING,
                                            NM.DeviceState.FAILED))
            self._updating_device = False
        elif dev_type_str == "wireless":
            self.on_wireless_enabled()

    def _set_device_info_value(self, dev_type_str, info, value_str):
        heading = self.builder.get_object("heading_%s_%s" % (dev_type_str, info))
        value_label = self.builder.get_object("label_%s_%s" % (dev_type_str, info))
        if value_str is None:
            really_hide(heading)
            really_hide(value_label)
        else:
            really_show(heading)
            really_show(value_label)
            value_label.set_label(value_str)

    def _ap_security_string(self, ap):

        flags = ap.get_flags()
        wpa_flags = ap.get_wpa_flags()
        rsn_flags = ap.get_rsn_flags()

        sec_str = ""

        if ((flags & NM._80211ApFlags.PRIVACY) and
            wpa_flags == NM._80211ApSecurityFlags.NONE and
            rsn_flags == NM._80211ApSecurityFlags.NONE):
            sec_str += "%s, " % _("WEP")

        if wpa_flags != NM._80211ApSecurityFlags.NONE:
            sec_str += "%s, " % _("WPA")

        if rsn_flags != NM._80211ApSecurityFlags.NONE:
            sec_str += "%s, " % _("WPA2")

        if ((wpa_flags & NM._80211ApSecurityFlags.KEY_MGMT_802_1X) or
            (rsn_flags & NM._80211ApSecurityFlags.KEY_MGMT_802_1X)):
            sec_str += "%s, " % _("Enterprise")

        if sec_str:
            sec_str = sec_str[:-2]
        else:
            sec_str = _("None")

        return sec_str

    @property
    def hostname(self):
        return self.entry_hostname.get_text()

    @hostname.setter
    def hostname(self, value):
        if not value:
            return
        self.entry_hostname.set_text(value)

    def set_current_hostname(self):
        value = self._network_module.GetCurrentHostname()

        if not value:
            return

        self.label_current_hostname.set_text(value)

    def disconnect_client_callbacks(self):
        if not self.client:
            return

        for cb in [self.on_wireless_enabled, self.on_nm_state_changed]:
            _try_disconnect(self.client, cb)

        for device in self.client.get_devices():
            _try_disconnect(device, self.on_device_config_changed)
            _try_disconnect(device, self.on_device_state_changed)
            _try_disconnect(device, self.on_ip_obj_changed)
            for config in self._get_ip_configs(device):
                _try_disconnect(config, self.on_config_changed)

        self._network_module.DeviceConfigurationChanged.disconnect(
            self.on_device_configurations_changed
        )

    def _get_ip_configs(self, device):
        out = []
        try:
            out.append(self.props.ip4_config)
        except AttributeError:
            pass
        try:
            out.append(self.props.ip6_config)
        except AttributeError:
            pass

        return out


def _try_disconnect(obj, callback):
    try:
        obj.disconnect_by_func(callback)
    except TypeError as e:
        if "nothing connected" not in str(e):
            log.debug("%s", e)


class ConfigureWirelessNetworksDialog(GUIObject):
    builderObjects = ["configure_wireless_network_dialog",
                      "liststore_configure_wireless_network"]
    mainWidgetName = "configure_wireless_network_dialog"
    uiFile = "spokes/network.glade"

    def __init__(self, data, nm_client):
        super().__init__(data)
        self._nm_client = nm_client

        self.window.set_size_request(500, 300)
        self._store = self.builder.get_object("liststore_configure_wireless_network")
        self._store.set_sort_column_id(CONFIGURE_WIRELESS_COLUMN_SSID_STR, Gtk.SortType.ASCENDING)
        self._treeview = self.builder.get_object("configure_wireless_network_treeview")
        selection = self._treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.BROWSE)
        self._configure_button = self.builder.get_object("wireless_configure_button")
        selection.connect("changed", self.on_selection_changed)
        self.on_selection_changed(selection)

    def on_selection_changed(self, selection):
        _model, itr = selection.get_selected()
        self._configure_button.set_sensitive(bool(itr))

    @property
    def selected_uuid(self):
        uuid = ""
        selection = self._treeview.get_selection()
        model, itr = selection.get_selected()
        if itr:
            uuid = model[itr][CONFIGURE_WIRELESS_COLUMN_CON_UUID]
        return uuid

    @property
    def selected_ssid(self):
        ssid = ""
        selection = self._treeview.get_selection()
        model, itr = selection.get_selected()
        if itr:
            ssid = model[itr][CONFIGURE_WIRELESS_COLUMN_SSID]
        return ssid

    # pylint: disable=arguments-differ
    def refresh(self, device_name):
        device = self._nm_client.get_device_by_iface(device_name)
        if not device:
            log.warnig("device for interface %s not found", device)
            return

        cons = _safe_device_filter_connections(device, self._nm_client.get_connections())

        # Update model
        self._store.clear()
        for con in cons:
            self._add_connection(con)

    def _add_connection(self, connection):
        wireless_setting = connection.get_setting_wireless()
        if not wireless_setting:
            return

        ssid = wireless_setting.get_ssid()
        if not ssid:
            # get_ssid can return None if AP does not broadcast.
            return

        ssid = ssid.get_data()
        if not ssid:
            return

        ssid_str = NM.utils_ssid_to_utf8(ssid)

        con_id = connection.get_setting_connection().get_id()

        con_uuid = connection.get_setting_connection().get_uuid()

        # the third column is for sorting
        self._store.append([ssid, ssid_str, con_id, con_uuid])

    def run(self):
        self.window.show()
        rc = self.window.run()
        self.window.hide()

        return rc


class SelectWirelessNetworksDialog(GUIObject):
    builderObjects = ["select_wireless_network_dialog", "liststore_wireless_network"]
    mainWidgetName = "select_wireless_network_dialog"
    uiFile = "spokes/network.glade"

    def __init__(self, data, nm_client):
        super().__init__(data)
        self._nm_client = nm_client
        self._device_name = None

        self.window.set_size_request(500, 300)
        self._store = self.builder.get_object("liststore_wireless_network")
        self._store.set_sort_column_id(SELECT_WIRELESS_COLUMN_STRENGTH, Gtk.SortType.DESCENDING)
        self._treeview = self.builder.get_object("select_wireless_network_treeview")
        selection = self._treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.BROWSE)
        self._connect_button = self.builder.get_object("wireless_connect_button")
        selection.connect("changed", self.on_selection_changed)
        self.on_selection_changed(selection)
        self._add_treeview_columns(self._treeview)

    def on_selection_changed(self, selection):
        _model, itr = selection.get_selected()
        self._connect_button.set_sensitive(bool(itr))

    def _add_treeview_columns(self, treeview):
        col = Gtk.TreeViewColumn("Ssid")
        ssid = Gtk.CellRendererText()
        active = CellRendererSelected()
        active.set_alignment(1, 0.5)
        col.pack_start(ssid, False)
        col.pack_start(active, True)
        col.add_attribute(ssid, "text", SELECT_WIRELESS_COLUMN_SSID_STR)
        col.add_attribute(active, "selected", SELECT_WIRELESS_COLUMN_ACTIVE)
        col.set_expand(True)
        treeview.append_column(col)

        rnd = CellRendererSecurity()
        rnd.set_padding(4, 0)
        col = Gtk.TreeViewColumn("Security", rnd, security=SELECT_WIRELESS_COLUMN_SECURITY)
        treeview.append_column(col)

        rnd = CellRendererSignalStrength()
        col = Gtk.TreeViewColumn("Strength", rnd, signal=SELECT_WIRELESS_COLUMN_STRENGTH)
        treeview.append_column(col)

    @property
    def selected_ssid(self):
        ssid = b""
        selection = self._treeview.get_selection()
        model, itr = selection.get_selected()
        if itr:
            ssid = model[itr][SELECT_WIRELESS_COLUMN_SSID]
        return ssid

    def _get_strongest_unique_aps(self, access_points):
        strongest_aps = {}
        for ap in access_points:
            if not ap.get_ssid():
                # non-broadcasting AP. We don't do anything with these
                continue
            ssid = ap.get_ssid().get_data()
            if ssid in strongest_aps:
                if ap.get_strength() > strongest_aps[ssid].get_strength():
                    strongest_aps[ssid] = ap
            else:
                strongest_aps[ssid] = ap

        return strongest_aps.values()

    # pylint: disable=arguments-differ
    def refresh(self, device_name):
        device = self._nm_client.get_device_by_iface(device_name)
        if not device:
            log.warnig("device for interface %s not found", device)
            return

        self._device_name = device_name

        aps = self._get_strongest_unique_aps(device.get_access_points())

        active_ap = device.get_active_access_point()
        if active_ap:
            active_ssid = active_ap.get_ssid().get_data()
        else:
            active_ssid = b""

        # Update model
        self._store.clear()
        for ap in aps:
            self._add_ap(ap, active_ssid)

    def _add_ap(self, ap, active_ssid):
        ssid = ap.get_ssid()
        if not ssid:
            # get_ssid can return None if AP does not broadcast.
            return

        ssid = ssid.get_data()
        if not ssid:
            return

        mode = ap.get_mode()
        if not mode:
            return

        security = self._ap_security(ap)

        ssid_str = NM.utils_ssid_to_utf8(ssid)

        active = ssid == active_ssid

        # the third column is for sorting
        self._store.append([ssid, ssid_str, ssid_str, ap.get_strength(), mode, security, active])

    def _ap_security(self, ap):
        ty = NM_AP_SEC_UNKNOWN

        flags = ap.get_flags()
        wpa_flags = ap.get_wpa_flags()
        rsn_flags = ap.get_rsn_flags()

        if not flags & NM._80211ApFlags.PRIVACY \
                and wpa_flags == NM._80211ApSecurityFlags.NONE \
                and rsn_flags == NM._80211ApSecurityFlags.NONE:
            ty = NM_AP_SEC_NONE
        elif flags & NM._80211ApFlags.PRIVACY \
                and wpa_flags == NM._80211ApSecurityFlags.NONE \
                and rsn_flags == NM._80211ApSecurityFlags.NONE:
            ty = NM_AP_SEC_WEP
        elif not flags & NM._80211ApFlags.PRIVACY \
                and wpa_flags != NM._80211ApSecurityFlags.NONE \
                and rsn_flags != NM._80211ApSecurityFlags.NONE:
            ty = NM_AP_SEC_WPA
        else:
            ty = NM_AP_SEC_WPA2

        return ty

    def run(self):
        self.window.show()
        rc = self.window.run()
        self.window.hide()

        if rc == 1:
            ssid = self.selected_ssid
            if ssid:
                log.info("selected access point to be activated: %s", ssid)
                device = self._nm_client.get_device_by_iface(self._device_name)
                if device:
                    self._activate_wireless_network(device, ssid)
                else:
                    log.warnig("device for interface %s not found", device)

        return rc

    def _activate_wireless_network(self, device, ssid):
        ap = self._get_strongest_ap_for_ssid(device.get_access_points(), ssid)
        if not ap:
            return

        cons = _safe_device_filter_connections(device, self._nm_client.get_connections())
        cons = _safe_ap_filter_connections(ap, cons)
        if cons:
            con = cons[0]
            self._nm_client.activate_connection_async(con, device, ap.get_path(), None)
        else:
            if self._ap_is_enterprise(ap):
                # Create a connection for the ap and [Configure] it later with nm-c-e
                ssid_str = NM.utils_ssid_to_utf8(ssid)
                con = NM.SimpleConnection.new()
                s_con = NM.SettingConnection.new()
                s_con.set_property('uuid', str(uuid4()))
                s_con.set_property('id', ssid_str)
                s_con.set_property('type', NM_CONNECTION_TYPE_WIFI)
                s_wireless = NM.SettingWireless.new()
                s_wireless.set_property('ssid', ap.get_ssid())
                s_wireless.set_property('mode', 'infrastructure')
                con.add_setting(s_con)
                con.add_setting(s_wireless)
                persistent = True
                log.debug("adding connection for WPA-Enterprise AP %s", ssid_str)
                self._nm_client.add_connection_async(con, persistent, None)
            else:
                self._nm_client.add_and_activate_connection_async(
                    None, device, ap.get_path(), None)

    def _ap_is_enterprise(self, ap):
        wpa_flags = ap.get_wpa_flags()
        rsn_flags = ap.get_rsn_flags()
        return ((wpa_flags & NM._80211ApSecurityFlags.KEY_MGMT_802_1X) or
                (rsn_flags & NM._80211ApSecurityFlags.KEY_MGMT_802_1X))

    def _get_strongest_ap_for_ssid(self, access_points, ssid):
        strongest_ap = None
        for ap in access_points:
            if not ap.get_ssid():
                # non-broadcasting AP. We don't do anything with these
                continue
            if ap.get_ssid().get_data() == ssid:
                if not strongest_ap or strongest_ap.get_strength() < ap.get_strength():
                    strongest_ap = ap

        return strongest_ap


class NetworkSpoke(FirstbootSpokeMixIn, NormalSpoke):
    """
       .. inheritance-diagram:: NetworkSpoke
          :parts: 3
    """
    builderObjects = ["networkWindow", "liststore_devices", "add_device_dialog",
                      "liststore_add_device"]
    mainWidgetName = "networkWindow"
    uiFile = "spokes/network.glade"
    title = CN_("GUI|Spoke", "_Network & Host Name")
    icon = "network-transmit-receive-symbolic"
    category = SystemCategory

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "network-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Should the spoke run?"""
        if not FirstbootSpokeMixIn.should_run(environment, data):
            return False

        # Always allow to configure the hostname for the target system.
        return True

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self.networking_changed = False
        self._network_module = NETWORK.get_proxy()
        self._nm_client = network.get_nm_client()
        self.network_control_box = NetworkControlBox(self.builder, self._nm_client, self._network_module, spoke=self)
        self.network_control_box.hostname = self._network_module.Hostname
        self.network_control_box.set_current_hostname()
        self._network_module.CurrentHostnameChanged.connect(self._hostname_changed)
        self.network_control_box.connect("nm-state-changed",
                                         self.on_nm_state_changed)
        self.network_control_box.connect("device-state-changed",
                                         self.on_device_state_changed)
        self.network_control_box.connect("apply-hostname",
                                         self.on_apply_hostname)

    def _hostname_changed(self, hostname):
        gtk_call_once(self._update_hostname)

    def apply(self):
        # Inform network module that device configurations might have been changed
        # and we want to generate kickstart from device configurations
        # (persistent NM / config files configuration), instead of using original kickstart.
        self._network_module.NetworkDeviceConfigurationChanged()
        self._network_module.Hostname = self.network_control_box.hostname

        # if installation media or hdd aren't used and settings have changed
        # try if source is available
        if self.networking_changed:
            if self.payload and self.payload.needs_network:
                if ANACONDA_ENVIRON in anaconda_flags.environs:
                    log.debug(
                        "network spoke (apply), network configuration changed - "
                        "restarting payload thread"
                    )
                    from pyanaconda.payload.manager import payloadMgr
                    payloadMgr.start(self.payload, only_on_change=True)
                else:
                    log.debug(
                        "network spoke (apply), network configuration changed - "
                        "skipping restart of payload thread, outside of Anaconda environment"
                    )
            else:
                log.debug(
                    "network spoke (apply), network configuration changed - "
                    "skipping restart of payload thread, payload does not need network"
                )

        self.networking_changed = False
        self.network_control_box.kill_nmce(msg="leaving network spoke")

    @property
    def completed(self):
        # TODO: check also if source requires updates when implemented
        # If we can't configure network, don't require it
        return (not conf.system.can_configure_network
                or self._network_module.IsConnecting()
                or self._network_module.Connected)

    @property
    def mandatory(self):
        # the network spoke should be mandatory only if it is running
        # during the installation and if the installation source requires network
        return ANACONDA_ENVIRON in anaconda_flags.environs and self.payload.needs_network

    @property
    def status(self):
        """ A short string describing which devices are connected. """
        return network.status_message(self._nm_client)

    def initialize(self):
        register_secret_agent(self)
        NormalSpoke.initialize(self)
        self.initialize_start()
        self.network_control_box.initialize()
        if not conf.system.can_configure_network or not self._nm_client:
            self.builder.get_object("network_config_vbox").set_no_show_all(True)
            self.builder.get_object("network_config_vbox").hide()
        else:
            self.builder.get_object("live_hint_label").set_no_show_all(True)
            self.builder.get_object("live_hint_label").hide()

        # report that we are done
        self.initialize_done()

    def refresh(self):
        NormalSpoke.refresh(self)
        self.network_control_box.refresh()
        self.network_control_box.set_current_hostname()

    def on_nm_state_changed(self, *args):
        gtk_call_once(self._update_status)
        # TODO MOD replace and test - will NM updating hostname from dhcp being
        # estabilished be propagated to module via hostnamed?
        gtk_call_once(self._update_hostname)

    def on_device_state_changed(self, source, device, new_state, *args):
        if new_state in (NM.DeviceState.ACTIVATED,
                         NM.DeviceState.DISCONNECTED,
                         NM.DeviceState.UNAVAILABLE):
            gtk_call_once(self._update_status)

    def on_apply_hostname(self, *args):
        hostname = self.network_control_box.hostname
        (valid, error) = network.is_valid_hostname(hostname, local=True)
        if hostname and not valid:
            self.clear_info()
            msg = _("Host name is not valid: %s") % error
            self.set_warning(msg)
            self.network_control_box.entry_hostname.grab_focus()
        else:
            self.clear_info()
            if conf.system.can_change_hostname:
                self._network_module.SetCurrentHostname(hostname)

    def _update_status(self):
        hubQ.send_message(self.__class__.__name__, self.status)

    def _update_hostname(self):
        self.network_control_box.set_current_hostname()

    def on_back_clicked(self, button):
        hostname = self.network_control_box.hostname
        (valid, error) = network.is_valid_hostname(hostname, local=True)
        if hostname and not valid:
            self.clear_info()
            msg = _("Host name is not valid: %s") % error
            self.set_warning(msg)
            self.network_control_box.entry_hostname.grab_focus()
        else:
            self.clear_info()
            NormalSpoke.on_back_clicked(self, button)

    def finished(self):
        """Disconnect callbacks

        Called when leaving summary hub
        """
        self.network_control_box.kill_nmce(msg="finished with network spoke")
        self.network_control_box.disconnect_client_callbacks()


class NetworkStandaloneSpoke(StandaloneSpoke):
    """
       .. inheritance-diagram:: NetworkStandaloneSpoke
          :parts: 3
    """
    builderObjects = ["networkStandaloneWindow", "networkControlBox_vbox",
                      "liststore_devices", "add_device_dialog", "liststore_add_device"]
    mainWidgetName = "networkStandaloneWindow"
    uiFile = "spokes/network.glade"

    preForHub = SummaryHub
    priority = 10

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "network-pre-configuration"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._network_module = NETWORK.get_proxy()
        self._nm_client = network.get_nm_client()
        self.network_control_box = NetworkControlBox(self.builder, self._nm_client, self._network_module, spoke=self)

        self.network_control_box.hostname = self._network_module.Hostname
        self.network_control_box.set_current_hostname()
        self._network_module.CurrentHostnameChanged.connect(self._hostname_changed)

        parent = self.builder.get_object("AnacondaStandaloneWindow-action_area5")
        parent.add(self.network_control_box.vbox)

        self.network_control_box.connect("nm-state-changed",
                                         self.on_nm_state_changed)
        self.network_control_box.connect("apply-hostname",
                                         self.on_apply_hostname)

        self._initially_available = self.completed
        log.debug("network standalone spoke (init): completed: %s", self._initially_available)
        self._now_available = False

    def _hostname_changed(self, hostname):
        gtk_call_once(self._update_hostname)

    def apply(self):
        # Inform network module that device configurations might have been changed
        # and we want to generate kickstart from device configurations
        # (persistent NM / config files configuration), instead of using original kickstart.
        self._network_module.NetworkDeviceConfigurationChanged()
        self._network_module.Hostname = self.network_control_box.hostname

        self._now_available = self.completed

        log.debug("network standalone spoke (apply) payload: %s completed: %s",
                  self.payload.is_ready(), self._now_available)

        if (not self.payload.is_ready() and not self._initially_available
            and self._now_available and self.payload.needs_network):
            from pyanaconda.payload.manager import payloadMgr
            payloadMgr.start(self.payload)

        self.network_control_box.kill_nmce(msg="leaving standalone network spoke")
        self.network_control_box.disconnect_client_callbacks()

    @property
    def completed(self):
        return (not conf.system.can_configure_network
                or self._network_module.Connected
                or self._network_module.IsConnecting()
                or not (self.payload.source_type != conf.payload.default_source
                        and self.payload.needs_network))

    def initialize(self):
        register_secret_agent(self)
        super().initialize()
        self.network_control_box.initialize()

    def refresh(self):
        super().refresh()
        self.network_control_box.refresh()
        self.network_control_box.set_current_hostname()

    def _on_continue_clicked(self, window, user_data=None):
        hostname = self.network_control_box.hostname
        (valid, error) = network.is_valid_hostname(hostname, local=True)
        if hostname and not valid:
            self.clear_info()
            msg = _("Host name is not valid: %s") % error
            self.set_warning(msg)
            self.network_control_box.entry_hostname.grab_focus()
        else:
            self.clear_info()
            StandaloneSpoke._on_continue_clicked(self, window, user_data)

    # Use case: slow dhcp has connected when on spoke
    def on_nm_state_changed(self, *args):
        # TODO MOD replace and test - will NM updating hostname from dhcp being
        # estabilished be propagated to module via hostnamed?
        gtk_call_once(self._update_hostname)

    def on_apply_hostname(self, *args):
        hostname = self.network_control_box.hostname
        (valid, error) = network.is_valid_hostname(hostname, local=True)
        if hostname and not valid:
            self.clear_info()
            msg = _("Host name is not valid: %s") % error
            self.set_warning(msg)
            self.network_control_box.entry_hostname.grab_focus()
        else:
            self.clear_info()
            if conf.system.can_change_hostname:
                self._network_module.SetCurrentHostname(hostname)

    def _update_hostname(self):
        self.network_control_box.set_current_hostname()


def _safe_device_filter_connections(device, connections):
    # Do not use device.filter_connections, rhbz#1873561
    return [c for c in connections if device.connection_valid(c)]


def _safe_ap_filter_connections(ap, connections):
    # Do not use ap.filter_connections, rhbz#1873561
    return [c for c in connections if ap.connection_valid(c)]
