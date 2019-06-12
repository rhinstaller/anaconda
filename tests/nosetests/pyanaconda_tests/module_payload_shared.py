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
from mock import Mock

from tests.nosetests.pyanaconda_tests import check_kickstart_interface
from pyanaconda.modules.payload.payload_interface import PayloadInterface
from pyanaconda.modules.payload.payload import PayloadModule


class PayloadHandlerMixin(object):

    def setup_payload(self):
        self.payload_module = PayloadModule()
        self.payload_interface = PayloadInterface(self.payload_module)

        # avoid publishing
        self.publish_mock = Mock()
        self.payload_module._publish_handler = self.publish_mock

    def check_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.payload_interface, ks_in, ks_out)
        self.publish_mock.assert_called_once()

    def get_payload_handler(self):
        return self.payload_module._payload_handler
