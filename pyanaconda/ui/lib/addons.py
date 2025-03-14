#
# Copyright (C) 2021  Red Hat, Inc.
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

__all__ = ["collect_addon_ui_paths"]

log = get_module_logger(__name__)


def collect_addon_ui_paths(addon_paths, subdir):
    """Collect the paths of spokes and categories that belong to add-ons.

    This method looks into the directories present
    in toplevel addon paths and registers each subdirectory
    as a new addon identified by that subdirectory name.

    It then registers spokes and categories paths for the
    application to use.

    :param addon_paths: a list of top-level add-on paths
    :param subdir: a name of a subdirectory, for example 'gui'
    """

    module_paths = {
        "spokes": [],
        "categories": []
    }

    for path in addon_paths:
        try:
            directories = os.listdir(path)
        except OSError:
            directories = []

        for addon_id in directories:
            addon_spoke_path = os.path.join(path, addon_id, subdir, "spokes")

            if os.path.isdir(addon_spoke_path):
                module_paths["spokes"].append(
                    ("%s.%s.spokes.%%s" % (addon_id, subdir), addon_spoke_path)
                )
                log.debug('Loading spokes into module path for addon %s', addon_id)

            addon_category_path = os.path.join(path, addon_id, "categories")

            if os.path.isdir(addon_category_path):
                module_paths["categories"].append(
                    ("%s.categories.%%s" % addon_id, addon_category_path)
                )
                log.debug('Loading categories into module path for addon %s', addon_id)

    return module_paths
