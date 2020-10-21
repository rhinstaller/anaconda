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
import unittest
from unittest.mock import patch

from pyanaconda.core.constants import PAYLOAD_TYPE_LIVE_OS, PAYLOAD_TYPE_DNF, SOURCE_TYPE_CDROM
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.ui.lib.payload import create_payload, get_payload, create_source, set_source, \
    get_source, set_up_sources, tear_down_sources
from tests.nosetests.pyanaconda_tests import patch_dbus_get_proxy_with_cache


class PayloadUITestCase(unittest.TestCase):
    """Test the UI functions and classes of the payload object."""

    @patch_dbus_get_proxy_with_cache
    def create_payload_test(self, proxy_getter):
        """Test the create_payload function."""
        payloads_proxy = PAYLOADS.get_proxy()
        payloads_proxy.CreatePayload.return_value = "/my/path"

        payload_proxy = PAYLOADS.get_proxy("/my/path")
        payload_proxy.Type = PAYLOAD_TYPE_LIVE_OS

        self.assertEqual(create_payload(PAYLOAD_TYPE_LIVE_OS), payload_proxy)
        payloads_proxy.CreatePayload.assert_called_once_with(PAYLOAD_TYPE_LIVE_OS)
        payloads_proxy.ActivatePayload.assert_called_once_with("/my/path")

    @patch_dbus_get_proxy_with_cache
    def get_payload_test(self, proxy_getter):
        """Test the get_payload function."""
        payloads_proxy = PAYLOADS.get_proxy()
        payloads_proxy.ActivePayload = "/my/path1"
        payloads_proxy.CreatePayload.return_value = "/my/path2"

        payload_proxy_1 = PAYLOADS.get_proxy("/my/path1")
        payload_proxy_1.Type = PAYLOAD_TYPE_LIVE_OS

        payload_proxy_2 = PAYLOADS.get_proxy("/my/path2")
        payload_proxy_2.Type = PAYLOAD_TYPE_DNF

        # Get the active payload.
        self.assertEqual(get_payload(PAYLOAD_TYPE_LIVE_OS), payload_proxy_1)
        self.assertEqual(get_payload(PAYLOAD_TYPE_LIVE_OS), payload_proxy_1)
        payloads_proxy.ActivatePayload.assert_not_called()

        # Or create a new one.
        self.assertEqual(get_payload(PAYLOAD_TYPE_DNF), payload_proxy_2)
        payloads_proxy.ActivatePayload.assert_called_once_with("/my/path2")

    @patch_dbus_get_proxy_with_cache
    def create_source_test(self, proxy_getter):
        """Test the create_source function."""
        payloads_proxy = PAYLOADS.get_proxy()
        payloads_proxy.CreateSource.return_value = "/my/source"

        source_proxy = PAYLOADS.get_proxy("/my/source")
        source_proxy.Type = SOURCE_TYPE_CDROM

        self.assertEqual(create_source(SOURCE_TYPE_CDROM), source_proxy)
        payloads_proxy.CreateSource.assert_called_once_with(SOURCE_TYPE_CDROM)

    @patch("pyanaconda.ui.lib.payload.get_object_path")
    @patch_dbus_get_proxy_with_cache
    def set_source_test(self, proxy_getter, get_object_path):
        """Test the set_source function."""
        payload_proxy = PAYLOADS.get_proxy("/my/payload")

        source_proxy = PAYLOADS.get_proxy("/my/source")
        get_object_path.return_value = "/my/source"

        set_source(payload_proxy, source_proxy)
        payload_proxy.SetSources.assert_called_once_with(["/my/source"])

    @patch("pyanaconda.ui.lib.payload.get_object_path")
    @patch_dbus_get_proxy_with_cache
    def get_source_test(self, proxy_getter, get_object_path):
        """Test the get_source function."""
        payload_proxy = PAYLOADS.get_proxy("/my/payload")
        source_proxy_1 = PAYLOADS.get_proxy("/my/source/1")

        payload_proxy.Sources = ["/my/source/1", "/my/source/2", "/my/source/3"]
        self.assertEqual(get_source(payload_proxy), source_proxy_1)

        payload_proxy.Sources = ["/my/source/1"]
        self.assertEqual(get_source(payload_proxy), source_proxy_1)

        payload_proxy.Sources = []
        self.assertRaises(ValueError, get_source, payload_proxy)

        payloads_proxy = PAYLOADS.get_proxy()
        payloads_proxy.CreateSource.return_value = "/my/source/4"

        source_proxy_4 = PAYLOADS.get_proxy("/my/source/4")
        get_object_path.return_value = "/my/source/4"

        payload_proxy.Sources = []
        self.assertEqual(get_source(payload_proxy, SOURCE_TYPE_CDROM), source_proxy_4)
        payloads_proxy.CreateSource.assert_called_once_with(SOURCE_TYPE_CDROM)
        payload_proxy.SetSources.assert_called_once_with(["/my/source/4"])

    @patch_dbus_get_proxy_with_cache
    def set_up_sources_test(self, proxy_getter):
        payload_proxy = PAYLOADS.get_proxy("/my/payload")
        payload_proxy.SetUpSourcesWithTask.return_value = "/my/task"

        task_proxy = PAYLOADS.get_proxy("/my/task")
        task_proxy.IsRunning = False

        set_up_sources(payload_proxy)
        payload_proxy.SetUpSourcesWithTask.assert_called_once_with()
        task_proxy.Start.assert_called_once_with()
        task_proxy.Finish.assert_called_once_with()

    @patch_dbus_get_proxy_with_cache
    def tear_down_sources_test(self, proxy_getter):
        payload_proxy = PAYLOADS.get_proxy("/my/payload")
        payload_proxy.TearDownSourcesWithTask.return_value = "/my/task"

        task_proxy = PAYLOADS.get_proxy("/my/task")
        task_proxy.IsRunning = False

        tear_down_sources(payload_proxy)
        payload_proxy.TearDownSourcesWithTask.assert_called_once_with()
        task_proxy.Start.assert_called_once_with()
        task_proxy.Finish.assert_called_once_with()
