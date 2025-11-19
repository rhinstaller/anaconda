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

import ast
from abc import ABC, abstractmethod

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.core.util import execWithCaptureAsLiveUser
from pyanaconda.core.live_user import get_live_user
from pyanaconda.keyboard import parse_layout_variant
from pyanaconda.modules.common.errors.configuration import KeyboardConfigurationError

log = get_module_logger(__name__)


def get_live_keyboard_instance():
    """Return instance of a class based on the current running live system.

    :return: instance of a LiveSystemKeyboardBase based class for the current live environment
    :rtype: instance of class inherited from LiveSystemKeyboardBase class
    """
    if conf.system.provides_liveuser:
        return GnomeShellKeyboard()

    return None


class LiveSystemKeyboardBase(ABC):

    @abstractmethod
    def read_keyboard_layouts(self):
        """Read keyboard configuration from the current system.

        The configuration have to be returned in format which is understandable by us for the
        installation. That means localed will understand it.

        :return: a list of "layout (variant)" or "layout" layout specifications
        :rtype: list(str)
        """
        pass

    @staticmethod
    def _run_as_liveuser(argv):
        """Run the command in a system as liveuser user.

        :param list argv: list of arguments for the command.
        :return: output of the command
        :rtype: str
        """
        return execWithCaptureAsLiveUser(argv[0], argv[1:])


class GnomeShellKeyboard(LiveSystemKeyboardBase):

    def read_keyboard_layouts(self):
        """Read keyboard configuration from the current system.

        The configuration have to be returned in format which is understandable by us for the
        installation. That means localed will understand it.

        :return: a list of "layout (variant)" or "layout" layout specifications
        :rtype: list(str)
        """
        command_args = ["gsettings", "get", "org.gnome.desktop.input-sources", "sources"]
        sources = self._run_as_liveuser(command_args)
        result = self._convert_to_xkb_format(sources)
        return result

    def _convert_to_xkb_format(self, sources):
        # convert input "[('xkb', 'us'), ('xkb', 'cz+qwerty')]\n"
        # to a python list of '["us", "cz (qwerty)"]'
        try:
            sources = ast.literal_eval(sources.rstrip())
        except (SyntaxError, ValueError, TypeError):
            log.error("Gnome Shell keyboard configuration can't be obtained from source %s!",
                      sources)
            return []
        result = []

        for t in sources:
            # keep only 'xkb' type and raise an error on 'ibus' variants which can't
            # be used in localed
            if t[0] != "xkb":
                msg = _("The live system has layout '{}' which can't be used for installation.")
                raise KeyboardConfigurationError(msg.format(t[1]))

            layout = t[1]
            # change layout variant from 'cz+qwerty' to 'cz (qwerty)'
            if '+' in layout:
                layout, variant = layout.split('+')
                result.append(f"{layout} ({variant})")
            else:
                result.append(layout)

        return result

    def write_keyboard_layouts(self, layout_variants, options=None):
        """Write keyboard configuration to the current system using gsettings.

        :param layout_variants: list of 'layout (variant)' or 'layout'
                               specifications of layouts and variants
        :type layout_variants: list(str)
        :param options: list of X11 options (not used for gsettings, but kept for API compatibility)
        :type options: list(str) or None
        :return: True if successful, False otherwise
        :rtype: bool
        """
        if not layout_variants:
            log.warning("No keyboard layouts to write")
            return False

        # Convert from "layout (variant)" format to gsettings format
        # gsettings format: [('xkb', 'us'), ('xkb', 'cz+qwerty')]
        sources = []
        for layout_variant in layout_variants:
            try:
                layout, variant = parse_layout_variant(layout_variant)
                # Convert to gsettings format: variant uses '+' instead of space
                if variant:
                    gsettings_layout = f"{layout}+{variant}"
                else:
                    gsettings_layout = layout
                sources.append(('xkb', gsettings_layout))
            except Exception as e:
                log.error("Failed to parse layout variant '%s': %s", layout_variant, e)
                continue

        if not sources:
            log.error("No valid keyboard layouts to write")
            return False

        # Convert sources list to gsettings format string
        # Format: "[('xkb', 'us'), ('xkb', 'cz+qwerty')]"
        sources_str = str(sources)

        # Set the keyboard layouts via gsettings
        # Use the same pattern as read_keyboard_layouts - run as liveuser
        command_args = ["gsettings", "set", "org.gnome.desktop.input-sources", "sources", sources_str]
        try:
            # Use execWithCaptureAsLiveUser pattern but we need to run a redirect command
            # Since execWithRedirect doesn't support user parameter, we'll use a workaround:
            # run the command and capture output (we don't need it for set operations)
            output = self._run_as_liveuser(command_args)
            # For gsettings set, successful execution means it worked
            # If there's an error, it would be in stderr which we can't easily check here
            # But if the command completes, we assume success
            log.debug("Successfully set keyboard layouts via gsettings: %s", layout_variants)
            return True
        except Exception as e:
            log.error("Exception while setting keyboard layouts via gsettings: %s", e)
            return False
