#
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from os.path import join
from blivet.arch import get_arch


def is_valid_install_disk(tree_dir):
    """Is the disk a valid installation repository?

    Success criteria:
    - Disk must be already mounted at tree_dir.
    - A .discinfo file exists.
    - Third line of .discinfo equals current architecture.

    :param str tree_dir: Where the disk is mounted.
    :rtype: bool
    """
    try:
        with open(join(tree_dir, ".discinfo"), "r") as f:
            f.readline()  # throw away timestamp
            f.readline()  # throw away description
            arch = f.readline().strip()
            if arch == get_arch():
                return True
    except OSError:
        pass
    return False
