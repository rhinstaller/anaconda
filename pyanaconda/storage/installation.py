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
import gi
gi.require_version("BlockDev", "2.0")
from gi.repository import BlockDev as blockdev

from blivet import util as blivet_util
from blivet.errors import FSResizeError, FormatResizeError

from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.errors import errorHandler as error_handler, ERROR_RAISE

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["turn_on_filesystems"]


def turn_on_filesystems(storage, callbacks=None):
    """Perform installer-specific activation of storage configuration.

    :param storage: the storage object
    :type storage: :class:`~.storage.InstallerStorage`
    :param callbacks: callbacks to be invoked when actions are executed
    :type callbacks: return value of the :func:`blivet.callbacks.create_new_callbacks_register`
    """
    # FIXME: This is a temporary workaround for live OS.
    if conf.system._is_live_os and conf.target.is_hardware and not storage.fsset.active:
        # turn off any swaps that we didn't turn on
        # needed for live installs
        blivet_util.run_program(["swapoff", "-a"])

    storage.devicetree.teardown_all()

    try:
        storage.do_it(callbacks)
    except (FSResizeError, FormatResizeError) as e:
        if error_handler.cb(e) == ERROR_RAISE:
            raise

    storage.turn_on_swap()

    # FIXME:  For livecd, skip_root needs to be True.
    storage.mount_filesystems()

    write_escrow_packets(storage)


def write_escrow_packets(storage):
    """Write the escrow packets.

    :param storage: the storage object
    :type storage: :class:`~.storage.InstallerStorage`
    """
    escrow_devices = [
        d for d in storage.devices
        if d.format.type == 'luks' and d.format.escrow_cert
    ]

    if not escrow_devices:
        return

    log.debug("escrow: write_escrow_packets start")
    backup_passphrase = blockdev.crypto.generate_backup_passphrase()

    try:
        escrow_dir = util.getSysroot() + "/root"
        log.debug("escrow: writing escrow packets to %s", escrow_dir)
        blivet_util.makedirs(escrow_dir)
        for device in escrow_devices:
            log.debug("escrow: device %s: %s",
                      repr(device.path), repr(device.format.type))
            device.format.escrow(escrow_dir,
                                 backup_passphrase)

    except (IOError, RuntimeError) as e:
        # TODO: real error handling
        log.error("failed to store encryption key: %s", e)

    log.debug("escrow: write_escrow_packets done")
