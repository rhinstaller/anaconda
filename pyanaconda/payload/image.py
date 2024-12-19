#
# image.py: Support methods for CD/DVD and ISO image installations.
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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
import os.path
import tempfile

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.storage import MountFilesystemError
from pyanaconda.payload import utils as payload_utils

log = get_module_logger(__name__)


def find_optical_install_media():
    """Find a device with a valid optical install media.

    Return the first device containing a valid optical install
    media for this product.

    FIXME: This is duplicated in SetUpCdromSourceTask.run

    :return: a device name or None
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)

    for dev in device_tree.FindOpticalMedia():
        mountpoint = tempfile.mkdtemp()

        try:
            try:
                payload_utils.mount_device(dev, mountpoint)
            except MountFilesystemError:
                continue
            try:
                from pyanaconda.modules.payloads.source.utils import (
                    is_valid_install_disk,
                )
                if not is_valid_install_disk(mountpoint):
                    continue
            finally:
                payload_utils.unmount_device(dev, mountpoint)
        finally:
            os.rmdir(mountpoint)

        return dev

    return None
