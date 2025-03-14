#
# Base object of all payload sources.
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
import os.path
from abc import ABC, ABCMeta, abstractmethod

from dasbus.server.publishable import Publishable
from dasbus.signal import Signal

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.async_utils import async_action_wait
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.source.utils import MountPointGenerator

__all__ = [
    "MountingSourceMixin",
    "PayloadSourceBase",
    "RPMSourceMixin",
    "RepositorySourceMixin"
]

log = get_module_logger(__name__)


class PayloadSourceBase(KickstartBaseModule, Publishable, metaclass=ABCMeta):
    """Base class for all the payload source modules.

    This object contains API shared by all the sources. Everything in this object has
    to be implemented by a source to be used.
    """

    @property
    @abstractmethod
    def type(self):
        """Get type of this source object.

        :return: type of this source
        :rtype: value of payload.base.constants.SourceType
        """
        pass

    @property
    @abstractmethod
    def description(self):
        """Get a l10n-able description of this source object.

        :return: description of this source
        :rtype: str
        """
        pass

    @property
    @abstractmethod
    def network_required(self):
        """Does the source require a network?

        :return: True or False
        """
        pass

    @property
    @abstractmethod
    def required_space(self):
        """The space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        return 0

    @abstractmethod
    def get_state(self):
        """Get state of this source.

        This method will not be part of the public API. There is no need for others than the
        payload owner to see the status of the source. It is also not really useful, in time when
        user gets the ready state the state could be different because of the DBus parallelism.
        In general we should not share state.

        :return: one of the supported state of SourceState enum
        :rtype: pyanaconda.modules.payloads.constants.SourceState enum value
        """
        pass

    @abstractmethod
    def set_up_with_tasks(self):
        """Prepare this payload source.

        Do everything it requires to be able to use this source for installation.

        This method will not be part of the public API. Having this private only will prevent race
        conditions and there is no real use outside of payload.

        :return: list of tasks to prepare this source
        :rtype: list[task]
        """
        pass

    @abstractmethod
    def tear_down_with_tasks(self):
        """Tear down this payload source.

        Cleanup everything done by the setup method.

        This method will not be part of the public API. Having this private only will prevent race
        conditions and there is no real use outside of payload.

        :return: list of tasks to tear down this source
        :rtype: list[task]
        """
        pass

    def __repr__(self):
        """The default string representation of the source."""
        return "Source(type='{}')".format(self.type.value)


class MountingSourceMixin(ABC):
    """Mixin class for sources that use mounting."""

    def __init__(self):
        super().__init__()
        self._mount_point = MountPointGenerator.generate_mount_point(self.type.value.lower())

    @property
    @abstractmethod
    def type(self):
        """Get type of this source object.

        This is the same property as in PayloadSourceBase so it should be implemented by
        a subclass so or so.

        :return: type of this source
        :rtype: value of payload.base.constants.SourceType
        """
        pass

    def get_mount_state(self):
        """Return state of the mount.

        :return: True if mounted
        :rtype: bool
        """
        return os.path.ismount(self._mount_point)

    @property
    def mount_point(self):
        """Where the source will be mounted.

        :return: path to the mount point
        :rtype: str
        """
        return self._mount_point


class RPMSourceMixin(ABC):
    """Mixin class which has to be implemented by all sources used by DNF payload."""

    @abstractmethod
    def generate_repo_configuration(self):
        """Generate RepoConfigurationData structure.

        This structure will be used by DNF payload in the main process.

        FIXME: This is a temporary solution. Will be removed after DNF payload logic is moved.
        """
        pass


class RepositorySourceMixin(ABC):
    """Mixin class for sources that provide access to a repository."""

    def __init__(self):
        super().__init__()
        self._configuration = RepoConfigurationData()
        self.configuration_changed = Signal()
        self._repository = None

    @property
    def configuration(self):
        """The configuration of the source.

        This configuration will be used to set up the source
        and generate a configuration of the available repository.

        :return RepoConfigurationData: a configuration data
        """
        return self._configuration

    def set_configuration(self, configuration):
        """Set the source configuration.

        :param RepoConfigurationData configuration: a configuration data
        :raise InvalidValueError: if the configuration is invalid
        """
        self._validate_configuration(configuration)
        self._configuration = configuration
        self.configuration_changed.emit(configuration)
        log.debug("The configuration is set to: %s", str(configuration))

    @abstractmethod
    def _validate_configuration(self, configuration):
        """Validate the specified source configuration.

        :param RepoConfigurationData configuration: a configuration data
        :raise InvalidValueError: if the configuration is invalid
        """
        pass

    @property
    @async_action_wait
    def repository(self):
        """The repository configuration of the prepared source.

        This configuration is generated after a successful setup of this
        source. It represents the available repository, if there is any,
        and it will be used to set up the repository via the DNF manager.

        :return RepoConfigurationData: a configuration data
        :raise SourceSetupError: if there are no configuration data
        """
        repository = self._repository

        if not repository:
            raise SourceSetupError("The repository configuration is unavailable.")

        return repository

    def _set_repository(self, repository):
        """Set the repository configuration of the prepared source.

        :return RepoConfigurationData: a configuration data
        """
        self._repository = repository
        log.debug("The repository is set to: %s", str(repository))
