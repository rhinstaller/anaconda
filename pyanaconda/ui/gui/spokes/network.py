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
from pyanaconda.i18n import _, N_
from pyanaconda import constants
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke, StandaloneSpoke
from pyanaconda.ui.gui.categories.system import SystemCategory
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.utils import gtk_call_once, enlightbox
from pyanaconda.ui.common import FirstbootSpokeMixIn

from pyanaconda import network
from pyanaconda.nm import nm_device_setting_value, nm_device_ip_config, nm_activated_devices, nm_device_active_ssid

from gi.repository import GLib, GObject, Pango, Gio, NetworkManager, NMClient
import dbus
import dbus.service
import subprocess
import string

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import ctypes
ctypes.cdll.LoadLibrary("libnm-util.so.2")
nm_utils = ctypes.CDLL("libnm-util.so.2")

import logging
log = logging.getLogger("anaconda")

# These are required for dbus API use we need because of
# NM_GI_BUGS: 767998, 773678
NM_SERVICE = "org.freedesktop.NetworkManager"
NM_802_11_AP_FLAGS_PRIVACY = 0x1
NM_802_11_AP_SEC_NONE = 0x0
NM_802_11_AP_SEC_KEY_MGMT_802_1X = 0x200
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
        if device.get_firmware_missing():
            s = _("Firmware missing")
        elif (device.get_device_type() == NetworkManager.DeviceType.ETHERNET
              and not device.get_carrier()):
            s = _("Cable unplugged")
        else:
            s = _("Unavailable")
    elif state == NetworkManager.DeviceState.DISCONNECTED:
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

configuration_of_disconnected_devices_allowed = True
# it is not in gnome-control-center but it makes sense
# for installer
# https://bugzilla.redhat.com/show_bug.cgi?id=704119

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

class NetworkControlBox(object):

    supported_device_types = [
        NetworkManager.DeviceType.ETHERNET,
        NetworkManager.DeviceType.WIFI,
        NetworkManager.DeviceType.BOND,
        NetworkManager.DeviceType.VLAN,
    ]

    def __init__(self, builder, spoke=None):

        self.builder = builder
        self._running_nmce = None
        self.spoke = spoke

        # button for creating of virtual bond and vlan devices
        self.builder.get_object("add_toolbutton").set_sensitive(True)
        self.builder.get_object("add_toolbutton").connect("clicked",
                                                           self.on_add_device_clicked)
        self.builder.get_object("remove_toolbutton").set_sensitive(False)

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
        self.remote_settings = NMClient.RemoteSettings()

        # devices list
        # limited to wired and wireless
        treeview = self.builder.get_object("treeview_devices")
        self._add_device_columns(treeview)
        devices_store = self.builder.get_object("liststore_devices")
        devices_store.set_sort_column_id(2, Gtk.SortType.ASCENDING)
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
            device.connect("notify::ip4-config", self.on_device_config_changed)
            device.connect("notify::ip6-config", self.on_device_config_changed)
            self.add_device_to_list(device)

        treeview = self.builder.get_object("treeview_devices")
        devices_store = self.builder.get_object("liststore_devices")
        selection = treeview.get_selection()
        itr = devices_store.get_iter_first()
        if itr:
            selection.select_iter(itr)

    def refresh(self):
        device = self.selected_device()
        self.refresh_ui(device)

    # Signal handlers.
    def on_device_selection_changed(self, *args):
        device = self.selected_device()
        if not device:
            return

        log.debug("network: selected device %s", device.get_iface())
        self.refresh_ui(device)

    def on_device_state_changed(self, *args):
        device = args[0]
        new_state = args[1]
        if new_state == NetworkManager.DeviceState.SECONDARIES:
            return
        self._refresh_carrier_info()
        if device == self.selected_device():
            self.refresh_ui(device, new_state)

    def on_device_config_changed(self, device, *args):
        if device == self.selected_device():
            self.refresh_ui(device)

    def on_wireless_ap_changed_cb(self, combobox, *args):
        if self._updating_device:
            return
        itr = combobox.get_active_iter()
        if not itr:
            return

        device = self.selected_device()
        ap_obj_path, ssid_target = combobox.get_model().get(itr, 0, 1)
        self.selected_ssid = ssid_target
        if ap_obj_path == "ap-other...":
            return

        log.info("network: access point changed: %s", ssid_target)

        con = self.find_connection_for_device(device, ssid_target)
        if con:
            self.client.activate_connection(con, device,
                                            None, None, None)
        else:
            self.client.add_and_activate_connection(None, device, ap_obj_path,
                                                    None, None)

    def on_device_added(self, client, device, *args):
        self.add_device_to_list(device)

    def on_device_removed(self, client, device, *args):
        self.remove_device(device)

    def on_edit_connection(self, *args):
        device = self.selected_device()
        if not device:
            return

        con = self.find_active_connection_for_device(device)
        ssid = None
        if not con and configuration_of_disconnected_devices_allowed:
            if device.get_device_type() == NetworkManager.DeviceType.WIFI:
                ssid = self.selected_ssid
            con = self.find_connection_for_device(device, ssid)

        if con:
            uuid = con.get_uuid()
        else:
            return

        # 871132 auto activate wireless connection after editing if it is not
        # already activated (assume entering secrets)
        activate = None
        if (device.get_device_type() == NetworkManager.DeviceType.WIFI and ssid
            and (nm_device_active_ssid(device.get_iface()) == ssid)):
            activate = (con, device)

        log.info("network: configuring connection %s device %s ssid %s", uuid, device.get_iface(), ssid)
        self.kill_nmce(msg="Configure button clicked")
        proc = subprocess.Popen(["nm-connection-editor", "--edit", "%s" % uuid])
        self._running_nmce = proc

        GLib.child_watch_add(proc.pid, self.on_nmce_exited, activate)

    def kill_nmce(self, msg=""):
        if not self._running_nmce:
            return False

        log.debug("network: killing running nm-c-e %s: %s", self._running_nmce.pid, msg)
        self._running_nmce.kill()
        self._running_nmce = None
        return True

    def on_nmce_exited(self, pid, condition, activate):
        # nm-c-e was closed normally, not killed by anaconda
        if condition == 0:
            if self._running_nmce and self._running_nmce.pid == pid:
                self._running_nmce = None
            if activate:
                con, device = activate
                gtk_call_once(self._activate_connection_cb, con, device)
            network.logIfcfgFiles("nm-c-e run")

    def _activate_connection_cb(self, con, device):
        self.client.activate_connection(con, device,
                                        None, None, None)

    def on_wireless_enabled(self, *args):
        switch = self.builder.get_object("device_wireless_off_switch")
        self._updating_device = True
        switch.set_active(self.client.wireless_get_enabled())
        self._updating_device = False

    def on_device_off_toggled(self, switch, *args):
        if self._updating_device:
            return

        active = switch.get_active()
        device = self.selected_device()

        log.info("network: device %s switched %s", device.get_iface(), "on" if active else "off")

        dev_type = device.get_device_type()
        if dev_type in (NetworkManager.DeviceType.ETHERNET,
                        NetworkManager.DeviceType.BOND,
                        NetworkManager.DeviceType.VLAN):
            if active:
                cons = self.remote_settings.list_connections()
                dev_cons = device.filter_connections(cons)
                if dev_cons:
                    self.client.activate_connection(dev_cons[0], device,
                                                    None, None, None)
                else:
                    self.client.add_and_activate_connection(None, device, None,
                                                            None, None)
            else:
                device.disconnect(None, None)
        elif dev_type == NetworkManager.DeviceType.WIFI:
            self.client.wireless_set_enabled(active)


    def on_add_device_clicked(self, *args):
        dialog = self.builder.get_object("add_device_dialog")
        if self.spoke:
            dialog.set_transient_for(self.spoke.window)
        rc = dialog.run()
        dialog.hide()
        if rc == 1:
            ai = self.builder.get_object("combobox_add_device").get_active_iter()
            model = self.builder.get_object("liststore_add_device")
            dev_type = model[ai][1]
            self.add_device(dev_type)

    def add_device(self, ty):
        log.info("network: adding device of type %s", ty)
        self.kill_nmce(msg="Add device button clicked")
        proc = subprocess.Popen(["nm-connection-editor", "--create", "--type=%s" % ty])
        self._running_nmce = proc

        GLib.child_watch_add(proc.pid, self.on_nmce_adding_exited)

    def on_nmce_adding_exited(self, pid, condition):
        if condition == 0:
            if self._running_nmce and self._running_nmce.pid == pid:
                self._running_nmce = None
            network.logIfcfgFiles("nm-c-e run")

    def selected_device(self):
        selection = self.builder.get_object("treeview_devices").get_selection()
        (model, itr) = selection.get_selected()
        if not itr:
            return None
        return model.get(itr, DEVICES_COLUMN_OBJECT)[0]

    def find_connection_for_device(self, device, ssid=None):
        dev_type = device.get_device_type()
        cons = self.remote_settings.list_connections()
        for con in cons:
            con_type = con.get_setting_connection().get_connection_type()
            if dev_type == NetworkManager.DeviceType.ETHERNET:
                if con_type != NetworkManager.SETTING_WIRED_SETTING_NAME:
                    continue
                settings = con.get_setting_wired()
                con_hwaddr = ":".join("%02X" % ord(bytechar)
                                      for bytechar in settings.get_mac_address())
                if con_hwaddr == device.get_hw_address():
                    return con
            elif dev_type == NetworkManager.DeviceType.WIFI:
                if con_type != NetworkManager.SETTING_WIRELESS_SETTING_NAME:
                    continue
                settings = con.get_setting_wireless()
                if ssid == settings.get_ssid():
                    return con
            elif dev_type == NetworkManager.DeviceType.BOND:
                if con_type != NetworkManager.SETTING_BOND_SETTING_NAME:
                    continue
                settings = con.get_setting_bond()
                if device.get_iface() == settings.get_virtual_iface_name():
                    return con
            elif dev_type == NetworkManager.DeviceType.VLAN:
                if con_type != NetworkManager.SETTING_VLAN_SETTING_NAME:
                    continue
                settings = con.get_setting_vlan()
                if device.get_iface() == settings.get_interface_name():
                    return con
            else:
                return None

    def find_active_connection_for_device(self, device):
        cons = self.client.get_active_connections()
        for con in cons:
            if con.get_devices()[0] is device:
                return self.remote_settings.get_connection_by_path(con.get_connection())
        return None

    def _device_is_stored(self, nm_device):
        """Check that device with Udi of nm_device is already in liststore"""
        udi = nm_device.get_udi()
        model = self.builder.get_object("liststore_devices")
        for row in model:
            if udi == row[DEVICES_COLUMN_OBJECT].get_udi():
                return True
        return False

    def add_device_to_list(self, device):
        if self._device_is_stored(device):
            return

        if device.get_device_type() not in self.supported_device_types:
            return

        device.connect("state-changed", self.on_device_state_changed)

        self.builder.get_object("liststore_devices").append([
            self._dev_icon_name(device),
            self._dev_type_sort_value(device),
            self._dev_title(device),
            device,
        ])

    def _dev_icon_name(self, device):
        icon_name = ""
        dev_type = device.get_device_type()
        if  dev_type == NetworkManager.DeviceType.ETHERNET:
            if device.get_state() == NetworkManager.DeviceState.UNAVAILABLE:
                icon_name = "network-wired-disconnected"
            else:
                icon_name = "network-wired"
        elif  dev_type == NetworkManager.DeviceType.BOND:
            if device.get_state() == NetworkManager.DeviceState.UNAVAILABLE:
                icon_name = "network-wired-disconnected"
            else:
                icon_name = "network-wired"
        elif  dev_type == NetworkManager.DeviceType.VLAN:
            if device.get_state() == NetworkManager.DeviceState.UNAVAILABLE:
                icon_name = "network-wired-disconnected"
            else:
                icon_name = "network-wired"
        elif dev_type == NetworkManager.DeviceType.WIFI:
            icon_name = "network-wireless"

        return icon_name

    def _dev_type_sort_value(self, device):
        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.ETHERNET:
            s = "1"
        elif dev_type == NetworkManager.DeviceType.WIFI:
            s = "2"
        else:
            s = "3"
        return s

    def _dev_title(self, device):
        unplugged = ''
        if (device.get_state() == NetworkManager.DeviceState.UNAVAILABLE
            and device.get_device_type() == NetworkManager.DeviceType.ETHERNET
            and not device.get_carrier()):
            # Translators: ethernet cable is unplugged
            unplugged = ', <i>%s</i>' % _("unplugged")
        title = '<span size="large">%s (%s%s)</span>' % (self._dev_type_str(device),
                                                         device.get_iface(),
                                                         unplugged)
        title += '\n<span size="small">%s %s</span>' % (device.get_vendor() or "",
                                                        device.get_product() or "")
        return title

    def _dev_type_str(self, device):
        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.UNKNOWN:
            title = _("Unknown")
        elif dev_type == NetworkManager.DeviceType.ETHERNET:
            title = _("Ethernet")
        elif dev_type == NetworkManager.DeviceType.WIFI:
            title = _("Wireless")
        elif dev_type == NetworkManager.DeviceType.BOND:
            title = _("Bond")
        elif dev_type == NetworkManager.DeviceType.VLAN:
            title = _("Vlan")
        else:
            title = ""
        return title

    def remove_device(self, device):
        # This should not concern wifi and ethernet devices,
        # just virtual devices e.g. vpn probably
        # TODO test!, remove perhaps
        model = self.builder.get_object("liststore_devices")
        rows_to_remove = []
        for row in model:
            if (device.get_udi() == row[DEVICES_COLUMN_OBJECT].get_udi()):
                rows_to_remove.append(row)
        for row in rows_to_remove:
            del(row)

    def refresh_ui(self, device, state=None):

        if not device:
            notebook = self.builder.get_object("notebook_types")
            notebook.set_current_page(5)
            return

        self._refresh_device_type_page(device)
        self._refresh_header_ui(device, state)
        self._refresh_slaves(device)
        self._refresh_parent_vlanid(device)
        self._refresh_speed_hwaddr(device, state)
        self._refresh_ap(device, state)
        self._refresh_device_cfg(device)

    def _refresh_device_cfg(self, device):

        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.ETHERNET:
            dt = "wired"
        elif dev_type == NetworkManager.DeviceType.WIFI:
            dt = "wireless"
        elif dev_type == NetworkManager.DeviceType.BOND:
            dt = "wired"
        elif dev_type == NetworkManager.DeviceType.VLAN:
            dt = "wired"

        ipv4cfg = nm_device_ip_config(device.get_iface(), version=4)
        ipv6cfg = nm_device_ip_config(device.get_iface(), version=6)

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

    def _refresh_ap(self, device, state=None):
        if device.get_device_type() != NetworkManager.DeviceType.WIFI:
            return

        if state is None:
            state = device.get_state()
        if state == NetworkManager.DeviceState.UNAVAILABLE:
            ap_str = None
        else:
            active_ap = device.get_active_access_point()
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
            aps = self._get_strongest_unique_aps(device.get_access_points())
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

    def _refresh_slaves(self, device):
        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.BOND:
            slaves = ",".join(s.get_iface()
                for s in device.get_slaves())
            self._set_device_info_value("wired", "slaves", slaves)

    def _refresh_parent_vlanid(self, device):
        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.VLAN:
            self._set_device_info_value("wired", "vlanid", str(device.get_vlan_id()))
            parent = nm_device_setting_value(device.get_iface(), "vlan", "parent")
            self._set_device_info_value("wired", "parent", parent)

    def _refresh_speed_hwaddr(self, device, state=None):
        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.ETHERNET:
            dt = "wired"
            speed = device.get_speed()
        elif dev_type == NetworkManager.DeviceType.WIFI:
            dt = "wireless"
            speed = device.get_bitrate() / 1000
        elif dev_type == NetworkManager.DeviceType.BOND:
            dt = "wired"
            speed = None
        elif dev_type == NetworkManager.DeviceType.VLAN:
            dt = "wired"
            speed = None

        if state is None:
            state = device.get_state()
        if state == NetworkManager.DeviceState.UNAVAILABLE:
            speed_str = None
        elif speed:
            speed_str = _("%d Mb/s") % speed
        else:
            speed_str = ""
        self._set_device_info_value(dt, "speed", speed_str)
        self._set_device_info_value(dt, "mac", device.get_hw_address())

    def _refresh_device_type_page(self, device):
        notebook = self.builder.get_object("notebook_types")
        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.ETHERNET:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_slaves").hide()
            self.builder.get_object("label_wired_slaves").hide()
            self.builder.get_object("heading_wired_vlanid").hide()
            self.builder.get_object("label_wired_vlanid").hide()
            self.builder.get_object("heading_wired_parent").hide()
            self.builder.get_object("label_wired_parent").hide()
        elif dev_type == NetworkManager.DeviceType.BOND:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_slaves").show()
            self.builder.get_object("label_wired_slaves").show()
            self.builder.get_object("heading_wired_vlanid").hide()
            self.builder.get_object("label_wired_vlanid").hide()
            self.builder.get_object("heading_wired_parent").hide()
            self.builder.get_object("label_wired_parent").hide()
        elif dev_type == NetworkManager.DeviceType.VLAN:
            notebook.set_current_page(0)
            self.builder.get_object("heading_wired_slaves").hide()
            self.builder.get_object("label_wired_slaves").hide()
            self.builder.get_object("heading_wired_vlanid").hide()
            self.builder.get_object("label_wired_vlanid").hide()
            self.builder.get_object("heading_wired_parent").hide()
            self.builder.get_object("label_wired_parent").hide()
        elif dev_type == NetworkManager.DeviceType.WIFI:
            notebook.set_current_page(1)

    def _refresh_carrier_info(self):
        for i in self.builder.get_object("liststore_devices"):
            i[DEVICES_COLUMN_TITLE] = self._dev_title(i[DEVICES_COLUMN_OBJECT])

    def _refresh_header_ui(self, device, state=None):
        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.ETHERNET:
            dev_type_str = "wired"
        elif dev_type == NetworkManager.DeviceType.WIFI:
            dev_type_str = "wireless"
        elif dev_type == NetworkManager.DeviceType.BOND:
            dev_type_str = "wired"
        elif dev_type == NetworkManager.DeviceType.VLAN:
            dev_type_str = "wired"

        if dev_type_str == "wired":
            # update icon according to device status
            img = self.builder.get_object("image_wired_device")
            img.set_from_icon_name(self._dev_icon_name(device), Gtk.IconSize.DIALOG)

        # TODO: is this necessary? Isn't it static from glade?
        self.builder.get_object("label_%s_device" % dev_type_str).set_label(
            "%s (%s)" % (self._dev_type_str(device), device.get_iface()))

        if state is None:
            state = device.get_state()
        self.builder.get_object("label_%s_status" % dev_type_str).set_label(
            localized_string_of_device_state(device, state))

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
            if not configuration_of_disconnected_devices_allowed:
                self.builder.get_object("button_%s_options" % dev_type_str).set_sensitive(state == NetworkManager.DeviceState.ACTIVATED)
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
        mode = getNMObjProperty(ap_dbus, ".AccessPoint", "Mode")

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
    def listed_devices(self):
        return [row[DEVICES_COLUMN_OBJECT] for
                row in self.builder.get_object("liststore_devices")]

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
        img = self.builder.get_object("image_password_dialog")
        img.set_from_icon_name("dialog-password-symbolic", Gtk.IconSize.DIALOG)
        self.builder.get_object("label_message").set_text(self._content['message'])
        self.builder.get_object("label_title").set_use_markup(True)
        self.builder.get_object("label_title").set_markup("<b>%s</b>" % self._content['title'])
        self._connect_button = self.builder.get_object("connect_button")

    def initialize(self):
        self._entries = {}
        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(6)

        for row, secret in enumerate(self._content['secrets']):
            label = Gtk.Label(secret['label'])
            label.set_halign(Gtk.Align.START)
            entry = Gtk.Entry()
            entry.set_visibility(False)
            entry.set_hexpand(True)
            self._validate(entry, secret)
            entry.connect("changed", self._validate, secret)
            entry.connect("activate", self._password_entered_cb)
            self._entries[secret['key']] = entry
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
            secret['value'] = self._entries[secret['key']].get_text()
        self.window.destroy()
        return rc

    @property
    def valid(self):
        return all(secret['valid'] for secret in self._content['secrets'])

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
    def GetSecrets(self, connection_hash, connection_path, setting_name, hints, request_new, sender=None):
        if not sender:
            raise NotAuthorizedException("Internal error: couldn't get sender")
        uid = self._bus.get_unix_user(sender)
        if uid != 0:
            raise NotAuthorizedException("UID %d not authorized" % uid)

        log.debug("Secrets requested path '%s' setting '%s' hints '%s' new %d",
                  connection_path, setting_name, str(hints), request_new)

        content = self._get_content(setting_name, connection_hash)
        dialog = SecretAgentDialog(self.spoke.data, content=content)
        with enlightbox(self.spoke.window, dialog.window):
            rc = dialog.run()

        secrets = dbus.Dictionary()
        if rc == 1:
            for secret in content['secrets']:
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
            content['secrets'] = self._get_wireless_secrets(connection_hash[setting_name])
        else:
            log.info("Connection type %s not supported by secret agent", connection_type)

        return content

    def _get_wireless_secrets(self, original_secrets):
        secrets = []
        key_mgmt = original_secrets['key-mgmt']
        if key_mgmt in ['wpa-none', 'wpa-psk']:
            secrets.append({'label'     : _('_Password:'),
                            'key'      : 'psk',
                            'value'    : original_secrets.get('psk', ''),
                            'validate' : self._validate_wpapsk,
                            'password' : True})
        # static WEP
        elif key_mgmt == 'none':
            key_idx = str(original_secrets.get('wep_tx_keyidx', '0'))
            secrets.append({'label'     : _('_Key:'),
                            'key'      : 'wep-key%s' % key_idx,
                            'value'    : original_secrets.get('wep-key%s' % key_idx, ''),
                            'wep_key_type': original_secrets.get('wep-key-type', ''),
                            'validate' : self._validate_staticwep,
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
                return all(c in string.letters for c in value)
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
        secret_agent = SecretAgent(spoke)
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

    title = N_("_NETWORK CONFIGURATION")
    icon = "network-transmit-receive-symbolic"

    category = SystemCategory

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self.network_control_box = NetworkControlBox(self.builder, spoke=self)
        self.network_control_box.hostname = self.data.network.hostname
        self.network_control_box.client.connect("notify::%s" %
                                                NMClient.CLIENT_STATE,
                                                self.on_nm_state_changed)
        for device in self.network_control_box.client.get_devices():
            device.connect("state-changed", self.on_device_state_changed)

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
                or nm_activated_devices())

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

    def on_device_state_changed(self, *args):
        new_state = args[1]
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
            msg = _("Hostname is not valid: %s") % error
            self.set_warning(msg)
            self.network_control_box.entry_hostname.grab_focus()
            self.window.show_all()
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

        self.network_control_box.client.connect("notify::%s" %
                                                NMClient.CLIENT_STATE,
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
            from pyanaconda.packaging import payloadInitialize
            from pyanaconda.threads import threadMgr, AnacondaThread

            threadMgr.wait(constants.THREAD_PAYLOAD)

            threadMgr.add(AnacondaThread(name=constants.THREAD_PAYLOAD, target=payloadInitialize, args=(self.storage, self.data, self.payload)))

        self.network_control_box.kill_nmce(msg="leaving standalone network spoke")

    def execute(self):
        # update system's hostname
        network.set_hostname(self.data.network.hostname)

    @property
    def completed(self):
        return (not can_touch_runtime_system("require network connection")
                or nm_activated_devices())

    def initialize(self):
        register_secret_agent(self)
        StandaloneSpoke.initialize(self)
        self.network_control_box.initialize()

    def refresh(self):
        StandaloneSpoke.refresh(self)
        self.network_control_box.refresh()

    def _on_continue_clicked(self, cb):
        hostname = self.network_control_box.hostname
        (valid, error) = network.sanityCheckHostname(hostname)
        if not valid:
            self.clear_info()
            msg = _("Hostname is not valid: %s") % error
            self.set_warning(msg)
            self.network_control_box.entry_hostname.grab_focus()
            self.window.show_all()
        else:
            self.clear_info()
            StandaloneSpoke._on_continue_clicked(self, cb)

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
    for dev in ncb.listed_devices:
        devname = dev.get_iface()
        nd = network.ksdata_from_ifcfg(devname)
        if not nd:
            continue
        if devname in nm_activated_devices():
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
