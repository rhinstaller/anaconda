#
# Kickstart module for CD-ROM payload source.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os

from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase
from pyanaconda.modules.payloads.source.cdrom.cdrom_interface import \
    CdromSourceInterface
from pyanaconda.modules.payloads.source.cdrom.initialization import \
    SetUpCdromSourceTask, TearDownCdromSourceTask

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class CdromSourceModule(PayloadSourceBase):
    """The CD-ROM source payload module."""

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.CDROM

    def is_ready(self):
        """This source is ready for the installation to start."""
        # TODO: this should be check on a special directory for every source
        res = os.path.ismount(INSTALL_TREE)
        log.debug("Source is set to %s ready state", res)
        return res

    def for_publication(self):
        """Get the interface used to publish this source."""
        return CdromSourceInterface(self)

    def set_up_with_tasks(self):
        """Set up the installation source.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpCdromSourceTask(INSTALL_TREE)
        return [task]

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        task = TearDownCdromSourceTask(INSTALL_TREE)
        return [task]
