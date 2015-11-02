#
# Copyright (C) 2015  Red Hat, Inc.
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
# Red Hat Author(s): Alexander Todorov <atodorov@redhat.com>
#

from pyanaconda.ui.gui.spokes.lib.lang_locale_handler import LangLocaleHandler
import unittest
import mock
import os

@unittest.skipUnless(os.environ.get("DISPLAY"), "DISPLAY is not defined")
class LLH(unittest.TestCase):
    def setUp(self):
        self.llh = LangLocaleHandler()
        self.llh._languageStoreFilter = mock.Mock()
        self.llh._langSelectedRenderer = mock.Mock()
        self.llh._langSelectedColumn = mock.Mock()
        self.llh._add_language = mock.Mock()

        self.orig_anaconda_widgets_data = os.environ.get("ANACONDA_WIDGETS_DATA", "")
        if not "ANACONDA_WIDGETS_DATA" in os.environ:
            widgets_data = os.path.dirname(os.path.abspath(__file__))
            widgets_data = os.path.dirname(os.path.dirname(widgets_data))
            widgets_data = os.path.join(widgets_data, "widgets", "data")
            # pylint: disable=environment-modify
            os.environ["ANACONDA_WIDGETS_DATA"] = widgets_data

    def tearDown(self):
        # pylint: disable=environment-modify
        os.environ["ANACONDA_WIDGETS_DATA"] = self.orig_anaconda_widgets_data

    def anaconda_widgets_data_test(self):
        """Test if ANACONDA_WIDGETS_DATA is used if specified."""
        self.llh.initialize()
        self.assertEqual(self.llh._right_arrow.get_property('file').find("/usr/share/anaconda"), -1)
        self.assertEqual(self.llh._left_arrow.get_property('file').find("/usr/share/anaconda"), -1)
