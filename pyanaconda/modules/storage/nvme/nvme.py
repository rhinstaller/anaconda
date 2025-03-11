#
# The NVMe module
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
from blivet.nvme import nvme

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import NVME
from pyanaconda.modules.storage.nvme.nvme_interface import NVMEInterface

log = get_module_logger(__name__)


class NVMEModule(KickstartBaseModule):
    """The NVMe module."""

    def __init__(self):
        super().__init__()
        self.reload_module()

        self.initiator_changed = Signal()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(NVME.object_path, NVMEInterface(self))

    def reload_module(self):
        """Reload the NVMe module."""
        log.debug("Start up the NVMe module.")
        nvme.startup()

    def write_configuration(self):
        """Write the configuration to sysroot."""
        log.debug("Write NVMe configuration.")
        nvme.write(conf.target.system_root)
