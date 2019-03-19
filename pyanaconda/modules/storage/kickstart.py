#
# Kickstart specification for the storage.
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
from blivet.fcoe import fcoe
from blivet.static_data import nvdimm
from blivet.zfcp import zfcp
from blivet.formats import get_format
from blivet.formats.disklabel import DiskLabel
from pykickstart.constants import CLEARPART_TYPE_NONE, NVDIMM_ACTION_RECONFIGURE, NVDIMM_ACTION_USE
from pykickstart.errors import KickstartParseError

from pyanaconda.network import get_supported_devices
from pyanaconda.core.i18n import _
from pyanaconda.core.kickstart import VERSION, KickstartSpecification, commands as COMMANDS
from pyanaconda.storage.utils import device_matches

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["StorageKickstartSpecification"]


def get_device_names(specs, disks_only=False, msg="{}", lineno=None):
    """Get device names from device specifications."""
    drives = []

    for spec in specs:
        matched = device_matches(spec, disks_only=disks_only)
        if not matched:
            raise KickstartParseError(msg.format(spec), lineno=lineno)
        else:
            drives.extend(matched)

    return drives


class AutoPart(COMMANDS.AutoPart):
    """The autopart kickstart command."""

    def parse(self, args):
        retval = super().parse(args)

        if self.fstype:
            fmt = get_format(self.fstype)

            if not fmt or fmt.type is None:
                raise KickstartParseError(_("File system type \"{}\" given in autopart command is "
                                            "invalid.").format(self.fstype), lineno=self.lineno)
        return retval


class ClearPart(COMMANDS.ClearPart):
    """The ignoredisk kickstart command."""

    def parse(self, args):
        """Parse the command.

        Do any glob expansion now, since we need to have the real
        list of disks available before the execute methods run.
        """
        retval = super().parse(args)

        # Set the default type.
        if self.type is None:
            self.type = CLEARPART_TYPE_NONE

        # Check the disk label.
        if self.disklabel and self.disklabel not in DiskLabel.get_platform_label_types():
            raise KickstartParseError(_("Disklabel \"{}\" given in clearpart command is not "
                                        "supported on this platform.").format(self.disklabel),
                                      lineno=self.lineno)

        # Get the disks names to clear.
        self.drives = get_device_names(self.drives, disks_only=True, lineno=self.lineno,
                                       msg=_("Disk \"{}\" given in clearpart command does "
                                             "not exist."))

        # Get the devices names to clear.
        self.devices = get_device_names(self.devices, disks_only=False, lineno=self.lineno,
                                        msg=_("Device \"{}\" given in clearpart device list "
                                              "does not exist."))

        return retval


class IgnoreDisk(COMMANDS.IgnoreDisk):
    """The ignoredisk kickstart command."""

    def parse(self, args):
        """Parse the command.

        Do any glob expansion now, since we need to have the real
        list of disks available before the execute methods run.
        """
        retval = super().parse(args)

        # Get the ignored disk names.
        self.ignoredisk = get_device_names(self.ignoredisk, disks_only=True, lineno=self.lineno,
                                           msg=_("Disk \"{}\" given in ignoredisk command does "
                                                 "not exist."))

        # Get the selected disk names.
        self.onlyuse = get_device_names(self.onlyuse, disks_only=True, lineno=self.lineno,
                                        msg=_("Disk \"{}\" given in ignoredisk command does "
                                              "not exist."))
        return retval


class Fcoe(COMMANDS.Fcoe):
    def parse(self, args):
        fc = super().parse(args)

        if fc.nic not in [dev.device_name for dev in get_supported_devices()]:
            raise KickstartParseError(_("NIC \"{}\" given in fcoe command does not "
                                        "exist.").format(fc.nic), lineno=self.lineno)

        if fc.nic in (info[0] for info in fcoe.nics):
            log.info("Kickstart fcoe device %s was already added from EDD, ignoring.", fc.nic)
        else:
            msg = fcoe.add_san(nic=fc.nic, dcb=fc.dcb, auto_vlan=True)

            if not msg:
                msg = "Succeeded."
                fcoe.added_nics.append(fc.nic)

            log.info("Adding FCoE SAN on %s: %s", fc.nic, msg)

        return fc


class Nvdimm(COMMANDS.Nvdimm):
    """The nvdimm kickstart command."""

    def parse(self, args):
        action = super().parse(args)

        if action.action == NVDIMM_ACTION_RECONFIGURE:
            if action.namespace not in nvdimm.namespaces:
                raise KickstartParseError(_("Namespace \"{}\" given in nvdimm command was not "
                                            "found.").format(action.namespace), lineno=self.lineno)

            log.info("Reconfiguring the namespace %s to %s mode", action.namespace, action.mode)
            nvdimm.reconfigure_namespace(action.namespace, action.mode, sector_size=action.sectorsize)

        elif action.action == NVDIMM_ACTION_USE:
            if action.namespace and action.namespace not in nvdimm.namespaces:
                raise KickstartParseError(_("Namespace \"{}\" given in nvdimm command was not "
                                            "found.").format(action.namespace), lineno=self.lineno)

            devs = action.blockdevs
            action.blockdevs = get_device_names(devs, disks_only=True, lineno=self.lineno,
                                                msg=_("Disk \"{}\" given in nvdimm command does "
                                                      "not exist."))

        return action


class Snapshot(COMMANDS.Snapshot):
    """The snapshot kickstart command."""

    def parse(self, args):
        request = super().parse(args)

        if not request.origin.count('/') == 1:
            raise KickstartParseError(_("Incorrectly specified origin of the snapshot. Use "
                                        "format \"VolGroup/LV-name\""), lineno=request.lineno)

        return request


class ZFCP(COMMANDS.ZFCP):
    """The zfcp kickstart command."""

    def parse(self, args):
        fcp = super().parse(args)

        # We need to bring the device online before we check
        # device names in other commands. See commit: 4e038ca
        try:
            zfcp.add_fcp(fcp.devnum, fcp.wwpn, fcp.fcplun)
        except ValueError as e:
            log.warning(str(e))

        return fcp


class StorageKickstartSpecification(KickstartSpecification):
    """Kickstart specification of the storage module."""

    version = VERSION

    commands = {
        "autopart": AutoPart,
        "bootloader": COMMANDS.Bootloader,
        "btrfs": COMMANDS.BTRFS,
        "clearpart": ClearPart,
        "fcoe": Fcoe,
        "ignoredisk": IgnoreDisk,
        "logvol": COMMANDS.LogVol,
        "mount": COMMANDS.Mount,
        "nvdimm": Nvdimm,
        "part": COMMANDS.Partition,
        "partition": COMMANDS.Partition,
        "raid": COMMANDS.Raid,
        "reqpart": COMMANDS.ReqPart,
        "snapshot": Snapshot,
        "volgroup": COMMANDS.VolGroup,
        "zerombr": COMMANDS.ZeroMbr,
        "zfcp": ZFCP,
    }

    commands_data = {
        "BTRFSData": COMMANDS.BTRFSData,
        "FcoeData": COMMANDS.FcoeData,
        "LogVolData": COMMANDS.LogVolData,
        "MountData": COMMANDS.MountData,
        "NvdimmData": COMMANDS.NvdimmData,
        "PartData": COMMANDS.PartData,
        "RaidData": COMMANDS.RaidData,
        "SnapshotData": COMMANDS.SnapshotData,
        "VolGroupData": COMMANDS.VolGroupData,
        "ZFCPData": COMMANDS.ZFCPData,
    }
