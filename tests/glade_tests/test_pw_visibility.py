#
# Copyright (C) 2013  Red Hat, Inc.
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

"""
Simple python script checking that password GtkEntries in the given .glade files
have the visibility set to False.

"""

from unittest import TestCase

from gladecheck import check_glade_files

PW_ID_INDICATORS = ("pw", "password", "passwd", "passphrase")


class CheckPwVisibility(TestCase):
    def test_pw_visibility(self):
        """Check that password GtkEntries have the visibility set to False"""
        check_glade_files(self, self._check_pw_visibility)

    def _check_pw_visibility(self, glade_tree):
        """Check that password GtkEntries have the visibility set to False"""

        for entry in glade_tree.xpath("//object[@class='GtkEntry']"):
            entry_id = entry.attrib.get("id", "UNKNOWN ID")
            visibility_props = entry.xpath("./property[@name='visibility']")

            # no entry should have visibility specified multiple times
            self.assertLessEqual(len(visibility_props), 1,
                    msg="Visibility specified multiple times for the entry %s (%s)" % (entry_id, entry.base))

            # password entry should have visibility set to False
            if any(ind in entry_id.lower() for ind in PW_ID_INDICATORS):
                self.assertTrue(visibility_props,
                        msg="Visibility not specified for the password entry %s (%s)" % (entry_id, entry.base))
                self.assertEqual(visibility_props[0].text.strip(), "False",
                        msg="Visibility not set properly for the password entry %s (%s)" % (entry_id, entry.base))
            # only password entries should have the visibility set to False
            elif visibility_props and visibility_props[0].text.strip() == "False":
                raise AssertionError("Non-password entry %s (%s) has the visibility set to False (bad id?)" %
                        (entry_id, entry.base))
