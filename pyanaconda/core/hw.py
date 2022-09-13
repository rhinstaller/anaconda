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
import blivet.arch
from pyanaconda.core.util import execWithCapture

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


if blivet.arch.get_arch() in ["ppc64", "ppc64le"]:
    MIN_RAM = 768
    GUI_INSTALL_EXTRA_RAM = 512
else:
    MIN_RAM = 320
    GUI_INSTALL_EXTRA_RAM = 90

MIN_GUI_RAM = MIN_RAM + GUI_INSTALL_EXTRA_RAM
SQUASHFS_EXTRA_RAM = 750
NO_SWAP_EXTRA_RAM = 200


def total_memory():
    """Returns total system memory in kB (given to us by /proc/meminfo)"""

    with open("/proc/meminfo", "r") as fobj:
        for line in fobj:
            if not line.startswith("MemTotal"):
                # we are only interested in the MemTotal: line
                continue

            fields = line.split()
            if len(fields) != 3:
                log.error("unknown format for MemTotal line in /proc/meminfo: %s", line.rstrip())
                raise RuntimeError("unknown format for MemTotal line in /proc/meminfo: %s" % line.rstrip())

            try:
                memsize = int(fields[1])
            except ValueError as err:
                log.error("invalid value of MemTotal /proc/meminfo: %s", fields[1])
                raise RuntimeError("invalid value of MemTotal /proc/meminfo: %s" % fields[1]) \
                    from err

            # Because /proc/meminfo only gives us the MemTotal (total physical
            # RAM minus the kernel binary code), we need to round this
            # up. Assuming every machine has the total RAM MB number divisible
            # by 128.
            memsize /= 1024
            memsize = (memsize / 128 + 1) * 128
            memsize *= 1024

            log.info("%d kB (%d MB) are available", memsize, memsize / 1024)
            return memsize

        log.error("MemTotal: line not found in /proc/meminfo")
        raise RuntimeError("MemTotal: line not found in /proc/meminfo")


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
    from pyanaconda.flags import flags
    from pyanaconda.core.configuration.anaconda import conf

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
    if not blivet.arch.is_arm():
        return False

    with open("/proc/cpuinfo", "r") as f:
        for line in f:
            if line.startswith("Features") and "lpae" in line.split():
                return True

    return False
