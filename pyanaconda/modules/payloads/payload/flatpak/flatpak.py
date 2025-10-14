#
# Payload module for preinstalling Flatpaks
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

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.payloads.base.utils import calculate_required_space
from pyanaconda.modules.payloads.constants import PayloadType
from pyanaconda.modules.payloads.payload.flatpak.flatpak_interface import (
    FlatpakInterface,
)
from pyanaconda.modules.payloads.payload.flatpak.flatpak_manager import FlatpakManager
from pyanaconda.modules.payloads.payload.flatpak.initialization import (
    CalculateFlatpaksSizeTask,
)
from pyanaconda.modules.payloads.payload.flatpak.installation import (
    CleanUpDownloadLocationTask,
    DownloadFlatpaksTask,
    InstallFlatpaksTask,
    PrepareDownloadLocationTask,
)
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase

log = get_module_logger(__name__)

# We need Flatpak to read configuration files from the target and write
# to the target system installation. Since we use the Flatpak API
# in process, we need to do this by modifying the environment before
# we start any threads. Setting these variables will be harmless if
# we aren't actually using Flatpak.
# These variables are available only for a running process so they are
# not impacting user environment.

# pylint: disable=environment-modify
os.environ["FLATPAK_DOWNLOAD_TMPDIR"] = os.path.join(conf.target.system_root, "var/tmp")
# pylint: disable=environment-modify
os.environ["FLATPAK_CONFIG_DIR"] = os.path.join(conf.target.system_root, "etc/flatpak")
# pylint: disable=environment-modify
os.environ["FLATPAK_OS_CONFIG_DIR"] = os.path.join(conf.target.system_root, "usr/share/flatpak")
# pylint: disable=environment-modify
os.environ["FLATPAK_SYSTEM_DIR"] = os.path.join(conf.target.system_root, "var/lib/flatpak")



class FlatpakModule(PayloadBase):
    """The Flatpak payload module."""

    def __init__(self):
        super().__init__()
        self._flatpak_manager = FlatpakManager()

    def for_publication(self):
        """Get the interface used to publish this source."""
        return FlatpakInterface(self)

    @property
    def type(self):
        """Type of this payload."""
        return PayloadType.FLATPAK

    @property
    def default_source_type(self):
        """Type of the default source."""
        return None

    @property
    def supported_source_types(self):
        """List of supported source types."""
        # Flatpak doesn't own any source.
        # FIXME: Flatpak needs it's own source because this way it needs to understand
        # all existing and future ones
        return []

    def set_sources(self, sources):
        """Set a new list of sources to a flatpak manager.

        This overrides the base implementation since the sources we set here
        are the sources from the main payload, and can already be initialized.

        TODO: This DBus API will not work until we have proper handling of the sources.
              It will only work as redirect to flatpak_manager but no sources are stored here.

        :param sources: set a new sources
        :type sources: instance of pyanaconda.modules.payloads.source.source_base.PayloadSourceBase
        """
        log.debug("Flatpak input sources set to: %s", sources)
        self._flatpak_manager.set_sources(sources)

    def set_flatpak_refs(self, refs):
        """Set the flatpak refs.

        :param refs: a list of flatpak refs
        """
        log.debug("Flatpak refs are set to: %s", refs)
        self._flatpak_manager.set_flatpak_refs(refs)

    def calculate_required_space(self):
        """Calculate space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        download_size = self._flatpak_manager.download_size
        install_size = self._flatpak_manager.install_size
        size = calculate_required_space(download_size, install_size)
        log.debug("Flatpak size required to download: %s to install: %s required: %s",
                  download_size, install_size, size)
        return size

    def calculate_size_with_task(self):
        """Refresh size requirement with task."""
        return CalculateFlatpaksSizeTask(flatpak_manager=self._flatpak_manager)

    def install_with_tasks(self):
        """Install the payload with tasks."""

        tasks = [
            PrepareDownloadLocationTask(
                flatpak_manager=self._flatpak_manager,
            ),
            DownloadFlatpaksTask(
                flatpak_manager=self._flatpak_manager,
            ),
            InstallFlatpaksTask(
                flatpak_manager=self._flatpak_manager,
            ),
            CleanUpDownloadLocationTask(
                flatpak_manager=self._flatpak_manager,
            ),
        ]

        return tasks
