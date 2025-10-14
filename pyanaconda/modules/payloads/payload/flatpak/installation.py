#
# Copyright (C) 2024 Red Hat, Inc.
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

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.base.utils import pick_download_location
from pyanaconda.modules.payloads.payload.flatpak.flatpak_manager import FlatpakManager

log = get_module_logger(__name__)

FLATPAK_MIRROR_DIR_SUFFIX = 'flatpak.mirror'


class PrepareDownloadLocationTask(Task):
    """The installation task for setting up the download location."""

    def __init__(self, flatpak_manager: FlatpakManager):
        """Create a new task.

        :param flatpak_manager: a Flatpak manager
        """
        super().__init__()
        self._flatpak_manager = flatpak_manager

    @property
    def name(self):
        return "Prepare the Flatpaks download"

    def run(self):
        """Run the task.

        :return: a path of the download location
        """

        self._flatpak_manager.calculate_size()

        path = pick_download_location(self._flatpak_manager.download_size,
                                      self._flatpak_manager.install_size,
                                      FLATPAK_MIRROR_DIR_SUFFIX)

        if os.path.exists(path):
            log.info("Removing existing Flatpak download location: %s", path)
            shutil.rmtree(path)

        self._flatpak_manager.set_download_location(path)
        return path


class CleanUpDownloadLocationTask(Task):
    """The installation task for cleaning up the download location."""

    def __init__(self, flatpak_manager):
        """Create a new task.

        :param flatpak_manager: a Flatpak manager
        """
        super().__init__()
        self._flatpak_manager = flatpak_manager

    @property
    def name(self):
        return "Remove downloaded Flatpaks"

    def run(self):
        """Run the task."""
        path = self._flatpak_manager.download_location

        if not os.path.exists(path):
            # If nothing was downloaded, there is nothing to clean up.
            return

        log.info("Removing downloaded Flatpaks from %s.", path)
        shutil.rmtree(path)


class DownloadFlatpaksTask(Task):
    """Task to download remote Flatpaks"""

    def __init__(self, flatpak_manager):
        """Create a new task."""
        super().__init__()
        self._flatpak_manager = flatpak_manager

    @property
    def name(self):
        """Name of the task."""
        return "Download remote Flatpaks"

    def run(self):
        """Run the task."""
        self._flatpak_manager.download(self)


class InstallFlatpaksTask(Task):
    """Task to install flatpaks"""

    def __init__(self, flatpak_manager):
        """Create a new task."""
        super().__init__()
        self._flatpak_manager = flatpak_manager

    @property
    def name(self):
        """Name of the task."""
        return "Install Flatpaks"

    def run(self):
        """Run the task."""
        self._flatpak_manager.install(self)
