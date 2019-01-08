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
from pyanaconda.bootloader.execution import BootloaderExecutor

__all__ = ["do_kickstart_storage"]


def do_kickstart_storage(storage, data):
    """Setup storage state from the kickstart data.

    :param storage: an instance of the Blivet's storage object
    :param data: an instance of kickstart data
    """
    # Clear partitions.
    data.clearpart.execute(storage, data)

    if not any(d for d in storage.disks
               if not d.format.hidden and not d.protected):
        return

    # Snapshot free space now, so that we know how much we had available.
    storage.create_free_space_snapshot()

    # Prepare the boot loader.
    BootloaderExecutor().execute(storage, dry_run=True)

    data.autopart.execute(storage, data)
    data.reqpart.execute(storage, data)
    data.partition.execute(storage, data)
    data.raid.execute(storage, data)
    data.volgroup.execute(storage, data)
    data.logvol.execute(storage, data)
    data.btrfs.execute(storage, data)
    data.mount.execute(storage, data)

    # Set up the snapshot here.
    data.snapshot.setup(storage, data)

    # Set up the boot loader.
    storage.set_up_bootloader()
