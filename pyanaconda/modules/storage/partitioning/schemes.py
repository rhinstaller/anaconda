#
# Automatic partitioning scheme metadata.
#
# Copyright (C) 2026 Red Hat, Inc.
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
from collections import namedtuple

from blivet.devicefactory import is_supported_device_type
from blivet.formats import get_format
from pykickstart.constants import (
    AUTOPART_TYPE_BTRFS,
    AUTOPART_TYPE_LVM,
    AUTOPART_TYPE_LVM_THINP,
    AUTOPART_TYPE_PLAIN,
    AUTOPART_TYPE_STRATIS,
)

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.configuration.storage import PartitioningScheme
from pyanaconda.core.i18n import N_
from pyanaconda.core.storage import AUTOPART_DEVICE_TYPES, DEVICE_TYPES
from pyanaconda.modules.common.structures.partitioning import PartitioningSchemeData
from pyanaconda.modules.storage.devicetree.utils import get_supported_filesystems

__all__ = [
    "get_default_partitioning_scheme_name",
    "get_supported_file_system_types",
    "get_supported_partitioning_schemes",
]

SchemeSpec = namedtuple(
    "SchemeSpec",
    (
        "name",
        "autopart_type",
        "title",
        "has_file_system_type",
    )
)

# All autopart schemes exposed to UIs, in display order.
_SCHEME_SPECS = (
    SchemeSpec(
        "PLAIN",
        AUTOPART_TYPE_PLAIN,
        N_("Standard Partition"),
        True,
    ),
    SchemeSpec(
        "BTRFS",
        AUTOPART_TYPE_BTRFS,
        N_("Btrfs"),
        False,
    ),
    SchemeSpec(
        "LVM",
        AUTOPART_TYPE_LVM,
        N_("LVM"),
        True,
    ),
    SchemeSpec(
        "LVM_THINP",
        AUTOPART_TYPE_LVM_THINP,
        N_("LVM Thin Provisioning"),
        True,
    ),
    SchemeSpec(
        "STRATIS",
        AUTOPART_TYPE_STRATIS,
        N_("Stratis"),
        False,
    ),
)


def _is_supported_autopart_type(autopart_type):
    device_type = AUTOPART_DEVICE_TYPES.get(autopart_type, DEVICE_TYPES.UNSUPPORTED)
    return is_supported_device_type(device_type)


def get_default_partitioning_scheme_name():
    """Return the configured default partitioning scheme name."""
    return PartitioningScheme(conf.storage.default_scheme).name


def get_supported_file_system_types():
    """Return the file system types an autopart request can ask for.

    The conditions are the ones blivet itself enforces in
    Blivet._check_valid_fstype, which is where the requested type ends up.
    """
    def is_valid(fs_type):
        fmt = get_format(fs_type)
        return fmt.mountable and fmt.formattable and fmt.supported and fmt.linux_native

    return sorted(filter(is_valid, get_supported_filesystems()))


def get_supported_partitioning_schemes():
    """Return metadata for autopart schemes supported on this system."""
    schemes = []

    for spec in _SCHEME_SPECS:
        if not _is_supported_autopart_type(spec.autopart_type):
            continue

        data = PartitioningSchemeData()
        data.scheme_id = spec.name
        data.has_file_system_type = spec.has_file_system_type
        schemes.append(data)

    return schemes
