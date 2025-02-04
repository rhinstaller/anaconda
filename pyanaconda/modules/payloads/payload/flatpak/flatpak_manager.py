#
# Root object for handling Flatpak pre-installation
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#


from typing import List, Optional

import gi

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.glib import GError
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.task.progress import ProgressReporter
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.payload.flatpak.source import (
    FlatpakRegistrySource,
    FlatpakStaticSource,
    NoSourceError,
)
from pyanaconda.modules.payloads.source.source_base import (
    PayloadSourceBase,
    RepositorySourceMixin,
)

gi.require_version("Flatpak", "1.0")
gi.require_version("Gio", "2.0")

from gi.repository.Flatpak import Installation, Transaction, TransactionOperationType

log = get_module_logger(__name__)

__all__ = ["FlatpakManager"]


class FlatpakManager:
    """Root object for handling Flatpak pre-installation"""

    def __init__(self):
        """Create and initialize this class.

        :param function callback: a progress reporting callback
        """
        self._flatpak_refs = []
        self._source_repository = None
        self._source = None
        self._skip_installation = False
        self._collection_location = None
        self._progress: Optional[ProgressReporter] = None
        self._transaction = None
        self._download_location = None
        self._download_size = 0
        self._install_size = 0

    def set_sources(self, sources: List[PayloadSourceBase]):
        """Set the source object we use to download Flatpak content.

        If unset, pre-installation will install directly from the configured
        Flatpak remote (see flatpak_remote in the anaconda configuration).

        :param str url: URL pointing to the Flatpak content
        """

        if not sources:
            return

        source = sources[0]

        if isinstance(source, RepositorySourceMixin):
            if self._source and isinstance(self._source, FlatpakStaticSource) \
                    and self._source.repository_config == source.repository:
                return
            self._source = FlatpakStaticSource(source.repository, relative_path="Flatpaks")
        elif source.type in (SourceType.CDN, SourceType.CLOSEST_MIRROR):
            if self._source and isinstance(self._source, FlatpakRegistrySource):
                return
            _, remote_url = conf.payload.flatpak_remote
            log.debug("Using Flatpak registry source: %s", remote_url)
            self._source = FlatpakRegistrySource(remote_url)
        else:
            self._source = None

    def set_flatpak_refs(self, refs: Optional[List[str]]):
        """Set the Flatpak refs to be installed.

        :param refs: List of Flatpak refs to be installed, None to use
           all Flatpak refs from the source. Each ref should be in the form
           [<collection_id>:](app|runtime)/<id>/[<arch>]/<branch>
        """
        self._skip_installation = False
        self._flatpak_refs = refs if refs is not None else []

    def set_download_location(self, path: str):
        """Sets a location that can be used for temporary download of Flatpak content.

        :param path: parent directory to store downloaded Flatpak content
           (the download should be to a subdirectory of this path)
        """
        self._download_location = path

    @property
    def download_location(self) -> str:
        """Get the download location."""
        return self._download_location

    def _get_source(self):
        if self._source is None:
            if self._source_repository:
                log.debug("Using Flatpak source repository at: %s/Flatpaks",
                          self._source_repository.url)
                self._source = FlatpakStaticSource(self._source_repository,
                                                   relative_path="Flatpaks")
            else:
                _, remote_url = conf.payload.flatpak_remote
                log.debug("Using Flatpak registry source: %s", remote_url)
                self._source = FlatpakRegistrySource(remote_url)

        return self._source

    def calculate_size(self):
        """Calculate the download and install size of the Flatpak content.

        :param progress: used to report progress of the operation

        The result is available from the download_size and install_size properties.
        """
        if self._skip_installation:
            log.debug("Flatpak installation is going to be skipped.")
            return

        if len(self._flatpak_refs) == 0:
            log.debug("No flatpaks are marked for installation.")
            return

        try:
            self._download_size, self._install_size = \
                self._get_source().calculate_size(self._flatpak_refs)
        except NoSourceError as e:
            log.error("Flatpak source not available, skipping installing %s: %s",
                      ", ".join(self._flatpak_refs), e)
            self._skip_installation = True

    @property
    def download_size(self):
        """Space needed to to temporarily download Flatpak content before installation"""
        return self._download_size

    @property
    def install_size(self):
        """Space used after installation in the target system"""
        return self._install_size

    def download(self, progress: ProgressReporter):
        """Download Flatpak content to a temporary location.

        :param progress: used to report progress of the operation

        This is only needed if Flatpak can't install the content directly.
        """
        if self._skip_installation or len(self._flatpak_refs) == 0:
            return

        try:
            self._collection_location = self._get_source().download(self._flatpak_refs,
                                                                    self._download_location,
                                                                    progress)
        except NoSourceError as e:
            log.error("Flatpak source not available, skipping installing %s: %s",
                      ", ".join(self._flatpak_refs), e)
            self._skip_installation = True

    def install(self, progress: ProgressReporter):
        """Install the Flatpak content to the target system.

        :param progress: used to report progress of the operation
        """
        if self._skip_installation or len(self._flatpak_refs) == 0:
            return

        installation = self._create_flatpak_installation()
        self._transaction = self._create_flatpak_transaction(installation)

        if self._collection_location:
            self._transaction.add_sideload_image_collection(self._collection_location, None)

        self._transaction.add_sync_preinstalled()

        try:
            self._progress = progress
            self._transaction.run()
        except GError as e:
            raise PayloadInstallationError("Failed to install flatpaks: {}".format(e)) from e
        finally:
            self._transaction.run_dispose()
            self._transaction = None
            self._progress = None

    def _create_flatpak_installation(self):
        return Installation.new_system(None)

    def _create_flatpak_transaction(self, installation):
        transaction = Transaction.new_for_installation(installation)
        transaction.connect("new_operation", self._operation_started_callback)
        transaction.connect("operation_done", self._operation_stopped_callback)
        transaction.connect("operation_error", self._operation_error_callback)

        return transaction

    def _operation_started_callback(self, transaction, operation, progress):
        """Start of the new operation.

        :param transaction: the main transaction object
        :type transaction: Flatpak.Transaction instance
        :param operation: object describing the operation
        :type operation: Flatpak.TransactionOperation instance
        :param progress: object providing progress of the operation
        :type progress: Flatpak.TransactionProgress instance
        """
        self._log_operation(operation, "started")
        self._report_progress(_("Installing {}").format(operation.get_ref()))

    def _operation_stopped_callback(self, transaction, operation, _commit, result):
        """Existing operation ended.

        :param transaction: the main transaction object
        :type transaction: Flatpak.Transaction instance
        :param operation: object describing the operation
        :type operation: Flatpak.TransactionOperation instance
        :param str _commit: operation was committed this is a commit id
        :param result: object containing details about the result of the operation
        :type result: Flatpak.TransactionResult instance
        """
        self._log_operation(operation, "stopped")

    def _operation_error_callback(self, transaction, operation, error, details):
        """Process error raised by the flatpak operation.

        :param transaction: the main transaction object
        :type transaction: Flatpak.Transaction instance
        :param operation: object describing the operation
        :type operation: Flatpak.TransactionOperation instance
        :param error: object containing error description
        :type error: GLib.Error instance
        :param details: information if the error was fatal
        :type details: int value of Flatpak.TransactionErrorDetails
        """
        self._log_operation(operation, "failed")
        log.error("Flatpak operation has failed with a message: '%s'", error.message)

    def _report_progress(self, message):
        """Report a progress message."""
        if not self._progress:
            return

        self._progress.report_progress(message)

    @staticmethod
    def _log_operation(operation, state):
        """Log a Flatpak operation."""
        operation_type_str = TransactionOperationType.to_string(operation.get_operation_type())
        log.debug("Flatpak operation: %s of ref %s state %s",
                  operation_type_str, operation.get_ref(), state)
