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
from blivet.formats import get_format
from blivet.formats.disklabel import DiskLabel
from pykickstart.commands.autopart import RHEL8_AutoPart
from pykickstart.commands.bootloader import RHEL8_Bootloader
from pykickstart.commands.clearpart import F28_ClearPart
from pykickstart.commands.ignoredisk import F29_IgnoreDisk
from pykickstart.commands.logvol import F23_LogVol, F23_LogVolData
from pykickstart.commands.mount import F27_Mount, F27_MountData
from pykickstart.commands.partition import F29_Partition, F29_PartData
from pykickstart.commands.raid import F25_Raid, F25_RaidData
from pykickstart.commands.reqpart import F23_ReqPart
from pykickstart.commands.volgroup import RHEL8_VolGroup, RHEL8_VolGroupData
from pykickstart.commands.zerombr import F9_ZeroMbr
from pykickstart.constants import CLEARPART_TYPE_NONE
from pykickstart.errors import KickstartParseError
from pykickstart.version import RHEL8

from pyanaconda.core.i18n import _
from pyanaconda.core.kickstart import KickstartSpecification
from pyanaconda.storage_utils import device_matches

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


class AutoPart(RHEL8_AutoPart):
    """The autopart kickstart command."""

    def parse(self, args):
        retval = super().parse(args)

        if self.fstype:
            fmt = get_format(self.fstype)

            if not fmt or fmt.type is None:
                raise KickstartParseError(_("File system type \"{}\" given in autopart command is "
                                            "invalid.").format(self.fstype), lineno=self.lineno)
        return retval


class ClearPart(F28_ClearPart):
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


class IgnoreDisk(F29_IgnoreDisk):
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


class StorageKickstartSpecification(KickstartSpecification):
    """Kickstart specification of the storage module."""

    version = RHEL8
    commands = {
        "autopart": AutoPart,
        "bootloader": RHEL8_Bootloader,
        "clearpart": ClearPart,
        "ignoredisk": IgnoreDisk,
        "logvol": F23_LogVol,
        "mount": F27_Mount,
        "part": F29_Partition,
        "partition": F29_Partition,
        "raid": F25_Raid,
        "reqpart": F23_ReqPart,
        "volgroup": RHEL8_VolGroup,
        "zerombr": F9_ZeroMbr,
    }

    commands_data = {
        "LogVolData": F23_LogVolData,
        "MountData": F27_MountData,
        "PartData": F29_PartData,
        "RaidData": F25_RaidData,
        "VolGroupData": RHEL8_VolGroupData,
    }
