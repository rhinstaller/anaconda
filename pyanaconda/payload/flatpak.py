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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import gi

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.progress import progressQ

gi.require_version("Flatpak", "1.0")
gi.require_version("Gio", "2.0")

from gi.repository.Flatpak import Transaction, Installation, Remote, RefKind, \
    TransactionOperationType
from gi.repository.Gio import File

log = get_module_logger(__name__)

__all__ = ["FlatpakPayload"]


class FlatpakPayload(object):
    """Main class to handle flatpak installation and management."""

    REMOTE_NAME = "Anaconda"

    def __init__(self, sysroot):
        """Create and initialize this class.

        This flatpak implementation works on a repository stored in the stage2 image specifically
        for the SilverBlue image. It will be used from the ostree payload after the installation.
        This is a temporal solution for SilverBlue use-case. It will be extended as full featured
        payload in the future.

        :param sysroot: path to the system root
        :type sysroot: str
        """
        self._remote_path = "/flatpak/repo"
        self._sysroot = sysroot
        self._remote_refs_list = None

        self._transaction = None

    @property
    def remote_path(self):
        """Path to the remote repository."""
        return self._remote_path

    @remote_path.setter
    def remote_path(self, value):
        """"Set path to the remote repository."""
        self.remote_path = value

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
        remote = self._create_flatpak_remote()

        installation = self._create_flatpak_installation(remote, target_path)

        self._transaction = self._create_flatpak_transaction(installation)
        self._remote_refs_list = RemoteRefsList(installation)

    def _create_flatpak_remote(self):
        remote = Remote.new(self.REMOTE_NAME)
        remote.set_gpg_verify(False)
        remote.set_url("file://{}".format(self.remote_path))

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

    def is_available(self):
        """Test if flatpak installation source is available.

        :return: bool
        """
        return os.path.isdir(self.remote_path)

    def get_required_size(self):
        """Get required size to install all the flatpaks.

        :returns: bytes required to install all flatpaks in the remote
        :rtype: int
        """
        return self._remote_refs_list.get_sum_installation_size()

    def install_all(self):
        """Install all the refs contained on the remote."""
        progressQ.send_message(_("Starting Flatpak installation"))
        self._stuff_refs_to_transaction()
        self._transaction.run()
        progressQ.send_message(_("Flatpak installation has finished"))

    def _stuff_refs_to_transaction(self):
        for ref in self._remote_refs_list.get_refs_in_install_format():
            self._transaction.add_install(self.REMOTE_NAME, ref, None)

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
        progressQ.send_message(_("Installing %(flatpak_name)s") %
                               {"flatpak_name": operation.get_ref()})

    def _operation_stopped_callback(self, transaction, operation, commit, result):
        """Existing operation ended.

        :param transaction: the main transaction object
        :type transaction: Flatpak.Transaction instance
        :param operation: object describing the operation
        :type operation: Flatpak.TransactionOperation instance
        :param str commit: operation was committed this is a commit id
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

    @staticmethod
    def _log_operation(operation, state):
        operation_type_str = TransactionOperationType.to_string(operation.get_operation_type())
        log.debug("Flatpak operation: %s of ref %s state %s",
                  operation_type_str, operation.get_ref(), state)


class RemoteRefsList(object):

    def __init__(self, installation):
        """Load all flatpak refs from the remote.

        :param installation: flatpak installation instance with remotes attached
        :type installation: Flatpak.Installation instance
        """
        self._installation = installation

        self._remote_refs = []

    @property
    def remote_refs(self):
        """Get list of remote flatpak applications refs."""
        if not self._remote_refs:
            self._load_remote_refs()

        return self._remote_refs

    def _load_remote_refs(self):
        """Load remote application references.

        This will load the list just once. We can do that because we support only one repository
        on the fixed place right now. This have to be re-implemented when there will be a proper
        flatpak support.
        """
        self._remote_refs = self._installation.list_remote_refs_sync(FlatpakPayload.REMOTE_NAME,
                                                                     None)

    def get_sum_installation_size(self):
        """Get sum of the installation size for all the flatpaks.

        :return: sum of bytes of the installation size of the all flatpaks
        :rtype: int
        """
        size_sum = 0
        for ref in self.remote_refs:
            size_sum = size_sum + ref.get_installed_size()

        return size_sum

    def get_refs_in_install_format(self):
        """Get list of strings used for the installation.

        Transaction object require to have refs for the installation in the correct format so
        create the correct format here.

        :return: list of refs in the correct format
        :rtype: [str]
        """
        result = []
        for ref in self.remote_refs:
            kind_type = "app" if ref.get_kind() is RefKind.APP else "runtime"
            # create ref string in format "runtime/org.example.app/x86_64/f30"
            result.append(kind_type + "/" +
                          ref.get_name() + "/" +
                          ref.get_arch() + "/" +
                          ref.get_branch())

        return result
