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
from blivet import util as blivet_util, udev
from blivet.errors import StorageError, UnknownSourceDeviceError
from blivet.flags import flags as blivet_flags

from pyanaconda.anaconda_logging import program_log_lock
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.errors import errorHandler as error_handler, ERROR_RAISE
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import DISK_SELECTION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.platform import platform as _platform

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

    blivet_flags.auto_dev_updates = True
    blivet_flags.selinux_reset_fcon = True
    blivet_flags.keep_empty_ext_partitions = False
    blivet_flags.discard_new = True

    udev.device_name_blacklist = [r'^mtd', r'^mmcblk.+boot', r'^mmcblk.+rpmb', r'^zram', '^ndblk']


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


def initialize_storage(storage, ksdata, protected):
    """Perform installer-specific storage initialization.

    :param storage: an instance of the Blivet's storage object
    :param ksdata: an instance of the kickstart data
    :param protected: a list of protected device names
    """
    update_blivet_flags()

    # Platform class setup depends on flags, re-initialize it.
    _platform.update_from_flags()

    storage.shutdown()

    # Set up the protected partitions list now.
    if protected:
        storage.config.protected_dev_specs.extend(protected)

    while True:
        try:
            # This also calls storage.config.update().
            storage.reset()
        except StorageError as e:
            if error_handler.cb(e) == ERROR_RAISE:
                raise
            else:
                continue
        else:
            break

    # FIXME: This is a temporary workaround for live OS.
    if protected and not conf.system._is_live_os and \
       not any(d.protected for d in storage.devices):
        raise UnknownSourceDeviceError(protected)

    # kickstart uses all the disks
    if flags.automatedInstall:
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        selected_disks = disk_select_proxy.SelectedDisks
        ignored_disks = disk_select_proxy.IgnoredDisks

        if not selected_disks:
            selected_disks = [d.name for d in storage.disks if d.name not in ignored_disks]
            disk_select_proxy.SetSelectedDisks(selected_disks)
            log.debug("onlyuse is now: %s", ",".join(selected_disks))
