#
# Supported kickstart version for dracut.
#
# Copyright (C) 2023 Red Hat, Inc.
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

import platform

from pykickstart.errors import KickstartVersionError
from pykickstart.version import DEFAULT_VERSION, stringToVersion


def _get_version_from_os_release():
    """Detect the pykickstart version from os-release fields.

    Reads ID/ID_LIKE and VERSION_ID from os-release and combines them to
    create a version string for pykickstart.version.stringToVersion.

    For remixed distributions, ID_LIKE is preferred over ID since ID
    contains the remix name while ID_LIKE contains the base distribution.

    :return: kickstart version constant or None if detection fails
    """
    try:
        os_release = platform.freedesktop_os_release()
    except OSError:
        return None

    version_id = os_release.get("VERSION_ID")
    if not version_id:
        return None

    id_like = os_release.get("ID_LIKE", "")
    os_id = os_release.get("ID", "")

    if id_like:
        effective_id = id_like.split()[0]
    elif os_id:
        effective_id = os_id
    else:
        return None

    if effective_id == "fedora":
        version_string = "f{}".format(version_id)
    elif effective_id == "rhel":
        version_string = "rhel{}".format(version_id)
    else:
        return None

    try:
        return stringToVersion(version_string)
    except KickstartVersionError:
        return None


VERSION = _get_version_from_os_release()
if VERSION is None:
    VERSION = DEFAULT_VERSION

__all__ = ["VERSION"]
