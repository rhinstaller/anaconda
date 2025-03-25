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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import shutil
import traceback
from glob import glob

from pyanaconda.modules.common.errors.payload import SourceSetupError, SourceTearDownError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.base.utils import create_root_dir, write_module_blacklist

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


# TODO: Can we remove this really old code which probably even doesn't work now?
# The tmpfs is mounted above Dracut /tmp where the below files are created so we never copy
# anything because we don't see those files.
# This code was introduced by commit 13f58e367f918320ce7f5be2e08c6a02ff90a087 with no bz number.
# It looks that the functionality is not required anymore on the newer implementation.
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


class SetUpSourcesTask(Task):
    """Set up all the installation source of the payload."""

    def __init__(self, sources):
        """Create set up sources task.

        The task will group all the sources set up tasks under this one.

        :param sources: list of sources
        :type sources: [instance of PayloadSourceBase class]
        """
        super().__init__()
        self._sources = sources

    @property
    def name(self):
        return "Set Up Installation Sources"

    def run(self):
        """Collect and call set up tasks for all the sources."""
        if not self._sources:
            raise SourceSetupError("No sources specified for set up!")

        for source in self._sources:
            tasks = source.set_up_with_tasks()
            log.debug("Collected %s tasks from %s source",
                      [task.name for task in tasks],
                      source.type)

            for task in tasks:
                log.debug("Running task %s", task.name)
                task.run_with_signals()


class TearDownSourcesTask(Task):
    """Tear down all the installation sources of the payload."""

    def __init__(self, sources):
        """Create tear down sources task.

        The task will group all the sources tear down tasks under this one.

        :param sources: list of sources
        :type sources: [instance of PayloadSourceBase class]
        """
        super().__init__()
        self._sources = sources

    @property
    def name(self):
        return "Tear Down Installation Sources"

    def run(self):
        """Collect and call tear down tasks for all the sources."""
        if not self._sources:
            raise SourceSetupError("No sources specified for tear down!")

        errors = []

        for source in self._sources:
            tasks = source.tear_down_with_tasks()
            log.debug("Collected %s tasks from %s source",
                      [task.name for task in tasks],
                      source.type)

            for task in tasks:
                log.debug("Running task %s", task.name)
                try:
                    task.run()
                except SourceTearDownError as e:
                    message = "Task '{}' from source '{}' has failed, reason: {}".format(
                        task.name, source.type, str(e))
                    errors.append(message)
                    log.error("%s\n%s", message, traceback.format_exc())

        if errors:
            raise SourceTearDownError("Sources tear down have failed", errors)
