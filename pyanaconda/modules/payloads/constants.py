#
# Constants shared in the payload module.
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
from enum import Enum, auto, unique

from pyanaconda.core.constants import (
    PAYLOAD_TYPE_DNF,
    PAYLOAD_TYPE_FLATPAK,
    PAYLOAD_TYPE_LIVE_IMAGE,
    PAYLOAD_TYPE_LIVE_OS,
    PAYLOAD_TYPE_RPM_OSTREE,
    SOURCE_TYPE_CDN,
    SOURCE_TYPE_CDROM,
    SOURCE_TYPE_CLOSEST_MIRROR,
    SOURCE_TYPE_FLATPAK,
    SOURCE_TYPE_HDD,
    SOURCE_TYPE_HMC,
    SOURCE_TYPE_LIVE_IMAGE,
    SOURCE_TYPE_LIVE_OS_IMAGE,
    SOURCE_TYPE_LIVE_TAR,
    SOURCE_TYPE_NFS,
    SOURCE_TYPE_REPO_FILES,
    SOURCE_TYPE_REPO_PATH,
    SOURCE_TYPE_RPM_OSTREE,
    SOURCE_TYPE_RPM_OSTREE_CONTAINER,
    SOURCE_TYPE_URL,
)

# Locations of repo files.
DNF_REPO_DIRS = [
    '/etc/yum.repos.d',
    '/etc/anaconda.repos.d'
]


@unique
class PayloadType(Enum):
    """Type of the payload."""
    DNF = PAYLOAD_TYPE_DNF
    FLATPAK = PAYLOAD_TYPE_FLATPAK
    LIVE_OS = PAYLOAD_TYPE_LIVE_OS
    LIVE_IMAGE = PAYLOAD_TYPE_LIVE_IMAGE
    RPM_OSTREE = PAYLOAD_TYPE_RPM_OSTREE


@unique
class SourceType(Enum):
    """Type of the payload source."""
    LIVE_OS_IMAGE = SOURCE_TYPE_LIVE_OS_IMAGE
    LIVE_IMAGE = SOURCE_TYPE_LIVE_IMAGE
    LIVE_TAR = SOURCE_TYPE_LIVE_TAR
    RPM_OSTREE = SOURCE_TYPE_RPM_OSTREE
    RPM_OSTREE_CONTAINER = SOURCE_TYPE_RPM_OSTREE_CONTAINER
    FLATPAK = SOURCE_TYPE_FLATPAK
    HMC = SOURCE_TYPE_HMC
    CDROM = SOURCE_TYPE_CDROM
    CLOSEST_MIRROR = SOURCE_TYPE_CLOSEST_MIRROR
    REPO_FILES = SOURCE_TYPE_REPO_FILES
    REPO_PATH = SOURCE_TYPE_REPO_PATH
    NFS = SOURCE_TYPE_NFS
    URL = SOURCE_TYPE_URL
    HDD = SOURCE_TYPE_HDD
    CDN = SOURCE_TYPE_CDN


@unique
class SourceState(Enum):
    """States in which the source modules could be.

    These will be used only internally. Not with a DBus API.
    """
    NOT_APPLICABLE = auto()
    READY = auto()
    UNREADY = auto()

    @staticmethod
    def from_bool(value):
        """Get state from a bool value.

        This way we can't return NONE state but that is not a problem. NONE state is specific
        for sources which do not have a state, so they don't have to convert it from bool.

        :param value: input boolean value
        :type value: bool

        :return: READY if value is True or UNREADY
        """
        return SourceState.READY if value else SourceState.UNREADY
