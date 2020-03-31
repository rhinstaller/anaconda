#
# Copyright (C) 2018 Red Hat, Inc.
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
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
from pyanaconda.core.configuration.base import Section


class UserInterfaceSection(Section):
    """The User Interface section."""

    @property
    def custom_stylesheet(self):
        """The path to a custom stylesheet."""
        return self._get_option("custom_stylesheet", str)

    @property
    def help_directory(self):
        """The path to a directory with help files."""
        return self._get_option("help_directory", str)

    @property
    def default_help_pages(self):
        """Default help pages for TUI, GUI and Live OS."""
        values = self._get_option("default_help_pages", str).split()

        if not values:
            return "", "", ""

        if len(values) != 3:
            raise ValueError("Invalid number of values: {}".format(values))

        return tuple(values)

    @property
    def blivet_gui_supported(self):
        """Is the partitioning with blivet-gui supported?"""
        return self._get_option("blivet_gui_supported", bool)

    @property
    def hidden_spokes(self):
        """A list of spokes to hide in UI.

        :return: a list of strings
        """
        return self._get_option("hidden_spokes", str).split()

    @property
    def decorated_window(self):
        """Run GUI installer in a decorated window.

        By default, the window is not decorated, so it doesn't
        have a title bar, resize controls, etc.

        :return: True or False
        """
        return self._get_option("decorated_window", bool)
