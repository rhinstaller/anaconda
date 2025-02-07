#
# Base object of all payloads.
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
from abc import ABCMeta, abstractmethod

from dasbus.server.publishable import Publishable

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.errors.general import UnavailableValueError
from pyanaconda.modules.common.errors.payload import (
    IncompatibleSourceError,
    SourceSetupError,
)
from pyanaconda.modules.payloads.base.initialization import (
    SetUpSourcesTask,
    TearDownSourcesTask,
)
from pyanaconda.modules.payloads.constants import SourceState

log = get_module_logger(__name__)


class PayloadBase(KickstartBaseModule, Publishable, metaclass=ABCMeta):
    """Base class for all the payload modules.

    This will contain all API specific to payload which will be called
    by the base payload module.
    """
    def __init__(self):
        super().__init__()
        self._sources = []
        self.sources_changed = Signal()
        self._kernel_version_list = None

        # side payload is attached to the payload so it stays even when active payload is changed
        # side payload standard methods and tasks are included in Payloads base class
        self._side_payload = None

    @property
    @abstractmethod
    def type(self):
        """Type of this payload.

        :return: value of the payload.base.constants.PayloadType enum
        """
        return None

    @property
    def side_payload(self):
        """Get side payload attached to this payload.

        The side payload is a payload attached to this payload. It can be configured by this
        payload.

        This side payload calls will be automatically queued for some DBus API in Payloads module.

        :return: PayloadBase based class or None
        :rtype: PayloadBase based class or None
        """
        return self._side_payload

    @side_payload.setter
    def side_payload(self, side_payload):
        """Set side payload attached to this payload.

        :param side_payload: side payload to be attached to this payload
        :type side_payload: PayloadBase based class or None
        """
        self._side_payload = side_payload

    @property
    @abstractmethod
    def default_source_type(self):
        """Type of the default source.

        :return SourceType: a default source type
        """
        return None

    @property
    @abstractmethod
    def supported_source_types(self):
        """Get list of supported source types.

        :return [SourceType]: a list of supported source types
        """
        return []

    @property
    def sources(self):
        """Get list of sources attached to this payload.

        :return: list of source objects attached to this payload
        :rtype: [instance of PayloadSourceBase class]
        """
        return self._sources

    def _get_source(self, source_type):
        """Get an attached source object of the specified type.

        :param SourceType source_type: a type of the source
        :return: a source object or None
        """
        for source in self.sources:
            if source.type == source_type:
                return source

        return None

    def set_sources(self, sources):
        """Set a new list of sources to this payload.

        Before setting the sources, please make sure the sources are not initialized otherwise
        the SourceSetupError exception will be raised. Payload have to cleanup after itself.

        ..NOTE:
        The SourceSetupError is a reasonable effort to solve the race condition. However,
        there is still a possibility that the task to initialize sources (`SetupSourcesWithTask()`)
        was created with the old list but not run yet. In that case this check will not work and
        the initialization task will run with the old list.

        :param sources: set a new sources
        :type sources: instance of pyanaconda.modules.payloads.source.source_base.PayloadSourceBase
        :raise: IncompatibleSourceError when source is not a supported type
                SourceSetupError when attached sources are initialized
        """
        for source in sources:
            if source.type not in self.supported_source_types:
                raise IncompatibleSourceError("Source type {} is not supported by this payload."
                                              .format(source.type.value))

        if any(source.get_state() == SourceState.READY for source in self.sources):
            raise SourceSetupError("Can't change list of sources if there is at least one source "
                                   "initialized! Please tear down the sources first.")

        self._sources = sources
        log.debug("New sources %s were added.", sources)
        self.sources_changed.emit()

    def add_source(self, source):
        """Module scope API for easier adding of sources.

        :param source: Source we want to add.
        """
        sources = list(self.sources)
        sources.append(source)
        self.set_sources(sources)

    def is_network_required(self):
        """Do the sources require a network?

        :return: True or False
        """
        for source in self.sources:
            if source.network_required:
                return True

        return False

    def calculate_required_space(self):
        """Calculate space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        total = 0

        for source in self.sources:
            total += source.required_space

        return total

    def get_kernel_version_list(self):
        """Get the kernel versions list.

        The kernel version list doesn't have to be available
        before the payload installation.

        :return: a list of kernel versions
        :raises UnavailableValueError: if the list is not available
        """
        if self._kernel_version_list is None:
            raise UnavailableValueError("The kernel version list is not available.")

        return self._kernel_version_list

    def set_kernel_version_list(self, kernels):
        """Set the kernel versions list.

        This function should be called by one of the installation tasks.

        :param kernels: a list of kernel versions
        """
        self._kernel_version_list = kernels
        log.debug("The kernel version list is set to: %s", kernels)

    def needs_flatpak_side_payload(self):
        """Does this payload need an extra payload for Flatpak installation

        :return: True or False
        """
        return False

    def get_flatpak_refs(self):
        """Get the list of Flatpak refs to install.

        :return: list of Flatpak refs
        """
        return []

    @abstractmethod
    def install_with_tasks(self):
        """Install the payload.

        :return: list of tasks
        """
        pass

    def post_install_with_tasks(self):
        """Execute post installation steps.

        :return: list of tasks
        """
        return []

    def set_up_sources_with_task(self):
        """Set up installation sources."""
        return SetUpSourcesTask(self.sources)

    def tear_down_sources_with_task(self):
        """Tear down installation sources."""
        return TearDownSourcesTask(self.sources)

    def tear_down_with_tasks(self):
        """Returns teardown tasks for this payload.

        Clean up everything after this payload.

        :return: a list of tasks
        """
        tasks = []

        if self.sources:
            tasks.append(self.tear_down_sources_with_task())

        return tasks
