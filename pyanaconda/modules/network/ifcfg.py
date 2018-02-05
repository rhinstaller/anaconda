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
from pyanaconda.core import util
from pyanaconda.modules.network import nm_client

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


IFCFG_DIR = "/etc/sysconfig/network-scripts"

class IfcfgFile(SimpleConfigFile):
    def __init__(self, filename):
        SimpleConfigFile.__init__(self, always_quote=True, filename=filename)
        self._dirty = False

    def read(self, filename=None):
        self.reset()
        SimpleConfigFile.read(self)
        self._dirty = False

    def write(self, filename=None, use_tmp=False):
        if self._dirty or filename:
            # ifcfg-rh is using inotify IN_CLOSE_WRITE event so we don't use
            # temporary file for new configuration
            SimpleConfigFile.write(self, filename, use_tmp=use_tmp)
            self._dirty = False

    def set(self, *args):
        for (key, data) in args:
            if self.get(key) != data:
                break
        else:
            return
        SimpleConfigFile.set(self, *args)
        self._dirty = True

    def unset(self, *args):
        for key in args:
            if self.get(key):
                self._dirty = True
                break
        else:
            return
        SimpleConfigFile.unset(self, *args)

    def get_kickstart_data(self, network_data_class):

        kwargs = {}

        # no network command for non-virtual device slaves
        if self.get("TYPE") not in ("Bond", "Team"):
            if self.get("MASTER") or self.get("TEAM_MASTER") or self.get("BRIDGE"):
                return None

        # ipv4 and ipv6
        if self.get("ONBOOT") and self.get("ONBOOT") == "no":
            kwargs["onboot"] = False
        if self.get('MTU') and self.get('MTU') != "0":
            kwargs["mtu"] = self.get('MTU')
        # ipv4
        if not self.get('BOOTPROTO'):
            kwargs["noipv4"] = True
        else:
            if util.lowerASCII(self.get('BOOTPROTO')) == 'dhcp':
                kwargs["bootProto"] = "dhcp"
                if self.get('DHCPCLASS'):
                    kwargs["dhcpclass"] = self.get('DHCPCLASS')
            elif self.get('IPADDR'):
                kwargs["bootProto"] = "static"
                kwargs["ip"] = self.get('IPADDR')
                netmask = self.get('NETMASK')
                prefix = self.get('PREFIX')
                if not netmask and prefix:
                    netmask = prefix2netmask(int(prefix))
                if netmask:
                    kwargs["netmask"] = netmask
                # note that --gateway is common for ipv4 and ipv6
                if self.get('GATEWAY'):
                    kwargs["gateway"] = self.get('GATEWAY')
            elif self.get('IPADDR0'):
                kwargs["bootProto"] = "static"
                kwargs["ip"] = self.get('IPADDR0')
                prefix = self.get('PREFIX0')
                if prefix:
                    netmask = prefix2netmask(int(prefix))
                    kwargs["netmask"] = netmask
                # note that --gateway is common for ipv4 and ipv6
                if self.get('GATEWAY0'):
                    kwargs["gateway"] = self.get('GATEWAY0')

        # ipv6
        if (not self.get('IPV6INIT') or self.get('IPV6INIT') == "no"):
            kwargs["noipv6"] = True
        else:
            if self.get('IPV6_AUTOCONF') in ("yes", ""):
                kwargs["ipv6"] = "auto"
            else:
                if self.get('IPV6ADDR'):
                    kwargs["ipv6"] = self.get('IPV6ADDR')
                    if self.get('IPV6_DEFAULTGW') \
                            and self.get('IPV6_DEFAULTGW') != "::":
                        kwargs["ipv6gateway"] = self.get('IPV6_DEFAULTGW')
                if self.get('DHCPV6C') == "yes":
                    kwargs["ipv6"] = "dhcp"

        # ipv4 and ipv6
        dnsline = ''
        for key in self.info.keys():
            if util.upperASCII(key).startswith('DNS'):
                if dnsline == '':
                    dnsline = self.get(key)
                else:
                    dnsline += "," + self.get(key)
        if dnsline:
            kwargs["nameserver"] = dnsline

        if self.get("ETHTOOL_OPTS"):
            kwargs["ethtool"] = self.get("ETHTOOL_OPTS")

        if self.get("ESSID"):
            kwargs["essid"] = self.get("ESSID")

        # hostname
        if self.get("DHCP_HOSTNAME"):
            kwargs["hostname"] = self.get("DHCP_HOSTNAME")

        iface = self.get("DEVICE")
        if not iface:
            hwaddr = self.get("HWADDR")
            if hwaddr:
                iface = nm_client.get_iface_from_hwaddr(hwaddr)
        if iface:
            kwargs["device"] = iface

        # bonding
        # FIXME: dracut has only BOND_OPTS
        if self.get("BONDING_MASTER") == "yes" or self.get("TYPE") == "Bond":
            slaves = get_slaves_from_ifcfgs("MASTER", [self.get("DEVICE"), self.get("UUID")])
            if slaves:
                kwargs["bondslaves"] = ",".join(iface for iface, uuid in slaves)
            bondopts = self.get("BONDING_OPTS")
            if bondopts:
                sep = ","
                if sep in bondopts:
                    sep = ";"
                kwargs["bondopts"] = sep.join(bondopts.split())

        # vlan
        if self.get("VLAN") == "yes" or self.get("TYPE") == "Vlan":
            kwargs["device"] = self.get("PHYSDEV")
            kwargs["vlanid"] = self.get("VLAN_ID")

        # bridging
        if self.get("TYPE") == "Bridge":
            slaves = get_slaves_from_ifcfgs("BRIDGE", [self.get("DEVICE"), self.get("UUID")])
            if slaves:
                kwargs["bridgeslaves"] = ",".join(iface for iface, uuid in slaves)

            bridgeopts = self.get("BRIDGING_OPTS").replace('_', '-').split()
            if self.get("STP"):
                bridgeopts.append("%s=%s" % ("stp", self.get("STP")))
            if self.get("DELAY"):
                bridgeopts.append("%s=%s" % ("forward-delay", self.get("DELAY")))
            if bridgeopts:
                kwargs["bridgeopts"] = ",".join(bridgeopts)

        nd = network_data_class(**kwargs)

        # teaming
        if self.get("TYPE") == "Team" or self.get("DEVICETYPE") == "Team":
            slaves = get_slaves_from_ifcfgs("TEAM_MASTER", [self.get("DEVICE"), self.get("UUID")])
            for iface, uuid in slaves:
                team_port_cfg = nm_client.get_team_port_config_from_connection(uuid)
                nd.teamslaves.append((iface, team_port_cfg))
            teamconfig = nm_client.get_team_config_form_connection(self.get("UUID"))
            if teamconfig:
                nd.teamconfig = teamconfig
        return nd

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

def prefix2netmask(prefix):
    """ Convert prefix (CIDR bits) to netmask """
    _bytes = []
    for _i in range(4):
        if prefix >= 8:
            _bytes.append(255)
            prefix -= 8
        else:
            _bytes.append(256 - 2 ** (8 - prefix))
            prefix = 0
    netmask = ".".join(str(byte) for byte in _bytes)
    return netmask

def get_slaves_from_ifcfgs(master_option, master_specs, root_path=""):
    """List of slaves of master specified by master_specs in master_option.

       master_option is ifcfg option containing spec of master
       master_specs is a list containing device name of master (dracut)
       and/or master's connection uuid
    """
    slaves = []

    for file_path in _ifcfg_files(os.path.normpath(root_path + IFCFG_DIR)):
        ifcfg = IfcfgFile(file_path)
        ifcfg.read()
        master = ifcfg.get(master_option)
        if master in master_specs:
            iface = ifcfg.get("DEVICE")
            if not iface:
                hwaddr = ifcfg.get("HWADDR")
                iface = nm_client.get_iface_from_hwaddr(hwaddr)
            if iface:
                slaves.append((iface, ifcfg.get("UUID")))
    return slaves
