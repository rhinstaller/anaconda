#
# Copyright (C) 2022  Red Hat, Inc.
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

from dasbus.error import DBusError

from pyanaconda.core.dbus import error_mapper
from pyanaconda.modules.common.errors.general import AnacondaError
from pyanaconda.modules.common.errors.module import UnavailableModuleError
from pyanaconda.modules.common.errors.payload import SourceSetupError


class DBusErrorTestCase(unittest.TestCase):
    """Test Anaconda DBus errors."""

    def _error_to_exception(self, error_name, exception_class):
        """Check the mapping of a DBus error to a Python exception class."""
        assert error_mapper.get_exception_type(error_name) == exception_class

    def _exception_to_error(self, exception_class, error_name):
        """Check the mapping of a Python exception class to a DBus error."""
        assert error_mapper.get_error_name(exception_class) == error_name

    def test_unknown_error_name(self):
        """Test mapping of an unknown DBus error."""
        self._error_to_exception(
            "not.known.Error",
            DBusError
        )

    def test_default_anaconda_error(self):
        """Test default mapping of Anaconda errors."""
        self._exception_to_error(
            ValueError,
            "org.fedoraproject.Anaconda.Error"
        )
        self._exception_to_error(
            OSError,
            "org.fedoraproject.Anaconda.Error"
        )
        self._exception_to_error(
            AnacondaError,
            "org.fedoraproject.Anaconda.Error"
        )
        self._error_to_exception(
            "org.fedoraproject.Anaconda.Error",
            AnacondaError
        )

    def test_defined_anaconda_errors(self):
        """Test defined mapping of Anaconda errors."""
        self._exception_to_error(
            UnavailableModuleError,
            "org.fedoraproject.Anaconda.UnavailableModuleError"
        )
        self._error_to_exception(
            "org.fedoraproject.Anaconda.UnavailableModuleError",
            UnavailableModuleError
        )
        self._exception_to_error(
            SourceSetupError,
            "org.fedoraproject.Anaconda.Modules.Payloads.SourceSetupError"
        )
        self._error_to_exception(
            "org.fedoraproject.Anaconda.Modules.Payloads.SourceSetupError",
            SourceSetupError
        )
