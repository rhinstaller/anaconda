#
# Copyright (C) 2019  Red Hat, Inc.
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
import blivet
from blivet.deviceaction import ActionResizeFormat, ActionResizeDevice, ActionCreateFormat
from blivet.devicelibs.crypto import MIN_CREATE_ENTROPY
from blivet.devices import LUKSDevice
from blivet.errors import PartitioningError, StorageError
from blivet.formats import get_format
from blivet.formats.disklabel import DiskLabel
from blivet.partitioning import do_partitioning
from blivet.size import Size
from blivet.static_data import luks_data
from pykickstart.errors import KickstartParseError

from pyanaconda.bootloader.execution import BootloaderExecutor
from pyanaconda.core.constants import AUTOPART_TYPE_DEFAULT
from pyanaconda.core.i18n import _
from pyanaconda.kickstart import refreshAutoSwapSize, getEscrowCertificate, getAvailableDiskSpace, \
    lookupAlias
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION, AUTO_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.platform import platform
from pyanaconda.storage import autopart
from pyanaconda.storage.checker import storage_checker
from pyanaconda.storage.utils import get_pbkdf_args


log = get_module_logger(__name__)

__all__ = ["do_kickstart_storage"]


def do_kickstart_storage(storage, data):
    """Setup storage state from the kickstart data.

    :param storage: an instance of the Blivet's storage object
    :param data: an instance of kickstart data
    """
    # Clear partitions.
    clear_partitions(storage)

    if not any(d for d in storage.disks
               if not d.format.hidden and not d.protected):
        return

    # Snapshot free space now, so that we know how much we had available.
    storage.create_free_space_snapshot()

    # Prepare the boot loader.
    BootloaderExecutor().execute(storage, dry_run=True)

    AutomaticPartitioningExecutor().execute(storage, data)
    CustomPartitioningExecutor().execute(storage, data)

    data.volgroup.execute(storage, data)
    data.logvol.execute(storage, data)
    data.btrfs.execute(storage, data)
    data.mount.execute(storage, data)

    # Set up the snapshot here.
    data.snapshot.setup(storage, data)

    # Set up the boot loader.
    storage.set_up_bootloader()


def clear_partitions(storage):
    """Clear partitions.

    :param storage: instance of the Blivet's storage object
    """
    disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
    storage.config.clear_part_type = disk_init_proxy.InitializationMode
    storage.config.clear_part_disks = disk_init_proxy.DrivesToClear
    storage.config.clear_part_devices = disk_init_proxy.DevicesToClear
    storage.config.initialize_disks = disk_init_proxy.InitializeLabelsEnabled

    disk_label = disk_init_proxy.DefaultDiskLabel

    if disk_label and not DiskLabel.set_default_label_type(disk_label):
        log.warning("%s is not a supported disklabel type on this platform. "
                    "Using default disklabel %s instead.", disk_label,
                    DiskLabel.get_platform_label_types()[0])

    storage.clear_partitions()


class AutomaticPartitioningExecutor(object):
    """The executor of the automatic partitioning."""

    def execute(self, storage, data):
        """Execute the automatic partitioning.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
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
            storage.autopart_add_backup_passphrase = auto_part_proxy.BackupPassphraseEnabled
            storage.autopart_escrow_cert = getEscrowCertificate(
                storage.escrow_certificates,
                auto_part_proxy.Escrowcert
            )

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

        autopart.do_autopart(storage, data, min_luks_entropy=MIN_CREATE_ENTROPY)
        report = storage_checker.check(storage)
        report.log(log)

        if report.failure:
            raise PartitioningError("autopart failed: \n" + "\n".join(report.all_errors))


class CustomPartitioningExecutor(object):
    """The executor of the custom partitioning."""

    def execute(self, storage, data):
        """Execute the custom partitioning.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        self._execute_reqpart(storage, data)
        self._execute_partition(storage, data)
        self._execute_raid(storage, data)

    def _execute_reqpart(self, storage, data):
        """Execute the reqpart command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        if not data.reqpart.reqpart:
            return

        log.debug("Looking for platform-specific bootloader requirements.")
        reqs = platform.set_platform_bootloader_reqs()

        if data.reqpart.addBoot:
            log.debug("Looking for platform-specific boot requirements.")
            boot_partitions = platform.set_platform_boot_partition()

            # Blivet doesn't know this - anaconda sets up the default boot fstype
            # in various places in this file. We need to duplicate that here.
            for part in boot_partitions:
                if part.mountpoint == "/boot":
                    part.fstype = storage.default_boot_fstype

            reqs += boot_partitions

        if reqs:
            log.debug("Applying requirements:\n%s", "".join(map(str, reqs)))
            autopart.do_reqpart(storage, reqs)

    def _execute_partition(self, storage, data):
        """Execute the partition command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        for partition_data in data.partition.partitions:
            self._execute_partition_data(storage, data, partition_data)

        if data.partition.partitions:
            do_partitioning(storage)

    def _execute_partition_data(self, storage, data, partition_data):
        """Execute the partition data.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        :param partition_data: an instance of PartData
        """
        devicetree = storage.devicetree
        kwargs = {}

        storage.do_autopart = False

        if partition_data.onbiosdisk != "":
            # edd_dict is only modified during storage.reset(), so don't do that
            # while executing storage.
            for (disk, biosdisk) in storage.edd_dict.items():
                if "%x" % biosdisk == partition_data.onbiosdisk:
                    partition_data.disk = disk
                    break

            if not partition_data.disk:
                raise KickstartParseError(
                    _("No disk found for specified BIOS disk \"%s\".")
                    % partition_data.onbiosdisk,
                    lineno=partition_data.lineno
                )

        size = None

        if partition_data.mountpoint == "swap":
            ty = "swap"
            partition_data.mountpoint = ""
            if partition_data.recommended or partition_data.hibernation:
                disk_space = getAvailableDiskSpace(storage)
                size = autopart.swap_suggestion(
                    hibernation=partition_data.hibernation,
                    disk_space=disk_space
                )
                partition_data.grow = False
        # if people want to specify no mountpoint for some reason, let them
        # this is really needed for pSeries boot partitions :(
        elif partition_data.mountpoint == "None":
            partition_data.mountpoint = ""
            if partition_data.fstype:
                ty = partition_data.fstype
            else:
                ty = storage.default_fstype
        elif partition_data.mountpoint == 'appleboot':
            ty = "appleboot"
            partition_data.mountpoint = ""
        elif partition_data.mountpoint == 'prepboot':
            ty = "prepboot"
            partition_data.mountpoint = ""
        elif partition_data.mountpoint == 'biosboot':
            ty = "biosboot"
            partition_data.mountpoint = ""
        elif partition_data.mountpoint.startswith("raid."):
            ty = "mdmember"
            kwargs["name"] = partition_data.mountpoint
            partition_data.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(
                    _("RAID partition \"%s\" is defined multiple times.") % kwargs["name"],
                    lineno=partition_data.lineno
                )

            if partition_data.onPart:
                data.onPart[kwargs["name"]] = partition_data.onPart
        elif partition_data.mountpoint.startswith("pv."):
            ty = "lvmpv"
            kwargs["name"] = partition_data.mountpoint
            partition_data.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(
                    _("PV partition \"%s\" is defined multiple times.") % kwargs["name"],
                    lineno=partition_data.lineno
                )

            if partition_data.onPart:
                data.onPart[kwargs["name"]] = partition_data.onPart
        elif partition_data.mountpoint.startswith("btrfs."):
            ty = "btrfs"
            kwargs["name"] = partition_data.mountpoint
            partition_data.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(
                    _("Btrfs partition \"%s\" is defined multiple times.") % kwargs["name"],
                    lineno=partition_data.lineno
                )

            if partition_data.onPart:
                data.onPart[kwargs["name"]] = partition_data.onPart
        elif partition_data.mountpoint == "/boot/efi":
            if blivet.arch.is_mactel():
                ty = "macefi"
            else:
                ty = "EFI System Partition"
                partition_data.fsopts = "defaults,uid=0,gid=0,umask=077,shortname=winnt"
        else:
            if partition_data.fstype != "":
                ty = partition_data.fstype
            elif partition_data.mountpoint == "/boot":
                ty = storage.default_boot_fstype
            else:
                ty = storage.default_fstype

        if not size and partition_data.size:
            try:
                size = Size("%d MiB" % partition_data.size)
            except ValueError:
                raise KickstartParseError(
                    _("The size \"%s\" is invalid.") % partition_data.size,
                    lineno=partition_data.lineno
                )

        # If this specified an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not partition_data.format:
            if not partition_data.onPart:
                raise KickstartParseError(
                    _("part --noformat must also use the --onpart option."),
                    lineno=partition_data.lineno
                )

            dev = devicetree.resolve_device(partition_data.onPart)
            if not dev:
                raise KickstartParseError(
                    _("Partition \"%s\" given in part command does not exist.")
                    % partition_data.onPart, lineno=partition_data.lineno
                )

            if partition_data.resize:
                size = dev.raw_device.align_target_size(size)
                if size < dev.currentSize:
                    # shrink
                    try:
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                    except ValueError:
                        raise KickstartParseError(
                            _("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                            {"size": partition_data.size, "device": dev.name},
                            lineno=partition_data.lineno
                        )
                else:
                    # grow
                    try:
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                    except ValueError:
                        raise KickstartParseError(
                            _("Target size \"%(size)s\" for device \"%(device)s\" is invalid.") %
                            {"size": partition_data.size, "device": dev.name},
                            lineno=partition_data.lineno
                        )

            dev.format.mountpoint = partition_data.mountpoint
            dev.format.mountopts = partition_data.fsopts
            if ty == "swap":
                storage.add_fstab_swap(dev)
            return

        # Now get a format to hold a lot of these extra values.
        kwargs["fmt"] = get_format(ty,
                                   mountpoint=partition_data.mountpoint,
                                   label=partition_data.label,
                                   fsprofile=partition_data.fsprofile,
                                   mountopts=partition_data.fsopts,
                                   create_options=partition_data.mkfsopts,
                                   size=size)
        if not kwargs["fmt"].type:
            raise KickstartParseError(
                _("The \"%s\" file system type is not supported.") % ty,
                lineno=partition_data.lineno
            )

        # If we were given a specific disk to create the partition on, verify
        # that it exists first.  If it doesn't exist, see if it exists with
        # mapper/ on the front.  If that doesn't exist either, it's an error.
        if partition_data.disk:
            disk = devicetree.resolve_device(partition_data.disk)
            # if this is a multipath member promote it to the real mpath
            if disk and disk.format.type == "multipath_member":
                mpath_device = disk.children[0]
                log.info("kickstart: part: promoting %s to %s", disk.name, mpath_device.name)
                disk = mpath_device
            if not disk:
                raise KickstartParseError(
                    _("Disk \"%s\" given in part command does not exist.") % partition_data.disk,
                    lineno=partition_data.lineno
                )
            if not disk.partitionable:
                raise KickstartParseError(
                    _("Cannot install to unpartitionable device \"%s\".") % partition_data.disk,
                    lineno=partition_data.lineno
                )

            should_clear = storage.should_clear(disk)
            if disk and (disk.partitioned or should_clear):
                kwargs["parents"] = [disk]
            elif disk:
                raise KickstartParseError(
                    _("Disk \"%s\" in part command is not partitioned.") % partition_data.disk,
                    lineno=partition_data.lineno
                )

            if not kwargs["parents"]:
                raise KickstartParseError(
                    _("Disk \"%s\" given in part command does not exist.") % partition_data.disk,
                    lineno=partition_data.lineno
                )

        kwargs["grow"] = partition_data.grow
        kwargs["size"] = size
        if partition_data.maxSizeMB:
            try:
                maxsize = Size("%d MiB" % partition_data.maxSizeMB)
            except ValueError:
                raise KickstartParseError(
                    _("The maximum size \"%s\" is invalid.") % partition_data.maxSizeMB,
                    lineno=partition_data.lineno
                )
        else:
            maxsize = None

        kwargs["maxsize"] = maxsize

        kwargs["primary"] = partition_data.primOnly

        add_fstab_swap = None
        # If we were given a pre-existing partition to create a filesystem on,
        # we need to verify it exists and then schedule a new format action to
        # take place there.  Also, we only support a subset of all the options
        # on pre-existing partitions.
        if partition_data.onPart:
            device = devicetree.resolve_device(partition_data.onPart)
            if not device:
                raise KickstartParseError(
                    _("Partition \"%s\" given in part command does not exist.")
                    % partition_data.onPart, lineno=partition_data.lineno
                )

            storage.devicetree.recursive_remove(device, remove_device=False)
            if partition_data.resize:
                size = device.raw_device.align_target_size(size)
                try:
                    devicetree.actions.add(ActionResizeDevice(device, size))
                except ValueError:
                    raise KickstartParseError(
                        _("Target size \"%(size)s\" for device \"%(device)s\" is invalid.")
                        % {"size": partition_data.size, "device": device.name},
                        lineno=partition_data.lineno
                    )

            devicetree.actions.add(ActionCreateFormat(device, kwargs["fmt"]))
            if ty == "swap":
                add_fstab_swap = device
        # tmpfs mounts are not disks and don't occupy a disk partition,
        # so handle them here
        elif partition_data.fstype == "tmpfs":
            try:
                request = storage.new_tmp_fs(**kwargs)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(lineno=partition_data.lineno, msg=str(e))
            storage.create_device(request)
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if partition_data.mountpoint:
                    device = storage.mountpoints[partition_data.mountpoint]
                    storage.destroy_device(device)
            except KeyError:
                pass

            try:
                request = storage.new_partition(**kwargs)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(lineno=partition_data.lineno, msg=str(e))

            storage.create_device(request)
            if ty == "swap":
                add_fstab_swap = request

        if partition_data.encrypted:
            if partition_data.passphrase and not storage.encryption_passphrase:
                storage.encryption_passphrase = partition_data.passphrase

            # try to use the global passphrase if available
            # XXX: we require the LV/part with --passphrase to be processed
            # before this one to setup the storage.encryption_passphrase
            partition_data.passphrase = partition_data.passphrase or storage.encryption_passphrase

            cert = getEscrowCertificate(storage.escrow_certificates, partition_data.escrowcert)

            # Get the version of LUKS and PBKDF arguments.
            partition_data.luks_version = partition_data.luks_version \
                                          or storage.default_luks_version

            pbkdf_args = get_pbkdf_args(
                luks_version=partition_data.luks_version,
                pbkdf_type=partition_data.pbkdf,
                max_memory_kb=partition_data.pbkdf_memory,
                iterations=partition_data.pbkdf_iterations,
                time_ms=partition_data.pbkdf_time
            )

            if pbkdf_args and not luks_data.pbkdf_args:
                luks_data.pbkdf_args = pbkdf_args

            if partition_data.onPart:
                luksformat = kwargs["fmt"]
                device.format = get_format(
                    "luks",
                    passphrase=partition_data.passphrase,
                    device=device.path,
                    cipher=partition_data.cipher,
                    escrow_cert=cert,
                    add_backup_passphrase=partition_data.backuppassphrase,
                    min_luks_entropy=MIN_CREATE_ENTROPY,
                    luks_version=partition_data.luks_version,
                    pbkdf_args=pbkdf_args
                )
                luksdev = LUKSDevice(
                    "luks%d" % storage.next_id,
                    fmt=luksformat,
                    parents=device
                )
            else:
                luksformat = request.format
                request.format = get_format(
                    "luks",
                    passphrase=partition_data.passphrase,
                    cipher=partition_data.cipher,
                    escrow_cert=cert,
                    add_backup_passphrase=partition_data.backuppassphrase,
                    min_luks_entropy=MIN_CREATE_ENTROPY,
                    luks_version=partition_data.luks_version,
                    pbkdf_args=pbkdf_args
                )
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

    def _execute_raid(self, storage, data):
        """Execute the raid command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        for raid_data in data.raid.raidList:
            self._execute_raid_data(storage, data, raid_data)

    def _execute_raid_data(self, storage, data, raid_data):
        """Execute the raid data.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        :param raid_data: an instance of RaidData
        """
        raidmems = []
        devicetree = storage.devicetree
        devicename = raid_data.device
        if raid_data.preexist:
            device = devicetree.resolve_device(devicename)
            if device:
                devicename = device.name

        kwargs = {}

        storage.do_autopart = False

        if raid_data.mountpoint == "swap":
            ty = "swap"
            raid_data.mountpoint = ""
        elif raid_data.mountpoint.startswith("pv."):
            ty = "lvmpv"
            kwargs["name"] = raid_data.mountpoint
            data.onPart[kwargs["name"]] = devicename

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(
                    _("PV partition \"%s\" is defined multiple times.") % kwargs["name"],
                    lineno=raid_data.lineno
                )

            raid_data.mountpoint = ""
        elif raid_data.mountpoint.startswith("btrfs."):
            ty = "btrfs"
            kwargs["name"] = raid_data.mountpoint
            data.onPart[kwargs["name"]] = devicename

            if devicetree.get_device_by_name(kwargs["name"]):
                raise KickstartParseError(
                    _("Btrfs partition \"%s\" is defined multiple times.") % kwargs["name"],
                    lineno=raid_data.lineno
                )

            raid_data.mountpoint = ""
        else:
            if raid_data.fstype != "":
                ty = raid_data.fstype
            elif raid_data.mountpoint == "/boot" and "mdarray" in storage.bootloader.stage2_device_types:
                ty = storage.default_boot_fstype
            else:
                ty = storage.default_fstype

        # Sanity check mountpoint
        if raid_data.mountpoint != "" and raid_data.mountpoint[0] != '/':
            raise KickstartParseError(
                _("The mount point \"%s\" is not valid.  It must start with a /.")
                % raid_data.mountpoint, lineno=raid_data.lineno
            )

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not raid_data.format:
            if not devicename:
                raise KickstartParseError(
                    _("raid --noformat must also use the --device option."),
                    lineno=raid_data.lineno
                )

            dev = devicetree.get_device_by_name(devicename)
            if not dev:
                raise KickstartParseError(
                    _("RAID device  \"%s\" given in raid command does not exist.") % devicename,
                    lineno=raid_data.lineno
                )

            dev.format.mountpoint = raid_data.mountpoint
            dev.format.mountopts = raid_data.fsopts
            if ty == "swap":
                storage.add_fstab_swap(dev)
            return

        # Get a list of all the RAID members.
        for member in raid_data.members:
            dev = devicetree.resolve_device(member)
            if not dev:
                # if member is using --onpart, use original device
                mem = data.onPart.get(member, member)
                dev = devicetree.resolve_device(mem) or lookupAlias(devicetree, member)
            if dev and dev.format.type == "luks":
                try:
                    dev = dev.children[0]
                except IndexError:
                    dev = None

            if dev and dev.format.type != "mdmember":
                raise KickstartParseError(
                    _("RAID device \"%(device)s\" has a format of \"%(format)s\", but should have "
                      "a format of \"mdmember\".") % {"device": member, "format": dev.format.type},
                    lineno=raid_data.lineno
                )

            if not dev:
                raise KickstartParseError(
                    _("Tried to use undefined partition \"%s\" in RAID specification.") % member,
                    lineno=raid_data.lineno
                )

            raidmems.append(dev)

        # Now get a format to hold a lot of these extra values.
        kwargs["fmt"] = get_format(
            ty,
            label=raid_data.label,
            fsprofile=raid_data.fsprofile,
            mountpoint=raid_data.mountpoint,
            mountopts=raid_data.fsopts,
            create_options=raid_data.mkfsopts
        )

        if not kwargs["fmt"].type:
            raise KickstartParseError(
                _("The \"%s\" file system type is not supported.") % ty,
                lineno=raid_data.lineno
            )

        kwargs["name"] = devicename
        kwargs["level"] = raid_data.level
        kwargs["parents"] = raidmems
        kwargs["member_devices"] = len(raidmems) - raid_data.spares
        kwargs["total_devices"] = len(raidmems)

        if raid_data.chunk_size:
            kwargs["chunk_size"] = Size("%d KiB" % raid_data.chunk_size)

        add_fstab_swap = None

        # If we were given a pre-existing RAID to create a filesystem on,
        # we need to verify it exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing RAIDs.
        if raid_data.preexist:
            device = devicetree.get_device_by_name(devicename)
            if not device:
                raise KickstartParseError(
                    _("RAID volume \"%s\" specified with --useexisting does not exist.")
                    % devicename, lineno=raid_data.lineno
                )

            storage.devicetree.recursive_remove(device, remove_device=False)
            devicetree.actions.add(ActionCreateFormat(device, kwargs["fmt"]))
            if ty == "swap":
                add_fstab_swap = device
        else:
            if devicename and devicename in (a.name for a in storage.mdarrays):
                raise KickstartParseError(
                    _("The RAID volume name \"%s\" is already in use.") % devicename,
                    lineno=raid_data.lineno
                )

            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if raid_data.mountpoint:
                    device = storage.mountpoints[raid_data.mountpoint]
                    storage.destroy_device(device)
            except KeyError:
                pass

            try:
                request = storage.new_mdarray(**kwargs)
            except (StorageError, ValueError) as e:
                raise KickstartParseError(str(e), lineno=raid_data.lineno)

            storage.create_device(request)
            if ty == "swap":
                add_fstab_swap = request

        if raid_data.encrypted:
            if raid_data.passphrase and not storage.encryption_passphrase:
                storage.encryption_passphrase = raid_data.passphrase

            cert = getEscrowCertificate(storage.escrow_certificates, raid_data.escrowcert)

            # Get the version of LUKS and PBKDF arguments.
            raid_data.luks_version = raid_data.luks_version or storage.default_luks_version

            pbkdf_args = get_pbkdf_args(
                luks_version=raid_data.luks_version,
                pbkdf_type=raid_data.pbkdf,
                max_memory_kb=raid_data.pbkdf_memory,
                iterations=raid_data.pbkdf_iterations,
                time_ms=raid_data.pbkdf_time
            )

            if pbkdf_args and not luks_data.pbkdf_args:
                luks_data.pbkdf_args = pbkdf_args

            if raid_data.preexist:
                luksformat = kwargs["fmt"]
                device.format = get_format(
                    "luks",
                    passphrase=raid_data.passphrase,
                    device=device.path,
                    cipher=raid_data.cipher,
                    escrow_cert=cert,
                    add_backup_passphrase=raid_data.backuppassphrase,
                    luks_version=raid_data.luks_version,
                    pbkdf_args=pbkdf_args
                )
                luksdev = LUKSDevice(
                    "luks%d" % storage.next_id,
                    fmt=luksformat,
                    parents=device
                )
            else:
                luksformat = request.format
                request.format = get_format(
                    "luks",
                    passphrase=raid_data.passphrase,
                    cipher=raid_data.cipher,
                    escrow_cert=cert,
                    add_backup_passphrase=raid_data.backuppassphrase,
                    luks_version=raid_data.luks_version,
                    pbkdf_args=pbkdf_args
                )
                luksdev = LUKSDevice(
                    "luks%d" % storage.next_id,
                    fmt=luksformat,
                    parents=request
                )

            if ty == "swap":
                # swap is on the LUKS device instead of the parent device,
                # override the device here
                add_fstab_swap = luksdev

            storage.create_device(luksdev)

        if add_fstab_swap:
            storage.add_fstab_swap(add_fstab_swap)
