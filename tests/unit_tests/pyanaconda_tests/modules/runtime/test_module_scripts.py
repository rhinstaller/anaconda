#
# Copyright (C) 2024  Red Hat, Inc.
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
import unittest

from pyanaconda.modules.common.constants.objects import SCRIPTS
from pyanaconda.modules.runtime.scripts import ScriptsModule
from pyanaconda.modules.runtime.scripts.scripts import RunScriptTask
from pyanaconda.modules.runtime.scripts.scripts_interface import ScriptsInterface
from tests.unit_tests.pyanaconda_tests import check_kickstart_interface, patch_dbus_publish_object

class ScriptsInterfaceTestCase(unittest.TestCase):
    """ Test Scripts DBus interface for the runtime module."""

    def setUp(self):
        self.module = ScriptsModule()
        self.interface = ScriptsInterface(self.module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            SCRIPTS,
            self.interface,
            *args, **kwargs
        )

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self.interface, ks_in, ks_out)

    def test_kickstart_set_pre_script(self):
        """Test setting pre script via kickstart."""
        ks_in = """
%pre
echo PRE
%end
"""
        ks_out = """
%pre
echo PRE
%end
"""
        self._test_kickstart(ks_in, ks_out)
        assert self.interface.pre.script == ks_out

    @patch_dbus_publish_object
    def test_run_pre_script_with_task(self, publisher):
        """Test RunPreScriptsWithTask method."""
        task_path = self.interface.RunPreScriptsWithTask()
        check_task_creation(taks_path, publisher, RunScriptTask)
