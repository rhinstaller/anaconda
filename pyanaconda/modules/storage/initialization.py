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
from blivet import arch, blockdev, udev
from blivet import util as blivet_util
from blivet.devicelibs import crypto, lvm
from blivet.flags import flags as blivet_flags
from blivet.formats import get_device_format_class
from blivet.static_data import luks_data

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.anaconda_logging import program_log_lock
from pyanaconda.core.configuration.anaconda import conf

__all__ = ["enable_installer_mode"]

log = get_module_logger(__name__)


def enable_installer_mode():
    """Configure Blivet for use by Anaconda."""
    blivet_util.program_log_lock = program_log_lock

    # always enable the debug mode when in the installer mode so that we
    # have more data in the logs for rare cases that are hard to reproduce
    blivet_flags.debug = True

    # We don't want image installs writing backups of the *image* metadata
    # into the *host's* /etc/lvm. This can get real messy on build systems.
    # Same applies to system.devices file that shouldn't be populated with
    # PV names from the system that creates the image
    if conf.target.is_image:
        blivet_flags.lvm_metadata_backup = False
        blivet_flags.lvm_devices_file = False

    # Set the flags.
    blivet_flags.auto_dev_updates = True
    blivet_flags.selinux_reset_fcon = True
    blivet_flags.keep_empty_ext_partitions = False
    blivet_flags.discard_new = True
    blivet_flags.selinux = conf.security.selinux
    blivet_flags.ibft = conf.storage.ibft
    blivet_flags.multipath_friendly_names = conf.storage.multipath_friendly_names
    blivet_flags.allow_imperfect_devices = conf.storage.allow_imperfect_devices
    blivet_flags.btrfs_compression = conf.storage.btrfs_compression

    # Platform class setup depends on flags, re-initialize it.
    _set_default_label_type()

    # Set the minimum required entropy.
    luks_data.min_entropy = crypto.MIN_CREATE_ENTROPY

    # Load plugins.
    if arch.is_s390():
        _load_plugin_s390()

    # Set the device name regexes to ignore.
    udev.ignored_device_names = [
        r'^mtd',
        r'^mmcblk.+boot',
        r'^mmcblk.+rpmb',
        r'^zram',
        r'^ndblk',
        r'^pmem[0-9]+$',
    ]

    # We need this so all the /dev/disk/* stuff is set up.
    udev.trigger(subsystem="block", action="change")

    # Disable LVM auto-activation during installation
    if not conf.target.is_directory and not conf.target.is_image:
        try:
            lvm.disable_lvm_autoactivation()
        except RuntimeError as e:
            log.error("Failed to disable LVM auto-activation: %s", str(e))


def _set_default_label_type():
    """Set up the default label type."""
    if not conf.storage.disk_label_type:
        return

    disklabel_class = get_device_format_class("disklabel")
    supported_types = disklabel_class.get_platform_label_types()
    default_type = supported_types[0] if supported_types else None
    requested_type = conf.storage.disk_label_type

    if requested_type == "mbr":
        requested_type = "msdos"

    if requested_type in supported_types:
        disklabel_class.set_default_label_type(requested_type)
    else:
        log.warning(
            "The requested disk label type '%s' is not supported on "
            "this platform. Using the default disk label '%s' instead.",
            conf.storage.disk_label_type, default_type
        )


def _load_plugin_s390():
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
