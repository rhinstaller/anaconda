#
# The NFS source module.
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
from pyanaconda.core.signal import Signal
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.nfs.nfs_interface import NFSSourceInterface
from pyanaconda.modules.payloads.source.nfs.initialization import SetUpNFSSourceTask, \
    TearDownNFSSourceTask
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["NFSSourceModule"]


class NFSSourceModule(PayloadSourceBase):
    """The NFS source module."""

    def __init__(self):
        super().__init__()
        self._url = ""
        self.url_changed = Signal()

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.NFS

    def for_publication(self):
        """Return a DBus representation."""
        return NFSSourceInterface(self)

    def is_ready(self):
        """This source is ready for the installation to start."""
        ready = os.path.ismount(INSTALL_TREE)
        log.debug("Source is set to %s ready state.", ready)
        return ready

    @property
    def url(self):
        """URL for mounting.

        Combines server address, path, and options.

        :rtype: str
        """
        return self._url

    def set_url(self, url):
        """Set all NFS values with a valid URL.

        Fires all signals.

        :param url: URL
        :type url: str
        """
        self._url = url
        self.url_changed.emit()
        log.debug("NFS URL is set to %s", self._url)

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        return [SetUpNFSSourceTask(INSTALL_TREE, self._url)]

    def tear_down_with_tasks(self):
        """Tear down the installation source for installation.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        return [TearDownNFSSourceTask(INSTALL_TREE)]
