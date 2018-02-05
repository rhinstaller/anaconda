#
# NetworkManager libnm client
#
# Copyright (C) 2018 Red Hat, Inc.
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
gi.require_version("NM", "1.0")
from gi.repository import NM

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


nm_client = NM.Client.new(None)

def get_iface_from_connection(uuid):
    """Get the name of device that would be used for the connection.

    In installer it should be just one device.
    We need to account also for the case of configurations bound to mac address
    (HWADDR), eg network --bindto=mac command.
    """
    connection = nm_client.get_connection_by_uuid(uuid)
    if not connection:
        return None
    iface = connection.get_setting_connection().get_interface_name()
    if not iface:
        wired_setting = connection.get_setting_wired()
        if wired_setting:
            mac = wired_setting.get_mac_address()
            if mac:
                iface = get_iface_from_hwaddr(mac)
    return iface

def get_iface_from_hwaddr(hwaddr):
    """Find the name of device specified by mac address."""
    for device in nm_client.get_devices():
        if device.get_device_type() in (NM.DeviceType.ETHERNET,
                                        NM.DeviceType.WIFI):
            try:
                address = device.get_permanent_hw_address()
            except AttributeError as e:
                log.warning("Device %s: %s", device.get_iface(), e)
                address = device.get_hw_address()
        else:
            address = device.get_hw_address()
        if address.upper() == hwaddr.upper():
            return device.get_iface()
    return None

def get_team_port_config_from_connection(uuid):
    connection = nm_client.get_connection_by_uuid(uuid)
    if not connection:
        return None
    team_port = connection.get_setting_team_port()
    if not team_port:
        return None
    config = team_port.get_config()
    return config

def get_team_config_form_connection(uuid):
    connection = nm_client.get_connection_by_uuid(uuid)
    if not connection:
        return None
    team = connection.get_setting_team()
    if not team:
        return None
    config = team.get_config()
    return config
