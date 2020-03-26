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

from dasbus.typing import *  # pylint: disable=wildcard-import

from tests.nosetests.pyanaconda_tests import check_dbus_property

from pyanaconda.core.constants import URL_TYPE_BASEURL, URL_TYPE_METALINK, URL_TYPE_MIRRORLIST
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_URL
from pyanaconda.modules.common.errors import InvalidValueError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.url.url import URLSourceModule
from pyanaconda.modules.payloads.source.url.url_interface import URLSourceInterface


class URLSourceInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.url_source_module = URLSourceModule()
        self.url_source_interface = URLSourceInterface(self.url_source_module)

    def _check_dbus_property(self, property_name, in_value):
        check_dbus_property(
            self,
            PAYLOAD_SOURCE_URL,
            self.url_source_interface,
            property_name,
            in_value
        )

    def type_test(self):
        """Test URL source has a correct type specified."""
        self.assertEqual(SourceType.URL.value, self.url_source_interface.Type)

    def set_url_base_source_properties_test(self):
        data = RepoConfigurationData()
        data.url = "http://example.com/repo"
        data.type = URL_TYPE_BASEURL

        self._check_dbus_property(
            "RepoConfiguration",
            RepoConfigurationData.to_structure(data)
        )

    def set_url_mirrorlist_properties_test(self):
        data = RepoConfigurationData()
        data.url = "http://forthehorde.com/mirrorlist?url"
        data.type = URL_TYPE_MIRRORLIST

        self._check_dbus_property(
            "RepoConfiguration",
            RepoConfigurationData.to_structure(data)
        )

    def set_url_metalink_properties_test(self):
        data = RepoConfigurationData()
        data.url = "https://alianceFTW/metalink?nopesir"
        data.type = URL_TYPE_METALINK

        self._check_dbus_property(
            "RepoConfiguration",
            RepoConfigurationData.to_structure(data)
        )

    def set_invalid_url_type_properties_test(self):
        data = RepoConfigurationData()
        data.url = "http://test"
        data.type = "DOES-NOT-EXISTS"

        with self.assertRaises(InvalidValueError):
            self._check_dbus_property(
                "RepoConfiguration",
                RepoConfigurationData.to_structure(data)
            )

    def set_raw_url_with_properties_test(self):
        data = {
            "url": get_variant(Str, "http://NaNaNaNaNaNa/Batmaaan"),
            "type": get_variant(Str, URL_TYPE_METALINK)
        }

        self._check_dbus_property(
            "RepoConfiguration",
            data
        )

    def set_empty_repo_configuration_properties_test(self):
        self._check_dbus_property(
            "RepoConfiguration",
            RepoConfigurationData.to_structure(RepoConfigurationData())
        )

    def default_repo_configuration_properties_test(self):
        self.assertEqual(self.url_source_interface.RepoConfiguration,
                         RepoConfigurationData.to_structure(RepoConfigurationData()))

    def set_true_install_properties_test(self):
        self._check_dbus_property(
            "InstallRepoEnabled",
            True
        )

    def set_false_install_properties_test(self):
        self._check_dbus_property(
            "InstallRepoEnabled",
            False
        )

    def default_install_properties_test(self):
        self.assertEqual(self.url_source_interface.InstallRepoEnabled, False)


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
