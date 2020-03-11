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


class PayloadFactory(object):
    """Factory to create payloads."""

    @classmethod
    def get_type_for_kickstart(cls, data):
        """Get a payload type for the given kickstart data.

        :param data: a kickstart data
        :return: a payload type
        """
        if data.liveimg.seen:
            return PayloadType.LIVE_IMAGE
        elif data.packages.seen:
            return PayloadType.DNF
        else:
            return None

    @staticmethod
    def create_payload(object_type: PayloadType):
        """Create a partitioning module.

        :param object_type: a payload type
        :return: a payload module
        """
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

        raise ValueError("Unknown payload type: {}".format(object_type))


class SourceFactory(object):
    """Factory to create payload sources."""

    @staticmethod
    def create_source(object_type: SourceType):
        """Create a source module.

        :param object_type: a source type
        :return: a source module
        """
        if object_type == SourceType.LIVE_OS_IMAGE:
            from pyanaconda.modules.payloads.source.live_os.live_os import LiveOSSourceModule
            return LiveOSSourceModule()

        raise ValueError("Unknown source type: {}".format(object_type))
