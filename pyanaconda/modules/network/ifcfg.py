#
# Handling of ifcfg files
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

import os

# TODO move to anaconda.core
from pyanaconda.simpleconfig import SimpleConfigFile

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


IFCFG_DIR = "/etc/sysconfig/network-scripts"

class IfcfgFile(SimpleConfigFile):
    def __init__(self, filename):
        SimpleConfigFile.__init__(self, always_quote=True, filename=filename)
        self._dirty = False

    def read(self, filename=None):
        self.reset()
        log.debug("IfcfFile.read %s", self.filename)
        SimpleConfigFile.read(self)
        self._dirty = False

    def write(self, filename=None, use_tmp=False):
        if self._dirty or filename:
            # ifcfg-rh is using inotify IN_CLOSE_WRITE event so we don't use
            # temporary file for new configuration
            log.debug("IfcfgFile.write %s:\n%s", self.filename, self.__str__())
            SimpleConfigFile.write(self, filename, use_tmp=use_tmp)
            self._dirty = False

    def set(self, *args):
        for (key, data) in args:
            if self.get(key) != data:
                break
        else:
            return
        log.debug("IfcfgFile.set %s: %s", self.filename, args)
        SimpleConfigFile.set(self, *args)
        self._dirty = True

    def unset(self, *args):
        for key in args:
            if self.get(key):
                self._dirty = True
                break
        else:
            return
        log.debug("IfcfgFile.unset %s: %s", self.filename, args)
        SimpleConfigFile.unset(self, *args)

def _ifcfg_files(directory):
    rv = []
    for name in os.listdir(directory):
        if name.startswith("ifcfg-"):
            if name == "ifcfg-lo":
                continue
            rv.append(os.path.join(directory, name))
    return rv

def find_ifcfg_file(values, root_path=""):
    for file_path in _ifcfg_files(os.path.normpath(root_path + IFCFG_DIR)):
        ifcfg = IfcfgFile(file_path)
        ifcfg.read()
        for key, value in values:
            if callable(value):
                if not value(ifcfg.get(key)):
                    break
            else:
                if ifcfg.get(key) != value:
                    break
        else:
            return file_path
    return None

def find_ifcfg_uuid_of_device(device_name, hwaddr=None):
    uuid = None
    ifcfg_path = find_ifcfg_file_of_device(device_name, hwaddr)
    if ifcfg_path:
        ifcfg = IfcfgFile(ifcfg_path)
        ifcfg.read()
        uuid = ifcfg.get('UUID')
    return uuid

# TODO check usage of the original function wrt slaves
def find_ifcfg_file_of_device(device_name, device_hwaddr=None, root_path=""):
    # hwaddr is supplementary (--bindto=mac)
    ifcfg_paths = []
    for file_path in _ifcfg_files(os.path.normpath(root_path + IFCFG_DIR)):
        ifcfg = IfcfgFile(file_path)
        ifcfg.read()
        device_type = ifcfg.get("TYPE") or ifcfg.get("DEVICETYPE")
        if device_type == "Wireless":
            # TODO check ESSID against active ssid of the device
            pass
        elif device_type in ("Bond", "Team", "Bridge", "Infiniband"):
            if ifcfg.get("DEVICE") == device_name:
                ifcfg_paths.append(file_path)
        elif device_type == "Vlan":
            interface_name = ifcfg.get("DEVICE")
            if interface_name:
                if interface_name == device_name:
                    ifcfg_paths.append(file_path)
            else:
                physdev = ifcfg.get("PHYSDEV")
                if len(physdev) == 36:
                    physdev = nm_client.get_iface_from_connection(physdev)
                vlanid = ifcfg.get("VLAN_ID")
                generated_dev_name = default_ks_vlan_interface_name(physdev, vlanid)
                if device_name == generated_dev_name:
                    ifcfg_paths.append(file_path)

        elif device_type == "Ethernet":
            # Ignore slaves
            if ifcfg.get("MASTER") or ifcfg.get("TEAM_MASTER") or ifcfg.get("BRIDGE"):
                continue
            device = ifcfg.get("DEVICE")
            hwaddr = ifcfg.get("HWADDR")
            if device:
                if device == device_name:
                    ifcfg_paths.append(file_path)
            elif hwaddr:
                if device_hwaddr:
                    if device_hwaddr.upper() == hwaddr.upper():
                        ifcfg_paths.append(file_path)
                else:
                    iface = nm_client.get_iface_from_hwaddr(hwaddr)
                    if iface == device_name:
                        ifcfg_paths.append(file_path)
            elif is_s390():
                # s390 setting generated in dracut with net.ifnames=0
                # has neither DEVICE nor HWADDR (#1249750)
                if device.get("NAME") == device_name:
                    ifcfg_paths.append(file_path)

    if len(ifcfg_paths) > 1:
        log.debug("Unexpected number of ifcfg files found for %s: %s", device_name,
                  ifcfg_paths)
    if ifcfg_paths:
        return ifcfg_paths[0]
    else:
        log.debug("Ifcfg file for %s not found", device_name)

# TODO use anaconda.core
def is_s390():
    return os.uname()[4].startswith('s390')

