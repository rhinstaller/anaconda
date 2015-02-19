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
# Red Hat Author(s): Samantha N. Bueno <sbueno@redhat.com>
#

from pyanaconda.ui.categories.localization import LocalizationCategory
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda import localization
from pyanaconda.i18n import N_, _, C_

class LangSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    """
    This spoke allows a user to select their installed language. Note that this
    does not affect the display of the installer, it only will affect the system
    post-install, because it's too much of a pain to make other languages work
    in text-mode.

    Also this doesn't allow for selection of multiple languages like in the GUI.
    """
    title = N_("Language settings")
    category = LocalizationCategory

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)

        self._langs = [localization.get_english_name(lang)
                        for lang in localization.get_available_translations()]
        self._langs_and_locales = dict((localization.get_english_name(lang), lang)
                                for lang in localization.get_available_translations())
        self._locales = dict((lang, localization.get_language_locales(lang))
                                for lang in self._langs_and_locales.values())
        self._selected = self.data.lang.lang

    @property
    def completed(self):
        return self.data.lang.lang

    @property
    def mandatory(self):
        return False

    @property
    def status(self):
        if self.data.lang.lang:
            return localization.get_english_name(self._selected)
        else:
            return _("Language is not set.")

    def refresh(self, args=None):
        """
        args is None if we want a list of languages; or, it is a list of all
        locales for a language.
        """
        NormalTUISpoke.refresh(self, args)

        if args:
            self._window += [TextWidget(_("Available locales"))]
            displayed = [TextWidget(localization.get_english_name(z)) for z in args]
        else:
            self._window += [TextWidget(_("Available languages"))]
            displayed = [TextWidget(z) for z in self._langs]

        def _prep(i, w):
            """ make everything look nice """
            number = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        # split zones to three columns
        middle = len(displayed) / 3
        left = [_prep(i, w) for i, w in enumerate(displayed) if i <= middle]
        center = [_prep(i, w) for i, w in enumerate(displayed) if i > middle and i <= 2*middle]
        right = [_prep(i, w) for i, w in enumerate(displayed) if i > 2*middle]

        c = ColumnWidget([(24, left), (24, center), (24, right)], 3)
        self._window.append(c)

        return True

    def input(self, args, key):
        """ Handle user input. """
        try:
            keyid = int(key) - 1
            if args:
                self._selected = args[keyid]
                self.apply()
                self.close()
            else:
                self.app.switch_screen(self, self._locales[self._langs_and_locales[self._langs[keyid]]])
            return True
        except (ValueError, IndexError):
            pass

        # TRANSLATORS: 'b' to go back
        if key.lower() == C_("TUI|Spoke Navigation|Language Support", "b"):
            self.app.switch_screen(self, None)
            return True
        else:
            return key

    def prompt(self, args=None):
        """ Override default prompt with a custom prompt. """
        return _("Please select language support to install.\n[b to language list, c to continue, q to quit]: ")

    def apply(self):
        """ Store the selected langsupport locales """
        self.data.lang.lang = self._selected
