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

import dnf
import dnf.callback

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


class DownloadProgress(dnf.callback.DownloadProgress):
    """The class for receiving information about an ongoing download."""

    def __init__(self, callback):
        """Create a new instance.

        :param callback: a progress reporting callback
        """
        super().__init__()
        self.callback = callback
        self.downloads = collections.defaultdict(int)
        self.last_time = time.time()
        self.total_files = 0
        self.total_size = Size(0)
        self.downloaded_size = Size(0)

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
            total_percent=int(100 * self.downloaded_size / self.total_size),
            total_files=self.total_files,
            total_size=self.total_size
        )

        self.callback(msg)

    def end(self, payload, status, msg):
        nevra = str(payload)

        if status is dnf.callback.STATUS_OK:
            self.downloads[nevra] = payload.download_size
            self._report_progress()
            return

        log.warning("Failed to download '%s': %d - %s", nevra, status, msg)

    def progress(self, payload, done):
        nevra = str(payload)
        self.downloads[nevra] = done
        self._report_progress()

    def start(self, total_files, total_size, total_drpms=0):
        del total_drpms
        self.total_files = total_files
        self.total_size = Size(total_size)
