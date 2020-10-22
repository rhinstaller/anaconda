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
import warnings

from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartService, KickstartModuleInterface
from pykickstart.errors import KickstartParseError, KickstartParseWarning, \
    KickstartDeprecationWarning


class BaseModuleTestCase(unittest.TestCase):
    """Test base classes for DBus modules."""

    def setUp(self):
        self.maxDiff = None

    def read_kickstart_error_test(self):
        """Test ReadKickstart with a custom error."""

        class Service(KickstartService):
            def process_kickstart(self, data):
                raise KickstartParseError("Error!")

        module = Service()
        interface = KickstartModuleInterface(module)

        error = {
            'file-name': get_variant(Str, ""),
            'line-number': get_variant(UInt32, 0),
            'message': get_variant(Str, 'Error!'),
            'module-name': get_variant(Str, ""),
        }

        report = {
            'error-messages': get_variant(List[Structure], [error]),
            'warning-messages': get_variant(List[Structure], [])
        }

        self.assertEqual(interface.ReadKickstart(""), report)

    def read_kickstart_error_line_number_test(self):
        """Test ReadKickstart with a custom error on a specified line."""

        class Service(KickstartService):
            def process_kickstart(self, data):
                raise KickstartParseError("Error!", lineno=10)

        module = Service()
        interface = KickstartModuleInterface(module)

        error = {
            'file-name': get_variant(Str, ""),
            'line-number': get_variant(UInt32, 10),
            'message': get_variant(Str, 'Error!'),
            'module-name': get_variant(Str, ""),
        }

        report = {
            'error-messages': get_variant(List[Structure], [error]),
            'warning-messages': get_variant(List[Structure], [])
        }

        self.assertEqual(interface.ReadKickstart(""), report)

    def read_kickstart_warning_test(self):
        """Test ReadKickstart with a custom warning."""

        class Service(KickstartService):
            def process_kickstart(self, data):
                warnings.warn("First warning!", KickstartParseWarning)
                warnings.warn("Other warning!", DeprecationWarning)
                warnings.warn("Second warning!", KickstartDeprecationWarning)

        module = Service()
        interface = KickstartModuleInterface(module)

        first_warning = {
            'file-name': get_variant(Str, ""),
            'line-number': get_variant(UInt32, 0),
            'message': get_variant(Str, 'First warning!'),
            'module-name': get_variant(Str, ""),
        }

        second_warning = {
            'file-name': get_variant(Str, ""),
            'line-number': get_variant(UInt32, 0),
            'message': get_variant(Str, 'Second warning!'),
            'module-name': get_variant(Str, ""),
        }

        report = {
            'error-messages': get_variant(List[Structure], []),
            'warning-messages': get_variant(List[Structure], [first_warning, second_warning])
        }

        self.assertEqual(interface.ReadKickstart(""), report)
