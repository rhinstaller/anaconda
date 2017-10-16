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
import requests
import shlex
import sys
import tempfile
import time
import warnings

import blivet.arch
import blivet.fcoe
import blivet.iscsi
import blivet.zfcp

import pykickstart.commands as commands

from contextlib import contextmanager

from pyanaconda import iutil, keyboard, localization, network, nm, ntp, screen_access, timezone
from pyanaconda.addons import AddonSection, AddonData, AddonRegistry, collect_addon_paths
from pyanaconda.bootloader import GRUB2, get_bootloader
from pyanaconda.constants import ADDON_PATHS, IPMI_ABORTED, TEXT_ONLY_TARGET, GRAPHICAL_TARGET, THREAD_STORAGE
from pyanaconda.desktop import Desktop
from pyanaconda.errors import ScriptError, errorHandler
from pyanaconda.flags import flags, can_touch_runtime_system
from pyanaconda.i18n import _
from pyanaconda.iutil import collect
from pyanaconda.pwpolicy import F22_PwPolicy, F22_PwPolicyData
from pyanaconda.simpleconfig import SimpleConfigFile
from pyanaconda.storage_utils import device_matches, try_populate_devicetree
from pyanaconda.threading import threadMgr
from pyanaconda.timezone import NTP_PACKAGE, NTP_SERVICE
from pyanaconda.users import getPassAlgo

from blivet import autopart, udev
from blivet.deviceaction import ActionCreateFormat, ActionResizeDevice, ActionResizeFormat
from blivet.devicelibs.crypto import MIN_CREATE_ENTROPY
from blivet.devicelibs.lvm import LVM_PE_SIZE, KNOWN_THPOOL_PROFILES
from blivet.devices import LUKSDevice
from blivet.devices.lvm import LVMVolumeGroupDevice, LVMCacheRequest, LVMLogicalVolumeDevice
from blivet.errors import PartitioningError, StorageError, BTRFSValueError
from blivet.formats.fs import XFS
from blivet.formats import get_format
from blivet.partitioning import do_partitioning, grow_lvm
from blivet.platform import platform
from blivet.size import Size, KiB

from pykickstart.base import BaseHandler, KickstartCommand
from pykickstart.options import KSOptionParser
from pykickstart.constants import CLEARPART_TYPE_NONE, CLEARPART_TYPE_ALL, \
                                  FIRSTBOOT_SKIP, FIRSTBOOT_RECONFIG, \
                                  KS_SCRIPT_POST, KS_SCRIPT_PRE, KS_SCRIPT_TRACEBACK, KS_SCRIPT_PREINSTALL, \
                                  SELINUX_DISABLED, SELINUX_ENFORCING, SELINUX_PERMISSIVE, \
                                  SNAPSHOT_WHEN_POST_INSTALL, SNAPSHOT_WHEN_PRE_INSTALL
from pykickstart.errors import formatErrorMsg, KickstartError, KickstartParseError
from pykickstart.parser import KickstartParser
from pykickstart.parser import Script as KSScript
from pykickstart.sections import NullSection, PackageSection, PostScriptSection, PreScriptSection, PreInstallScriptSection, \
                                 OnErrorScriptSection, TracebackScriptSection, Section
from pykickstart.version import returnClassForVersion

from pyanaconda import anaconda_logging
from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger, get_stderr_logger, get_blivet_logger, get_anaconda_root_logger
log = get_module_logger(__name__)

stderrLog = get_stderr_logger()
stdoutLog = get_stdout_logger()
storage_log = get_blivet_logger()

# kickstart parsing and kickstart script
script_log = log.getChild("script")
parsing_log = log.getChild("parsing")

# command specific loggers
authconfig_log = log.getChild("kickstart.authconfig")
bootloader_log = log.getChild("kickstart.bootloader")
user_log = log.getChild("kickstart.user")
group_log = log.getChild("kickstart.group")
clearpart_log = log.getChild("kickstart.clearpart")
autopart_log = log.getChild("kickstart.autopart")
logvol_log = log.getChild("kickstart.logvol")
iscsi_log = log.getChild("kickstart.iscsi")
fcoe_log = log.getChild("kickstart.fcoe")
zfcp_log = log.getChild("kickstart.zfcp")
network_log = log.getChild("kickstart.network")
selinux_log = log.getChild("kickstart.selinux")
timezone_log = log.getChild("kickstart.timezone")
realm_log = log.getChild("kickstart.realm")
escrow_log = log.getChild("kickstart.escrow")
upgrade_log = log.getChild("kickstart.upgrade")

@contextmanager
def check_kickstart_error():
    try:
        yield
    except KickstartError as e:
        # We do not have an interface here yet, so we cannot use our error
        # handling callback.
        print(e)
        iutil.ipmi_report(IPMI_ABORTED)
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
            rc = iutil.execWithRedirect(self.interp, ["/tmp/%s" % os.path.basename(path)],
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
                iutil.ipmi_report(IPMI_ABORTED)
                sys.exit(0)

class AnacondaInternalScript(AnacondaKSScript):
    def __init__(self, *args, **kwargs):
        AnacondaKSScript.__init__(self, *args, **kwargs)
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
    if needs_net and not nm.nm_is_connected():
        msg = _("Escrow certificate %s requires the network.") % url
        raise KickstartError(msg)

    escrow_log.info("escrow: downloading %s", url)

    try:
        request = iutil.requests_session().get(url, verify=True)
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

class Authconfig(commands.authconfig.FC3_Authconfig):
    def __init__(self, *args, **kwargs):
        commands.authconfig.FC3_Authconfig.__init__(self, *args, **kwargs)
        self.packages = []

    def setup(self):
        if self.seen:
            self.packages = ["authconfig"]

    def execute(self, *args):
        cmd = "/usr/sbin/authconfig"
        if not os.path.lexists(iutil.getSysroot()+cmd):
            if flags.automatedInstall and self.seen:
                msg = _("%s is missing. Cannot setup authentication.") % cmd
                raise KickstartError(msg)
            else:
                return

        args = ["--update", "--nostart"] + shlex.split(self.authconfig)

        if not flags.automatedInstall and \
           (os.path.exists(iutil.getSysroot() + "/lib64/security/pam_fprintd.so") or
            os.path.exists(iutil.getSysroot() + "/lib/security/pam_fprintd.so")):
            args += ["--enablefingerprint"]

        try:
            iutil.execInSysroot(cmd, args)
        except RuntimeError as msg:
            authconfig_log.error("Error running %s %s: %s", cmd, args, msg)

class AutoPart(commands.autopart.F26_AutoPart):
    def parse(self, args):
        retval = commands.autopart.F26_AutoPart.parse(self, args)

        if self.fstype:
            fmt = blivet.formats.get_format(self.fstype)
            if not fmt or fmt.type is None:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                                          msg=_("autopart fstype of %s is invalid.") % self.fstype))

        return retval

    def execute(self, storage, ksdata, instClass):
        from blivet.autopart import do_autopart
        from pyanaconda.storage_utils import storage_checker

        if not self.autopart:
            return

        # Sets up default autopartitioning. Use clearpart separately if you want it.
        # The filesystem type is already set in the storage.
        refreshAutoSwapSize(storage)
        storage.do_autopart = True

        if self.encrypted:
            storage.encrypted_autopart = True
            storage.encryption_passphrase = self.passphrase
            storage.encryption_cipher = self.cipher
            storage.autopart_escrow_cert = getEscrowCertificate(storage.escrow_certificates, self.escrowcert)
            storage.autoppart_add_backup_passphrase = self.backuppassphrase

        if self.type is not None:
            storage.autopart_type = self.type

        do_autopart(storage, ksdata, min_luks_entropy=MIN_CREATE_ENTROPY)
        report = storage_checker.check(storage)
        report.log(autopart_log)

        if report.failure:
            raise PartitioningError("autopart failed: \n" + "\n".join(report.all_errors))

class Bootloader(commands.bootloader.F21_Bootloader):
    def __init__(self, *args, **kwargs):
        commands.bootloader.F21_Bootloader.__init__(self, *args, **kwargs)
        self.location = "mbr"
        self._useBackup = False
        self._origBootDrive = None

    def parse(self, args):
        commands.bootloader.F21_Bootloader.parse(self, args)
        if self.location == "partition" and isinstance(get_bootloader(), GRUB2):
            raise KickstartParseError(formatErrorMsg(self.lineno,
                                      msg=_("GRUB2 does not support installation to a partition.")))

        if self.isCrypted and isinstance(get_bootloader(), GRUB2):
            if not self.password.startswith("grub.pbkdf2."):
                raise KickstartParseError(formatErrorMsg(self.lineno,
                                          msg="GRUB2 encrypted password must be in grub.pbkdf2 format."))

        return self

    def execute(self, storage, ksdata, instClass, dry_run=False):
        """ Resolve and execute the bootloader installation.

            :param storage: object storing storage-related information
                            (disks, partitioning, bootloader, etc.)
            :type storage: blivet.Blivet
            :param payload: object storing payload-related information
            :type payload: pyanaconda.payload.Payload
            :param instclass: distribution-specific information
            :type instclass: pyanaconda.installclass.BaseInstallClass
            :param dry_run: flag if this is only dry run before the partitioning
                            will be resolved
            :type dry_run: bool
        """

        if flags.imageInstall and blivet.arch.is_s390():
            self.location = "none"

        if dry_run:
            self._origBootDrive = self.bootDrive
            self._useBackup = True
        elif self._useBackup:
            self.bootDrive = self._origBootDrive
            self._useBackup = False

        if self.location == "none":
            location = None
        elif self.location == "partition":
            location = "boot"
        else:
            location = self.location

        if not location:
            storage.bootloader.skip_bootloader = True
            return

        if self.appendLine:
            args = self.appendLine.split()
            storage.bootloader.boot_args.update(args)

        if self.password:
            if self.isCrypted:
                storage.bootloader.encrypted_password = self.password
            else:
                storage.bootloader.password = self.password

        if location:
            storage.bootloader.set_preferred_stage1_type(location)

        if self.timeout is not None:
            storage.bootloader.timeout = self.timeout

        # Throw out drives specified that don't exist or cannot be used (iSCSI
        # device on an s390 machine)
        disk_names = [d.name for d in storage.disks
                      if not d.format.hidden and not d.protected and
                      (not blivet.arch.is_s390() or not isinstance(d, blivet.devices.iScsiDiskDevice))]
        diskSet = set(disk_names)

        valid_disks = []
        # Drive specifications can contain | delimited variant specifications,
        # such as for example: "vd*|hd*|sd*"
        # So use the resolved disk identifiers returned by the device_matches() function in place
        # of the original specification but still remove the specifications that don't match anything
        # from the output kickstart to keep existing --driveorder processing behavior.
        for drive in self.driveorder[:]:
            matches = device_matches(drive, devicetree=storage.devicetree, disks_only=True)
            if set(matches).isdisjoint(diskSet):
                bootloader_log.warning("requested drive %s in boot drive order doesn't exist or cannot be used",
                                       drive)
                self.driveorder.remove(drive)
            else:
                valid_disks.extend(matches)

        storage.bootloader.disk_order = valid_disks

        # When bootloader doesn't have --boot-drive parameter then use this logic as fallback:
        # 1) If present first valid disk from driveorder parameter
        # 2) If present and usable, use disk where /boot partition is placed
        # 3) Use first disk from Blivet
        if self.bootDrive:
            matches = set(device_matches(self.bootDrive, devicetree=storage.devicetree, disks_only=True))
            if len(matches) > 1:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                                          msg=(_("More than one match found for given boot drive \"%s\".")
                                               % self.bootDrive)))
            elif matches.isdisjoint(diskSet):
                raise KickstartParseError(formatErrorMsg(self.lineno,
                                          msg=(_("Requested boot drive \"%s\" doesn't exist or cannot be used.")
                                               % self.bootDrive)))
        # Take valid disk from --driveorder
        elif len(valid_disks) >= 1:
            bootloader_log.debug("Bootloader: use '%s' first disk from driveorder as boot drive, dry run %s",
                      valid_disks[0], dry_run)
            self.bootDrive = valid_disks[0]
        else:
            # Try to find /boot
            #
            # This method is executed two times. Before and after partitioning.
            # In the first run, the result is used for other partitioning but
            # the second will be used.
            try:
                boot_dev = storage.mountpoints["/boot"]
            except KeyError:
                bootloader_log.debug("Bootloader: /boot partition is not present, dry run %s", dry_run)
            else:
                boot_drive = ""
                # Use disk ancestor
                if boot_dev.disks:
                    boot_drive = boot_dev.disks[0].name

                if boot_drive and boot_drive in disk_names:
                    self.bootDrive = boot_drive
                    bootloader_log.debug("Bootloader: use /boot partition's disk '%s' as boot drive, dry run %s",
                              boot_drive, dry_run)

        # Nothing was found use first disk from Blivet
        if not self.bootDrive:
            bootloader_log.debug("Bootloader: fallback use first disk return from Blivet '%s' as boot drive, dry run %s",
                      disk_names[0], dry_run)
            self.bootDrive = disk_names[0]

        drive = storage.devicetree.resolve_device(self.bootDrive)
        storage.bootloader.stage1_disk = drive

        if self.leavebootorder:
            flags.leavebootorder = True

        if self.nombr:
            flags.nombr = True

class BTRFS(commands.btrfs.F23_BTRFS):
    def execute(self, storage, ksdata, instClass):
        for b in self.btrfsList:
            b.execute(storage, ksdata, instClass)

class BTRFSData(commands.btrfs.F23_BTRFSData):
    def execute(self, storage, ksdata, instClass):
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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Btrfs partition \"%(device)s\" has a format of \"%(format)s\", but should have a format of \"btrfs\".") %
                             {"device": member, "format": dev.format.type}))

            if not dev:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Tried to use undefined partition \"%s\" in Btrfs volume specification.") % member))

            members.append(dev)

        if self.subvol:
            name = self.name
        elif self.label:
            name = self.label
        else:
            name = None

        if len(members) == 0 and not self.preexist:
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("Btrfs volume defined without any member devices.  Either specify member devices or use --useexisting.")))

        # allow creating btrfs vols/subvols without specifying mountpoint
        if self.mountpoint in ("none", "None"):
            self.mountpoint = ""

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("The mount point \"%s\" is not valid.  It must start with a /.") % self.mountpoint))

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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Btrfs volume \"%s\" specified with --useexisting does not exist.") % self.name))

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
                raise KickstartParseError(formatErrorMsg(self.lineno, msg=str(e)))

            storage.create_device(request)

class Realm(commands.realm.F19_Realm):
    def __init__(self, *args):
        commands.realm.F19_Realm.__init__(self, *args)
        self.packages = []
        self.discovered = ""

    def setup(self):
        if not self.join_realm:
            return

        try:
            argv = ["discover", "--verbose"] + self.discover_options + [self.join_realm]
            output = iutil.execWithCapture("realm", argv, filter_stderr=True)
        except OSError:
            # TODO: A lousy way of propagating what will usually be
            # 'no such realm'
            # The error message is logged by iutil
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
        for arg in self.join_args:
            if arg.startswith("--no-password") or arg.startswith("--one-time-password"):
                pw_args = []
                break
        else:
            # no explicit password arg using implicit --no-password
            pw_args = ["--no-password"]

        argv = ["join", "--install", iutil.getSysroot(), "--verbose"] + pw_args + self.join_args
        rc = -1
        try:
            rc = iutil.execWithRedirect("realm", argv)
        except OSError:
            pass

        if rc == 0:
            realm_log.info("Joined realm %s", self.join_realm)


class ClearPart(commands.clearpart.F21_ClearPart):
    def parse(self, args):
        retval = commands.clearpart.F21_ClearPart.parse(self, args)

        if self.type is None:
            self.type = CLEARPART_TYPE_NONE

        if self.disklabel and self.disklabel not in platform.disklabel_types:
            raise KickstartParseError(formatErrorMsg(self.lineno,
                                      msg=_("Disklabel \"%s\" given in clearpart command is not "
                                      "supported on this platform.") % self.disklabel))

        # Do any glob expansion now, since we need to have the real list of
        # disks available before the execute methods run.
        drives = []
        for spec in self.drives:
            matched = device_matches(spec, disks_only=True)
            if matched:
                drives.extend(matched)
            else:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Disk \"%s\" given in clearpart command does not exist.") % spec))

        self.drives = drives

        # Do any glob expansion now, since we need to have the real list of
        # devices available before the execute methods run.
        devices = []
        for spec in self.devices:
            matched = device_matches(spec, disks_only=True)
            if matched:
                devices.extend(matched)
            else:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Device \"%s\" given in clearpart device list does not exist.") % spec))

        self.devices = devices

        return retval

    def execute(self, storage, ksdata, instClass):
        storage.config.clearpart_type = self.type
        storage.config.clearpart_disks = self.drives
        storage.config.clearpart_devices = self.devices

        if self.initAll:
            storage.config.initialize_disks = self.initAll

        if self.disklabel:
            if not platform.set_default_disklabel_type(self.disklabel):
                clearpart_log.warning("%s is not a supported disklabel type on this platform. "
                                      "Using default disklabel %s instead.", self.disklabel, platform.default_disklabel_type)

        storage.clear_partitions()

class Fcoe(commands.fcoe.F13_Fcoe):
    def parse(self, args):
        fc = commands.fcoe.F13_Fcoe.parse(self, args)

        if fc.nic not in nm.nm_devices():
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("NIC \"%s\" given in fcoe command does not exist.") % fc.nic))

        if fc.nic in (info[0] for info in blivet.fcoe.fcoe.nics):
            fcoe_log.info("Kickstart fcoe device %s already added from EDD, ignoring", fc.nic)
        else:
            msg = blivet.fcoe.fcoe.add_san(nic=fc.nic, dcb=fc.dcb, auto_vlan=True)
            if not msg:
                msg = "Succeeded."
                blivet.fcoe.fcoe.added_nics.append(fc.nic)

            fcoe_log.info("adding FCoE SAN on %s: %s", fc.nic, msg)

        return fc

class Firewall(commands.firewall.F20_Firewall):
    def __init__(self, *args, **kwargs):
        commands.firewall.F20_Firewall.__init__(self, *args, **kwargs)
        self.packages = []

    def setup(self):
        if self.seen:
            self.packages = ["firewalld"]

    def execute(self, storage, ksdata, instClass):
        args = []
        # enabled is None if neither --enable or --disable is passed
        # default to enabled if nothing has been set.
        if self.enabled == False:
            args += ["--disabled"]
        else:
            args += ["--enabled"]

        if "ssh" not in self.services and "ssh" not in self.remove_services and "22:tcp" not in self.ports:
            args += ["--service=ssh"]

        for dev in self.trusts:
            args += ["--trust=%s" % (dev,)]

        for port in self.ports:
            args += ["--port=%s" % (port,)]

        for remove_service in self.remove_services:
            args += ["--remove-service=%s" % (remove_service,)]

        for service in self.services:
            args += ["--service=%s" % (service,)]

        cmd = "/usr/bin/firewall-offline-cmd"
        if not os.path.exists(iutil.getSysroot() + cmd):
            if self.enabled:
                msg = _("%s is missing. Cannot setup firewall.") % (cmd,)
                raise KickstartError(msg)
        else:
            iutil.execInSysroot(cmd, args)

class Firstboot(commands.firstboot.FC3_Firstboot):
    def setup(self, ksdata, instClass):
        if not self.seen:
            if flags.automatedInstall:
                # firstboot should be disabled by default after kickstart installations
                self.firstboot = FIRSTBOOT_SKIP
            elif instClass.firstboot and not self.firstboot:
                # if nothing is specified, use the installclass default for firstboot
                self.firstboot = instClass.firstboot

    def execute(self, *args):
        action = iutil.enable_service
        unit_name = "initial-setup.service"

        # find if the unit file for the Initial Setup service is installed
        unit_exists = os.path.exists(os.path.join(iutil.getSysroot(), "lib/systemd/system/", unit_name))
        if unit_exists and self.firstboot == FIRSTBOOT_RECONFIG:
            # write the reconfig trigger file
            f = open(os.path.join(iutil.getSysroot(), "etc/reconfigSys"), "w+")
            f.close()

        if self.firstboot == FIRSTBOOT_SKIP:
            action = iutil.disable_service
            # Also tell the screen access manager, so that the fact that post installation tools
            # should be disabled propagates to the user interaction config file.
            screen_access.sam.post_install_tools_disabled = True

        # enable/disable the Initial Setup service (if its unit is installed)
        if unit_exists:
            action(unit_name)

class Group(commands.group.F12_Group):
    def execute(self, storage, ksdata, instClass, users):
        for grp in self.groupList:
            kwargs = grp.__dict__
            kwargs.update({"root": iutil.getSysroot()})
            try:
                users.createGroup(grp.name, **kwargs)
            except ValueError as e:
                group_log.warning(str(e))

class IgnoreDisk(commands.ignoredisk.RHEL6_IgnoreDisk):
    def parse(self, args):
        retval = commands.ignoredisk.RHEL6_IgnoreDisk.parse(self, args)

        # See comment in ClearPart.parse
        drives = []
        for spec in self.ignoredisk:
            matched = device_matches(spec, disks_only=True)
            if matched:
                drives.extend(matched)
            else:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                                          msg=_("Disk \"%s\" given in ignoredisk command does not exist.") % spec))

        self.ignoredisk = drives

        drives = []
        for spec in self.onlyuse:
            matched = device_matches(spec, disks_only=True)
            if matched:
                drives.extend(matched)
            else:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                                          msg=_("Disk \"%s\" given in ignoredisk command does not exist.") % spec))

        self.onlyuse = drives

        return retval

class Iscsi(commands.iscsi.F17_Iscsi):
    def parse(self, args):
        tg = commands.iscsi.F17_Iscsi.parse(self, args)

        if tg.iface:
            if not network.wait_for_network_devices([tg.iface]):
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Network interface \"%(nic)s\" required by iSCSI \"%(iscsiTarget)s\" target is not up.") %
                             {"nic": tg.iface, "iscsiTarget": tg.target}))

        mode = blivet.iscsi.iscsi.mode
        if mode == "none":
            if tg.iface:
                blivet.iscsi.iscsi.create_interfaces(nm.nm_activated_devices())
        elif ((mode == "bind" and not tg.iface)
              or (mode == "default" and tg.iface)):
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("iscsi --iface must be specified (binding used) either for all targets or for none")))

        try:
            blivet.iscsi.iscsi.add_target(tg.ipaddr, tg.port, tg.user,
                                          tg.password, tg.user_in,
                                          tg.password_in,
                                          target=tg.target,
                                          iface=tg.iface)
            iscsi_log.info("added iscsi target %s at %s via %s", tg.target, tg.ipaddr, tg.iface)
        except (IOError, ValueError) as e:
            raise KickstartParseError(formatErrorMsg(self.lineno, msg=str(e)))

        return tg

class IscsiName(commands.iscsiname.FC6_IscsiName):
    def parse(self, args):
        retval = commands.iscsiname.FC6_IscsiName.parse(self, args)

        blivet.iscsi.iscsi.initiator = self.iscsiname
        return retval

class Lang(commands.lang.F19_Lang):
    def execute(self, *args, **kwargs):
        localization.write_language_configuration(self, iutil.getSysroot())

# no overrides needed here
Eula = commands.eula.F20_Eula

class LogVol(commands.logvol.F23_LogVol):
    def execute(self, storage, ksdata, instClass):
        for l in self.lvList:
            l.execute(storage, ksdata, instClass)

        if self.lvList:
            grow_lvm(storage)

class LogVolData(commands.logvol.F23_LogVolData):
    def execute(self, storage, ksdata, instClass):
        devicetree = storage.devicetree

        storage.do_autopart = False

        # FIXME: we should be running sanityCheck on partitioning that is not ks
        # autopart, but that's likely too invasive for #873135 at this moment
        if self.mountpoint == "/boot" and blivet.arch.is_s390():
            raise KickstartParseError(formatErrorMsg(self.lineno, msg="/boot can not be of type 'lvmlv' on s390x"))

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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg="Size can not be decided on from kickstart nor obtained from device."))
            try:
                size = Size("%d MiB" % self.size)
            except ValueError:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                                          msg="The size \"%s\" is invalid." % self.size))

        if self.thin_pool:
            self.mountpoint = ""
            ty = None

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("The mount point \"%s\" is not valid.  It must start with a /.") % self.mountpoint))

        # Check that the VG this LV is a member of has already been specified.
        vg = devicetree.get_device_by_name(vgname)
        if not vg:
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("No volume group exists with the name \"%s\".  Specify volume groups before logical volumes.") % self.vgname))

        # If cache PVs specified, check that they belong to the same VG this LV is a member of
        if self.cache_pvs:
            pv_devices = (lookupAlias(devicetree, pv) for pv in self.cache_pvs)
            if not all(pv in vg.pvs for pv in pv_devices):
                raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("Cache PVs must belong to the same VG as the cached LV")))

        pool = None
        if self.thin_volume:
            pool = devicetree.get_device_by_name("%s-%s" % (vg.name, self.pool_name))
            if not pool:
                err = formatErrorMsg(self.lineno,
                                     msg=_("No thin pool exists with the name \"%s\". Specify thin pools before thin volumes.") % self.pool_name)
                raise KickstartParseError(err)

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not self.name:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                                          msg=_("logvol --noformat must also use the --name= option.")))

            dev = devicetree.get_device_by_name("%s-%s" % (vg.name, self.name))
            if not dev:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Logical volume \"%s\" given in logvol command does not exist.") % self.name))

            if self.resize:
                size = dev.raw_device.align_target_size(size)
                if size < dev.currentSize:
                    # shrink
                    try:
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                    except ValueError:
                        raise KickstartParseError(formatErrorMsg(self.lineno,
                                msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                     {"size": self.size, "device": dev.name}))
                else:
                    # grow
                    try:
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                    except ValueError:
                        raise KickstartParseError(formatErrorMsg(self.lineno,
                                msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                     {"size": self.size, "device": dev.name}))

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            if ty == "swap":
                storage.add_fstab_swap(dev)
            return

        # Make sure this LV name is not already used in the requested VG.
        if not self.preexist:
            tmp = devicetree.get_device_by_name("%s-%s" % (vg.name, self.name))
            if tmp:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Logical volume name \"%(logvol)s\" is already in use in volume group \"%(volgroup)s\".") %
                             {"logvol": self.name, "volgroup": vg.name}))

            if not self.percent and size and not self.grow and size < vg.pe_size:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Logical volume size \"%(logvolSize)s\" must be larger than the volume group extent size of \"%(extentSize)s\".") %
                             {"logvolSize": size, "extentSize": vg.pe_size}))

        # Now get a format to hold a lot of these extra values.
        fmt = get_format(ty,
                         mountpoint=self.mountpoint,
                         label=self.label,
                         fsprofile=self.fsprofile,
                         create_options=self.mkfsopts,
                         mountopts=self.fsopts)
        if not fmt.type and not self.thin_pool:
            raise KickstartParseError(formatErrorMsg(self.lineno,
                                      msg=_("The \"%s\" file system type is not supported.") % ty))

        add_fstab_swap = None
        # If we were given a pre-existing LV to create a filesystem on, we need
        # to verify it and its VG exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing LVs.
        if self.preexist:
            device = devicetree.get_device_by_name("%s-%s" % (vg.name, self.name))
            if not device:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Logical volume \"%s\" given in logvol command does not exist.") % self.name))

            storage.devicetree.recursive_remove(device, remove_device=False)

            if self.resize:
                size = device.raw_device.align_target_size(size)
                try:
                    devicetree.actions.add(ActionResizeDevice(device, size))
                except ValueError:
                    raise KickstartParseError(formatErrorMsg(self.lineno,
                            msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                 {"size": self.size, "device": device.name}))

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
                    pool_args["metadatasize"] = Size("%d MiB" % self.metadata_size)
                if self.chunk_size:
                    pool_args["chunksize"] = Size("%d KiB" % self.chunk_size)

            if self.maxSizeMB:
                try:
                    maxsize = Size("%d MiB" % self.maxSizeMB)
                except ValueError:
                    raise KickstartParseError(formatErrorMsg(self.lineno,
                            msg="The maximum size \"%s\" is invalid." % self.maxSizeMB))
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
                raise KickstartParseError(formatErrorMsg(self.lineno, msg=str(e)))

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
            if self.preexist:
                luksformat = fmt
                device.format = get_format("luks", passphrase=self.passphrase, device=device.path,
                                           cipher=self.cipher,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.next_id,
                                     fmt=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = get_format("luks", passphrase=self.passphrase,
                                            cipher=self.cipher,
                                            escrow_cert=cert,
                                            add_backup_passphrase=self.backuppassphrase,
                                            min_luks_entropy=MIN_CREATE_ENTROPY)
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

class Logging(commands.logging.FC6_Logging):
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


class Mount(commands.mount.F27_Mount):
    def execute(self, storage, ksdata, instClass):
        storage.do_autopart = False

        for md in self.dataList():
            md.execute(storage, ksdata, instClass)

    def add_mount_data(self, md):
        self.mount_points.append(md)

    def remove_mount_data(self, md):
        self.mount_points.remove(md)

    def clear_mount_data(self):
        self.mount_points = list()

class MountData(commands.mount.F27_MountData):
    def execute(self, storage, ksdata, instClass):
        dev = storage.devicetree.resolve_device(self.device)
        if dev is None:
            raise KickstartParseError(formatErrorMsg(self.lineno,
                                      msg=_("Unknown or invalid device '%s' specified") % self.device))
        if self.reformat:
            if self.format:
                fmt = get_format(self.format)
                if not fmt:
                    msg = _("Unknown or invalid format '%(format)s' specified for device '%(device)s'") % \
                            {"format" : self.format, "device" : self.device}
                    raise KickstartParseError(formatErrorMsg(self.lineno, msg))
            else:
                old_fmt = dev.format
                if not old_fmt or old_fmt.type is None:
                    raise KickstartParseError(formatErrorMsg(self.lineno,
                                              msg=_("No format on device '%s'") % self.device))
                fmt = get_format(old_fmt.type)
            storage.format_device(dev, fmt)
            # make sure swaps end up in /etc/fstab
            if fmt.type == "swap":
                storage.add_fstab_swap(dev)

        # only set mount points for mountable formats
        if dev.format.mountable and self.mount_point is not None and self.mount_point != "none":
            dev.format.mountpoint = self.mount_point

        dev.format.create_options = self.mkfs_opts
        dev.format.options = self.mount_opts


class Network(commands.network.F27_Network):
    def __init__(self, *args, **kwargs):
        commands.network.F27_Network.__init__(self, *args, **kwargs)
        self.packages = []

    def parse(self, args):
        nd = commands.network.F27_Network.parse(self, args)
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

    def execute(self, storage, ksdata, instClass):
        network.write_network_config(storage, ksdata, instClass, iutil.getSysroot())

class Partition(commands.partition.F23_Partition):
    def execute(self, storage, ksdata, instClass):
        for p in self.partitions:
            p.execute(storage, ksdata, instClass)

        if self.partitions:
            do_partitioning(storage)

class PartitionData(commands.partition.F23_PartData):
    def execute(self, storage, ksdata, instClass):
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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("No disk found for specified BIOS disk \"%s\".") % self.onbiosdisk))

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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("RAID partition \"%s\" is defined multiple times.") % kwargs["name"]))

            if self.onPart:
                ksdata.onPart[kwargs["name"]] = self.onPart
        elif self.mountpoint.startswith("pv."):
            ty = "lvmpv"
            kwargs["name"] = self.mountpoint
            self.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("PV partition \"%s\" is defined multiple times.") % kwargs["name"]))

            if self.onPart:
                ksdata.onPart[kwargs["name"]] = self.onPart
        elif self.mountpoint.startswith("btrfs."):
            ty = "btrfs"
            kwargs["name"] = self.mountpoint
            self.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Btrfs partition \"%s\" is defined multiple times.") % kwargs["name"]))

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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                                          msg=_("The size \"%s\" is invalid.") % self.size))

        # If this specified an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not self.onPart:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("part --noformat must also use the --onpart option.")))

            dev = devicetree.resolve_device(self.onPart)
            if not dev:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Partition \"%s\" given in part command does not exist.") % self.onPart))

            if self.resize:
                size = dev.raw_device.align_target_size(size)
                if size < dev.currentSize:
                    # shrink
                    try:
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                    except ValueError:
                        raise KickstartParseError(formatErrorMsg(self.lineno,
                                msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                     {"size": self.size, "device": dev.name}))
                else:
                    # grow
                    try:
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                    except ValueError:
                        raise KickstartParseError(formatErrorMsg(self.lineno,
                                msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                     {"size": self.size, "device": dev.name}))

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
            raise KickstartParseError(formatErrorMsg(self.lineno,
                                      msg=_("The \"%s\" file system type is not supported.") % ty))

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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Disk \"%s\" given in part command does not exist.") % self.disk))
            if not disk.partitionable:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Cannot install to unpartitionable device \"%s\".") % self.disk))

            should_clear = storage.should_clear(disk)
            if disk and (disk.partitioned or should_clear):
                kwargs["parents"] = [disk]
            elif disk:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Disk \"%s\" in part command is not partitioned.") % self.disk))

            if not kwargs["parents"]:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Disk \"%s\" given in part command does not exist.") % self.disk))

        kwargs["grow"] = self.grow
        kwargs["size"] = size
        if self.maxSizeMB:
            try:
                maxsize = Size("%d MiB" % self.maxSizeMB)
            except ValueError:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("The maximum size \"%s\" is invalid.") % self.maxSizeMB))
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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Partition \"%s\" given in part command does not exist.") % self.onPart))

            storage.devicetree.recursive_remove(device, remove_device=False)
            if self.resize:
                size = device.raw_device.align_target_size(size)
                try:
                    devicetree.actions.add(ActionResizeDevice(device, size))
                except ValueError:
                    raise KickstartParseError(formatErrorMsg(self.lineno,
                            msg=_("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                                 {"size": self.size, "device": device.name}))

            devicetree.actions.add(ActionCreateFormat(device, kwargs["fmt"]))
            if ty == "swap":
                add_fstab_swap = device
        # tmpfs mounts are not disks and don't occupy a disk partition,
        # so handle them here
        elif self.fstype == "tmpfs":
            try:
                request = storage.new_tmp_fs(**kwargs)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(formatErrorMsg(self.lineno, msg=str(e)))
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
                raise KickstartParseError(formatErrorMsg(self.lineno, msg=str(e)))

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
            if self.onPart:
                luksformat = kwargs["fmt"]
                device.format = get_format("luks", passphrase=self.passphrase, device=device.path,
                                           cipher=self.cipher,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase,
                                           min_luks_entropy=MIN_CREATE_ENTROPY)
                luksdev = LUKSDevice("luks%d" % storage.next_id,
                                     fmt=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = get_format("luks", passphrase=self.passphrase,
                                            cipher=self.cipher,
                                            escrow_cert=cert,
                                            add_backup_passphrase=self.backuppassphrase,
                                            min_luks_entropy=MIN_CREATE_ENTROPY)
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

class Raid(commands.raid.F25_Raid):
    def execute(self, storage, ksdata, instClass):
        for r in self.raidList:
            r.execute(storage, ksdata, instClass)

class RaidData(commands.raid.F25_RaidData):
    def execute(self, storage, ksdata, instClass):
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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("PV partition \"%s\" is defined multiple times.") % kwargs["name"]))

            self.mountpoint = ""
        elif self.mountpoint.startswith("btrfs."):
            ty = "btrfs"
            kwargs["name"] = self.mountpoint
            ksdata.onPart[kwargs["name"]] = devicename

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Btrfs partition \"%s\" is defined multiple times.") % kwargs["name"]))

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
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("The mount point \"%s\" is not valid.  It must start with a /.") % self.mountpoint))

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not devicename:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("raid --noformat must also use the --device option.")))

            dev = devicetree.get_device_by_name(devicename)
            if not dev:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("RAID device  \"%s\" given in raid command does not exist.") % devicename))

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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("RAID device \"%(device)s\" has a format of \"%(format)s\", but should have a format of \"mdmember\".") %
                             {"device": member, "format": dev.format.type}))

            if not dev:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Tried to use undefined partition \"%s\" in RAID specification.") % member))

            raidmems.append(dev)

        # Now get a format to hold a lot of these extra values.
        kwargs["fmt"] = get_format(ty,
                                   label=self.label,
                                   fsprofile=self.fsprofile,
                                   mountpoint=self.mountpoint,
                                   mountopts=self.fsopts,
                                   create_options=self.mkfsopts)
        if not kwargs["fmt"].type:
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("The \"%s\" file system type is not supported.") % ty))

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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("RAID volume \"%s\" specified with --useexisting does not exist.") % devicename))

            storage.devicetree.recursive_remove(device, remove_device=False)
            devicetree.actions.add(ActionCreateFormat(device, kwargs["fmt"]))
            if ty == "swap":
                add_fstab_swap = device
        else:
            if devicename and devicename in (a.name for a in storage.mdarrays):
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("The RAID volume name \"%s\" is already in use.") % devicename))

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
                raise KickstartParseError(formatErrorMsg(self.lineno, msg=str(e)))

            storage.create_device(request)
            if ty == "swap":
                add_fstab_swap = request

        if self.encrypted:
            if self.passphrase and not storage.encryption_passphrase:
                storage.encryption_passphrase = self.passphrase

            cert = getEscrowCertificate(storage.escrow_certificates, self.escrowcert)
            if self.preexist:
                luksformat = kwargs["fmt"]
                device.format = get_format("luks", passphrase=self.passphrase, device=device.path,
                                           cipher=self.cipher,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.next_id,
                                     fmt=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = get_format("luks", passphrase=self.passphrase,
                                            cipher=self.cipher,
                                            escrow_cert=cert,
                                            add_backup_passphrase=self.backuppassphrase)
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

class RepoData(commands.repo.F27_RepoData):
    def __init__(self, *args, **kwargs):
        """ Add enabled kwarg

            :param enabled: The repo has been enabled
            :type enabled: bool
        """
        self.enabled = kwargs.pop("enabled", True)
        self.repo_id = kwargs.pop("repo_id", None)

        commands.repo.F27_RepoData.__init__(self, *args, **kwargs)

class ReqPart(commands.reqpart.F23_ReqPart):
    def execute(self, storage, ksdata, instClass):
        from blivet.autopart import do_reqpart

        if not self.reqpart:
            return

        reqs = platform.set_platform_bootloader_reqs()
        if self.addBoot:
            bootPartitions = platform.set_platform_boot_partition()

            # blivet doesn't know this - anaconda sets up the default boot fstype
            # in various places in this file, as well as in setDefaultPartitioning
            # in the install classes.  We need to duplicate that here.
            for part in bootPartitions:
                if part.mountpoint == "/boot":
                    part.fstype = storage.default_boot_fstype

            reqs += bootPartitions

        do_reqpart(storage, reqs)

class RootPw(commands.rootpw.F18_RootPw):
    def execute(self, storage, ksdata, instClass, users):
        if flags.automatedInstall and not self.password and not self.seen:
            # Lock the root password if during an installation with kickstart
            # the root password is empty & not specififed as empty in the kickstart
            # (seen == False) via the rootpw command.
            # Note that kickstart is actually the only way to specify an empty
            # root password - we don't allow that via the UI.
            self.lock = True
        elif not flags.automatedInstall and not self.password:
            # Also lock the root password if it was not set during interactive installation.
            self.lock = True


        algo = getPassAlgo(ksdata.authconfig.authconfig)
        users.setRootPassword(self.password, self.isCrypted, self.lock, algo, iutil.getSysroot())

class SELinux(commands.selinux.FC3_SELinux):
    def execute(self, *args):
        selinux_states = {SELINUX_DISABLED: "disabled",
                          SELINUX_ENFORCING: "enforcing",
                          SELINUX_PERMISSIVE: "permissive"}

        if self.selinux is None:
            # Use the defaults set by the installed (or not) selinux package
            return
        elif self.selinux not in selinux_states:
            selinux_log.error("unknown selinux state: %s", self.selinux)
            return

        try:
            selinux_cfg = SimpleConfigFile(iutil.getSysroot() + "/etc/selinux/config")
            selinux_cfg.read()
            selinux_cfg.set(("SELINUX", selinux_states[self.selinux]))
            selinux_cfg.write()
        except IOError as msg:
            selinux_log.error("Error setting selinux mode: %s", msg)

class Services(commands.services.FC6_Services):
    def execute(self, storage, ksdata, instClass):
        for svc in self.disabled:
            iutil.disable_service(svc)

        for svc in self.enabled:
            iutil.enable_service(svc)

class SshKey(commands.sshkey.F22_SshKey):
    def execute(self, storage, ksdata, instClass, users):
        for usr in self.sshUserList:
            users.setUserSshKey(usr.username, usr.key)

class Timezone(commands.timezone.F25_Timezone):
    def __init__(self, *args):
        commands.timezone.F25_Timezone.__init__(self, *args)
        self.packages = []

    def setup(self, ksdata):
        # do not install and use NTP package
        if self.nontp or NTP_PACKAGE in ksdata.packages.excludedList:
            if iutil.service_running(NTP_SERVICE) and \
                    can_touch_runtime_system("stop NTP service"):
                ret = iutil.stop_service(NTP_SERVICE)
                if ret != 0:
                    timezone_log.error("Failed to stop NTP service")

            if NTP_SERVICE not in ksdata.services.disabled:
                ksdata.services.disabled.append(NTP_SERVICE)
        # install and use NTP package
        else:
            if not iutil.service_running(NTP_SERVICE) and \
                    can_touch_runtime_system("start NTP service"):
                ret = iutil.start_service(NTP_SERVICE)
                if ret != 0:
                    timezone_log.error("Failed to start NTP service")

            self.packages.append(NTP_PACKAGE)

            if not NTP_SERVICE in ksdata.services.enabled and \
                    not NTP_SERVICE in ksdata.services.disabled:
                ksdata.services.enabled.append(NTP_SERVICE)

    def execute(self, *args):
        # write out timezone configuration
        if not timezone.is_valid_timezone(self.timezone):
            # this should never happen, but for pity's sake
            timezone_log.warning("Timezone %s set in kickstart is not valid, falling "
                                 "back to default (America/New_York).", self.timezone)
            self.timezone = "America/New_York"

        timezone.write_timezone_config(self, iutil.getSysroot())

        # write out NTP configuration (if set) and --nontp is not used
        if not self.nontp and self.ntpservers:
            chronyd_conf_path = os.path.normpath(iutil.getSysroot() + ntp.NTP_CONFIG_FILE)
            pools, servers = ntp.internal_to_pools_and_servers(self.ntpservers)
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

class User(commands.user.F19_User):
    def execute(self, storage, ksdata, instClass, users):
        algo = getPassAlgo(ksdata.authconfig.authconfig)

        for usr in self.userList:
            kwargs = usr.__dict__
            kwargs.update({"algo": algo, "root": iutil.getSysroot()})

            # If the user password came from a kickstart and it is blank we
            # need to make sure the account is locked, not created with an
            # empty password.
            if ksdata.user.seen and kwargs.get("password", "") == "":
                kwargs["password"] = None
            try:
                users.createUser(usr.name, **kwargs)
            except ValueError as e:
                user_log.warning(str(e))

class VolGroup(commands.volgroup.F21_VolGroup):
    def execute(self, storage, ksdata, instClass):
        for v in self.vgList:
            v.execute(storage, ksdata, instClass)

class VolGroupData(commands.volgroup.F21_VolGroupData):
    def execute(self, storage, ksdata, instClass):
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
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Physical volume \"%(device)s\" has a format of \"%(format)s\", but should have a format of \"lvmpv\".") %
                             {"device": pv, "format": dev.format.type}))

            if not dev:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Tried to use undefined partition \"%s\" in Volume Group specification") % pv))

            pvs.append(dev)

        if len(pvs) == 0 and not self.preexist:
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("Volume group \"%s\" defined without any physical volumes.  Either specify physical volumes or use --useexisting.") % self.vgname))

        if self.pesize == 0:
            # default PE size requested -- we use blivet's default in KiB
            self.pesize = LVM_PE_SIZE.convert_to(KiB)

        pesize = Size("%d KiB" % self.pesize)
        possible_extents = LVMVolumeGroupDevice.get_supported_pe_sizes()
        if pesize not in possible_extents:
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("Volume group given physical extent size of \"%(extentSize)s\", but must be one of:\n%(validExtentSizes)s.") %
                         {"extentSize": pesize, "validExtentSizes": ", ".join(str(e) for e in possible_extents)}))

        # If --noformat or --useexisting was given, there's really nothing to do.
        if not self.format or self.preexist:
            if not self.vgname:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("volgroup --noformat and volgroup --useexisting must also use the --name= option.")))

            dev = devicetree.get_device_by_name(self.vgname)
            if not dev:
                raise KickstartParseError(formatErrorMsg(self.lineno,
                        msg=_("Volume group \"%s\" given in volgroup command does not exist.") % self.vgname))
        elif self.vgname in (vg.name for vg in storage.vgs):
            raise KickstartParseError(formatErrorMsg(self.lineno,
                    msg=_("The volume group name \"%s\" is already in use.") % self.vgname))
        else:
            try:
                request = storage.new_vg(parents=pvs,
                                         name=self.vgname,
                                         pe_size=pesize)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(formatErrorMsg(self.lineno, msg=str(e)))

            storage.create_device(request)
            if self.reserved_space:
                request.reserved_space = self.reserved_space
            elif self.reserved_percent:
                request.reserved_percent = self.reserved_percent

            # in case we had to truncate or otherwise adjust the specified name
            ksdata.onPart[self.vgname] = request.name

class XConfig(commands.xconfig.F14_XConfig):
    def execute(self, *args):
        desktop = Desktop()
        if self.startX:
            desktop.default_target = GRAPHICAL_TARGET

        if self.defaultdesktop:
            desktop.desktop = self.defaultdesktop

        # now write it out
        desktop.write()

class SkipX(commands.skipx.FC3_SkipX):
    def execute(self, *args):
        if self.skipx:
            desktop = Desktop()
            desktop.default_target = TEXT_ONLY_TARGET
            desktop.write()

class Snapshot(commands.snapshot.F26_Snapshot):
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

    def setup(self, storage, ksdata, instClass):
        """ Prepare post installation snapshots.

            This will also do the checking of snapshot validity.
        """
        for snap_data in self._post_snapshots():
            snap_data.setup(storage, ksdata, instClass)

    def execute(self, storage, ksdata, instClass):
        """ Create ThinLV snapshot after post section stops.

            Blivet must be reset before creation of the snapshot. This is
            required because the storage could be changed in post section.
        """
        post_snapshots = self._post_snapshots()

        if post_snapshots:
            try_populate_devicetree(storage.devicetree)
            for snap_data in post_snapshots:
                log.debug("Snapshot: creating post-install snapshot %s", snap_data.name)
                snap_data.execute(storage, ksdata, instClass)

    def pre_setup(self, storage, ksdata, instClass):
        """ Prepare pre installation snapshots.

            This will also do the checking of snapshot validity.
        """
        pre_snapshots = self._pre_snapshots()

        # wait for the storage to load devices
        if pre_snapshots:
            threadMgr.wait(THREAD_STORAGE)

        for snap_data in pre_snapshots:
            snap_data.setup(storage, ksdata, instClass)

    def pre_execute(self, storage, ksdata, instClass):
        """ Create ThinLV snapshot before installation starts.

            This must be done before user can change anything
        """
        pre_snapshots = self._pre_snapshots()

        if pre_snapshots:
            threadMgr.wait(THREAD_STORAGE)

            if (ksdata.clearpart.devices or ksdata.clearpart.drives or
                ksdata.clearpart.type == CLEARPART_TYPE_ALL):
                log.warning("Snapshot: \"clearpart\" command could erase pre-install snapshots!")
            if ksdata.zerombr.zerombr:
                log.warning("Snapshot: \"zerombr\" command could erase pre-install snapshots!")

            for snap_data in pre_snapshots:
                log.debug("Snapshot: creating pre-install snapshot %s", snap_data.name)
                snap_data.execute(storage, ksdata, instClass)

            try_populate_devicetree(storage.devicetree)

class SnapshotData(commands.snapshot.F26_SnapshotData):
    def __init__(self, *args, **kwargs):
        commands.snapshot.F26_SnapshotData.__init__(self, *args, **kwargs)
        self.thin_snapshot = None

    def setup(self, storage, ksdata, instClass):
        """ Add ThinLV snapshot to Blivet model but do not create it.

            This will plan snapshot creation on the end of the installation. This way
            Blivet will do a validity checking for future snapshot.
        """
        if not self.origin.count('/') == 1:
            msg = _("Incorrectly specified origin of the snapshot. Use format \"VolGroup/LV-name\"")
            raise KickstartParseError(formatErrorMsg(self.lineno, msg=msg))

        # modify origin and snapshot name to the proper DM naming
        snap_name = self.name.replace('-', '--')
        origin = self.origin.replace('-', '--').replace('/', '-')
        origin_dev = storage.devicetree.get_device_by_name(origin)
        log.debug("Snapshot: name %s has origin %s", self.name, origin_dev)

        if origin_dev is None:
            msg = _("Snapshot: origin \"%s\" doesn't exists!") % self.origin
            raise KickstartParseError(formatErrorMsg(self.lineno, msg=msg))

        if not origin_dev.is_thin_lv:
            msg = (_("Snapshot: origin \"%(origin)s\" of snapshot \"%(name)s\""
                     " is not a valid thin LV device.") % {"origin": self.origin,
                                                           "name": self.name})
            raise KickstartParseError(formatErrorMsg(self.lineno, msg=msg))

        if storage.devicetree.get_device_by_name("%s-%s" % (origin_dev.vg.name, snap_name)):
            msg = _("Snapshot %s already exists.") % self.name
            raise KickstartParseError(formatErrorMsg(self.lineno, msg=msg))

        self.thin_snapshot = None
        try:
            self.thin_snapshot = LVMLogicalVolumeDevice(name=self.name,
                                                        parents=[origin_dev.pool],
                                                        seg_type="thin",
                                                        origin=origin_dev)
        except ValueError as e:
            raise KickstartParseError(formatErrorMsg(self.lineno, msg=e))

    def execute(self, storage, ksdata, instClass):
        """ Execute an action for snapshot creation. """
        self.thin_snapshot.create()
        if isinstance(self.thin_snapshot.format, XFS):
            log.debug("Generating new UUID for XFS snapshot")
            self.thin_snapshot.format.reset_uuid()

class ZFCP(commands.zfcp.F14_ZFCP):
    def parse(self, args):
        fcp = commands.zfcp.F14_ZFCP.parse(self, args)
        try:
            blivet.zfcp.zfcp.add_fcp(fcp.devnum, fcp.wwpn, fcp.fcplun)
        except ValueError as e:
            zfcp_log.warning(str(e))

        return fcp

class Keyboard(commands.keyboard.F18_Keyboard):
    def execute(self, *args):
        keyboard.write_keyboard_config(self, iutil.getSysroot())

class Upgrade(commands.upgrade.F20_Upgrade):
    # Upgrade is no longer supported. If an upgrade command was included in
    # a kickstart, warn the user and exit.
    def parse(self, args):
        upgrade_log.error("The upgrade kickstart command is no longer supported. Upgrade functionality is provided through fedup.")
        sys.stderr.write(_("The upgrade kickstart command is no longer supported. Upgrade functionality is provided through fedup."))
        iutil.ipmi_report(IPMI_ABORTED)
        sys.exit(1)

###
### %anaconda Section
###


class F27_InstallClass(KickstartCommand):
    removedKeywords = KickstartCommand.removedKeywords
    removedAttrs = KickstartCommand.removedAttrs

    def __init__(self, *args, **kwargs):
        KickstartCommand.__init__(self, *args, **kwargs)
        self.op = self._getParser()
        self.name = kwargs.get("name", "")

    def __str__(self):
        retval = KickstartCommand.__str__(self)
        if not self.seen:
            return retval

        retval += "installclass%s\n" % self._getArgsAsStr()
        return retval

    def _getArgsAsStr(self):
        retval = ""
        if self.name:
            retval += ' --name="%s"' % self.name
        return retval

    def _getParser(self):
        op = KSOptionParser()
        op.add_option("--name", dest="name", required=True, type="string")
        return op

    def parse(self, args):
        (opts, _) = self.op.parse_args(args=args, lineno=self.lineno)
        self.set_to_self(self.op, opts)
        return self

class AnacondaSectionHandler(BaseHandler):
    """A handler for only the anaconda ection's commands."""
    commandMap = {
        "installclass": F27_InstallClass,
        "pwpolicy": F22_PwPolicy
    }

    dataMap = {
        "PwPolicyData": F22_PwPolicyData
    }

    def __init__(self):
        BaseHandler.__init__(self, mapping=self.commandMap, dataMapping=self.dataMap)

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
        Section.__init__(self, *args, **kwargs)
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
    "auth": Authconfig,
    "authconfig": Authconfig,
    "autopart": AutoPart,
    "btrfs": BTRFS,
    "bootloader": Bootloader,
    "clearpart": ClearPart,
    "eula": Eula,
    "fcoe": Fcoe,
    "firewall": Firewall,
    "firstboot": Firstboot,
    "group": Group,
    "ignoredisk": IgnoreDisk,
    "iscsi": Iscsi,
    "iscsiname": IscsiName,
    "keyboard": Keyboard,
    "lang": Lang,
    "logging": Logging,
    "logvol": LogVol,
    "mount": Mount,
    "network": Network,
    "part": Partition,
    "partition": Partition,
    "raid": Raid,
    "realm": Realm,
    "reqpart": ReqPart,
    "rootpw": RootPw,
    "selinux": SELinux,
    "services": Services,
    "sshkey": SshKey,
    "skipx": SkipX,
    "snapshot": Snapshot,
    "timezone": Timezone,
    "upgrade": Upgrade,
    "user": User,
    "volgroup": VolGroup,
    "xconfig": XConfig,
    "zfcp": ZFCP,
}

dataMap = {
    "BTRFSData": BTRFSData,
    "LogVolData": LogVolData,
    "MountData": MountData,
    "PartData": PartitionData,
    "RaidData": RaidData,
    "RepoData": RepoData,
    "SnapshotData": SnapshotData,
    "VolGroupData": VolGroupData,
}

superclass = returnClassForVersion()

class AnacondaKSHandler(superclass):
    AddonClassType = AddonData

    def __init__(self, addon_paths=None, commandUpdates=None, dataUpdates=None):
        if addon_paths is None:
            addon_paths = []

        if commandUpdates is None:
            commandUpdates = commandMap

        if dataUpdates is None:
            dataUpdates = dataMap

        superclass.__init__(self, commandUpdates=commandUpdates, dataUpdates=dataUpdates)
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

            classes = collect(module_name, path, lambda cls: issubclass(cls, self.AddonClassType))
            if classes:
                addons[addon_id] = classes[0](name=addon_id)

        # Prepare the final structures for 3rd party addons
        self.addons = AddonRegistry(addons)

        # The %anaconda section uses its own handler for a limited set of commands
        self.anaconda = AnacondaSectionHandler()

    def __str__(self):
        return superclass.__str__(self) + "\n" + str(self.addons) + str(self.anaconda)

class AnacondaPreParser(KickstartParser):
    # A subclass of KickstartParser that only looks for %pre scripts and
    # sets them up to be run.  All other scripts and commands are ignored.
    def __init__(self, handler, followIncludes=True, errorsAreFatal=True,
                 missingIncludeIsFatal=True):
        KickstartParser.__init__(self, handler, missingIncludeIsFatal=False)

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
        KickstartParser.__init__(self, handler)

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

def parseKickstart(f, strict_mode=False):
    # preprocessing the kickstart file has already been handled in initramfs.

    addon_paths = collect_addon_paths(ADDON_PATHS)
    handler = AnacondaKSHandler(addon_paths["ks"])
    ksparser = AnacondaKSParser(handler)

    # We need this so all the /dev/disk/* stuff is set up before parsing.
    udev.trigger(subsystem="block", action="change")
    # So that drives onlined by these can be used in the ks file
    blivet.iscsi.iscsi.startup()
    blivet.fcoe.fcoe.startup()
    blivet.zfcp.zfcp.startup()
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

            # Parse the kickstart file.
            ksparser.readKickstart(f)

            # Process pykickstart warnings in the strict mode:
            if strict_mode and kswarnings:
                raise KickstartError("Please modify your kickstart file to fix the warnings "
                                     "or remove the `ksstrict` option.")

    except KickstartError as e:
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

        iutil.ipmi_report(IPMI_ABORTED)
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
        script.run(iutil.getSysroot())
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

def doKickstartStorage(storage, ksdata, instClass):
    """ Setup storage state from the kickstart data """
    ksdata.clearpart.execute(storage, ksdata, instClass)
    if not any(d for d in storage.disks
               if not d.format.hidden and not d.protected):
        return

    # snapshot free space now so that we know how much we had available
    storage.create_free_space_snapshot()

    ksdata.bootloader.execute(storage, ksdata, instClass, dry_run=True)
    ksdata.autopart.execute(storage, ksdata, instClass)
    ksdata.reqpart.execute(storage, ksdata, instClass)
    ksdata.partition.execute(storage, ksdata, instClass)
    ksdata.raid.execute(storage, ksdata, instClass)
    ksdata.volgroup.execute(storage, ksdata, instClass)
    ksdata.logvol.execute(storage, ksdata, instClass)
    ksdata.btrfs.execute(storage, ksdata, instClass)
    ksdata.mount.execute(storage, ksdata, instClass)
    # setup snapshot here, that means add it to model and do the tests
    # snapshot will be created on the end of the installation
    ksdata.snapshot.setup(storage, ksdata, instClass)
    # also calls ksdata.bootloader.execute
    storage.set_up_bootloader()
