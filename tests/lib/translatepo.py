#
# translatepo.py: translate strings from data in .po files
#
# Copyright (C) 2013-2014  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: David Shea <dshea@redhat.com>

# This module is helpful for testing translated data. The input is the .po files
# in the po directory, so no gettext compilation or LC_MESSAGES directories are
# necessary.

import os
import locale
import re

try:
    import polib
except ImportError:
    print("You need to install the python-polib package to read translations")
    raise

class PODict(object):
    def __init__(self, filename):
        """Create a new dictionary of translations from a po file."""

        self._dict = {}
        self._dict[None] = {}

        pofile = polib.pofile(filename)
        self.metadata = pofile.metadata

        # Rearrange the entries in the pofile to make it easier to look up contexts.
        # _dict will be layed out _dict[msgctxt][msgid] = (translated1, translated2, ...)
        # There may be multiple translations because of plurals
        for entry in pofile.translated_entries():
            if (entry.msgctxt is not None) and (entry.msgctxt not in self._dict):
                self._dict[entry.msgctxt] = {}

            # If this is a plural entry, add entries for both the singular and
            # plural forms so that either can be used for a lookup
            if entry.msgstr_plural:
                xlist = [entry.msgstr_plural[key] for key in entry.msgstr_plural.keys()]
                self._dict[entry.msgctxt][entry.msgid] = xlist
                self._dict[entry.msgctxt][entry.msgid_plural] = xlist
            else:
                self._dict[entry.msgctxt][entry.msgid] = (entry.msgstr,)

    def get(self, key, context=None):
        return self._dict[context][key]

# Return a dictionary of PODict objects for each language in a po directory
def translate_all(podir):
    # Reset the locale to C before parsing the po file because
    # polib has erroneous uses of lower()
    saved_locale = locale.setlocale(locale.LC_ALL, None)
    locale.setlocale(locale.LC_CTYPE, 'C')

    podicts = {}

    with open(os.path.join(podir, 'LINGUAS')) as linguas:
        for line in linguas.readlines():
            if re.match(r'^#', line):
                continue

            for lang in line.strip().split(" "):
                podicts[lang] = PODict(os.path.join(podir, lang + ".po"))

    locale.setlocale(locale.LC_CTYPE, saved_locale)
    return podicts
