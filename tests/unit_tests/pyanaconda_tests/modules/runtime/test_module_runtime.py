#
# Copyright (C) 2023  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from textwrap import dedent

from pyanaconda.modules.runtime.runtime import RuntimeService
from pyanaconda.modules.runtime.runtime_interface import RuntimeInterface
from tests.unit_tests.pyanaconda_tests import check_kickstart_interface


class RuntimeInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the users module."""

    def setUp(self):
        """Set up the user module."""
        # Set up the users module.
        self.module = RuntimeService()
        self.interface = RuntimeInterface(self.module)

    def test_kickstart_properties(self):
        """Test kickstart properties."""
        commands = ["driverdisk",
                    "mediacheck",
                    "sshpw",
                    "updates",
                    "logging",
                    "rescue",
                    "eula",
                    "graphical",
                    "text",
                    "cmdline",
                    "rdp",
                    "vnc"]
        assert self.interface.KickstartCommands == commands
        sections = ['pre-install',
                    'post',
                    'onerror',
                    'traceback']
        assert self.interface.KickstartSections == sections
        assert self.interface.KickstartAddons == []

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self.interface, ks_in, ks_out)

    def test_no_kickstart(self):
        """Test with no kickstart and empty string."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_mediacheck(self):
        """Test preserving the mediacheck kickstart command."""
        ks_in = "mediacheck\n"
        ks_out = "mediacheck\n"
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_updates(self):
        """Test setting the updates image via kickstart."""
        ks_in = "updates http://example.com/updates/anaconda.img\n"
        ks_out = "updates http://example.com/updates/anaconda.img\n"
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_sshpw(self):
        """Test saving the ssh passwords set via kickstart."""
        ks_in = dedent("""
            sshpw --username root --plaintext anaconda
            sshpw --username vslavik --lock --iscrypted $y$j9T$bLceUf7O5RmwKa1Vt3Hbg.$evO.pNo0Z8kxG.u3uDxraPaffuthT7sS9QSpPFWEnf6
        """)
        ks_out = dedent("""
            sshpw --username=root --plaintext anaconda
            sshpw --username=vslavik --lock --iscrypted $y$j9T$bLceUf7O5RmwKa1Vt3Hbg.$evO.pNo0Z8kxG.u3uDxraPaffuthT7sS9QSpPFWEnf6
        """)
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_driverdisk(self):
        """Test saving the driver disk via kickstart."""
        ks_in = "driverdisk --source=nfs:host:/path/to/img\n"
        ks_out = "driverdisk --source=nfs:host:/path/to/img\n"
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_logging(self):
        """Test controls the error logging via kickstart."""
        ks_in = "logging --host=localhost --port=514\n"
        ks_out = "# Installation logging level\nlogging --host=localhost --port=514\n"
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_rescue(self):
        """Test rescue mode via kickstart."""
        ks_in = "rescue --nomount\n"
        ks_out = "# Start rescue mode\nrescue --nomount\n"
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_eula(self):
        """Test for eula accepting via kickstart."""
        ks_in = "eula --agreed\n"
        ks_out = "# License agreement\neula --agreed\n"
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_graphical(self):
        """Test graphical mode via kickstart."""
        ks_in = "graphical\n"
        ks_out = "# Use graphical install\ngraphical\n"
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_text(self):
        """Test text mode via kickstart."""
        ks_in = "text\n"
        ks_out = "# Use text mode install\ntext\n"
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_cmdline(self):
        """Test graphical mode via kickstart."""
        ks_in = "cmdline\n"
        ks_out = "cmdline\n"
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_vnc(self):
        """Test vnc via kickstart."""
        ks_in = "vnc --host=192.168.1.100 --port=5901 --password=testpassword\n"
        ks_out = "vnc --host=192.168.1.100 --port=5901 --password=testpassword\n"
        self._test_kickstart(ks_in, ks_out)
