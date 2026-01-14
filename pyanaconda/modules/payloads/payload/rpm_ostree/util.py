#
# Copyright (C) 2023 Red Hat, Inc.
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

import os.path

import gi

gi.require_version("OSTree", "1.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gio, OSTree

from pyanaconda.core.path import join_paths

__all__ = ["get_ostree_deployment_path", "have_bootupd"]


def have_bootupd(sysroot):
    """Is bootupd/bootupctl present in sysroot?"""
    return os.path.exists(join_paths(sysroot, "/usr/bin/bootupctl"))


def get_ostree_deployment_path(sysroot_path):
    """Get the OSTree deployment path for a given sysroot.

    :param sysroot_path: path to the mounted sysroot
    :return: deployment directory path, or None if not found
    """
    # Check if this looks like an ostree installation
    ostree_deploy_path = os.path.join(sysroot_path, "ostree", "deploy")
    if not os.path.isdir(ostree_deploy_path):
        return None

    sysroot_file = Gio.File.new_for_path(sysroot_path)
    ostree_sysroot = OSTree.Sysroot.new(sysroot_file)
    ostree_sysroot.load(None)
    deployments = ostree_sysroot.get_deployments()
    if deployments:
        deployment = deployments[0]
        deployment_dir = ostree_sysroot.get_deployment_directory(deployment)
        deployment_path = deployment_dir.get_path()
        if os.path.isdir(deployment_path):
            return deployment_path

    return None
