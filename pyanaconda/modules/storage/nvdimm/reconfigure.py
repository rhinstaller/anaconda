#
# Reconfigure tasks
#
# Copyright (C) 2019 Red Hat, Inc.
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
from blivet.static_data import nvdimm

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.errors.configuration import StorageConfigurationError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

__all__ = ["NVDIMMReconfigureTask"]


class NVDIMMReconfigureTask(Task):
    """A task for reconfiguring an NVDIMM namespace"""

    def __init__(self, namespace, mode, sector_size):
        super().__init__()
        self._namespace = namespace
        self._mode = mode
        self._sector_size = sector_size

    @property
    def name(self):
        return "Reconfigure an NVDIMM namespace"

    def run(self):
        """Run the reconfiguration."""
        self._reconfigure_namespace(self._namespace, self._mode, self._sector_size)

    def _reconfigure_namespace(self, namespace, mode, sector_size):
        """Reconfigure a namespace.

        :param namespace: a device name of the namespace
        :param mode: a new mode of the namespace
        :param sector_size: a size of the sector
        :raise: StorageConfigurationError in case of failure
        """
        try:
            nvdimm.reconfigure_namespace(namespace, mode, sector_size=sector_size)
        except Exception as e:  # pylint: disable=broad-except
            raise StorageConfigurationError(str(e)) from e
