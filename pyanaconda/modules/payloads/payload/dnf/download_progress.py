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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import collections
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

    def add_new_download(self, user_data, description, total_to_download):
        """Notify the client that a new download has been created.

        :param user_data: user data entered together with a package to download
        :param str description: a message describing the package
        :param float total_to_download: a total number of bytes to download
        :return: associated user data for the new package download
        """
        self._report_progress("Downloading {} - {} bytes".format(
            description, total_to_download
        ))
        return description

    def progress(self, user_cb_data, total_to_download, downloaded):
        """Download progress callback.

        :param user_cb_data: associated user data obtained from add_new_download
        :param float total_to_download: a total number of bytes to download
        :param float downloaded: a number of bytes downloaded
        """
        self._report_progress("Downloading {} - {}/{} bytes".format(
                user_cb_data, downloaded, total_to_download
        ))

    def end(self, user_cb_data, status, msg):
        """End of download callback.

        :param user_cb_data: associated user data obtained from add_new_download
        :param status: the transfer status
        :param msg: the error message in case of error
        """
        self._report_progress("Downloaded {} - {} ({})".format(
            user_cb_data, status, msg
        ))

    def _report_progress(self, msg):
        log.debug(msg)
        self.callback(msg)
