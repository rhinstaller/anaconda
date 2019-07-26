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

from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payload.shared.utils import create_root_dir, write_module_blacklist, \
    copy_driver_disk_files


class PrepareSystemForInstallationTask(Task):
    """Prepare system for the installation process.

    Steps to prepare the installation root:
    * Create a root directory
    * Create a module blacklist from the boot cmdline
    """

    @property
    def name(self):
        return "Prepare System for Installation"

    def run(self):
        """Create a root and write module blacklist."""
        create_root_dir()
        write_module_blacklist()


class CopyDriverDisksFilesTask(Task):
    """Copy driver disks files after installation to the installed system."""

    @property
    def name(self):
        return "Copy Driver Disks Files"

    def run(self):
        """Copy files from the driver disks to the installed system."""
        copy_driver_disk_files()
