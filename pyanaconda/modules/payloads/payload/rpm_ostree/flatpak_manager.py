#
# Setup and install Flatpaks to the prepared (installed) system.
#
# Copyright (C) 2019  Red Hat, Inc.
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
from abc import ABC, abstractmethod

import gi

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.glib import Bytes, GError, Variant, VariantType
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.installation import PayloadInstallationError

gi.require_version("Flatpak", "1.0")
gi.require_version("Gio", "2.0")

from gi.repository.Flatpak import (
    Installation,
    Remote,
    Transaction,
    TransactionOperationType,
)
from gi.repository.Gio import File

log = get_module_logger(__name__)

__all__ = ["FlatpakManager"]


class FlatpakManager:
    """Main class to handle flatpak installation and management."""

    LOCAL_REMOTE_NAME = "Anaconda"
    LOCAL_REMOTE_PATH = "file:///flatpak/repo"

    def __init__(self, sysroot, callback=None):
        """Create and initialize this class.

        This flatpak implementation works on a repository stored in the stage2 image specifically
        for the SilverBlue image. It will be used from the ostree payload after the installation.
        This is a temporal solution for SilverBlue use-case. It will be extended as full featured
        payload in the future.

        :param str sysroot: path to the system root
        :param function callback: a progress reporting callback
        """
        self._sysroot = sysroot
        self._remote_refs_list = None
        self._transaction = None
        self._callback = callback

    def initialize_with_system_path(self):
        """Create flatpak objects and set them to install to the result system.

        This call will re-initialize current settings so everything set here will be cleaned.
        """
        target_path = os.path.join(self._sysroot, "var/lib/flatpak")
        self.initialize_with_path(target_path)

    def initialize_with_path(self, target_path):
        """Create flatpak objects and set them for the given target path.

        The initialization process will create a repository on the given path.

        This call will re-initialize current settings so everything set here will be cleaned.

        :param str target_path: path where we want to install flatpaks
        """
        log.debug("Configure flatpak for path %s", target_path)
        remote = self._create_flatpak_remote(self.LOCAL_REMOTE_NAME, self.LOCAL_REMOTE_PATH, False)

        installation = self._create_flatpak_installation(remote, target_path)

        self._transaction = self._create_flatpak_transaction(installation)
        self._remote_refs_list = RemoteRefsList(installation)

    def _create_flatpak_remote(self, name, path, gpg_verify):
        remote = Remote.new(name)
        remote.set_gpg_verify(gpg_verify)
        remote.set_url(path)

        return remote

    def _create_flatpak_installation(self, remote, target_path):
        install_path = File.new_for_path(target_path)
        installation = Installation.new_for_path(install_path, False, None)
        installation.add_remote(remote, False, None)

        return installation

    def _create_flatpak_transaction(self, installation):
        transaction = Transaction.new_for_installation(installation)
        transaction.connect("new_operation", self._operation_started_callback)
        transaction.connect("operation_done", self._operation_stopped_callback)
        transaction.connect("operation_error", self._operation_error_callback)

        return transaction

    def cleanup(self):
        """Clean the current repository and settings.

        One of the initialize methods have to be called before the flatpak object can be
        used again.
        """
        log.debug("Cleaning up flatpak repository")
        if self._transaction:
            path = self._transaction.get_installation().get_path()
            path = path.get_path()  # unpack the Gio.File

            if os.path.exists(path):
                log.debug("Removing flatpak repository %s", path)
                shutil.rmtree(path)

        self._transaction = None

    @classmethod
    def is_source_available(cls):
        """Test if flatpak installation source is available.

        :return: bool
        """
        # Remove the file:// prefix
        return os.path.isdir(cls.LOCAL_REMOTE_PATH[7:])

    def get_required_size(self):
        """Get required size to install all the flatpaks.

        :returns: bytes required to install all flatpaks in the remote
        :rtype: int
        """
        return self._remote_refs_list.get_sum_installation_size()

    def add_remote(self, name, url):
        """Add a new remote to the existing installation.

        :param str name: name of the remote
        :param str url: url pointing to the remote (use file:// for local paths)
        """
        log.debug("Adding a new flatpak remote %s: %s", name, url)
        remote = self._create_flatpak_remote(name, url, True)

        installation = self._transaction.get_installation()
        installation.add_remote(remote, True, None)

    def remove_remote(self, name):
        """Remove remote from the existing installation.

        :param str name: Name of the remote to remove.
        """
        log.debug("Removing a flatpak remote %s", name)
        installation = self._transaction.get_installation()

        for remote in installation.list_remotes():
            if remote.get_name() == name:
                installation.remove_remote(name, None)
                log.debug("Flatpak remote %s removed", name)

    def install_all(self):
        """Install all the refs contained on the remote."""
        self._stuff_refs_to_transaction()

        try:
            self._transaction.run()
        except GError as e:
            raise PayloadInstallationError("Failed to install flatpaks: {}".format(e)) from e

    def _stuff_refs_to_transaction(self):
        for ref in self._remote_refs_list.get_refs_full_format():
            self._transaction.add_install(self.LOCAL_REMOTE_NAME, ref, None)

    def replace_installed_refs_remote(self, new_remote):
        """Replace remote on all the installed refs.

        :param str new_remote: name of the new remote
        """
        installed_refs_list = InstalledRefsList(self._transaction.get_installation())

        installed_refs_list.replace_installed_refs_remote(new_remote)

    def _operation_started_callback(self, transaction, operation, progress):
        """Start of the new operation.

        :param transaction: the main transaction object
        :type transaction: Flatpak.Transaction instance
        :param operation: object describing the operation
        :type operation: Flatpak.TransactionOperation instance
        :param progress: object providing progess of the operation
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
        if not self._callback:
            return

        self._callback(message)

    @staticmethod
    def _log_operation(operation, state):
        """Log a Flatpak operation."""
        operation_type_str = TransactionOperationType.to_string(operation.get_operation_type())
        log.debug("Flatpak operation: %s of ref %s state %s",
                  operation_type_str, operation.get_ref(), state)


class BaseRefsList(ABC):

    def __init__(self, installation):
        """Load all flatpak refs from the installed system.

        Makes easier operations above the refs.

        :param installation: flatpak installation instance with remotes attached
        :type installation: Flatpak.Installation instance
        """
        self._installation = installation

        self._refs = []

    @property
    def refs(self):
        """Get list of installed application refs."""
        if not self._refs:
            self._load_refs()

        return self._refs

    @abstractmethod
    def _load_refs(self):
        pass

    def get_refs_full_format(self):
        """Get list of refs in full format.

        This formatting is used for example for installation.
        The format looks like:

        [app|runtime]/ref/arch/branch

        examples:
        runtime/org.videolan.VLC.Plugin.bdj/x86_64/3-18.08
        app/org.gnome.Gnote/x86_64/stable

        :return: list of refs in the full format
        :rtype: [str]
        """
        result = []
        for ref in self.refs:
            # create ref string in format "runtime/org.example.app/x86_64/f30"
            result.append(ref.format_ref())

        return result


class RemoteRefsList(BaseRefsList):

    def _load_refs(self):
        """Load remote application references.

        This will load the list just once. We can do that because we support only one repository
        on the fixed place right now. This have to be re-implemented when there will be a proper
        flatpak support.
        """
        self._refs = self._installation.list_remote_refs_sync(
            FlatpakManager.LOCAL_REMOTE_NAME,
            None)

    def get_sum_installation_size(self):
        """Get sum of the installation size for all the flatpaks.

        :return: sum of bytes of the installation size of the all flatpaks
        :rtype: int
        """
        size_sum = 0
        for ref in self.refs:
            size_sum = size_sum + ref.get_installed_size()

        return size_sum


class InstalledRefsList(BaseRefsList):

    FLATPAK_DEPLOY_DATA_GVARIANT_STRING = '(ssasta{sv})'

    def _load_refs(self):
        self._refs = self._installation.list_installed_refs()

    def replace_installed_refs_remote(self, new_remote_name):
        """Replace remote for all the refs.

        :param str new_remote_name: the remote name which will be used instead of the current one
        """
        install_path = self._installation.get_path()
        install_path = install_path.get_path()  # unpack the Gio.File

        variant_type = VariantType(self.FLATPAK_DEPLOY_DATA_GVARIANT_STRING)

        for ref in self.get_refs_full_format():
            deploy_path = os.path.join(install_path, ref, "active/deploy")

            with open(deploy_path, "rb") as f:
                content = f.read()

            variant = Variant.new_from_bytes(variant_type, Bytes(content), False)
            children = [variant.get_child_value(i) for i in range(variant.n_children())]
            # Replace the origin
            children[0] = Variant('s', new_remote_name)
            new_variant = Variant.new_tuple(*children)
            serialized = new_variant.get_data_as_bytes().get_data()

            with open(deploy_path, "wb") as f:
                f.write(serialized)
