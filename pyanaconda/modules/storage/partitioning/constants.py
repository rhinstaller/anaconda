#
# The constants for partitioning.
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
#
from enum import Enum

from pyanaconda.core.constants import (
    PARTITIONING_METHOD_AUTOMATIC,
    PARTITIONING_METHOD_BLIVET,
    PARTITIONING_METHOD_CUSTOM,
    PARTITIONING_METHOD_INTERACTIVE,
    PARTITIONING_METHOD_MANUAL,
)


class PartitioningMethod(Enum):
    """Type of the partitioning method."""
    AUTOMATIC = PARTITIONING_METHOD_AUTOMATIC
    CUSTOM = PARTITIONING_METHOD_CUSTOM
    MANUAL = PARTITIONING_METHOD_MANUAL
    INTERACTIVE = PARTITIONING_METHOD_INTERACTIVE
    BLIVET = PARTITIONING_METHOD_BLIVET
