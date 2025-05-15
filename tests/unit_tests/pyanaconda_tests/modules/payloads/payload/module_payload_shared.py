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
from unittest.mock import Mock, patch

import pytest

from pyanaconda.modules.common.containers import PayloadSourceContainer
from pyanaconda.modules.payloads.constants import SourceState
from pyanaconda.modules.payloads.source.factory import SourceFactory
from tests.unit_tests.pyanaconda_tests import check_kickstart_interface


class PayloadKickstartSharedTest(object):

    def __init__(self, payload_service, payload_service_intf):
        """Setup shared payload testing object for testing kickstart.

        :param payload_service: main payload service module
        :param payload_service_intf: main payload service interface
        """
        self.payload_service = payload_service
        self.payload_service_interface = payload_service_intf

    def check_kickstart(self, ks_in, ks_out=None, ks_valid=True, ks_tmp=None,
                        expected_publish_calls=1):
        """Test kickstart processing.

        :param ks_in: input kickstart for testing
        :param ks_out: expected output kickstart
        :param ks_valid: True if the input kickstart is valid, otherwise False
        :param ks_tmp: string with the temporary output kickstart
        :param expected_publish_calls: how many times times the publisher should be called
        :type expected_publish_calls: int
        """
        with patch('pyanaconda.core.dbus.DBus.publish_object') as publisher:
            result = check_kickstart_interface(self.payload_service_interface,
                                               ks_in, ks_out, ks_valid, ks_tmp)

            if ks_valid and expected_publish_calls != 0:
                publisher.assert_called()
                assert publisher.call_count == expected_publish_calls
            else:
                publisher.assert_not_called()

            return result

    def get_payload(self):
        """Get payload created."""
        return self.payload_service.active_payload


class PayloadSharedTest(object):

    def __init__(self, payload, payload_intf):
        """Setup shared payload test object for common payload testing.

        :param payload: payload module
        :type payload: instance of PayloadBase class
        :param payload_intf: payload module interface
        :type payload_intf: instance of PayloadBaseInterface class
        """
        self.payload = payload
        self.payload_interface = payload_intf

    def check_type(self, payload_type):
        """Check if payload type property is correct.

        :param payload_type: expected payload type
        :type payload_type: value of the payload.base.constants.PayloadType enum
        """
        t = self.payload_interface.Type
        assert t == payload_type.value

    @staticmethod
    def prepare_source(source_type, state=SourceState.READY):
        """Prepare mock objects which will present given source.

        :param SourceType source: Enum describing the source type
        :param SourceState state: mock state of the created source
        """
        source = SourceFactory.create_source(source_type)
        source.get_state = Mock(return_value=state)

        return source

    def check_empty_sources(self):
        """Default check for payload with no sources set."""
        assert self.payload_interface.Sources == []

    def set_and_check_sources(self, test_sources, exception=None):
        """Default check to set sources.

        :param test_sources: list of sources for emptiness failed check
        :type test_sources: list of source instances
        :param exception: exception class which will be raised for the given sources
        :return: caught exception if exception raised
        """
        ret = self.set_sources(test_sources, exception)

        if exception:
            self.check_sources([])
        else:
            self.check_sources(test_sources)

        return ret

    def set_sources(self, test_sources, exception=None):
        """Set sources to payload.

        :param test_sources: list of sources for emptiness failed check
        :type test_sources: list of source instances
        :param exception: exception class which will be raised for the given sources
        :return: caught exception if exception raised
        """
        paths = PayloadSourceContainer.to_object_path_list(test_sources)

        if exception:
            with pytest.raises(exception) as cm:
                self.payload_interface.SetSources(paths)
            return cm

        self.payload_interface.SetSources(paths)
        return None

    def check_sources(self, expected_sources=None):
        """Check what sources are set in payload.

        :param expected_sources: list of expected sources after trying to set;
                                 including when exception raised
        :type expected_sources: list of source instances
        """
        expected_paths = PayloadSourceContainer.to_object_path_list(expected_sources)

        assert self.payload_interface.Sources == expected_paths
