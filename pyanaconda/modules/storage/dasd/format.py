#
# Formatting tasks
#
# Copyright (C) 2018 Red Hat, Inc.
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

from pyanaconda.modules.common.task import Task
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


class DASDFormatTask(Task):
    """A task for formatting DASDs"""

    def __init__(self, dasds):
        """Create a new task.

        :param dasds: a list of names of DASDs to format
        """
        super().__init__()
        self._dasds = dasds

    @property
    def name(self):
        return "Formatting DASDs"

    def run(self):
        for disk_name in self._dasds:
            self._do_format(disk_name)

    def _do_format(self, disk_name):
        """Format the specified DASD disk."""
        try:
            self.report_progress("Formatting {}".format(disk_name))
            blockdev.s390.dasd_format(disk_name)
        except blockdev.S390Error as err:
            self.report_progress("Failed formatting {}".format(disk_name))
            log.error(err)
