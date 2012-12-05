# User interface library functions for filesystem/disk space checking
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

from pyanaconda.storage.size import Size

import gettext

_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

import logging
log = logging.getLogger("anaconda")

class FileSystemSpaceChecker(object):
    error_template = N_("Not enough space in filesystems for the current "
                        "software selection. An additional %s is needed.")

    def __init__(self, storage, payload):
        self.payload = payload
        self.storage = storage

        self.reset()

    def reset(self):
        self.success = False
        self.deficit = Size(bytes=0)
        self.error_message = ""

    def check(self):
        self.reset()
        free = Size(spec="%.2f MB" % self.storage.fileSystemFreeSpace)
        needed = self.payload.spaceRequired
        log.info("fs space: %s  needed: %s" % (free, needed))
        self.success = (free >= needed)
        if not self.success:
            self.deficit = needed - free
            self.error_message = _(self.error_template) % self.deficit

        return self.success
