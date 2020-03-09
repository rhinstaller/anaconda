#
# Installation tasks
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
from datetime import timedelta
from time import sleep

from blivet import callbacks
from blivet.errors import FSResizeError, FormatResizeError, StorageError
from blivet.util import get_current_entropy

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.errors.installation import StorageInstallationError
from pyanaconda.modules.common.task import Task
from pyanaconda.storage.installation import turn_on_filesystems, write_storage_configuration

log = get_module_logger(__name__)


__all__ = ["ActivateFilesystemsTask", "MountFilesystemsTask", "WriteConfigurationTask"]


class ActivateFilesystemsTask(Task):
    """Installation task for activation of the storage configuration."""

    def __init__(self, storage, entropy_timeout=600):
        """Create a new task.

        :param storage: the storage model
        :param entropy_timeout: a number of seconds for entropy gathering
        """
        super().__init__()
        self._storage = storage
        self._entropy_timeout = entropy_timeout

    @property
    def name(self):
        return "Activate filesystems"

    def run(self):
        """Do the activation.

        :raise: StorageInstallationError if the activation fails
        """
        if conf.target.is_directory:
            log.debug("Don't activate file systems during "
                      "the installation to a directory.")
            return

        register = callbacks.create_new_callbacks_register(
            create_format_pre=self._report_message,
            resize_format_pre=self._report_message,
            wait_for_entropy=self._wait_for_entropy
        )

        try:
            turn_on_filesystems(
                self._storage,
                callbacks=register
            )
        except (FSResizeError, FormatResizeError) as e:
            log.error("Failed to resize device %s: %s", e.details, str(e))
            message = _("An error occurred while resizing the device {}: {}").format(
                e.details, str(e)
            )
            raise StorageInstallationError(message) from None
        except StorageError as e:
            log.error("Failed to activate filesystems: %s", str(e))
            raise StorageInstallationError(str(e)) from None

    def _report_message(self, data):
        """Report a Blivet message.

        :param data: Blivet's callback data
        """
        self.report_progress(data.msg)

    def _wait_for_entropy(self, data):
        """Wait for entropy.

        :param data: Blivet's callback data
        :return: True if we are out of time, otherwise False
        """
        log.debug(data.msg)
        required_entropy = data.min_entropy
        total_time = self._entropy_timeout
        current_time = 0

        while True:
            # Report the current status.
            current_entropy = get_current_entropy()
            current_percents = min(int(current_entropy / required_entropy * 100), 100)
            remaining_time = max(total_time - current_time, 0)
            self._report_entropy_message(current_percents, remaining_time)

            sleep(5)
            current_time += 5

            # Enough entropy gathered.
            if current_percents == 100:
                return False

            # Out of time.
            if remaining_time == 0:
                return True

    def _report_entropy_message(self, percents, time):
        """Report an entropy message.

        :param percents: the percentage of gathered entropy
        :param time: a number of seconds of remaining time
        """
        if percents == 100:
            self.report_progress(_("Gathering entropy 100%"))
            return

        if time == 0:
            self.report_progress(_("Gathering entropy (time ran out)"))
            return

        message = _("Gathering entropy {percents}% (remaining time {time})").format(
            percents=percents,
            time=timedelta(seconds=time)
        )

        self.report_progress(message)


class MountFilesystemsTask(Task):
    """Installation task for mounting the filesystems."""

    def __init__(self, storage):
        """Create a new task."""
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Mount filesystems"

    def run(self):
        """Mount the filesystems."""
        self._storage.mount_filesystems()


class WriteConfigurationTask(Task):
    """Installation task for writing out the storage configuration."""

    def __init__(self, storage):
        """Create a new task."""
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Write the storage configuration"

    def run(self):
        """Mount the filesystems."""
        if conf.target.is_directory:
            log.debug("Don't write the storage configuration "
                      "during the installation to a directory.")
            return

        write_storage_configuration(self._storage)
