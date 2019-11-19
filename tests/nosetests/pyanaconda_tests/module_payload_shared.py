#
# Copyright (C) 2019  Red Hat, Inc.
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
from unittest.mock import patch, create_autospec

from tests.nosetests.pyanaconda_tests import check_kickstart_interface
from pyanaconda.modules.common.containers import PayloadSourceContainer
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.payloads_interface import PayloadsInterface
from pyanaconda.modules.payloads.payloads import PayloadsService
from pyanaconda.modules.payloads.sources.live_os.live_os import LiveOSSourceModule


class PayloadSharedTest(object):

    def __init__(self, test, payload_service, payload_service_intf):
        """Setup shared payload test object for common payload testing.

        :param test: instance of TestCase
        :param payload_service: main payload service module
        :param payload_service_intf: main payload service interface
        """
        self._test = test
        self.payload_service = PayloadsService()
        self.payload_service_interface = PayloadsInterface(self.payload_service)

    def check_kickstart(self, ks_in, ks_out, expected_publish_calls=1):
        """Test kickstart processing.

        :param test_obj: TestCase object (probably self)
        :param ks_in: input kickstart for testing
        :param ks_out: expected output kickstart
        :param expected_publish_calls: how many times times the publisher should be called
        :type expected_publish_calls: int
        """
        with patch('pyanaconda.core.dbus.DBus.publish_object') as publisher:
            check_kickstart_interface(self._test,
                                      self.payload_service_interface,
                                      ks_in, "", ks_tmp=ks_out)

            publisher.assert_called()
            self._test.assertEqual(publisher.call_count, expected_publish_calls)

    def get_payload(self):
        """Get payload created."""
        return self.payload_service.payload


class SourceSharedTest(object):

    def __init__(self, test, payload, payload_intf):
        """Setup shared payload source test object for common payload testing.

        :param test: instance of TestCase
        :param payload: payload module
        :type payload: instance of PayloadBase class
        :param payload_intf: payload module interface
        :type payload_intf: instance of PayloadBaseInterface class
        """
        self._test = test
        self.payload = payload
        self.payload_interface = payload_intf

    @staticmethod
    def prepare_source(source_type):
        """Prepare mock objects which will present given source.

        :param SourceType source: Enum describing the source type
        """
        if source_type == SourceType.LIVE_OS_IMAGE:
            source = create_autospec(LiveOSSourceModule)
            source.image_path = "/test/path"

        source.type = source_type
        source.is_ready.return_value = True

        return source

    def set_sources(self, sources):
        """Set sources list to payload object.

        This will not call DBus API.

        :param sources: list of source objects to be set
        """
        self.payload.set_sources(sources)

    def check_empty_sources(self):
        """Default check for payload with no sources set."""
        self._test.assertEqual([], self.payload_interface.Sources)
        self._test.assertFalse(self.payload_interface.HasSource())

    def check_set_sources(self, test_sources, exception=None):
        """Default check to set sources.

        :param test_sources: list of sources for emptiness failed check
        :param exception: exception class which will be raised for the given sources
        """
        paths = PayloadSourceContainer.to_object_path_list(test_sources)

        if exception:
            with self._test.assertRaises(exception):
                self.payload_interface.SetSources(paths)

            self._test.assertEqual(self.payload_interface.Sources, [])
            self._test.assertFalse(self.payload_interface.HasSource())
        else:
            self.payload_interface.SetSources(paths)

            self._test.assertEqual(self.payload_interface.Sources, paths)
            self._test.assertTrue(self.payload_interface.HasSource())
