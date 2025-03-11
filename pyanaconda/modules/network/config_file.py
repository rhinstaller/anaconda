#
# Handling of NM connection configuration files
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

import os

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["IFCFG_DIR", "KEYFILE_DIR", "get_config_files_content", "is_config_file_for_system"]

IFCFG_DIR = "/etc/sysconfig/network-scripts"
KEYFILE_DIR = "/etc/NetworkManager/system-connections"


def get_config_files_content(root_path=""):
    """Get content of all network device config files."""
    fragments = []
    for file_path in get_config_files_paths(root_path):
        fragments.append("{}:".format(file_path))
        with open(file_path, "r") as f:
            fragments.append(f.read().strip("\n"))
    return "\n".join(fragments)


def get_config_files_paths(root_path=""):
    """Get paths of all network device config files found."""
    paths = []
    for directory in (os.path.normpath(root_path + IFCFG_DIR),
                      os.path.normpath(root_path + KEYFILE_DIR)):
        if not os.path.exists(directory):
            log.info("network device config directory %s does not exist, skipping", directory)
            continue

        for filename in os.listdir(directory):
            if not (_has_keyfile_basename(filename) or _has_ifcfg_basename(filename)):
                continue
            paths.append(os.path.join(directory, filename))
    return paths


def is_config_file_for_system(filename):
    """Checks if the file stores configuration for target system."""
    dirname = os.path.dirname(filename)
    return ((dirname == IFCFG_DIR and _has_ifcfg_basename(filename)) or
            (dirname == KEYFILE_DIR and _has_keyfile_basename(filename)))


def _has_ifcfg_basename(name):
    basename = os.path.basename(name)
    return basename.startswith("ifcfg-") and basename != "ifcfg-lo"


def _has_keyfile_basename(name):
    basename = os.path.basename(name)
    return basename.endswith(".nmconnection")
