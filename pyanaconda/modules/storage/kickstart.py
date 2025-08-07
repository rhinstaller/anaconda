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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet.fcoe import fcoe
from blivet.formats import get_format
from blivet.formats.disklabel import DiskLabel
from blivet.iscsi import iscsi
from blivet.zfcp import zfcp
from pykickstart.constants import CLEARPART_TYPE_NONE
from pykickstart.errors import KickstartParseError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import FIPS_PASSPHRASE_MIN_LENGTH
from pyanaconda.core.i18n import _
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.kickstart import KickstartSpecification
from pyanaconda.core.kickstart import commands as COMMANDS
from pyanaconda.core.storage import device_matches
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.network import get_supported_devices, wait_for_network_devices

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


def fips_check_luks_passphrase(luks_passphrase, command_name, line_number):
    """Is the LUKS passphrase long enough in FIPS mode?

    Signal a parse error if not.

    This function is meant to be called indiscriminately, it will determine itself if FIPS is on.

    :param str luks_passphrase: LUKS passphrase to check
    :param str command_name: name of the command that had the passphrase
    :param int line_number: line number where the command is found
    :raise KickstartParseError: When the passphrase is not long enough
    """
    if not luks_passphrase:
        return

    if not kernel_arguments.is_enabled("fips"):
        return

    if len(luks_passphrase) >= FIPS_PASSPHRASE_MIN_LENGTH:
        return

    raise KickstartParseError(
        _("Passphrase given in the {} command is too short in FIPS mode. "
          "Please use at least {} characters.").format(command_name, FIPS_PASSPHRASE_MIN_LENGTH),
        lineno=line_number
    )


class AutoPart(COMMANDS.AutoPart):
    """The autopart kickstart command."""

    def parse(self, args):
        retval = super().parse(args)

        if self.fstype:
            fmt = get_format(self.fstype)

            if not fmt or fmt.type is None:
                raise KickstartParseError(_("File system type \"{}\" given in autopart command is "
                                            "invalid.").format(self.fstype), lineno=self.lineno)

        fips_check_luks_passphrase(self.passphrase, "autopart", self.lineno)

        return retval


class BTRFS(COMMANDS.BTRFS):
    """The btrfs kickstart command."""

    def parse(self, args):
        """Parse the command."""
        retval = super().parse(args)

        # Check the file system type.
        fmt = get_format("btrfs")

        if not fmt.supported or not fmt.formattable:
            msg = _("Btrfs file system is not supported.")
            raise KickstartParseError(msg, lineno=self.lineno)

        return retval


class ClearPart(COMMANDS.ClearPart):
    """The clearpart kickstart command."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure attributes are properly initialized for pylint
        # These may be overridden in parse() but need to exist for static analysis
        if not hasattr(self, 'type'):
            self.type = None
        if not hasattr(self, 'drives'):
            self.drives = []
        if not hasattr(self, 'devices'):
            self.devices = []

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure attributes are properly initialized for pylint
        if not hasattr(self, 'ignoredisk'):
            self.ignoredisk = []
        if not hasattr(self, 'onlyuse'):
            self.onlyuse = []

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


class Iscsi(COMMANDS.Iscsi):
    def parse(self, args):
        tg = super().parse(args)

        if tg.iface:
            if not wait_for_network_devices([tg.iface]):
                raise KickstartParseError(
                    lineno=self.lineno,
                    msg=_("Network interface \"{nic}\" required by iSCSI \"{iscsi_target}\" "
                          "target is not up.").format(
                              nic=tg.iface,
                              iscsi_target=tg.target
                          )
                )

        mode = iscsi.mode
        if mode == "none":
            if tg.iface:
                network_proxy = NETWORK.get_proxy()
                activated_ifaces = network_proxy.GetActivatedInterfaces()
                iscsi.create_interfaces(activated_ifaces)
        elif ((mode == "bind" and not tg.iface) or (mode == "default" and tg.iface)):
            raise KickstartParseError(
                lineno=self.lineno,
                msg=_("iscsi --iface must be specified (binding used) either for all targets "
                      "or for none")
            )

        try:
            if tg.target:
                log.info("adding iscsi target %s at %s:%d via %s",
                         tg.target, tg.ipaddr, tg.port, tg.iface)
            else:
                log.info("adding all iscsi targets discovered at %s:%d via %s",
                         tg.ipaddr, tg.port, tg.iface)
            iscsi.add_target(tg.ipaddr, tg.port, tg.user,
                             tg.password, tg.user_in,
                             tg.password_in,
                             target=tg.target,
                             iface=tg.iface)
        except (IOError, ValueError) as e:
            raise KickstartParseError(lineno=self.lineno, msg=str(e)) from e

        return tg


class IscsiName(COMMANDS.IscsiName):
    def parse(self, args):
        retval = super().parse(args)

        iscsi.initiator = self.iscsiname
        return retval


class LogVol(COMMANDS.LogVol):
    def parse(self, args):
        retval = super().parse(args)

        fips_check_luks_passphrase(retval.passphrase, "logvol", self.lineno)

        return retval


class Partition(COMMANDS.Partition):
    def parse(self, args):
        retval = super().parse(args)

        fips_check_luks_passphrase(retval.passphrase, self.currentCmd, self.lineno)

        return retval


class Raid(COMMANDS.Raid):
    def parse(self, args):
        retval = super().parse(args)

        fips_check_luks_passphrase(retval.passphrase, "raid", self.lineno)

        return retval


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

    commands = {
        "autopart": AutoPart,
        "bootloader": COMMANDS.Bootloader,
        "btrfs": BTRFS,
        "clearpart": ClearPart,
        "fcoe": Fcoe,
        "ignoredisk": IgnoreDisk,
        "iscsi": Iscsi,
        "iscsiname": IscsiName,
        "logvol": LogVol,
        "mount": COMMANDS.Mount,
        "nvdimm": COMMANDS.Nvdimm,
        "part": Partition,
        "partition": Partition,
        "raid": Raid,
        "reqpart": COMMANDS.ReqPart,
        "snapshot": Snapshot,
        "volgroup": COMMANDS.VolGroup,
        "zerombr": COMMANDS.ZeroMbr,
        "zfcp": ZFCP,
        "zipl": COMMANDS.Zipl
    }

    commands_data = {
        "BTRFSData": COMMANDS.BTRFSData,
        "FcoeData": COMMANDS.FcoeData,
        "IscsiData": COMMANDS.IscsiData,
        "LogVolData": COMMANDS.LogVolData,
        "MountData": COMMANDS.MountData,
        "NvdimmData": COMMANDS.NvdimmData,
        "PartData": COMMANDS.PartData,
        "RaidData": COMMANDS.RaidData,
        "SnapshotData": COMMANDS.SnapshotData,
        "VolGroupData": COMMANDS.VolGroupData,
        "ZFCPData": COMMANDS.ZFCPData,
    }
