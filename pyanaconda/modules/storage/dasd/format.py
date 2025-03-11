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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet import blockdev

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

__all__ = ["DASDFormatTask", "FindFormattableDASDTask"]


class FindFormattableDASDTask(Task):
    """A task for finding DASDs for formatting."""

    def __init__(self, disks, can_format_unformatted=False, can_format_ldl=False):
        """Create a new task.

        :param disks: a list of disks to search
        :param can_format_unformatted: can we format unformatted?
        :param can_format_ldl: can we format LDL?
        """
        super().__init__()
        self._disks = disks
        self._can_format_unformatted = can_format_unformatted
        self._can_format_ldl = can_format_ldl

    @property
    def name(self):
        """Name of the task."""
        return "Finding DASDs for formatting"

    def run(self):
        """Run the task."""
        return list(set(
            self._get_unformatted_dasds(self._disks)
            + self._get_ldl_dasds(self._disks)
        ))

    def _get_unformatted_dasds(self, disks):
        """Returns a list of unformatted DASDs."""
        result = []

        if not self._can_format_unformatted:
            log.debug("We are not allowed to format unformatted DASDs.")
            return result

        for disk in disks:
            if self._is_unformatted_dasd(disk):
                log.debug("Found unformatted DASD: %s (%s)", disk.path, disk.busid)
                result.append(disk)

        return result

    def _is_unformatted_dasd(self, disk):
        """Is it an unformatted DASD?"""
        return self._is_dasd(disk) \
            and not blockdev.s390.dasd_is_fba(disk.name) \
            and blockdev.s390.dasd_needs_format(disk.busid)

    def _is_dasd(self, disk):
        """Is it a DASD disk?"""
        return disk.type == "dasd"

    def _get_ldl_dasds(self, disks):
        """Returns a list of LDL DASDs."""
        result = []

        if not self._can_format_ldl:
            log.debug("We are not allowed to format LDL DASDs.")
            return result

        for disk in disks:
            if self._is_ldl_dasd(disk):
                log.debug("Found LDL DASD: %s (%s)", disk.path, disk.busid)
                result.append(disk)

        return result

    def _is_ldl_dasd(self, disk):
        """Is it an LDL DASD?"""
        return self._is_dasd(disk) and blockdev.s390.dasd_is_ldl(disk.name)


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
