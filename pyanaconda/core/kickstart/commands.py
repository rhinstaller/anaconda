#
# Supported kickstart commands.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

# Disable unused imports for the whole module.
# pylint:disable=unused-import
# ruff: noqa: F401, I001

# Get command classes dynamically from our OS-release based version detection
from pyanaconda.core.kickstart.version import VERSION
from pykickstart.handlers.control import commandMap, dataMap

# Hardcoded imports for commands that need special handling
from pykickstart.commands.displaymode import F26_DisplayMode as DisplayMode

# Get the command and data maps for the default version
_commands = commandMap[VERSION]
_data = dataMap[VERSION]

# Supported kickstart commands - dynamically imported
Authselect = _commands['authselect']
AutoPart = _commands['autopart']
Bootc = _commands['bootc']
Bootloader = _commands['bootloader']
BTRFS = _commands['btrfs']
Cdrom = _commands['cdrom']
ClearPart = _commands['clearpart']
DriverDisk = _commands['driverdisk']
Module = _commands['module']
Eula = _commands['eula']
Fcoe = _commands['fcoe']
Firewall = _commands['firewall']
Firstboot = _commands['firstboot']
Group = _commands['group']
HardDrive = _commands['harddrive']
Hmc = _commands['hmc']
IgnoreDisk = _commands['ignoredisk']
Iscsi = _commands['iscsi']
IscsiName = _commands['iscsiname']
Keyboard = _commands['keyboard']
Lang = _commands['lang']
Liveimg = _commands['liveimg']
Logging = _commands['logging']
LogVol = _commands['logvol']
MediaCheck = _commands['mediacheck']
Mount = _commands['mount']
Network = _commands['network']
NFS = _commands['nfs']
Nvdimm = _commands['nvdimm']
OSTreeContainer = _commands['ostreecontainer']
OSTreeSetup = _commands['ostreesetup']
Partition = _commands['part']  # 'part' and 'partition' both map to the same class
RDP = _commands['rdp']
Raid = _commands['raid']
Realm = _commands['realm']
Reboot = _commands['reboot']
Repo = _commands['repo']
ReqPart = _commands['reqpart']
Rescue = _commands['rescue']
RootPw = _commands['rootpw']
SELinux = _commands['selinux']
Services = _commands['services']
SkipX = _commands['skipx']
Snapshot = _commands['snapshot']
SshPw = _commands['sshpw']
SshKey = _commands['sshkey']
Timezone = _commands['timezone']
Timesource = _commands['timesource']
Updates = _commands['updates']
Url = _commands['url']
User = _commands['user']
Vnc = _commands['vnc']
VolGroup = _commands['volgroup']
XConfig = _commands['xconfig']
ZeroMbr = _commands['zerombr']
ZFCP = _commands['zfcp']
Zipl = _commands['zipl']

# RHEL-specific commands - import latest available classes regardless of current version
# This ensures they're always available for modules and testing
from pykickstart.commands.rhsm import RHEL8_RHSM as RHSM
from pykickstart.commands.syspurpose import RHEL8_Syspurpose as Syspurpose

# Supported kickstart data - dynamically imported
BTRFSData = _data['BTRFSData']
DriverDiskData = _data['DriverDiskData']
ModuleData = _data['ModuleData']
FcoeData = _data['FcoeData']
GroupData = _data['GroupData']
IscsiData = _data['IscsiData']
LogVolData = _data['LogVolData']
MountData = _data['MountData']
NetworkData = _data['NetworkData']
NvdimmData = _data['NvdimmData']
PartData = _data['PartData']
RaidData = _data['RaidData']
RepoData = _data['RepoData']
SnapshotData = _data['SnapshotData']
SshPwData = _data['SshPwData']
SshKeyData = _data['SshKeyData']
TimesourceData = _data['TimesourceData']
UserData = _data['UserData']
VolGroupData = _data['VolGroupData']
ZFCPData = _data['ZFCPData']
