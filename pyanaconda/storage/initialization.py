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

from blivet import util as blivet_util, udev
from blivet.errors import StorageError, UnknownSourceDeviceError
from blivet.flags import flags as blivet_flags

from pyanaconda.anaconda_logging import program_log_lock
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.errors import errorHandler as error_handler, ERROR_RAISE
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, AUTO_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.platform import platform as _platform

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.storage.partitioning import get_default_partitioning

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

    blivet_flags.auto_dev_updates = True
    blivet_flags.selinux_reset_fcon = True
    blivet_flags.keep_empty_ext_partitions = False
    blivet_flags.discard_new = True

    udev.device_name_blacklist = [r'^mtd', r'^mmcblk.+boot', r'^mmcblk.+rpmb', r'^zram', '^ndblk']


def create_storage():
    """Create the storage object.

    :return: an instance of the Blivet's storage object
    """
    from pyanaconda.storage.osinstall import InstallerStorage
    import blivet.arch

    storage = InstallerStorage()
    _set_storage_defaults(storage)

    if blivet.arch.is_s390():
        _load_plugin_s390()

    return storage


def _set_storage_defaults(storage):
    """Set the storage default values."""
    fstype = None
    boot_fstype = None

    # Get the default fstype from a kickstart file.
    auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)

    if auto_part_proxy.Enabled and auto_part_proxy.FilesystemType:
        fstype = auto_part_proxy.FilesystemType
        boot_fstype = fstype
    # Or from the configuration.
    elif conf.storage.file_system_type:
        fstype = conf.storage.file_system_type
        boot_fstype = None

    # Set the default fstype.
    if fstype:
        storage.set_default_fstype(fstype)

    # Set the default boot fstype.
    if boot_fstype:
        storage.set_default_boot_fstype(boot_fstype)

    # Set the default LUKS version.
    luks_version = conf.storage.luks_version

    if luks_version:
        storage.set_default_luks_version(luks_version)

    # Set the default partitioning.
    storage.set_default_partitioning(get_default_partitioning())


def _load_plugin_s390():
    """Load the s390x plugin."""
    # Is the plugin loaded? We are done then.
    if "s390" in blockdev.get_available_plugin_names():
        return

    # Otherwise, load the plugin.
    plugin = blockdev.PluginSpec()
    plugin.name = blockdev.Plugin.S390
    plugin.so_name = None
    blockdev.reinit([plugin], reload=False)


def update_blivet_flags():
    """Set installer-specific flags.

    This changes blivet default flags by either flipping the original value,
    or it assigns the flag value based on anaconda settings that are passed in.
    """
    blivet_flags.selinux = conf.security.selinux
    blivet_flags.dmraid = conf.storage.dmraid
    blivet_flags.ibft = conf.storage.ibft
    blivet_flags.multipath_friendly_names = conf.storage.multipath_friendly_names
    blivet_flags.allow_imperfect_devices = conf.storage.allow_imperfect_devices


def initialize_storage(storage):
    """Perform installer-specific storage initialization.

    :param storage: an instance of the Blivet's storage object
    """
    update_blivet_flags()

    # Platform class setup depends on flags, re-initialize it.
    _platform.update_from_flags()

    storage.shutdown()

    while True:
        try:
            storage.reset()
        except StorageError as e:
            if error_handler.cb(e) == ERROR_RAISE:
                raise
            else:
                continue
        else:
            break

    # FIXME: This is a temporary workaround for live OS.
    # TODO: Shouldn't we move this somewhere else?
    if not conf.system._is_live_os and not any(d.protected for d in storage.devices):
        raise UnknownSourceDeviceError()

    # kickstart uses all the disks
    if flags.automatedInstall:
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        selected_disks = disk_select_proxy.SelectedDisks
        ignored_disks = disk_select_proxy.IgnoredDisks

        if not selected_disks:
            selected_disks = [d.name for d in storage.disks if d.name not in ignored_disks]
            disk_select_proxy.SetSelectedDisks(selected_disks)
            log.debug("onlyuse is now: %s", ",".join(selected_disks))
