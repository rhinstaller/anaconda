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
import gi
gi.require_version("BlockDev", "2.0")
from gi.repository import BlockDev as blockdev

from blivet import util as blivet_util, udev, arch
from blivet.devicelibs import crypto
from blivet.errors import StorageError
from blivet.flags import flags as blivet_flags
from blivet.static_data import luks_data

from pyanaconda.anaconda_logging import program_log_lock
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import BOOTLOADER_DRIVE_UNSET
from pyanaconda.errors import errorHandler as error_handler, ERROR_RAISE
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, FCOE, ZFCP, BOOTLOADER, \
    ISCSI
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.storage.osinstall import InstallerStorage
from pyanaconda.platform import platform

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def enable_installer_mode():
    """Configure Blivet for use by Anaconda."""
    blivet_util.program_log_lock = program_log_lock

    # always enable the debug mode when in the installer mode so that we
    # have more data in the logs for rare cases that are hard to reproduce
    blivet_flags.debug = True

    # We don't want image installs writing backups of the *image* metadata
    # into the *host's* /etc/lvm. This can get real messy on build systems.
    if conf.target.is_image:
        blivet_flags.lvm_metadata_backup = False

    # Set the flags.
    blivet_flags.auto_dev_updates = True
    blivet_flags.selinux_reset_fcon = True
    blivet_flags.keep_empty_ext_partitions = False
    blivet_flags.discard_new = True
    blivet_flags.selinux = conf.security.selinux
    blivet_flags.dmraid = conf.storage.dmraid
    blivet_flags.ibft = conf.storage.ibft
    blivet_flags.multipath_friendly_names = conf.storage.multipath_friendly_names
    blivet_flags.allow_imperfect_devices = conf.storage.allow_imperfect_devices

    # Platform class setup depends on flags, re-initialize it.
    platform.update_from_flags()

    # Set the minimum required entropy.
    luks_data.min_entropy = crypto.MIN_CREATE_ENTROPY

    # Load plugins.
    if arch.is_s390():
        load_plugin_s390()

    # Set the blacklist.
    udev.device_name_blacklist = [r'^mtd', r'^mmcblk.+boot', r'^mmcblk.+rpmb', r'^zram', '^ndblk']

    # We need this so all the /dev/disk/* stuff is set up.
    udev.trigger(subsystem="block", action="change")


def create_storage():
    """Create the storage object.

    :return: an instance of the Blivet's storage object
    """
    storage = InstallerStorage()

    # Set the default filesystem type.
    storage.set_default_fstype(conf.storage.file_system_type or storage.default_fstype)

    # Set the default LUKS version.
    storage.set_default_luks_version(conf.storage.luks_version or storage.default_luks_version)

    return storage


def load_plugin_s390():
    """Load the s390x plugin."""
    # Don't load the plugin in a dir installation.
    if conf.target.is_directory:
        return

    # Is the plugin loaded? We are done then.
    if "s390" in blockdev.get_available_plugin_names():
        return

    # Otherwise, load the plugin.
    plugin = blockdev.PluginSpec()
    plugin.name = blockdev.Plugin.S390
    plugin.so_name = None
    blockdev.reinit([plugin], reload=False)


def reset_storage(storage, scan_all=False, retry=True):
    """Reset the storage model.

    :param storage: an instance of the Blivet's storage object
    :param scan_all: should we scan all devices in the system?
    :param retry: should we allow to retry the reset?
    """
    # Clear the exclusive disks to scan all devices in the system.
    if scan_all:
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        disk_select_proxy.SetExclusiveDisks([])

    # Do the reset.
    while True:
        try:
            _reset_storage(storage)
        except StorageError as e:
            # Is the retry allowed?
            if not retry:
                raise
            # Does the user want to retry?
            elif error_handler.cb(e) == ERROR_RAISE:
                raise
            # Retry the storage reset.
            else:
                continue
        else:
            # No need to retry.
            break


def reset_bootloader(storage):
    """Reset the bootloader.

    :param storage: an instance of the Blivet's storage object
    """
    bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)
    bootloader_proxy.SetDrive(BOOTLOADER_DRIVE_UNSET)
    storage.bootloader.reset()


def select_all_disks_by_default(storage):
    """Select all disks for the partitioning by default.

    It will select all disks for the partitioning if there are
    no disks selected. Kickstart uses all the disks by default.

    :param storage: an instance of the Blivet's storage object
    :return: a list of selected disks
    """
    disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
    selected_disks = disk_select_proxy.SelectedDisks
    ignored_disks = disk_select_proxy.IgnoredDisks

    if not selected_disks:
        selected_disks = [d.name for d in storage.disks if d.name not in ignored_disks]
        disk_select_proxy.SetSelectedDisks(selected_disks)
        log.debug("Selecting all disks by default: %s", ",".join(selected_disks))

    return selected_disks


def _reset_storage(storage):
    """Do reset the storage.

    FIXME: Call the DBus task instead of this function.

    :param storage: an instance of the Blivet's storage object
    """
    # Set the ignored and exclusive disks.
    disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
    storage.ignored_disks = disk_select_proxy.IgnoredDisks
    storage.exclusive_disks = disk_select_proxy.ExclusiveDisks
    storage.protected_devices = disk_select_proxy.ProtectedDevices
    storage.disk_images = disk_select_proxy.DiskImages

    # Reload additional modules.
    if not conf.target.is_image:
        iscsi_proxy = STORAGE.get_proxy(ISCSI)
        iscsi_proxy.ReloadModule()

        fcoe_proxy = STORAGE.get_proxy(FCOE)
        fcoe_proxy.ReloadModule()

        zfcp_proxy = STORAGE.get_proxy(ZFCP)
        zfcp_proxy.ReloadModule()

    # Do the reset.
    storage.reset()
