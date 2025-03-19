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
import collections
import time

import dnf
import dnf.callback
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core.i18n import _
from pyanaconda.progress import progressQ

log = get_packaging_logger()

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
    def __init__(self):
        super().__init__()
        self.downloads = collections.defaultdict(int)
        self.last_time = time.time()
        self.total_files = 0
        self.total_size = Size(0)

    @paced
    def _update(self):
        msg = _('Downloading %(total_files)s RPMs, '
                '%(downloaded)s / %(total_size)s (%(percent)d%%) done.')
        downloaded = Size(sum(self.downloads.values()))
        vals = {
            'downloaded': downloaded,
            'percent': int(100 * downloaded / self.total_size),
            'total_files': self.total_files,
            'total_size': self.total_size
        }
        progressQ.send_message(msg % vals)

    def end(self, dnf_payload, status, msg):  # pylint: disable=arguments-differ
        nevra = str(dnf_payload)
        if status is dnf.callback.STATUS_OK:
            self.downloads[nevra] = dnf_payload.download_size
            self._update()
            return
        log.warning("Failed to download '%s': %d - %s", nevra, status, msg)

    def progress(self, dnf_payload, done):  # pylint: disable=arguments-differ
        nevra = str(dnf_payload)
        self.downloads[nevra] = done
        self._update()

    # TODO: Remove pylint disable after DNF-2.5.0 will arrive in Fedora
    def start(self, total_files, total_size, total_drpms=0):  # pylint: disable=arguments-differ
        self.total_files = total_files
        self.total_size = Size(total_size)
