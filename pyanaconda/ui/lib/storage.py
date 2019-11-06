#
# Copyright (C) 2019  Red Hat, Inc.
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
#

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import PARTITIONING_METHOD_AUTOMATIC
from pyanaconda.modules.common.constants.services import STORAGE

log = get_module_logger(__name__)


def find_partitioning():
    """Find a partitioning to use or create a new one.

    :return: a proxy of a partitioning module
    """
    storage_proxy = STORAGE.get_proxy()
    object_paths = storage_proxy.CreatedPartitioning

    if object_paths:
        # Choose the last created partitioning.
        object_path = object_paths[-1]
    else:
        # Or create the automatic partitioning.
        object_path = storage_proxy.CreatePartitioning(
            PARTITIONING_METHOD_AUTOMATIC
        )

    return STORAGE.get_proxy(object_path)
