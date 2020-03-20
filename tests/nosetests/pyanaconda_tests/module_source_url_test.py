#
# Copyright (C) 2020  Red Hat, Inc.
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
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import unittest

from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.url.url import URLSourceModule
from pyanaconda.modules.payloads.source.url.url_interface import URLSourceInterface


class URLSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.url_source_module = URLSourceModule()
        self.url_source_interface = URLSourceInterface(self.url_source_module)

    def type_test(self):
        """Test URL source has a correct type specified."""
        self.assertEqual(SourceType.URL.value, self.url_source_interface.Type)


class URLSourceTestCase(unittest.TestCase):
    """Test the URL source module."""

    def setUp(self):
        self.module = URLSourceModule()

    def ready_state_test(self):
        """Check ready state of URL source.

        It will be always True there is no state.
        """
        self.assertTrue(self.module.is_ready())

    def set_up_with_tasks_test(self):
        """Get set up tasks for url source.

        No task is required. Will be an empty list.
        """
        self.assertEqual(self.module.set_up_with_tasks(), [])

    def tear_down_with_tasks_test(self):
        """Get tear down tasks for url source.

        No task is required. Will be an empty list.
        """
        self.assertEqual(self.module.tear_down_with_tasks(), [])
