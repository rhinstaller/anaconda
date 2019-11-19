#
# Factory class to create payloads.
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

from pyanaconda.modules.payloads.constants import PayloadType, SourceType

__all__ = ["PayloadFactory", "SourceFactory"]


class BaseFactory(ABC):
    """Factory to create payload objects."""

    @classmethod
    def create(cls, object_type):
        """Create an object of the given type.

        :param object_type: value from the enum of given type
        """
        obj = cls._create(object_type)

        return obj

    @abstractclassmethod
    def _create(cls, object_type):
        """Return class from the type.

        :rtype: class
        """
        pass


class PayloadFactory(BaseFactory):
    """Factory to create payloads."""

    @classmethod
    def create_from_ks_data(cls, data):
        """Create payload based on the KS data.

        :param data: kickstart data
        """
        payload_type = cls._get_type_from_ks(data)

        if payload_type is None:
            return None

        return cls.create(payload_type)

    @classmethod
    def _get_type_from_ks(cls, data):
        if data.liveimg.seen:
            return PayloadType.LIVE_IMAGE
        elif data.packages.seen:
            return PayloadType.DNF
        else:
            return None

    @classmethod
    def _create(cls, object_type):
        if object_type == PayloadType.LIVE_IMAGE:
            from pyanaconda.modules.payloads.payload.live_image.live_image import \
                LiveImageModule
            return LiveImageModule()
        elif object_type == PayloadType.LIVE_OS:
            from pyanaconda.modules.payloads.payload.live_os.live_os import LiveOSModule
            return LiveOSModule()
        elif object_type == PayloadType.DNF:
            from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
            return DNFModule()


class SourceFactory(BaseFactory):
    """Factory to create payload sources."""

    @classmethod
    def _create(cls, object_type):
        if object_type == SourceType.LIVE_OS_IMAGE:
            from pyanaconda.modules.payloads.sources.live_os.live_os import LiveOSSourceModule
            return LiveOSSourceModule()
