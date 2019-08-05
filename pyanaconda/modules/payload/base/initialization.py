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

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payload.base.utils import create_root_dir, write_module_blacklist

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class PrepareSystemForInstallationTask(Task):
    """Prepare system for the installation process.

    Steps to prepare the installation root:
    * Create a root directory
    * Create a module blacklist from the boot cmdline
    """

    def __init__(self, sysroot):
        """Create prepare system for installation task.

        :param sysroot: path to the installation root
        :type sysroot: str
        """
        super().__init__()
        self._sysroot = sysroot

    @property
    def name(self):
        return "Prepare System for Installation"

    def run(self):
        """Create a root and write module blacklist."""
        create_root_dir(self._sysroot)
        write_module_blacklist(self._sysroot)


class CopyDriverDisksFilesTask(Task):
    """Copy driver disks files after installation to the installed system."""

    DD_DIR = "/tmp/DD"
    DD_FIRMWARE_DIR = "/tmp/DD/lib/firmware"
    DD_RPMS_DIR = "/tmp"
    DD_RPMS_GLOB = "DD-*"

    def __init__(self, sysroot):
        """Create copy driver disks files task.

        :param sysroot: path to the installation root
        :type sysroot: str
        """
        super().__init__()
        self._sysroot = sysroot

    @property
    def name(self):
        return "Copy Driver Disks Files"

    def run(self):
        """Copy files from the driver disks to the installed system."""
        # Multiple driver disks may be loaded, so we need to glob for all
        # the firmware files in the common DD firmware directory
        for f in glob(self.DD_FIRMWARE_DIR + "/*"):
            try:
                shutil.copyfile(f, os.path.join(self._sysroot, "lib/firmware/"))
            except IOError as e:
                log.error("Could not copy firmware file %s: %s", f, e.strerror)

        # copy RPMS
        for d in glob(os.path.join(self.DD_RPMS_DIR, self.DD_RPMS_GLOB)):
            dest_dir = os.path.join(self._sysroot, "root/", os.path.basename(d))
            shutil.copytree(d, dest_dir)

        # copy modules and firmware into root's home directory
        if os.path.exists(self.DD_DIR):
            try:
                shutil.copytree(self.DD_DIR, os.path.join(self._sysroot, "root/DD"))
            except IOError as e:
                log.error("failed to copy driver disk files: %s", e.strerror)
                # XXX TODO: real error handling, as this is probably going to
                #           prevent boot on some systems
