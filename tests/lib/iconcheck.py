#
# iconcheck.py: Gtk icon testing
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: David Shea <dshea@redhat.com>

import os

ICON_PATH = "/usr/share/icons/gnome"
ICON_EXTS = ("png", "jpg", "svg")

# This method depends on gnome-icon-theme being installed. gnome-icon-theme-legacy
# may be installed, but the icons in it will not be considered.
def icon_exists(icon_name):
    for dirpath, _dirs, files in os.walk(ICON_PATH):
        for icon in (icon_name + "." + ext for ext in ICON_EXTS):
            if icon in files:
                icon_path = os.path.join(dirpath, icon)

                # If the file is a symbolic link, it's a legacy icon; reject it
                if os.path.islink(icon_path):
                    return False
                else:
                    return True

    # Nothing found
    return False
