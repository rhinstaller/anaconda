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
        self.set_language(data.lang.lang)
        self.set_language_support(data.lang.addsupport)

    def generate_kickstart(self):
        """Return the kickstart string."""
        log.debug("Generating kickstart data...")
        data = self.get_kickstart_handler()
        data.lang.lang = self.language
        data.lang.addsupport = self.language_support

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
