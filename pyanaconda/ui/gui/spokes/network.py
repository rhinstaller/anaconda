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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#

# TODO:

# - move callback connection to initialize?
# - Automatically reconnecting wifi after failure
#   https://bugzilla.redhat.com/show_bug.cgi?id=712778#c1
# - callback on NM_CLIENT_ACTIVE_CONNECTIONS
# - support connection to hidden network (ap-other)
# - NMClient.CLIENT_WIRELESS_ENABLED callback (hw switch?) - test
# - nm-c-e run: blocking? logging?

from gi.repository import Gtk

from pyanaconda.flags import can_touch_runtime_system
from pyanaconda.i18n import _, N_, C_, CN_
from pyanaconda.flags import flags as anaconda_flags
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke, StandaloneSpoke
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.utils import gtk_call_once, escape_markup
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.iutil import startProgram

from pyanaconda import network
from pyanaconda import nm

from gi.repository import GLib, GObject, Pango, Gio, NetworkManager, NMClient
import dbus
import dbus.service
# Used for ascii_letters and hexdigits constants
import string # pylint: disable=deprecated-module
from uuid import uuid4

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import logging
log = logging.getLogger("anaconda")

# These are required for dbus API use we need because of
# NM_GI_BUGS: 767998, 773678
NM_SERVICE = "org.freedesktop.NetworkManager"
NM_802_11_AP_FLAGS_PRIVACY = 0x1
NM_802_11_AP_SEC_NONE = 0x0
NM_802_11_AP_SEC_KEY_MGMT_802_1X = 0x200
NM_SECRET_AGENT_GET_SECRETS_FLAG_ALLOW_INTERACTION = 0x1
DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"
SECRET_AGENT_IFACE = 'org.freedesktop.NetworkManager.SecretAgent'
AGENT_MANAGER_IFACE = 'org.freedesktop.NetworkManager.AgentManager'
AGENT_MANAGER_PATH = "/org/freedesktop/NetworkManager/AgentManager"



def getNMObjProperty(obj, nm_iface_suffix, prop):
    props_iface = dbus.Interface(obj, DBUS_PROPS_IFACE)
    return props_iface.Get("org.freedesktop.NetworkManager"+nm_iface_suffix,
                           prop)


DEVICES_COLUMN_TITLE  = 2
DEVICES_COLUMN_OBJECT = 3


def localized_string_of_device_state(device, state):
    s = _("Status unknown (missing)")

    if state == NetworkManager.DeviceState.UNKNOWN:
        s = _("Status unknown")
    elif state == NetworkManager.DeviceState.UNMANAGED:
        s = _("Unmanaged")
    elif state == NetworkManager.DeviceState.UNAVAILABLE:
        if not device:
            s = _("Unavailable")
        elif device.get_firmware_missing():
            s = _("Firmware missing")
        else:
            s = _("Unavailable")
    elif state == NetworkManager.DeviceState.DISCONNECTED:
        if (device and device.get_device_type() == NetworkManager.DeviceType.ETHERNET
              and not device.get_carrier()):
            s = _("Cable unplugged")
        else:
            s = _("Disconnected")
    elif state in (NetworkManager.DeviceState.PREPARE,
                   NetworkManager.DeviceState.CONFIG,
                   NetworkManager.DeviceState.IP_CONFIG,
                   NetworkManager.DeviceState.IP_CHECK):
        s = _("Connecting")
    elif state == NetworkManager.DeviceState.NEED_AUTH:
        s = _("Authentication required")
    elif state == NetworkManager.DeviceState.ACTIVATED:
        s = _("Connected")
    elif state == NetworkManager.DeviceState.DEACTIVATING:
        s = _("Disconnecting")
    elif state == NetworkManager.DeviceState.FAILED:
        s = _("Connection failed")

    return s

__all__ = ["NetworkSpoke", "NetworkStandaloneSpoke"]

class CellRendererSignal(Gtk.CellRendererPixbuf):

    __gtype_name__ = "CellRendererSignal"
    __gproperties__ = {
        "signal": (GObject.TYPE_UINT,
                   "Signal", "Signal",
                   0, GObject.G_MAXUINT, 0,
                   GObject.PARAM_READWRITE),
    }

    def __init__(self):
        Gtk.CellRendererPixbuf.__init__(self)
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
    __gproperties__ = {
        "security": (GObject.TYPE_UINT,
                   "Security", "Security",
                   0, GObject.G_MAXUINT, 0,
                   GObject.PARAM_READWRITE),
    }

    def __init__(self):
        Gtk.CellRendererPixbuf.__init__(self)
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

class DeviceConfiguration(object):

    setting_types = {
        '802-11-wireless': NetworkManager.DeviceType.WIFI,
        '802-3-ethernet': NetworkManager.DeviceType.ETHERNET,
        'vlan': NetworkManager.DeviceType.VLAN,
        'bond': NetworkManager.DeviceType.BOND,
        'team': NetworkManager.DeviceType.TEAM,
        'bridge': NetworkManager.DeviceType.BRIDGE,
        }

    def __init__(self, device=None, con_uuid=None):
        self.device = device
        self.con_uuid = con_uuid

        if device:
            self.device_type = self.device.get_device_type()
        elif con_uuid:
            self.device_type = self._setting_device_type(self.con_uuid)

        if not self.con_uuid:
            if self.device_type != NetworkManager.DeviceType.WIFI:
                uuid = nm.nm_device_setting_value(device.get_iface(), "connection", "uuid")
                settings = nm.nm_get_settings(uuid, "connection", "uuid")
                if settings and 'slave-type' not in settings[0]['connection']:
                    self.con_uuid = uuid

    def _setting_device_type(self, uuid):
        settings = nm.nm_get_settings(uuid, "connection", "uuid")
        if not settings:
            return None
        dev_type = self.setting_types.get(settings[0]["connection"]["type"], None)
        return dev_type

    def get_iface(self):
        if self.device:
            iface = self.device.get_iface()
        else:
            iface = self.setting_value("connection", "interface-name")
            if not iface:
                hwaddr = self.setting_value("802-3-ethernet","mac-address")
                if hwaddr:
                    hwaddr = ":".join("%02X" % b for b in hwaddr)
                    iface = nm.nm_hwaddr_to_device_name(hwaddr)
        return iface

    def setting_value(self, key1, key2):
        settings = nm.nm_get_settings(self.con_uuid, "connection", "uuid")
        try:
            value = settings[0][key1][key2]
        except IndexError:
            log.debug("network: can't find connection with uuid %s",
                      self.con_uuid)
        except KeyError:
            log.debug("network: can't find '%s' '%s' in connection %s",
                      key1, key2, self.con_uuid)
        else:
            return value

class NetworkControlBox(GObject.GObject):

    __gsignals__ = {
        "nm-state-changed": (GObject.SIGNAL_RUN_LAST, GObject.TYPE_NONE, []),
        "device-state-changed": (GObject.SIGNAL_RUN_LAST, GObject.TYPE_NONE, [str, int, int, int]),
    }

    supported_device_types = [
        NetworkManager.DeviceType.ETHERNET,
        NetworkManager.DeviceType.WIFI,
        NetworkManager.DeviceType.TEAM,
        NetworkManager.DeviceType.BOND,
        NetworkManager.DeviceType.VLAN,
        NetworkManager.DeviceType.BRIDGE,
    ]

    wired_ui_device_types = [
        NetworkManager.DeviceType.ETHERNET,
        NetworkManager.DeviceType.TEAM,
        NetworkManager.DeviceType.BOND,
        NetworkManager.DeviceType.VLAN,
        NetworkManager.DeviceType.BRIDGE,
    ]

    device_type_sort_value = {
        NetworkManager.DeviceType.ETHERNET : "1",
        NetworkManager.DeviceType.WIFI : "2",
    }

    device_type_name = {
        NetworkManager.DeviceType.UNKNOWN: N_("Unknown"),
        NetworkManager.DeviceType.ETHERNET: N_("Ethernet"),
        NetworkManager.DeviceType.WIFI: N_("Wireless"),
        NetworkManager.DeviceType.BOND: N_("Bond"),
        NetworkManager.DeviceType.VLAN: N_("VLAN"),
        NetworkManager.DeviceType.TEAM: N_("Team"),
        NetworkManager.DeviceType.BRIDGE: N_("Bridge"),
    }

    def __init__(self, builder, spoke=None):

        GObject.GObject.__init__(self)

        self.builder = builder
        self._running_nmce = None
        self.spoke = spoke

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

        self.client = NMClient.Client.new()

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
        self.selected_ssid = None

        # NM Client
        self.client.connect("device-added", self.on_device_added)
        self.client.connect("device-removed", self.on_device_removed)

        self.builder.get_object("device_wired_off_switch").connect("notify::active",
                                                             self.on_device_off_toggled)
        self.builder.get_object("device_wireless_off_switch").connect("notify::active",
                                                             self.on_device_off_toggled)
        self.client.connect("notify::%s" % NMClient.CLIENT_WIRELESS_ENABLED,
                            self.on_wireless_enabled)

        self.builder.get_object("button_wired_options").connect("clicked",
                                                           self.on_edit_connection)
        self.builder.get_object("button_wireless_options").connect("clicked",
                                                              self.on_edit_connection)
        self.entry_hostname = self.builder.get_object("entry_hostname")

        self.client.connect("notify::%s" % NMClient.CLIENT_STATE,
                            self.on_nm_state_changed)

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
        for device in self.client.get_devices():
            self.add_device_to_list(device)

        for setting in nm.nm_get_all_settings():
            uuid = setting["connection"]["uuid"]
            log.debug("network: GUI, connection %s found", uuid)
            if self.dev_cfg(uuid=uuid):
                continue
            if setting["connection"].get("read-only", False):
                log.debug("network: GUI, not adding read-only connection %s", uuid)
                continue
            dev_cfg = DeviceConfiguration(con_uuid=uuid)
            if dev_cfg.device_type in self.supported_device_types:
                # Configs for ethernet has been already added,
                # this must be some slave.
                if dev_cfg.device_type == NetworkManager.DeviceType.ETHERNET:
                    continue
                # Wireless settings are handled in scope of its device's dev_cfg
                if dev_cfg.device_type == NetworkManager.DeviceType.WIFI:
                    continue
                # Virtual device settings (bond, team, vlan, ...)
                self.add_dev_cfg(dev_cfg)

        # select the first device
        treeview = self.builder.get_object("treeview_devices")
        selection = treeview.get_selection()
        itr = self.dev_cfg_store.get_iter_first()
        if itr:
            selection.select_iter(itr)

    def refresh(self):
        self.refresh_ui()

    # Signal handlers.
    def on_nm_state_changed(self, *args):
        self.emit("nm-state-changed")

    def on_device_selection_changed(self, *args):
        self.refresh_ui()

    def on_device_state_changed(self, device, new_state, *args):
        self.emit("device-state-changed", device.get_iface(), new_state, *args)
        if new_state == NetworkManager.DeviceState.SECONDARIES:
            return
        self._refresh_carrier_info()
        dev_cfg = self.selected_dev_cfg()
        if dev_cfg and dev_cfg.device == device:
            self.refresh_ui(state=new_state)

    def on_device_config_changed(self, device, *args):
        dev_cfg = self.selected_dev_cfg()
        if dev_cfg and dev_cfg.device == device:
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

        ap_obj_path, ssid_target = combobox.get_model().get(itr, 0, 1)
        self.selected_ssid = ssid_target
        if ap_obj_path == "ap-other...":
            return

        log.info("network: selected access point: %s", ssid_target)

        try:
            uuid = nm.nm_ap_setting_value(ssid_target, "connection", "uuid")
            nm.nm_activate_device_connection(dev_cfg.device.get_iface(), uuid)
        except nm.UnmanagedDeviceError as e:
            log.debug("network: on_wireless_ap_changed: %s", e)
        except nm.SettingsNotFoundError as e:
            log.debug("network: on_wireless_ap_changed: %s", e)
            if self._ap_is_enterprise_dbus(ap_obj_path):
                # Create a connection for the ap and [Configure] it later with nm-c-e
                values = []
                values.append(['connection', 'uuid', str(uuid4()), 's'])
                values.append(['connection', 'id', ssid_target, 's'])
                values.append(['connection', 'type', '802-11-wireless', 's'])
                ssid = [ord(c) for c in ssid_target]
                values.append(['802-11-wireless', 'ssid', ssid, 'ay'])
                values.append(['802-11-wireless', 'mode', 'infrastructure', 's'])
                log.debug("network: adding connection for WPA-Enterprise AP %s", ssid_target)
                nm.nm_add_connection(values)
                self.builder.get_object("button_wireless_options").set_sensitive(True)
            else:
                self.client.add_and_activate_connection(None, dev_cfg.device, ap_obj_path,
                                                    None, None)

    def on_device_added(self, client, device, *args):
        self.add_device_to_list(device)

    def on_device_removed(self, client, device, *args):
        self.remove_device(device)

    def on_edit_connection(self, *args):
        dev_cfg = self.selected_dev_cfg()
        if not dev_cfg:
            return

        uuid = dev_cfg.con_uuid
        devname = dev_cfg.get_iface()
        activate = None

        if dev_cfg.device_type == NetworkManager.DeviceType.WIFI:
            if self.selected_ssid:
                try:
                    uuid = nm.nm_ap_setting_value(self.selected_ssid, "connection", "uuid")
                except nm.SettingsNotFoundError as e:
                    log.debug("network: on_edit_connection: %s", e)
                else:
                    # 871132 auto activate wireless connection after editing if it is not
                    # already activated (assume entering secrets)
                    condition = lambda: self.selected_ssid != nm.nm_device_active_ssid(devname)
                    activate = (uuid, devname, condition)

        if not uuid:
            log.debug("network: on_edit_connection: can't find connection for device %s", devname)
            return

        if dev_cfg.device_type != NetworkManager.DeviceType.WIFI \
           and dev_cfg.get_iface() in nm.nm_activated_devices():
            # Reactivate the connection after configuring it (if it changed)
            settings = nm.nm_get_settings(uuid, "connection", "uuid")
            settings_changed = lambda: settings != nm.nm_get_settings(uuid, "connection", "uuid")
            activate = (uuid, devname, settings_changed)

        log.info("network: configuring connection %s device %s ssid %s",
                 uuid, devname, self.selected_ssid)
        self.kill_nmce(msg="Configure button clicked")
        proc = startProgram(["nm-connection-editor", "--edit", "%s" % uuid], reset_lang=False)
        self._running_nmce = proc

        GLib.child_watch_add(proc.pid, self.on_nmce_exited, activate)

    def kill_nmce(self, msg=""):
        if not self._running_nmce:
            return False

        log.debug("network: killing running nm-c-e %s: %s", self._running_nmce.pid, msg)
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
                uuid, devname, activate_condition = activate # pylint: disable=unpacking-non-sequence
                if activate_condition():
                    gtk_call_once(self._activate_connection_cb, uuid, devname)
            network.logIfcfgFiles("nm-c-e run")

    def _activate_connection_cb(self, uuid, devname):
        nm.nm_activate_device_connection(devname, uuid)

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

        log.info("network: device %s switched %s", dev_cfg.get_iface(), "on" if active else "off")

        if dev_cfg.device_type == NetworkManager.DeviceType.WIFI:
            self.client.wireless_set_enabled(active)
        else:
            if active:
                dev_name = dev_cfg.device and dev_cfg.device.get_iface()
                if not dev_cfg.con_uuid:
                    log.debug("network: on_device_off_toggled: no connection for %s",
                               dev_name)
                    return
                try:
                    nm.nm_activate_device_connection(dev_name, dev_cfg.con_uuid)
                except (nm.UnmanagedDeviceError, nm.UnknownDeviceError, nm.UnknownConnectionError) as e:
                    log.debug("network: on_device_off_toggled: %s", e)
            else:
                try:
                    nm.nm_disconnect_device(dev_cfg.get_iface())
                except (nm.UnmanagedDeviceError, nm.DeviceNotActiveError) as e:
                    log.debug("network: on_device_off_toggled: %s", e)

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
        model.remove(itr)
        nm.nm_delete_connection(dev_cfg.con_uuid)

    def add_device(self, ty):
        log.info("network: adding device of type %s", ty)
        self.kill_nmce(msg="Add device button clicked")
        proc = startProgram(["nm-connection-editor", "--create", "--type=%s" % ty], reset_lang=False)
        self._running_nmce = proc

        GLib.child_watch_add(proc.pid, self.on_nmce_exited)

    def selected_dev_cfg(self):
        selection = self.builder.get_object("treeview_devices").get_selection()
        model, itr = selection.get_selected()
        if not itr:
            return None
        return model[itr][DEVICES_COLUMN_OBJECT]

    def add_dev_cfg(self, dev_cfg):
        log.debug ("network: GUI, device configuration added: connection %s device %s",
                     dev_cfg.con_uuid, dev_cfg.get_iface())
        self.dev_cfg_store.append([
            self._dev_icon_name(dev_cfg),
            self.device_type_sort_value.get(dev_cfg.device_type, "100"),
            self._dev_title(dev_cfg),
            dev_cfg
        ])

    def add_device_to_list(self, device):
        if device.get_device_type() not in self.supported_device_types:
            return
        # ignore fcoe vlan devices
        # (can be chopped off to IFNAMSIZ kernel limit)
        if device.get_iface().endswith(('-fcoe', '-fco', '-fc', '-f', '-')):
            return

        try:
            read_only = nm.nm_device_setting_value(device.get_iface(), "connection", "read-only")
            if read_only:
                log.debug("network: not adding read-only connection for device %s", device.get_iface())
                return
            con_uuid = nm.nm_device_setting_value(device.get_iface(), "connection", "uuid")
            dev_cfg = self.dev_cfg(uuid=con_uuid)
        except nm.UnknownDeviceError as e:
            log.error(e)
            return
        except nm.SettingsNotFoundError:
            # wireless devices
            dev_cfg = None
        if dev_cfg:
            dev_cfg.device = device
        else:
            dev_cfg = DeviceConfiguration(device=device)
            self.add_dev_cfg(dev_cfg)

        device.connect("notify::ip4-config", self.on_device_config_changed)
        device.connect("notify::ip6-config", self.on_device_config_changed)
        device.connect("state-changed", self.on_device_state_changed)

    def _dev_icon_name(self, dev_cfg):
        icon_name = ""
        if dev_cfg.device_type in self.wired_ui_device_types:
            if dev_cfg.device:
                if dev_cfg.device.get_state() == NetworkManager.DeviceState.UNAVAILABLE:
                    icon_name = "network-wired-disconnected"
                else:
                    icon_name = "network-wired"
            else:
                icon_name = "network-wired-disconnected"
        elif dev_cfg.device_type == NetworkManager.DeviceType.WIFI:
            icon_name = "network-wireless"

        return icon_name

    def _dev_title(self, dev_cfg):
        unplugged = ''

        if dev_cfg.device:
            if (dev_cfg.device.get_state() == NetworkManager.DeviceState.UNAVAILABLE
                and dev_cfg.device.get_device_type() == NetworkManager.DeviceType.ETHERNET
                and not dev_cfg.device.get_carrier()):
                # TRANSLATORS: ethernet cable is unplugged
                unplugged = ', <i>%s</i>' % escape_markup(_("unplugged"))
        # pylint: disable=unescaped-markup
        title = '<span size="large">%s (%s%s)</span>' % \
                 (escape_markup(_(self.device_type_name.get(dev_cfg.device_type, ""))),
                  escape_markup(dev_cfg.get_iface()),
                  unplugged)

        if dev_cfg.device:
            title += '\n<span size="small">%s %s</span>' % \
                    (escape_markup(dev_cfg.device.get_vendor() or ""),
                     escape_markup(dev_cfg.device.get_product() or ""))
        return title

    def dev_cfg(self, uuid=None, device=None):
        for row in self.dev_cfg_store:
            dev_cfg = row[DEVICES_COLUMN_OBJECT]
            if uuid:
                if uuid != dev_cfg.con_uuid:
                    continue
            if device:
                if not dev_cfg.device \
                   or dev_cfg.device.get_udi() != device.get_udi():
                    continue
            return dev_cfg
        return None

    def remove_device(self, device):
        # This should not concern wifi and ethernet devices,
        # just virtual devices e.g. vpn probably
        log.debug("network: GUI, device removed: %s" , device.get_iface())
        dev_cfg = self.dev_cfg(device=device)
        if dev_cfg:
            dev_cfg.device = None

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
        elif dev_cfg.device_type == NetworkManager.DeviceType.WIFI:
            dt = "wireless"

        if dev_cfg.device:
            try:
                ipv4cfg = nm.nm_device_ip_config(dev_cfg.device.get_iface(), version=4)
                ipv6cfg = nm.nm_device_ip_config(dev_cfg.device.get_iface(), version=6)
            except nm.UnknownDeviceError:
                ipv4cfg = ipv6cfg = None
        else:
            ipv4cfg = ipv6cfg = None

        if ipv4cfg and ipv4cfg[0]:
            addr_str, prefix, gateway_str = ipv4cfg[0][0]
            netmask_str = network.prefix2netmask(prefix)
            dnss_str = " ".join(ipv4cfg[1])
        else:
            addr_str = dnss_str = gateway_str = netmask_str = None
        self._set_device_info_value(dt, "ipv4", addr_str)
        self._set_device_info_value(dt, "dns", dnss_str)
        self._set_device_info_value(dt, "route", gateway_str)
        if dt == "wired":
            self._set_device_info_value(dt, "subnet", netmask_str)

        addr6_str = ""
        if ipv6cfg and ipv6cfg[0]:
            for ipv6addr in ipv6cfg[0]:
                addr_str, prefix, gateway_str = ipv6addr
                # Do not display link-local addresses
                if not addr_str.startswith("fe80:"):
                    addr6_str += "%s/%d\n" % (addr_str, prefix)

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
        if dev_cfg.device_type != NetworkManager.DeviceType.WIFI:
            return

        if state is None:
            state = dev_cfg.device.get_state()
        if state == NetworkManager.DeviceState.UNAVAILABLE:
            ap_str = None
        else:
            active_ap = dev_cfg.device.get_active_access_point()
            if active_ap:
                active_ap_dbus = dbus.SystemBus().get_object(NM_SERVICE,
                                                             active_ap.get_path())
                ap_str = self._ap_security_string_dbus(active_ap_dbus)
                # TODO NM_GI_BUGS move to gi after fixed in NM
                # - NetworkManager.80211ApFlags
                # - active_ap.get_flags, get_wpa_flags, get_rsn_flags
                #ap_str = self._ap_security_string(active_ap)
            else:
                ap_str = ""

        self._set_device_info_value("wireless", "security", ap_str)

        if state == NetworkManager.DeviceState.UNAVAILABLE:
            self.builder.get_object("heading_wireless_network_name").hide()
            self.builder.get_object("combobox_wireless_network_name").hide()
        else:
            self.builder.get_object("heading_wireless_network_name").show()
            self.builder.get_object("combobox_wireless_network_name").show()

            store = self.builder.get_object("liststore_wireless_network")
            self._updating_device = True
            store.clear()
            aps = self._get_strongest_unique_aps(dev_cfg.device.get_access_points())
            for ap in aps:
                active = active_ap and active_ap.get_path() == ap.get_path()
                self._add_ap(ap, active)
            # TODO: add access point other...
            if active_ap:
                combobox = self.builder.get_object("combobox_wireless_network_name")
                for i in combobox.get_model():
                    if i[1] == active_ap.get_ssid():
                        combobox.set_active_iter(i.iter)
                        self.selected_ssid = active_ap.get_ssid()
                        break
            self._updating_device = False

    def _refresh_slaves(self, dev_cfg):
        if dev_cfg.device_type in [NetworkManager.DeviceType.BOND,
                                   NetworkManager.DeviceType.TEAM,
                                   NetworkManager.DeviceType.BRIDGE]:
            slaves = ""
            if dev_cfg.device:
                slaves = ",".join(s.get_iface() for s in dev_cfg.device.get_slaves())
            self._set_device_info_value("wired", "slaves", slaves)

    def _refresh_parent_vlanid(self, dev_cfg):
        if dev_cfg.device_type == NetworkManager.DeviceType.VLAN:
            if dev_cfg.device:
                vlanid = dev_cfg.device.get_vlan_id()
            else:
                vlanid = dev_cfg.setting_value("vlan", "id")
            parent = dev_cfg.setting_value("vlan", "parent")
            self._set_device_info_value("wired", "vlanid", str(vlanid))
            self._set_device_info_value("wired", "parent", parent)

    def _refresh_speed_hwaddr(self, dev_cfg, state=None):
        dev_type = dev_cfg.device_type
        if dev_type in self.wired_ui_device_types:
            dt = "wired"
        elif dev_type == NetworkManager.DeviceType.WIFI:
            dt = "wireless"

        # Speed
        speed = None
        if dev_cfg.device:
            if dev_type == NetworkManager.DeviceType.ETHERNET:
                speed = dev_cfg.device.get_speed()
            elif dev_type == NetworkManager.DeviceType.WIFI:
                speed = dev_cfg.device.get_bitrate() / 1000
            if state is None:
                state = dev_cfg.device.get_state()

        if not dev_cfg.device or state == NetworkManager.DeviceState.UNAVAILABLE:
            speed_str = None
        elif speed:
            speed_str = _("%d Mb/s") % speed
        else:
            speed_str = ""
        self._set_device_info_value(dt, "speed", speed_str)
        # Hardware address
        hwaddr = dev_cfg.device and dev_cfg.device.get_hw_address()
        self._set_device_info_value(dt, "mac", hwaddr)

    def _refresh_device_type_page(self, dev_type):
        notebook = self.builder.get_object("notebook_types")
        if dev_type == NetworkManager.DeviceType.ETHERNET:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_slaves").hide()
            self.builder.get_object("label_wired_slaves").hide()
            self.builder.get_object("heading_wired_vlanid").hide()
            self.builder.get_object("label_wired_vlanid").hide()
            self.builder.get_object("heading_wired_parent").hide()
            self.builder.get_object("label_wired_parent").hide()
            self.builder.get_object("remove_toolbutton").set_sensitive(False)
        elif dev_type in [NetworkManager.DeviceType.BOND,
                          NetworkManager.DeviceType.TEAM,
                          NetworkManager.DeviceType.BRIDGE]:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_slaves").show()
            self.builder.get_object("label_wired_slaves").show()
            self.builder.get_object("heading_wired_vlanid").hide()
            self.builder.get_object("label_wired_vlanid").hide()
            self.builder.get_object("heading_wired_parent").hide()
            self.builder.get_object("label_wired_parent").hide()
            self.builder.get_object("remove_toolbutton").set_sensitive(True)
        elif dev_type == NetworkManager.DeviceType.VLAN:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_slaves").hide()
            self.builder.get_object("label_wired_slaves").hide()
            self.builder.get_object("heading_wired_vlanid").show()
            self.builder.get_object("label_wired_vlanid").show()
            self.builder.get_object("heading_wired_parent").show()
            self.builder.get_object("label_wired_parent").show()
            self.builder.get_object("remove_toolbutton").set_sensitive(True)
        elif dev_type == NetworkManager.DeviceType.WIFI:
            notebook.set_current_page(1)
            self.builder.get_object("button_wireless_options").set_sensitive(self.selected_ssid is not None)

    def _refresh_carrier_info(self):
        for i in self.dev_cfg_store:
            i[DEVICES_COLUMN_TITLE] = self._dev_title(i[DEVICES_COLUMN_OBJECT])

    def _refresh_header_ui(self, dev_cfg, state=None):
        if dev_cfg.device_type in self.wired_ui_device_types:
            dev_type_str = "wired"
        elif dev_cfg.device_type == NetworkManager.DeviceType.WIFI:
            dev_type_str = "wireless"

        if dev_type_str == "wired":
            # update icon according to device status
            img = self.builder.get_object("image_wired_device")
            img.set_from_icon_name(self._dev_icon_name(dev_cfg), Gtk.IconSize.DIALOG)

        # TODO: is this necessary? Isn't it static from glade?
        device_type_label = _(self.device_type_name.get(dev_cfg.device_type, ""))
        self.builder.get_object("label_%s_device" % dev_type_str).set_label(
            "%s (%s)" % (device_type_label, dev_cfg.get_iface()))

        if state is None:
            if not dev_cfg.device:
                state = NetworkManager.DeviceState.DISCONNECTED
            else:
                state = dev_cfg.device.get_state()

        self.builder.get_object("label_%s_status" % dev_type_str).set_label(
            localized_string_of_device_state(dev_cfg.device, state))

        switch = self.builder.get_object("device_%s_off_switch" % dev_type_str)
        if dev_type_str == "wired":
            switch.set_visible(state not in (NetworkManager.DeviceState.UNAVAILABLE,
                                             NetworkManager.DeviceState.UNMANAGED))
            self._updating_device = True
            switch.set_active(state not in (NetworkManager.DeviceState.UNMANAGED,
                                            NetworkManager.DeviceState.UNAVAILABLE,
                                            NetworkManager.DeviceState.DISCONNECTED,
                                            NetworkManager.DeviceState.DEACTIVATING,
                                            NetworkManager.DeviceState.FAILED))
            self._updating_device = False
        elif dev_type_str == "wireless":
            self.on_wireless_enabled()

    def _set_device_info_value(self, dev_type_str, info, value_str):
        heading = self.builder.get_object("heading_%s_%s" % (dev_type_str, info))
        value_label = self.builder.get_object("label_%s_%s" % (dev_type_str, info))
        if value_str is None:
            heading.hide()
            value_label.hide()
        else:
            heading.show()
            value_label.show()
            value_label.set_label(value_str)

    # TODO NM_GI_BUGS use glib methods for mode and security (dbus obj or nm obj?)
    def _add_ap(self, ap, active=False):
        ssid = ap.get_ssid()
        if not ssid:
            return

        # TODO NM_GI_BUGS
        ap_dbus = dbus.SystemBus().get_object(NM_SERVICE, ap.get_path())
        try:
            mode = getNMObjProperty(ap_dbus, ".AccessPoint", "Mode")
        except dbus.DBusException as e:
            # object has became invalid (race)
            if e.get_dbus_name() == "org.freedesktop.DBus.Error.UnknownMethod":
                return
            else:
                raise


        security = self._ap_security_dbus(ap)

        store = self.builder.get_object("liststore_wireless_network")
        # the third column is for sorting
        itr = store.append([ap.get_path(),
                            ssid,
                            ssid,
                            ap.get_strength(),
                            mode,
                            security])
        if active:
            self.builder.get_object("combobox_wireless_network_name").set_active_iter(itr)

    def _get_strongest_unique_aps(self, access_points):
        strongest_aps = {}
        for ap in access_points:
            ssid = ap.get_ssid()
            if ssid in strongest_aps:
                if ap.get_strength() > strongest_aps[ssid].get_strength():
                    strongest_aps[ssid] = ap
            else:
                strongest_aps[ssid] = ap

        return strongest_aps.values()

    # TODO NM_GI_BUGS fix as _ap_security_string
    def _ap_security_dbus(self, ap):
        if ap.get_path() == "/":
            return NM_AP_SEC_UNKNOWN

        ap_dbus = dbus.SystemBus().get_object(NM_SERVICE, ap.get_path())
        flags = getNMObjProperty(ap_dbus, ".AccessPoint", "Flags")
        wpa_flags = getNMObjProperty(ap_dbus, ".AccessPoint", "WpaFlags")
        rsn_flags = getNMObjProperty(ap_dbus, ".AccessPoint", "RsnFlags")

        if (not (flags & NM_802_11_AP_FLAGS_PRIVACY) and
            wpa_flags == NM_802_11_AP_SEC_NONE and
            rsn_flags == NM_802_11_AP_SEC_NONE):
            ty = NM_AP_SEC_NONE
        elif (flags & NM_802_11_AP_FLAGS_PRIVACY and
              wpa_flags == NM_802_11_AP_SEC_NONE and
              rsn_flags == NM_802_11_AP_SEC_NONE):
            ty = NM_AP_SEC_WEP
        elif (not (flags & NM_802_11_AP_FLAGS_PRIVACY) and
              wpa_flags != NM_802_11_AP_SEC_NONE and
              rsn_flags != NM_802_11_AP_SEC_NONE):
            ty = NM_AP_SEC_WPA
        else:
            ty = NM_AP_SEC_WPA2

        return ty

## TODO NM_GI_BUGS - attribute starts with number
#    def _ap_security_string(self, ap):
#        if ap.object_path == "/":
#            return ""
#
#        flags = ap.get_flags()
#        wpa_flags = ap.get_wpa_flags()
#        rsn_flags = ap.get_rsn_flags()
#
#        sec_str = ""
#
#        if ((flags & NetworkManager.80211ApFlags.PRIVACY) and
#            wpa_flags == NetworkManager.80211ApSecurityFlags.NONE and
#            rsn_flags == NetworkManager.80211ApSecurityFlags.NONE):
#            sec_str += "%s, " % _("WEP")
#
#        if wpa_flags != NetworkManager.80211ApSecurityFlags.NONE:
#            sec_str += "%s, " % _("WPA")
#
#        if rsn_flags != NetworkManager.80211ApSecurityFlags.NONE:
#            sec_str += "%s, " % _("WPA2")
#
#        if ((wpa_flags & NetworkManager.80211ApSecurityFlags.KEY_MGMT_802_1X) or
#            (rsn_flags & NetworkManager.80211ApSecurityFlags.KEY_MGMT_802_1X)):
#            sec_str += "%s, " % _("Enterprise")
#
#        if sec_str:
#            sec_str = sec_str[:-2]
#        else:
#            sec_str = _("None")
#
#        return sec_str

    def _ap_is_enterprise_dbus(self, ap_path):
        ap = dbus.SystemBus().get_object(NM_SERVICE, ap_path)
        wpa_flags = getNMObjProperty(ap, ".AccessPoint", "WpaFlags")
        rsn_flags = getNMObjProperty(ap, ".AccessPoint", "RsnFlags")
        return ((wpa_flags & NM_802_11_AP_SEC_KEY_MGMT_802_1X) or
                (rsn_flags & NM_802_11_AP_SEC_KEY_MGMT_802_1X))

    def _ap_security_string_dbus(self, ap):
        if ap.object_path == "/":
            return ""

        flags = getNMObjProperty(ap, ".AccessPoint", "Flags")
        wpa_flags = getNMObjProperty(ap, ".AccessPoint", "WpaFlags")
        rsn_flags = getNMObjProperty(ap, ".AccessPoint", "RsnFlags")

        sec_str = ""

        if ((flags & NM_802_11_AP_FLAGS_PRIVACY) and
            wpa_flags == NM_802_11_AP_SEC_NONE and
            rsn_flags == NM_802_11_AP_SEC_NONE):
            sec_str += "%s, " % _("WEP")

        if wpa_flags != NM_802_11_AP_SEC_NONE:
            sec_str += "%s, " % _("WPA")

        if rsn_flags != NM_802_11_AP_SEC_NONE:
            sec_str += "%s, " % _("WPA2")

        if ((wpa_flags & NM_802_11_AP_SEC_KEY_MGMT_802_1X) or
            (rsn_flags & NM_802_11_AP_SEC_KEY_MGMT_802_1X)):
            sec_str += "%s, " % _("Enterprise")

        if sec_str:
            sec_str = sec_str[:-2]
        else:
            sec_str = _("None")

        return sec_str

    @property
    def dev_cfgs(self):
        return [row[DEVICES_COLUMN_OBJECT] for
                row in self.dev_cfg_store]

    @property
    def hostname(self):
        return self.entry_hostname.get_text()

    @hostname.setter
    def hostname(self, value):
        if not value:
            return
        self.entry_hostname.set_text(value)


class SecretAgentDialog(GUIObject):
    builderObjects = ["secret_agent_dialog"]
    mainWidgetName = "secret_agent_dialog"
    uiFile = "spokes/network.glade"

    def __init__(self, *args, **kwargs):
        self._content = kwargs.pop('content', {})
        GUIObject.__init__(self, *args, **kwargs)
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
        dbus.service.Object.__init__(self, self._bus, "/org/freedesktop/NetworkManager/SecretAgent")

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

        log.debug("network: secrets requested path '%s' setting '%s' hints '%s' new %d",
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
        if secret['wep_key_type'] == NetworkManager.WepKeyType.KEY:
            if len(value) in (10, 26):
                return all(c in string.hexdigits for c in value)
            elif len(value) in (5, 13):
                return all(c in string.ascii_letters for c in value)
            else:
                return False
        elif secret['wep_key_type'] == NetworkManager.WepKeyType.PASSPHRASE:
            return 0 <= len(value) <= 64
        else:
            return True

def register_secret_agent(spoke):

    if not can_touch_runtime_system("register anaconda secret agent"):
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
    builderObjects = ["networkWindow", "liststore_wireless_network", "liststore_devices", "add_device_dialog", "liststore_add_device"]
    mainWidgetName = "networkWindow"
    uiFile = "spokes/network.glade"
    helpFile = "NetworkSpoke.xml"

    title = CN_("GUI|Spoke", "_NETWORK & HOST NAME")
    icon = "network-transmit-receive-symbolic"

    category = SystemCategory

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self.network_control_box = NetworkControlBox(self.builder, spoke=self)
        self.network_control_box.hostname = self.data.network.hostname
        self.network_control_box.connect("nm-state-changed",
                                         self.on_nm_state_changed)
        self.network_control_box.connect("device-state-changed",
                                         self.on_device_state_changed)

    def apply(self):
        _update_network_data(self.data, self.network_control_box)
        log.debug("network: apply ksdata %s", self.data.network)
        self.network_control_box.kill_nmce(msg="leaving network spoke")

    def execute(self):
        # update system's hostname
        network.set_hostname(self.data.network.hostname)

    @property
    def completed(self):
        # TODO: check also if source requires updates when implemented
        return (not can_touch_runtime_system("require network connection")
                or nm.nm_activated_devices())

    @property
    def mandatory(self):
        return self.data.method.method in ("url", "nfs")

    @property
    def status(self):
        """ A short string describing which devices are connected. """
        return network.status_message()

    def initialize(self):
        register_secret_agent(self)
        NormalSpoke.initialize(self)
        self.network_control_box.initialize()
        if not can_touch_runtime_system("hide hint to use network configuration in DE"):
            self.builder.get_object("network_config_vbox").set_no_show_all(True)
            self.builder.get_object("network_config_vbox").hide()
        else:
            self.builder.get_object("live_hint_label").set_no_show_all(True)
            self.builder.get_object("live_hint_label").hide()

        if not self.data.network.seen:
            _update_network_data(self.data, self.network_control_box)

    def refresh(self):
        NormalSpoke.refresh(self)
        self.network_control_box.refresh()

    def on_nm_state_changed(self, *args):
        gtk_call_once(self._update_status)
        gtk_call_once(self._update_hostname)

    def on_device_state_changed(self, source, device, new_state, *args):
        if new_state in (NetworkManager.DeviceState.ACTIVATED,
                         NetworkManager.DeviceState.DISCONNECTED,
                         NetworkManager.DeviceState.UNAVAILABLE):
            gtk_call_once(self._update_status)

    def _update_status(self):
        hubQ.send_message(self.__class__.__name__, self.status)

    def _update_hostname(self):
        if self.network_control_box.hostname == network.DEFAULT_HOSTNAME:
            hostname = network.getHostname()
            network.update_hostname_data(self.data, hostname)
            self.network_control_box.hostname = self.data.network.hostname

    def on_back_clicked(self, button):
        hostname = self.network_control_box.hostname
        (valid, error) = network.sanityCheckHostname(hostname)
        if not valid:
            self.clear_info()
            msg = _("Host name is not valid: %s") % error
            self.set_warning(msg)
            self.network_control_box.entry_hostname.grab_focus()
        else:
            self.clear_info()
            NormalSpoke.on_back_clicked(self, button)


class NetworkStandaloneSpoke(StandaloneSpoke):
    builderObjects = ["networkStandaloneWindow", "networkControlBox_vbox", "liststore_wireless_network", "liststore_devices", "add_device_dialog", "liststore_add_device"]
    mainWidgetName = "networkStandaloneWindow"
    uiFile = "spokes/network.glade"

    preForHub = SummaryHub
    priority = 10

    def __init__(self, *args, **kwargs):
        StandaloneSpoke.__init__(self, *args, **kwargs)
        self.network_control_box = NetworkControlBox(self.builder, spoke=self)
        self.network_control_box.hostname = self.data.network.hostname
        parent = self.builder.get_object("AnacondaStandaloneWindow-action_area5")
        parent.add(self.network_control_box.vbox)

        self.network_control_box.connect("nm-state-changed",
                                         self.on_nm_state_changed)

        self._initially_available = self.completed
        log.debug("network standalone spoke (init): completed: %s", self._initially_available)
        self._now_available = False

    def apply(self):
        _update_network_data(self.data, self.network_control_box)

        log.debug("network: apply ksdata %s", self.data.network)

        self._now_available = self.completed

        log.debug("network standalone spoke (apply) payload: %s completed: %s", self.payload.baseRepo, self._now_available)
        if not self.payload.baseRepo and not self._initially_available and self._now_available:
            from pyanaconda.packaging import payloadMgr
            payloadMgr.restartThread(self.storage, self.data, self.payload, self.instclass,
                    fallback=not anaconda_flags.automatedInstall)

        self.network_control_box.kill_nmce(msg="leaving standalone network spoke")

    def execute(self):
        # update system's hostname
        network.set_hostname(self.data.network.hostname)

    @property
    def completed(self):
        return (not can_touch_runtime_system("require network connection")
                or nm.nm_activated_devices()
                or self.data.method.method not in ("url", "nfs"))

    def initialize(self):
        register_secret_agent(self)
        StandaloneSpoke.initialize(self)
        self.network_control_box.initialize()

    def refresh(self):
        StandaloneSpoke.refresh(self)
        self.network_control_box.refresh()

    def _on_continue_clicked(self, window, user_data=None):
        hostname = self.network_control_box.hostname
        (valid, error) = network.sanityCheckHostname(hostname)
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
        gtk_call_once(self._update_hostname)

    def _update_hostname(self):
        if self.network_control_box.hostname == network.DEFAULT_HOSTNAME:
            hostname = network.getHostname()
            network.update_hostname_data(self.data, hostname)
            self.network_control_box.hostname = self.data.network.hostname

def _update_network_data(data, ncb):
    data.network.network = []
    for dev_cfg in ncb.dev_cfgs:
        devname = dev_cfg.get_iface()
        nd = network.ksdata_from_ifcfg(devname, dev_cfg.con_uuid)
        if not nd:
            continue
        if devname in nm.nm_activated_devices():
            nd.activate = True
        data.network.network.append(nd)
    hostname = ncb.hostname
    network.update_hostname_data(data, hostname)


def test():
    win = Gtk.Window()
    win.connect("delete-event", Gtk.main_quit)

    builder = Gtk.Builder()
    import os
    ui_file_path = os.environ.get('UIPATH')+'spokes/network.glade'
    builder.add_from_file(ui_file_path)

    n = NetworkControlBox(builder)
    n.initialize()
    n.refresh()

    n.vbox.reparent(win)

    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    test()
