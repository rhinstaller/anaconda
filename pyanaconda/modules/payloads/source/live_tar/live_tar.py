#
# The live tar source module.
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
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.live_image.live_image import (
    LiveImageSourceModule,
)
from pyanaconda.modules.payloads.source.live_tar.installation import InstallLiveTarTask

log = get_module_logger(__name__)

__all__ = ["LiveTarSourceModule"]


class LiveTarSourceModule(LiveImageSourceModule):
    """The live tar source module."""

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.LIVE_TAR

    @property
    def description(self):
        """Get description of this source."""
        return _("Live tarball")

    def install_with_tasks(self):
        """Install the installation source.

        :return: a list of installation tasks
        """
        return [
            InstallLiveTarTask(
                sysroot=conf.target.system_root,
                configuration=self.configuration
            )
        ]
