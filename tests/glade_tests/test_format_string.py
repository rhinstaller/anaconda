#
# Copyright (C) 2014  Red Hat, Inc.
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

from gladecheck import check_glade_files
from unittest import TestCase


class CheckFormatString(TestCase):
    def test_format_strings(self):
        """Reject translatable format string in glade."""
        check_glade_files(self, self._check_format_strings)

    def _check_format_strings(self, glade_tree):
        """Reject translatable format string in glade.

           Since format substitution is language-dependent, gettext is unable
           to check the validity of format string translations for strings
           within glade. Instead, the format string constant, the translation
           substitution, and the format substitution should all happen outside
           of glade. Untranslated placeholder strings are allowable within
           glade.
        """
        # Check any property with translatable="yes"
        for translatable in glade_tree.xpath(".//*[@translatable='yes']"):
            # Look for % followed by an open parenthesis (indicating %(name)
            # style substitution), one of the python format conversion flags
            # (#0- +hlL), or one of the python conversion types
            # (diouxXeEfFgGcrs)
            self.assertNotRegex(translatable.text,
                    r'%[-(#0 +hlLdiouxXeEfFgGcrs]',
                    msg="Translatable format string found at %s:%d" %
                        (translatable.base, translatable.sourceline))
