#
# Supported kickstart version.
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

from pykickstart.errors import KickstartVersionError
from pykickstart.version import DEFAULT_VERSION, stringToVersion

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.util import get_os_release_value

log = get_module_logger(__name__)


def _get_version_from_os_release():
    """Get kickstart version from os-release fields.

    Reads ID/ID_LIKE and VERSION_ID from os-release and combines them to create
    a version string suitable for pykickstart.version.stringToVersion.

    For remixed distributions, ID_LIKE is preferred over ID since ID contains
    the remix name while ID_LIKE contains the base distribution.

    Examples:
        ID=fedora, VERSION_ID=43 -> "f43" -> 43000
        ID=rhel, VERSION_ID=10 -> "rhel10" -> 40100
        ID=bazzite, ID_LIKE=fedora, VERSION_ID=43 -> "f43" -> 43000 (uses ID_LIKE)

    :return: kickstart version constant or None if detection fails
    """
    os_id = get_os_release_value("ID")
    id_like = get_os_release_value("ID_LIKE")
    version_id = get_os_release_value("VERSION_ID")

    if not version_id:
        log.debug("Missing VERSION_ID in os-release")
        return None

    # Determine which ID to use - prefer ID_LIKE for remixed distributions
    effective_id = None
    if id_like:
        # ID_LIKE can contain multiple space-separated values, use the first one
        first_like = id_like.split()[0]
        effective_id = first_like
        log.debug("Using ID_LIKE for version detection: %s (from '%s')", first_like, id_like)
    elif os_id:
        effective_id = os_id
        log.debug("Using ID for version detection: %s", os_id)
    else:
        log.debug("Missing both ID and ID_LIKE in os-release")
        return None

    # Create version string for pykickstart
    if effective_id == "fedora":
        version_string = f"f{version_id}"
    elif effective_id == "rhel":
        version_string = f"rhel{version_id}"
    else:
        log.debug("Unsupported os-release ID: %s", effective_id)
        return None

    log.debug("Attempting to convert version string: %s", version_string)

    # Convert to pykickstart version
    try:
        version = stringToVersion(version_string)
        log.info("Detected kickstart version from platform ID: %s -> %s", version_string, version)
        return version
    except KickstartVersionError as e:
        log.info("Failed to parse kickstart version string '%s': %s", version_string, e)
        return None


# Try to detect version from os-release, fall back to default
VERSION = _get_version_from_os_release()
if VERSION is None:
    log.info("Using default kickstart version")
    VERSION = DEFAULT_VERSION
else:
    log.info("Using os-release detected kickstart version")

__all__ = ["VERSION"]
