#
# Copyright (C) 2021 Red Hat, Inc.
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
import os
import shutil
from glob import glob

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.path import make_directories
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

__all__ = ["CopyDriverDisksFilesTask", "PrepareSystemForInstallationTask"]


class PrepareSystemForInstallationTask(Task):
    """Prepare system for the installation process.

    Steps to prepare the installation root:
    * Create a root directory
    * Create a module denylist from the boot cmdline
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
        return "Prepare system for installation"

    def run(self):
        """Create a root and write module denylist."""
        self._create_root_dir(self._sysroot)
        self._write_module_denylist(self._sysroot)

    @staticmethod
    def _create_root_dir(sysroot):
        """Create root directory on the installed system."""
        make_directories(os.path.join(sysroot, "root"))

    @staticmethod
    def _write_module_denylist(sysroot):
        """Create module denylist based on the user preference.

        Copy modules from modprobe.blacklist=<module> on cmdline to
        /etc/modprobe.d/anaconda-denylist.conf so that modules will
        continue to be added to a denylist when the system boots.
        """
        if "modprobe.blacklist" not in kernel_arguments:
            return

        make_directories(os.path.join(sysroot, "etc/modprobe.d"))
        with open(os.path.join(sysroot, "etc/modprobe.d/anaconda-denylist.conf"), "w") as f:
            f.write("# Module denylist written by anaconda\n")
            for module in kernel_arguments.get("modprobe.blacklist").split():
                f.write("blacklist %s\n" % module)


class CopyDriverDisksFilesTask(Task):
    """Copy driver disks files after installation to the installed system.

    TODO: Can we remove this really old code?

    The tmpfs is mounted above Dracut /tmp where the below files are created
    so we never copy anything because we don't see those files.

    This code was introduced by commit 13f58e3 with no bz number.

    It looks that the functionality is not required anymore on the newer
    implementation.
    """

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
        return "Copy driver disks files"

    def run(self):
        """Copy files from the driver disks to the installed system."""
        if not conf.system.can_use_driver_disks:
            log.info("Skipping copying of driver disk files.")
            return

        # Multiple driver disks may be loaded, so we need to glob for all
        # the firmware files in the common DD firmware directory
        for f in glob(self.DD_FIRMWARE_DIR + "/*"):
            try:
                shutil.copyfile(f, os.path.join(self._sysroot, "lib/firmware/"))
            except OSError as e:
                log.error("Could not copy firmware file %s: %s", f, e.strerror)

        # copy RPMS
        for d in glob(os.path.join(self.DD_RPMS_DIR, self.DD_RPMS_GLOB)):
            dest_dir = os.path.join(self._sysroot, "root/", os.path.basename(d))
            shutil.copytree(d, dest_dir)

        # copy modules and firmware into root's home directory
        if os.path.exists(self.DD_DIR):
            try:
                shutil.copytree(self.DD_DIR, os.path.join(self._sysroot, "root/DD"))
            except (OSError, shutil.Error) as e:
                log.error("failed to copy driver disk files: %s", e.strerror)
                # XXX TODO: real error handling, as this is probably going to
                #           prevent boot on some systems
