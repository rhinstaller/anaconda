# tarpayload.py
# Tar archive software payload management.
#
# Copyright (C) 2012  Red Hat, Inc.
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
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#

"""
    TODO
        - error handling!!!
        - document all methods

"""

import logging
log = logging.getLogger("anaconda")

try:
    import tarfile
except ImportError:
    log.error("import of tarfile failed")
    tarfile = None

from pyanaconda.packaging import ArchivePayload, PayloadError, versionCmp
from pyanaconda import iutil

# TarPayload is not yet fully implemented
# pylint: disable=abstract-method
class TarPayload(ArchivePayload):
    """ A TarPayload unpacks a single tar archive onto the target system. """
    def __init__(self, data):
        if tarfile is None:
            raise PayloadError("unsupported payload type")

        super(TarPayload, self).__init__(data)
        self.archive = None
        self.image_file = None

    def setup(self, storage, instClass):
        super(TarPayload, self).setup(storage, instClass)

        try:
            self.archive = tarfile.open(self.image_file)
        except (tarfile.ReadError, tarfile.CompressionError) as e:
            # maybe we only need to catch ReadError and CompressionError here
            log.error("opening tar archive %s: %s", self.image_file, e)
            raise PayloadError("invalid payload format")

    def unsetup(self):
        super(TarPayload, self).unsetup()
        self.archive = None

    @property
    def requiredSpace(self):
        byte_count = sum(m.size for m in self.archive.getmembers())
        return byte_count / (1024.0 * 1024.0)   # FIXME: Size

    @property
    def kernelVersionList(self):
        names = self.archive.getnames()

        # Strip out vmlinuz- from the names
        return sorted((n.split("/")[-1][8:] for n in names if "boot/vmlinuz-" in n),
                cmp=versionCmp)

    def install(self):
        try:
            self.archive.extractall(path=iutil.getSysroot())
        except (tarfile.ExtractError, tarfile.CompressionError) as e:
            log.error("extracting tar archive %s: %s", self.image_file, e)

