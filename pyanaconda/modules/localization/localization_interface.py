#
# DBus interface for the localization module.
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

from pyanaconda.dbus.constants import MODULE_LOCALIZATION_NAME
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.dbus.interface import dbus_interface


@dbus_interface(MODULE_LOCALIZATION_NAME)
class LocalizationInterface(KickstartModuleInterface):
    """DBus interface for Localization module."""

    def connect_signals(self):
        super().connect_signals()
        self.implementation.language_changed.connect(self.changed("Language"))
        self.implementation.language_support_changed.connect(self.changed("LanguageSupport"))

    @property
    def Language(self) -> Str:
        """The language the system will use."""
        return self.implementation.language

    @emits_properties_changed
    def SetLanguage(self, language: Str):
        """Set the language.

        Sets the language to use during installation and the default language
        to use on the installed system.

        The value (language ID) can be the same as any recognized setting for
        the ``$LANG`` environment variable, though not all languages are
        supported during installation.

        :param language: Language ID ($LANG).
        """
        self.implementation.set_language(language)

    @property
    def LanguageSupport(self) -> List[Str]:
        """Supported languages on the system."""
        return self.implementation.language_support

    @emits_properties_changed
    def SetLanguageSupport(self, language_support: List[Str]):
        """Set the languages for which the support should be installed.

        Language support packages for specified languages will be installed.

        :param language_support: IDs of languages ($LANG) to be supported on system.
        """
        self.implementation.set_language_support(language_support)
