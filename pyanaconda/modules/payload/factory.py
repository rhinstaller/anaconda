#
# Factory class to create payload handlers.
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
from abc import ABC, abstractclassmethod

from pyanaconda.modules.payload.base.constants import HandlerType, SourceType
from pyanaconda.modules.payload.payloads.dnf.dnf import DNFHandlerModule
from pyanaconda.modules.payload.live.live_image import LiveImageHandlerModule
from pyanaconda.modules.payload.live.live_os import LiveOSHandlerModule
from pyanaconda.modules.payload.sources.live_os import LiveOSSourceModule

__all__ = ["HandlerFactory", "SourceFactory"]


class BaseFactory(ABC):
    """Factory to create payload objects."""

    @classmethod
    def create(cls, handler_type):
        """Create an object of the given type.

        :param handler_type: value from the enum of given type
        """
        handler = cls._create(handler_type)

        return handler

    @abstractclassmethod
    def _create(cls, object_type):
        """Return class from the type.

        :rtype: class
        """
        pass


class HandlerFactory(BaseFactory):
    """Factory to create payload handlers."""

    @classmethod
    def create_from_ks_data(cls, data):
        """Create handler based on the KS data.

        :param data: kickstart data
        """
        handler_type = cls._get_handler_type_from_ks(data)

        if handler_type is None:
            return None

        return cls.create(handler_type)

    @classmethod
    def _get_handler_type_from_ks(cls, data):
        if data.liveimg.seen:
            return HandlerType.LIVE_IMAGE
        elif data.packages.seen:
            return HandlerType.DNF
        else:
            return None

    @classmethod
    def _create(cls, object_type):
        if object_type == HandlerType.LIVE_IMAGE:
            return LiveImageHandlerModule()
        elif object_type == HandlerType.LIVE_OS:
            return LiveOSHandlerModule()
        elif object_type == HandlerType.DNF:
            return DNFHandlerModule()


class SourceFactory(BaseFactory):
    """Factory to create payload sources."""

    @classmethod
    def _create(cls, object_type):
        if object_type == SourceType.LIVE_OS_IMAGE:
            return LiveOSSourceModule()
