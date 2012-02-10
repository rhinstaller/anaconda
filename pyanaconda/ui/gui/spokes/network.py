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
# - secrets agent - use nm_applet?
#   see we_dont_have_nm_applet_as_secrets_agent
# - callback on NM_CLIENT_ACTIVE_CONNECTIONS
# - support connection to hidden network (ap-other)
# - apply(): fill ksdata (from ifcfg files!)
# - device_is_stored
# - NMClient.CLIENT_WIRELESS_ENABLED callback (hw switch?) - test
# - nm-c-e run: blocking? logging?

from gi.repository import Gtk, AnacondaWidgets

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke, StandaloneSpoke
from pyanaconda.ui.gui.categories.software import SoftwareCategory
from pyanaconda.ui.gui.hubs.summary import SummaryHub

from gi.repository import GLib, GObject, Pango, Gio, NetworkManager, NMClient
import dbus
import socket
import subprocess
import struct
import time
from dbus.mainloop.glib import DBusGMainLoop
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

import ctypes
ctypes.cdll.LoadLibrary("libnm-util.so.2")
nm_utils = ctypes.CDLL("libnm-util.so.2")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

# These are required for dbus API use we need because of
# NM_GI_BUGS: 767998, 773678
NM_SERVICE = "org.freedesktop.NetworkManager"
NM_MANAGER_PATH = "/org/freedesktop/NetworkManager"
NM_SETTINGS_PATH = "/org/freedesktop/NetworkManager/Settings"
NM_MANAGER_IFACE = "org.freedesktop.NetworkManager"
NM_SETTINGS_IFACE = "org.freedesktop.NetworkManager.Settings"
NM_CONNECTION_IFACE = "org.freedesktop.NetworkManager.Settings.Connection"
NM_DEVICE_IFACE = "org.freedesktop.NetworkManager.Device"
NM_802_11_AP_FLAGS_PRIVACY = 0x1
NM_802_11_AP_SEC_NONE = 0x0
NM_802_11_AP_SEC_KEY_MGMT_802_1X = 0x200
DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"

def getNMObjProperty(object, nm_iface_suffix, property):
    props_iface = dbus.Interface(object, DBUS_PROPS_IFACE)
    return props_iface.Get("org.freedesktop.NetworkManager"+nm_iface_suffix,
                           property)


DEVICES_COLUMN_TITLE  = 2
DEVICES_COLUMN_OBJECT = 3


def localized_string_of_device_state(device):
    str = _("Status unknown (missing)")

    state = device.get_state()
    if state == NetworkManager.DeviceState.UNKNOWN:
        str = _("Status unknown")
    elif state == NetworkManager.DeviceState.UNMANAGED:
        str = _("Unmanaged")
    elif state == NetworkManager.DeviceState.UNAVAILABLE:
        if device.get_firmware_missing():
            str = _("Firmware missing")
        elif (device.get_device_type() == NetworkManager.DeviceType.ETHERNET
              and not device.get_carrier()):
            str = _("Cable unplugged")
        else:
            str = _("Unavailable")
    elif state == NetworkManager.DeviceState.DISCONNECTED:
        str = _("Disconnected")
    elif state in (NetworkManager.DeviceState.PREPARE,
                   NetworkManager.DeviceState.CONFIG,
                   NetworkManager.DeviceState.IP_CONFIG,
                   NetworkManager.DeviceState.IP_CHECK):
        str = _("Connecting")
    elif state == NetworkManager.DeviceState.NEED_AUTH:
        str = _("Authentication required")
    elif state == NetworkManager.DeviceState.ACTIVATED:
        str = _("Connected")
    elif state == NetworkManager.DeviceState.DEACTIVATING:
        str = _("Disconnecting")
    elif state == NetworkManager.DeviceState.FAILED:
        str = _("Connection failed")

    return str

configuration_of_disconnected_devices_allowed = True
# it is not in gnome-control-center but it makes sense
# for installer
# https://bugzilla.redhat.com/show_bug.cgi?id=704119

we_dont_have_nm_applet_as_secrets_agent = True
# so we have to disconnect from former ap before trying
# to connect to new one bound to fail due to no secrets

__all__ = ["NetworkSpoke"]

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


    def do_get_property(self, property):
        if property.name == 'signal':
            return self.signal
        else:
            raise AttributeError, 'unknown property %s' % property.name

    def do_set_property(self, property, value):
        if property.name == 'signal':
            self.signal = value
            self._set_icon_name(value)
        else:
            raise AttributeError, 'unknown property %s' % property.name

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

    def do_get_property(self, property):
        if property.name == 'security':
            return self.security
        else:
            raise AttributeError, 'unknown property %s' % property.name

    def do_set_property(self, property, value):
        if property.name == 'security':
            self.security = value
            self._set_icon_name(value)
        else:
            raise AttributeError, 'unknown property %s' % property.name

    def _set_icon_name(self, security):
        self.icon_name = ""
        if security not in (NM_AP_SEC_NONE, NM_AP_SEC_UNKNOWN):
            self.icon_name = "network-wireless-encrypted-symbolic"

        self.set_property("icon-name", self.icon_name)

class NetworkControlBox():

    supported_device_types = [
        NetworkManager.DeviceType.ETHERNET,
        NetworkManager.DeviceType.WIFI,
    ]

    def __init__(self, builder):

        self.builder = builder

        # these buttons are only for vpn and proxy
        self.builder.get_object("add_toolbutton").set_sensitive(False)
        self.builder.get_object("remove_toolbutton").set_sensitive(False)

        for id in ["start_hotspot_button",
                   "stop_hotspot_button",
                   "heading_hotspot_network_name",
                   "heading_hotspot_security_key",
                   "label_hotspot_network_name",
                   "label_hotspot_security_key",
                   "devices_toolbar",
                   "hbox54",
                  ]:
            self.builder.get_object(id).set_no_show_all(True)
            self.builder.get_object(id).hide()

        self.builder.get_object("notebook_types").set_show_tabs(False)

        self._refresh_idle = None
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

        # NM Client
        self.client.connect("device-added", self.on_device_added)
        self.client.connect("device-removed", self.on_device_removed)
        # TODO (active_connections_changed)
        #self.client.connect("notify::%s" % NMClient.CLIENT_ACTIVE_CONNECTIONS,
        #                    self.on_active_connections_changed)

        self.builder.get_object("device_wired_off_switch").connect("notify::active",
                                                             self.on_device_off_toggled)
        self.builder.get_object("device_wireless_off_switch").connect("notify::active",
                                                             self.on_device_off_toggled)
        # TODO
        #self.client.connect("notify::%s" % NMClient.CLIENT_WIRELESS_ENABLED,
        #                    self._wireless_enabled_toggled)

        self.builder.get_object("button_wired_options").connect("clicked",
                                                           self.on_edit_connection)
        self.builder.get_object("button_wireless_options").connect("clicked",
                                                              self.on_edit_connection)

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
            self.add_device(device)

        treeview = self.builder.get_object("treeview_devices")
        devices_store = self.builder.get_object("liststore_devices")
        selection = treeview.get_selection()
        selection.select_iter(devices_store.get_iter_first())

    def refresh(self):
        self.refresh_ui()

    def status(self):
        active_wired_devs = []
        active_wireless_devs = []

        for con in self.client.get_active_connections():
            device = con.get_devices()[0]
            if device.get_device_type() == NetworkManager.DeviceType.ETHERNET:
                active_wired_devs.append(device.get_iface())
            elif device.get_device_type() == NetworkManager.DeviceType.WIFI:
                active_wireless_devs.append([device.get_iface(),
                                    device.get_active_access_point().get_ssid()])

        numdevs = len(active_wired_devs) + len(active_wireless_devs)
        if numdevs:
            if numdevs == 1:
                if active_wired_devs:
                    msg = _("Wired (%s) connected") % active_wired_devs[0]
                else:
                    msg = _("Wireless (%s) connected to %s" %
                            tuple(active_wireless_devs[0]))

            else:
                devlist = ", ".join(active_wired_devs +
                                    ["%s (%s)" % (iface, ap) for iface, ap in
                                     active_wireless_devs])
                msg = _("Connected devices: %s") % devlist
        else:
            msg = _("Not connected")

        return msg

    # Signal handlers.
    def on_device_selection_changed(self, *args):
        print "DBG: on_device_selection_changed"
        self.refresh_ui()

    def on_device_state_changed(self, *args):
        print "DBG: on_device_state_changed"
        self.refresh_ui()

    def on_active_connections_changed(self, *args):
        print "DBG: on_active_connections_changed"
        self.refresh_ui()

    def on_wireless_ap_changed_cb(self, combobox, *args):
        print "DBG: on_wireles_ap_changed_cb"

        if self._updating_device:
            return
        iter = combobox.get_active_iter()
        if not iter:
            return

        print "DBG: on_wireless_ap_changed_cb was not ignored"

        device = self.selected_device()
        ap_obj_path, ssid_target = combobox.get_model().get(iter, 0, 1)
        if ap_obj_path == "ap-other...":
            print "DBG: connection to hidden network not supported (nm-applet)"
            return

        if we_dont_have_nm_applet_as_secrets_agent:
            if self.find_active_connection_for_device(device):
                # TODO we should pass callback and block until really disconnected?
                # or is wireless reconnection stuff solved in NM? TEST!
                device.disconnect(None, None)

        con = self.find_connection_for_device(device, ssid_target)
        if con:
            self.client.activate_connection(con, device,
                                            None, None, None)
        else:
            self.client.add_and_activate_connection(None, device, ap_obj_path,
                                                    None, None)

    def on_device_added(self, device):
        self.add_device(device)

    def on_device_removed(self, device):
        self.remove_device(device)

    def on_edit_connection(self, *args):
        device = self.selected_device()
        if not device:
            return

        con = self.find_active_connection_for_device(device)
        if not con and configuration_of_disconnected_devices_allowed:
            if device.get_device_type() == NetworkManager.DeviceType.WIFI:
                combobox = self.builder.get_object("combobox_wireless_network_name")
                iter = combobox.get_active_iter()
                if not iter:
                    return
                ap_obj_path, ssid = combobox.get_model().get(iter, 0, 1)

            con = self.find_connection_for_device(device, ssid=None)

        if con:
            uuid = con.get_uuid()
        else:
            print "DBG: no connection to be edited found"
            return

        subprocess.Popen(["nm-connection-editor", "--edit", "%s" % uuid])

    def on_device_off_toggled(self, switch, *args):
        if self._updating_device:
            print "DBG: off switch ignored"
            return

        print "DBG: off switch"
        active = switch.get_active()

        device = self.selected_device()

        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.ETHERNET:
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

    def selected_device(self):
        selection = self.builder.get_object("treeview_devices").get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return None
        return model.get(iter, DEVICES_COLUMN_OBJECT)[0]

    def find_connection_for_device(self, device, ssid=None):
        dev_hwaddr = device.get_hw_address()
        cons = self.remote_settings.list_connections()
        for con in cons:
            con_type = con.get_setting_connection().get_connection_type()
            if con_type == NetworkManager.SETTING_WIRED_SETTING_NAME:
                settings = con.get_setting_wired()
            elif con_type == NetworkManager.SETTING_WIRELESS_SETTING_NAME:
                settings = con.get_setting_wireless()
                if ssid and ssid != settings.get_ssid():
                    continue
            else:
                continue
            con_hwaddr = ":".join("%02X" % ord(bytechar) for bytechar in settings.get_mac_address())
            if con_hwaddr == dev_hwaddr:
                return con
        return None

    def find_active_connection_for_device(self, device):
        cons = self.client.get_active_connections()
        for con in cons:
            if con.get_devices()[0] is device:
                return self.remote_settings.get_connection_by_path(con.get_connection())
        return None

    def _device_is_stored(self, nm_device):
        """TODO check that device with Udi of nm_device is already in
        liststore"""
        return False

    def add_device(self, device):
        print "DBG: adding device %s" % device

        if self._device_is_stored(device):
            print "DBG: device already stored"
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
        elif dev_type == NetworkManager.DeviceType.WIFI:
            icon_name = "network-wireless"

        return icon_name

    def _dev_type_sort_value(self, device):
        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.ETHERNET:
            str = "1"
        elif dev_type == NetworkManager.DeviceType.WIFI:
            str = "2"
        else:
            str = "3"
        return str

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
        title += '\n<span size="small">%s %s</span>' % (device.get_vendor(),
                                                        device.get_product())
        return title

    def _dev_type_str(self, device):
        dev_type = device.get_device_type()
        if dev_type == NetworkManager.DeviceType.UNKNOWN:
            title = _("Unknown")
        elif dev_type == NetworkManager.DeviceType.ETHERNET:
            title = _("Ethernet")
        elif dev_type == NetworkManager.DeviceType.WIFI:
            title = _("Wireless")
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

    def refresh_ui(self):
        if self._refresh_idle:
            print "DBG: refresh_ui_idle found"
            return
        time.sleep(0.3)
        self._refresh_idle = GLib.idle_add(self.refresh_ui_idle)
        print "DBG: refresh_ui_idle planned"

    def refresh_ui_idle(self):
        print "DBG: refreshing ui"
        self.refresh_device_ui(self.selected_device())
        self._refresh_idle = None

    def refresh_device_ui(self, device):

        notebook = self.builder.get_object("notebook_types")

        dev_type = device.get_device_type()

        if dev_type == NetworkManager.DeviceType.ETHERNET:

            dt = "wired"
            notebook.set_current_page(0)

            self._refresh_header_ui(device, dt)

            speed = device.get_speed()
            if device.get_state() == NetworkManager.DeviceState.UNAVAILABLE:
                speed_str = None
            elif speed:
                speed_str = _("%d Mb/s") % speed
            else:
                speed_str = ""
            self._set_device_info_value(dt, "speed", speed_str)

            self._set_device_info_value(dt, "mac", device.get_hw_address())

        elif dev_type == NetworkManager.DeviceType.WIFI:

            dt = "wireless"
            notebook.set_current_page(1)

            self._refresh_header_ui(device, dt)

            speed = device.get_bitrate()
            if device.get_state() == NetworkManager.DeviceState.UNAVAILABLE:
                speed_str = None
            elif speed:
                speed_str = _("%d Mb/s") % (speed / 1000)
            else:
                speed_str = ""
            self._set_device_info_value(dt, "speed", speed_str)

            self._set_device_info_value(dt, "mac", device.get_hw_address())

            if device.get_state() == NetworkManager.DeviceState.UNAVAILABLE:
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

            self._set_device_info_value(dt, "security", ap_str)

            if device.get_state() == NetworkManager.DeviceState.UNAVAILABLE:
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
                self._updating_device = False

        else:
            print ("DBG: unsupported device type in the list!")
            return

        # Only dhcp info is presented for ipv4, for static go to Options...?

        ipv4cfg = device.get_ip4_config()
        if (ipv4cfg
            and device.get_state() == NetworkManager.DeviceState.ACTIVATED):
            addr = socket.inet_ntoa(struct.pack('=L',
                                                ipv4cfg.get_addresses()[0].get_address()))
            self._set_device_info_value(dt, "ipv4", addr)
            dnss = " ".join([socket.inet_ntoa(struct.pack('=L', addr))
                             for addr in ipv4cfg.get_nameservers()])
            self._set_device_info_value(dt, "dns", dnss)
            gateway = socket.inet_ntoa(struct.pack('=L',
                                                   ipv4cfg.get_addresses()[0].get_gateway()))
            self._set_device_info_value(dt, "route", gateway)
            if dt == "wired":
                prefix = ipv4cfg.get_addresses()[0].get_prefix()
                netmask = nm_utils.nm_utils_ip4_prefix_to_netmask(prefix)
                netmask = socket.inet_ntoa(struct.pack('=L', netmask))
                self._set_device_info_value(dt, "subnet", netmask)
        else:
            self._set_device_info_value(dt, "ipv4", None)
            self._set_device_info_value(dt, "dns", None)
            self._set_device_info_value(dt, "route", None)
            if dt == "wired":
                self._set_device_info_value(dt, "subnet", None)

        # TODO NM_GI_BUGS - segfaults on get_addres(), get_prefix()
        ipv6_addr = None
        ipv6cfg = device.get_ip6_config()
        if (ipv6cfg
            and device.get_state() == NetworkManager.DeviceState.ACTIVATED):
            config = dbus.SystemBus().get_object(NM_SERVICE, ipv6cfg.get_path())
            addr, prefix, gw = getNMObjProperty(config, ".IP6Config",
                                                "Addresses")[0]
            ipv6_addr = socket.inet_ntop(socket.AF_INET6, "".join(str(byte) for byte in addr))
        self._set_device_info_value(dt, "ipv6", ipv6_addr)

        if ipv4cfg and ipv6_addr:
            self.builder.get_object("heading_%s_ipv4" % dt).set_label(_("IPv4 Address"))
            self.builder.get_object("heading_%s_ipv6" % dt).set_label(_("IPv6 Address"))
        elif ipv4cfg:
            self.builder.get_object("heading_%s_ipv4" % dt).set_label(_("IP Address"))
        elif ipv6_addr:
            self.builder.get_object("heading_%s_ipv6" % dt).set_label(_("IP Address"))

        self._refresh_carrier_info()

    def _refresh_carrier_info(self):
        for i in self.builder.get_object("liststore_devices"):
            i[DEVICES_COLUMN_TITLE] = self._dev_title(i[DEVICES_COLUMN_OBJECT])

    def _refresh_header_ui(self, device, dev_type_str):

        if dev_type_str == "wired":
            # update icon according to device status
            img = self.builder.get_object("image_wired_device")
            img.set_from_icon_name(self._dev_icon_name(device), Gtk.IconSize.DIALOG)

        # TODO: is this necessary? Isn't it static from glade?
        self.builder.get_object("label_%s_device" % dev_type_str).set_label(
            "%s (%s)" % (self._dev_type_str(device), device.get_iface()))

        state = device.get_state()
        self.builder.get_object("label_%s_status" % dev_type_str).set_label(
            localized_string_of_device_state(device))

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
            switch.set_active(self.client.wireless_get_enabled())

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
        iter = store.append([ap.get_path(),
                             ssid,
                             ssid,
                             ap.get_strength(),
                             mode,
                             security])
        if active:
            self.builder.get_object("combobox_wireless_network_name").set_active_iter(iter)

    def _get_strongest_unique_aps(self, access_points):
        strongest_aps = {}
        for ap in access_points:
            ssid = ap.get_ssid()
            if ssid in strongest_aps:
                #print "DBG: found %s duplicate" % ssid
                if ap.get_strength() > strongest_aps[ssid].get_strength():
                    strongest_aps[ssid] = ap
                    #print "DBG: ...stronger"
            else:
                strongest_aps[ssid] = ap
                #print "DBG: adding %s ap" % ssid

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
            type = NM_AP_SEC_NONE
        elif (flags & NM_802_11_AP_FLAGS_PRIVACY and
              wpa_flags == NM_802_11_AP_SEC_NONE and
              rsn_flags == NM_802_11_AP_SEC_NONE):
            type = NM_AP_SEC_WEP
        elif (not (flags & NM_802_11_AP_FLAGS_PRIVACY) and
              wpa_flags != NM_802_11_AP_SEC_NONE and
              rsn_flags != NM_802_11_AP_SEC_NONE):
            type = NM_AP_SEC_WPA
        else:
            type = NM_AP_SEC_WPA2

        return type

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

class NetworkSpoke(NormalSpoke):
    builderObjects = ["networkWindow", "liststore_wireless_network", "liststore_devices"]
    mainWidgetName = "networkWindow"
    uiFile = "spokes/network.ui"

    title = N_("NETWORK CONFIGURATION")
    icon = "network-transmit-receive-symbolic"

    category = SoftwareCategory

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self.network_control_box = NetworkControlBox(self.builder)

    def apply(self):
        pass

    @property
    def completed(self):
        return self.status != _("Not connected")

    @property
    def status(self):
        """ A short string describing which devices are connected. """
        return self.network_control_box.status()

    def initialize(self):
        NormalSpoke.initialize(self)
        self.network_control_box.initialize()

    def refresh(self):
        NormalSpoke.refresh(self)
        self.network_control_box.refresh()


class NetworkStandaloneSpoke(StandaloneSpoke):
    builderObjects = ["networkStandaloneWindow", "networkControlBox_vbox", "liststore_wireless_network", "liststore_devices"]
    mainWidgetName = "networkStandaloneWindow"
    uiFile = "spokes/network.ui"

    preForHub = SummaryHub
    priority = 10

    def __init__(self, *args, **kwargs):
        StandaloneSpoke.__init__(self, *args, **kwargs)
        self.network_control_box = NetworkControlBox(self.builder)
        parent = self.builder.get_object("AnacondaStandaloneWindow-action_area5")
        parent.add(self.network_control_box.vbox)

    def apply(self):
        pass

    def initialize(self):
        StandaloneSpoke.initialize(self)
        self.network_control_box.initialize()

    def refresh(self):
        StandaloneSpoke.refresh(self)
        self.network_control_box.refresh()

    def on_back_clicked(self, window):
        self.window.hide()
        Gtk.main_quit()


if __name__ == "__main__":

    win = Gtk.Window()
    win.connect("delete-event", Gtk.main_quit)

    builder = Gtk.Builder()
    import os
    ui_file_path = os.environ.get('UIPATH')+'spokes/network.ui'
    builder.add_from_file(ui_file_path)

    n = NetworkControlBox(builder)
    n.initialize()
    n.refresh()

    n.vbox.reparent(win)

    win.show_all()
    Gtk.main()
