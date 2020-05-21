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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

# Diable unused imports for the whole module.
# pylint:disable=unused-import

# Supported kickstart commands.
from pykickstart.commands.authconfig import F28_Authconfig as Authconfig
from pykickstart.commands.authselect import F28_Authselect as Authselect
from pykickstart.commands.autopart import RHEL8_AutoPart as AutoPart
from pykickstart.commands.autostep import FC3_AutoStep as AutoStep
from pykickstart.commands.bootloader import RHEL8_Bootloader as Bootloader
from pykickstart.commands.btrfs import RHEL8_BTRFS as BTRFS
from pykickstart.commands.cdrom import FC3_Cdrom as Cdrom
from pykickstart.commands.clearpart import F28_ClearPart as ClearPart
from pykickstart.commands.displaymode import F26_DisplayMode as DisplayMode
from pykickstart.commands.device import F24_Device as Device
from pykickstart.commands.deviceprobe import F29_DeviceProbe as DeviceProbe
from pykickstart.commands.dmraid import F24_DmRaid as DmRaid
from pykickstart.commands.driverdisk import F14_DriverDisk as DriverDisk
from pykickstart.commands.module import RHEL8_Module as Module
from pykickstart.commands.eula import F20_Eula as Eula
from pykickstart.commands.fcoe import RHEL8_Fcoe as Fcoe
from pykickstart.commands.firewall import F28_Firewall as Firewall
from pykickstart.commands.firstboot import FC3_Firstboot as Firstboot
from pykickstart.commands.group import F12_Group as Group
from pykickstart.commands.harddrive import FC3_HardDrive as HardDrive
from pykickstart.commands.hmc import F28_Hmc as Hmc
from pykickstart.commands.ignoredisk import F29_IgnoreDisk as IgnoreDisk
from pykickstart.commands.install import F29_Install as Install
from pykickstart.commands.iscsi import F17_Iscsi as Iscsi
from pykickstart.commands.iscsiname import FC6_IscsiName as IscsiName
from pykickstart.commands.keyboard import F18_Keyboard as Keyboard
from pykickstart.commands.lang import F19_Lang as Lang
from pykickstart.commands.liveimg import F19_Liveimg as Liveimg
from pykickstart.commands.logging import FC6_Logging as Logging
from pykickstart.commands.logvol import RHEL8_LogVol as LogVol
from pykickstart.commands.mediacheck import FC4_MediaCheck as MediaCheck
from pykickstart.commands.method import F28_Method as Method
from pykickstart.commands.mount import F27_Mount as Mount
from pykickstart.commands.multipath import F24_MultiPath as MultiPath
from pykickstart.commands.network import F27_Network as Network
from pykickstart.commands.nfs import FC6_NFS as NFS
from pykickstart.commands.nvdimm import F28_Nvdimm as Nvdimm
from pykickstart.commands.ostreesetup import RHEL8_OSTreeSetup as OSTreeSetup
from pykickstart.commands.partition import RHEL8_Partition as Partition
from pykickstart.commands.raid import RHEL8_Raid as Raid
from pykickstart.commands.realm import F19_Realm as Realm
from pykickstart.commands.reboot import F23_Reboot as Reboot
from pykickstart.commands.repo import RHEL8_Repo as Repo
from pykickstart.commands.reqpart import F23_ReqPart as ReqPart
from pykickstart.commands.rescue import F10_Rescue as Rescue
from pykickstart.commands.rhsm import RHEL8_RHSM as RHSM
from pykickstart.commands.rootpw import F18_RootPw as RootPw
from pykickstart.commands.selinux import FC3_SELinux as SELinux
from pykickstart.commands.services import FC6_Services as Services
from pykickstart.commands.skipx import FC3_SkipX as SkipX
from pykickstart.commands.snapshot import F26_Snapshot as Snapshot
from pykickstart.commands.sshpw import F24_SshPw as SshPw
from pykickstart.commands.sshkey import F22_SshKey as SshKey
from pykickstart.commands.syspurpose import RHEL8_Syspurpose as Syspurpose
from pykickstart.commands.timezone import F32_Timezone as Timezone
from pykickstart.commands.updates import F7_Updates as Updates
from pykickstart.commands.url import RHEL8_Url as Url
from pykickstart.commands.user import F24_User as User
from pykickstart.commands.vnc import F9_Vnc as Vnc
from pykickstart.commands.volgroup import RHEL8_VolGroup as VolGroup
from pykickstart.commands.xconfig import F14_XConfig as XConfig
from pykickstart.commands.zerombr import F9_ZeroMbr as ZeroMbr
from pykickstart.commands.zfcp import F14_ZFCP as ZFCP
from pykickstart.commands.zipl import RHEL8_Zipl as Zipl

# Supported kickstart data.
from pykickstart.commands.btrfs import F23_BTRFSData as BTRFSData
from pykickstart.commands.driverdisk import F14_DriverDiskData as DriverDiskData
from pykickstart.commands.device import F8_DeviceData as DeviceData
from pykickstart.commands.dmraid import FC6_DmRaidData as DmRaidData
from pykickstart.commands.module import RHEL8_ModuleData as ModuleData
from pykickstart.commands.fcoe import RHEL8_FcoeData as FcoeData
from pykickstart.commands.group import F12_GroupData as GroupData
from pykickstart.commands.iscsi import F17_IscsiData as IscsiData
from pykickstart.commands.logvol import RHEL8_LogVolData as LogVolData
from pykickstart.commands.mount import F27_MountData as MountData
from pykickstart.commands.multipath import FC6_MultiPathData as MultiPathData
from pykickstart.commands.network import F27_NetworkData as NetworkData
from pykickstart.commands.nvdimm import F28_NvdimmData as NvdimmData
from pykickstart.commands.partition import RHEL8_PartData as PartData
from pykickstart.commands.raid import RHEL8_RaidData as RaidData
from pykickstart.commands.repo import RHEL8_RepoData as RepoData
from pykickstart.commands.snapshot import F26_SnapshotData as SnapshotData
from pykickstart.commands.sshpw import F24_SshPwData as SshPwData
from pykickstart.commands.sshkey import F22_SshKeyData as SshKeyData
from pykickstart.commands.user import F19_UserData as UserData
from pykickstart.commands.volgroup import RHEL8_VolGroupData as VolGroupData
from pykickstart.commands.zfcp import F14_ZFCPData as ZFCPData
