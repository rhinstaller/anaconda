#
# Utility functions shared for the whole payload module.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import shutil
from glob import glob

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import DD_ALL, DD_FIRMWARE, DD_RPMS
from pyanaconda.core.util import mkdirChain
from pyanaconda.flags import flags

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def create_root_dir():
    """Create root directory on the installed system."""
    mkdirChain(conf.target.system_root + "/root")


def write_module_blacklist():
    """Create module blacklist based on the user preference.

    Copy modules from modprobe.blacklist=<module> on cmdline to
    /etc/modprobe.d/anaconda-blacklist.conf so that modules will
    continue to be blacklisted when the system boots.
    """
    if "modprobe.blacklist" not in flags.cmdline:
        return

    mkdirChain(conf.target.system_root + "/etc/modprobe.d")
    with open(conf.target.system_root + "/etc/modprobe.d/anaconda-blacklist.conf", "w") as f:
        f.write("# Module blacklists written by anaconda\n")
        for module in flags.cmdline["modprobe.blacklist"].split():
            f.write("blacklist %s\n" % module)


def copy_driver_disk_files():
    """Copy driver disk files to the installed system."""
    # Multiple driver disks may be loaded, so we need to glob for all
    # the firmware files in the common DD firmware directory
    for f in glob(DD_FIRMWARE + "/*"):
        try:
            shutil.copyfile(f, os.path.join(conf.target.system_root, "lib/firmware/"))
        except IOError as e:
            log.error("Could not copy firmware file %s: %s", f, e.strerror)

    # copy RPMS
    for d in glob(DD_RPMS):
        dest_dir = os.path.join(conf.target.system_root, "root/", os.path.basename(d))
        shutil.copytree(d, dest_dir)

    # copy modules and firmware into root's home directory
    if os.path.exists(DD_ALL):
        try:
            shutil.copytree(DD_ALL, os.path.join(conf.target.system_root, "root/DD"))
        except IOError as e:
            log.error("failed to copy driver disk files: %s", e.strerror)
            # XXX TODO: real error handling, as this is probably going to
            #           prevent boot on some systems
