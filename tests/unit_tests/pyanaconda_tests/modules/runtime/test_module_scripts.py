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
#
import unittest

from pyanaconda.modules.runtime.scripts import ScriptsModule
from pyanaconda.modules.runtime.scripts.scripts_interface import ScriptsInterface

class ScriptsKickstartSharedTest:
    """Shared test utilities for kickstart scripts testing."""

    def __init__(self, scripts_service, scripts_service_intf):
        self.scripts_service = scripts_service
        self.scripts_service_interface = scripts_service_intf

    def check_kickstart(self, ks_in, ks_out=None, ks_valid=True, expected_publish_calls=1):
        """Test kickstart processing."""
        # Directly compare kickstart script input and expected output
        assert ks_in.strip() == ks_out.strip(), f"Expected: {ks_out.strip()}, Got: {ks_in.strip()}"

class ScriptsKickstartTestCase(unittest.TestCase):
    """Test the kickstart commands for scripts."""

    def setUp(self):
        self.module = ScriptsModule()
        self.interface = ScriptsInterface(self.module)
        self.shared_ks_tests = ScriptsKickstartSharedTest(
            scripts_service=self.module,
            scripts_service_intf=self.interface
        )

    def _test_kickstart(self, ks_in, ks_out, *args, **kwargs):
        """Helper function to verify the kickstart input and output."""
        self.shared_ks_tests.check_kickstart(ks_in, ks_out, *args, **kwargs)

    def test_pre_install_kickstart(self):
        """Test the %pre section."""
        ks_in = """
        %pre --erroronfail --interpreter=/usr/bin/python --log=/tmp/pre.log
        print("Preparing system for installation")
        %end
        """
        ks_out = """
        %pre --erroronfail --interpreter=/usr/bin/python --log=/tmp/pre.log
        print("Preparing system for installation")
        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def test_post_install_kickstart(self):
        """Test the %post section."""
        ks_in = """
        %post --erroronfail --interpreter=/usr/bin/python --log=/tmp/post.log --nochroot
        echo "Installation finished"
        %end
        """
        ks_out = """
        %post --erroronfail --interpreter=/usr/bin/python --log=/tmp/post.log --nochroot
        echo "Installation finished"
        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def test_onerror_script_kickstart(self):
        """Test the %onerror section."""
        ks_in = """
        %onerror --erroronfail --interpreter=/usr/bin/python --log=/tmp/onerror.log
        echo "Handling error during installation"
        %end
        """
        ks_out = """
        %onerror --erroronfail --interpreter=/usr/bin/python --log=/tmp/onerror.log
        echo "Handling error during installation"
        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def test_traceback_script_kickstart(self):
        """Test the %traceback section."""
        ks_in = """
        %traceback --erroronfail --interpreter=/usr/bin/python --log=/tmp/traceback.log
        echo "Error occurred during installation"
        %end
        """
        ks_out = """
        %traceback --erroronfail --interpreter=/usr/bin/python --log=/tmp/traceback.log
        echo "Error occurred during installation"
        %end
        """
        self._test_kickstart(ks_in, ks_out)
