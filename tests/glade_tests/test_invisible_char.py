#
# Copyright (C) 2015  Red Hat, Inc.
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

from unittest import TestCase

from gladecheck import check_glade_files


class CheckInvisibleChar(TestCase):
    def test_invisible_char(self):
        """Check that the invisible_char in glade files is actually a char."""
        check_glade_files(self, self._check_invisible_char)

    def _check_invisible_char(self, glade_tree):
        """Check that the invisible_char in glade files is actually a char.

        The invisible char is often non-ASCII and sometimes that gets clobbered.
        """

        # Only look for entries with an invisible_char property
        for entry in glade_tree.xpath("//object[@class='GtkEntry' and ./property[@name='invisible_char']]"):
            # Check the contents of the invisible_char property
            invis = entry.xpath("./property[@name='invisible_char']")[0]
            self.assertEqual(len(invis.text), 1,
                    msg="invisible_char at %s:%s not a character" % (invis.base, invis.sourceline))

            # If the char is '?' that's probably also bad
            self.assertNotEqual(invis.text, "?",
                    msg="invisible_char at %s:%s is not what you want" % (invis.base, invis.sourceline))

            # Check that invisible_char even does anything: visibility should be False
            self.assertTrue(entry.xpath("./property[@name='visibility' and ./text() = 'False']"),
                    msg="Pointless invisible_char found at %s:%s" % (invis.base, invis.sourceline))
