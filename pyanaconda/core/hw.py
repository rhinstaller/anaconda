#
# hw.py - utility functions dealing with hardware
#
# Copyright (C) 2022  Red Hat, Inc.  All rights reserved.
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
from blivet.arch import get_arch, is_arm

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.util import execWithCapture

log = get_module_logger(__name__)


NO_SWAP_EXTRA_RAM = 200


def minimal_memory_needed(with_gui=False, with_squashfs=False):
    """Get minimal memory needed to run the installation.

    :return: minimal memory needed in MB (MiB?)
    """
    if get_arch() in ["ppc64", "ppc64le"]:
        min_ram = 768
        gui_install_extra_ram = 512
    else:
        min_ram = 320
        gui_install_extra_ram = 90

    result = min_ram

    if with_gui:
        result += gui_install_extra_ram

    if with_squashfs:
        squashfs_extra_ram = 750
        result += squashfs_extra_ram

    return result


def detect_virtualized_platform():
    """Detect execution in a virtualized environment.

    This runs systemd-detect-virt and, if the result is not 'none',
    it returns an id of the detected virtualization technology.

    Otherwise, it returns None.

    :return: a virtualization technology identifier or None
    """
    try:
        platform = execWithCapture("systemd-detect-virt", []).strip()
    except (OSError, AttributeError):
        return None

    if platform == "none":
        return None

    return platform


def is_smt_enabled():
    """Is Simultaneous Multithreading (SMT) enabled?

    :return: True or False
    """
    from pyanaconda.core.configuration.anaconda import conf
    from pyanaconda.flags import flags

    if flags.automatedInstall \
            or not conf.target.is_hardware \
            or not conf.system.can_detect_enabled_smt:
        log.info("Skipping detection of SMT.")
        return False

    try:
        return int(open("/sys/devices/system/cpu/smt/active").read()) == 1
    except (OSError, ValueError):
        log.warning("Failed to detect SMT.")
        return False


def is_lpae_available():
    """Is LPAE available?

    :return: True of False
    """
    if not is_arm():
        return False

    with open("/proc/cpuinfo", "r") as f:
        for line in f:
            if line.startswith("Features") and "lpae" in line.split():
                return True

    return False
