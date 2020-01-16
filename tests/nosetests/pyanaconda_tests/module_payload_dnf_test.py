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
import unittest

from tests.nosetests.pyanaconda_tests.module_payload_shared import PayloadSharedTest

from pyanaconda.modules.payloads.constants import PayloadType
from pyanaconda.modules.payloads.payload.dnf.dnf import DNFModule
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface


class DNFInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        self.dnf_module = DNFModule()
        self.dnf_interface = DNFInterface(self.dnf_module)

        self.shared_tests = PayloadSharedTest(self,
                                              payload=self.dnf_module,
                                              payload_intf=self.dnf_interface)

    def type_test(self):
        self.shared_tests.check_type(PayloadType.DNF)
