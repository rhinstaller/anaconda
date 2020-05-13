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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from abc import ABCMeta, abstractmethod

from dasbus.server.publishable import Publishable

from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.errors.payload import IncompatibleSourceError, SourceSetupError
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.payloads.constants import SourceState

from pyanaconda.anaconda_loggers import get_module_logger
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

        self._required_space = None
        self.required_space_changed = Signal()

    @property
    @abstractmethod
    def type(self):
        """Get type of this payload.

        :return: value of the payload.base.constants.PayloadType enum
        """
        pass

    @property
    def required_space(self):
        """Get required space by payload for the installation.

        :return: required size in bytes
        :rtype: int
        """
        if self._required_space:
            return self._required_space
        else:
            return self.default_required_space

    def set_required_space(self, required_space):
        """Set space required for the installation.

        :param required_space: space required to make installation of this payload successful,
                               use None if space is not known
        :type required_space: int or None if not known
        """
        if not required_space:
            log.debug("Required space is not known, using reasonable default.")

        self._required_space = required_space
        self.required_space_changed.emit()
        log.debug("Space required for installation '%s'", self.required_space)
        self.module_properties_changed.emit()

    @property
    def default_required_space(self):
        """Get reasonable guess for required space when the real value is not known.

        :return: reasonable default required space
        :rtype: int
        """
        return 0

    @property
    @abstractmethod
    def supported_source_types(self):
        """Get list of supported source types.

        :return: list of supported source types
        :rtype: [values from payload.base.constants.SourceType]
        """
        pass

    @property
    def sources(self):
        """Get list of sources attached to this payload.

        :return: list of source objects attached to this payload
        :rtype: [instance of PayloadSourceBase class]
        """
        return self._sources

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

    @abstractmethod
    def pre_install_with_tasks(self):
        """Execute preparation steps.

        :return: list of tasks
        """
        pass

    @abstractmethod
    def install_with_tasks(self):
        """Install the payload.

        :return: list of tasks
        """
        pass

    @abstractmethod
    def post_install_with_tasks(self):
        """Execute post installation steps.

        :return: list of tasks
        """
        pass

    @abstractmethod
    def set_up_sources_with_task(self):
        """Set up installation sources."""
        pass

    @abstractmethod
    def tear_down_sources_with_task(self):
        """Tear down installation sources."""
        pass
