#
# Query and download sources of Flatpak content
#
# Copyright (C) 2024 Red Hat, Inc.
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

from typing import Optional, Tuple

from blivet.arch import get_arch

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["canonicalize_flatpak_ref", "get_container_arch"]

# Cases where the Podman/Docker name is different from the Flatpak/RPM name
# For other architectures the name is correct.
_CONTAINER_ARCH_MAP = {
    "x86_64": "amd64",
    "aarch64": "arm64"
}


def get_container_arch():
    """Architecture name as used by OCI format (docker/podman)

    This architecture conversion is needed because the OCI format (used by docker/podman).add()
    The OCI format is needed when we downloading the Flatpak images or otherwise interacting with
    the registry tooling.
    """
    arch = get_arch()
    return _CONTAINER_ARCH_MAP.get(arch, arch)


def canonicalize_flatpak_ref(ref) -> Tuple[Optional[str], str]:
    """Split off a collection ID, and add architecture if unspecified

    This method will convert the abbreviated Flatpak ref to a full Flatpak ref.

    Turn "org.fedoraproject.Stable:app/org.example.Foo//stable" into
    ("org.fedoraproject.Stable", "app/org.example.Foo/amd64/stable")
    """
    collection_parts = ref.split(":", 1)
    if len(collection_parts) == 2:
        collection = collection_parts[0]
        ref = collection_parts[1]
    else:
        collection = None

    parts = ref.split("/")
    if len(parts) != 4:
        raise RuntimeError("Can't parse reference")
    if parts[2] == "":
        parts[2] = get_arch()

    return collection, "/".join(parts)
