#
# Utility functions shared for the whole payload module.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import functools
import os
import stat

from packaging.version import LegacyVersion as parse_version

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


def get_dir_size(directory):
    """Get the size of a directory and all its subdirectories.

    :param str directory: the name of the directory to find the size of
    :return: the size of the directory in kilobytes
    """
    def get_subdir_size(directory):
        # returns size in bytes
        try:
            mydev = os.lstat(directory)[stat.ST_DEV]
        except OSError as e:
            log.debug("failed to stat %s: %s", directory, e)
            return 0

        try:
            dirlist = os.listdir(directory)
        except OSError as e:
            log.debug("failed to listdir %s: %s", directory, e)
            return 0

        dsize = 0
        for f in dirlist:
            curpath = '%s/%s' % (directory, f)
            try:
                sinfo = os.lstat(curpath)
            except OSError as e:
                log.debug("failed to stat %s/%s: %s", directory, f, e)
                continue

            if stat.S_ISDIR(sinfo[stat.ST_MODE]):
                if os.path.ismount(curpath):
                    continue
                if mydev == sinfo[stat.ST_DEV]:
                    dsize += get_subdir_size(curpath)
            elif stat.S_ISREG(sinfo[stat.ST_MODE]):
                dsize += sinfo[stat.ST_SIZE]

        return dsize
    return get_subdir_size(directory) // 1024


def sort_kernel_version_list(kernel_version_list):
    """Sort the given kernel version list."""
    kernel_version_list.sort(key=functools.cmp_to_key(_compare_versions))


def _compare_versions(v1, v2):
    """Compare two version number strings."""
    first_version = parse_version(v1)
    second_version = parse_version(v2)
    return (first_version > second_version) - (first_version < second_version)
