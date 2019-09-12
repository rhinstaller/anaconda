#
# Kickstart module for Live OS payload source.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.modules.payload.base.source_base import PayloadSourceBase
from pyanaconda.modules.payload.sources.live_os_interface import LiveOSSourceInterface
from pyanaconda.modules.payload.sources.initialization import SetUpInstallationSourceTask


class LiveOSSourceModule(PayloadSourceBase):
    """The Live OS source payload module."""

    def __init__(self, image_path):
        super().__init__()
        self._image_path = image_path

    def for_publication(self):
        """Get the interface used to publish this source."""
        return LiveOSSourceInterface(self)

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpInstallationSourceTask(self._image_path, INSTALL_TREE)

        task.succeeded_signal.connect(lambda: self._set_is_ready(True))

        return [task]

    def tear_down_with_tasks(self):
        pass

    def validate(self):
        return True
