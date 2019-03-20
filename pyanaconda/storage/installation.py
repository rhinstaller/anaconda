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
import os

import gi
gi.require_version("BlockDev", "2.0")
from gi.repository import BlockDev as blockdev

from blivet import util as blivet_util, arch
from blivet.errors import FSResizeError, FormatResizeError
from blivet.iscsi import iscsi

from pyanaconda.core import util
from pyanaconda.errors import errorHandler as error_handler, ERROR_RAISE
from pyanaconda.modules.common.constants.objects import FCOE, ZFCP
from pyanaconda.modules.common.constants.services import STORAGE

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["turn_on_filesystems", "write_storage_configuration"]


def turn_on_filesystems(storage, callbacks=None):
    """Perform installer-specific activation of storage configuration.

    :param storage: the storage object
    :type storage: :class:`~.storage.InstallerStorage`
    :param callbacks: callbacks to be invoked when actions are executed
    :type callbacks: return value of the :func:`blivet.callbacks.create_new_callbacks_register`
    """
    storage.devicetree.teardown_all()

    try:
        storage.do_it(callbacks)
    except (FSResizeError, FormatResizeError) as e:
        if error_handler.cb(e) == ERROR_RAISE:
            raise

    storage.turn_on_swap()


def _write_escrow_packets(storage, sysroot):
    """Write the escrow packets.

    :param storage: the storage object
    :type storage: :class:`~.storage.InstallerStorage`
    :param sysroot: a path to the target OS installation
    :type sysroot: str
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
        escrow_dir = sysroot + "/root"
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


def write_storage_configuration(storage, sysroot=None):
    """Write the storage configuration to sysroot.

    :param storage: the storage object
    :param sysroot: a path to the target OS installation
    """
    if sysroot is None:
        sysroot = util.getSysroot()

    if not os.path.isdir("%s/etc" % sysroot):
        os.mkdir("%s/etc" % sysroot)

    _write_escrow_packets(storage, sysroot)

    storage.make_mtab()
    storage.fsset.write()
    iscsi.write(sysroot, storage)

    fcoe_proxy = STORAGE.get_proxy(FCOE)
    fcoe_proxy.WriteConfiguration(sysroot)

    if arch.is_s390():
        zfcp_proxy = STORAGE.get_proxy(ZFCP)
        zfcp_proxy.WriteConfiguration(sysroot)

    _write_dasd_conf(storage, sysroot)


def _write_dasd_conf(storage, sysroot):
    """Write DASD configuration to sysroot.

    Write /etc/dasd.conf to target system for all DASD devices
    configured during installation.

    :param storage: the storage object
    :param sysroot: a path to the target OS installation
    """
    dasds = [d for d in storage.devices if d.type == "dasd"]
    dasds.sort(key=lambda d: d.name)
    if not (arch.is_s390() and dasds):
        return

    with open(os.path.realpath(sysroot + "/etc/dasd.conf"), "w") as f:
        for dasd in dasds:
            fields = [dasd.busid] + dasd.get_opts()
            f.write("%s\n" % " ".join(fields),)

    # check for hyper PAV aliases; they need to get added to dasd.conf as well
    sysfs = "/sys/bus/ccw/drivers/dasd-eckd"

    # in the case that someone is installing with *only* FBA DASDs,the above
    # sysfs path will not exist; so check for it and just bail out of here if
    # that's the case
    if not os.path.exists(sysfs):
        return

    # this does catch every DASD, even non-aliases, but we're only going to be
    # checking for a very specific flag, so there won't be any duplicate entries
    # in dasd.conf
    devs = [d for d in os.listdir(sysfs) if d.startswith("0.0")]
    with open(os.path.realpath(sysroot + "/etc/dasd.conf"), "a") as f:
        for d in devs:
            aliasfile = "%s/%s/alias" % (sysfs, d)
            with open(aliasfile, "r") as falias:
                alias = falias.read().strip()

            # if alias == 1, then the device is an alias; otherwise it is a
            # normal dasd (alias == 0) and we can skip it, since it will have
            # been added to dasd.conf in the above block of code
            if alias == "1":
                f.write("%s\n" % d)
