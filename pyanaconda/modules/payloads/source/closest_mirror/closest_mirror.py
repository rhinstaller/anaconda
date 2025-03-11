#
# Source module for the closest mirror.
#
# Copyright (C) 2020 Red Hat, Inc.
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
from pyanaconda.core.i18n import _
from pyanaconda.core.signal import Signal
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.closest_mirror.closest_mirror_interface import (
    ClosestMirrorSourceInterface,
)
from pyanaconda.modules.payloads.source.repo_files.repo_files import (
    RepoFilesSourceModule,
)

log = get_module_logger(__name__)


class ClosestMirrorSourceModule(RepoFilesSourceModule):
    """The source payload module for the closest mirror."""

    def __init__(self):
        """Create the module."""
        super().__init__()
        self._updates_enabled = True
        self.updates_enabled_changed = Signal()

    def for_publication(self):
        """Get the interface used to publish this source."""
        return ClosestMirrorSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.CLOSEST_MIRROR

    @property
    def description(self):
        """Get description of this source."""
        return _("Closest mirror")

    @property
    def updates_enabled(self):
        """Should repositories that provide updates be enabled?

        :return: True or False
        """
        return self._updates_enabled

    def set_updates_enabled(self, enabled):
        """Enable or disable repositories that provide updates.

        :param enabled: True to enable, False to disable
        """
        self._updates_enabled = enabled
        self.updates_enabled_changed.emit()
        log.debug("Updates enabled is set to '%s'.", enabled)
