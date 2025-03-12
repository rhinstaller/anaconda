#
# Installation tasks
#
# Copyright (C) 2019 Red Hat, Inc.
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
import itertools
import os
import shutil
from datetime import timedelta
from time import sleep

import parted
from blivet import arch, blockdev
from blivet import callbacks as blivet_callbacks
from blivet import util as blivet_util
from blivet.devicelibs.lvm import HAVE_LVMDEVICES
from blivet.errors import FormatResizeError, FSResizeError, StorageError
from blivet.util import get_current_entropy

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.core.path import make_directories
from pyanaconda.core.util import execWithRedirect, join_paths
from pyanaconda.modules.common.constants.objects import FCOE, ISCSI, NVME
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.installation import StorageInstallationError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)


__all__ = ["CreateStorageLayoutTask", "MountFilesystemsTask", "WriteConfigurationTask"]


class CreateStorageLayoutTask(Task):
    """Installation task for execution of the storage configuration."""

    def __init__(self, storage, entropy_timeout=600):
        """Create a new task.

        :param storage: the storage model
        :param entropy_timeout: a number of seconds for entropy gathering
        """
        super().__init__()
        self._storage = storage
        self._entropy_timeout = entropy_timeout

    @property
    def name(self):
        return "Create storage layout"

    def run(self):
        """Do the execution.

        :raise: StorageInstallationError if the execution fails
        """
        if conf.target.is_directory:
            log.debug("Don't create the storage layout during "
                      "the installation to a directory.")
            return

        register = blivet_callbacks.create_new_callbacks_register(
            create_format_pre=self._report_message,
            resize_format_pre=self._report_message,
            wait_for_entropy=self._wait_for_entropy
        )

        try:
            self._turn_on_filesystems(
                self._storage,
                callbacks=register
            )
        except (FSResizeError, FormatResizeError) as e:
            log.exception("Failed to resize device %s: %s", e.details, str(e))
            message = _("An error occurred while resizing the device {}: {}").format(
                e.details, str(e)
            )
            raise StorageInstallationError(message) from None
        except StorageError as e:
            log.exception("Failed to create storage layout: %s", str(e))
            raise StorageInstallationError(str(e)) from None

    def _report_message(self, data):
        """Report a Blivet message.

        :param data: Blivet's callback data
        """
        self.report_progress(data.msg)

    def _wait_for_entropy(self, data):
        """Wait for entropy.

        :param data: Blivet's callback data
        :return: True if we are out of time, otherwise False
        """
        log.debug(data.msg)
        required_entropy = data.min_entropy
        total_time = self._entropy_timeout
        current_time = 0

        while True:
            # Report the current status.
            current_entropy = get_current_entropy()
            current_percents = min(int(current_entropy / required_entropy * 100), 100)
            remaining_time = max(total_time - current_time, 0)
            self._report_entropy_message(current_percents, remaining_time)

            sleep(5)
            current_time += 5

            # Enough entropy gathered.
            if current_percents == 100:
                return False

            # Out of time.
            if remaining_time == 0:
                return True

    def _report_entropy_message(self, percents, time):
        """Report an entropy message.

        :param percents: the percentage of gathered entropy
        :param time: a number of seconds of remaining time
        """
        if percents == 100:
            self.report_progress(_("Gathering entropy 100%"))
            return

        if time == 0:
            self.report_progress(_("Gathering entropy (time ran out)"))
            return

        message = _("Gathering entropy {percents}% (remaining time {time})").format(
            percents=percents,
            time=timedelta(seconds=time)
        )

        self.report_progress(message)

    def _turn_on_filesystems(self, storage, callbacks=None):
        """Perform installer-specific execution of storage configuration.

        :param storage: the storage object
        :type storage: an instance of InstallerStorage
        :param callbacks: callbacks to be invoked when actions are executed
        :type callbacks: return value of the :func:`blivet.callbacks.create_new_callbacks_register`
        """
        storage.devicetree.teardown_all()
        storage.do_it(callbacks)
        self._setup_bootable_devices(storage)
        storage.dump_state("final")
        storage.turn_on_swap()

    def _setup_bootable_devices(self, storage):
        """Set up the bootable devices.

        Mark the boot devices as bootable.

        :param storage: an instance of the storage
        """
        if storage.bootloader.skip_bootloader:
            return

        if storage.bootloader.stage2_bootable:
            boot = storage.boot_device
        else:
            boot = storage.bootloader.stage1_device

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


class MountFilesystemsTask(Task):
    """Installation task for mounting the filesystems."""

    def __init__(self, storage):
        """Create a new task."""
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Mount filesystems"

    def run(self):
        """Mount the filesystems."""
        self._storage.mount_filesystems()


class WriteConfigurationTask(Task):
    """Installation task for writing out the storage configuration."""

    def __init__(self, storage):
        """Create a new task."""
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Write the storage configuration"

    def run(self):
        """Mount the filesystems."""
        if conf.target.is_directory:
            log.debug("Don't write the storage configuration "
                      "during the installation to a directory.")
            return

        self._write_storage_configuration(self._storage)

    def _write_storage_configuration(self, storage, sysroot=None):
        """Write the storage configuration to sysroot.

        :param storage: the storage object
        :param sysroot: a path to the target OS installation
        """
        if sysroot is None:
            sysroot = conf.target.system_root

        if not os.path.isdir("%s/etc" % sysroot):
            os.mkdir("%s/etc" % sysroot)

        self._write_escrow_packets(storage, sysroot)

        storage.make_mtab()
        storage.fsset.write()

        self._write_lvm_devices_file(self._storage, sysroot)

        iscsi_proxy = STORAGE.get_proxy(ISCSI)
        iscsi_proxy.WriteConfiguration()

        fcoe_proxy = STORAGE.get_proxy(FCOE)
        fcoe_proxy.WriteConfiguration()

        nvme_proxy = STORAGE.get_proxy(NVME)
        nvme_proxy.WriteConfiguration()

        self._write_s390_device_config(sysroot)

    def _write_escrow_packets(self, storage, sysroot):
        """Write the escrow packets.

        :param storage: the storage object
        :type storage: an instance of InstallerStorage
        :param sysroot: a path to the target OS installation
        :type sysroot: str
        """
        escrow_devices = [
            d for d in storage.devices
            if d.format.type == 'luks' and d.format.escrow_cert
        ]

        if not escrow_devices:
            return

        log.debug("escrow: write_escrow_packets start")
        backup_passphrase = blockdev.crypto.generate_backup_passphrase()

        try:
            escrow_dir = sysroot + "/root"
            log.debug("escrow: writing escrow packets to %s", escrow_dir)
            blivet_util.makedirs(escrow_dir)
            for device in escrow_devices:
                log.debug("escrow: device %s: %s",
                          repr(device.path), repr(device.format.type))
                device.format.escrow(escrow_dir,
                                     backup_passphrase)

        except (OSError, RuntimeError) as e:
            # TODO: real error handling
            log.error("failed to store encryption key: %s", e)

        log.debug("escrow: write_escrow_packets done")

    @staticmethod
    def _write_lvm_devices_file(storage, sysroot):
        """Create the LVM devices file for the target system.

        Adds all present PVs according to https://bugzilla.redhat.com/show_bug.cgi?id=2011329#c9
        The file is located at /etc/lvm/devices/system.devices

        :param Blivet storage: instance of Blivet or a subclass
        :param str sysroot: path to the target OS installation
        """
        if conf.target.is_image:
            log.debug("Don't write the LVM devices file during image installation.")
            return

        if not HAVE_LVMDEVICES:
            return

        for device in itertools.chain(storage.devices, storage.devicetree._hidden):
            if device.format and device.format.type == "lvmpv":
                device.format.lvmdevices_add()

        in_filename = "/etc/lvm/devices/system.devices"
        out_filename = join_paths(sysroot, in_filename)

        if os.path.exists(in_filename):
            make_directories(os.path.dirname(out_filename))
            shutil.copyfile(in_filename, out_filename)

    def _write_s390_device_config(self, sysroot):
        """Copy entire persistent config of any s390 devices to sysroot.

        This includes config imported from initrd as well as anything the user
        configured via the installer user interface.

        :param sysroot: a path to the target OS installation
        """
        if arch.is_s390():
            execWithRedirect("chzdev",
                             ["--export", "/tmp/zdev.config",
                              "--all", "--type", "--persistent",
                              "--verbose"])
            execWithRedirect("chzdev",
                             ["--import", "/tmp/zdev.config",
                              "--persistent",
                              "--yes", "--no-root-update", "--force", "--verbose",
                              "--base", "/etc=%s/etc" % sysroot])
