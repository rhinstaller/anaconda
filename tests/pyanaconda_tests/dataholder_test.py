# -*- coding: utf-8 -*-
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
# Red Hat Author(s): Brian C. Lane <bcl@redhat.com>

from pyanaconda.iutil import DataHolder
import unittest

class DataHolderTests(unittest.TestCase):
    def dataholder_test(self):
        """Test the DataHolder class"""

        source = {"name": "Minion", "color": "Yellow", "size": 3}
        data = DataHolder(**source)

        # test that init keywords show up as attrs
        self.assertTrue(all([getattr(data, s) == source[s] for s in source]))

        # test that init keywords show as keys
        self.assertTrue(all([data[s] == source[s] for s in source]))

        # test that adding an attr shows as a key
        data.master = "Gru"
        self.assertEquals(data["master"], "Gru")

        # test that adding a key shows as an attr
        data["sibling"] = "More Minions"
        self.assertEquals(data.sibling, "More Minions")

        # test that a copy results in the same key/values
        data_copy = data.copy()
        self.assertEquals(data, data_copy)
