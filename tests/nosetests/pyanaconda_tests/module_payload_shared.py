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
from mock import patch

from tests.nosetests.pyanaconda_tests import check_kickstart_interface
from pyanaconda.modules.payload.payload_interface import PayloadInterface
from pyanaconda.modules.payload.payload import PayloadService


class PayloadSharedTest(object):

    def __init__(self, test, payload_service, payload_service_intf):
        """Setup shared payload test object for common payload testing.

        :param test: instance of TestCase
        :param payload_service: main payload service module
        :param payload_service_intf: main payload service interface
        """
        self._test = test
        self.payload_service = PayloadService()
        self.payload_service_interface = PayloadInterface(self.payload_service)

    def check_kickstart(self, ks_in, ks_out, expected_publish_calls=1):
        """Test kickstart processing.

        :param test_obj: TestCase object (probably self)
        :param ks_in: input kickstart for testing
        :param ks_out: expected output kickstart
        :param expected_publish_calls: how many times times the publisher should be called
        :type expected_publish_calls: int
        """
        with patch('pyanaconda.dbus.DBus.publish_object') as publisher:
            check_kickstart_interface(self._test,
                                      self.payload_service_interface,
                                      ks_in, "", ks_tmp=ks_out)

            publisher.assert_called()
            self._test.assertEqual(publisher.call_count, expected_publish_calls)

    def get_payload_handler(self):
        """Get payload handler created."""
        return self.payload_service.payload_handler
