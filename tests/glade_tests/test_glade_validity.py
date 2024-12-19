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

from collections import Counter
from unittest import TestCase

from gladecheck import check_glade_files


class CheckValidity(TestCase):
    def test_validity_check(self):
        """Check for common glade validity errors."""
        check_glade_files(self, self._check_validity)

    def _check_validity(self, glade_tree):
        """Check for common glade validity errors"""
        # Check for duplicate IDs
        # Build a Counter from a list of all ids and extract the ones with count > 1
        # Fun fact: glade uses <col id="<number>"> in GtkListStore data, so ids
        # aren't actually unique and getting an object with a particular ID
        # isn't as simple as document.getElementById. Only check the IDs on objects.
        for glade_id in [c for c in Counter(glade_tree.xpath(".//object/@id")).most_common() \
                if c[1] > 1]:
            raise AssertionError("%s: ID %s appears %d times" %
                    (glade_tree.getroot().base, glade_id[0], glade_id[1]))

        # Check for ID references
        # mnemonic_widget properties and action-widget elements need to refer to
        # valid object ids.
        for mnemonic_widget in glade_tree.xpath(".//property[@name='mnemonic_widget']"):
            self.assertTrue(glade_tree.xpath(".//object[@id='%s']" % mnemonic_widget.text),
                    msg="mnemonic_widget reference to invalid ID %s at line %d of %s" %
                        (mnemonic_widget.text, mnemonic_widget.sourceline, mnemonic_widget.base))

        for action_widget in glade_tree.xpath(".//action-widget"):
            self.assertTrue(glade_tree.xpath(".//object[@id='%s']" % action_widget.text),
                msg="action-widget reference to invalid ID %s at line %d of %s" %
                        (action_widget.text, action_widget.sourceline, action_widget.base))
