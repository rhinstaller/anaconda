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
from abc import ABC

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import SystemBus
from pyanaconda.core.signal import Signal
from pyanaconda.keyboard import (
    InvalidLayoutVariantSpec,
    join_layout_variant,
    parse_layout_variant,
)
from pyanaconda.modules.common.constants.services import LOCALED

log = get_module_logger(__name__)


__all__ = ["CompositorLocaledWrapper", "LocaledWrapper"]


class LocaledWrapperBase(ABC):
    """Class wrapping systemd-localed daemon functionality."""

    def __init__(self):
        self._localed_proxy = None

        if not conf.system.provides_system_bus:
            log.debug("Not using localed service: "
                      "system does not provide system bus according to configuration.")
            return

        if not SystemBus.check_connection():
            log.debug("Not using localed service: "
                      "system bus connection check failed.")
            return

        self._localed_proxy = LOCALED.get_proxy()

    def get_layouts_variants(self):
        """Read current X11 layouts with variants from system.

        :return: a list of "layout (variant)" or "layout" layout specifications
        :rtype: list(str)
        """
        if not self._localed_proxy:
            return []

        layouts = self._localed_proxy.X11Layout
        variants = self._localed_proxy.X11Variant

        return self._from_localed_format(layouts, variants)

    @staticmethod
    def _from_localed_format(layouts, variants):
        layouts = layouts.split(",") if layouts else []
        variants = variants.split(",") if variants else []

        # if there are more layouts than variants, empty strings should be appended
        diff = len(layouts) - len(variants)
        variants.extend(diff * [""])

        return [join_layout_variant(layout, variant) for layout, variant in zip(layouts, variants)]

    @property
    def options(self):
        """Get current X11 options.

        :return: a list of X11 options
        :rtype: list(str)
        """
        if not self._localed_proxy:
            return []

        options = self._localed_proxy.X11Options

        return options.split(",") if options else []

    def set_layouts(self, layouts_variants, options=None, convert=False):
        """Set X11 layouts.

        :param layouts_variants: list of 'layout (variant)' or 'layout'
                                 specifications of layouts and variants
        :type layouts_variants: list(str)
        :param options: list of X11 options that should be set
        :type options: list(str) or None
        :param convert: whether the layouts should be converted to a VConsole keymap
                        (see set_and_convert_layouts)
        :type convert: bool
        """
        if not self._localed_proxy:
            return

        layouts = []
        variants = []
        parsing_failed = False

        for layout_variant in (nonempty for nonempty in layouts_variants if nonempty):
            try:
                (layout, variant) = parse_layout_variant(layout_variant)
            except InvalidLayoutVariantSpec as e:
                log.debug("Parsing of %s failed: %s", layout_variant, e)
                parsing_failed = True
                continue
            layouts.append(layout)
            variants.append(variant)

        if not layouts and parsing_failed:
            return

        layouts_str = ",".join(layouts)
        variants_str = ",".join(variants)
        options_str = ",".join(options) if options else ""

        log.debug("Setting keyboard layouts: '%s' options: '%s' convert: '%s",
                  layouts_variants, options, convert)

        self._localed_proxy.SetX11Keyboard(
            layouts_str,
            "pc105",
            variants_str,
            options_str,
            convert,
            False
        )


class LocaledWrapper(LocaledWrapperBase):
    """Localed wrapper class which is used to installation.

    It adds support for keymap and conversion methods between keymap and layouts.
    """

    @property
    def keymap(self):
        """Get current VConsole keymap.

        :return: VConsole keymap specification
        :rtype: string
        """
        if not self._localed_proxy:
            return ""

        return self._localed_proxy.VConsoleKeymap

    def set_keymap(self, keymap, convert=False):
        """Set current VConsole keymap.

        :param keymap: VConsole keymap that should be set
        :type keymap: str
        :param convert: whether the keymap should be converted and set as X11 layout
        :type convert: bool
        """
        if not self._localed_proxy:
            return ""

        self._localed_proxy.SetVConsoleKeyboard(keymap, "", convert, False)

    def convert_keymap(self, keymap):
        """Get X11 layouts and variants by converting VConsole keymap.

        NOTE: Systemd-localed performs the conversion. Current VConsole keymap
        and X11 layouts are set temporarily to the converted values in the
        process of conversion.

        :param keymap: VConsole keymap
        :type keymap: str
        :return: a list of "layout (variant)" or "layout" layout specifications
                 obtained by conversion of VConsole keymap
        :rtype: list(str)
        """
        if not self._localed_proxy:
            return []

        # hack around systemd's lack of functionality -- no function to just
        # convert without changing keyboard configuration
        orig_layouts_variants = self.get_layouts_variants()
        orig_keymap = self.keymap
        converted_layouts = self.set_and_convert_keymap(keymap)
        self.set_layouts(orig_layouts_variants)
        self.set_keymap(orig_keymap)

        return converted_layouts

    def set_and_convert_keymap(self, keymap):
        """Set VConsole keymap and set and get converted X11 layouts.

        :param keymap: VConsole keymap
        :type keymap: str
        :return: a list of "layout (variant)" or "layout" layout specifications
                 obtained by conversion from VConsole keymap
        :rtype: list(str)
        """
        self.set_keymap(keymap, convert=True)

        return self.get_layouts_variants()

    def set_and_convert_layouts(self, layouts_variants):
        """Set X11 layouts and set and get converted VConsole keymap.

        :param layouts_variants: list of 'layout (variant)' or 'layout'
                                 specifications of layouts and variants
        :type layouts_variants: list(str)
        :return: a VConsole keymap obtained by conversion from X11 layouts
        :rtype: str
        """

        self.set_layouts(layouts_variants, convert=True)

        return self.keymap

    def convert_layouts(self, layouts_variants):
        """Get VConsole keymap by converting X11 layouts and variants.

        NOTE: Systemd-localed performs the conversion. Current VConsole keymap
        and X11 layouts are set temporarily to the converted values in the
        process of conversion.

        :param layouts_variants: list of 'layout (variant)' or 'layout'
                                 specifications of layouts and variants
        :type layouts_variants: list(str)
        :return: a VConsole keymap obtained by conversion from X11 layouts
        :rtype: str
        """
        if not self._localed_proxy:
            return ""

        # hack around systemd's lack of functionality -- no function to just
        # convert without changing keyboard configuration
        orig_layouts_variants = self.get_layouts_variants()
        orig_keymap = self.keymap
        ret = self.set_and_convert_layouts(layouts_variants)
        self.set_layouts(orig_layouts_variants)
        self.set_keymap(orig_keymap)

        return ret


class CompositorLocaledWrapper(LocaledWrapperBase):
    """Localed wrapper class which is used to control compositor.

    It adds support for layout selection and reactions on the compositor system changes.
    """

    def __init__(self):
        super().__init__()

        self._user_layouts_variants = []
        self._last_layouts_variants = []

        self.compositor_layouts_changed = Signal()
        self.compositor_selected_layout_changed = Signal()

        # to reflect updates from the compositor
        self._localed_proxy.PropertiesChanged.connect(self._on_properties_changed)

    def _on_properties_changed(self, interface, changed_props, invalid_props):
        if "X11Layout" in changed_props or "X11Variant" in changed_props:
            layouts_variants = self._from_localed_format(changed_props["X11Layout"].get_string(),
                                                         changed_props["X11Variant"].get_string())
            # This part is a bit tricky. The signal processing here means that compositor has
            # changed current layouts configuration. This could happen for multiple reasons:
            # - user changed the layout in compositor
            # - Anaconda set the layout to compositor
            # - any other magic logic for compositor (we just don't know)
            #
            # The question is how we should behave:
            # - we don't want to take compositor layouts to Anaconda because that will change
            #   what user will have in the installed system.
            # - we don't want to force our layouts to compositor because that would forbid user
            #   to change compositor layout when Anaconda runs in background
            #
            # The best shot seems to just signal out that the layout has changed and nothing else.

            # layouts has changed in compositor, always emit this signal
            log.debug("Localed layouts has changed. Last known: '%s' current: '%s'",
                      self._last_layouts_variants, layouts_variants)
            self.compositor_layouts_changed.emit(layouts_variants)

            # check if last selected variant has changed
            # nothing is selected in compositor
            if not layouts_variants:
                log.warning("Compositor layouts not set.")
                self.compositor_selected_layout_changed.emit("")
            # we don't know last used layouts
            elif not self._last_layouts_variants:
                log.debug("Compositor selected layout is different. "
                          "Missing information about last selected layouts.")
                self.compositor_selected_layout_changed.emit(layouts_variants[0])
            # selected (first) has changed
            elif layouts_variants[0] != self._last_layouts_variants[0]:
                log.debug("Compositor selected layout is different.")
                self.compositor_selected_layout_changed.emit(layouts_variants[0])

            self._last_layouts_variants = layouts_variants

    @property
    def current_layout_variant(self):
        """Get first (current) layout with variant.

        :return: a list of "layout (variant)" or "layout" layout specifications
        :rtype: list(str)
        """
        layouts_variants = self.get_layouts_variants()
        return "" if not layouts_variants else layouts_variants[0]

    def get_layouts_variants(self):
        """Read current X11 layouts with variants from system.

        Store information about the last selected layout variant used.

        :return: a list of "layout (variant)" or "layout" layout specifications
        :rtype: list(str)
        """
        self._last_layouts_variants = super().get_layouts_variants()
        return self._last_layouts_variants

    def set_layouts(self, layouts_variants, options=None, convert=False):
        """Set X11 layouts.

        Store user selected layouts with variants.

        :param layouts_variants: list of 'layout (variant)' or 'layout'
                                 specifications of layouts and variants
        :type layouts_variants: list(str)
        :param options: list of X11 options that should be set
        :type options: list(str)
        :param convert: whether the layouts should be converted to a VConsole keymap
                        (see set_and_convert_layouts)
        :type convert: bool
        """
        self._set_layouts(layouts_variants, options, convert)
        log.debug("Storing layouts for compositor configured by user")
        self._user_layouts_variants = layouts_variants

    def _set_layouts(self, layouts_variants, options=None, convert=False):
        """Set a new layouts for compositor.

        Extension of the parent code with compositor specific code.
        """
        # If options are not set let's use from a system so we don't change the system settings
        if options is None:
            options = self.options
            log.debug(
                "Keyboard layouts for compositor are missing options. Use compositor options: %s",
                options,
            )

        # Disable keyboard layout switching by keyboard shortcut as it is hard to make this
        # working from the system to localed. The current layout is in general problematic to
        # decide.
        log.debug(
            "Disable keyboard layouts switching shortcut to compositor from the options: '%s'",
            options,
        )
        options = list(filter(lambda x: not x.startswith("grp:"), options))

        # store configuration from user
        super().set_layouts(layouts_variants, options, convert)

    def select_layout(self, layout_variant):
        """Select layout from the list of current layouts set.

        This will search for the given layout variant in the list and move it as first
        in the list. The first layout in systemd is taken as the used one.

        :param layout_variant: The layout to set, with format "layout (variant)"
            (e.g. "cz (qwerty)")
        :type layout_variant: str
        :return: If the keyboard layout was activated
        :rtype: bool
        """
        # ignore compositor layouts but force Anaconda configuration
        layouts = self._user_layouts_variants

        try:
            new_layouts = self._shift_list(layouts, layout_variant)
            self._set_layouts(new_layouts)
            return True
        except ValueError:
            log.warning("Can't set layout: '%s' as first to the current set: %s",
                        layout_variant, layouts)
            return False

    @staticmethod
    def _shift_list(source_layouts, value_to_first):
        """Helper method to reorder list of layouts and move one as first in the list.

        We should preserve the ordering just shift items from start of the list to the
        end in the same order.

        When we want to set 2nd as first in this list:
        ["cz", "es", "us"]
        The result should be:
        ["es", "us", "cz"]

        So the compositor has the same next layout as Anaconda.

        :raises: ValueError: if the list is small or the layout is not inside
        """
        value_id = source_layouts.index(value_to_first)
        new_list = source_layouts[value_id:len(source_layouts)] + source_layouts[0:value_id]
        return new_list

    def select_next_layout(self):
        """Select (make it first) next layout for compositor.

        Find current compositor layout in the list of defined layouts and set next to it as
        current (first) for compositor. We need to have user defined list because compositor
        layouts will change with the selection. Store this list when user is setting configuration
        to compositor. This list must not change ordering.

        :param user_layouts: List of layouts selected by user in Anaconda.
        :type user_layouts: [str]
        :return: If switch was successful True otherwise False
        :rtype: bool
        """
        current_layout = self.current_layout_variant
        layout_id = 0

        if not self._user_layouts_variants:
            log.error("Can't switch next layout - user defined keyboard layout is not present!")
            return False

        # find next layout
        for i, v in enumerate(self._user_layouts_variants):
            if v == current_layout:
                layout_id = i + 1
                layout_id %= len(self._user_layouts_variants)

        try:
            new_layouts = self._shift_list(self._user_layouts_variants,
                                           self._user_layouts_variants[layout_id])
            self._set_layouts(new_layouts)
            return True
        except ValueError:
            log.warning("Can't set next keyboard layout %s", self._user_layouts_variants)
            return False
