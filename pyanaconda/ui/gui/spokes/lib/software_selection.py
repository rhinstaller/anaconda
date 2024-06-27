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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.ui.gui.utils import escape_markup, blockedHandler

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Pango

log = get_module_logger(__name__)

__all__ = ["SeparatorRow", "GroupListBoxRow", "EnvironmentListBoxRow"]


class SeparatorRow(Gtk.ListBoxRow):

    def __init__(self):
        """Create a new list box row with a separator."""
        super().__init__()
        self.add(Gtk.Separator())


class CustomListBoxRow(Gtk.ListBoxRow):
    """A base class for a software selection row.."""

    def __init__(self, data, selected):
        """Create a new list box row.

        :param data: the data for the row
        :param selected: is the row selected by default?
        """
        super().__init__()
        self.data = data
        self._create_row(selected)

    def _create_row(self, selected):
        """Create a new row."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )

        button = self._create_button()
        button.set_valign(Gtk.Align.START)
        button.set_active(selected)
        button.connect("toggled", self._on_button_toggled)
        box.add(button)

        label = self._create_label()
        box.add(label)

        self.add(box)

    def _create_button(self):
        """Create a row button."""
        return Gtk.CheckButton()

    def _on_button_toggled(self, button):
        """A callback of a toggled button."""
        self.activate()

    def _create_label(self):
        """Create a row label."""
        # ruff: noqa: UP032
        text = "<b>{}</b>\n{}".format(
            escape_markup(self.data.name),
            escape_markup(self.data.description)
        )
        label = Gtk.Label(
            label=text,
            use_markup=True,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            hexpand=True,
            xalign=0,
            yalign=0.5
        )
        return label

    def toggle_button(self, active):
        """Toggle the row button."""
        box = self.get_children()[0]
        button = box.get_children()[0]

        with blockedHandler(button, self._on_button_toggled):
            button.set_active(active)


class GroupListBoxRow(CustomListBoxRow):
    """A list box row for a group."""

    def get_group_id(self):
        """Get an ID of the group.

        :return: a string with the ID
        """
        return self.data.id


class EnvironmentListBoxRow(CustomListBoxRow):
    """A list box row for an environment."""

    _button_group = None

    @classmethod
    def _get_button_group(cls):
        """Get the button group for all radio buttons.

        Add an invisible radio button so that we can show
        the environment list with no radio buttons ticked.
        """
        if not cls._button_group:
            cls._button_group = Gtk.RadioButton(group=None)
            cls._button_group.set_active(True)

        return cls._button_group

    def _create_button(self):
        """Create a new radio button for the row."""
        return Gtk.RadioButton(group=self._get_button_group())

    def _on_button_toggled(self, button):
        """A callback of a toggled radio button."""
        # If the radio button toggled to inactive,
        # don't reactivate the row.
        if not button.get_active():
            return

        super()._on_button_toggled(button)

    def get_environment_id(self):
        """Get an ID of the environment.

        :return: a string with the ID
        """
        return self.data.id
