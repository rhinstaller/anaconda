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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import blivet
from blivet.deviceaction import (
    ActionCreateFormat,
    ActionResizeDevice,
    ActionResizeFormat,
)
from blivet.devicelibs.lvm import KNOWN_THPOOL_PROFILES, LVM_PE_SIZE
from blivet.devices import LUKSDevice, LVMVolumeGroupDevice
from blivet.devices.lvm import LVMCacheRequest
from blivet.errors import StorageError
from blivet.formats import get_format
from blivet.partitioning import do_partitioning, grow_lvm
from blivet.size import Size
from blivet.static_data import luks_data
from bytesize.bytesize import KiB
from pykickstart.base import DeprecatedCommand
from pykickstart.constants import AUTOPART_TYPE_PLAIN

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.storage import suggest_swap_size
from pyanaconda.modules.storage.partitioning.automatic.noninteractive_partitioning import (
    NonInteractivePartitioningTask,
)
from pyanaconda.modules.storage.partitioning.automatic.utils import (
    get_candidate_disks,
    get_pbkdf_args,
    lookup_alias,
    schedule_partitions,
)
from pyanaconda.modules.storage.platform import platform

log = get_module_logger(__name__)

__all__ = ["CustomPartitioningTask"]


class CustomPartitioningTask(NonInteractivePartitioningTask):
    """A task for the custom partitioning configuration."""

    def __init__(self, storage, data):
        """Create a task.

        :param data: an instance of kickstart data
        """
        super().__init__(storage)
        self._data = data
        self._disk_free_space = Size(0)
        self._default_passphrase = None

    def _get_passphrase(self, data):
        """Get a passphrase for the given data object.

        Use a passphrase from the data object, if the passphrase
        is specified. Otherwise, use the default passphrase if
        available.

        If the default passphrase is not set, set it to the
        data passphrase.

        :param data: a kickstart data object
        :return: a string with the passphrase
        """
        if data.passphrase and not self._default_passphrase:
            self._default_passphrase = data.passphrase

        return data.passphrase or self._default_passphrase

    def _configure_partitioning(self, storage):
        """Configure the partitioning.

        :param storage: an instance of Blivet
        """
        log.debug("Executing the custom partitioning.")
        data = self._data

        # Get the available disk space.
        self._disk_free_space = storage.get_disk_free_space()

        # Start the partitioning.
        self._execute_reqpart(storage, data)
        self._execute_partition(storage, data)
        self._execute_raid(storage, data)
        self._execute_volgroup(storage, data)
        self._execute_logvol(storage, data)
        self._execute_btrfs(storage, data)

    def _execute_reqpart(self, storage, data):
        """Execute the reqpart command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        if not data.reqpart.reqpart:
            return

        log.debug("Looking for platform-specific requirements.")
        requests = list(platform.partitions)

        for request in requests[:]:
            if request.mountpoint != "/boot":
                continue

            if not data.reqpart.addBoot:
                log.debug("Removing the requirement for /boot.")
                requests.remove(request)
                continue

            # Blivet doesn't know this - anaconda sets up the default boot fstype
            # in various places in this file. We need to duplicate that here.
            request.fstype = storage.default_boot_fstype

        if not requests:
            return

        disks = get_candidate_disks(storage)

        log.debug("Applying requirements:\n%s", "".join(map(str, requests)))
        schedule_partitions(storage, disks, [], scheme=AUTOPART_TYPE_PLAIN, requests=requests)

    def _execute_partition(self, storage, data):
        """Execute the partition command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        for partition_data in data.partition.partitions:
            self._execute_partition_data(storage, data, partition_data)

        if data.partition.partitions:
            do_partitioning(storage, boot_disk=storage.bootloader.stage1_disk)

    def _execute_partition_data(self, storage, data, partition_data):
        """Execute the partition data.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        :param partition_data: an instance of PartData
        """
        devicetree = storage.devicetree
        kwargs = {}

        if partition_data.onbiosdisk != "":
            # edd_dict is only modified during storage.reset(), so don't do that
            # while executing storage.
            for (disk, biosdisk) in storage.edd_dict.items():
                if "%x" % biosdisk == partition_data.onbiosdisk:
                    partition_data.disk = disk
                    break

            if not partition_data.disk:
                raise StorageError(
                    _("No disk found for specified BIOS disk \"{}\".").format(
                        partition_data.onbiosdisk
                    )
                )

        size = None

        if partition_data.mountpoint == "swap":
            ty = "swap"
            partition_data.mountpoint = ""
            if partition_data.recommended or partition_data.hibernation:
                disk_space = self._disk_free_space
                size = suggest_swap_size(
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
                raise StorageError(
                    _("RAID partition \"{}\" is defined multiple times.").format(kwargs["name"])
                )

            if partition_data.onPart:
                data.onPart[kwargs["name"]] = partition_data.onPart
        elif partition_data.mountpoint.startswith("pv."):
            ty = "lvmpv"
            kwargs["name"] = partition_data.mountpoint
            partition_data.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise StorageError(
                    _("PV partition \"{}\" is defined multiple times.").format(kwargs["name"])
                )

            if partition_data.onPart:
                data.onPart[kwargs["name"]] = partition_data.onPart
        elif partition_data.mountpoint.startswith("btrfs."):
            ty = "btrfs"
            kwargs["name"] = partition_data.mountpoint
            partition_data.mountpoint = ""

            if devicetree.get_device_by_name(kwargs["name"]):
                raise StorageError(
                    _("Btrfs partition \"{}\" is defined multiple times.").format(kwargs["name"])
                )

            if partition_data.onPart:
                data.onPart[kwargs["name"]] = partition_data.onPart
        elif partition_data.mountpoint == "/boot/efi":
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
            size = self._get_size(partition_data.size, "MiB")

        # If this specified an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not partition_data.format:
            if not partition_data.onPart:
                raise StorageError(_("part --noformat must also use the --onpart option."))

            dev = devicetree.resolve_device(partition_data.onPart)
            if not dev:
                raise StorageError(
                    _("Partition \"{}\" given in part command does "
                      "not exist.").format(partition_data.onPart)
                )

            if partition_data.resize:
                size = dev.raw_device.align_target_size(size)
                if size < dev.currentSize:
                    # shrink
                    try:
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                    except ValueError as e:
                        self._handle_invalid_target_size(e, partition_data.size, dev.name)
                else:
                    # grow
                    try:
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                    except ValueError as e:
                        self._handle_invalid_target_size(e, partition_data.size, dev.name)

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
            raise StorageError(
                _("The \"{}\" file system type is not supported.").format(ty)
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
                raise StorageError(
                    _("Disk \"{}\" given in part command does "
                      "not exist.").format(partition_data.disk)
                )
            if not disk.partitionable:
                raise StorageError(
                    _("Cannot install to unpartitionable device "
                      "\"{}\".").format(partition_data.disk)
                )

            if disk and disk.partitioned:
                kwargs["parents"] = [disk]
            elif disk:
                raise StorageError(
                    _("Disk \"{}\" in part command is not "
                      "partitioned.").format(partition_data.disk)
                )

            if not kwargs["parents"]:
                raise StorageError(
                    _("Disk \"{}\" given in part command does "
                      "not exist.").format(partition_data.disk)
                )

        kwargs["grow"] = partition_data.grow
        kwargs["size"] = size

        if partition_data.maxSizeMB:
            maxsize = self._get_size(partition_data.maxSizeMB, "MiB")
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
                raise StorageError(
                    _("Partition \"{}\" given in part command does "
                      "not exist.").format(partition_data.onPart)
                )

            storage.devicetree.recursive_remove(device, remove_device=False)
            if partition_data.resize:
                size = device.raw_device.align_target_size(size)
                try:
                    devicetree.actions.add(ActionResizeDevice(device, size))
                except ValueError as e:
                    self._handle_invalid_target_size(e, partition_data.size, device.name)

            devicetree.actions.add(ActionCreateFormat(device, kwargs["fmt"]))
            if ty == "swap":
                add_fstab_swap = device
        # tmpfs mounts are not disks and don't occupy a disk partition,
        # so handle them here
        elif partition_data.fstype == "tmpfs":
            request = storage.new_tmp_fs(**kwargs)
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

            request = storage.new_partition(**kwargs)
            storage.create_device(request)

            if ty == "swap":
                add_fstab_swap = request

        if partition_data.encrypted:
            passphrase = self._get_passphrase(partition_data)
            cert = storage.get_escrow_certificate(partition_data.escrowcert)

            # Get the version of LUKS and PBKDF arguments.
            partition_data.luks_version = (partition_data.luks_version
                                           or storage.default_luks_version)
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
                    passphrase=passphrase,
                    device=device.path,
                    cipher=partition_data.cipher,
                    escrow_cert=cert,
                    add_backup_passphrase=partition_data.backuppassphrase,
                    luks_version=partition_data.luks_version,
                    pbkdf_args=pbkdf_args,
                    opal_admin_passphrase=partition_data.hw_passphrase,
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
                    passphrase=passphrase,
                    cipher=partition_data.cipher,
                    escrow_cert=cert,
                    add_backup_passphrase=partition_data.backuppassphrase,
                    luks_version=partition_data.luks_version,
                    pbkdf_args=pbkdf_args,
                    opal_admin_passphrase=partition_data.hw_passphrase,
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

        if raid_data.mountpoint == "swap":
            ty = "swap"
            raid_data.mountpoint = ""
        elif raid_data.mountpoint.startswith("pv."):
            ty = "lvmpv"
            kwargs["name"] = raid_data.mountpoint
            data.onPart[kwargs["name"]] = devicename

            if devicetree.get_device_by_name(kwargs["name"]):
                raise StorageError(
                    _("PV partition \"{}\" is defined multiple "
                      "times.").format(kwargs["name"])
                )

            raid_data.mountpoint = ""
        elif raid_data.mountpoint.startswith("btrfs."):
            ty = "btrfs"
            kwargs["name"] = raid_data.mountpoint
            data.onPart[kwargs["name"]] = devicename

            if devicetree.get_device_by_name(kwargs["name"]):
                raise StorageError(
                    _("Btrfs partition \"{}\" is defined multiple "
                      "times.").format(kwargs["name"])
                )

            raid_data.mountpoint = ""
        else:
            if raid_data.fstype != "":
                ty = raid_data.fstype
            elif (raid_data.mountpoint == "/boot"
                  and "mdarray" in storage.bootloader.stage2_device_types):
                ty = storage.default_boot_fstype
            else:
                ty = storage.default_fstype

        # Sanity check mountpoint
        self._check_mount_point(raid_data.mountpoint)

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not raid_data.format:
            if not devicename:
                raise StorageError(
                    _("raid --noformat must also use the --device option.")
                )

            dev = devicetree.get_device_by_name(devicename)
            if not dev:
                raise StorageError(
                    _("RAID device  \"{}\" given in raid command does "
                      "not exist.").format(devicename)
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
                dev = devicetree.resolve_device(mem) or lookup_alias(devicetree, member)
            if dev and dev.format.type == "luks":
                try:
                    dev = dev.children[0]
                except IndexError:
                    dev = None

            if dev and dev.format.type != "mdmember":
                raise StorageError(
                    _("RAID device \"{}\" has a format of \"{}\", but should have "
                      "a format of \"mdmember\".").format(member, dev.format.type)
                )

            if not dev:
                raise StorageError(
                    _("Tried to use undefined partition \"{}\" in RAID "
                      "specification.").format(member)
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
            raise StorageError(
                _("The \"{}\" file system type is not supported.").format(ty)
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
                raise StorageError(
                    _("RAID volume \"{}\" specified with --useexisting does "
                      "not exist.").format(devicename)
                )

            storage.devicetree.recursive_remove(device, remove_device=False)
            devicetree.actions.add(ActionCreateFormat(device, kwargs["fmt"]))
            if ty == "swap":
                add_fstab_swap = device
        else:
            if devicename and devicename in (a.name for a in storage.mdarrays):
                raise StorageError(
                    _("The RAID volume name \"{}\" is already in use.").format(devicename)
                )

            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if raid_data.mountpoint:
                    device = storage.mountpoints[raid_data.mountpoint]
                    storage.destroy_device(device)
            except KeyError:
                pass

            request = storage.new_mdarray(**kwargs)
            storage.create_device(request)

            # in case we had to truncate or otherwise adjust the specified name
            data.onPart[devicename] = request.name

            if ty == "swap":
                add_fstab_swap = request

        if raid_data.encrypted:
            passphrase = self._get_passphrase(raid_data)
            cert = storage.get_escrow_certificate(raid_data.escrowcert)

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
                    passphrase=passphrase,
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
                    passphrase=passphrase,
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

    def _execute_volgroup(self, storage, data):
        """Execute the volgroup command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        for volgroup_data in data.volgroup.vgList:
            self._execute_volgroup_data(storage, data, volgroup_data)

    def _execute_volgroup_data(self, storage, data, volgroup_data):
        """Execute the volgroup data.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        :param volgroup_data: an instance of VolGroupData
        """
        pvs = []
        devicetree = storage.devicetree

        # Get a list of all the physical volume devices that make up this VG.
        for pv in volgroup_data.physvols:
            dev = devicetree.resolve_device(pv)
            if not dev:
                # if pv is using --onpart, use original device
                pv_name = data.onPart.get(pv, pv)
                dev = devicetree.resolve_device(pv_name) or lookup_alias(devicetree, pv)
            if dev and dev.format.type == "luks":
                try:
                    dev = dev.children[0]
                except IndexError:
                    dev = None

            if dev and dev.format.type != "lvmpv":
                raise StorageError(
                    _("Physical volume \"{}\" has a format of \"{}\", but should "
                      "have a format of \"lvmpv\".").format(pv, dev.format.type)
                )

            if not dev:
                raise StorageError(
                    _("Tried to use undefined partition \"{}\" in Volume Group "
                      "specification").format(pv)
                )

            pvs.append(dev)

        if len(pvs) == 0 and not volgroup_data.preexist:
            raise StorageError(
                _("Volume group \"{}\" defined without any physical volumes. Either specify "
                  "physical volumes or use --useexisting.").format(volgroup_data.vgname)
            )

        if volgroup_data.pesize == 0:
            # default PE size requested -- we use blivet's default in KiB
            volgroup_data.pesize = LVM_PE_SIZE.convert_to(KiB)

        pesize = Size("%d KiB" % volgroup_data.pesize)
        possible_extents = LVMVolumeGroupDevice.get_supported_pe_sizes()
        if pesize not in possible_extents:
            raise StorageError(
                _("Volume group given physical extent size of \"{}\", but must be one "
                  "of:\n{}.").format(pesize, ", ".join(str(e) for e in possible_extents))
            )

        # If --noformat or --useexisting was given, there's really nothing to do.
        if not volgroup_data.format or volgroup_data.preexist:
            if not volgroup_data.vgname:
                raise StorageError(
                    _("volgroup --noformat and volgroup --useexisting must "
                      "also use the --name= option.")
                )

            dev = devicetree.get_device_by_name(volgroup_data.vgname)
            if not dev:
                raise StorageError(
                    _("Volume group \"{}\" given in volgroup command does "
                      "not exist.").format(volgroup_data.vgname)
                )
        elif volgroup_data.vgname in (vg.name for vg in storage.vgs):
            raise StorageError(
                _("The volume group name \"{}\" is already "
                  "in use.").format(volgroup_data.vgname)
            )
        else:
            request = storage.new_vg(
                parents=pvs,
                name=volgroup_data.vgname,
                pe_size=pesize
            )

            storage.create_device(request)
            if volgroup_data.reserved_space:
                request.reserved_space = Size("{:d} MiB".format(volgroup_data.reserved_space))
            elif volgroup_data.reserved_percent:
                request.reserved_percent = volgroup_data.reserved_percent

            # in case we had to truncate or otherwise adjust the specified name
            data.onPart[volgroup_data.vgname] = request.name

    def _execute_logvol(self, storage, data):
        """Execute the logvol command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        for logvol_data in data.logvol.lvList:
            self._execute_logvol_data(storage, data, logvol_data)

        if data.logvol.lvList:
            grow_lvm(storage)

    def _get_cache_pv_devices(self, devicetree, logvol_data):
        pv_devices = []
        for pvname in logvol_data.cache_pvs:
            pv = lookup_alias(devicetree, pvname)
            if pv.format.type == "luks":
                pv_devices.append(pv.children[0])
            else:
                pv_devices.append(pv)
        return pv_devices

    def _execute_logvol_data(self, storage, data, logvol_data):
        """Execute the logvol data.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        :param logvol_data: an instance of LogVolData
        """
        devicetree = storage.devicetree

        # FIXME: we should be running sanityCheck on partitioning that is not ks
        # autopart, but that's likely too invasive for #873135 at this moment
        if logvol_data.mountpoint == "/boot" and blivet.arch.is_s390():
            raise StorageError(
                _("/boot cannot be of type \"lvmlv\" on s390x")
            )

        # we might have truncated or otherwise changed the specified vg name
        vgname = data.onPart.get(logvol_data.vgname, logvol_data.vgname)

        size = None

        if logvol_data.percent:
            size = Size(0)

        if logvol_data.mountpoint == "swap":
            ty = "swap"
            logvol_data.mountpoint = ""
            if logvol_data.recommended or logvol_data.hibernation:
                disk_space = self._disk_free_space
                size = suggest_swap_size(
                    hibernation=logvol_data.hibernation,
                    disk_space=disk_space
                )
                logvol_data.grow = False
        else:
            if logvol_data.fstype != "":
                ty = logvol_data.fstype
            else:
                ty = storage.default_fstype

        if size is None and not logvol_data.preexist:
            if not logvol_data.size:
                raise StorageError(
                    _("Size cannot be decided on from kickstart nor obtained from device.")
                )

            size = self._get_size(logvol_data.size, "MiB")

        if logvol_data.thin_pool:
            logvol_data.mountpoint = ""
            ty = None

        # Sanity check mountpoint
        self._check_mount_point(logvol_data.mountpoint)

        # Check that the VG this LV is a member of has already been specified.
        vg = devicetree.get_device_by_name(vgname)
        if not vg:
            raise StorageError(
                _("No volume group exists with the name \"{}\". Specify volume "
                  "groups before logical volumes.").format(logvol_data.vgname)
            )

        # If cache PVs specified, check that they belong to the same VG this LV is a member of
        if logvol_data.cache_pvs:
            pv_devices = self._get_cache_pv_devices(devicetree, logvol_data)
            if not all(pv in vg.pvs for pv in pv_devices):
                raise StorageError(
                    _("Cache PVs must belong to the same VG as the cached LV")
                )

        pool = None
        if logvol_data.thin_volume:
            pool = devicetree.get_device_by_name("%s-%s" % (vg.name, logvol_data.pool_name))
            if not pool:
                raise StorageError(
                    _("No thin pool exists with the name \"{}\". Specify thin pools "
                      "before thin volumes.").format(logvol_data.pool_name)
                )

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not logvol_data.format:
            if not logvol_data.name:
                raise StorageError(
                    _("logvol --noformat must also use the --name= option.")
                )

            dev = devicetree.get_device_by_name("%s-%s" % (vg.name, logvol_data.name))
            if not dev:
                raise StorageError(
                    _("Logical volume \"{}\" given in logvol command does "
                      "not exist.").format(logvol_data.name)
                )

            if logvol_data.resize:
                size = dev.raw_device.align_target_size(size)
                if size < dev.currentSize:
                    # shrink
                    try:
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                    except ValueError as e:
                        self._handle_invalid_target_size(e, logvol_data.size, dev.name)
                else:
                    # grow
                    try:
                        devicetree.actions.add(ActionResizeDevice(dev, size))
                        devicetree.actions.add(ActionResizeFormat(dev, size))
                    except ValueError as e:
                        self._handle_invalid_target_size(e, logvol_data.size, dev.name)

            dev.format.mountpoint = logvol_data.mountpoint
            dev.format.mountopts = logvol_data.fsopts
            if ty == "swap":
                storage.add_fstab_swap(dev)
            return

        # Make sure this LV name is not already used in the requested VG.
        if not logvol_data.preexist:
            tmp = devicetree.get_device_by_name("%s-%s" % (vg.name, logvol_data.name))
            if tmp:
                raise StorageError(
                    _("Logical volume name \"{}\" is already in use in volume group "
                      "\"{}\".").format(logvol_data.name, vg.name)
                )

            if not logvol_data.percent and size and not logvol_data.grow and size < vg.pe_size:
                raise StorageError(
                    _("Logical volume size \"{}\" must be larger than the volume "
                      "group extent size of \"{}\".").format(size, vg.pe_size)
                )

        # Now get a format to hold a lot of these extra values.
        fmt = get_format(
            ty,
            mountpoint=logvol_data.mountpoint,
            label=logvol_data.label,
            fsprofile=logvol_data.fsprofile,
            create_options=logvol_data.mkfsopts,
            mountopts=logvol_data.fsopts
        )
        if not fmt.type and not logvol_data.thin_pool:
            raise StorageError(
                _("The \"{}\" file system type is not supported.").format(ty)
            )

        add_fstab_swap = None
        # If we were given a pre-existing LV to create a filesystem on, we need
        # to verify it and its VG exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing LVs.
        if logvol_data.preexist:
            device = devicetree.get_device_by_name("%s-%s" % (vg.name, logvol_data.name))
            if not device:
                raise StorageError(
                    _("Logical volume \"{}\" given in logvol command does "
                      "not exist.").format(logvol_data.name)
                )

            storage.devicetree.recursive_remove(device, remove_device=False)

            if logvol_data.resize:
                size = device.raw_device.align_target_size(size)
                try:
                    devicetree.actions.add(ActionResizeDevice(device, size))
                except ValueError as e:
                    self._handle_invalid_target_size(e, logvol_data.size, device.name)

            devicetree.actions.add(ActionCreateFormat(device, fmt))
            if ty == "swap":
                add_fstab_swap = device
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if logvol_data.mountpoint:
                    device = storage.mountpoints[logvol_data.mountpoint]
                    storage.destroy_device(device)
            except KeyError:
                pass

            if logvol_data.thin_volume:
                parents = [pool]
            else:
                parents = [vg]

            pool_args = {}
            if logvol_data.thin_pool:
                if logvol_data.profile:
                    matching = (p for p in KNOWN_THPOOL_PROFILES if p.name == logvol_data.profile)
                    profile = next(matching, None)
                    if profile:
                        pool_args["profile"] = profile
                    else:
                        log.warning(
                            "No matching profile for %s found in LVM configuration",
                            logvol_data.profile
                        )
                if logvol_data.metadata_size:
                    pool_args["metadata_size"] = Size("%d MiB" % logvol_data.metadata_size)
                if logvol_data.chunk_size:
                    pool_args["chunk_size"] = Size("%d KiB" % logvol_data.chunk_size)

            if logvol_data.maxSizeMB:
                maxsize = self._get_size(logvol_data.maxSizeMB, "MiB")
            else:
                maxsize = None

            if logvol_data.cache_size and logvol_data.cache_pvs:
                pv_devices = self._get_cache_pv_devices(devicetree, logvol_data)
                cache_size = Size("%d MiB" % logvol_data.cache_size)
                cache_mode = logvol_data.cache_mode or None
                cache_request = LVMCacheRequest(cache_size, pv_devices, cache_mode)
            else:
                cache_request = None

            request = storage.new_lv(
                fmt=fmt,
                name=logvol_data.name,
                parents=parents,
                size=size,
                thin_pool=logvol_data.thin_pool,
                thin_volume=logvol_data.thin_volume,
                grow=logvol_data.grow,
                maxsize=maxsize,
                percent=logvol_data.percent,
                cache_request=cache_request,
                **pool_args
            )

            storage.create_device(request)
            if ty == "swap":
                add_fstab_swap = request

        if logvol_data.encrypted:
            passphrase = self._get_passphrase(logvol_data)
            cert = storage.get_escrow_certificate(logvol_data.escrowcert)

            # Get the version of LUKS and PBKDF arguments.
            logvol_data.luks_version = logvol_data.luks_version or storage.default_luks_version

            pbkdf_args = get_pbkdf_args(
                luks_version=logvol_data.luks_version,
                pbkdf_type=logvol_data.pbkdf,
                max_memory_kb=logvol_data.pbkdf_memory,
                iterations=logvol_data.pbkdf_iterations,
                time_ms=logvol_data.pbkdf_time
            )

            if pbkdf_args and not luks_data.pbkdf_args:
                luks_data.pbkdf_args = pbkdf_args

            if logvol_data.preexist:
                luksformat = fmt
                device.format = get_format(
                    "luks",
                    passphrase=passphrase,
                    device=device.path,
                    cipher=logvol_data.cipher,
                    escrow_cert=cert,
                    add_backup_passphrase=logvol_data.backuppassphrase,
                    luks_version=logvol_data.luks_version,
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
                    passphrase=passphrase,
                    cipher=logvol_data.cipher,
                    escrow_cert=cert,
                    add_backup_passphrase=logvol_data.backuppassphrase,
                    luks_version=logvol_data.luks_version,
                    pbkdf_args=pbkdf_args
                )
                luksdev = LUKSDevice(
                    "luks%d" % storage.next_id,
                    fmt=luksformat,
                    parents=request
                )

            if ty == "swap":
                # swap is on the LUKS device not on the LUKS' parent device,
                # override the info here
                add_fstab_swap = luksdev

            storage.create_device(luksdev)

        if add_fstab_swap:
            storage.add_fstab_swap(add_fstab_swap)

    def _execute_btrfs(self, storage, data):
        """Execute the btrfs command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        """
        if isinstance(data.btrfs, DeprecatedCommand):
            log.debug("Skipping the deprecated command 'btrfs'.")
            return

        for btrfs_data in data.btrfs.btrfsList:
            self._execute_btrfs_data(storage, data, btrfs_data)

    def _execute_btrfs_data(self, storage, data, btrfs_data):
        """Execute the btrfs command.

        :param storage: an instance of the Blivet's storage object
        :param data: an instance of kickstart data
        :param btrfs_data: an instance of BTRFSData
        """
        devicetree = storage.devicetree
        members = []

        # Get a list of all the devices that make up this volume.
        for member in btrfs_data.devices:
            dev = devicetree.resolve_device(member)
            if not dev:
                # if using --onpart, use original device
                member_name = data.onPart.get(member, member)
                dev = devicetree.resolve_device(member_name) or lookup_alias(devicetree, member)

            if dev and dev.format.type == "luks":
                try:
                    dev = dev.children[0]
                except IndexError:
                    dev = None

            if dev and dev.format.type != "btrfs":
                raise StorageError(
                    _("Btrfs partition \"{}\" has a format of \"{}\", but should "
                      "have a format of \"btrfs\".").format(member, dev.format.type)
                )

            if not dev:
                raise StorageError(
                    _("Tried to use undefined partition \"{}\" in Btrfs volume "
                      "specification.").format(member)
                )

            members.append(dev)

        if btrfs_data.subvol:
            name = btrfs_data.name
        elif btrfs_data.label:
            name = btrfs_data.label
        else:
            name = None

        if len(members) == 0 and not btrfs_data.preexist:
            raise StorageError(
                _("Btrfs volume defined without any member devices. "
                  "Either specify member devices or use --useexisting.")
            )

        # allow creating btrfs vols/subvols without specifying mountpoint
        if btrfs_data.mountpoint in ("none", "None"):
            btrfs_data.mountpoint = ""

        # Sanity check mountpoint
        self._check_mount_point(btrfs_data.mountpoint)

        # If a previous device has claimed this mount point, delete the
        # old one.
        try:
            if btrfs_data.mountpoint:
                device = storage.mountpoints[btrfs_data.mountpoint]
                storage.destroy_device(device)
        except KeyError:
            pass

        if btrfs_data.preexist:
            device = devicetree.resolve_device(btrfs_data.name)
            if not device:
                raise StorageError(
                    _("Btrfs volume \"{}\" specified with --useexisting "
                      "does not exist.").format(btrfs_data.name)
                )

            device.format.mountpoint = btrfs_data.mountpoint
        else:
            request = storage.new_btrfs(
                name=name,
                subvol=btrfs_data.subvol,
                mountpoint=btrfs_data.mountpoint,
                metadata_level=btrfs_data.metaDataLevel,
                data_level=btrfs_data.dataLevel,
                parents=members,
                create_options=btrfs_data.mkfsopts
            )

            storage.create_device(request)

    def _get_size(self, number, unit):
        """Get a size from the given number and unit."""
        try:
            return Size("{} {}".format(number, unit))
        except ValueError as e:
            raise StorageError(_("The size \"{}\" is invalid.").format(number)) from e

    def _check_mount_point(self, mount_point):
        """Check if the given mount point is valid."""
        if mount_point != "" and mount_point[0] != '/':
            msg = _("The mount point \"{}\" is not valid. It must start with a /.")
            raise StorageError(msg.format(mount_point))

    def _handle_invalid_target_size(self, exception, size, device):
        """Handle an invalid target size."""
        msg = _("Target size \"{size}\" for device \"{device}\" is invalid.")
        raise StorageError(msg.format(size=size, device=device)) from exception
