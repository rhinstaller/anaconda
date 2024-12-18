#
# Subscription related helper functions.
#
# Copyright (C) 2020  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os

from pyanaconda.core.constants import RHSM_SYSPURPOSE_FILE_PATH
from pyanaconda.core.path import join_paths


def check_system_purpose_set(sysroot="/"):
    """Check if System Purpose has been set for the system.

    By manipulating the sysroot parameter it is possible to
    check is System Purpose has been set for both the installation
    environment and the target system.

    For installation environment use "/", for the target system
    path to the installation root.

    :param str sysroot: system root where to check
    :return: True if System Purpose has been set, False otherwise
    """
    syspurpose_path = join_paths(sysroot, RHSM_SYSPURPOSE_FILE_PATH)
    return os.path.exists(syspurpose_path)
