#
# Copyright (C) 2021  Red Hat, Inc.
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
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _

__all__ = ["DownloadProgress"]

log = get_module_logger(__name__)


class DownloadProgress:
    """Provide methods for image download progress reporting."""

    def __init__(self, url, total_size, callback):
        """Create a new progress reporter.

        :param str url: an URL of the image to download
        :param inst total_size: a total size to download in bytes
        :param callback: a function for the progress reporting
        """
        self._url = url
        self._last_pct = -1
        self._downloaded_size = 0
        self._total_size = total_size
        self._callback = callback

    def _report_progress(self):
        """Report the progress."""
        pct = min(int(100 * self._downloaded_size / self._total_size), 100)

        if pct == self._last_pct:
            return

        self._last_pct = pct

        log.debug("Downloaded %s (%s%%)", Size(self._downloaded_size), pct)
        self._callback(_("Downloading {} ({}%)").format(self._url, pct))

    def start(self):
        """Start the download progress."""
        self._downloaded_size = 0
        self._report_progress()

    def update(self, downloaded_size):
        """Update the download progress.

        :param int downloaded_size: a size in bytes
        """
        self._downloaded_size = downloaded_size
        self._report_progress()

    def end(self):
        """Finish the download progress."""
        self._downloaded_size = self._total_size
        self._report_progress()
