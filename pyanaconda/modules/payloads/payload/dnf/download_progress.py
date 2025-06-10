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
import time

import libdnf5
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _

log = get_module_logger(__name__)

__all__ = ["DownloadProgress"]


def paced(fn):
    """Execute `fn` no more often then every 2 seconds."""
    def paced_fn(self, *args):
        now = time.time()
        if now - self.last_time < 2:
            return
        self.last_time = now
        return fn(self, *args)
    return paced_fn


class DownloadProgress(libdnf5.repo.DownloadCallbacks):
    """The class for receiving information about an ongoing download."""

    def __init__(self, callback):
        """Create a new instance.

        :param callback: a progress reporting callback
        """
        super().__init__()
        self.callback = callback
        self.user_cb_data_container = []  # Hold references to user_cb_data
        self.last_time = time.time()  # Used to pace _report_progress
        self.total_files = 0
        self.total_size = Size(0)
        self.downloads = {}  # Hold number of bytes downloaded for each nevra
        self.downloaded_size = 0

    def add_new_download(self, user_data, description, total_to_download):
        """Notify the client that a new download has been created.

        :param user_data: user data entered together with a package to download
        :param str description: a message describing the package
        :param float total_to_download: a total number of bytes to download
        :return: associated user data for the new package download
        """
        self.user_cb_data_container.append(description)
        self.total_files += 1
        self.total_size += total_to_download
        log.debug("Started downloading '%s' - %s bytes", description, total_to_download)
        self._report_progress()
        return len(self.user_cb_data_container) - 1

    def progress(self, user_cb_data, total_to_download, downloaded):
        """Download progress callback.

        :param user_cb_data: associated user data obtained from add_new_download
        :param float total_to_download: a total number of bytes to download
        :param float downloaded: a number of bytes downloaded
        """
        nevra = self.user_cb_data_container[user_cb_data]
        self.downloads[nevra] = downloaded

        if total_to_download > 0:
            self._report_progress()

        return 0  # Not used, but int is expected to be returned.

    def end(self, user_cb_data, status, msg):
        """End of download callback.

        :param user_cb_data: associated user data obtained from add_new_download
        :param status: the transfer status
        :param msg: the error message in case of error
        """
        nevra = self.user_cb_data_container[user_cb_data]

        if status is libdnf5.repo.DownloadCallbacks.TransferStatus_SUCCESSFUL:
            log.debug("Downloaded '%s'", nevra)
            self._report_progress()
        elif status is libdnf5.repo.DownloadCallbacks.TransferStatus_ALREADYEXISTS:
            log.debug("Skipping to download '%s': %s", nevra, msg)
            self._report_progress()
        else:
            log.warning("Failed to download '%s': %s", nevra, msg)

        return 0  # Not used, but int is expected to be returned.

    @paced
    def _report_progress(self):
        # Update the downloaded size.
        self.downloaded_size = Size(sum(self.downloads.values()))

        # Report the progress.
        msg = _(
            'Downloading {total_files} RPMs, '
            '{downloaded_size} / {total_size} '
            '({total_percent}%) done.'
        ).format(
            downloaded_size=self.downloaded_size,
            total_percent=int(100 * int(self.downloaded_size) / int(self.total_size)),
            total_files=self.total_files,
            total_size=self.total_size
        )

        self.callback(msg)
