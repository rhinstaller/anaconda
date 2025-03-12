#
# The source module for flatpaks.
#
# Copyright (C) 2021 Red Hat, Inc.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.payload.rpm_ostree.flatpak_manager import (
    FlatpakManager,
)
from pyanaconda.modules.payloads.source.flatpak.flatpak_interface import (
    FlatpakSourceInterface,
)
from pyanaconda.modules.payloads.source.flatpak.initialization import (
    GetFlatpaksSizeTask,
)
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase

log = get_module_logger(__name__)

__all__ = ["FlatpakSourceModule"]


class FlatpakSourceModule(PayloadSourceBase):
    """The Flatpak source module."""

    def __init__(self):
        super().__init__()
        self._required_space = 0

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.FLATPAK

    @property
    def description(self):
        """Get description of this source."""
        return _("Flatpak")

    def for_publication(self):
        """Return a DBus representation."""
        return FlatpakSourceInterface(self)

    @property
    def network_required(self):
        """Does the source require a network?"""
        return False

    @property
    def required_space(self):
        """The space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        return self._required_space

    def _set_required_space(self, size):
        """Set up the space required for the installation."""
        self._required_space = size

    def is_available(self):
        """Is the predefined flatpak repository available?

        FIXME: This is a temporary method. Configure the source instead.

        :return: True or False
        """
        return FlatpakManager.is_source_available()

    def get_state(self):
        """Get state of this source."""
        return SourceState.NOT_APPLICABLE

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = GetFlatpaksSizeTask(conf.target.system_root)
        task.succeeded_signal.connect(
            lambda: self._set_required_space(task.get_result())
        )
        return [task]

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        return []

    def __repr__(self):
        """Return a string representation of the source."""
        return "Source(type='{}')".format(
            self.type.value
        )
