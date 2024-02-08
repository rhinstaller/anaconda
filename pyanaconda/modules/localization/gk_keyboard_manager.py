#
# Copyright (C) 2024 Red Hat, Inc.
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

from pyanaconda.core.signal import Signal
from pyanaconda.keyboard import join_layout_variant, parse_layout_variant, KeyboardConfigError
from pyanaconda.modules.common.constants.services import GK_INPUT_SOURCES


class GkKeyboardManager(object):
    """Class wrapping GNOME Kiosk's input sources API."""

    def __init__(self):
        self.compositor_selected_layout_changed = Signal()
        self.compositor_layouts_changed = Signal()

        object_path = GK_INPUT_SOURCES.object_path + '/InputSources/Manager'
        self._proxy = GK_INPUT_SOURCES.get_proxy(object_path=object_path)
        self._proxy.PropertiesChanged.connect(self._on_properties_changed)

    def _on_properties_changed(self, interface, changed_props, invalid_props):
        for prop in changed_props:
            if prop == 'SelectedInputSource':
                layout_path = changed_props[prop]
                layout_variant = self._path_to_layout(layout_path.get_string())
                self.compositor_selected_layout_changed.emit(layout_variant)
            if prop == 'InputSources':
                layout_paths = changed_props[prop]
                layout_variants = map(self._path_to_layout, list(layout_paths))
                self.compositor_layouts_changed.emit(list(layout_variants))

    def _path_to_layout(self, layout_path):
        """Transforms a layout path as returned by GNOME Kiosk to "layout (variant)".

        :param layout_path: D-Bus path to the layout.
            (e.g. "/org/gnome/Kiosk/InputSources/xkb_cz_2b_mon_5f_todo_5f_galik")
        :type layout_path: str
        :return: The layout with format "layout (variant)" (e.g. "cn (mon_todo_galik)")
        :rtype: str

        :raise KeyboardConfigError: if layouts with invalid backend type is found
        """
        layout_proxy = GK_INPUT_SOURCES.get_proxy(object_path=layout_path)

        if layout_proxy.BackendType != 'xkb':
            raise KeyboardConfigError('Failed to get configuration from compositor')

        if '+' in layout_proxy.BackendId:
            layout, variant = layout_proxy.BackendId.split('+')
            return join_layout_variant(layout, variant)
        else:
            return layout_proxy.BackendId

    def _layout_to_xkb(self, layout_variant):
        """Transforms a "layout (variant)" to a "('xkb', 'layout+variant')".

        :param layout_variant: The layout with format "layout (variant)" (e.g. "cz (qwerty)")
        :type layout_variant: str
        :return: The layout with format "('xkb', 'layout+variant')" (e.g. "('xkb', 'cz+qwerty')")
        :rtype: str
        """
        layout, variant = parse_layout_variant(layout_variant)
        if variant:
            return ('xkb', '{0}+{1}'.format(layout, variant))
        else:
            return ('xkb', layout)

    def get_compositor_selected_layout(self):
        """Get the activated keyboard layout.

        :return: Current keyboard layout (e.g. "cz (qwerty)")
        :rtype: str
        """
        layout_path = self._proxy.SelectedInputSource
        if not layout_path or layout_path == '/':
            return ''

        return self._path_to_layout(layout_path)

    def set_compositor_selected_layout(self, layout_variant):
        """Set the activated keyboard layout.

        :param layout_variant: The layout to set, with format "layout (variant)"
            (e.g. "cz (qwerty)")
        :type layout_variant: str
        :return: If the keyboard layout was activated
        :rtype: bool
        """
        layout_paths = self._proxy.InputSources
        for layout_path in layout_paths:
            if self._path_to_layout(layout_path) == layout_variant:
                self._proxy.SelectInputSource(layout_path)
                return True

        return False

    def select_next_compositor_layout(self):
        """Set the next available layout as active."""
        self._proxy.SelectNextInputSource()

    def get_compositor_layouts(self):
        """Get all available keyboard layouts.

        :return: A list of keyboard layouts (e.g. ["cz (qwerty)", cn (mon_todo_galik)])
        :rtype: list of strings
        """
        layout_paths = self._proxy.InputSources
        layout_variants = map(self._path_to_layout, list(layout_paths))
        return list(layout_variants)

    def set_compositor_layouts(self, layout_variants, options):
        """Set the available keyboard layouts.

        :param layout_variants: A list of keyboard layouts (e.g. ["cz (qwerty)",
            cn (mon_todo_galik)])
        :type layout_variants: list of strings
        :param options: A list of switching options
        :type options: list of strings
        """
        xkb_layouts = list(map(self._layout_to_xkb, layout_variants))
        self._proxy.SetInputSources(xkb_layouts, options)
