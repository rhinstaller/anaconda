#
# Base object of all payload handlers.
#
# Copyright (C) 2018 Red Hat, Inc.
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

from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.errors.payload import IncompatibleSourceError
from pyanaconda.modules.common.base import KickstartBaseModule

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class PayloadHandlerBase(KickstartBaseModule, metaclass=ABCMeta):
    """Base class for all the payload handler modules.

    This will contain all API specific to payload handlers which will be called
    by the base payload module.
    """
    def __init__(self):
        super().__init__()
        self._sources = set()
        self.sources_changed = Signal()

    @property
    @abstractmethod
    def supported_source_kinds(self):
        """Get list of supported source types.

        :return: list of supported source types
        :rtype: [values from payload.base.constants.SourceType]
        """
        pass

    @property
    def sources(self):
        """Get list of sources attached to this payload handler.

        :return: list of source objects attached to this handler
        :rtype: set(instance of PayloadSourceBase class)
        """
        return self._sources

    def add_source(self, source):
        """Add source to the list of sources.

        :param source: source object
        :type source: instance of pyanaconda.modules.payload.base.source_base.PayloadSourceBase
        :raises: IncompatibleSourceError
        """
        # TODO: Add test for this when there will be public API
        if source.kind not in self.supported_source_kinds:
            raise IncompatibleSourceError("Source type {} is not supported by this handler."
                                          .format(source.kind))

        if source not in self._sources:
            self._sources.add(source)
            log.debug("New source %s was added.", source.kind)
            self.sources_changed.emit()

    def has_source(self):
        """Check if any source is set.

        :return: True if source object is set
        :rtype: bool
        """
        return bool(self.sources)

    @abstractmethod
    def publish_handler(self):
        """Publish object on DBus and return its path.

        :returns: path to this handler
        :rtype: string
        """
        pass

    def attach_source(self, source):
        """Attach source to this payload handler.

        :param source: source object
        :type source: instance of pyanaconda.modules.payload.base.source_base.PayloadSourceBase
        """
        self.add_source(source)
