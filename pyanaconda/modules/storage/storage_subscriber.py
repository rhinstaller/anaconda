#
# Copyright (C) 2023 Red Hat, Inc.
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
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.errors.storage import UnavailableStorageError


class StorageSubscriberModule(KickstartBaseModule):
    """Kickstart module that keeps track of storage."""

    def __init__(self):
        super().__init__()
        self._storage = None

    @property
    def storage(self):
        """The storage model.

        :return: an instance of Blivet
        """
        if self._storage is None:
            raise UnavailableStorageError()

        return self._storage

    def on_storage_changed(self, storage):
        """Keep the instance of the current storage."""
        self._storage = storage
