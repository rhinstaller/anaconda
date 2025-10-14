#
# Copyright (C) 2020  Red Hat, Inc.
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
import libdnf5

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.installation import PayloadInstallationError

log = get_module_logger(__name__)

__all__ = ["TransactionProgress", "process_transaction_progress"]


def process_transaction_progress(queue, callback):
    """Process the transaction progress.

    When the installation works correctly it will end by 'quit' token.

    :param queue: a process shared queue
    :param callback: a callback for progress reporting
    :raise PayloadInstallationError: if the transaction fails
    """
    (token, msg) = queue.get()

    while token:
        if token == 'install':
            callback(_("Installing {}").format(msg))
        elif token == 'configure':
            callback(_("Configuring {}").format(msg))
        elif token == 'log':
            log.info(msg)
        elif token == 'post':
            callback(_("Performing post-installation setup tasks"))
        elif token == 'quit':
            log.info(msg)
            break  # Installation finished successfully
        elif token == 'error':
            log.error(msg)
            raise PayloadInstallationError("An error occurred during the transaction: " + msg)

        (token, msg) = queue.get()


class TransactionProgress(libdnf5.rpm.TransactionCallbacks):
    """The class for receiving information about an ongoing transaction."""

    def __init__(self, queue):
        """Create a new instance.

        :param queue: a process shared queue
        """
        super().__init__()
        self._queue = queue
        self.installed_amount = 0
        self.installed_total = 0

    def before_begin(self, total):
        self.installed_total = total
        log.debug("Starting the installation. Total packages: %s", total)

    def install_start(self, item, total):
        package = item.get_package()
        log.debug("Installing - %s", package.to_string())
        self.installed_amount += 1
        self._queue.put((
            'install',
            "{name}.{arch} ({amount}/{total})".format(
                name=package.get_name(),
                arch=package.get_arch(),
                amount=self.installed_amount,
                total=self.installed_total
            )
        ))

    def verify_progress(self, amount, total):
        log.debug("Verify %s/%s", amount, total)
        self._queue.put(('verify', 'packages'))

    def script_start(self, item, nevra, type):  # pylint: disable=redefined-builtin
        log.debug(
            "Configuring - %s, %s, %s",
            # In case of the script_start callback, the item can be a nullpointer.
            # There reason is some scriptlets (namely file triggers) can be run for a package
            # that is not part of the transaction.
            item.get_package().to_string() if item else "unknown",
            libdnf5.rpm.to_full_nevra_string(nevra),
            libdnf5.rpm.TransactionCallbacks.script_type_to_string(type)
        )
        self._queue.put(('configure', "%s.%s" % (nevra.get_name(), nevra.get_arch())))

    def after_complete(self, success):
        log.debug("Done - %s", success)
        self._queue.put(('done', None))

    def cpio_error(self, item):
        log.debug("Error - %s", item.get_package().to_string())
        self._queue.put(('error', item.get_package().to_string()))

    def script_error(self, item, nevra, type, return_code):  # pylint: disable=redefined-builtin
        log.debug(
            "Error - %s, %s, %s, %s",
            # In case of the script_error callback, the item can be a nullpointer.
            # There reason is some scriptlets (namely file triggers) can be run for a package
            # that is not part of the transaction.
            item.get_package().to_string() if item else "unknown",
            libdnf5.rpm.to_full_nevra_string(nevra),
            libdnf5.rpm.TransactionCallbacks.script_type_to_string(type),
            return_code
        )
        self._queue.put(('error', item.get_package().to_string()))

    def unpack_error(self, item):
        log.debug("Error - %s", item.get_package().to_string())
        self._queue.put(('error', item.get_package().to_string()))

    def error(self, message):
        """Report an error that occurred during the transaction.

        :param message: a string that describes the error
        """
        self._queue.put(('error', message))

    def quit(self, message):
        """Report the end of the transaction and close the queue.

        :param message: the reason why the transaction ended
        """
        self._queue.put(('quit', message))
        self._queue.close()
