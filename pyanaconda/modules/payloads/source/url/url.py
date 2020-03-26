#
# Kickstart module for URL payload source.
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
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase
from pyanaconda.modules.payloads.source.url.url_interface import URLSourceInterface

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class URLSourceModule(PayloadSourceBase):
    """The URL source payload module."""

    def __init__(self):
        super().__init__()
        self._repo_configuration = RepoConfigurationData()
        self.repo_configuration_changed = Signal()

        self._install_repo_enabled = False
        self.install_repo_enabled_changed = Signal()

    def is_ready(self):
        """This source is ready for the installation to start."""
        # FIXME: always true is correct but it will block change of payload source. Find solution!
        return True

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.URL

    def for_publication(self):
        """Get the interface used to publish this source."""
        return URLSourceInterface(self)

    def set_up_with_tasks(self):
        """Set up the installation source.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        return []

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        return []

    @property
    def repo_configuration(self):
        """Get repository configuration data.

        :rtype: RepoConfigurationData data structure
        """
        return self._repo_configuration

    def set_repo_configuration(self, repo_configuration):
        """Set repository configuration data.

        :param repo_configuration: configuration for this repository
        :type repo_configuration: RepoConfigurationData data structure
        """
        self._repo_configuration = repo_configuration
        self.repo_configuration_changed.emit(self._repo_configuration)
        log.debug("The repo_configuration is set to %s", self._repo_configuration)

    @property
    def install_repo_enabled(self):
        """Get if this repository will be installed to the resulting system.

        :rtype: bool
        """
        return self._install_repo_enabled

    def set_install_repo_enabled(self, install_repo_enabled):
        """Set if this repository will be installed to the resulting system.

        :param install_repo_enabled: True if we want to have this repository installed
        :type install_repo_enabled: bool
        """
        self._install_repo_enabled = install_repo_enabled
        self.install_repo_enabled_changed.emit(self._install_repo_enabled)
        log.debug("The install_repo_enabled has changed %s", install_repo_enabled)
