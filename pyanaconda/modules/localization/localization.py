#
# Kickstart module for language and keyboard settings.
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
from pyanaconda.dbus import DBus
from pyanaconda.dbus.constants import MODULE_LOCALIZATION_NAME, MODULE_LOCALIZATION_PATH
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.localization.localization_interface import LocalizationInterface
from pyanaconda.modules.localization.kickstart import LocalizationKickstartSpecification

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class LocalizationModule(KickstartModule):
    """The Localization module."""

    def __init__(self):
        super().__init__()
        self.language_changed = Signal()
        self._language = ""

        self.language_support_changed = Signal()
        self._language_support = []

        self.keyboard_changed = Signal()
        self._keyboard = ""

        self.vc_keymap_changed = Signal()
        self._vc_keymap = ""

        self.x_layouts_changed = Signal()
        self._x_layouts = []

        self.switch_options_changed = Signal()
        self._switch_options = []

        self.keyboard_seen_changed = Signal()
        self._keyboard_seen = False

    def publish(self):
        """Publish the module."""
        DBus.publish_object(LocalizationInterface(self), MODULE_LOCALIZATION_PATH)
        DBus.register_service(MODULE_LOCALIZATION_NAME)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return LocalizationKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("Processing kickstart data...")

        # lang
        self.set_language(data.lang.lang)
        self.set_language_support(data.lang.addsupport)

        # keyboard
        self.set_keyboard(data.keyboard._keyboard)
        self.set_vc_keymap(data.keyboard.vc_keymap)
        self.set_x_layouts(data.keyboard.x_layouts)
        self.set_switch_options(data.keyboard.switch_options)

        self.set_keyboard_seen(data.keyboard.seen)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()

        # lang
        data.lang.lang = self.language
        data.lang.addsupport = self.language_support

        # keyboard
        data.keyboard._keyboard = self.keyboard
        data.keyboard.vc_keymap = self.vc_keymap
        data.keyboard.x_layouts = self.x_layouts
        data.keyboard.switch_options = self.switch_options

        return str(data)

    @property
    def language(self):
        """Return the language."""
        return self._language

    def set_language(self, language):
        """Set the language."""
        self._language = language
        self.language_changed.emit()
        log.debug("Language is set to %s.", language)

    @property
    def language_support(self):
        """Return suppored languages."""
        return self._language_support

    def set_language_support(self, language_support):
        """Set supported languages."""
        self._language_support = language_support
        self.language_support_changed.emit()
        log.debug("Language support is set to %s.", language_support)

    @property
    def keyboard(self):
        """Return keyboard."""
        return self._keyboard

    def set_keyboard(self, keyboard):
        """Set the keyboard."""
        self._keyboard = keyboard
        self.keyboard_changed.emit()
        log.debug("Keyboard is set to %s.", keyboard)

    @property
    def vc_keymap(self):
        """Return virtual console keymap."""
        return self._vc_keymap

    def set_vc_keymap(self, vc_keymap):
        """Set virtual console keymap."""
        self._vc_keymap = vc_keymap
        self.vc_keymap_changed.emit()
        log.debug("Virtual console keymap is set to %s.", vc_keymap)

    @property
    def x_layouts(self):
        """Return X Keyboard Layouts."""
        return self._x_layouts

    def set_x_layouts(self, x_layouts):
        """Set X Keyboard Layouts."""
        self._x_layouts = x_layouts
        self.x_layouts_changed.emit()
        log.debug("X Layouts are set to %s.", x_layouts)

    @property
    def switch_options(self):
        """Return X layout switching options."""
        return self._switch_options

    def set_switch_options(self, switch_options):
        """Set X layout switching options."""
        self._switch_options = switch_options
        self.switch_options_changed.emit()
        log.debug("X layout switch options are set to %s.", switch_options)

    @property
    def keyboard_seen(self):
        """Was keyboard command seen in kickstart?"""
        return self._keyboard_seen

    def set_keyboard_seen(self, keyboard_seen):
        """Set whether keyboard command was seen in kickstart."""
        self._keyboard_seen = keyboard_seen
        self.keyboard_seen_changed.emit()
        log.debug("keyboard command considered seen in kicksatart: %s.", keyboard_seen)
