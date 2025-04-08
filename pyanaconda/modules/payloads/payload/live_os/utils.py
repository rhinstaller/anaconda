
# Copyright (C) 2020 Red Hat, Inc.
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
import glob
import os

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.payloads.base.utils import sort_kernel_version_list

log = get_module_logger(__name__)


def get_kernel_version_list(root_path):
    """Get a list of installed kernel versions.

    :param root_path: a path to the system root
    :return: a list of kernel versions
    """
    efi_dir = conf.bootloader.efi_dir
    files = glob.glob(root_path + "/boot/vmlinuz-*")
    files.extend(glob.glob(root_path + "/boot/efi/EFI/{}/vmlinuz-*".format(efi_dir)))

    kernel_version_list = [
        f.split("/")[-1][8:] for f in files
        if os.path.isfile(f) and "-rescue-" not in f
    ]

    sort_kernel_version_list(kernel_version_list)
    return kernel_version_list
