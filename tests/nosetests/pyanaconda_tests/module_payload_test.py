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

from mock import Mock

from pyanaconda.modules.common.constants.objects import DNF_PACKAGES
from pyanaconda.modules.payload.payload_interface import PayloadInterface
from pyanaconda.modules.payload.payload import PayloadModule
from pyanaconda.modules.payload.dnf.packages.packages_interface import PackagesHandlerInterface
from pyanaconda.modules.payload.dnf.packages.packages import PackagesHandlerModule
from tests.nosetests.pyanaconda_tests import check_kickstart_interface


class PayloadInterfaceTestCase(unittest.TestCase):

    def setUp(self):
        """Set up the payload module."""
        # Set up the security module.
        self.payload_module = PayloadModule()
        self.payload_interface = PayloadInterface(self.payload_module)

        self.package_module = PackagesHandlerModule()
        self.package_interface = PackagesHandlerInterface(self.package_module)

        self.callback = Mock()
        self.package_interface.PropertiesChanged.connect(self.callback)

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.payload_interface, ks_in, ks_out)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.payload_interface.KickstartCommands, [])
        self.assertEqual(self.payload_interface.KickstartSections, ["packages"])
        self.assertEqual(self.payload_interface.KickstartAddons, [])

    def packages_section_empty_kickstart_test(self):
        """Test the empty packages section."""
        ks_in = """
        %packages
        %end
        """
        ks_out = """
        %packages

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_kickstart_test(self):
        """Test the packages section."""
        ks_in = """
        %packages
        package
        @group
        @module:10
        @module2:1.5/server
        @^environment
        %end
        """
        ks_out = """
        %packages
        @^environment
        @group
        @module2:1.5/server
        @module:10
        package

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_complex_kickstart_test(self):
        """Test the packages section with duplicates."""
        ks_in = """
        %packages
        @^environment1
        package1
        @group1
        package2

        # Only this environment will stay (last specified wins)
        @^environment2
        @group2

        # duplicates
        package2
        @group2

        # modules
        @module:4
        @module:3.5/server

        %end
        """
        # The last specified environment wins, you can't specify two environments
        # Same package or group specified twice will be deduplicated
        ks_out = """
        %packages
        @^environment2
        @group1
        @group2
        @module:3.5/server
        @module:4
        package1
        package2

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_with_attribute_kickstart_test(self):
        """Test the packages section with attribute."""
        ks_in = """
        %packages --nocore
        %end
        """
        ks_out = """
        %packages --nocore

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_multiple_attributes_kickstart_test(self):
        """Test the packages section with multiple attributes."""
        ks_in = """
        %packages --nocore --multilib --instLangs en_US.UTF-8

        %end
        """
        ks_out = """
        %packages --nocore --instLangs=en_US.UTF-8 --multilib

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_excludes_kickstart_test(self):
        """Test the packages section with excludes."""
        ks_in = """
        %packages
        -vim
        %end
        """
        ks_out = """
        %packages
        -vim

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def packages_section_complex_exclude_kickstart_test(self):
        """Test the packages section with complex exclude example."""
        ks_in = """
        %packages --nocore --ignoremissing
        @^environment1
        @group1
        package1
        -package2
        -@group2
        @group3
        package3
        %end
        """
        ks_out = """
        %packages --nocore --ignoremissing
        @^environment1
        @group1
        @group3
        package1
        package3
        -@group2
        -package2

        %end
        """
        self._test_kickstart(ks_in, ks_out)

    def core_group_enabled_properties_test(self):
        self.package_interface.SetCoreGroupEnabled(True)
        self.assertEqual(self.package_interface.CoreGroupEnabled, True)
        self.callback.assert_called_once_with(
            DNF_PACKAGES.interface_name, {"CoreGroupEnabled": True}, [])
