#
# Handling of ifcfg files
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

import os

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


IFCFG_DIR = "/etc/sysconfig/network-scripts"
KEYFILE_DIR = "/etc/NetworkManager/system-connections"


def get_ifcfg_files_paths(directory):
    rv = []
    for name in os.listdir(directory):
        if name.startswith("ifcfg-"):
            if name == "ifcfg-lo":
                continue
            rv.append(os.path.join(directory, name))
    return rv


def get_keyfile_files_paths(directory):
    rv = []
    for name in os.listdir(directory):
        if name.endswith(".nmconnection"):
            rv.append(os.path.join(directory, name))
    return rv


def get_config_files_content(root_path=""):
    fragments = []
    file_paths = get_ifcfg_files_paths(os.path.normpath(root_path + IFCFG_DIR)) + \
        get_keyfile_files_paths(os.path.normpath(root_path + KEYFILE_DIR))
    for file_path in file_paths:
        fragments.append("{}:".format(file_path))
        with open(file_path, "r") as f:
            fragments.append(f.read().strip("\n"))
    return "\n".join(fragments)
