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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.modules.payloads.constants import PayloadType

__all__ = ["PayloadFactory"]


class PayloadFactory:
    """Factory to create payloads."""

    @staticmethod
    def create_payload(payload_type: PayloadType):
        """Create a partitioning module.

        :param payload_type: a payload type
        :return: a payload module
        """
        if payload_type == PayloadType.LIVE_IMAGE:
            from pyanaconda.modules.payloads.payload.live_image.live_image import (
                LiveImageModule,
            )
            return LiveImageModule()

        if payload_type == PayloadType.LIVE_OS:
            from pyanaconda.modules.payloads.payload.live_os.live_os import LiveOSModule
            return LiveOSModule()

        if payload_type == PayloadType.DNF:
            from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
            return DNFModule()

        if payload_type == PayloadType.RPM_OSTREE:
            from pyanaconda.modules.payloads.payload.rpm_ostree.rpm_ostree import (
                RPMOSTreeModule,
            )
            return RPMOSTreeModule()

        if payload_type == PayloadType.FLATPAK:
            from pyanaconda.modules.payloads.payload.flatpak.flatpak import FlatpakModule
            return FlatpakModule()

        raise ValueError("Unknown payload type: {}".format(payload_type))

    @classmethod
    def get_type_for_kickstart(cls, data):
        """Get a payload type for the given kickstart data.

        :param data: a kickstart data
        :return: a payload type
        """
        if data.ostreesetup.seen or data.ostreecontainer.seen:
            return PayloadType.RPM_OSTREE

        if data.liveimg.seen:
            return PayloadType.LIVE_IMAGE

        if data.cdrom.seen or \
           data.harddrive.seen or \
           data.hmc.seen or \
           data.nfs.seen or \
           data.url.seen or \
           data.repo.seen or \
           data.packages.seen:
            return PayloadType.DNF

        return None
