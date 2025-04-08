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
from pyanaconda.core.i18n import _
from pyanaconda.progress import progressQ

__all__ = ["DownloadProgress"]


class DownloadProgress(object):
    """ Provide methods for download progress reporting."""

    def __init__(self):
        self.url = ""
        self.size = 0
        self._pct = -1

    def start(self, url, size):
        """ Start of download

            :param url:      url of the download
            :type url:       str
            :param size:     length of the file
            :type size:      int
        """
        self.url = url
        self.size = size
        self._pct = -1

    def update(self, bytes_read):
        """ Download update

            :param bytes_read: Bytes read so far
            :type bytes_read:  int
        """
        if not bytes_read:
            return
        pct = min(100, int(100 * bytes_read / self.size))

        if pct == self._pct:
            return
        self._pct = pct
        progressQ.send_message(_("Downloading %(url)s (%(pct)d%%)") %
                               {"url": self.url, "pct": pct})

    def end(self, bytes_read):
        """ Download complete

            :param bytes_read: Bytes read so far
            :type bytes_read:  int
        """
        progressQ.send_message(_("Downloading %(url)s (%(pct)d%%)") %
                               {"url": self.url, "pct": 100})
