# Language text spoke
#
# Copyright (C) 2014  Red Hat, Inc.
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

from simpleline.render.containers import ListColumnContainer
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget

from pyanaconda import localization
from pyanaconda.core.i18n import N_, _
from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.ui.categories.localization import LocalizationCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.tui.spokes import NormalTUISpoke

# TRANSLATORS: 'b' to go back to language list
PROMPT_BACK_DESCRIPTION = N_("to return to language list")
PROMPT_BACK_KEY = 'b'


class LangSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    """
    This spoke allows a user to select their installed language. Note that this
    does not affect the display of the installer, it only will affect the system
    post-install, because it's too much of a pain to make other languages work
    in text-mode.

    Also this doesn't allow for selection of multiple languages like in the GUI.

       .. inheritance-diagram:: LangSpoke
          :parts: 3
    """
    category = LocalizationCategory

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "language-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Should the spoke run?"""
        if not is_module_available(LOCALIZATION):
            return False

        return FirstbootSpokeMixIn.should_run(environment, data)

    def __init__(self, data, storage, payload):
        NormalTUISpoke.__init__(self, data, storage, payload)
        self.title = N_("Language settings")
        self.initialize_start()
        self._container = None

        self._langs = [localization.get_english_name(lang)
                       for lang in localization.get_available_translations()]
        self._langs_and_locales = dict((localization.get_english_name(lang), lang)
                                       for lang in localization.get_available_translations())
        self._locales = dict((lang, localization.get_language_locales(lang))
                             for lang in self._langs_and_locales.values())

        self._l12_module = LOCALIZATION.get_proxy()

        self._selected = self._l12_module.Language
        self.initialize_done()

    @property
    def completed(self):
        return self._l12_module.Language

    @property
    def mandatory(self):
        return False

    @property
    def status(self):
        if self._l12_module.Language:
            return localization.get_english_name(self._selected)
        else:
            return _("Language is not set.")

    def refresh(self, args=None):
        """
        args is None if we want a list of languages; or, it is a list of all
        locales for a language.
        """
        NormalTUISpoke.refresh(self, args)

        self._container = ListColumnContainer(3)

        if args:
            self.window.add(TextWidget(_("Available locales")))
            for locale in args:
                widget = TextWidget(localization.get_english_name(locale))
                self._container.add(widget, self._set_locales_callback, locale)
        else:
            self.window.add(TextWidget(_("Available languages")))
            for lang in self._langs:
                langs_and_locales = self._langs_and_locales[lang]
                locales = self._locales[langs_and_locales]
                self._container.add(TextWidget(lang), self._show_locales_callback, locales)

        self.window.add_with_separator(self._container)

    def _set_locales_callback(self, data):
        locale = data
        self._selected = locale
        self.apply()
        self.close()

    def _show_locales_callback(self, data):
        locales = data
        ScreenHandler.replace_screen(self, locales)

    def input(self, args, key):
        """ Handle user input. """
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:

            if key.lower() == PROMPT_BACK_KEY:
                ScreenHandler.replace_screen(self)
                return InputState.PROCESSED
            else:
                return super().input(args, key)

    def prompt(self, args=None):
        """ Customize default prompt. """
        prompt = NormalTUISpoke.prompt(self, args)
        prompt.set_message(_("Please select language support to install"))
        prompt.add_option(PROMPT_BACK_KEY, _(PROMPT_BACK_DESCRIPTION))
        return prompt

    def apply(self):
        """ Store the selected lang support locales """
        self._l12_module.SetLanguage(self._selected)
