#
# Copyright (C) 2009-2017  Red Hat, Inc.
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#

"""This module provides storage functions related to OS installation."""

import os
import parted

from blivet.blivet import Blivet
from blivet.storage_log import log_exception_info
from blivet.devices import PartitionDevice, BTRFSSubVolumeDevice
from blivet.formats import get_format
from blivet.size import Size
from blivet.devicelibs.crypto import DEFAULT_LUKS_VERSION

from pyanaconda.core import util
from pyanaconda.bootloader import get_bootloader
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import shortProductName, CLEAR_PARTITIONS_NONE, \
    CLEAR_PARTITIONS_LINUX, CLEAR_PARTITIONS_ALL, CLEAR_PARTITIONS_LIST, CLEAR_PARTITIONS_DEFAULT, \
    DEFAULT_AUTOPART_TYPE
from pyanaconda.bootloader.execution import BootloaderExecutor
from pyanaconda.platform import platform as _platform
from pyanaconda.storage.fsset import FSSet
from pyanaconda.storage.partitioning import get_full_partitioning_requests, \
    get_default_partitioning
from pyanaconda.storage.utils import download_escrow_certificate, find_live_backing_device
from pyanaconda.storage.root import find_existing_installations
from pyanaconda.modules.common.constants.services import NETWORK

import logging
log = logging.getLogger("anaconda.storage")


class StorageDiscoveryConfig(object):

    """ Class to encapsulate various detection/initialization parameters. """

    def __init__(self):

        # storage configuration variables
        self.clear_part_type = CLEAR_PARTITIONS_DEFAULT
        self.clear_part_disks = []
        self.clear_part_devices = []
        self.initialize_disks = False
        self.protected_dev_specs = []
        self.zero_mbr = False

        # Whether clear_partitions removes scheduled/non-existent devices and
        # disklabels depends on this flag.
        self.clear_non_existent = False


class InstallerStorage(Blivet):
    """ Top-level class for managing installer-related storage configuration. """

    def __init__(self):
        super().__init__()
        self.do_autopart = False
        self.encrypted_autopart = False
        self.encryption_cipher = None
        self._escrow_certificates = {}

        self.autopart_escrow_cert = None
        self.autopart_add_backup_passphrase = False

        self._default_boot_fstype = None

        self._bootloader = None
        self.config = StorageDiscoveryConfig()
        self.autopart_type = DEFAULT_AUTOPART_TYPE

        self.__luks_devs = {}
        self.fsset = FSSet(self.devicetree)
        self._free_space_snapshot = None

        self._short_product_name = shortProductName
        self._default_luks_version = DEFAULT_LUKS_VERSION

        self._autopart_luks_version = None
        self.autopart_pbkdf_args = None

    def do_it(self, callbacks=None):
        """
        Commit queued changes to disk.

        :param callbacks: callbacks to be invoked when actions are executed
        :type callbacks: return value of the :func:`blivet.callbacks.create_new_callbacks_

        """
        super().do_it(callbacks=callbacks)

        # now set the boot partition's flag
        if self.bootloader and not self.bootloader.skip_bootloader:
            if self.bootloader.stage2_bootable:
                boot = self.boot_device
            else:
                boot = self.bootloader_device

            if boot.type == "mdarray":
                boot_devs = boot.parents
            else:
                boot_devs = [boot]

            for dev in boot_devs:
                if not hasattr(dev, "bootable"):
                    log.info("Skipping %s, not bootable", dev)
                    continue

                # Dos labels can only have one partition marked as active
                # and unmarking ie the windows partition is not a good idea
                skip = False
                if dev.disk.format.parted_disk.type == "msdos":
                    for p in dev.disk.format.parted_disk.partitions:
                        if p.type == parted.PARTITION_NORMAL and \
                           p.getFlag(parted.PARTITION_BOOT):
                            skip = True
                            break

                # GPT labeled disks should only have bootable set on the
                # EFI system partition (parted sets the EFI System GUID on
                # GPT partitions with the boot flag)
                if dev.disk.format.label_type == "gpt" and \
                   dev.format.type not in ["efi", "macefi"]:
                    skip = True

                if skip:
                    log.info("Skipping %s", dev.name)
                    continue

                # hfs+ partitions on gpt can't be marked bootable via parted
                if dev.disk.format.parted_disk.type != "gpt" or \
                        dev.format.type not in ["hfs+", "macefi"]:
                    log.info("setting boot flag on %s", dev.name)
                    dev.bootable = True

                # Set the boot partition's name on disk labels that support it
                if dev.parted_partition.disk.supportsFeature(parted.DISK_TYPE_PARTITION_NAME):
                    ped_partition = dev.parted_partition.getPedPartition()
                    ped_partition.set_name(dev.format.name)
                    log.info("Setting label on %s to '%s'", dev, dev.format.name)

                dev.disk.setup()
                dev.disk.format.commit_to_disk()

        self.dump_state("final")

    @property
    def bootloader(self):
        if self._bootloader is None:
            self._bootloader = get_bootloader()

        return self._bootloader

    def update_bootloader_disk_list(self):
        if not self.bootloader:
            return

        boot_disks = [d for d in self.disks if d.partitioned]
        boot_disks.sort(key=self.compare_disks_key)
        self.bootloader.set_disk_list(boot_disks)

    @property
    def boot_device(self):
        dev = None
        root_device = self.mountpoints.get("/")

        dev = self.mountpoints.get("/boot", root_device)
        return dev

    @property
    def default_boot_fstype(self):
        """The default filesystem type for the boot partition."""
        if self._default_boot_fstype:
            return self._default_boot_fstype

        fstype = None
        if self.bootloader:
            fstype = self.boot_fstypes[0]
        return fstype

    def set_default_boot_fstype(self, newtype):
        """ Set the default /boot fstype for this instance.

            Raise ValueError on invalid input.
        """
        log.debug("trying to set new default /boot fstype to '%s'", newtype)
        # This will raise ValueError if it isn't valid
        self._check_valid_fstype(newtype)
        self._default_boot_fstype = newtype

    @property
    def default_luks_version(self):
        """The default LUKS version."""
        return self._default_luks_version

    def set_default_luks_version(self, version):
        """Set the default LUKS version.

        :param version: a string with LUKS version
        :raises: ValueError on invalid input
        """
        log.debug("trying to set new default luks version to '%s'", version)
        self._check_valid_luks_version(version)
        self._default_luks_version = version

    @property
    def autopart_luks_version(self):
        """The autopart LUKS version."""
        return self._autopart_luks_version or self._default_luks_version

    @autopart_luks_version.setter
    def autopart_luks_version(self, version):
        """Set the autopart LUKS version.

        :param version: a string with LUKS version
        :raises: ValueError on invalid input
        """
        self._check_valid_luks_version(version)
        self._autopart_luks_version = version

    def _check_valid_luks_version(self, version):
        get_format("luks", luks_version=version)

    @property
    def autopart_requests(self):
        """The default partitioning requests.

        :return: a list of full partitioning specs
        """
        return get_full_partitioning_requests(self, _platform, get_default_partitioning())

    def set_up_bootloader(self, early=False):
        """ Set up the boot loader.

            :keyword bool early: Set to True to skip stage1_device setup

            :raises BootloaderError: if stage1 setup fails

            If this needs to be run early, eg. to setup stage1_disk but
            not stage1_device 'early' should be set True to prevent
            it from raising BootloaderError
        """
        if not self.bootloader:
            log.warning("bootloader data missing")
            return

        if self.bootloader.skip_bootloader:
            log.info("user specified that bootloader install be skipped")
            return

        # Need to make sure that boot drive has been setup from the latest information.
        # This will also set self.bootloader.stage1_disk.
        BootloaderExecutor().execute(self, dry_run=False)

        self.bootloader.stage2_device = self.boot_device
        if not early:
            self.bootloader.set_stage1_device(self.devices)

    @property
    def bootloader_device(self):
        return getattr(self.bootloader, "stage1_device", None)

    @property
    def boot_fstypes(self):
        """A list of all valid filesystem types for the boot partition."""
        fstypes = []
        if self.bootloader:
            fstypes = self.bootloader.stage2_format_types
        return fstypes

    def get_fstype(self, mountpoint=None):
        """ Return the default filesystem type based on mountpoint. """
        fstype = super().get_fstype(mountpoint=mountpoint)

        if mountpoint == "/boot":
            fstype = self.default_boot_fstype

        return fstype

    def get_escrow_certificate(self, url):
        """Get the escrow certificate.

        :param url: an URL of the certificate
        :return: a content of the certificate
        """
        if not url:
            return None

        certificate = self._escrow_certificates.get(url, None)

        if not certificate:
            certificate = download_escrow_certificate(url)
            self._escrow_certificates[url] = certificate

        return certificate

    @property
    def mountpoints(self):
        return self.fsset.mountpoints

    @property
    def root_device(self):
        return self.fsset.root_device

    @property
    def file_system_free_space(self):
        """ Combined free space in / and /usr as :class:`blivet.size.Size`. """
        mountpoints = ["/", "/usr"]
        free = Size(0)
        btrfs_volumes = []
        for mountpoint in mountpoints:
            device = self.mountpoints.get(mountpoint)
            if not device:
                continue

            # don't count the size of btrfs volumes repeatedly when multiple
            # subvolumes are present
            if isinstance(device, BTRFSSubVolumeDevice):
                if device.volume in btrfs_volumes:
                    continue
                else:
                    btrfs_volumes.append(device.volume)

            if device.format.exists:
                free += device.format.free
            else:
                free += device.format.free_space_estimate(device.size)

        return free

    def get_disk_free_space(self, disks=None):
        """Get total free space on the given disks.

        :param disks: a list of disks or None
        :return: a total size
        """
        # Use all disks in the device tree by default.
        if disks is None:
            disks = self.disks

        # Get the dictionary of free spaces for each disk.
        snapshot = super().get_free_space(disks)

        # Calculate the total free space.
        return sum((disk_free for disk_free, fs_free in snapshot.values()), Size(0))

    @property
    def free_space_snapshot(self):
        # if no snapshot is available, do it now and return it
        self._free_space_snapshot = self._free_space_snapshot or self.get_free_space()

        return self._free_space_snapshot

    def create_free_space_snapshot(self):
        self._free_space_snapshot = self.get_free_space()

        return self._free_space_snapshot

    def get_free_space(self, disks=None, clear_part_type=None):  # pylint: disable=arguments-differ
        """ Return a dict with free space info for each disk.

             The dict values are 2-tuples: (disk_free, fs_free). fs_free is
             space available by shrinking filesystems. disk_free is space not
             allocated to any partition.

             disks and clear_part_type allow specifying a set of disks other than
             self.disks and a clear_part_type value other than
             self.config.clear_part_type.

             :keyword disks: overrides :attr:`disks`
             :type disks: list
             :keyword clear_part_type: overrides :attr:`self.config.clear_part_type`
             :type clear_part_type: int
             :returns: dict with disk name keys and tuple (disk, fs) free values
             :rtype: dict

            .. note::

                The free space values are :class:`blivet.size.Size` instances.

        """

        # FIXME: we should definitely do something with this method -- it takes
        # different parameters than get_free_space from Blivet and does
        # different things too

        if disks is None:
            disks = self.disks

        if clear_part_type is None:
            clear_part_type = self.config.clear_part_type

        free = {}
        for disk in disks:
            should_clear = self.should_clear(disk, clear_part_type=clear_part_type,
                                             clear_part_disks=[disk.name])
            if should_clear:
                free[disk.name] = (disk.size, Size(0))
                continue

            disk_free = Size(0)
            fs_free = Size(0)
            if disk.partitioned:
                disk_free = disk.format.free
                for partition in (p for p in self.partitions if p.disk == disk):
                    # only check actual filesystems since lvm &c require a bunch of
                    # operations to translate free filesystem space into free disk
                    # space
                    should_clear = self.should_clear(partition,
                                                     clear_part_type=clear_part_type,
                                                     clear_part_disks=[disk.name])
                    if should_clear:
                        disk_free += partition.size
                    elif hasattr(partition.format, "free"):
                        fs_free += partition.format.free
            elif hasattr(disk.format, "free"):
                fs_free = disk.format.free
            elif disk.format.type is None:
                disk_free = disk.size

            free[disk.name] = (disk_free, fs_free)

        return free

    def shutdown(self):
        """ Deactivate all devices. """
        try:
            self.devicetree.teardown_all()
        except Exception:  # pylint: disable=broad-except
            log_exception_info(log.error, "failure tearing down device tree")

    def reset(self, cleanup_only=False):
        """ Reset storage configuration to reflect actual system state.

            This will cancel any queued actions and rescan from scratch but not
            clobber user-obtained information like passphrases, iscsi config, &c

            :keyword cleanup_only: prepare the tree only to deactivate devices
            :type cleanup_only: bool

            See :meth:`devicetree.Devicetree.populate` for more information
            about the cleanup_only keyword argument.
        """
        # save passphrases for luks devices so we don't have to reprompt
        self.encryption_passphrase = None
        for device in self.devices:
            if device.format.type == "luks" and device.format.exists:
                self.save_passphrase(device)

        super().reset(cleanup_only=cleanup_only)

        self.fsset = FSSet(self.devicetree)

        if self.bootloader:
            # clear out bootloader attributes that refer to devices that are
            # no longer in the tree
            self.bootloader.reset()

        self.update_bootloader_disk_list()
        self._mark_protected_devices()

        self.roots = []
        self.roots = find_existing_installations(self.devicetree)
        self.dump_state("initial")

    def _mark_protected_devices(self):
        """Mark protected devices.

        If a device is protected, mark it as such now. Once the tree
        has been populated, devices' protected attribute is how we will
        identify protected devices.
        """
        protected = []

        # Resolve the protected device specs to devices.
        for spec in self.config.protected_dev_specs:
            dev = self.devicetree.resolve_device(spec)

            if dev is not None:
                log.debug("Protected device spec %s resolved to %s.", spec, dev.name)
                protected.append(dev)

        # Find the live backing device and its parents.
        live_device_name = find_live_backing_device()

        if live_device_name:
            log.debug("Resolved live device to %s.", live_device_name)
            dev = self.devicetree.get_device_by_name(live_device_name, hidden=True)
            protected.append(dev)
            protected.extend(dev.parents)

        # Mark the collected devices as protected.
        for dev in protected:
            log.debug("Marking device %s as protected.", dev.name)
            dev.protected = True

    def empty_device(self, device):
        empty = True
        if device.partitioned:
            partitions = device.children
            empty = all([p.is_magic for p in partitions])
        else:
            empty = (device.format.type is None)

        return empty

    @property
    def unused_devices(self):
        used_devices = []
        for root in self.roots:
            for device in list(root.mounts.values()) + root.swaps:
                if device not in self.devices:
                    continue

                used_devices.extend(device.ancestors)

        for new in [d for d in self.devicetree.leaves if not d.format.exists]:
            if new.format.mountable and not new.format.mountpoint:
                continue

            used_devices.extend(new.ancestors)

        for device in self.partitions:
            if getattr(device, "is_logical", False):
                extended = device.disk.format.extended_partition.path
                used_devices.append(self.devicetree.get_device_by_path(extended))

        used = set(used_devices)
        _all = set(self.devices)
        return list(_all.difference(used))

    def should_clear(self, device, **kwargs):
        """ Return True if a clearpart settings say a device should be cleared.

            :param device: the device (required)
            :type device: :class:`blivet.devices.StorageDevice`
            :keyword clear_part_type: overrides :attr:`self.config.clear_part_type`
            :type clear_part_type: int
            :keyword clear_part_disks: overrides
                                     :attr:`self.config.clear_part_disks`
            :type clear_part_disks: list
            :keyword clear_part_devices: overrides
                                       :attr:`self.config.clear_part_devices`
            :type clear_part_devices: list
            :returns: whether or not clear_partitions should remove this device
            :rtype: bool
        """
        clear_part_type = kwargs.get("clear_part_type", self.config.clear_part_type)
        clear_part_disks = kwargs.get("clear_part_disks",
                                      self.config.clear_part_disks)
        clear_part_devices = kwargs.get("clear_part_devices",
                                        self.config.clear_part_devices)

        for disk in device.disks:
            # this will not include disks with hidden formats like multipath
            # and firmware raid member disks
            if clear_part_disks and disk.name not in clear_part_disks:
                return False

        if not self.config.clear_non_existent:
            if (device.is_disk and not device.format.exists) or \
               (not device.is_disk and not device.exists):
                return False

        # the only devices we want to clear when clear_part_type is
        # CLEAR_PARTITIONS_NONE are uninitialized disks, or disks with no
        # partitions, in clear_part_disks, and then only when we have been asked
        # to initialize disks as needed
        if clear_part_type in [CLEAR_PARTITIONS_NONE, CLEAR_PARTITIONS_DEFAULT]:
            if not self.config.initialize_disks or not device.is_disk:
                return False

            if not self.empty_device(device):
                return False

        if isinstance(device, PartitionDevice):
            # Never clear the special first partition on a Mac disk label, as
            # that holds the partition table itself.
            # Something similar for the third partition on a Sun disklabel.
            if device.is_magic:
                return False

            # We don't want to fool with extended partitions, freespace, &c
            if not device.is_primary and not device.is_logical:
                return False

            if clear_part_type == CLEAR_PARTITIONS_LINUX and \
               not device.format.linux_native and \
               not device.get_flag(parted.PARTITION_LVM) and \
               not device.get_flag(parted.PARTITION_RAID) and \
               not device.get_flag(parted.PARTITION_SWAP):
                return False
        elif device.is_disk:
            if device.partitioned and clear_part_type != CLEAR_PARTITIONS_ALL:
                # if clear_part_type is not CLEAR_PARTITIONS_ALL but we'll still be
                # removing every partition from the disk, return True since we
                # will want to be able to create a new disklabel on this disk
                if not self.empty_device(device):
                    return False

            # Never clear disks with hidden formats
            if device.format.hidden:
                return False

            # When clear_part_type is CLEAR_PARTITIONS_LINUX and a disk has non-
            # linux whole-disk formatting, do not clear it. The exception is
            # the case of an uninitialized disk when we've been asked to
            # initialize disks as needed
            if (clear_part_type == CLEAR_PARTITIONS_LINUX and
                not ((self.config.initialize_disks and
                      self.empty_device(device)) or
                     (not device.partitioned and device.format.linux_native))):
                return False

        # Don't clear devices holding install media.
        descendants = self.devicetree.get_dependent_devices(device)
        if device.protected or any(d.protected for d in descendants):
            return False

        if clear_part_type == CLEAR_PARTITIONS_LIST and \
           device.name not in clear_part_devices:
            return False

        return True

    def clear_partitions(self):
        """ Clear partitions and dependent devices from disks.

            This is also where zerombr is handled.
        """
        # Sort partitions by descending partition number to minimize confusing
        # things like multiple "destroy sda5" actions due to parted renumbering
        # partitions. This can still happen through the UI but it makes sense to
        # avoid it where possible.
        partitions = sorted(self.partitions,
                            key=lambda p: getattr(p.parted_partition, "number", 1),
                            reverse=True)
        for part in partitions:
            log.debug("clearpart: looking at %s", part.name)
            if not self.should_clear(part):
                continue

            self.recursive_remove(part)
            log.debug("partitions: %s", [p.name for p in part.disk.children])

        # now remove any empty extended partitions
        self.remove_empty_extended_partitions()

        # ensure all disks have appropriate disklabels
        for disk in self.disks:
            zerombr = (self.config.zero_mbr and disk.format.type is None)
            should_clear = self.should_clear(disk)
            if should_clear:
                self.recursive_remove(disk)

            if zerombr or should_clear:
                if disk.protected:
                    log.warning("cannot clear '%s': disk is protected or read only", disk.name)
                else:
                    log.debug("clearpart: initializing %s", disk.name)
                    self.initialize_disk(disk)

        self.update_bootloader_disk_list()

    def _get_hostname(self):
        """Return a hostname."""
        ignored_hostnames = {None, "", 'localhost', 'localhost.localdomain'}

        network_proxy = NETWORK.get_proxy()
        hostname = network_proxy.Hostname

        if hostname in ignored_hostnames:
            hostname = network_proxy.GetCurrentHostname()

        if hostname in ignored_hostnames:
            hostname = None

        return hostname

    def _get_container_name_template(self, prefix=None):
        """Return a template for suggest_container_name method."""
        prefix = prefix or ""  # make sure prefix is a string instead of None

        # try to create a device name incorporating the hostname
        hostname = self._get_hostname()

        if hostname:
            template = "%s_%s" % (prefix, hostname.split('.')[0].lower())
            template = self.safe_device_name(template)
        else:
            template = prefix

        if conf.target.is_image:
            template = "%s_image" % template

        return template

    def turn_on_swap(self):
        self.fsset.turn_on_swap(root_path=util.getSysroot())

    def mount_filesystems(self, read_only=None, skip_root=False):
        self.fsset.mount_filesystems(root_path=util.getSysroot(),
                                     read_only=read_only, skip_root=skip_root)

    def umount_filesystems(self, swapoff=True):
        self.fsset.umount_filesystems(swapoff=swapoff)

    def parse_fstab(self, chroot=None):
        self.fsset.parse_fstab(chroot=chroot)

    def mk_dev_root(self):
        self.fsset.mk_dev_root()

    def create_swap_file(self, device, size):
        self.fsset.create_swap_file(device, size)

    def make_mtab(self):
        path = "/etc/mtab"
        target = "/proc/self/mounts"
        path = os.path.normpath("%s/%s" % (util.getSysroot(), path))

        if os.path.islink(path):
            # return early if the mtab symlink is already how we like it
            current_target = os.path.normpath(os.path.dirname(path) +
                                              "/" + os.readlink(path))
            if current_target == target:
                return

        if os.path.exists(path):
            os.unlink(path)

        os.symlink(target, path)

    def add_fstab_swap(self, device):
        """
        Add swap device to the list of swaps that should appear in the fstab.

        :param device: swap device that should be added to the list
        :type device: blivet.devices.StorageDevice instance holding a swap format

        """

        self.fsset.add_fstab_swap(device)

    def remove_fstab_swap(self, device):
        """
        Remove swap device from the list of swaps that should appear in the fstab.

        :param device: swap device that should be removed from the list
        :type device: blivet.devices.StorageDevice instance holding a swap format

        """

        self.fsset.remove_fstab_swap(device)

    def set_fstab_swaps(self, devices):
        """
        Set swap devices that should appear in the fstab.

        :param devices: iterable providing devices that should appear in the fstab
        :type devices: iterable providing blivet.devices.StorageDevice instances holding
                       a swap format

        """

        self.fsset.set_fstab_swaps(devices)
