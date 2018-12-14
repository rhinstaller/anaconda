#
# kickstart.py: kickstart install support
#
# Copyright (C) 1999-2016
# Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import glob
import os
import os.path
from abc import ABCMeta, abstractmethod

import requests
import shlex
import sys
import tempfile
import time
import warnings

import blivet.arch
import blivet.iscsi

from contextlib import contextmanager

from pyanaconda import keyboard, network, nm, ntp, screen_access, timezone
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.kickstart import VERSION, commands as COMMANDS
from pyanaconda.addons import AddonSection, AddonData, AddonRegistry, collect_addon_paths
from pyanaconda.bootloader import GRUB2, get_bootloader
from pyanaconda.core.constants import ADDON_PATHS, IPMI_ABORTED, THREAD_STORAGE, SELINUX_DEFAULT, \
    SETUP_ON_BOOT_DISABLED, SETUP_ON_BOOT_RECONFIG, \
    CLEAR_PARTITIONS_ALL, BOOTLOADER_LOCATION_PARTITION, BOOTLOADER_SKIPPED, BOOTLOADER_ENABLED, \
    BOOTLOADER_TIMEOUT_UNSET, FIREWALL_ENABLED, FIREWALL_DISABLED, FIREWALL_USE_SYSTEM_DEFAULTS, \
    AUTOPART_TYPE_DEFAULT, MOUNT_POINT_DEVICE, MOUNT_POINT_REFORMAT, MOUNT_POINT_FORMAT, \
    MOUNT_POINT_PATH, MOUNT_POINT_FORMAT_OPTIONS, MOUNT_POINT_MOUNT_OPTIONS
from pyanaconda.dbus.structure import apply_structure
from pyanaconda.desktop import Desktop
from pyanaconda.errors import ScriptError, errorHandler
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.kickstart import SplitKickstartError
from pyanaconda.modules.common.constants.services import BOSS, TIMEZONE, LOCALIZATION, SECURITY, \
    USERS, SERVICES, STORAGE, NETWORK
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION, BOOTLOADER, FIREWALL, \
    AUTO_PARTITIONING, MANUAL_PARTITIONING
from pyanaconda.modules.common.structures.realm import RealmData
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.platform import platform
from pyanaconda.pwpolicy import F22_PwPolicy, F22_PwPolicyData
from pyanaconda.simpleconfig import SimpleConfigFile
from pyanaconda.storage import autopart
from pyanaconda.storage_utils import device_matches, try_populate_devicetree, storage_checker, \
    get_pbkdf_args
from pyanaconda.threading import threadMgr
from pyanaconda.timezone import NTP_PACKAGE, NTP_SERVICE

from blivet.deviceaction import ActionCreateFormat, ActionResizeDevice, ActionResizeFormat
from blivet.devicelibs.crypto import MIN_CREATE_ENTROPY
from blivet.devicelibs.lvm import LVM_PE_SIZE, KNOWN_THPOOL_PROFILES
from blivet.devices import LUKSDevice, iScsiDiskDevice
from blivet.devices.lvm import LVMVolumeGroupDevice, LVMCacheRequest, LVMLogicalVolumeDevice
from blivet.static_data import nvdimm, luks_data
from blivet.errors import PartitioningError, StorageError, BTRFSValueError
from blivet.formats.disklabel import DiskLabel
from blivet.formats.fs import XFS
from blivet.formats import get_format
from blivet.partitioning import do_partitioning, grow_lvm
from blivet.size import Size, KiB

from pykickstart.base import BaseHandler, KickstartCommand
from pykickstart.constants import KS_SCRIPT_POST, KS_SCRIPT_PRE, KS_SCRIPT_TRACEBACK, \
    KS_SCRIPT_PREINSTALL, SELINUX_DISABLED, SELINUX_ENFORCING, SELINUX_PERMISSIVE, \
    SNAPSHOT_WHEN_POST_INSTALL, SNAPSHOT_WHEN_PRE_INSTALL, NVDIMM_ACTION_RECONFIGURE, \
    NVDIMM_ACTION_USE
from pykickstart.errors import KickstartError, KickstartParseError
from pykickstart.parser import KickstartParser
from pykickstart.parser import Script as KSScript
from pykickstart.sections import NullSection, PackageSection, PostScriptSection, PreScriptSection, PreInstallScriptSection, \
                                 OnErrorScriptSection, TracebackScriptSection, Section
from pykickstart.version import returnClassForVersion

from pyanaconda import anaconda_logging
from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger, get_blivet_logger,\
    get_anaconda_root_logger

log = get_module_logger(__name__)

stdoutLog = get_stdout_logger()
storage_log = get_blivet_logger()

# kickstart parsing and kickstart script
script_log = log.getChild("script")
parsing_log = log.getChild("parsing")

# command specific loggers
authselect_log = log.getChild("kickstart.authselect")
bootloader_log = log.getChild("kickstart.bootloader")
user_log = log.getChild("kickstart.user")
group_log = log.getChild("kickstart.group")
clearpart_log = log.getChild("kickstart.clearpart")
autopart_log = log.getChild("kickstart.autopart")
logvol_log = log.getChild("kickstart.logvol")
iscsi_log = log.getChild("kickstart.iscsi")
network_log = log.getChild("kickstart.network")
selinux_log = log.getChild("kickstart.selinux")
timezone_log = log.getChild("kickstart.timezone")
realm_log = log.getChild("kickstart.realm")
escrow_log = log.getChild("kickstart.escrow")
firewall_log = log.getChild("kickstart.firewall")

@contextmanager
def check_kickstart_error():
    try:
        yield
    except KickstartError as e:
        # We do not have an interface here yet, so we cannot use our error
        # handling callback.
        print(e)
        util.ipmi_report(IPMI_ABORTED)
        sys.exit(1)

class AnacondaKSScript(KSScript):
    """ Execute a kickstart script

        This will write the script to a file named /tmp/ks-script- before
        execution.
        Output is logged by the program logger, the path specified by --log
        or to /tmp/ks-script-\\*.log
    """
    def run(self, chroot):
        """ Run the kickstart script
            @param chroot directory path to chroot into before execution
        """
        if self.inChroot:
            scriptRoot = chroot
        else:
            scriptRoot = "/"

        (fd, path) = tempfile.mkstemp("", "ks-script-", scriptRoot + "/tmp")

        os.write(fd, self.script.encode("utf-8"))
        os.close(fd)
        os.chmod(path, 0o700)

        # Always log stdout/stderr from scripts.  Using --log just lets you
        # pick where it goes.  The script will also be logged to program.log
        # because of execWithRedirect.
        if self.logfile:
            if self.inChroot:
                messages = "%s/%s" % (scriptRoot, self.logfile)
            else:
                messages = self.logfile

            d = os.path.dirname(messages)
            if not os.path.exists(d):
                os.makedirs(d)
        else:
            # Always log outside the chroot, we copy those logs into the
            # chroot later.
            messages = "/tmp/%s.log" % os.path.basename(path)

        with open(messages, "w") as fp:
            rc = util.execWithRedirect(self.interp, ["/tmp/%s" % os.path.basename(path)],
                                       stdout=fp,
                                       root=scriptRoot)

        if rc != 0:
            script_log.error("Error code %s running the kickstart script at line %s", rc, self.lineno)
            if self.errorOnFail:
                err = ""
                with open(messages, "r") as fp:
                    err = "".join(fp.readlines())

                # Show error dialog even for non-interactive
                flags.ksprompt = True

                errorHandler.cb(ScriptError(self.lineno, err))
                util.ipmi_report(IPMI_ABORTED)
                sys.exit(0)

class AnacondaInternalScript(AnacondaKSScript):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hidden = True

    def __str__(self):
        # Scripts that implement portions of anaconda (copying screenshots and
        # log files, setfilecons, etc.) should not be written to the output
        # kickstart file.
        return ""

def getEscrowCertificate(escrowCerts, url):
    if not url:
        return None

    if url in escrowCerts:
        return escrowCerts[url]

    needs_net = not url.startswith("/") and not url.startswith("file:")
    if needs_net:
        network_proxy = NETWORK.get_proxy()
        if not network_proxy.Connected:
            msg = _("Escrow certificate %s requires the network.") % url
            raise KickstartError(msg)

    escrow_log.info("escrow: downloading %s", url)

    try:
        request = util.requests_session().get(url, verify=True)
    except requests.exceptions.SSLError as e:
        msg = _("SSL error while downloading the escrow certificate:\n\n%s") % e
        raise KickstartError(msg)
    except requests.exceptions.RequestException as e:
        msg = _("The following error was encountered while downloading the escrow certificate:\n\n%s") % e
        raise KickstartError(msg)

    try:
        escrowCerts[url] = request.content
    finally:
        request.close()

    return escrowCerts[url]

def lookupAlias(devicetree, alias):
    for dev in devicetree.devices:
        if getattr(dev, "req_name", None) == alias:
            return dev

    return None

def getAvailableDiskSpace(storage):
    """
    Get overall disk space available on disks we may use.

    :param storage: blivet.Blivet instance
    :return: overall disk space available
    :rtype: :class:`blivet.size.Size`

    """

    free_space = storage.free_space_snapshot
    # blivet creates a new free space dict to instead of modifying the old one,
    # so there is no worry about the dictionary changing during iteration.
    return sum(disk_free for disk_free, fs_free in free_space.values())

def refreshAutoSwapSize(storage):
    """
    Refresh size of the auto partitioning request for swap device according to
    the current state of the storage configuration.

    :param storage: blivet.Blivet instance

    """

    for request in storage.autopart_requests:
        if request.fstype == "swap":
            disk_space = getAvailableDiskSpace(storage)
            request.size = autopart.swap_suggestion(disk_space=disk_space)
            break

###
### SUBCLASSES OF PYKICKSTART COMMAND HANDLERS
###


class RemovedCommand(KickstartCommand, metaclass=ABCMeta):
    """Kickstart command that was moved on DBus.

    This class should simplify the transition to DBus.

    Kickstart command that was moved on DBus should inherit this
    class. Methods parse, setup and execute should be modified to
    access the DBus modules or moved on DBus.
    """

    @abstractmethod
    def __str__(self):
        """Generate this part of a kickstart file from the module.

        This method is required to be overridden, so we don't forget
        to use DBus modules to generate their part of a kickstart file.

        Make sure that each DBus module is used only once.
        """
        return ""

    def parse(self, args):
        """Do not parse anything.

        We can keep this method for the checks if it is possible, but
        it shouldn't parse anything.
        """
        log.warning("Command %s will be parsed in DBus module.", self.currentCmd)


class UselessCommand(RemovedCommand):
    """Kickstart command that was moved on DBus and doesn't do anything.

    Use this class to override the pykickstart command in our command map,
    when we don't want the command to do anything. It is not allowed to
    subclass this class.
    """

    def __init_subclass__(cls, **kwargs):
        raise TypeError("It is not allowed to subclass the UselessCommand class.")

    def __str__(self):
        return ""


class Authselect(RemovedCommand):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packages = []

    def __str__(self):
        # The kickstart for this command is generated
        # by Security module in the SELinux class.
        return ""

    @property
    def fingerprint_supported(self):
        return (os.path.exists(util.getSysroot() + "/lib64/security/pam_fprintd.so") or
                os.path.exists(util.getSysroot() + "/lib/security/pam_fprintd.so"))

    def setup(self):
        security_proxy = SECURITY.get_proxy()

        if security_proxy.Authselect or not flags.automatedInstall:
            self.packages += ["authselect"]

        if security_proxy.Authconfig:
            self.packages += ["authselect-compat"]

    def execute(self, *args):
        security_proxy = SECURITY.get_proxy()

        # Enable fingerprint option by default (#481273).
        if not flags.automatedInstall and self.fingerprint_supported:
            self._run(
                "/usr/bin/authselect",
                ["select", "sssd", "with-fingerprint", "with-silent-lastlog", "--force"],
                required=False
            )

        # Apply the authselect options from the kickstart file.
        if security_proxy.Authselect:
            self._run(
                "/usr/bin/authselect",
                security_proxy.Authselect + ["--force"]
            )

        # Apply the authconfig options from the kickstart file (deprecated).
        if security_proxy.Authconfig:
            self._run(
                "/usr/sbin/authconfig",
                ["--update", "--nostart"] + security_proxy.Authconfig
            )

    def _run(self, cmd, args, required=True):
        if not os.path.lexists(util.getSysroot() + cmd):
            if required:
                msg = _("%s is missing. Cannot setup authentication.") % cmd
                raise KickstartError(msg)
            else:
                return
        try:
            util.execInSysroot(cmd, args)
        except RuntimeError as msg:
            authselect_log.error("Error running %s %s: %s", cmd, args, msg)


class AutoPart(RemovedCommand):

    def __str__(self):
        return ""

    def execute(self, storage, ksdata):
        # Create the auto partitioning proxy.
        auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)

        # Is the auto partitioning enabled?
        if not auto_part_proxy.Enabled:
            return

        # Sets up default auto partitioning. Use clearpart separately if you want it.
        # The filesystem type is already set in the storage.
        refreshAutoSwapSize(storage)
        storage.do_autopart = True

        if auto_part_proxy.Encrypted:
            storage.encrypted_autopart = True
            storage.encryption_passphrase = auto_part_proxy.Passphrase
            storage.encryption_cipher = auto_part_proxy.Cipher
            storage.autopart_escrow_cert = getEscrowCertificate(storage.escrow_certificates,
                                                                auto_part_proxy.Escrowcert)
            storage.autopart_add_backup_passphrase = auto_part_proxy.BackupPassphraseEnabled

            luks_version = auto_part_proxy.LUKSVersion or storage.default_luks_version

            pbkdf_args = get_pbkdf_args(
                luks_version=luks_version,
                pbkdf_type=auto_part_proxy.PBKDF or None,
                max_memory_kb=auto_part_proxy.PBKDFMemory,
                iterations=auto_part_proxy.PBKDFIterations,
                time_ms=auto_part_proxy.PBKDFTime
            )

            if pbkdf_args and not luks_data.pbkdf_args:
                luks_data.pbkdf_args = pbkdf_args

            storage.autopart_luks_version = luks_version
            storage.autopart_pbkdf_args = pbkdf_args

        if auto_part_proxy.Type != AUTOPART_TYPE_DEFAULT:
            storage.autopart_type = auto_part_proxy.Type

        autopart.do_autopart(storage, ksdata, min_luks_entropy=MIN_CREATE_ENTROPY)
        report = storage_checker.check(storage)
        report.log(autopart_log)

        if report.failure:
            raise PartitioningError("autopart failed: \n" + "\n".join(report.all_errors))

class Bootloader(RemovedCommand):
    def __str__(self):
        return ""

    def parse(self, args):
        """Do not parse anything.

        Only validate the bootloader module.
        """
        super().parse(args)

        # Validate the attributes of the bootloader module.
        bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)

        # Skip the check if the bootloader instance is not GRUB2:
        if not isinstance(get_bootloader(), GRUB2):
            return

        # Check the location support.
        if bootloader_proxy.PreferredLocation == BOOTLOADER_LOCATION_PARTITION:
            raise KickstartParseError(_("GRUB2 does not support installation to a partition."),
                                      lineno=self.lineno)

        # Check the password format.
        if bootloader_proxy.IsPasswordSet \
                and bootloader_proxy.IsPasswordEncrypted \
                and not bootloader_proxy.Password.startswith("grub.pbkdf2."):
            raise KickstartParseError(_("GRUB2 encrypted password must be in grub.pbkdf2 format."),
                                      lineno=self.lineno)

    def execute(self, storage, ksdata, dry_run=False):
        """ Resolve and execute the bootloader installation.

            :param storage: object storing storage-related information
                            (disks, partitioning, bootloader, etc.)
            :type storage: blivet.Blivet
            :param payload: object storing payload-related information
            :type payload: pyanaconda.payload.Payload
            :param dry_run: flag if this is only dry run before the partitioning
                            will be resolved
            :type dry_run: bool
        """
        bootloader_log.debug("Execute the bootloader with dry run %s.", dry_run)
        bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)

        # Skip bootloader for s390x image installation.
        if blivet.arch.is_s390() \
                and conf.target.is_image \
                and bootloader_proxy.BootloaderMode == BOOTLOADER_ENABLED:
            bootloader_proxy.SetBootloaderMode(BOOTLOADER_SKIPPED)

        # Is the bootloader enabled?
        if bootloader_proxy.BootloaderMode != BOOTLOADER_ENABLED:
            storage.bootloader.skip_bootloader = True
            bootloader_log.debug("Bootloader is not enabled, skipping.")
            return

        # Apply the settings.
        self._update_flags(storage, bootloader_proxy)
        self._apply_args(storage, bootloader_proxy)
        self._apply_location(storage, bootloader_proxy)
        self._apply_password(storage, bootloader_proxy)
        self._apply_timeout(storage, bootloader_proxy)
        self._apply_drive_order(storage, bootloader_proxy, dry_run=dry_run)
        self._apply_boot_drive(storage, bootloader_proxy, dry_run=dry_run)

    def _update_flags(self, storage, bootloader_proxy):
        """Update flags."""
        if bootloader_proxy.KeepMBR:
            bootloader_log.debug("Don't update the MBR.")
            storage.bootloader.keep_mbr = True

        if bootloader_proxy.KeepBootOrder:
            bootloader_log.debug("Don't change the existing boot order.")
            storage.bootloader.keep_boot_order = True

    def _apply_args(self, storage, bootloader_proxy):
        """Apply the arguments."""
        args = bootloader_proxy.ExtraArguments
        bootloader_log.debug("Applying bootloader arguments: %s", args)
        storage.bootloader.boot_args.update(args)

    def _apply_location(self, storage, bootloader_proxy):
        """Set the location."""
        location = bootloader_proxy.PreferredLocation
        bootloader_log.debug("Applying bootloader location: %s", location)

        storage.bootloader.set_preferred_stage1_type(
            "boot" if location == BOOTLOADER_LOCATION_PARTITION else "mbr"
        )

    def _apply_password(self, storage, bootloader_proxy):
        """Set the password."""
        if bootloader_proxy.IsPasswordSet:
            bootloader_log.debug("Applying bootloader password.")

            if bootloader_proxy.IsPasswordEncrypted:
                storage.bootloader.encrypted_password = bootloader_proxy.Password
            else:
                storage.bootloader.password = bootloader_proxy.Password

    def _apply_timeout(self, storage, bootloader_proxy):
        """Set the timeout."""
        timeout = bootloader_proxy.Timeout
        if timeout != BOOTLOADER_TIMEOUT_UNSET:
            bootloader_log.debug("Applying bootloader timeout: %s", timeout)
            storage.bootloader.timeout = timeout

    def _is_usable_disk(self, d):
        """Is the disk usable for the bootloader?

        Throw out drives that don't exist or cannot be used
        (iSCSI device on an s390 machine).
        """
        return \
            not d.format.hidden and \
            not d.protected and \
            not (blivet.arch.is_s390() and isinstance(d, iScsiDiskDevice))

    def _get_usable_disks(self, storage):
        """Get a list of usable disks."""
        return [d.name for d in storage.disks if self._is_usable_disk(d)]

    def _apply_drive_order(self, storage, bootloader_proxy, dry_run=False):
        """Apply the drive order.

        Drive specifications can contain | delimited variant specifications,
        such as for example: "vd*|hd*|sd*"

        So use the resolved disk identifiers returned by the device_matches()
        function in place of the original specification but still remove the
        specifications that don't match anything from the output kickstart to
        keep existing --driveorder processing behavior.
        """
        drive_order = bootloader_proxy.DriveOrder
        usable_disks = set(self._get_usable_disks(storage))
        valid_disks = []

        for drive in drive_order[:]:
            # Resolve disk identifiers.
            matched_disks = device_matches(drive, devicetree=storage.devicetree, disks_only=True)

            # Are any of the matched disks usable?
            if any(d in usable_disks for d in matched_disks):
                valid_disks.extend(matched_disks)
            else:
                drive_order.remove(drive)
                bootloader_log.warning("Requested drive %s in boot drive order doesn't exist "
                                       "or cannot be used.", drive)

        # Apply the drive order.
        bootloader_log.debug("Applying drive order: %s", valid_disks)
        storage.bootloader.disk_order = valid_disks

        # Update the module.
        if not dry_run and bootloader_proxy.DriveOrder != drive_order:
            bootloader_proxy.SetDriveOrder(drive_order)

    def _check_boot_drive(self, storage, boot_drive, usable_disks):
        """Check the specified boot drive."""
        # Resolve the disk identifier.
        matched_disks = device_matches(boot_drive, devicetree=storage.devicetree, disks_only=True)

        if not matched_disks:
            raise KickstartParseError(_("No match found for given boot drive "
                                        "\"{}\".").format(boot_drive), lineno=self.lineno)

        if len(matched_disks) > 1:
            raise KickstartParseError(_("More than one match found for given boot drive "
                                        "\"{}\".").format(boot_drive), lineno=self.lineno)

        if matched_disks[0] not in usable_disks:
            raise KickstartParseError(_("Requested boot drive \"{}\" doesn't exist or cannot "
                                        "be used.").format(boot_drive), lineno=self.lineno)

    def _find_drive_with_boot(self, storage, usable_disks):
        """Find a drive with the /boot partition."""
        # Find a device for /boot.
        device = storage.mountpoints.get("/boot", None)

        if not device:
            bootloader_log.debug("The /boot partition doesn't exist.")
            return None

        # Use a disk of the device.
        if device.disks:
            drive = device.disks[0].name

            if drive in usable_disks:
                bootloader_log.debug("Found a boot drive: %s", drive)
                return drive

        # No usable disk found.
        bootloader_log.debug("No usable drive with /boot was found.")
        return None

    def _get_boot_drive(self, storage, bootloader_proxy, dry_run=False):
        """Apply the boot drive.

        When bootloader doesn't have --boot-drive parameter then use this logic as fallback:
        1) If present first valid disk from driveorder parameter
        2) If present and usable, use disk where /boot partition is placed
        3) Use first disk from Blivet
        """
        boot_drive = bootloader_proxy.Drive
        drive_order = storage.bootloader.disk_order
        usable_disks_list = self._get_usable_disks(storage)
        usable_disks_set = set(usable_disks_list)

        # Use a disk from --boot-drive.
        if boot_drive:
            bootloader_log.debug("Use the requested boot drive.")
            self._check_boot_drive(storage, boot_drive, usable_disks_set)
            return boot_drive

        # Or use the first disk from --driveorder.
        if drive_order:
            bootloader_log.debug("Use the first usable drive from the drive order.")
            return drive_order[0]

        # Or find a disk with the /boot partition.
        found_drive = self._find_drive_with_boot(storage, usable_disks_set)
        if found_drive:
            bootloader_log.debug("Use a usable drive with a /boot partition.")
            return found_drive

        # Or use the first usable drive.
        bootloader_log.debug("Use the first usable drive.")
        return usable_disks_list[0]

    def _apply_boot_drive(self, storage, bootloader_proxy, dry_run=False):
        """Apply the boot drive.

        When bootloader doesn't have --boot-drive parameter then use this logic as fallback:

        1) If present first valid disk from --driveorder parameter.
        2) If present and usable, use disk where /boot partition is placed.
        3) Use first disk from Blivet.
        """
        boot_drive = self._get_boot_drive(storage, bootloader_proxy)
        bootloader_log.debug("Using a boot drive: %s", boot_drive)

        # Apply the boot drive.
        drive = storage.devicetree.resolve_device(boot_drive)
        storage.bootloader.stage1_disk = drive

        # Update the bootloader module.
        if not dry_run and bootloader_proxy.Drive != boot_drive:
            bootloader_proxy.SetDrive(boot_drive)

class BTRFS(COMMANDS.BTRFS):
    def execute(self, storage, ksdata):
        for b in self.btrfsList:
            b.execute(storage, ksdata)

class BTRFSData(COMMANDS.BTRFSData):
    def execute(self, storage, ksdata):
        devicetree = storage.devicetree

        storage.do_autopart = False

        members = []

        # Get a list of all the devices that make up this volume.
        for member in self.devices:
            dev = devicetree.resolve_device(member)
            if not dev:
                # if using --onpart, use original device
                member_name = ksdata.onPart.get(member, member)
                dev = devicetree.resolve_device(member_name) or lookupAlias(devicetree, member)

            if dev and dev.format.type == "luks":
                try:
                    dev = dev.children[0]
                except IndexError:
                    dev = None

            if dev and dev.format.type != "btrfs":
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Btrfs partition \"%(device)s\" has a format of \"%(format)s\", but should have a format of \"btrfs\".") %
                             {"device": member, "format": dev.format.type})

            if not dev:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Tried to use undefined partition \"%s\" in Btrfs volume specification.") % member)

            members.append(dev)

        if self.subvol:
            name = self.name
        elif self.label:
            name = self.label
        else:
            name = None

        if len(members) == 0 and not self.preexist:
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("Btrfs volume defined without any member devices.  Either specify member devices or use --useexisting."))

        # allow creating btrfs vols/subvols without specifying mountpoint
        if self.mountpoint in ("none", "None"):
            self.mountpoint = ""

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("The mount point \"%s\" is not valid.  It must start with a /.") % self.mountpoint)

        # If a previous device has claimed this mount point, delete the
        # old one.
        try:
            if self.mountpoint:
                device = storage.mountpoints[self.mountpoint]
                storage.destroy_device(device)
        except KeyError:
            pass

        if self.preexist:
            device = devicetree.resolve_device(self.name)
            if not device:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Btrfs volume \"%s\" specified with --useexisting does not exist.") % self.name)

            device.format.mountpoint = self.mountpoint
        else:
            try:
                request = storage.new_btrfs(name=name,
                                            subvol=self.subvol,
                                            mountpoint=self.mountpoint,
                                            metadata_level=self.metaDataLevel,
                                            data_level=self.dataLevel,
                                            parents=members,
                                            create_options=self.mkfsopts)
            except BTRFSValueError as e:
                raise KickstartParseError(lineno=self.lineno, msg=str(e))

            storage.create_device(request)

class Realm(RemovedCommand):
    def __init__(self, *args):
        super().__init__(*args)
        self.packages = []
        self.discovered = ""

    def __str__(self):
        # The kickstart for this command is generated
        # by Security module in the SELinux class.
        return ""

    def setup(self):
        security_proxy = SECURITY.get_proxy()
        realm = apply_structure(security_proxy.Realm, RealmData())

        if not realm.name:
            return

        try:
            argv = ["discover", "--verbose"] + realm.discover_options + [realm.name]
            output = util.execWithCapture("realm", argv, filter_stderr=True)
        except OSError:
            # TODO: A lousy way of propagating what will usually be
            # 'no such realm'
            # The error message is logged by util
            return

        # Now parse the output for the required software. First line is the
        # realm name, and following lines are information as "name: value"
        self.packages = ["realmd"]
        self.discovered = ""

        lines = output.split("\n")
        if not lines:
            return
        self.discovered = lines.pop(0).strip()
        realm_log.info("Realm discovered: %s", self.discovered)
        for line in lines:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip() == "required-package":
                self.packages.append(parts[1].strip())

        realm_log.info("Realm %s needs packages %s",
                       self.discovered, ", ".join(self.packages))

    def execute(self, *args):
        if not self.discovered:
            return

        security_proxy = SECURITY.get_proxy()
        realm = apply_structure(security_proxy.Realm, RealmData())

        for arg in realm.join_options:
            if arg.startswith("--no-password") or arg.startswith("--one-time-password"):
                pw_args = []
                break
        else:
            # no explicit password arg using implicit --no-password
            pw_args = ["--no-password"]

        argv = ["join", "--install", util.getSysroot(), "--verbose"] + pw_args + realm.join_options
        rc = -1
        try:
            rc = util.execWithRedirect("realm", argv)
        except OSError:
            pass

        if rc == 0:
            realm_log.info("Joined realm %s", realm.name)

class ClearPart(RemovedCommand):
    def __str__(self):
        storage_module_proxy = STORAGE.get_proxy()
        return storage_module_proxy.GenerateTemporaryKickstart()

    def execute(self, storage, ksdata):
        disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
        storage.config.clear_part_type = disk_init_proxy.InitializationMode
        storage.config.clear_part_disks = disk_init_proxy.DrivesToClear
        storage.config.clear_part_devices = disk_init_proxy.DevicesToClear
        storage.config.initialize_disks = disk_init_proxy.InitializeLabelsEnabled

        disk_label = disk_init_proxy.DefaultDiskLabel
        if disk_label:
            if not DiskLabel.set_default_label_type(disk_label):
                clearpart_log.warning("%s is not a supported disklabel type on this platform. "
                                      "Using default disklabel %s instead.", disk_label,
                                      DiskLabel.get_platform_label_types()[0])

        storage.clear_partitions()

class Firewall(RemovedCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packages = []

    def __str__(self):
        # The kickstart for this command is generated by the Firewall sub module
        return ""

    def setup(self):
        firewall_proxy = NETWORK.get_proxy(FIREWALL)
        if firewall_proxy.FirewallKickstarted:
            self.packages = ["firewalld"]

    def execute(self, storage, ksdata):
        args = []

        firewall_proxy = NETWORK.get_proxy(FIREWALL)
        # If --use-system-defaults was passed then the user wants
        # whatever was provided by the rpms or ostree to be the
        # default, do nothing.
        if firewall_proxy.FirewallMode == FIREWALL_USE_SYSTEM_DEFAULTS:
            firewall_log.info("ks file instructs to use system defaults for "
                              "firewall, skipping configuration.")
            return

        # enabled is None if neither --enable or --disable is passed
        # default to enabled if nothing has been set.
        if firewall_proxy.FirewallMode == FIREWALL_DISABLED:
            args += ["--disabled"]
        else:
            args += ["--enabled"]

        ssh_service_not_enabled = "ssh" not in firewall_proxy.EnabledServices
        ssh_service_not_disabled = "ssh" not in firewall_proxy.DisabledServices
        ssh_port_not_enabled = "22:tcp" not in firewall_proxy.EnabledPorts

        # always enable SSH unless the service is explicitely disabled
        if ssh_service_not_enabled and ssh_service_not_disabled and ssh_port_not_enabled:
            args += ["--service=ssh"]

        for dev in firewall_proxy.Trusts:
            args += ["--trust=%s" % (dev,)]

        for port in firewall_proxy.EnabledPorts:
            args += ["--port=%s" % (port,)]

        for remove_service in firewall_proxy.DisabledServices:
            args += ["--remove-service=%s" % (remove_service,)]

        for service in firewall_proxy.EnabledServices:
            args += ["--service=%s" % (service,)]

        cmd = "/usr/bin/firewall-offline-cmd"
        if not os.path.exists(util.getSysroot() + cmd):
            if firewall_proxy.FirewallMode == FIREWALL_ENABLED:
                msg = _("%s is missing. Cannot setup firewall.") % (cmd,)
                raise KickstartError(msg)
        else:
            util.execInSysroot(cmd, args)

class Firstboot(RemovedCommand):

    def __str__(self):
        # The kickstart for this command is generated
        # by Services module in the Services class.
        return ""

    def execute(self, *args):
        unit_name = "initial-setup.service"
        services_proxy = SERVICES.get_proxy()
        setup_on_boot = services_proxy.SetupOnBoot

        if setup_on_boot == SETUP_ON_BOOT_DISABLED:
            log.debug("The %s service will be disabled.", unit_name)
            util.disable_service(unit_name)
            # Also tell the screen access manager, so that the fact that post installation tools
            # should be disabled propagates to the user interaction config file.
            screen_access.sam.post_install_tools_disabled = True
            return

        if not os.path.exists(os.path.join(util.getSysroot(), "lib/systemd/system/", unit_name)):
            log.debug("The %s service will not be started on first boot, because "
                      "it's unit file is not installed.", unit_name)
            return

        if setup_on_boot == SETUP_ON_BOOT_RECONFIG:
            log.debug("The %s service will run in the reconfiguration mode.", unit_name)
            # write the reconfig trigger file
            f = open(os.path.join(util.getSysroot(), "etc/reconfigSys"), "w+")
            f.close()

        log.debug("The %s service will be enabled.", unit_name)
        util.enable_service(unit_name)

class Group(COMMANDS.Group):
    def execute(self, storage, ksdata, users):
        for grp in self.groupList:
            kwargs = grp.__dict__
            kwargs.update({"root": util.getSysroot()})
            try:
                users.createGroup(grp.name, **kwargs)
            except ValueError as e:
                group_log.warning(str(e))

class Iscsi(COMMANDS.Iscsi):
    def parse(self, args):
        tg = super().parse(args)

        if tg.iface:
            if not network.wait_for_network_devices([tg.iface]):
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Network interface \"%(nic)s\" required by iSCSI \"%(iscsiTarget)s\" target is not up.") %
                             {"nic": tg.iface, "iscsiTarget": tg.target})

        mode = blivet.iscsi.iscsi.mode
        if mode == "none":
            if tg.iface:
                blivet.iscsi.iscsi.create_interfaces(nm.nm_activated_devices())
        elif ((mode == "bind" and not tg.iface)
              or (mode == "default" and tg.iface)):
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("iscsi --iface must be specified (binding used) either for all targets or for none"))

        try:
            blivet.iscsi.iscsi.add_target(tg.ipaddr, tg.port, tg.user,
                                          tg.password, tg.user_in,
                                          tg.password_in,
                                          target=tg.target,
                                          iface=tg.iface)
            iscsi_log.info("added iscsi target %s at %s via %s", tg.target, tg.ipaddr, tg.iface)
        except (IOError, ValueError) as e:
            raise KickstartParseError(lineno=self.lineno, msg=str(e))

        return tg

class IscsiName(COMMANDS.IscsiName):
    def parse(self, args):
        retval = super().parse(args)

        blivet.iscsi.iscsi.initiator = self.iscsiname
        return retval

class Lang(RemovedCommand):
    def __str__(self):
        localization_proxy = LOCALIZATION.get_proxy()
        return localization_proxy.GenerateKickstart()

    def execute(self, *args, **kwargs):
        localization_proxy = LOCALIZATION.get_proxy()
        task_path = localization_proxy.InstallLanguageWithTask(util.getSysroot())
        task_proxy = LOCALIZATION.get_proxy(task_path)
        sync_run_task(task_proxy)

# no overrides needed here
Eula = COMMANDS.Eula

class LogVol(COMMANDS.LogVol):
    def execute(self, storage, ksdata):
        for l in self.lvList:
            l.execute(storage, ksdata)

        if self.lvList:
            grow_lvm(storage)

class LogVolData(COMMANDS.LogVolData):
    def execute(self, storage, ksdata):
        devicetree = storage.devicetree

        storage.do_autopart = False

        # FIXME: we should be running sanityCheck on partitioning that is not ks
        # autopart, but that's likely too invasive for #873135 at this moment
        if self.mountpoint == "/boot" and blivet.arch.is_s390():
            raise KickstartParseError(lineno=self.lineno, msg="/boot can not be of type 'lvmlv' on s390x")

        # we might have truncated or otherwise changed the specified vg name
        vgname = ksdata.onPart.get(self.vgname, self.vgname)

        size = None

        if self.percent:
            size = Size(0)

        if self.mountpoint == "swap":
            ty = "swap"
            self.mountpoint = ""
            if self.recommended or self.hibernation:
                disk_space = getAvailableDiskSpace(storage)
                size = autopart.swap_suggestion(hibernation=self.hibernation, disk_space=disk_space)
                self.grow = False
        else:
            if self.fstype != "":
                ty = self.fstype
            else:
                ty = storage.default_fstype

        if size is None and not self.preexist:
            if not self.size:
                raise KickstartParseError(lineno=self.lineno,
                    msg="Size can not be decided on from kickstart nor obtained from device.")
            try:
                size = Size("%d MiB" % self.size)
            except ValueError:
                raise KickstartParseError(lineno=self.lineno,
                                          msg="The size \"%s\" is invalid." % self.size)

        if self.thin_pool:
            self.mountpoint = ""
            ty = None

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("The mount point \"%s\" is not valid.  It must start with a /.") % self.mountpoint)

        # Check that the VG this LV is a member of has already been specified.
        vg = devicetree.get_device_by_name(vgname)
        if not vg:
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("No volume group exists with the name \"%s\".  Specify volume groups before logical volumes.") % self.vgname)

        # If cache PVs specified, check that they belong to the same VG this LV is a member of
        if self.cache_pvs:
            pv_devices = (lookupAlias(devicetree, pv) for pv in self.cache_pvs)
            if not all(pv in vg.pvs for pv in pv_devices):
                raise KickstartParseError(lineno=self.lineno,
                    msg=_("Cache PVs must belong to the same VG as the cached LV"))

        pool = None
        if self.thin_volume:
            pool = devicetree.get_device_by_name("%s-%s" % (vg.name, self.pool_name))
            if not pool:
                err = _("No thin pool exists with the name \"%s\". Specify thin pools before thin volumes.") % self.pool_name
                raise KickstartParseError(err, lineno=self.lineno)

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not self.name:
                raise KickstartParseError(lineno=self.lineno,
                                          msg=_("logvol --noformat must also use the --name= option."))

            dev = devicetree.get_device_by_name("%s-%s" % (vg.name, self.name))
            if not dev:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Logical volume \"%s\" given in logvol command does not exist.") % self.name)

            if self.resize:
                size = dev.raw_device.align_target_size(size)
                if size < dev.currentSize:
                    # shrink
                    try:
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                    except ValueError:
                        raise KickstartParseError(lineno=self.lineno,
                                msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                     {"size": self.size, "device": dev.name})
                else:
                    # grow
                    try:
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                    except ValueError:
                        raise KickstartParseError(lineno=self.lineno,
                                msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                     {"size": self.size, "device": dev.name})

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            if ty == "swap":
                storage.add_fstab_swap(dev)
            return

        # Make sure this LV name is not already used in the requested VG.
        if not self.preexist:
            tmp = devicetree.get_device_by_name("%s-%s" % (vg.name, self.name))
            if tmp:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Logical volume name \"%(logvol)s\" is already in use in volume group \"%(volgroup)s\".") %
                             {"logvol": self.name, "volgroup": vg.name})

            if not self.percent and size and not self.grow and size < vg.pe_size:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Logical volume size \"%(logvolSize)s\" must be larger than the volume group extent size of \"%(extentSize)s\".") %
                             {"logvolSize": size, "extentSize": vg.pe_size})

        # Now get a format to hold a lot of these extra values.
        fmt = get_format(ty,
                         mountpoint=self.mountpoint,
                         label=self.label,
                         fsprofile=self.fsprofile,
                         create_options=self.mkfsopts,
                         mountopts=self.fsopts)
        if not fmt.type and not self.thin_pool:
            raise KickstartParseError(lineno=self.lineno,
                                      msg=_("The \"%s\" file system type is not supported.") % ty)

        add_fstab_swap = None
        # If we were given a pre-existing LV to create a filesystem on, we need
        # to verify it and its VG exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing LVs.
        if self.preexist:
            device = devicetree.get_device_by_name("%s-%s" % (vg.name, self.name))
            if not device:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Logical volume \"%s\" given in logvol command does not exist.") % self.name)

            storage.devicetree.recursive_remove(device, remove_device=False)

            if self.resize:
                size = device.raw_device.align_target_size(size)
                try:
                    devicetree.actions.add(ActionResizeDevice(device, size))
                except ValueError:
                    raise KickstartParseError(lineno=self.lineno,
                            msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                 {"size": self.size, "device": device.name})

            devicetree.actions.add(ActionCreateFormat(device, fmt))
            if ty == "swap":
                add_fstab_swap = device
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroy_device(device)
            except KeyError:
                pass

            if self.thin_volume:
                parents = [pool]
            else:
                parents = [vg]

            pool_args = {}
            if self.thin_pool:
                if self.profile:
                    matching = (p for p in KNOWN_THPOOL_PROFILES if p.name == self.profile)
                    profile = next(matching, None)
                    if profile:
                        pool_args["profile"] = profile
                    else:
                        logvol_log.warning("No matching profile for %s found in LVM configuration", self.profile)
                if self.metadata_size:
                    pool_args["metadata_size"] = Size("%d MiB" % self.metadata_size)
                if self.chunk_size:
                    pool_args["chunk_size"] = Size("%d KiB" % self.chunk_size)

            if self.maxSizeMB:
                try:
                    maxsize = Size("%d MiB" % self.maxSizeMB)
                except ValueError:
                    raise KickstartParseError(lineno=self.lineno,
                            msg="The maximum size \"%s\" is invalid." % self.maxSizeMB)
            else:
                maxsize = None

            if self.cache_size and self.cache_pvs:
                pv_devices = [lookupAlias(devicetree, pv) for pv in self.cache_pvs]
                cache_size = Size("%d MiB" % self.cache_size)
                cache_mode = self.cache_mode or None
                cache_request = LVMCacheRequest(cache_size, pv_devices, cache_mode)
            else:
                cache_request = None

            try:
                request = storage.new_lv(fmt=fmt,
                                         name=self.name,
                                         parents=parents,
                                         size=size,
                                         thin_pool=self.thin_pool,
                                         thin_volume=self.thin_volume,
                                         grow=self.grow,
                                         maxsize=maxsize,
                                         percent=self.percent,
                                         cache_request=cache_request,
                                         **pool_args)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(lineno=self.lineno, msg=str(e))

            storage.create_device(request)
            if ty == "swap":
                add_fstab_swap = request

        if self.encrypted:
            if self.passphrase and not storage.encryption_passphrase:
                storage.encryption_passphrase = self.passphrase

            # try to use the global passphrase if available
            # XXX: we require the LV/part with --passphrase to be processed
            # before this one to setup the storage.encryption_passphrase
            self.passphrase = self.passphrase or storage.encryption_passphrase

            cert = getEscrowCertificate(storage.escrow_certificates, self.escrowcert)

            # Get the version of LUKS and PBKDF arguments.
            self.luks_version = self.luks_version or storage.default_luks_version

            pbkdf_args = get_pbkdf_args(
                luks_version=self.luks_version,
                pbkdf_type=self.pbkdf,
                max_memory_kb=self.pbkdf_memory,
                iterations=self.pbkdf_iterations,
                time_ms=self.pbkdf_time
            )

            if pbkdf_args and not luks_data.pbkdf_args:
                luks_data.pbkdf_args = pbkdf_args

            if self.preexist:
                luksformat = fmt
                device.format = get_format("luks", passphrase=self.passphrase, device=device.path,
                                           cipher=self.cipher,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase,
                                           luks_version=self.luks_version,
                                           pbkdf_args=pbkdf_args)
                luksdev = LUKSDevice("luks%d" % storage.next_id,
                                     fmt=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = get_format("luks", passphrase=self.passphrase,
                                            cipher=self.cipher,
                                            escrow_cert=cert,
                                            add_backup_passphrase=self.backuppassphrase,
                                            min_luks_entropy=MIN_CREATE_ENTROPY,
                                            luks_version=self.luks_version,
                                            pbkdf_args=pbkdf_args)
                luksdev = LUKSDevice("luks%d" % storage.next_id,
                                     fmt=luksformat,
                                     parents=request)
            if ty == "swap":
                # swap is on the LUKS device not on the LUKS' parent device,
                # override the info here
                add_fstab_swap = luksdev

            storage.create_device(luksdev)

        if add_fstab_swap:
            storage.add_fstab_swap(add_fstab_swap)

class Logging(COMMANDS.Logging):
    def execute(self, *args):
        if anaconda_logging.logger.loglevel == anaconda_logging.DEFAULT_LEVEL:
            # not set from the command line
            level = anaconda_logging.logLevelMap[self.level]
            anaconda_logging.logger.loglevel = level
            # set log level for the "anaconda" root logger
            anaconda_logging.setHandlersLevel(get_anaconda_root_logger(), level)
            # set log level for the storage logger
            anaconda_logging.setHandlersLevel(storage_log, level)

        if anaconda_logging.logger.remote_syslog is None and len(self.host) > 0:
            # not set from the command line, ok to use kickstart
            remote_server = self.host
            if self.port:
                remote_server = "%s:%s" % (self.host, self.port)
            anaconda_logging.logger.updateRemote(remote_server)


class Mount(RemovedCommand):

    def __str__(self):
        return ""

    def execute(self, storage, *args, **kwargs):
        manual_part_proxy = STORAGE.get_proxy(MANUAL_PARTITIONING)

        if not manual_part_proxy.Enabled:
            return

        # Disable autopart.
        storage.do_autopart = False

        # Set up mount points.
        for data in manual_part_proxy.MountPoints:
            self._setup_mount_point(storage, data)

    def _setup_mount_point(self, storage, data):
        device = data[MOUNT_POINT_DEVICE]
        device_reformat = data[MOUNT_POINT_REFORMAT]
        device_format = data[MOUNT_POINT_FORMAT]

        dev = storage.devicetree.resolve_device(device)
        if dev is None:
            raise KickstartParseError(lineno=self.lineno,
                                      msg=_("Unknown or invalid device '%s' specified") % device)

        if device_reformat:
            if device_format:
                fmt = get_format(device_format)
                if not fmt:
                    msg = _("Unknown or invalid format '%(format)s' specified for device '%(device)s'") % \
                            {"format": device_format, "device": device}
                    raise KickstartParseError(lineno=self.lineno, msg=msg)
            else:
                old_fmt = dev.format
                if not old_fmt or old_fmt.type is None:
                    raise KickstartParseError(lineno=self.lineno,
                                              msg=_("No format on device '%s'") % device)
                fmt = get_format(old_fmt.type)
            storage.format_device(dev, fmt)
            # make sure swaps end up in /etc/fstab
            if fmt.type == "swap":
                storage.add_fstab_swap(dev)

        # only set mount points for mountable formats
        mount_point = data[MOUNT_POINT_PATH]

        if dev.format.mountable and mount_point and mount_point != "none":
            dev.format.mountpoint = mount_point

        dev.format.create_options = data[MOUNT_POINT_FORMAT_OPTIONS]
        dev.format.options = data[MOUNT_POINT_MOUNT_OPTIONS]


class Network(COMMANDS.Network):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packages = []

    def parse(self, args):
        nd = super().parse(args)
        setting_only_hostname = nd.hostname and len(args) <= 2
        if not setting_only_hostname:
            if not nd.device:
                ksdevice = flags.cmdline.get('ksdevice')
                if ksdevice:
                    network_log.info('setting %s from ksdevice for missing kickstart --device', ksdevice)
                    nd.device = ksdevice
                else:
                    network_log.info('setting "link" for missing --device specification in kickstart')
                    nd.device = "link"
        return nd

    def setup(self):
        if network.is_using_team_device():
            self.packages = ["teamd"]

    def execute(self, storage, payload, ksdata):
        fcoe_ifaces = network.devices_used_by_fcoe(storage)
        overwrite = network.can_overwrite_configuration(payload)
        network_proxy = NETWORK.get_proxy()
        task_path = network_proxy.InstallNetworkWithTask(util.getSysroot(),
                                                         fcoe_ifaces,
                                                         overwrite)
        task_proxy = NETWORK.get_proxy(task_path)
        sync_run_task(task_proxy)

        hostname = network_proxy.Hostname
        if hostname != network.DEFAULT_HOSTNAME:
            network.set_hostname(hostname)


class Nvdimm(COMMANDS.Nvdimm):
    def parse(self, args):
        action = super().parse(args)

        if action.action == NVDIMM_ACTION_RECONFIGURE:
            if action.namespace not in nvdimm.namespaces:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("nvdimm: namespace %s not found.") % action.namespace)
            else:
                log.info("nvdimm: reconfiguring %s to %s mode", action.namespace, action.mode)
                nvdimm.reconfigure_namespace(action.namespace, action.mode,
                                             sector_size=action.sectorsize)
        elif action.action == NVDIMM_ACTION_USE:
            if action.namespace and action.namespace not in nvdimm.namespaces:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("nvdimm: namespace %s not found.") % action.namespace)

            if action.blockdevs:
                # See comment in ClearPart.parse
                drives = []
                for spec in action.blockdevs:
                    matched = device_matches(spec, disks_only=True)
                    if matched:
                        drives.extend(matched)
                    else:
                        raise KickstartParseError(lineno=self.lineno,
                                msg=_("Disk \"%s\" given in nvdimm command does not exist.") % spec)

                action.blockdevs = drives

        return action

class Partition(COMMANDS.Partition):
    def execute(self, storage, ksdata):
        for p in self.partitions:
            p.execute(storage, ksdata)

        if self.partitions:
            do_partitioning(storage)

class PartitionData(COMMANDS.PartData):
    def execute(self, storage, ksdata):
        devicetree = storage.devicetree
        kwargs = {}

        storage.do_autopart = False

        if self.onbiosdisk != "":
            # edd_dict is only modified during storage.reset(), so don't do that
            # while executing storage.
            for (disk, biosdisk) in storage.edd_dict.items():
                if "%x" % biosdisk == self.onbiosdisk:
                    self.disk = disk
                    break

            if not self.disk:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("No disk found for specified BIOS disk \"%s\".") % self.onbiosdisk)

        size = None

        if self.mountpoint == "swap":
            ty = "swap"
            self.mountpoint = ""
            if self.recommended or self.hibernation:
                disk_space = getAvailableDiskSpace(storage)
                size = autopart.swap_suggestion(hibernation=self.hibernation, disk_space=disk_space)
                self.grow = False
        # if people want to specify no mountpoint for some reason, let them
        # this is really needed for pSeries boot partitions :(
        elif self.mountpoint == "None":
            self.mountpoint = ""
            if self.fstype:
                ty = self.fstype
            else:
                ty = storage.default_fstype
        elif self.mountpoint == 'appleboot':
            ty = "appleboot"
            self.mountpoint = ""
        elif self.mountpoint == 'prepboot':
            ty = "prepboot"
            self.mountpoint = ""
        elif self.mountpoint == 'biosboot':
            ty = "biosboot"
            self.mountpoint = ""
        elif self.mountpoint.startswith("raid."):
            ty = "mdmember"
            kwargs["name"] = self.mountpoint
            self.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("RAID partition \"%s\" is defined multiple times.") % kwargs["name"])

            if self.onPart:
                ksdata.onPart[kwargs["name"]] = self.onPart
        elif self.mountpoint.startswith("pv."):
            ty = "lvmpv"
            kwargs["name"] = self.mountpoint
            self.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("PV partition \"%s\" is defined multiple times.") % kwargs["name"])

            if self.onPart:
                ksdata.onPart[kwargs["name"]] = self.onPart
        elif self.mountpoint.startswith("btrfs."):
            ty = "btrfs"
            kwargs["name"] = self.mountpoint
            self.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Btrfs partition \"%s\" is defined multiple times.") % kwargs["name"])

            if self.onPart:
                ksdata.onPart[kwargs["name"]] = self.onPart
        elif self.mountpoint == "/boot/efi":
            if blivet.arch.is_mactel():
                ty = "macefi"
            else:
                ty = "EFI System Partition"
                self.fsopts = "defaults,uid=0,gid=0,umask=077,shortname=winnt"
        else:
            if self.fstype != "":
                ty = self.fstype
            elif self.mountpoint == "/boot":
                ty = storage.default_boot_fstype
            else:
                ty = storage.default_fstype

        if not size and self.size:
            try:
                size = Size("%d MiB" % self.size)
            except ValueError:
                raise KickstartParseError(lineno=self.lineno,
                                          msg=_("The size \"%s\" is invalid.") % self.size)

        # If this specified an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not self.onPart:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("part --noformat must also use the --onpart option."))

            dev = devicetree.resolve_device(self.onPart)
            if not dev:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Partition \"%s\" given in part command does not exist.") % self.onPart)

            if self.resize:
                size = dev.raw_device.align_target_size(size)
                if size < dev.currentSize:
                    # shrink
                    try:
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                    except ValueError:
                        raise KickstartParseError(lineno=self.lineno,
                                msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                     {"size": self.size, "device": dev.name})
                else:
                    # grow
                    try:
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                    except ValueError:
                        raise KickstartParseError(lineno=self.lineno,
                                msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                     {"size": self.size, "device": dev.name})

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            if ty == "swap":
                storage.add_fstab_swap(dev)
            return

        # Now get a format to hold a lot of these extra values.
        kwargs["fmt"] = get_format(ty,
                                   mountpoint=self.mountpoint,
                                   label=self.label,
                                   fsprofile=self.fsprofile,
                                   mountopts=self.fsopts,
                                   create_options=self.mkfsopts,
                                   size=size)
        if not kwargs["fmt"].type:
            raise KickstartParseError(lineno=self.lineno,
                                      msg=_("The \"%s\" file system type is not supported.") % ty)

        # If we were given a specific disk to create the partition on, verify
        # that it exists first.  If it doesn't exist, see if it exists with
        # mapper/ on the front.  If that doesn't exist either, it's an error.
        if self.disk:
            disk = devicetree.resolve_device(self.disk)
            # if this is a multipath member promote it to the real mpath
            if disk and disk.format.type == "multipath_member":
                mpath_device = disk.children[0]
                storage_log.info("kickstart: part: promoting %s to %s",
                                 disk.name, mpath_device.name)
                disk = mpath_device
            if not disk:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Disk \"%s\" given in part command does not exist.") % self.disk)
            if not disk.partitionable:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Cannot install to unpartitionable device \"%s\".") % self.disk)

            should_clear = storage.should_clear(disk)
            if disk and (disk.partitioned or should_clear):
                kwargs["parents"] = [disk]
            elif disk:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Disk \"%s\" in part command is not partitioned.") % self.disk)

            if not kwargs["parents"]:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Disk \"%s\" given in part command does not exist.") % self.disk)

        kwargs["grow"] = self.grow
        kwargs["size"] = size
        if self.maxSizeMB:
            try:
                maxsize = Size("%d MiB" % self.maxSizeMB)
            except ValueError:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("The maximum size \"%s\" is invalid.") % self.maxSizeMB)
        else:
            maxsize = None

        kwargs["maxsize"] = maxsize

        kwargs["primary"] = self.primOnly

        add_fstab_swap = None
        # If we were given a pre-existing partition to create a filesystem on,
        # we need to verify it exists and then schedule a new format action to
        # take place there.  Also, we only support a subset of all the options
        # on pre-existing partitions.
        if self.onPart:
            device = devicetree.resolve_device(self.onPart)
            if not device:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Partition \"%s\" given in part command does not exist.") % self.onPart)

            storage.devicetree.recursive_remove(device, remove_device=False)
            if self.resize:
                size = device.raw_device.align_target_size(size)
                try:
                    devicetree.actions.add(ActionResizeDevice(device, size))
                except ValueError:
                    raise KickstartParseError(lineno=self.lineno,
                            msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                 {"size": self.size, "device": device.name})

            devicetree.actions.add(ActionCreateFormat(device, kwargs["fmt"]))
            if ty == "swap":
                add_fstab_swap = device
        # tmpfs mounts are not disks and don't occupy a disk partition,
        # so handle them here
        elif self.fstype == "tmpfs":
            try:
                request = storage.new_tmp_fs(**kwargs)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(lineno=self.lineno, msg=str(e))
            storage.create_device(request)
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroy_device(device)
            except KeyError:
                pass

            try:
                request = storage.new_partition(**kwargs)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(lineno=self.lineno, msg=str(e))

            storage.create_device(request)
            if ty == "swap":
                add_fstab_swap = request

        if self.encrypted:
            if self.passphrase and not storage.encryption_passphrase:
                storage.encryption_passphrase = self.passphrase

            # try to use the global passphrase if available
            # XXX: we require the LV/part with --passphrase to be processed
            # before this one to setup the storage.encryption_passphrase
            self.passphrase = self.passphrase or storage.encryption_passphrase

            cert = getEscrowCertificate(storage.escrow_certificates, self.escrowcert)

            # Get the version of LUKS and PBKDF arguments.
            self.luks_version = self.luks_version or storage.default_luks_version

            pbkdf_args = get_pbkdf_args(
                luks_version=self.luks_version,
                pbkdf_type=self.pbkdf,
                max_memory_kb=self.pbkdf_memory,
                iterations=self.pbkdf_iterations,
                time_ms=self.pbkdf_time
            )

            if pbkdf_args and not luks_data.pbkdf_args:
                luks_data.pbkdf_args = pbkdf_args

            if self.onPart:
                luksformat = kwargs["fmt"]
                device.format = get_format("luks", passphrase=self.passphrase, device=device.path,
                                           cipher=self.cipher,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase,
                                           min_luks_entropy=MIN_CREATE_ENTROPY,
                                           luks_version=self.luks_version,
                                           pbkdf_args=pbkdf_args)
                luksdev = LUKSDevice("luks%d" % storage.next_id,
                                     fmt=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = get_format("luks", passphrase=self.passphrase,
                                            cipher=self.cipher,
                                            escrow_cert=cert,
                                            add_backup_passphrase=self.backuppassphrase,
                                            min_luks_entropy=MIN_CREATE_ENTROPY,
                                            luks_version=self.luks_version,
                                            pbkdf_args=pbkdf_args)
                luksdev = LUKSDevice("luks%d" % storage.next_id,
                                     fmt=luksformat,
                                     parents=request)

            if ty == "swap":
                # swap is on the LUKS device not on the LUKS' parent device,
                # override the info here
                add_fstab_swap = luksdev

            storage.create_device(luksdev)

        if add_fstab_swap:
            storage.add_fstab_swap(add_fstab_swap)

class Raid(COMMANDS.Raid):
    def execute(self, storage, ksdata):
        for r in self.raidList:
            r.execute(storage, ksdata)

class RaidData(COMMANDS.RaidData):
    def execute(self, storage, ksdata):
        raidmems = []
        devicetree = storage.devicetree
        devicename = self.device
        if self.preexist:
            device = devicetree.resolve_device(devicename)
            if device:
                devicename = device.name

        kwargs = {}

        storage.do_autopart = False

        if self.mountpoint == "swap":
            ty = "swap"
            self.mountpoint = ""
        elif self.mountpoint.startswith("pv."):
            ty = "lvmpv"
            kwargs["name"] = self.mountpoint
            ksdata.onPart[kwargs["name"]] = devicename

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("PV partition \"%s\" is defined multiple times.") % kwargs["name"])

            self.mountpoint = ""
        elif self.mountpoint.startswith("btrfs."):
            ty = "btrfs"
            kwargs["name"] = self.mountpoint
            ksdata.onPart[kwargs["name"]] = devicename

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Btrfs partition \"%s\" is defined multiple times.") % kwargs["name"])

            self.mountpoint = ""
        else:
            if self.fstype != "":
                ty = self.fstype
            elif self.mountpoint == "/boot" and "mdarray" in storage.bootloader.stage2_device_types:
                ty = storage.default_boot_fstype
            else:
                ty = storage.default_fstype

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("The mount point \"%s\" is not valid.  It must start with a /.") % self.mountpoint)

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not devicename:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("raid --noformat must also use the --device option."))

            dev = devicetree.get_device_by_name(devicename)
            if not dev:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("RAID device  \"%s\" given in raid command does not exist.") % devicename)

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            if ty == "swap":
                storage.add_fstab_swap(dev)
            return

        # Get a list of all the RAID members.
        for member in self.members:
            dev = devicetree.resolve_device(member)
            if not dev:
                # if member is using --onpart, use original device
                mem = ksdata.onPart.get(member, member)
                dev = devicetree.resolve_device(mem) or lookupAlias(devicetree, member)
            if dev and dev.format.type == "luks":
                try:
                    dev = dev.children[0]
                except IndexError:
                    dev = None

            if dev and dev.format.type != "mdmember":
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("RAID device \"%(device)s\" has a format of \"%(format)s\", but should have a format of \"mdmember\".") %
                             {"device": member, "format": dev.format.type})

            if not dev:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Tried to use undefined partition \"%s\" in RAID specification.") % member)

            raidmems.append(dev)

        # Now get a format to hold a lot of these extra values.
        kwargs["fmt"] = get_format(ty,
                                   label=self.label,
                                   fsprofile=self.fsprofile,
                                   mountpoint=self.mountpoint,
                                   mountopts=self.fsopts,
                                   create_options=self.mkfsopts)
        if not kwargs["fmt"].type:
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("The \"%s\" file system type is not supported.") % ty)

        kwargs["name"] = devicename
        kwargs["level"] = self.level
        kwargs["parents"] = raidmems
        kwargs["member_devices"] = len(raidmems) - self.spares
        kwargs["total_devices"] = len(raidmems)

        if self.chunk_size:
            kwargs["chunk_size"] = Size("%d KiB" % self.chunk_size)

        add_fstab_swap = None

        # If we were given a pre-existing RAID to create a filesystem on,
        # we need to verify it exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing RAIDs.
        if self.preexist:
            device = devicetree.get_device_by_name(devicename)
            if not device:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("RAID volume \"%s\" specified with --useexisting does not exist.") % devicename)

            storage.devicetree.recursive_remove(device, remove_device=False)
            devicetree.actions.add(ActionCreateFormat(device, kwargs["fmt"]))
            if ty == "swap":
                add_fstab_swap = device
        else:
            if devicename and devicename in (a.name for a in storage.mdarrays):
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("The RAID volume name \"%s\" is already in use.") % devicename)

            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroy_device(device)
            except KeyError:
                pass

            try:
                request = storage.new_mdarray(**kwargs)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(lineno=self.lineno, msg=str(e))

            storage.create_device(request)
            if ty == "swap":
                add_fstab_swap = request

        if self.encrypted:
            if self.passphrase and not storage.encryption_passphrase:
                storage.encryption_passphrase = self.passphrase

            cert = getEscrowCertificate(storage.escrow_certificates, self.escrowcert)

            # Get the version of LUKS and PBKDF arguments.
            self.luks_version = self.luks_version or storage.default_luks_version

            pbkdf_args = get_pbkdf_args(
                luks_version=self.luks_version,
                pbkdf_type=self.pbkdf,
                max_memory_kb=self.pbkdf_memory,
                iterations=self.pbkdf_iterations,
                time_ms=self.pbkdf_time
            )

            if pbkdf_args and not luks_data.pbkdf_args:
                luks_data.pbkdf_args = pbkdf_args

            if self.preexist:
                luksformat = kwargs["fmt"]
                device.format = get_format("luks", passphrase=self.passphrase, device=device.path,
                                           cipher=self.cipher,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase,
                                           luks_version=self.luks_version,
                                           pbkdf_args=pbkdf_args)
                luksdev = LUKSDevice("luks%d" % storage.next_id,
                                     fmt=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = get_format("luks", passphrase=self.passphrase,
                                            cipher=self.cipher,
                                            escrow_cert=cert,
                                            add_backup_passphrase=self.backuppassphrase,
                                            luks_version=self.luks_version,
                                            pbkdf_args=pbkdf_args)
                luksdev = LUKSDevice("luks%d" % storage.next_id,
                                     fmt=luksformat,
                                     parents=request)

            if ty == "swap":
                # swap is on the LUKS device instead of the parent device,
                # override the device here
                add_fstab_swap = luksdev

            storage.create_device(luksdev)

        if add_fstab_swap:
            storage.add_fstab_swap(add_fstab_swap)

class RepoData(COMMANDS.RepoData):

    __mount_counter = 0

    def __init__(self, *args, **kwargs):
        """ Add enabled kwarg

            :param enabled: The repo has been enabled
            :type enabled: bool
        """
        self.enabled = kwargs.pop("enabled", True)
        self.repo_id = kwargs.pop("repo_id", None)
        self.treeinfo_origin = kwargs.pop("treeinfo_origin", False)
        self.partition = kwargs.pop("partition", None)
        self.iso_path = kwargs.pop("iso_path", None)

        self.mount_dir_suffix = kwargs.pop("mount_dir_suffix", None)

        super().__init__(*args, **kwargs)

    @classmethod
    def create_copy(cls, other):
        return cls(name=other.name,
                   baseurl=other.baseurl,
                   mirrorlist=other.mirrorlist,
                   metalink=other.metalink,
                   proxy=other.proxy,
                   enabled=other.enabled,
                   treeinfo_origin=other.treeinfo_origin,
                   partition=other.partition,
                   iso_path=other.iso_path,
                   mount_dir_suffix=other.mount_dir_suffix)

    def generate_mount_dir(self):
        """Generate persistent mount directory suffix

        This is valid only for HD repositories
        """
        if self.is_harddrive_based() and self.mount_dir_suffix is None:
            self.mount_dir_suffix = "addition_" + self._generate_mount_dir_suffix()

    @classmethod
    def _generate_mount_dir_suffix(cls):
        suffix = str(cls.__mount_counter)
        cls.__mount_counter += 1
        return suffix

    def __str__(self):
        """Don't output disabled repos"""
        if self.enabled:
            return super().__str__()
        else:
            return ''

    def is_harddrive_based(self):
        return self.partition is not None

class ReqPart(COMMANDS.ReqPart):
    def execute(self, storage, ksdata):
        if not self.reqpart:
            return

        log.debug("Looking for platform-specific bootloader requirements.")
        reqs = platform.set_platform_bootloader_reqs()

        if self.addBoot:
            log.debug("Looking for platform-specific boot requirements.")
            bootPartitions = platform.set_platform_boot_partition()

            # Blivet doesn't know this - anaconda sets up the default boot fstype
            # in various places in this file. We need to duplicate that here.
            for part in bootPartitions:
                if part.mountpoint == "/boot":
                    part.fstype = storage.default_boot_fstype

            reqs += bootPartitions

        if reqs:
            log.debug("Applying requirements:\n%s", "".join(map(str, reqs)))
            autopart.do_reqpart(storage, reqs)

class RootPw(RemovedCommand):

    def __str__(self):
        users_proxy = USERS.get_proxy()
        return users_proxy.GenerateTemporaryKickstart()

    def execute(self, storage, ksdata, users):

        users_proxy = USERS.get_proxy()

        if flags.automatedInstall and not users_proxy.IsRootPasswordSet and not users_proxy.IsRootpwKickstarted:
            # Lock the root password if during an installation with kickstart
            # the root password is empty & not specififed as empty in the kickstart
            # (seen == False) via the rootpw command.
            # Note that kickstart is actually the only way to specify an empty
            # root password - we don't allow that via the UI.
            users_proxy.SetRootAccountLocked(True)
        elif not flags.automatedInstall and not users_proxy.IsRootPasswordSet:
            # Also lock the root password if it was not set during interactive installation.
            users_proxy.SetRootAccountLocked(True)

        users.setRootPassword(users_proxy.RootPassword,
                              users_proxy.IsRootPasswordCrypted,
                              users_proxy.IsRootAccountLocked,
                              None,
                              util.getSysroot())

class SELinux(RemovedCommand):

    SELINUX_STATES = {
        SELINUX_DISABLED: "disabled",
        SELINUX_ENFORCING: "enforcing",
        SELINUX_PERMISSIVE: "permissive"
    }

    def __str__(self):
        security_proxy = SECURITY.get_proxy()
        return security_proxy.GenerateKickstart()

    def execute(self, *args):
        security_proxy = SECURITY.get_proxy()
        selinux = security_proxy.SELinux

        if selinux == SELINUX_DEFAULT:
            selinux_log.debug("Use SELinux default configuration.")
            return

        if selinux not in self.SELINUX_STATES:
            selinux_log.error("Unknown SELinux state for %s.", selinux)
            return

        try:
            selinux_cfg = SimpleConfigFile(util.getSysroot() + "/etc/selinux/config")
            selinux_cfg.read()
            selinux_cfg.set(("SELINUX", self.SELINUX_STATES[selinux]))
            selinux_cfg.write()
        except IOError as msg:
            selinux_log.error("SELinux configuration failed: %s", msg)

class Services(RemovedCommand):

    def __str__(self):
        services_proxy = SERVICES.get_proxy()
        return services_proxy.GenerateKickstart()

    def execute(self, storage, ksdata):
        services_proxy = SERVICES.get_proxy()

        for svc in services_proxy.DisabledServices:
            log.debug("Disabling the service %s.", svc)
            util.disable_service(svc)

        for svc in services_proxy.EnabledServices:
            log.debug("Enabling the service %s.", svc)
            util.enable_service(svc)

class SshKey(COMMANDS.SshKey):
    def execute(self, storage, ksdata, users):
        for usr in self.sshUserList:
            users.setUserSshKey(usr.username, usr.key)

class Timezone(RemovedCommand):

    def __init__(self, *args):
        super().__init__(*args)
        self.packages = []

    def __str__(self):
        timezone_proxy = TIMEZONE.get_proxy()
        return timezone_proxy.GenerateKickstart()

    def setup(self, ksdata):
        timezone_proxy = TIMEZONE.get_proxy()
        services_proxy = SERVICES.get_proxy()

        enabled_services = services_proxy.EnabledServices
        disabled_services = services_proxy.DisabledServices

        # do not install and use NTP package
        if not timezone_proxy.NTPEnabled or NTP_PACKAGE in ksdata.packages.excludedList:
            if util.service_running(NTP_SERVICE) and conf.system.can_set_time_synchronization:
                ret = util.stop_service(NTP_SERVICE)
                if ret != 0:
                    timezone_log.error("Failed to stop NTP service")

            if NTP_SERVICE not in disabled_services:
                disabled_services.append(NTP_SERVICE)
                services_proxy.SetDisabledServices(disabled_services)
        # install and use NTP package
        else:
            if not util.service_running(NTP_SERVICE) and conf.system.can_set_time_synchronization:
                ret = util.start_service(NTP_SERVICE)
                if ret != 0:
                    timezone_log.error("Failed to start NTP service")

            self.packages.append(NTP_PACKAGE)

            if not NTP_SERVICE in enabled_services and \
                    not NTP_SERVICE in disabled_services:
                enabled_services.append(NTP_SERVICE)
                services_proxy.SetEnabledServices(enabled_services)

    def execute(self, *args):
        # get the DBus proxies
        timezone_proxy = TIMEZONE.get_proxy()

        # write out timezone configuration
        kickstart_timezone = timezone_proxy.Timezone

        if not timezone.is_valid_timezone(kickstart_timezone):
            # this should never happen, but for pity's sake
            timezone_log.warning("Timezone %s set in kickstart is not valid, falling "
                                 "back to default (America/New_York).", kickstart_timezone)
            timezone_proxy.SetTimezone("America/New_York")

        timezone.write_timezone_config(timezone_proxy, util.getSysroot())

        # write out NTP configuration (if set) and --nontp is not used
        kickstart_ntp_servers = timezone_proxy.NTPServers

        if timezone_proxy.NTPEnabled and kickstart_ntp_servers:
            chronyd_conf_path = os.path.normpath(util.getSysroot() + ntp.NTP_CONFIG_FILE)
            pools, servers = ntp.internal_to_pools_and_servers(kickstart_ntp_servers)
            if os.path.exists(chronyd_conf_path):
                timezone_log.debug("Modifying installed chrony configuration")
                try:
                    ntp.save_servers_to_config(pools, servers, conf_file_path=chronyd_conf_path)
                except ntp.NTPconfigError as ntperr:
                    timezone_log.warning("Failed to save NTP configuration: %s", ntperr)
            # use chrony conf file from installation environment when
            # chrony is not installed (chrony conf file is missing)
            else:
                timezone_log.debug("Creating chrony configuration based on the "
                                   "configuration from installation environment")
                try:
                    ntp.save_servers_to_config(pools, servers,
                                               conf_file_path=ntp.NTP_CONFIG_FILE,
                                               out_file_path=chronyd_conf_path)
                except ntp.NTPconfigError as ntperr:
                    timezone_log.warning("Failed to save NTP configuration without chrony package: %s", ntperr)

class User(COMMANDS.User):
    def execute(self, storage, ksdata, users):

        for usr in self.userList:
            kwargs = usr.__dict__
            kwargs.update({"root": util.getSysroot()})

            # If the user password came from a kickstart and it is blank we
            # need to make sure the account is locked, not created with an
            # empty password.
            if ksdata.user.seen and kwargs.get("password", "") == "":
                kwargs["password"] = None
            try:
                users.createUser(usr.name, **kwargs)
            except ValueError as e:
                user_log.warning(str(e))

class VolGroup(COMMANDS.VolGroup):
    def execute(self, storage, ksdata):
        for v in self.vgList:
            v.execute(storage, ksdata)

class VolGroupData(COMMANDS.VolGroupData):
    def execute(self, storage, ksdata):
        pvs = []

        devicetree = storage.devicetree

        storage.do_autopart = False

        # Get a list of all the physical volume devices that make up this VG.
        for pv in self.physvols:
            dev = devicetree.resolve_device(pv)
            if not dev:
                # if pv is using --onpart, use original device
                pv_name = ksdata.onPart.get(pv, pv)
                dev = devicetree.resolve_device(pv_name) or lookupAlias(devicetree, pv)
            if dev and dev.format.type == "luks":
                try:
                    dev = dev.children[0]
                except IndexError:
                    dev = None

            if dev and dev.format.type != "lvmpv":
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Physical volume \"%(device)s\" has a format of \"%(format)s\", but should have a format of \"lvmpv\".") %
                             {"device": pv, "format": dev.format.type})

            if not dev:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Tried to use undefined partition \"%s\" in Volume Group specification") % pv)

            pvs.append(dev)

        if len(pvs) == 0 and not self.preexist:
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("Volume group \"%s\" defined without any physical volumes.  Either specify physical volumes or use --useexisting.") % self.vgname)

        if self.pesize == 0:
            # default PE size requested -- we use blivet's default in KiB
            self.pesize = LVM_PE_SIZE.convert_to(KiB)

        pesize = Size("%d KiB" % self.pesize)
        possible_extents = LVMVolumeGroupDevice.get_supported_pe_sizes()
        if pesize not in possible_extents:
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("Volume group given physical extent size of \"%(extentSize)s\", but must be one of:\n%(validExtentSizes)s.") %
                         {"extentSize": pesize, "validExtentSizes": ", ".join(str(e) for e in possible_extents)})

        # If --noformat or --useexisting was given, there's really nothing to do.
        if not self.format or self.preexist:
            if not self.vgname:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("volgroup --noformat and volgroup --useexisting must also use the --name= option."))

            dev = devicetree.get_device_by_name(self.vgname)
            if not dev:
                raise KickstartParseError(lineno=self.lineno,
                        msg=_("Volume group \"%s\" given in volgroup command does not exist.") % self.vgname)
        elif self.vgname in (vg.name for vg in storage.vgs):
            raise KickstartParseError(lineno=self.lineno,
                    msg=_("The volume group name \"%s\" is already in use.") % self.vgname)
        else:
            try:
                request = storage.new_vg(parents=pvs,
                                         name=self.vgname,
                                         pe_size=pesize)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(lineno=self.lineno, msg=str(e))

            storage.create_device(request)
            if self.reserved_space:
                request.reserved_space = self.reserved_space
            elif self.reserved_percent:
                request.reserved_percent = self.reserved_percent

            # in case we had to truncate or otherwise adjust the specified name
            ksdata.onPart[self.vgname] = request.name

class XConfig(RemovedCommand):

    def __str__(self):
        # The kickstart for this command is generated
        # by Services module in the Services class.
        return ""

    def execute(self, *args):
        desktop = Desktop()
        services_proxy = SERVICES.get_proxy()
        default_target = services_proxy.DefaultTarget
        default_desktop = services_proxy.DefaultDesktop

        if default_target:
            log.debug("Using the default target %s.", default_target)
            desktop.default_target = default_target

        if default_desktop:
            log.debug("Using the default desktop %s.", default_desktop)
            desktop.desktop = default_desktop

        desktop.write()

class Snapshot(COMMANDS.Snapshot):
    def _post_snapshots(self):
        return filter(lambda snap: snap.when == SNAPSHOT_WHEN_POST_INSTALL, self.dataList())

    def _pre_snapshots(self):
        return filter(lambda snap: snap.when == SNAPSHOT_WHEN_PRE_INSTALL, self.dataList())

    def has_snapshot(self, when):
        """ Is snapshot with this `when` parameter contained in the list of snapshots?

            :param when: `when` parameter from pykickstart which should be test for present.
            :type when: One of the constants from `pykickstart.constants.SNAPSHOT_*`
            :returns: True if snapshot with this `when` parameter is present,
                      False otherwise.
        """
        return any(snap.when == when for snap in self.dataList())

    def setup(self, storage, ksdata):
        """ Prepare post installation snapshots.

            This will also do the checking of snapshot validity.
        """
        for snap_data in self._post_snapshots():
            snap_data.setup(storage, ksdata)

    def execute(self, storage, ksdata):
        """ Create ThinLV snapshot after post section stops.

            Blivet must be reset before creation of the snapshot. This is
            required because the storage could be changed in post section.
        """
        post_snapshots = self._post_snapshots()

        if post_snapshots:
            try_populate_devicetree(storage.devicetree)
            for snap_data in post_snapshots:
                log.debug("Snapshot: creating post-install snapshot %s", snap_data.name)
                snap_data.execute(storage, ksdata)

    def pre_setup(self, storage, ksdata):
        """ Prepare pre installation snapshots.

            This will also do the checking of snapshot validity.
        """
        pre_snapshots = self._pre_snapshots()

        # wait for the storage to load devices
        if pre_snapshots:
            threadMgr.wait(THREAD_STORAGE)

        for snap_data in pre_snapshots:
            snap_data.setup(storage, ksdata)

    def pre_execute(self, storage, ksdata):
        """ Create ThinLV snapshot before installation starts.

            This must be done before user can change anything
        """
        pre_snapshots = self._pre_snapshots()

        if pre_snapshots:
            threadMgr.wait(THREAD_STORAGE)
            disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)

            if disk_init_proxy.DevicesToClear \
                or disk_init_proxy.DrivesToClear \
                    or disk_init_proxy.InitializationMode == CLEAR_PARTITIONS_ALL:
                log.warning("Snapshot: \"clearpart\" command could erase pre-install snapshots!")

            if disk_init_proxy.FormatUnrecognizedEnabled:
                log.warning("Snapshot: \"zerombr\" command could erase pre-install snapshots!")

            for snap_data in pre_snapshots:
                log.debug("Snapshot: creating pre-install snapshot %s", snap_data.name)
                snap_data.execute(storage, ksdata)

            try_populate_devicetree(storage.devicetree)

class SnapshotData(COMMANDS.SnapshotData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thin_snapshot = None

    def setup(self, storage, ksdata):
        """ Add ThinLV snapshot to Blivet model but do not create it.

            This will plan snapshot creation on the end of the installation. This way
            Blivet will do a validity checking for future snapshot.
        """
        if not self.origin.count('/') == 1:
            msg = _("Incorrectly specified origin of the snapshot. Use format \"VolGroup/LV-name\"")
            raise KickstartParseError(lineno=self.lineno, msg=msg)

        # modify origin and snapshot name to the proper DM naming
        snap_name = self.name.replace('-', '--')
        origin = self.origin.replace('-', '--').replace('/', '-')
        origin_dev = storage.devicetree.get_device_by_name(origin)
        log.debug("Snapshot: name %s has origin %s", self.name, origin_dev)

        if origin_dev is None:
            msg = _("Snapshot: origin \"%s\" doesn't exists!") % self.origin
            raise KickstartParseError(lineno=self.lineno, msg=msg)

        if not origin_dev.is_thin_lv:
            msg = (_("Snapshot: origin \"%(origin)s\" of snapshot \"%(name)s\""
                     " is not a valid thin LV device.") % {"origin": self.origin,
                                                           "name": self.name})
            raise KickstartParseError(lineno=self.lineno, msg=msg)

        if storage.devicetree.get_device_by_name("%s-%s" % (origin_dev.vg.name, snap_name)):
            msg = _("Snapshot %s already exists.") % self.name
            raise KickstartParseError(lineno=self.lineno, msg=msg)

        self.thin_snapshot = None
        try:
            self.thin_snapshot = LVMLogicalVolumeDevice(name=self.name,
                                                        parents=[origin_dev.pool],
                                                        seg_type="thin",
                                                        origin=origin_dev)
        except ValueError as e:
            raise KickstartParseError(lineno=self.lineno, msg=e)

    def execute(self, storage, ksdata):
        """ Execute an action for snapshot creation. """
        self.thin_snapshot.create()
        if isinstance(self.thin_snapshot.format, XFS):
            log.debug("Generating new UUID for XFS snapshot")
            self.thin_snapshot.format.reset_uuid()

class Keyboard(RemovedCommand):

    def __str__(self):
        # The kickstart for this command is generated
        # by Localization module in the Lang class.
        return ""

    def execute(self, *args):
        localization_proxy = LOCALIZATION.get_proxy()
        keyboard.write_keyboard_config(localization_proxy, util.getSysroot())


###
### %anaconda Section
###
class AnacondaSectionHandler(BaseHandler):
    """A handler for only the anaconda ection's commands."""
    commandMap = {
        "pwpolicy": F22_PwPolicy
    }

    dataMap = {
        "PwPolicyData": F22_PwPolicyData
    }

    def __init__(self):
        super().__init__(mapping=self.commandMap, dataMapping=self.dataMap)

    def __str__(self):
        """Return the %anaconda section"""
        retval = ""
        # This dictionary should only be modified during __init__, so if it
        # changes during iteration something has gone horribly wrong.
        lst = sorted(self._writeOrder.keys())
        for prio in lst:
            for obj in self._writeOrder[prio]:
                retval += str(obj)

        if retval:
            retval = "\n%anaconda\n" + retval + "%end\n"
        return retval

class AnacondaSection(Section):
    """A section for anaconda specific commands."""
    sectionOpen = "%anaconda"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmdno = 0

    def handleLine(self, line):
        if not self.handler:
            return

        self.cmdno += 1
        args = shlex.split(line, comments=True)
        self.handler.currentCmd = args[0]
        self.handler.currentLine = self.cmdno
        return self.handler.dispatcher(args, self.cmdno)

    def handleHeader(self, lineno, args):
        """Process the arguments to the %anaconda header."""
        Section.handleHeader(self, lineno, args)

    def finalize(self):
        """Let %anaconda know no additional data will come."""
        Section.finalize(self)

###
### HANDLERS
###

# This is just the latest entry from pykickstart.handlers.control with all the
# classes we're overriding in place of the defaults.
commandMap = {
    "auth": UselessCommand,
    "authconfig": UselessCommand,
    "authselect": Authselect,
    "autopart": AutoPart,
    "btrfs": BTRFS,
    "bootloader": Bootloader,
    "clearpart": ClearPart,
    "eula": Eula,
    "fcoe": UselessCommand,
    "firewall": Firewall,
    "firstboot": Firstboot,
    "group": Group,
    "ignoredisk": UselessCommand,
    "iscsi": Iscsi,
    "iscsiname": IscsiName,
    "keyboard": Keyboard,
    "lang": Lang,
    "logging": Logging,
    "logvol": LogVol,
    "mount": Mount,
    "network": Network,
    "nvdimm": Nvdimm,
    "part": Partition,
    "partition": Partition,
    "raid": Raid,
    "realm": Realm,
    "reqpart": ReqPart,
    "rootpw": RootPw,
    "selinux": SELinux,
    "services": Services,
    "sshkey": SshKey,
    "skipx": UselessCommand,
    "snapshot": Snapshot,
    "timezone": Timezone,
    "user": User,
    "volgroup": VolGroup,
    "xconfig": XConfig,
    "zerombr": UselessCommand,
    "zfcp": UselessCommand,
}

dataMap = {
    "BTRFSData": BTRFSData,
    "LogVolData": LogVolData,
    "PartData": PartitionData,
    "RaidData": RaidData,
    "RepoData": RepoData,
    "SnapshotData": SnapshotData,
    "VolGroupData": VolGroupData,
}

superclass = returnClassForVersion(VERSION)

class AnacondaKSHandler(superclass):
    AddonClassType = AddonData

    def __init__(self, addon_paths=None, commandUpdates=None, dataUpdates=None):
        if addon_paths is None:
            addon_paths = []

        if commandUpdates is None:
            commandUpdates = commandMap

        if dataUpdates is None:
            dataUpdates = dataMap

        super().__init__(commandUpdates=commandUpdates, dataUpdates=dataUpdates)
        self.onPart = {}

        # collect all kickstart addons for anaconda to addons dictionary
        # which maps addon_id to it's own data structure based on BaseData
        # with execute method
        addons = {}

        # collect all AddonData subclasses from
        # for p in addon_paths: <p>/<plugin id>/ks/*.(py|so)
        # and register them under <plugin id> name
        for module_name, path in addon_paths:
            addon_id = os.path.basename(os.path.dirname(os.path.abspath(path)))
            if not os.path.isdir(path):
                continue

            classes = util.collect(module_name, path,
                                   lambda cls: issubclass(cls, self.AddonClassType))
            if classes:
                addons[addon_id] = classes[0](name=addon_id)

        # Prepare the final structures for 3rd party addons
        self.addons = AddonRegistry(addons)

        # The %anaconda section uses its own handler for a limited set of commands
        self.anaconda = AnacondaSectionHandler()

    def __str__(self):
        return super().__str__() + "\n" + str(self.addons) + str(self.anaconda)

class AnacondaPreParser(KickstartParser):
    # A subclass of KickstartParser that only looks for %pre scripts and
    # sets them up to be run.  All other scripts and commands are ignored.
    def __init__(self, handler, followIncludes=True, errorsAreFatal=True,
                 missingIncludeIsFatal=True):
        super().__init__(handler, missingIncludeIsFatal=False)

    def handleCommand(self, lineno, args):
        pass

    def setupSections(self):
        self.registerSection(PreScriptSection(self.handler, dataObj=AnacondaKSScript))
        self.registerSection(NullSection(self.handler, sectionOpen="%pre-install"))
        self.registerSection(NullSection(self.handler, sectionOpen="%post"))
        self.registerSection(NullSection(self.handler, sectionOpen="%onerror"))
        self.registerSection(NullSection(self.handler, sectionOpen="%traceback"))
        self.registerSection(NullSection(self.handler, sectionOpen="%packages"))
        self.registerSection(NullSection(self.handler, sectionOpen="%addon"))
        self.registerSection(NullSection(self.handler.anaconda, sectionOpen="%anaconda"))


class AnacondaKSParser(KickstartParser):
    def __init__(self, handler, followIncludes=True, errorsAreFatal=True,
                 missingIncludeIsFatal=True, scriptClass=AnacondaKSScript):
        self.scriptClass = scriptClass
        super().__init__(handler)

    def handleCommand(self, lineno, args):
        if not self.handler:
            return

        return KickstartParser.handleCommand(self, lineno, args)

    def setupSections(self):
        self.registerSection(PreScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PreInstallScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PostScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(TracebackScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(OnErrorScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PackageSection(self.handler))
        self.registerSection(AddonSection(self.handler))
        self.registerSection(AnacondaSection(self.handler.anaconda))

def preScriptPass(f):
    # The first pass through kickstart file processing - look for %pre scripts
    # and run them.  This must come in a separate pass in case a script
    # generates an included file that has commands for later.
    ksparser = AnacondaPreParser(AnacondaKSHandler())

    with check_kickstart_error():
        ksparser.readKickstart(f)

    # run %pre scripts
    runPreScripts(ksparser.handler.scripts)

def parseKickstart(f, strict_mode=False, pass_to_boss=False):
    # preprocessing the kickstart file has already been handled in initramfs.

    addon_paths = collect_addon_paths(ADDON_PATHS)
    handler = AnacondaKSHandler(addon_paths["ks"])
    ksparser = AnacondaKSParser(handler)

    # So that drives onlined by these can be used in the ks file
    blivet.iscsi.iscsi.startup()
    # Note we do NOT call dasd.startup() here, that does not online drives, but
    # only checks if they need formatting, which requires zerombr to be known

    kswarnings = []
    ksmodule = "pykickstart"
    kscategories = (UserWarning, SyntaxWarning, DeprecationWarning)
    showwarning = warnings.showwarning

    def ksshowwarning(message, category, filename, lineno, file=None, line=None):
        # Print the warning with default function.
        showwarning(message, category, filename, lineno, file, line)
        # Collect pykickstart warnings.
        if ksmodule in filename and issubclass(category, kscategories):
            kswarnings.append(message)

    try:
        # Process warnings differently in this part.
        with warnings.catch_warnings():

            # Set up the warnings module.
            warnings.showwarning = ksshowwarning

            for category in kscategories:
                warnings.filterwarnings(action="always", module=ksmodule, category=category)

            # Parse the kickstart file in DBus modules.
            if pass_to_boss:
                boss = BOSS.get_proxy()

                boss.SplitKickstart(f)
                errors = boss.DistributeKickstart()

                if errors:
                    message = "\n\n".join("{error_message}".format_map(e) for e in errors)
                    raise KickstartError(message)

            # Parse the kickstart file in anaconda.
            ksparser.readKickstart(f)

            # Process pykickstart warnings in the strict mode:
            if strict_mode and kswarnings:
                raise KickstartError("Please modify your kickstart file to fix the warnings "
                                     "or remove the `ksstrict` option.")

    except (KickstartError, SplitKickstartError) as e:
        # We do not have an interface here yet, so we cannot use our error
        # handling callback.
        parsing_log.error(e)

        # Print kickstart warnings in the strict mode.
        if strict_mode and kswarnings:
            print(_("\nSome warnings occurred during reading the kickstart file:"))
            for w in kswarnings:
                print(str(w).strip())

        # Print an error and terminate.
        print(_("\nAn error occurred during reading the kickstart file:"
                "\n%s\n\nThe installer will now terminate.") % str(e).strip())

        util.ipmi_report(IPMI_ABORTED)
        time.sleep(10)
        sys.exit(1)

    return handler

def appendPostScripts(ksdata):
    scripts = ""

    # Read in all the post script snippets to a single big string.
    for fn in glob.glob("/usr/share/anaconda/post-scripts/*ks"):
        f = open(fn, "r")
        scripts += f.read()
        f.close()

    # Then parse the snippets against the existing ksdata.  We can do this
    # because pykickstart allows multiple parses to save their data into a
    # single data object.  Errors parsing the scripts are a bug in anaconda,
    # so just raise an exception.
    ksparser = AnacondaKSParser(ksdata, scriptClass=AnacondaInternalScript)
    ksparser.readKickstartFromString(scripts, reset=False)

def runPostScripts(scripts):
    postScripts = [s for s in scripts if s.type == KS_SCRIPT_POST]

    if len(postScripts) == 0:
        return

    script_log.info("Running kickstart %%post script(s)")
    for script in postScripts:
        script.run(util.getSysroot())
    script_log.info("All kickstart %%post script(s) have been run")

def runPreScripts(scripts):
    preScripts = [s for s in scripts if s.type == KS_SCRIPT_PRE]

    if len(preScripts) == 0:
        return

    script_log.info("Running kickstart %%pre script(s)")
    stdoutLog.info(_("Running pre-installation scripts"))

    for script in preScripts:
        script.run("/")

    script_log.info("All kickstart %%pre script(s) have been run")

def runPreInstallScripts(scripts):
    preInstallScripts = [s for s in scripts if s.type == KS_SCRIPT_PREINSTALL]

    if len(preInstallScripts) == 0:
        return

    script_log.info("Running kickstart %%pre-install script(s)")

    for script in preInstallScripts:
        script.run("/")

    script_log.info("All kickstart %%pre-install script(s) have been run")

def runTracebackScripts(scripts):
    script_log.info("Running kickstart %%traceback script(s)")
    for script in filter(lambda s: s.type == KS_SCRIPT_TRACEBACK, scripts):
        script.run("/")
    script_log.info("All kickstart %%traceback script(s) have been run")

def resetCustomStorageData(ksdata):
    for command in ["partition", "raid", "volgroup", "logvol", "btrfs"]:
        ksdata.resetCommand(command)

def doKickstartStorage(storage, ksdata):
    """ Setup storage state from the kickstart data """
    ksdata.clearpart.execute(storage, ksdata)
    if not any(d for d in storage.disks
               if not d.format.hidden and not d.protected):
        return

    # snapshot free space now so that we know how much we had available
    storage.create_free_space_snapshot()

    ksdata.bootloader.execute(storage, ksdata, dry_run=True)
    ksdata.autopart.execute(storage, ksdata)
    ksdata.reqpart.execute(storage, ksdata)
    ksdata.partition.execute(storage, ksdata)
    ksdata.raid.execute(storage, ksdata)
    ksdata.volgroup.execute(storage, ksdata)
    ksdata.logvol.execute(storage, ksdata)
    ksdata.btrfs.execute(storage, ksdata)
    ksdata.mount.execute(storage, ksdata)
    # setup snapshot here, that means add it to model and do the tests
    # snapshot will be created on the end of the installation
    ksdata.snapshot.setup(storage, ksdata)
    # also calls ksdata.bootloader.execute
    storage.set_up_bootloader()
