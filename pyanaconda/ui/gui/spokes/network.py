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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
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

from gi.repository import Gtk
from gi.repository import GObject, Pango, Gio, NM

from pyanaconda.core.i18n import _, N_, C_, CN_
from pyanaconda.flags import flags as anaconda_flags
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke, StandaloneSpoke
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.utils import gtk_call_once, escape_markup, really_hide, really_show
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.util import startProgram
from pyanaconda.core.process_watchers import PidWatcher
from pyanaconda.core.constants import ANACONDA_ENVIRON
from pyanaconda.core import glib
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.structures.network import NetworkDeviceConfiguration
from pyanaconda.dbus.structure import apply_structure

from pyanaconda import network

import dbus
import dbus.service
# Used for ascii_letters and hexdigits constants
import string # pylint: disable=deprecated-module
from uuid import uuid4

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

NM._80211ApFlags = getattr(NM, "80211ApFlags")
NM._80211ApSecurityFlags = getattr(NM, "80211ApSecurityFlags")
NM._80211Mode = getattr(NM, "80211Mode")

NM_SERVICE = "org.freedesktop.NetworkManager"
NM_SECRET_AGENT_GET_SECRETS_FLAG_ALLOW_INTERACTION = 0x1
SECRET_AGENT_IFACE = 'org.freedesktop.NetworkManager.SecretAgent'
AGENT_MANAGER_IFACE = 'org.freedesktop.NetworkManager.AgentManager'
AGENT_MANAGER_PATH = "/org/freedesktop/NetworkManager/AgentManager"

IPV4_CONFIG = "IPv4"
IPV6_CONFIG = "IPv6"

DEVICES_COLUMN_ICON_NAME = 0
DEVICES_COLUMN_SORT = 1
DEVICES_COLUMN_TITLE = 2
DEVICES_COLUMN_OBJECT = 3

nmclient = NM.Client.new()

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

class CellRendererSignal(Gtk.CellRendererPixbuf):

    __gtype_name__ = "CellRendererSignal"
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
                                  "combobox_wireless_network_name"]
        do_not_show_in_refresh += ["%s_%s_%s" % (widget, ty, value)
                                   for widget in ["heading", "label"]
                                   for ty in ["wired", "wireless"]
                                   for value in ["ipv4", "ipv6", "dns", "route"]]
        do_not_show_in_refresh += ["%s_wired_%s" % (widget, value)
                                   for widget in ["heading", "label"]
                                   for value in ["slaves", "vlanid", "parent"]]

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

        # wireless APs list
        combobox = self.builder.get_object("combobox_wireless_network_name")
        self._add_ap_icons(combobox)
        model = combobox.get_model()
        model.set_sort_column_id(2, Gtk.SortType.ASCENDING)
        combobox.connect("changed", self.on_wireless_ap_changed_cb)
        self.selected_ap = None

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

    @property
    def vbox(self):
        return self.builder.get_object("networkControlBox_vbox")


    def _add_ap_icons(self, combobox):
        cell = CellRendererSecurity()
        cell.set_padding(4, 0)
        combobox.pack_start(cell, False)
        combobox.add_attribute(cell, "security", 5)

        cell = CellRendererSignal()
        cell.set_padding(4, 0)
        #cell.set_property("xalign", 1.0)
        combobox.pack_start(cell, False)
        combobox.add_attribute(cell, "signal", 3)

    def _add_device_columns(self, treeview):
        rnd = Gtk.CellRendererPixbuf()
        rnd.set_property("stock-size", Gtk.IconSize.DND)
        # TODO Gtk3 icon-name? (also at other places)
        col = Gtk.TreeViewColumn("Icon", rnd, **{"icon-name":0})
        treeview.append_column(col)

        rnd = Gtk.CellRendererText()
        rnd.set_property("wrap-mode", Pango.WrapMode.WORD)
        col = Gtk.TreeViewColumn("Text", rnd, markup=2)
        col.set_sort_column_id(2)
        col.set_expand(True)
        treeview.append_column(col)

    def initialize(self):
        self.client.connect("notify::%s" % NM.CLIENT_WIRELESS_ENABLED,
                            self.on_wireless_enabled)
        self.client.connect("notify::%s" % NM.CLIENT_STATE,
                            self.on_nm_state_changed)


        self._load_device_configurations()
        self._dev_cfg_subscription = self._network_module.proxy.DeviceConfigurationChanged.connect(
            self.on_device_configurations_changed)

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
            old_cfg = apply_structure(old_values, NetworkDeviceConfiguration())
            new_cfg = apply_structure(new_values, NetworkDeviceConfiguration())

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
        device_configurations = self._network_module.proxy.GetDeviceConfigurations()
        self.dev_cfg_store.clear()
        for device_configuration in device_configurations:
            dev_cfg = apply_structure(device_configuration, NetworkDeviceConfiguration())
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

    def on_wireless_ap_changed_cb(self, combobox, *args):
        if self._updating_device:
            return
        itr = combobox.get_active_iter()
        if not itr:
            return

        dev_cfg = self.selected_dev_cfg()
        if not dev_cfg:
            return

        device = self.client.get_device_by_iface(dev_cfg.device_name)

        ap, ssid_target = combobox.get_model().get(itr, 0, 1)
        self.selected_ap = ap

        log.info("selected access point: %s", ssid_target)

        cons = ap.filter_connections(device.filter_connections(self.client.get_connections()))
        if cons:
            con = cons[0]
            self.client.activate_connection_async(con, device, ap.get_path(), None)
        else:
            if self._ap_is_enterprise(ap):
                # Create a connection for the ap and [Configure] it later with nm-c-e
                con = NM.SimpleConnection.new()
                s_con = NM.SettingConnection.new()
                s_con.set_property('uuid', str(uuid4()))
                s_con.set_property('id', ssid_target)
                s_con.set_property('type', '802-11-wireless')
                s_wireless = NM.SettingWireless.new()
                s_wireless.set_property('ssid', ap.get_ssid())
                s_wireless.set_property('mode', 'infrastructure')
                log.debug("adding connection for WPA-Enterprise AP %s", ssid_target)
                con.add_setting(s_con)
                con.add_setting(s_wireless)
                persistent = True
                self.client.add_connection_async(con, persistent, None)
                self.builder.get_object("button_wireless_options").set_sensitive(True)
            else:
                self.client.add_and_activate_connection_async(None, device, ap.get_path(), None)

    def _find_first_ap_setting(self, device, ap):
        for con in device.filter_connections(self.client.get_connections()):
            wireless_setting = con.get_setting_wireless()
            if not wireless_setting or not wireless_setting.get_ssid():
                # setting is None or non-broadcast AP, we ignore these
                return
            if wireless_setting.get_ssid().get_data() == ap.get_ssid().get_data():
                return con

    def on_edit_connection(self, *args):
        dev_cfg = self.selected_dev_cfg()
        if not dev_cfg:
            return

        device = self.client.get_device_by_iface(dev_cfg.device_name)
        con = self.client.get_connection_by_uuid(dev_cfg.connection_uuid)
        device_type = dev_cfg.device_type
        iface = dev_cfg.device_name
        activate = None
        ssid = ""

        if device_type == NM.DeviceType.WIFI:
            if not self.selected_ap:
                return
            ssid = self.selected_ap.get_ssid().get_data()
            con = self._find_first_ap_setting(device, self.selected_ap)
            if not con:
                log.debug("on_edit_connection: connection for ap %s not found", self.selected_ap)
                return
            # 871132 auto activate wireless connection after editing if it is not
            # already activated (assume entering secrets)
            condition = lambda: self.selected_ap != device.get_active_access_point()
            activate = (con, device, condition)
        else:
            if not con:
                log.debug("on_edit_connection: connection for device %s not found", iface)
                if device_type == NM.DeviceType.ETHERNET:
                    # Create default connection for the device and run nm-c-e on it
                    default_con = self._default_eth_con(iface, autoconnect=False)
                    persistent = False
                    log.info("creating new connection for %s device", iface)
                    self.client.add_connection_async(default_con, persistent, None,
                            self._default_connection_added_cb, activate)
                return

            if device and device.get_state() == NM.DeviceState.ACTIVATED:
                # Reactivate the connection after configuring it (if it changed)
                settings = con.to_dbus(NM.ConnectionSerializationFlags.ALL)
                settings_changed = lambda: settings != con.to_dbus(NM.ConnectionSerializationFlags.ALL)
                activate = (con, device, settings_changed)

        log.info("configuring connection %s device %s ssid %s",
                 con.get_uuid(), iface, ssid)
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

    def _default_eth_con(self, iface, autoconnect):
        con = NM.SimpleConnection.new()
        s_con = NM.SettingConnection.new()
        s_con.set_property('uuid', str(uuid4()))
        s_con.set_property('id', iface)
        s_con.set_property('interface-name', iface)
        s_con.set_property('autoconnect', autoconnect)
        s_con.set_property('type', '802-3-ethernet')
        s_wired = NM.SettingWired.new()
        con.add_setting(s_con)
        con.add_setting(s_wired)
        return con

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
            self._network_module.proxy.LogConfigurationState("Connection Editor was run.")

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
        self.kill_nmce(msg="Add device button clicked")
        proc = startProgram(["nm-connection-editor", "--keep-above", "--create", "--type=%s" % ty], reset_lang=False)
        self._running_nmce = proc

        PidWatcher().watch_process(proc.pid, self.on_nmce_exited)

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
                    icon_name = "network-wired-disconnected"
                else:
                    icon_name = "network-wired"
            else:
                icon_name = "network-wired-disconnected"
        elif dev_cfg.device_type == NM.DeviceType.WIFI:
            icon_name = "network-wireless"

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

        self._refresh_device_type_page(dev_cfg.device_type)
        self._refresh_header_ui(dev_cfg, state)
        self._refresh_slaves(dev_cfg)
        self._refresh_parent_vlanid(dev_cfg)
        self._refresh_speed_hwaddr(dev_cfg, state)
        self._refresh_ap(dev_cfg, state)
        self._refresh_device_cfg(dev_cfg)

    def _refresh_device_cfg(self, dev_cfg):

        if dev_cfg.device_type in self.wired_ui_device_types:
            dt = "wired"
        elif dev_cfg.device_type  == NM.DeviceType.WIFI:
            dt = "wireless"

        device = self.client.get_device_by_iface(dev_cfg.device_name)
        if device:
            ipv4cfg = device.get_ip4_config()
            ipv6cfg = device.get_ip6_config()
        else:
            ipv4cfg = ipv6cfg = None

        if ipv4cfg:
            addr_str = ",".join("%s/%d" % (a.get_address(), a.get_prefix())
                                           for a in ipv4cfg.get_addresses())
            gateway_str = ipv4cfg.get_gateway()
            dnss_str = ",".join(ipv4cfg.get_nameservers())
        else:
            addr_str = dnss_str = gateway_str = None
        self._set_device_info_value(dt, "ipv4", addr_str)
        self._set_device_info_value(dt, "dns", dnss_str)
        self._set_device_info_value(dt, "route", gateway_str)

        addr6_str = ""
        if ipv6cfg:
            addr6_str = ",".join("%s/%d" % (a.get_address(), a.get_prefix())
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
        if state == NM.DeviceState.UNAVAILABLE:
            ap_str = None
        else:
            active_ap = device.get_active_access_point()
            if active_ap:
                ap_str = self._ap_security_string(active_ap)
            else:
                ap_str = ""

        self._set_device_info_value("wireless", "security", ap_str)

        if state == NM.DeviceState.UNAVAILABLE:
            self.builder.get_object("heading_wireless_network_name").hide()
            self.builder.get_object("combobox_wireless_network_name").hide()
        else:
            self.builder.get_object("heading_wireless_network_name").show()
            self.builder.get_object("combobox_wireless_network_name").show()

            store = self.builder.get_object("liststore_wireless_network")
            self._updating_device = True
            store.clear()
            aps = self._get_strongest_unique_aps(device.get_access_points())
            for ap in aps:
                self._add_ap(ap, active_ap == ap)
            # TODO: add access point other...
            if active_ap:
                combobox = self.builder.get_object("combobox_wireless_network_name")
                for i in combobox.get_model():
                    if i[0] == active_ap:
                        combobox.set_active_iter(i.iter)
                        self.selected_ap = active_ap
                        break
            self._updating_device = False

    def _refresh_slaves(self, dev_cfg):
        if dev_cfg.device_type in [NM.DeviceType.BOND,
                                   NM.DeviceType.TEAM,
                                   NM.DeviceType.BRIDGE]:
            slaves = ""
            device = self.client.get_device_by_iface(dev_cfg.device_name)
            if device:
                slaves = ",".join(s.get_iface() for s in device.get_slaves())
            self._set_device_info_value("wired", "slaves", slaves)

    def _refresh_parent_vlanid(self, dev_cfg):
        if dev_cfg.device_type == NM.DeviceType.VLAN:
            parent = ""
            vlanid = ""
            device = self.client.get_device_by_iface(dev_cfg.device_name)
            if device:
                vlanid = device.get_vlan_id()
                parent = device.get_parent().get_iface()
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

    def _refresh_device_type_page(self, dev_type):
        notebook = self.builder.get_object("notebook_types")
        if dev_type == NM.DeviceType.ETHERNET:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_slaves").hide()
            self.builder.get_object("label_wired_slaves").hide()
            self.builder.get_object("heading_wired_vlanid").hide()
            self.builder.get_object("label_wired_vlanid").hide()
            self.builder.get_object("heading_wired_parent").hide()
            self.builder.get_object("label_wired_parent").hide()
            self.builder.get_object("remove_toolbutton").set_sensitive(False)
        elif dev_type in [NM.DeviceType.BOND,
                          NM.DeviceType.TEAM,
                          NM.DeviceType.BRIDGE]:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_slaves").show()
            self.builder.get_object("label_wired_slaves").show()
            self.builder.get_object("heading_wired_vlanid").hide()
            self.builder.get_object("label_wired_vlanid").hide()
            self.builder.get_object("heading_wired_parent").hide()
            self.builder.get_object("label_wired_parent").hide()
            self.builder.get_object("remove_toolbutton").set_sensitive(True)
        elif dev_type == NM.DeviceType.VLAN:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_slaves").hide()
            self.builder.get_object("label_wired_slaves").hide()
            self.builder.get_object("heading_wired_vlanid").show()
            self.builder.get_object("label_wired_vlanid").show()
            self.builder.get_object("heading_wired_parent").show()
            self.builder.get_object("label_wired_parent").show()
            self.builder.get_object("remove_toolbutton").set_sensitive(True)
        elif dev_type == NM.DeviceType.WIFI:
            notebook.set_current_page(1)
            self.builder.get_object("button_wireless_options").set_sensitive(self.selected_ap is not None)

    def _refresh_carrier_info(self):
        for row in self.dev_cfg_store:
            row[DEVICES_COLUMN_TITLE] = self._dev_title(row[DEVICES_COLUMN_OBJECT])

    def _refresh_header_ui(self, dev_cfg, state=None):
        if dev_cfg.device_type in self.wired_ui_device_types:
            dev_type_str = "wired"
        elif dev_cfg.device_type == NM.DeviceType.WIFI:
            dev_type_str = "wireless"

        if dev_type_str == "wired":
            # update icon according to device status
            img = self.builder.get_object("image_wired_device")
            img.set_from_icon_name(self._dev_icon_name(dev_cfg), Gtk.IconSize.DIALOG)

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
            switch.set_visible(state not in (NM.DeviceState.UNAVAILABLE,
                                             NM.DeviceState.UNMANAGED))
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

    def _add_ap(self, ap, active=False):
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

        store = self.builder.get_object("liststore_wireless_network")

        # Decode the SSID (a byte sequence) into something resembling a string
        ssid_str = NM.utils_ssid_to_utf8(ssid)

        # the third column is for sorting
        itr = store.append([ap,
                            ssid_str,
                            ssid_str,
                            ap.get_strength(),
                            mode,
                            security])
        if active:
            self.builder.get_object("combobox_wireless_network_name").set_active_iter(itr)

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

    def _ap_security(self, ap):
        ty = NM_AP_SEC_UNKNOWN

        flags = ap.get_flags()
        wpa_flags = ap.get_wpa_flags()
        rsn_flags = ap.get_rsn_flags()

        if (not (flags & NM._80211ApFlags.PRIVACY) and
            wpa_flags == NM._80211ApSecurityFlags.NONE and
            rsn_flags == NM._80211ApSecurityFlags.NONE):
            ty = NM_AP_SEC_NONE
        elif (flags & NM._80211ApFlags.PRIVACY and
              wpa_flags == NM._80211ApSecurityFlags.NONE and
              rsn_flags == NM._80211ApSecurityFlags.NONE):
            ty = NM_AP_SEC_WEP
        elif (not (flags & NM._80211ApFlags.PRIVACY) and
              wpa_flags != NM._80211ApSecurityFlags.NONE and
              rsn_flags != NM._80211ApSecurityFlags.NONE):
            ty = NM_AP_SEC_WPA
        else:
            ty = NM_AP_SEC_WPA2

        return ty

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

    def _ap_is_enterprise(self, ap):
        wpa_flags = ap.get_wpa_flags()
        rsn_flags = ap.get_rsn_flags()
        return ((wpa_flags & NM._80211ApSecurityFlags.KEY_MGMT_802_1X) or
                (rsn_flags & NM._80211ApSecurityFlags.KEY_MGMT_802_1X))

    @property
    def hostname(self):
        return self.entry_hostname.get_text()

    @hostname.setter
    def hostname(self, value):
        if not value:
            return
        self.entry_hostname.set_text(value)

    @property
    def current_hostname(self):
        return self.label_current_hostname.get_text()

    @current_hostname.setter
    def current_hostname(self, value):
        if not value:
            return
        self.label_current_hostname.set_text(value)

    def disconnect_client_callbacks(self):
        for cb in [self.on_wireless_enabled, self.on_nm_state_changed]:
            _try_disconnect(self.client, cb)

        for device in self.client.get_devices():
            _try_disconnect(device, self.on_device_config_changed)
            _try_disconnect(device, self.on_device_state_changed)
            _try_disconnect(device, self.on_ip_obj_changed)
            for config in self._get_ip_configs(device):
                _try_disconnect(config, self.on_config_changed)

        self._dev_cfg_subscription.disconnect()

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
        if not "nothing connected" in str(e):
            log.debug("%s", e)

class SecretAgentDialog(GUIObject):
    builderObjects = ["secret_agent_dialog"]
    mainWidgetName = "secret_agent_dialog"
    uiFile = "spokes/network.glade"

    def __init__(self, *args, **kwargs):
        self._content = kwargs.pop('content', {})
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

secret_agent = None

class NotAuthorizedException(dbus.DBusException):
    _dbus_error_name = SECRET_AGENT_IFACE + '.NotAuthorized'

class SecretAgent(dbus.service.Object):
    def __init__(self, spoke):
        self._bus = dbus.SystemBus()
        self.spoke = spoke
        super().__init__(self._bus, "/org/freedesktop/NetworkManager/SecretAgent")

    @dbus.service.method(SECRET_AGENT_IFACE,
                         in_signature='a{sa{sv}}osasb',
                         out_signature='a{sa{sv}}',
                         sender_keyword='sender')
    def GetSecrets(self, connection_hash, connection_path, setting_name, hints, flags, sender=None):
        if not sender:
            raise NotAuthorizedException("Internal error: couldn't get sender")
        uid = self._bus.get_unix_user(sender)
        if uid != 0:
            raise NotAuthorizedException("UID %d not authorized" % uid)

        log.debug("secrets requested path '%s' setting '%s' hints '%s' new %d",
                  connection_path, setting_name, str(hints), flags)
        if not (flags & NM_SECRET_AGENT_GET_SECRETS_FLAG_ALLOW_INTERACTION):
            return

        content = self._get_content(setting_name, connection_hash)
        dialog = SecretAgentDialog(self.spoke.data, content=content)
        with self.spoke.main_window.enlightbox(dialog.window):
            rc = dialog.run()

        secrets = dbus.Dictionary()
        if rc == 1:
            for secret in content['secrets']:
                if secret['key']:
                    secrets[secret['key']] = secret['value']

        settings = dbus.Dictionary({setting_name: secrets})

        return settings

    def _get_content(self, setting_name, connection_hash):
        content = {}
        connection_type = connection_hash['connection']['type']
        if connection_type == "802-11-wireless":
            content['title'] = _("Authentication required by wireless network")
            content['message'] = _("Passwords or encryption keys are required to access\n"
                                   "the wireless network '%(network_id)s'.") \
                                   % {'network_id':str(connection_hash['connection']['id'])}
            content['secrets'] = self._get_wireless_secrets(setting_name, connection_hash)
        else:
            log.info("Connection type %s not supported by secret agent", connection_type)

        return content

    def _get_wireless_secrets(self, setting_name, connection_hash):
        key_mgmt = connection_hash['802-11-wireless-security']['key-mgmt']
        original_secrets = connection_hash[setting_name]
        secrets = []
        if key_mgmt in ['wpa-none', 'wpa-psk']:
            secrets.append({'label'     : C_('GUI|Network|Secrets Dialog', '_Password:'),
                            'key'      : 'psk',
                            'value'    : original_secrets.get('psk', ''),
                            'validate' : self._validate_wpapsk,
                            'password' : True})
        # static WEP
        elif key_mgmt == 'none':
            key_idx = str(original_secrets.get('wep_tx_keyidx', '0'))
            secrets.append({'label'     : C_('GUI|Network|Secrets Dialog', '_Key:'),
                            'key'      : 'wep-key%s' % key_idx,
                            'value'    : original_secrets.get('wep-key%s' % key_idx, ''),
                            'wep_key_type': original_secrets.get('wep-key-type', ''),
                            'validate' : self._validate_staticwep,
                            'password' : True})
        # WPA-Enterprise
        elif key_mgmt == 'wpa-eap':
            eap = original_secrets['eap'][0]
            if eap in ('md5', 'leap', 'ttls', 'peap'):
                secrets.append({'label'    : _('User name: '),
                                'key'      : None,
                                'value'    : original_secrets.get('identity', ''),
                                'validate' : None,
                                'password' : False})
                secrets.append({'label'    : _('Password: '),
                                'key'      : 'password',
                                'value'    : original_secrets.get('password', ''),
                                'validate' : None,
                                'password' : True})
            elif eap == 'tls':
                secrets.append({'label'    : _('Identity: '),
                                'key'      : None,
                                'value'    : original_secrets.get('identity', ''),
                                'validate' : None,
                                'password' : False})
                secrets.append({'label'    : _('Private key password: '),
                                'key'      : 'private-key-password',
                                'value'    : original_secrets.get('private-key-password', ''),
                                'validate' : None,
                                'password' : True})
        else:
            log.info("Unsupported wireless key management: %s", key_mgmt)

        return secrets

    def _validate_wpapsk(self, secret):
        value = secret['value']
        if len(value) == 64:
            # must be composed of hexadecimal digits only
            return all(c in string.hexdigits for c in value)
        else:
            return 8 <= len(value) <= 63

    def _validate_staticwep(self, secret):
        value = secret['value']
        if secret['wep_key_type'] == NM.WepKeyType.KEY:
            if len(value) in (10, 26):
                return all(c in string.hexdigits for c in value)
            elif len(value) in (5, 13):
                return all(c in string.ascii_letters for c in value)
            else:
                return False
        elif secret['wep_key_type'] == NM.WepKeyType.PASSPHRASE:
            return 0 <= len(value) <= 64
        else:
            return True

def register_secret_agent(spoke):

    if not conf.system.can_configure_network:
        return False

    global secret_agent
    if not secret_agent:
        # Ignore an error from pylint incorrectly analyzing types in dbus-python
        secret_agent = SecretAgent(spoke) # pylint: disable=no-value-for-parameter
        bus = dbus.SystemBus()
        proxy = bus.get_object(NM_SERVICE, AGENT_MANAGER_PATH)
        proxy.Register("anaconda", dbus_interface=AGENT_MANAGER_IFACE)
    else:
        secret_agent.spoke = spoke

    return True


class NetworkSpoke(FirstbootSpokeMixIn, NormalSpoke):
    """
       .. inheritance-diagram:: NetworkSpoke
          :parts: 3
    """
    builderObjects = ["networkWindow", "liststore_wireless_network", "liststore_devices", "add_device_dialog", "liststore_add_device"]
    mainWidgetName = "networkWindow"
    uiFile = "spokes/network.glade"
    helpFile = "NetworkSpoke.xml"

    title = CN_("GUI|Spoke", "_Network & Host Name")
    icon = "network-transmit-receive-symbolic"

    category = SystemCategory

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self.networking_changed = False
        self._network_module = NETWORK.get_observer()
        self._network_module.connect()
        self.network_control_box = NetworkControlBox(self.builder, nmclient, self._network_module, spoke=self)
        self.network_control_box.hostname = self._network_module.proxy.Hostname
        self.network_control_box.current_hostname = self._network_module.proxy.GetCurrentHostname()
        self._network_module.proxy.CurrentHostnameChanged.connect(self._hostname_changed)
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
        # (persistent NM / ifcfg configuration), instead of using original kickstart.
        self._network_module.proxy.NetworkDeviceConfigurationChanged()
        self._network_module.proxy.SetHostname(self.network_control_box.hostname)
        log.debug("apply ksdata %s", self.data.network)

        # if installation media or hdd aren't used and settings have changed
        # try if source is available
        if self.networking_changed:
            if self.payload and self.payload.needs_network:
                if ANACONDA_ENVIRON in anaconda_flags.environs:
                    log.debug("network spoke (apply), network configuration changed - restarting payload thread")
                    from pyanaconda.payload.manager import payloadMgr
                    payloadMgr.restart_thread(self.storage, self.data, self.payload,
                                             fallback=not anaconda_flags.automatedInstall, onlyOnChange=True)
                else:
                    log.debug("network spoke (apply), network configuration changed - "
                              "skipping restart of payload thread, outside of Anaconda environment")
            else:
                log.debug("network spoke (apply), network configuration changed - "
                          "skipping restart of payload thread, payload does not need network")
        self.networking_changed = False

        self.network_control_box.kill_nmce(msg="leaving network spoke")

    @property
    def completed(self):
        # TODO: check also if source requires updates when implemented
        # If we can't configure network, don't require it
        return (not conf.system.can_configure_network
                or self._network_module.proxy.GetActivatedInterfaces())

    @property
    def mandatory(self):
        # the network spoke should be mandatory only if it is running
        # during the installation and if the installation source requires network
        return ANACONDA_ENVIRON in anaconda_flags.environs and self.payload.needs_network

    @property
    def status(self):
        """ A short string describing which devices are connected. """
        return network.status_message(nmclient)

    def initialize(self):
        register_secret_agent(self)
        NormalSpoke.initialize(self)
        self.initialize_start()
        self.network_control_box.initialize()
        if not conf.system.can_configure_network:
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
        self.network_control_box.current_hostname = self._network_module.proxy.GetCurrentHostname()

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
        (valid, error) = network.is_valid_hostname(hostname)
        if not valid:
            self.clear_info()
            msg = _("Host name is not valid: %s") % error
            self.set_warning(msg)
            self.network_control_box.entry_hostname.grab_focus()
        else:
            self.clear_info()
            if conf.system.can_change_hostname:
                self._network_module.proxy.SetCurrentHostname(hostname)

    def _update_status(self):
        hubQ.send_message(self.__class__.__name__, self.status)

    def _update_hostname(self):
        self.network_control_box.current_hostname = self._network_module.proxy.GetCurrentHostname()

    def on_back_clicked(self, button):
        hostname = self.network_control_box.hostname
        (valid, error) = network.is_valid_hostname(hostname)
        if not valid:
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
    builderObjects = ["networkStandaloneWindow", "networkControlBox_vbox", "liststore_wireless_network", "liststore_devices", "add_device_dialog", "liststore_add_device"]
    mainWidgetName = "networkStandaloneWindow"
    uiFile = "spokes/network.glade"

    preForHub = SummaryHub
    priority = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._network_module = NETWORK.get_observer()
        self._network_module.connect()
        self.network_control_box = NetworkControlBox(self.builder, nmclient, self._network_module, spoke=self)

        self.network_control_box.hostname = self._network_module.proxy.Hostname
        self.network_control_box.current_hostname = self._network_module.proxy.GetCurrentHostname()
        self._network_module.proxy.CurrentHostnameChanged.connect(self._hostname_changed)

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
        # (persistent NM / ifcfg configuration), instead of using original kickstart.
        self._network_module.proxy.NetworkDeviceConfigurationChanged()
        self._network_module.proxy.SetHostname(self.network_control_box.hostname)

        log.debug("apply ksdata %s", self.data.network)

        self._now_available = self.completed

        log.debug("network standalone spoke (apply) payload: %s completed: %s", self.payload.base_repo, self._now_available)
        if (not self.payload.base_repo and not self._initially_available
            and self._now_available and self.payload.needs_network):
            from pyanaconda.payload.manager import payloadMgr
            payloadMgr.restart_thread(self.storage, self.data, self.payload,
                    fallback=not anaconda_flags.automatedInstall)

        self.network_control_box.kill_nmce(msg="leaving standalone network spoke")
        self.network_control_box.disconnect_client_callbacks()

    @property
    def completed(self):
        # If we can't configure network, don't require it
        return (not conf.system.can_configure_network
                or self._network_module.proxy.GetActivatedInterfaces()
                or self.data.method.method not in ("url", "nfs"))

    def initialize(self):
        register_secret_agent(self)
        super().initialize()
        self.network_control_box.initialize()

    def refresh(self):
        super().refresh()
        self.network_control_box.refresh()
        self.network_control_box.current_hostname = self._network_module.proxy.GetCurrentHostname()

    def _on_continue_clicked(self, window, user_data=None):
        hostname = self.network_control_box.hostname
        (valid, error) = network.is_valid_hostname(hostname)
        if not valid:
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
        (valid, error) = network.is_valid_hostname(hostname)
        if not valid:
            self.clear_info()
            msg = _("Host name is not valid: %s") % error
            self.set_warning(msg)
            self.network_control_box.entry_hostname.grab_focus()
        else:
            self.clear_info()
            if conf.system.can_change_hostname:
                self._network_module.proxy.SetCurrentHostname(hostname)

    def _update_hostname(self):
        self.network_control_box.current_hostname = self._network_module.proxy.GetCurrentHostname()


def test():
    win = Gtk.Window()
    win.connect("delete-event", Gtk.main_quit)

    builder = Gtk.Builder()
    import os
    ui_file_path = os.environ.get('UIPATH')+'spokes/network.glade'
    builder.add_from_file(ui_file_path)

    network_module = NETWORK.get_observer()
    network_module.connect()

    n = NetworkControlBox(builder, nmclient, network_module)
    n.initialize()
    n.refresh()

    n.vbox.reparent(win)

    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    test()
