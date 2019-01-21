#
# Copyright (C) 2019  Red Hat, Inc.
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


class StorageSnapshot(object):
    """R/W snapshot of storage (i.e. a :class:`pyanaconda.storage.InstallerStorage` instance)"""

    def __init__(self, storage=None):
        """Create new instance of the class

        :param storage: if given, its snapshot is created
        :type storage: :class:`pyanaconda.storage.InstallerStorage`
        """
        if storage:
            self._storage_snap = storage.copy()
        else:
            self._storage_snap = None

    @property
    def storage(self):
        return self._storage_snap

    @property
    def created(self):
        return bool(self._storage_snap)

    def create_snapshot(self, storage):
        """Create (and save) snapshot of storage"""

        self._storage_snap = storage.copy()

    def dispose_snapshot(self):
        """Dispose (unref) the snapshot

        .. note::

            In order to free the memory taken by the snapshot, all references
            returned by :property:`self.storage` have to be unrefed too.
        """
        self._storage_snap = None

    def reset_to_snapshot(self, storage, dispose=False):
        """Reset storage to snapshot (**modifies :param:`storage` in place**)

        :param storage: :class:`pyanaconda.storage.InstallerStorage` instance to reset
        :param bool dispose: whether to dispose the snapshot after reset or not
        :raises ValueError: if no snapshot is available (was not created before)
        """
        if not self.created:
            raise ValueError("No snapshot created, cannot reset")

        # we need to create a new copy from the snapshot first -- simple
        # assignment from the snapshot would result in snapshot being modified
        # by further changes of 'storage'
        new_copy = self._storage_snap.copy()
        storage.devicetree = new_copy.devicetree
        storage.roots = new_copy.roots
        storage.fsset = new_copy.fsset

        if dispose:
            self.dispose_snapshot()


# A snapshot of early storage as we got it from scanning disks without doing any changes.
on_disk_storage = StorageSnapshot()
