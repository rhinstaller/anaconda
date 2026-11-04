#
# Copyright (C) 2026 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Read operating system metadata without depending on installer configuration."""

import logging
import os.path

log = logging.getLogger("anaconda.core.os_release")


def get_os_release_value(name, sysroot="/"):
    """Read os-release files and return a value of the specified parameter.

    :param name: a name of the parameter (for example, "VERSION_ID")
    :param sysroot: a path to the system root
    :return: a string with the value or None if nothing found
    """
    # Match the variable assignment (for example, "VERSION_ID=").
    name += "="

    # Search all os-release files in the system root.
    paths = ("/etc/os-release", "/usr/lib/os-release")

    for path in paths:
        try:
            with open(os.path.join(sysroot, path.lstrip(os.path.sep)), "r") as f:
                for line in f:
                    # Match the current line.
                    if not line.startswith(name):
                        continue

                    # Get the value.
                    value = line[len(name):]

                    # Strip spaces and then quotes.
                    value = value.strip().strip("\"'")
                    return value
        except FileNotFoundError:
            pass

    # No value found.
    log.debug("%s not found in os-release files", name[:-1])
    return None
