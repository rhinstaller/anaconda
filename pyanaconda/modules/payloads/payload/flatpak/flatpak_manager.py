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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
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
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task.progress import ProgressReporter
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.payload.flatpak.source import (
    FlatpakRegistrySource,
    FlatpakStaticSource,
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


# FIXME: Workaround for https://issues.redhat.com/browse/RHEL-85624 - remove when fixed
# We use this when disabling downloads. .invalid URLS are
# guaranteed not to resolve by RFC 2606
INVALID_DOWNLOAD_URL = 'oci+https://no-download.invalid'


class FlatpakManager:
    """Root object for handling Flatpak pre-installation"""

    def __init__(self):
        """Create and initialize this class.

        :param function callback: a progress reporting callback
        """
        self._flatpak_refs = []

        self._source = None
        self._skip_installation = True
        # location of the local installation source ready for installation in flatpak format
        self._collection_location = None
        self._progress: Optional[ProgressReporter] = None
        self._transaction = None
        self._download_location = None
        self._download_size = 0
        self._install_size = 0

    @property
    def flatpak_refs(self):
        """Get required flatpak refs for installation.

        :returns: list of refs
        :rtype: list
        """
        return self._flatpak_refs

    @property
    def skip_installation(self):
        """Report if the installation of Flatpaks will be skipped.

        :returns: True if the installation should be skipped
        :rtype: bool
        """
        return self._skip_installation

    def set_sources(self, sources: List[PayloadSourceBase]):
        """Set the source object we use to download Flatpak content.

        If unset, pre-installation will install directly from the configured
        Flatpak remote (see flatpak_remote in the anaconda configuration).

        :param sources: List of sources from the DNF payload (only supported now)
        """
        # TODO: We need to add Flatpak own source type so we can expect
        # something specific here not just any source

        if not sources:
            return

        # Take the first source as that is the base source from the DNF repository list.
        # We expect that the URL of the base DNF repository is source of the Flatpak repository.
        source = sources[0]

        log.debug("FlatpakManager: set_sources: %s", source)
        # Decide how we want to process the main payload source to use the URL of the source
        # for that we need to know that this is Repository source so we know what we can do
        if source.type in (SourceType.CDN, SourceType.CLOSEST_MIRROR):
            if self._source and isinstance(self._source, FlatpakRegistrySource):
                log.debug("Skipping registry source: %s as it is already set.", source)
                return
            _, remote_url = conf.payload.flatpak_remote
            log.debug("Using Flatpak registry source: %s", remote_url)
            self._source = FlatpakRegistrySource(remote_url)
        elif isinstance(source, RepositorySourceMixin) or source.type in (SourceType.REPO_PATH, SourceType.CDROM):
            # synchronize input for FlatpakStaticSource from different DNF input sources
            # TODO: when CDN installations are supported, prefer installing from online sources as the packages
            # would be more up to date
            if source.type in (SourceType.REPO_PATH, SourceType.CDROM):
                repository = source.generate_repo_configuration()
            else:
                repository = source.repository

            # verify this Flatpak source is already created and used
            if self._source and isinstance(self._source, FlatpakStaticSource) \
                    and self._source.repository_config == source.repository:
                log.debug("Skipping static source from repo: %s as it is already set.", source)
                return
            log.debug("Using FlatpakStaticSource from repository: %s", repository)
            self._source = FlatpakStaticSource(repository, relative_path="Flatpaks")
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

        log.debug("Flatpak refs which will get installed: %s", self._flatpak_refs)

    def set_download_location(self, path: str):
        """Sets a location that can be used for temporary download of Flatpak content.

        :param path: Path to directory we will use to download flatpaks into
        """
        log.debug("Flatpak download location set to: %s", path)
        self._download_location = path

    @property
    def download_location(self) -> str:
        """Get the download location."""
        return self._download_location

    def get_source(self):
        """Retrieve flatpak source."""
        if self._source is None:
            _, remote_url = conf.payload.flatpak_remote
            log.debug("Using Flatpak registry source: %s", remote_url)
            self._source = FlatpakRegistrySource(remote_url)

        return self._source

    def calculate_size(self):
        """Calculate the download and install size of the Flatpak content.

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
                self.get_source().calculate_size(self._flatpak_refs)
        except SourceSetupError as e:
            log.error("Flatpak source not available, skipping size calculation %s: %s",
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

        This is only needed if Flatpak can't install the content directly. This happens when
        the Flatpaks are available remotely on HTTP/FTP etc. repository.
        This method is not necessary when installing from Flatpak repository or offline local
        installation.
        """
        if self._skip_installation:
            log.debug("Flatpak download is going to be skipped.")
            return

        if len(self._flatpak_refs) == 0:
            log.debug("No flatpaks are marked for download.")
            return

        try:
            # pylint: disable=assignment-from-none
            self._collection_location = self.get_source().download(self._flatpak_refs,
                                                                   self._download_location,
                                                                   progress)
        except SourceSetupError as e:
            log.error("Flatpak source not available, skipping download %s: %s",
                      ", ".join(self._flatpak_refs), e)
            self._skip_installation = True

    def install(self, progress: ProgressReporter):
        """Install the Flatpak content to the target system.

        :param progress: used to report progress of the operation
        """
        if self._skip_installation:
            log.debug("Flatpak install is going to be skipped.")
            return

        if len(self._flatpak_refs) == 0:
            log.debug("No flatpaks are marked for install.")
            return

        log.debug("Installing Flatpaks")

        installation = self._create_flatpak_installation()
        saved_urls = None

        try:
            if self._collection_location:
                # If we're installing from a local source, we need to disable
                # loading the list of current Flatpaks from the network - we
                # want to install what was in the install image even if it is
                # out of date.
                saved_urls = self._disable_network_download(installation)

            self._transaction = self._create_flatpak_transaction(installation)

            if self._collection_location:
                self._transaction.add_sideload_image_collection(self._collection_location, None)

            # Add to the Flatpak transaction all Flatpaks and runtimes marked for
            # installation by preinstall.d Flatpak feature
            # See https://github.com/flatpak/flatpak/issues/5579
            self._transaction.add_sync_preinstalled()

            self._progress = progress
            self._transaction.run()
        except GError as e:
            raise PayloadInstallationError("Failed to install flatpaks: {}".format(e)) from e
        finally:
            if self._transaction:
                self._transaction.run_dispose()
                self._transaction = None

            if saved_urls:
                self._reenable_network_download(installation, saved_urls)

            self._progress = None

    def _create_flatpak_installation(self):
        return Installation.new_system(None)

    def _create_flatpak_transaction(self, installation):
        transaction = Transaction.new_for_installation(installation)
        transaction.connect("new_operation", self._operation_started_callback)
        transaction.connect("operation_done", self._operation_stopped_callback)
        transaction.connect("operation_error", self._operation_error_callback)

        return transaction

    # FlatpakTransaction.set_no_pull() does not leave sideload
    # repositories working - it basically entirely disables all
    # remote handling. So we have to resort to an uglier
    # workaround for now.
    # https://issues.redhat.com/browse/RHEL-85624

    def _disable_network_download(self, installation):
        # Temporary workaround for https://issues.redhat.com/browse/RHEL-85624
        saved_urls = {}
        for remote in installation.list_remotes():
            old_url = remote.get_url()
            if old_url.startswith("oci+https:"):
                saved_urls[remote.get_name()] = old_url
                remote.set_url(INVALID_DOWNLOAD_URL)
                installation.modify_remote(remote)

        return saved_urls

    def _reenable_network_download(self, installation, saved_urls):
        # Temporary workaround for https://issues.redhat.com/browse/RHEL-85624
        for remote in installation.list_remotes():
            old_url = saved_urls.get(remote.get_name())
            if old_url:
                remote.set_url(old_url)
                installation.modify_remote(remote)

    def _operation_started_callback(self, transaction, operation, progress):
        """Start of the new operation.

        This callback is called when a new operation is started in the Transaction set.

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

        This callback is called when an operation in the Transaction set was stopped.

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

        This callback is called when an operation in the Transaction set has failed.

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
